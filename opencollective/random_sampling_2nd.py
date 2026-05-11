from sqlalchemy import create_engine
import pandas as pd
import api

# PostgreSQL接続
engine = create_engine(
  f"postgresql+psycopg2://postgres:{api.load_sql_password_from_credentials()}@localhost:5432/opencollective"
)

# Contribution データ取得
query = """
SELECT
  id,
  expense_description
FROM collective_transactions
WHERE kind = 'EXPENSE' and amount_currency = 'USD'
ORDER BY random()
"""

df_sql = pd.read_sql(query, engine)
df_csv = pd.read_csv("expenses_random_order_v2.csv")[["id", "expense_description"]]

print(df_sql.head(5))
print(df_csv.head(5))
