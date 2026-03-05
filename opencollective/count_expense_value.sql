SELECT
    expense_tags,
    COUNT(*) AS n_records,
    SUM(-amount_value) AS total_usd
FROM collective_transactions ct
WHERE kind = 'EXPENSE' and amount_currency = 'USD'
GROUP BY expense_tags
ORDER BY total_usd DESC
limit 20;
