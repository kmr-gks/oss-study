-- psql -U postgres -d opencollective -f .\count_kind.sql
set client_encoding to UTF8;

SELECT
  COALESCE(kind, '[null]') AS kind,
  COUNT(*) AS count
FROM collective_transactions
GROUP BY COALESCE(kind, '[null]')
ORDER BY count DESC;
