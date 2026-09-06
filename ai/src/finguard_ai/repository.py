import hashlib
import json
from dataclasses import dataclass

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from finguard_ai.errors import StaleDocument


@dataclass(frozen=True)
class Chunk:
    chunk_id: int
    document_id: int
    title: str
    content: str
    score: float = 0

    @property
    def content_hash(self):
        return hashlib.sha256(self.content.encode()).hexdigest()


class CorpusRepository:
    def __init__(self, pool: ConnectionPool):
        self.pool = pool

    def ready(self):
        with self.pool.connection() as conn:
            conn.execute("SELECT chunk_id FROM document_embeddings LIMIT 0")

    def document_chunks(self, document_id: int) -> list[Chunk]:
        with self.pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT c.chunk_id, d.document_id, d.title, c.content
                FROM document_chunks c JOIN documents d USING(document_id)
                WHERE d.document_id = %s AND d.status = 'COMPLETED'
                ORDER BY c.chunk_index
            """,
                (document_id,),
            ).fetchall()
        return [Chunk(**r) for r in rows]

    def has_embeddings(self, model: str) -> bool:
        with self.pool.connection() as conn:
            return bool(
                conn.execute(
                    """
                SELECT 1 FROM document_embeddings e
                JOIN document_chunks c USING(chunk_id) JOIN documents d USING(document_id)
                WHERE d.status = 'COMPLETED' AND e.embedding_model = %s
                  AND e.content_hash = encode(sha256(convert_to(c.content, 'UTF8')), 'hex') LIMIT 1
            """,
                    (model,),
                ).fetchone()
            )

    def publish(self, document_id: int, snapshot: list[Chunk], vectors: list[list[float]], model: str):
        if not snapshot or len(snapshot) != len(vectors):
            raise ValueError("Invalid index snapshot")
        with self.pool.connection() as conn:
            # Serialize with Spring's completion/deletion lock; provider work has already finished.
            doc = conn.execute(
                "SELECT status FROM documents WHERE document_id = %s FOR UPDATE", (document_id,)
            ).fetchone()
            if not doc or doc["status"] != "COMPLETED":
                raise StaleDocument("Document no longer complete")
            current = conn.execute(
                "SELECT chunk_id, content FROM document_chunks WHERE document_id = %s ORDER BY chunk_index",
                (document_id,),
            ).fetchall()
            if [(r["chunk_id"], r["content"]) for r in current] != [
                (c.chunk_id, c.content) for c in snapshot
            ]:
                raise StaleDocument("Document changed during indexing")
            for chunk, vector in zip(snapshot, vectors):
                conn.execute(
                    """
                    INSERT INTO document_embeddings (chunk_id, embedding_model, content_hash, embedding)
                    VALUES (%s, %s, %s, %s::vector)
                    ON CONFLICT (chunk_id, embedding_model) DO UPDATE
                    SET content_hash = EXCLUDED.content_hash, embedding = EXCLUDED.embedding, updated_at = now()
                """,
                    (chunk.chunk_id, model, chunk.content_hash, json.dumps(vector, allow_nan=False)),
                )

    def search(self, vector: list[float], model: str, limit: int, min_score: float) -> list[Chunk]:
        with self.pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT c.chunk_id, d.document_id, d.title, c.content,
                       1 - (e.embedding <=> %s::vector) AS score
                FROM document_embeddings e JOIN document_chunks c USING(chunk_id)
                JOIN documents d USING(document_id)
                WHERE d.status = 'COMPLETED' AND e.embedding_model = %s
                  AND e.content_hash = encode(sha256(convert_to(c.content, 'UTF8')), 'hex')
                  AND 1 - (e.embedding <=> %s::vector) >= %s
                ORDER BY e.embedding <=> %s::vector, c.chunk_id LIMIT %s
            """,
                (json.dumps(vector), model, json.dumps(vector), min_score, json.dumps(vector), limit),
            ).fetchall()
        return [Chunk(**r) for r in rows]


def make_pool(url: str, size: int = 4) -> ConnectionPool:
    return ConnectionPool(
        url,
        min_size=0,
        max_size=size,
        timeout=3,
        max_waiting=16,
        kwargs={
            "row_factory": dict_row,
            "connect_timeout": 3,
            "options": "-c statement_timeout=3000 -c lock_timeout=2000",
        },
        open=False,
    )
