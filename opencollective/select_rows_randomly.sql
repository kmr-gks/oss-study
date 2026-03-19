copy(
SELECT * FROM collective_transactions
where kind = 'EXPENSE'
ORDER BY random()
limit 381
) to STDOUT with csv header;
