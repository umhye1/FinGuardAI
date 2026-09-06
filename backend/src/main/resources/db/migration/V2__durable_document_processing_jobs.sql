CREATE TABLE processing_jobs (
 job_id UUID PRIMARY KEY, document_id BIGINT NOT NULL REFERENCES documents ON DELETE CASCADE,
 owner_id BIGINT NOT NULL REFERENCES users, status VARCHAR(255) NOT NULL,
 attempts INTEGER NOT NULL, error_code VARCHAR(255), lease_token UUID,
 lease_until TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_jobs_claim ON processing_jobs(status, lease_until, created_at);
CREATE UNIQUE INDEX uq_active_document_job ON processing_jobs(document_id) WHERE status IN ('PENDING', 'RUNNING');
CREATE UNIQUE INDEX uq_document_chunk_index ON document_chunks(document_id, chunk_index);
CREATE INDEX idx_analysis_user_created ON analysis_logs(user_id, created_at DESC);
CREATE INDEX idx_chat_messages_session_created ON chat_messages(session_id, created_at);
