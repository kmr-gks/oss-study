SELECT expense_tags, COUNT(*) AS count
FROM collective_transactions
where kind = 'EXPENSE'
group by expense_tags

ORDER BY count DESC
LIMIT 20;
