-- ===============================
-- Create table: collective_expenses
-- ===============================

\connect opencollective

DROP TABLE IF EXISTS collective_expenses;

CREATE TABLE collective_expenses (
    id TEXT PRIMARY KEY,
    project_slug TEXT,
    project_name TEXT,
    type TEXT,              -- INVOICE / RECEIPT / GRANT / etc.
    description TEXT,
    amount_value NUMERIC,
    amount_currency TEXT,
    created_at TIMESTAMP,
    incurred_at TIMESTAMP,
    tags JSONB,
    payee_name TEXT,
    payee_slug TEXT,
    status TEXT             -- APPROVED / PAID / REJECTED / etc.
);

CREATE INDEX IF NOT EXISTS idx_collective_expenses_project_slug ON collective_expenses(project_slug);
CREATE INDEX IF NOT EXISTS idx_collective_expenses_created_at ON collective_expenses(created_at);

\echo 'Table "collective_expenses" created successfully.'
