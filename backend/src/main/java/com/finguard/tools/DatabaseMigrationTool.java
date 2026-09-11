package com.finguard.tools;

import org.flywaydb.core.Flyway;
import java.sql.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Explicit operator tool. Run only after a backup has been restored and tested. */
public final class DatabaseMigrationTool {
    private static final Map<String, String> SEQUENCES = Map.of(
            "documents", "document_seq", "analysis_logs", "analysis_logs_seq",
            "chat_sessions", "chat_sessions_seq", "chat_messages", "chat_messages_seq", "audit_logs", "audit_logs_seq");
    private static final Map<String, String> IDS = Map.of(
            "documents", "document_id", "analysis_logs", "analysis_id", "chat_sessions", "session_id",
            "chat_messages", "message_id", "audit_logs", "audit_id");

    public static void main(String[] args) throws Exception {
        String url = required("FG_MIGRATION_URL");
        String user = required("FG_MIGRATION_USER");
        String password = required("FG_MIGRATION_PASSWORD");
        boolean baseline = Arrays.asList(args).contains("--baseline-v1");
        if (baseline && !"true".equals(System.getenv("FG_BACKUP_RESTORE_VERIFIED"))) {
            throw new IllegalArgumentException("Restore a backup first; set FG_BACKUP_RESTORE_VERIFIED=true after verification");
        }
        migrate(url, user, password, baseline);
    }

    public static void migrate(String url, String user, String password, boolean baseline) throws Exception {
        try (Connection lock = DriverManager.getConnection(url, user, password)) {
            lock.createStatement().execute("SELECT pg_advisory_lock(71412027)");
            boolean hasHistory;
            try (ResultSet r = lock.createStatement().executeQuery("SELECT to_regclass('public.flyway_schema_history') IS NOT NULL")) {
                r.next(); hasHistory = r.getBoolean(1);
            }
            if (baseline && !hasHistory) prepareLegacyV1(lock);
            Flyway flyway = Flyway.configure().dataSource(url, user, password).defaultSchema("public")
                    .locations("classpath:db/migration").baselineOnMigrate(false).baselineVersion("1").load();
            if (baseline && !hasHistory) flyway.baseline();
            flyway.migrate();
            flyway.validate();
            System.out.println("MIGRATION_VALIDATED version=" + flyway.info().current().getVersion());
        }
    }

