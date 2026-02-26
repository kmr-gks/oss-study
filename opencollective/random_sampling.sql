copy (
  SELECT
    id,
    project_slug,
    project_name,
    created_at,
    amount_value,
    from_account_type,
    to_account_type,
    to_account_name,
    expense_type,
    expense_description,
    expense_tags,
    description
  FROM collective_transactions
  WHERE kind = 'EXPENSE' and amount_currency = 'USD'
  ORDER BY random()
  LIMIT 100
) TO STDOUT WITH CSV HEADER;
