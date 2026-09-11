-- Ordinary uploads remain unreviewed. Only the validated corpus importer sets metadata.
ALTER TABLE documents ADD COLUMN evidence_metadata TEXT;
CREATE UNIQUE INDEX documents_corpus_id ON documents ((CAST(evidence_metadata AS jsonb)->>'corpus_id'))
 WHERE evidence_metadata IS NOT NULL;

ALTER TABLE chat_messages ADD COLUMN reason_code VARCHAR(100);
ALTER TABLE chat_messages ADD COLUMN policy_version VARCHAR(100);
