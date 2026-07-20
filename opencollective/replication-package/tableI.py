import api
import pandas as pd
from sqlalchemy import create_engine
from duckdb_util import database_engine

COLLECTIVES_SQL = "data/collectives.parquet"
COLLECTIVE_TRANSACTIONS_SQL = "data/collective_transactions.parquet"
COMMIT_HISTORY = "data/commit_history.parquet"
GITHUB_ISSUE_PR_ITEMS = "data/github_issue_pr_items.parquet"

DB_NAME = "opencollective"
engine = database_engine()

results = []

sql_query = "SELECT count(*) as count, type FROM public.collectives GROUP BY type"
df = pd.read_sql(sql_query, engine)
results.append(["Collectives", df[df["type"] == "COLLECTIVE"]["count"].values[0]])
results.append(["Projects", df[df["type"] == "PROJECT"]["count"].values[0]])

sql_query = "SELECT count(*) as count FROM public.collective_transactions"
df = pd.read_sql(sql_query, engine)
results.append(["Transactions", df["count"].values[0]])

sql_query = "SELECT count(DISTINCT repo_name) as count FROM public.commit_history"
df = pd.read_sql(sql_query, engine)
results.append(["Repositories with commit histories", df["count"].values[0]])

sql_query = "SELECT count(DISTINCT repo_name) as count FROM public.github_issue_pr_items"
df = pd.read_sql(sql_query, engine)
results.append(["Repositories with issue/pr histories", df["count"].values[0]])

sql_query = "SELECT count(*) as count FROM public.github_issue_pr_items"
df = pd.read_sql(sql_query, engine)
results.append(["Issue and pull request records", df["count"].values[0]])

result = pd.DataFrame(results, columns=["Item", "Count"])
result.to_csv("table_i.csv", index=False)

print("TABLE I")
print(result.to_string(index=False))

engine.dispose()
