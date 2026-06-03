set client_encoding to 'UTF8';

\echo 'all expenses in USD';
select sum(abs(amount_value)) from public.collective_transactions
where kind='EXPENSE' and amount_currency='USD';

\echo 'average expense in USD';
select avg(abs(amount_value)) from public.collective_transactions
where kind='EXPENSE' and amount_currency='USD';

\echo 'median expense in USD';
select percentile_cont(0.5) within group (order by abs(amount_value)) from public.collective_transactions
where kind='EXPENSE' and amount_currency='USD';

\echo 'top 1% expenses in USD';
select percentile_cont(0.99) within group (order by abs(amount_value)) from public.collective_transactions
where kind='EXPENSE' and amount_currency='USD';

\echo 'all contributions in USD';
select sum(abs(amount_value)) from public.collective_transactions
where kind='CONTRIBUTION' and amount_currency='USD';

\echo 'average contribution in USD';
select avg(abs(amount_value)) from public.collective_transactions
where kind='CONTRIBUTION' and amount_currency='USD';

\echo 'median contribution in USD';
select percentile_cont(0.5) within group (order by abs(amount_value)) from public.collective_transactions
where kind='CONTRIBUTION' and amount_currency='USD';

\echo 'top 1% contributions in USD';
select percentile_cont(0.99) within group (order by abs(amount_value)) from public.collective_transactions
where kind='CONTRIBUTION' and amount_currency='USD';

