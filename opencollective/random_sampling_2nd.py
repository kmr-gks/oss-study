from sqlalchemy import create_engine
import pandas as pd
import api

# PostgreSQL接続
engine = create_engine(
    f"postgresql+psycopg2://postgres:{api.load_sql_password_from_credentials()}@localhost:5432/opencollective"
)

query = """
SELECT
  id,
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
"""

df_sql = pd.read_sql(query, engine)

# 既存ラベル済みデータ
df_csv = pd.read_csv("expenses_random_order_v2.csv")[["expense_description"]]

# description重複除外
existing_descriptions = set(df_csv["expense_description"])
df_new_candidates = df_sql[
    ~df_sql["expense_description"].isin(existing_descriptions)
]

# SQL内の重複descriptionも除去
df_new_candidates = df_new_candidates.drop_duplicates(
    subset=["expense_description"]
)

# ランダムサンプリング
df_new_sample = df_new_candidates.sample(
    n=381,
    random_state=42
).reset_index(drop=True)

# 保存
df_new_sample.to_csv(
    "expenses_random_order_2nd.csv",
    index=False
)