    static void prepareLegacyV1(Connection connection) throws Exception {
        String reference = "migration_reference_" + UUID.randomUUID().toString().replace("-", "");
        connection.setAutoCommit(false);
        try (Statement s = connection.createStatement()) {
            s.execute("SET LOCAL lock_timeout = '5s'");
            s.execute("CREATE SCHEMA " + reference);
            s.execute("SET LOCAL search_path = " + reference);
            String initial;
            try (var stream = DatabaseMigrationTool.class.getResourceAsStream("/db/migration/V1__initial_backend_schema.sql")) {
                initial = new String(Objects.requireNonNull(stream).readAllBytes(), StandardCharsets.UTF_8);
            }
            s.execute(initial);
            Map<String, String> expected = columns(connection, reference);
            if (!expected.equals(columns(connection, "public"))) {
                throw new IllegalStateException("Legacy column layout differs from V1; refusing baseline");
            }
            s.execute("SET LOCAL search_path = public");
            // Exclude application writers while checking/normalizing the legacy layout.
            var tables = new TreeSet<String>();
            expected.keySet().forEach(k -> tables.add(k.substring(0, k.indexOf('.'))));
            s.execute("LOCK TABLE " + String.join(",", tables) + " IN ACCESS EXCLUSIVE MODE");
            verifyKeys(connection, reference);
            try (ResultSet r = s.executeQuery("SELECT 1 FROM document_chunks GROUP BY document_id, chunk_index HAVING count(*) > 1 LIMIT 1")) {
                if (r.next()) throw new IllegalStateException("Duplicate chunk indices; refusing baseline");
            }
            for (var item : SEQUENCES.entrySet()) {
                String table = item.getKey(), sequence = item.getValue(), id = IDS.get(table);
                try (ResultSet r = s.executeQuery("SELECT increment_by FROM pg_sequences WHERE schemaname='public' AND sequencename='" + sequence + "'")) {
                    if (!r.next() || r.getLong(1) != 1) throw new IllegalStateException("Unexpected sequence " + sequence);
                }
                s.execute("ALTER TABLE " + table + " ALTER COLUMN " + id + " SET DEFAULT nextval('" + sequence + "')");
                s.execute("SELECT setval('" + sequence + "', GREATEST((SELECT last_value FROM " + sequence
                        + "), COALESCE((SELECT max(" + id + ") FROM " + table + "), 1)), true)");
            }
            // V1 specifies cascades for these two relationships. Constraint names can differ under Hibernate.
            for (String table : List.of("document_chunks", "chat_messages")) {
                String column = table.equals("document_chunks") ? "document_id" : "session_id";
                String parent = table.equals("document_chunks") ? "documents(document_id)" : "chat_sessions(session_id)";
                List<String> constraints = new ArrayList<>();
                try (ResultSet r = s.executeQuery("SELECT conname FROM pg_constraint WHERE contype='f' AND conrelid='public."
                        + table + "'::regclass")) { while (r.next()) constraints.add(r.getString(1)); }
                for (String name : constraints) s.execute("ALTER TABLE " + table + " DROP CONSTRAINT \"" + name.replace("\"", "\"\"") + "\"");
                s.execute("ALTER TABLE " + table + " ADD FOREIGN KEY (" + column + ") REFERENCES " + parent + " ON DELETE CASCADE");
            }
            s.execute("DROP SCHEMA " + reference + " CASCADE");
            connection.commit();
        } catch (Exception e) {
            connection.rollback();
            throw e;
        } finally { connection.setAutoCommit(true); }
    }

    private static Map<String, String> columns(Connection c, String schema) throws SQLException {
        Map<String, String> result = new TreeMap<>();
        try (PreparedStatement s = c.prepareStatement("SELECT table_name,column_name,data_type,character_maximum_length,is_nullable,is_identity "
                + "FROM information_schema.columns WHERE table_schema=? ORDER BY table_name,column_name")) {
            s.setString(1, schema);
            try (ResultSet r = s.executeQuery()) { while (r.next()) result.put(r.getString(1) + "." + r.getString(2),
                    r.getString(3) + ":" + r.getString(4) + ":" + r.getString(5) + ":" + r.getString(6)); }
        }
        return result;
    }

    private static void verifyKeys(Connection c, String reference) throws SQLException {
        // Constraint names are generated differently. Compare logical definitions, allowing legacy FK delete actions.
        if (!keys(c, reference).equals(keys(c, "public"))) {
            throw new IllegalStateException("Legacy primary/unique/foreign keys differ from V1; refusing baseline");
        }
    }

    private static Set<String> keys(Connection c, String schema) throws SQLException {
        Set<String> result = new TreeSet<>();
        try (PreparedStatement s = c.prepareStatement("SELECT t.relname, pg_get_constraintdef(k.oid) FROM pg_constraint k "
                + "JOIN pg_class t ON t.oid=k.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace "
                + "WHERE n.nspname=? AND k.contype IN ('p','u','f')")) {
            s.setString(1, schema);
            try (ResultSet r = s.executeQuery()) { while (r.next()) result.add(r.getString(1) + ":"
                    + r.getString(2).replace(schema + ".", "").replace("public.", "").replace(" ON DELETE CASCADE", "")); }
        }
        return result;
    }

    private static String required(String key) {
        String value = System.getenv(key);
        if (value == null || value.isBlank()) throw new IllegalArgumentException(key + " required");
        return value;
    }
}
