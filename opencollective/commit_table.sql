set client_encoding to UTF8;

\connect opencollective

DROP TABLE IF EXISTS commit_history;

CREATE TABLE commit_history (
    repo_path TEXT NOT NULL,              -- local path (unique identifier in your environment)
    repo_name TEXT,                       -- directory name
    commit_hash TEXT NOT NULL,            -- SHA
    parent_hashes TEXT,                   -- space-separated parents (merge detection)
    author_name TEXT,
    author_email TEXT,
    author_time TIMESTAMP,               -- author date
    committer_name TEXT,
    committer_email TEXT,
    commit_time TIMESTAMP,               -- commit date
    subject TEXT,                         -- first line of message
    body TEXT,                            -- rest of message (optional but often useful)
    files_changed INT,                    -- lightweight stats (optional)
    insertions INT,
    deletions INT,
    mined_at TIMESTAMP NOT NULL DEFAULT now(),

    PRIMARY KEY (repo_path, commit_hash)
);

CREATE INDEX IF NOT EXISTS idx_commit_history_repo_path ON commit_history(repo_path);
CREATE INDEX IF NOT EXISTS idx_commit_history_commit_time ON commit_history(commit_time);
CREATE INDEX IF NOT EXISTS idx_commit_history_author_time ON commit_history(author_time);
CREATE INDEX IF NOT EXISTS idx_commit_history_author_email ON commit_history(author_email);

\echo 'Table "commit_history" created successfully.'
