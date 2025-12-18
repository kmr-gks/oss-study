-- psql -U postgres -d opencollective -f .\count_expense_type.sql
set client_encoding to UTF8;

SELECT
  COALESCE(expense_description, '[null]') AS expense_description,
  COUNT(*) AS count
FROM collective_transactions
GROUP BY COALESCE(expense_description, '[null]')
ORDER BY count DESC
LIMIT 20;
