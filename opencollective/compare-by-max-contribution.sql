-- 各プロジェクトについて、最大金額のcontributionを抽出する
-- その最大のコントリビューションの前後のコミット数を比較する。

set client_encoding to UTF8;

COPY (
  WITH max_contribution AS (
    SELECT DISTINCT ON (project_slug)
      project_slug,
      created_at AS funding_time
    FROM collective_transactions
    WHERE kind = 'CONTRIBUTION'
      AND amount_value IS NOT NULL
    ORDER BY project_slug, amount_value DESC, created_at
  ),
  mapped AS (
    SELECT
      mc.project_slug,
      mc.funding_time,
      REPLACE(col.github_account, '/', '-') AS repo_name_key
    FROM max_contribution mc
    JOIN collectives col
      ON col.slug = mc.project_slug
    WHERE col.github_account IS NOT NULL
  ),
  counts AS (
    SELECT
      m.project_slug,
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
    commits_before,
    commits_after,
    commits_after - commits_before AS diff,
    CASE
      WHEN commits_before = 0 THEN NULL
      ELSE commits_after::numeric / commits_before
    END AS ratio
  FROM counts
  ORDER BY diff DESC
) TO STDOUT WITH CSV HEADER;
