import api
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

engine = create_engine(
    f"postgresql+psycopg2://postgres:{api.load_sql_password_from_credentials()}@localhost:5432/opencollective"
)

query_joining_time = """
SELECT id, name, slug, type, created_at, github_account FROM public.collectives
ORDER BY github_account ASC
"""

query_commit_history = """
SELECT repo_name, author_time, commit_time FROM public.commit_history
ORDER BY repo_path ASC, commit_hash ASC
limit 10000
"""

df_joining_time = pd.read_sql(query_joining_time, engine)
df_commit_history = pd.read_sql(query_commit_history, engine)


# collectiveテーブルではgithubアカウント名とリポジトリ名が'/'で区切られているが、commit_historyでは'-'で区切られていることに注意。
df_joining_time = df_joining_time[
    df_joining_time["github_account"].notna()
]
df_joining_time = df_joining_time[
    df_joining_time["github_account"].str.contains("/", na=False)
]
df_joining_time["repo_name"] = (
    df_joining_time["github_account"]
    .str.strip()
    .str.replace("/", "-", regex=False)
)

matched_repos = set(df_joining_time["repo_name"]) & set(df_commit_history["repo_name"])
print("Collectives with owner/repo:", len(df_joining_time))
print("Repos in commit_history:", df_commit_history["repo_name"].nunique())
print("Matched repos:", len(matched_repos))
print("Match rate:", len(matched_repos) / len(df_joining_time))
