package com.finguard.tools;

import org.junit.jupiter.api.*;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.*;
import org.testcontainers.utility.DockerImageName;
import java.sql.*;
import java.nio.charset.StandardCharsets;
import static org.assertj.core.api.Assertions.*;

@Testcontainers
class DatabaseMigrationToolTest {
    @Container static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>(
            DockerImageName.parse("pgvector/pgvector:pg16").asCompatibleSubstituteFor("postgres"));
    Connection connect() throws SQLException { return DriverManager.getConnection(postgres.getJdbcUrl(), postgres.getUsername(), postgres.getPassword()); }
    @BeforeEach void legacy() throws Exception {
        try (Connection c=connect(); Statement s=c.createStatement()) {
            s.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public");
            try (var stream=getClass().getResourceAsStream("/db/migration/V1__initial_backend_schema.sql")) {
                s.execute(new String(stream.readAllBytes(), StandardCharsets.UTF_8));
            }
            s.execute("ALTER TABLE documents ALTER COLUMN document_id DROP DEFAULT");
            s.execute("INSERT INTO documents(document_id,title,source,file_path,status,created_at,original_file_name,stored_file_name,chunk_count) "
                    + "VALUES (80,'legacy','test','/test','COMPLETED',now(),'test.txt','test.txt',1)");
            s.execute("INSERT INTO document_chunks(document_id,chunk_index,content,created_at) VALUES (80,0,'original content',now())");
        }
    }
    void migrate() throws Exception { DatabaseMigrationTool.migrate(postgres.getJdbcUrl(), postgres.getUsername(), postgres.getPassword(), true); }
    @Test void preservesLegacyRowsAndAdvancesSequenceThenValidatesRerun() throws Exception {
        migrate(); migrate();
        try (Connection c=connect(); Statement s=c.createStatement()) {
            try (ResultSet r=s.executeQuery("SELECT content FROM document_chunks WHERE document_id=80")) { r.next(); assertThat(r.getString(1)).isEqualTo("original content"); }
            try (ResultSet r=s.executeQuery("SELECT nextval('document_seq')")) { r.next(); assertThat(r.getLong(1)).isGreaterThan(80); }
            try (ResultSet r=s.executeQuery("SELECT max(version::int) FROM flyway_schema_history WHERE type <> 'BASELINE'")) { r.next(); assertThat(r.getInt(1)).isEqualTo(7); }
        }
    }
    @Test void rejectsUnknownColumnsWithoutBaselining() throws Exception {
        try (Connection c=connect()) { c.createStatement().execute("ALTER TABLE documents ADD COLUMN unknown_data TEXT"); }
        assertThatThrownBy(this::migrate).isInstanceOf(IllegalStateException.class).hasMessageContaining("column layout");
        assertNoHistory();
    }
    @Test void rejectsDuplicateChunksWithoutDeletingThem() throws Exception {
        try (Connection c=connect()) { c.createStatement().execute("INSERT INTO document_chunks(document_id,chunk_index,content,created_at) VALUES (80,0,'duplicate',now())"); }
        assertThatThrownBy(this::migrate).isInstanceOf(IllegalStateException.class).hasMessageContaining("Duplicate");
        assertNoHistory();
        try (Connection c=connect(); ResultSet r=c.createStatement().executeQuery("SELECT count(*) FROM document_chunks")) { r.next(); assertThat(r.getInt(1)).isEqualTo(2); }
    }
    void assertNoHistory() throws Exception {
        try (Connection c=connect(); ResultSet r=c.createStatement().executeQuery("SELECT to_regclass('public.flyway_schema_history')")) { r.next(); assertThat(r.getString(1)).isNull(); }
    }
}
