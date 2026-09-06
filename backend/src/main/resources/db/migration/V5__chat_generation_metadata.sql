ALTER TABLE chat_messages ADD COLUMN generation_status VARCHAR(30);
ALTER TABLE chat_messages ADD COLUMN model_version VARCHAR(100);
ALTER TABLE chat_messages ADD COLUMN prompt_version VARCHAR(100);
