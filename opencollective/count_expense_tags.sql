SELECT expense_tags, COUNT(*) AS count
FROM collective_transactions
group by expense_tags

ORDER BY count DESC
LIMIT 20;
