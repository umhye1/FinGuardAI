"""Only an isolated finguard_ai_test database is accepted; each test uses a private schema."""

import os
import uuid
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from finguard_ai.errors import StaleDocument
from finguard_ai.repository import CorpusRepository

pytestmark = pytest.mark.integration


@pytest.fixture
def repository():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL for isolated pgvector integration tests")
    assert urlparse(url).path == "/finguard_ai_test", "Refusing a non-test database"
    schema = "ai_test_" + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        root = Path(__file__).parents[2]
        for path in sorted((root / "backend/src/main/resources/db/migration").glob("V*__*.sql")):
            conn.execute(path.read_text())
    pool = ConnectionPool(
        url,
        min_size=0,
        max_size=2,
        open=True,
        kwargs={"row_factory": dict_row, "options": f"-c search_path={schema},public"},
    )
    try:
        yield CorpusRepository(pool)
    finally:
        pool.close()
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def insert_document(repo, content="공식 테스트 문단"):
    with repo.pool.connection() as conn:
        doc = conn.execute("""INSERT INTO documents(title, source, file_path, status, created_at,
            original_file_name, stored_file_name, chunk_count)
            VALUES ('테스트', 'test-only', '/test', 'COMPLETED', now(), 'test.txt', 'test.txt', 1)
            RETURNING document_id""").fetchone()["document_id"]
        conn.execute(
            "INSERT INTO document_chunks(document_id, chunk_index, content, created_at) VALUES (%s, 0, %s, now())",
            (doc, content),
        )
    return doc


def test_vector_upsert_is_idempotent_and_filters_models(repository):
    doc = insert_document(repository)
    chunks = repository.document_chunks(doc)
    v = [1.0] + [0.0] * 767
    repository.publish(doc, chunks, [v], "model-a")
    repository.publish(doc, chunks, [v], "model-a")
    assert repository.has_embeddings("model-a")
    assert not repository.has_embeddings("model-b")
    found = repository.search(v, "model-a", 5, 0.9)
    assert len(found) == 1
    assert found[0].chunk_id == chunks[0].chunk_id
    assert found[0].score == pytest.approx(1.0)
    with repository.pool.connection() as conn:
        assert conn.execute("SELECT count(*) n FROM document_embeddings").fetchone()["n"] == 1


def test_stale_snapshot_never_publishes_and_changed_content_is_not_retrieved(repository):
    doc = insert_document(repository)
    chunks = repository.document_chunks(doc)
    v = [1.0] + [0.0] * 767
    repository.publish(doc, chunks, [v], "model-a")
    with repository.pool.connection() as conn:
        conn.execute("UPDATE document_chunks SET content = '변경된 문단' WHERE document_id = %s", (doc,))
    assert not repository.has_embeddings("model-a")
    assert repository.search(v, "model-a", 5, 0) == []
    with pytest.raises(StaleDocument):
        repository.publish(doc, chunks, [v], "model-a")


def test_processing_document_and_deleted_chunks_are_excluded(repository):
    doc = insert_document(repository)
    chunks = repository.document_chunks(doc)
    v = [1.0] + [0.0] * 767
    repository.publish(doc, chunks, [v], "model-a")
    with repository.pool.connection() as conn:
        conn.execute("UPDATE documents SET status = 'PROCESSING' WHERE document_id = %s", (doc,))
    assert repository.search(v, "model-a", 5, 0) == []
    with pytest.raises(StaleDocument):
        repository.publish(doc, chunks, [v], "model-a")
    with repository.pool.connection() as conn:
        conn.execute("DELETE FROM document_chunks WHERE document_id = %s", (doc,))
        assert conn.execute("SELECT count(*) n FROM document_embeddings").fetchone()["n"] == 0


def test_index_publish_rolls_back_all_vectors_on_invalid_dimension(repository):
    doc = insert_document(repository)
    with repository.pool.connection() as conn:
        conn.execute(
            "INSERT INTO document_chunks(document_id, chunk_index, content, created_at) VALUES (%s, 1, 'second', now())",
            (doc,),
        )
    with pytest.raises(psycopg.Error):
        repository.publish(doc, repository.document_chunks(doc), [[1.0] + [0.0] * 767, [1.0]], "model-a")
    with repository.pool.connection() as conn:
        assert conn.execute("SELECT count(*) n FROM document_embeddings").fetchone()["n"] == 0


def test_official_import_hybrid_policy_and_idempotency(repository):
    from datetime import date

    from finguard_ai.corpus import import_corpus, load_manifest
    from finguard_ai.evidence import select_evidence

    records = list(load_manifest(Path(__file__).parents[1] / "data/official/manifest.json"))
    ids = import_corpus(repository.pool, records)
    assert import_corpus(repository.pool, records) == ids
    # Lexical retrieval works before a paid embedding call; CASE never answers.
    rows = repository.policy_candidates({"transfer", "smishing"}, None, "offline-test", "문자 송금", 0.6)
    decision = select_evidence("문자 송금", rows, today=date(2026, 9, 11))
    assert decision.reason is None
    assert all(c.metadata["kind"] == "OFFICIAL_GUIDANCE" for c in decision.chunks)
    # Exercise actual pgvector + lexical union with intentionally orthogonal test embeddings.
    for doc in ids:
        chunks = repository.document_chunks(doc)
        repository.publish(doc, chunks, [[1.0] + [0.0] * 767], "offline-test")
    rows = repository.policy_candidates({"transfer"}, [1.0] + [0.0] * 767, "offline-test", "송금", 0.6)
    assert len(rows) == 2
    assert all(c.score > 0 for c in rows)
    # Metadata modification is visible to the next retrieval, not an embedding cache.
    with repository.pool.connection() as conn:
        conn.execute(
            "UPDATE documents SET evidence_metadata = "
            "jsonb_set(evidence_metadata::jsonb, '{claims,0,value}', '\"synthetic-conflict\"')::text "
            "WHERE document_id = %s",
            (ids[3],),
        )
    rows = repository.policy_candidates({"transfer"}, [1.0] + [0.0] * 767, "offline-test", "송금", 0.6)
    assert select_evidence("송금", rows, today=date(2026, 9, 11)).reason == "CONFLICTING_EVIDENCE"
