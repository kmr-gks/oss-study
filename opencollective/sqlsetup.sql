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

-- 既存のテーブルに新しい列を追加
ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS monthly_spending_value NUMERIC,
  ADD COLUMN IF NOT EXISTS monthly_spending_currency TEXT,
  ADD COLUMN IF NOT EXISTS total_paid_expenses_value NUMERIC,
  ADD COLUMN IF NOT EXISTS total_paid_expenses_currency TEXT,
  ADD COLUMN IF NOT EXISTS managed_amount_value NUMERIC,
  ADD COLUMN IF NOT EXISTS managed_amount_currency TEXT,
  ADD COLUMN IF NOT EXISTS contributors_count INT,
  ADD COLUMN IF NOT EXISTS contributions_count INT;

\echo 'Table "projects" created successfully.'
