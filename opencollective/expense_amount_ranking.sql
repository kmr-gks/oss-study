-- psql -U postgres -d opencollective -f .\expense_amount_ranking.sql
set client_encoding to UTF8;

-- 1) to_account_type 別：支出総額ランキング
SELECT
  COALESCE(to_account_type, '[null]') AS to_account_type,
  SUM(amount_value) AS total_amount_value
FROM collective_transactions
WHERE kind = 'EXPENSE'
  AND amount_currency = 'USD'
GROUP BY COALESCE(to_account_type, '[null]')
ORDER BY ABS(SUM(amount_value)) DESC;

-- 2) to_account_name 別：支出総額ランキング（上位20件）
SELECT
  COALESCE(to_account_name, '[null]') AS to_account_name,
  SUM(amount_value) AS total_amount_value
FROM collective_transactions
WHERE kind = 'EXPENSE'
  AND amount_currency = 'USD'
GROUP BY COALESCE(to_account_name, '[null]')
ORDER BY ABS(SUM(amount_value)) DESC
LIMIT 20;
