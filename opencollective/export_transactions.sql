
COPY (
	SELECT from_account_type, to_account_name, to_account_type, expense_type, expense_tags, description, expense_description
	FROM public.collective_transactions
	WHERE kind = 'EXPENSE' AND amount_currency='USD'
	ORDER BY id ASC
) TO STDOUT WITH CSV HEADER
