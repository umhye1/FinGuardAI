-- Separate from active search embeddings: survives chunk-ID recreation, not document deletion.
-- A profile identifies provider/model/revision/input processing/task/dimensions.
CREATE TABLE document_embedding_cache (
    document_id BIGINT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    profile_hash VARCHAR(64) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    embedding VECTOR(768) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, profile_hash, content_hash)
);
-- No backfill from document_embeddings: legacy vectors have no provider/revision provenance.
