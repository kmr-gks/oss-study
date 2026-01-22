-- GitHub リポジトリが特定できた OpenCollective プロジェクトについて、
-- 最初の資金提供（CONTRIBUTION）の前後90日間で、
-- そのリポジトリのコミット数がどれだけ変化したか

set client_encoding to UTF8;

WITH funding AS (
  SELECT project_slug, MIN(created_at) AS funding_time
  FROM collective_transactions
  WHERE kind = 'CONTRIBUTION'
  GROUP BY project_slug
),
mapped AS (
  SELECT
    f.project_slug,
    f.funding_time,
    REPLACE(col.github_account, '/', '-') AS repo_name_key
  FROM funding f
  JOIN collectives col
    ON col.slug = f.project_slug
  WHERE col.github_account IS NOT NULL
),
counts AS (
  SELECT
    m.project_slug,
    m.funding_time,
    COUNT(*) FILTER (
      WHERE c.author_time >= m.funding_time - INTERVAL '90 days'
        AND c.author_time <  m.funding_time
    ) AS commits_before,
    COUNT(*) FILTER (
      WHERE c.author_time >= m.funding_time
        AND c.author_time <  m.funding_time + INTERVAL '90 days'
    ) AS commits_after
  FROM mapped m
  JOIN commit_history c
    ON c.repo_name = m.repo_name_key
  GROUP BY m.project_slug, m.funding_time
)
SELECT
  project_slug,
  funding_time,
  commits_before,
  commits_after,
  (commits_after - commits_before) AS diff,
  CASE WHEN commits_before = 0 THEN NULL
       ELSE commits_after::numeric / commits_before
  END AS ratio
FROM counts
ORDER BY diff DESC;
