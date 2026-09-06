-- Requires pgvector on the PostgreSQL server. Enable explicitly through Flyway.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE document_embeddings (
    chunk_id BIGINT NOT NULL REFERENCES document_chunks(chunk_id) ON DELETE CASCADE,
    embedding_model VARCHAR(100) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    embedding VECTOR(768) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (chunk_id, embedding_model)
);
-- Exact cosine search first. Add ANN indexes only after measuring recall/latency tradeoffs.
CREATE INDEX idx_embeddings_model ON document_embeddings(embedding_model);
