-- psql -U postgres -d opencollective -f .\count_kind.sql
set client_encoding to UTF8;

SELECT
  COALESCE(kind, '[null]') AS kind,
  COUNT(*) AS count,
  SUM(amount_value) AS total_amount_value
FROM collective_transactions
WHERE amount_currency = 'USD'
GROUP BY COALESCE(kind, '[null]')
ORDER BY count DESC
LIMIT 20;
