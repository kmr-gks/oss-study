-- 1. データベースを作成（既に存在する場合はスキップ）
--    この部分は "postgres" データベースで実行してください。
CREATE DATABASE opencollective;

-- 2. 対象DBに接続
\connect opencollective

-- 3. テーブル作成
--    親Collective情報を含む最新版
DROP TABLE IF EXISTS projects;

CREATE TABLE projects (
    -- 基本情報
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    name TEXT,
    type TEXT,
    created_at TIMESTAMP,
    is_active BOOLEAN,
    website TEXT,
    github_handle TEXT,
    twitter_handle TEXT,
    social_links JSONB,

    -- 財務情報（Amount.valueは小数を扱うのでNUMERIC）
    stats_id TEXT,
    balance_value NUMERIC,
    balance_currency TEXT,
    total_received_value NUMERIC,
    total_received_currency TEXT,
    total_spent_value NUMERIC,
    total_spent_currency TEXT,
    yearly_budget_value NUMERIC,
    yearly_budget_currency TEXT,

    -- 追加予算情報
    monthly_spending_value NUMERIC,
    monthly_spending_currency TEXT,
    total_paid_expenses_value NUMERIC,
    total_paid_expenses_currency TEXT,
    managed_amount_value NUMERIC,
    managed_amount_currency TEXT,

    -- 寄付統計
    contributors_count INT,
    contributions_count INT

    -- 親Collective情報
    parent_id TEXT,
    parent_slug TEXT,
    parent_name TEXT,
    parent_github_handle TEXT,
);

-- 4. インデックス作成（検索高速化）
CREATE INDEX IF NOT EXISTS idx_projects_slug ON projects(slug);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at);
CREATE INDEX IF NOT EXISTS idx_projects_balance_value ON projects(balance_value);
CREATE INDEX IF NOT EXISTS idx_projects_parent_slug ON projects(parent_slug);

\echo '✅ Table "projects" (with parent info) created successfully'
