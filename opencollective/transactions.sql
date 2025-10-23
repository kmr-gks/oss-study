-- transactionsテーブル
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    project_slug TEXT NOT NULL,
    project_name TEXT,
    type TEXT,                  -- CREDIT / DEBIT
    description TEXT,           -- 理由（例: hire person, pay advertisement）
    created_at TIMESTAMP,       -- 取引日時
    amount_value NUMERIC,
    amount_currency TEXT,
    from_account_slug TEXT,
    from_account_name TEXT,
    to_account_slug TEXT,
    to_account_name TEXT
);

-- 索引（よく使うフィールドに）
CREATE INDEX IF NOT EXISTS idx_transactions_project_slug ON transactions(project_slug);
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at);
