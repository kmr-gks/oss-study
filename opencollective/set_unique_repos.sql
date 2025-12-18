set client_encoding to UTF8;

BEGIN;

SELECT COUNT(DISTINCT github_account) AS unique_repos
FROM collectives
WHERE github_account LIKE '%/%';

COMMIT;
