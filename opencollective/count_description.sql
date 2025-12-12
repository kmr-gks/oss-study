-- psql -U postgres -d opencollective -f .\count_description.sql
set client_encoding to UTF8;

SELECT
  COALESCE(description, '[null]') AS description,
  COUNT(*) AS count
FROM collective_transactions
GROUP BY COALESCE(description, '[null]')
ORDER BY count DESC;
