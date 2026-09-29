"""
TABLE III: Transaction Records by Kind

kind 別の取引件数と合計金額（USD）。
金額は元の符号を保持する（CONTRIBUTION は正、EXPENSE / 各種手数料は負）ため、
資金の向きがそのまま読める。対向仕訳は transaction_util 側で除去済みなので、
同一の資金移動を二重に数えることはない。
"""

import pandas as pd

from output_util import TABLES_DIR
from transaction_util import load_transactions

TOP_N = 5  # これより下位の kind は "Others" にまとめる

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

result.to_csv(TABLES_DIR / "table_iii.csv", index=False)

print("TABLE III  (Amount は百万 USD、符号は資金の向きを示す)")
print(result.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
