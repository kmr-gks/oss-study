-- psql -U postgres -d opencollective -f .\count_expense_type.sql
set client_encoding to UTF8;

SELECT
  COALESCE(expense_type, '[null]') AS expense_type,
  COUNT(*) AS count
FROM collective_transactions
GROUP BY COALESCE(expense_type, '[null]')
ORDER BY count DESC
LIMIT 20;
