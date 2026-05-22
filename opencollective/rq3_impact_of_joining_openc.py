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
limit 10;
"""

query_commit_history = """
SELECT repo_name, author_time, commit_time FROM public.commit_history
ORDER BY repo_path ASC, commit_hash ASC 
limit 10;
"""

df_joining_time = pd.read_sql(query_joining_time, engine)
df_commit_history = pd.read_sql(query_commit_history, engine)

print("Collectives:", len(df_joining_time), df_joining_time.head(10))
print("Commit history:", len(df_commit_history), df_commit_history.head(10))