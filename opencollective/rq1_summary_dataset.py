import api
import pandas as pd
from sqlalchemy import create_engine

DB_NAME = "opencollective"
engine = create_engine(
    f"postgresql+psycopg2://postgres:{api.load_sql_password_from_credentials()}@localhost:5432/{DB_NAME}"
)
print("TABLE I")

sql_query = """
SELECT count(*),type FROM public.collectives group by type 
"""
df=pd.read_sql(sql_query, engine)
print(f"Collectives: {df[df['type']=='COLLECTIVE']['count'].values[0]}")
print(f"Projects: {df[df['type']=='PROJECT']['count'].values[0]}")

sql_query = """
SELECT count(*) FROM public.collective_transactions
"""
df=pd.read_sql(sql_query, engine)
print(f"Transactions: {df['count'].values[0]}")

sql_query = """
SELECT count(distinct(repo_name)) FROM public.commit_history
"""
df=pd.read_sql(sql_query, engine)
print(f"Repositories with commit histories: {df['count'].values[0]}")

sql_query = """
SELECT count(distinct(repo_name)) FROM public.github_issue_pr_items
"""
df=pd.read_sql(sql_query, engine)
print(f"Repositories with issue/pr histories: {df['count'].values[0]}")

sql_query = """
SELECT count(*) FROM public.github_issue_pr_items
"""
df=pd.read_sql(sql_query, engine)
print(f"Issue and pull request records: {df['count'].values[0]}")



print("TABLE III")

sql_query = """
SELECT kind,count(*) as count, sum(amount_value) as amount FROM public.collective_transactions group by kind
"""
df=pd.read_sql(sql_query, engine)
count_sum, amount_sum = df['count'].sum(), df['amount'].sum()
for kind in ['CONTRIBUTION','HOST_FEE','PAYMENT_PROCESSOR_FEE','EXPENSE','ADDED_FUNDS']:
    count, amount = df[df['kind']==kind]['count'].values[0], df[df['kind']==kind]['amount'].values[0]
    print(f"{kind}: {count}, {amount/1e6:.2f}M")
    count_sum -= count
    amount_sum -= amount
print(f"Others: {count_sum}, {amount_sum/1e6:.2f}M")
