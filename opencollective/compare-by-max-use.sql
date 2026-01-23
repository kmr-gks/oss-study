WITH max_expense AS (
  SELECT
    project_slug,
    MAX(amount_value) AS max_expense_usd
  FROM collective_transactions
  WHERE kind = 'EXPENSE'
    AND amount_currency = 'USD'
  GROUP BY project_slug
),
expense_event AS (
  SELECT
    t.project_slug,
    t.created_at AS expense_time,
    t.amount_value AS max_expense_usd
  FROM collective_transactions t
  JOIN max_expense m
    ON t.project_slug = m.project_slug
   AND t.amount_value = m.max_expense_usd
  WHERE t.kind = 'EXPENSE'
    AND t.amount_currency = 'USD'
),
mapped AS (
  SELECT
    e.project_slug,
    e.expense_time,
    e.max_expense_usd,
    REPLACE(c.github_account, '/', '-') AS repo_name_key
  FROM expense_event e
  JOIN collectives c
    ON c.slug = e.project_slug
  WHERE c.github_account IS NOT NULL
),
counts AS (
  SELECT
    m.project_slug,
    m.expense_time,
    m.max_expense_usd,
    COUNT(*) FILTER (
      WHERE c.author_time >= m.expense_time - INTERVAL '30 days'
        AND c.author_time <  m.expense_time
    ) AS commits_before,
    COUNT(*) FILTER (
      WHERE c.author_time >= m.expense_time
        AND c.author_time <  m.expense_time + INTERVAL '30 days'
    ) AS commits_after
  FROM mapped m
  JOIN commit_history c
    ON c.repo_name = m.repo_name_key
  GROUP BY m.project_slug, m.expense_time, m.max_expense_usd
)
SELECT
  project_slug,
  expense_time,
  max_expense_usd,
  commits_before,
  commits_after,
  (commits_after - commits_before) AS diff,
  CASE
    WHEN commits_before = 0 THEN NULL
    ELSE commits_after::numeric / commits_before
  END AS ratio
FROM counts
ORDER BY expense_time;
