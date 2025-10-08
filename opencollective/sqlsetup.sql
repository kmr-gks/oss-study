-- 1. データベースを作成（既に存在する場合はスキップ）
--    この部分は "postgres" データベースで実行してください。
CREATE DATABASE opencollective;


-- 1. 接続
\connect opencollective

-- 2. テーブル作成
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    name TEXT,
    type TEXT,
    created_at TIMESTAMP,
    is_active BOOLEAN,
    balance_value NUMERIC,
    balance_currency TEXT,
    total_received_value NUMERIC,
    total_received_currency TEXT,
    total_spent_value NUMERIC,
    total_spent_currency TEXT,
    yearly_budget_value NUMERIC,
    yearly_budget_currency TEXT
);

-- 3. インデックス作成
CREATE INDEX IF NOT EXISTS idx_projects_slug ON projects(slug);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at);

\echo 'Table "projects" created successfully.'
