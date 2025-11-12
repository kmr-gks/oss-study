-- ===============================
-- Create table: collective_transactions
-- ===============================

\connect opencollective

DROP TABLE IF EXISTS collective_transactions;

CREATE TABLE collective_transactions (
    id TEXT PRIMARY KEY,
    project_slug TEXT,
    project_name TEXT,
    type TEXT,                 -- CREDIT or DEBIT
    kind TEXT,                 -- CONTRIBUTION, EXPENSE, HOST_FEE, etc.
    description TEXT,
    created_at TIMESTAMP,
    amount_value NUMERIC,
    amount_currency TEXT,
    from_account_slug TEXT,
    from_account_name TEXT,
    from_account_type TEXT,
    to_account_slug TEXT,
    to_account_name TEXT,
    to_account_type TEXT
);

CREATE INDEX IF NOT EXISTS idx_collective_transactions_project_slug ON collective_transactions(project_slug);
CREATE INDEX IF NOT EXISTS idx_collective_transactions_created_at ON collective_transactions(created_at);

\echo 'Table "collective_transactions" created successfully.'
