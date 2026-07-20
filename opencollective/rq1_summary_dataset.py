import api
import pandas as pd
from sqlalchemy import create_engine

DB_NAME = "opencollective"
engine = create_engine(
	f"postgresql+psycopg2://postgres:{api.load_sql_password_from_credentials()}@localhost:5432/{DB_NAME}"
)

results = []

sql_query = "SELECT count(*), type FROM public.collectives GROUP BY type"
df = pd.read_sql(sql_query, engine)
results.append(["Collectives", df[df["type"] == "COLLECTIVE"]["count"].values[0]])
results.append(["Projects", df[df["type"] == "PROJECT"]["count"].values[0]])

sql_query = "SELECT count(*) FROM public.collective_transactions"
df = pd.read_sql(sql_query, engine)
results.append(["Transactions", df["count"].values[0]])

sql_query = "SELECT count(DISTINCT repo_name) FROM public.commit_history"
df = pd.read_sql(sql_query, engine)
results.append(["Repositories with commit histories", df["count"].values[0]])

sql_query = "SELECT count(DISTINCT repo_name) FROM public.github_issue_pr_items"
df = pd.read_sql(sql_query, engine)
results.append(["Repositories with issue/pr histories", df["count"].values[0]])

sql_query = "SELECT count(*) FROM public.github_issue_pr_items"
df = pd.read_sql(sql_query, engine)
results.append(["Issue and pull request records", df["count"].values[0]])

result = pd.DataFrame(results, columns=["Item", "Count"])
result.to_csv("table_i.csv", index=False)

print("TABLE I")
print(result.to_string(index=False))

engine.dispose()
