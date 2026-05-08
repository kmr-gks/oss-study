import api
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

# PostgreSQL接続
engine = create_engine(
    f"postgresql+psycopg2://postgres:{api.load_sql_password_from_credentials()}@localhost:5432/opencollective"
)

# Contribution データ取得
query_contrib = """
SELECT ABS(amount_value) AS amount
FROM public.collective_transactions
WHERE kind = 'CONTRIBUTION'
  AND amount_currency = 'USD'
  AND amount_value <> 0;
"""

df_contrib = pd.read_sql(query_contrib, engine)

print("Contribution transactions:", len(df_contrib))

# Expense データ取得
query_expense = """
SELECT ABS(amount_value) AS amount
FROM public.collective_transactions
WHERE kind = 'EXPENSE'
  AND amount_currency = 'USD'
  AND amount_value <> 0;
"""

df_expense = pd.read_sql(query_expense, engine)

print("Expense transactions:", len(df_expense))

# Contribution Histogram
contrib = df_contrib["amount"]

bins_contrib = np.logspace(
    np.log10(contrib.min()),
    np.log10(contrib.max()),
    50
)

plt.figure(figsize=(8, 5))

plt.hist(contrib, bins=bins_contrib)

plt.xscale("log")

plt.xlabel("Contribution Amount (USD, log scale)")
plt.ylabel("Number of Transactions")
plt.title("Distribution of Contributions")

plt.tight_layout()
plt.show()

# Expense Histogram

expense = df_expense["amount"]

bins_expense = np.logspace(
    np.log10(expense.min()),
    np.log10(expense.max()),
    50
)

plt.figure(figsize=(8, 5))

plt.hist(expense, bins=bins_expense)

plt.xscale("log")

plt.xlabel("Expense Amount (USD, log scale)")
plt.ylabel("Number of Transactions")
plt.title("Distribution of Expenses")

plt.tight_layout()
plt.show()
