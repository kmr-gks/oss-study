-- 1. データベース作成（存在しない場合のみ）
CREATE DATABASE opencollective;

-- 2. 対象DBに接続
\connect opencollective

-- 3. 旧テーブル削除（必要なら）
DROP TABLE IF EXISTS collectives;

-- 4. 新テーブル作成
CREATE TABLE collectives (
    -- 基本情報
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    name TEXT,
    type TEXT,
    created_at TIMESTAMP,
    is_active BOOLEAN,
    description TEXT,
    website TEXT,
    github_handle TEXT,
    twitter_handle TEXT,
    social_links JSONB,

    -- 財務統計情報
    balance_value NUMERIC,
    balance_currency TEXT,
    total_received_value NUMERIC,
    total_received_currency TEXT,
    total_spent_value NUMERIC,
    total_spent_currency TEXT,
    yearly_budget_value NUMERIC,
    yearly_budget_currency TEXT,

    -- メタ情報
    host_slug TEXT DEFAULT 'opensource'
);

-- 5. インデックス作成
CREATE INDEX IF NOT EXISTS idx_collectives_slug ON collectives(slug);
CREATE INDEX IF NOT EXISTS idx_collectives_created_at ON collectives(created_at);
CREATE INDEX IF NOT EXISTS idx_collectives_balance_value ON collectives(balance_value);

\echo 'Table "collectives" created successfully'
