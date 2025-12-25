-- psql -U postgres -d opencollective -f .\expense_ranking.sql
set client_encoding to UTF8;

-- 1) to_account_type の頻度ランキング
SELECT
  COALESCE(to_account_type, '[null]') AS to_account_type,
  COUNT(*) AS count
FROM collective_transactions
WHERE kind = 'EXPENSE'
  AND amount_currency = 'USD'
GROUP BY COALESCE(to_account_type, '[null]')
ORDER BY count DESC;

-- 2) to_account_name の頻度ランキング（上位50件）
SELECT
  COALESCE(to_account_name, '[null]') AS to_account_name,
  COUNT(*) AS count
FROM collective_transactions
WHERE kind = 'EXPENSE'
  AND amount_currency = 'USD'
GROUP BY COALESCE(to_account_name, '[null]')
ORDER BY count DESC
LIMIT 20;
