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
"""

df_sql = pd.read_sql(query, engine)

# 既存ラベル済みデータ
#2nd dataも除外する
df_csv = pd.read_csv("expenses_random_order_v2.csv")[["expense_description"]]
df_csv2 = pd.read_csv("expenses_random_order_2nd.csv", encoding='shift-jis')[["expense_description"]]
df_csv = pd.concat([df_csv, df_csv2], ignore_index=True)

# 欠損除外
df_sql = df_sql.dropna(subset=["expense_description"])
df_csv = df_csv.dropna(subset=["expense_description"])

# 前後空白除去
df_sql["expense_description"] = df_sql["expense_description"].str.strip()
df_csv["expense_description"] = df_csv["expense_description"].str.strip()

# description重複除外
existing_descriptions = set(df_csv["expense_description"])
df_new_candidates = df_sql[
    ~df_sql["expense_description"].isin(existing_descriptions)
]

# ランダムサンプリング
df_new_sample = df_new_candidates.sample(
    n=1784,
    random_state=42
).reset_index(drop=True)

# 保存
df_new_sample.to_csv(
    "expenses_random_order_3rd.csv",
    index=False
)
