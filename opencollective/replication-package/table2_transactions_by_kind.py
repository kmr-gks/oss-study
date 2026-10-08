"""
Table 2: Transaction Records by Kind

Number of transactions and total amount (USD) per transaction kind.
Amounts keep their original sign (positive for CONTRIBUTION, negative for
EXPENSE and fees), so the sign shows the direction of the flow. Counterpart
entries of double-entry records are removed in transaction_util, so no
transfer is counted twice.
"""

import pandas as pd

from output_util import TABLES_DIR
from transaction_util import load_transactions

TOP_N = 5  # kinds below the top N are grouped as "Others"

df = load_transactions()

result = (
    df.groupby("kind", as_index=False)
      .agg(Count=("amount_usd", "size"), Amount_USD=("amount_usd", "sum"))
      .sort_values("Count", ascending=False)
      .reset_index(drop=True)
)

if len(result) > TOP_N:
    others = pd.DataFrame([{
        "kind": "Others",
        "Count": result.loc[TOP_N:, "Count"].sum(),
        "Amount_USD": result.loc[TOP_N:, "Amount_USD"].sum(),
    }])
    result = pd.concat([result.iloc[:TOP_N], others], ignore_index=True)

result["Amount_USD"] = result["Amount_USD"] / 1e6

result = result.rename(columns={"Count": "count", "Amount_USD": "amount_musd"})
result.to_csv(TABLES_DIR / "table2_transactions_by_kind.csv", index=False)

print("Table 2  (amount in million USD; the sign shows the direction of the flow)")
print(result.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
