-- 各プロジェクトについて、最大の支出(expenseは負なので正確には最小値)を抽出する
-- その最大のexpenseの前後30/180日間のコミット数を比較する

-- set client_encoding to UTF8;

COPY (
  WITH max_contribution_row AS (
    SELECT
      project_slug,
      created_at AS funding_time,
      amount_value AS max_contribution_usd
    FROM (
      SELECT
        project_slug,
        created_at,
        amount_value,
        ROW_NUMBER() OVER (
          PARTITION BY project_slug
          ORDER BY amount_value ASC, created_at ASC
        ) AS rn
      FROM collective_transactions
      WHERE kind = 'EXPENSE'
        AND to_account_type = 'INDIVIDUAL'
        AND amount_currency = 'USD'
    ) t
    WHERE rn = 1
  ),
  mapped AS (
    SELECT
      mcr.project_slug,
      mcr.funding_time,
      mcr.max_contribution_usd,
      REPLACE(col.github_account, '/', '-') AS repo_name_key
    FROM max_contribution_row mcr
    JOIN collectives col
      ON col.slug = mcr.project_slug
    WHERE col.github_account IS NOT NULL
  ),
  counts AS (
    SELECT
      m.project_slug,
      m.funding_time,
      m.max_contribution_usd,
      COUNT(*) FILTER (
        WHERE c.author_time >= m.funding_time - INTERVAL '30 days'
          AND c.author_time <  m.funding_time
      ) AS commits_before,
      COUNT(*) FILTER (
        WHERE c.author_time >= m.funding_time
          AND c.author_time <  m.funding_time + INTERVAL '30 days'
      ) AS commits_after
    FROM mapped m
    JOIN commit_history c
      ON c.repo_name = m.repo_name_key
    GROUP BY m.project_slug, m.funding_time, m.max_contribution_usd
  )
  SELECT
    project_slug,
    funding_time,
    max_contribution_usd,
    commits_before,
    commits_after,
    commits_after - commits_before AS diff,
    CASE
      WHEN commits_before = 0 THEN NULL
      ELSE commits_after::numeric / commits_before
    END AS ratio
  FROM counts
  ORDER BY project_slug DESC
) TO STDOUT WITH CSV HEADER;
