-- Conversation audit log ("black box"): every agent Q&A — what it said, and
-- whether it could actually answer (status). Additive + safe: creates ONE new
-- table and two indexes; touches nothing existing. Run once in Supabase SQL Editor.

CREATE TABLE IF NOT EXISTS chat_logs (
    id          BIGSERIAL   PRIMARY KEY,
    project_id  TEXT        NOT NULL,
    session_id  TEXT,
    question    TEXT        NOT NULL,
    answer      TEXT        NOT NULL,
    tools_used  TEXT        DEFAULT '',
    status      TEXT        NOT NULL DEFAULT 'answered'
                            CHECK (status IN ('answered', 'no_info')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Hot path: a project's history, newest first, optionally filtered by status.
CREATE INDEX IF NOT EXISTS chat_logs_project_created_idx
    ON chat_logs (project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS chat_logs_status_idx
    ON chat_logs (project_id, status);

-- Match the access pattern of the other tables (the app writes via the service key).
ALTER TABLE chat_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access" ON chat_logs FOR ALL USING (true) WITH CHECK (true);
