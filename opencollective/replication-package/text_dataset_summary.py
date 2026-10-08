import pandas as pd
from duckdb_util import database_engine
from output_util import TABLES_DIR
from transaction_util import load_transactions

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

# Count transactions after removing the counterpart entries of each
# double-entry record (see transaction_util.load_transactions), so that this
# number equals the sum of the counts in table2_transactions_by_kind.csv.
results.append(["Transactions", len(load_transactions(verbose=False))])

sql_query = "SELECT count(DISTINCT repo_name) as count FROM public.commit_history"
df = pd.read_sql(sql_query, engine)
results.append(["Repositories with commit histories", df["count"].values[0]])

sql_query = "SELECT count(DISTINCT repo_name) as count FROM public.github_issue_pr_items"
df = pd.read_sql(sql_query, engine)
results.append(["Repositories with issue/pr histories", df["count"].values[0]])

sql_query = "SELECT count(*) as count FROM public.github_issue_pr_items"
df = pd.read_sql(sql_query, engine)
results.append(["Issue and pull request records", df["count"].values[0]])

result = pd.DataFrame(results, columns=["item", "count"])
result.to_csv(TABLES_DIR / "text_dataset_summary.csv", index=False)

print("Dataset summary (Section 3.1)")
print(result.to_string(index=False))

engine.dispose()
