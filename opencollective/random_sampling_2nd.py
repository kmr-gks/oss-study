from sqlalchemy import create_engine
import pandas as pd
import api
import json

# PostgreSQL接続
engine = create_engine(
    f"postgresql+psycopg2://postgres:{api.load_sql_password_from_credentials()}@localhost:5432/opencollective"
)

# Contribution データ取得
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
  LIMIT 5
"""

df = pd.read_sql(query, engine)

print(df[["expense_description", "description"]])

df = pd.read_csv("expenses_random_order_v2.csv")
df = df[["expense_description", "manual_label_v2"]].dropna()

print(df.head(5))
