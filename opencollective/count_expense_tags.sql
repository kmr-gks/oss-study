-- psql -U postgres -d opencollective -f .\count_expense_tags.sql
set client_encoding to UTF8;

-- 1. count each tag in expense_tags
WITH tag_counts AS (
    SELECT jsonb_array_elements_text(expense_tags) AS tag
    FROM collective_transactions
    WHERE expense_tags IS NOT NULL
      AND jsonb_array_length(expense_tags) > 0
),

-- 2. count empty tags
empty_counts AS (
    SELECT '[]' AS tag, COUNT(*) AS count
    FROM collective_transactions
    WHERE expense_tags IS NOT NULL
      AND jsonb_array_length(expense_tags) = 0
)

-- 3. final selection
SELECT tag, COUNT(*) AS count
FROM tag_counts
GROUP BY tag

UNION ALL

SELECT tag, count
FROM empty_counts

ORDER BY count DESC;
