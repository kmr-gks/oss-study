"""
Table 3: Transaction Statistics for Contributions and Expenses

CONTRIBUTION と EXPENSE について、件数・合計・平均・中央値を報告する。
取引規模の比較が目的なので金額は絶対値で扱う。対向仕訳は
transaction_util 側で除去済みであり、フィルタ後は各 kind の符号が
揃っているため、絶対値化によって向きの異なる取引が混ざることはない。

件数と金額の絶対値は Table III と一致する（末尾で自動チェック）。
"""

import pandas as pd

from output_util import TABLES_DIR
from transaction_util import load_transactions

TARGET_KINDS = ["CONTRIBUTION", "EXPENSE"]

df = load_transactions()

sub = df[df["kind"].isin(TARGET_KINDS)].copy()

# フィルタ後に符号の乱れがないことを確認しておく
for kind in TARGET_KINDS:
    signs = sub.loc[sub["kind"] == kind, "amount_usd"].apply(
        lambda x: 1 if x > 0 else (-1 if x < 0 else 0)
    ).unique()
    nonzero = [s for s in signs if s != 0]
    if len(nonzero) > 1:
        print(f"[WARN] {kind} に正負が混在しています: {sorted(nonzero)}")

sub["amount_abs"] = sub["amount_usd"].abs()

result = sub.groupby("kind").agg(
    count=("amount_abs", "count"),
    total_usd=("amount_abs", "sum"),
    mean_usd=("amount_abs", "mean"),
    median_usd=("amount_abs", "median"),
).T

result = result.reindex(columns=[k for k in TARGET_KINDS if k in result.columns])

result.rename(columns=str.lower).rename_axis("metric").reset_index().to_csv(
    TABLES_DIR / "table3_contribution_expense_stats.csv",
    index=False,
)

print("Table 3")
print(result.to_string(float_format=lambda x: f"{x:,.2f}"))

# --- Table III との整合性チェック -------------------------------------------

table2_path = TABLES_DIR / "table2_transactions_by_kind.csv"
if table2_path.exists():
    t3 = pd.read_csv(table2_path)
    print("\n[Consistency check: Table 2 vs Table 3]")
    for kind in TARGET_KINDS:
        row = t3[t3["kind"] == kind]
        if row.empty or kind not in result.columns:
            print(f"  {kind:<13} Table III 側に該当なし（Others に含まれている可能性）")
            continue

        c3 = int(row["count"].iloc[0])
        a3 = abs(float(row["amount_musd"].iloc[0])) * 1e6
        c4 = int(result.loc["count", kind])
        a4 = float(result.loc["total_usd", kind])

        ok_c = "OK" if c3 == c4 else "MISMATCH"
        ok_a = "OK" if abs(a3 - a4) < 1.0 else "MISMATCH"
        print(f"  {kind:<13} count    : {c3:,} vs {c4:,}  -> {ok_c}")
        print(f"  {kind:<13} |amount| : {a3:,.2f} vs {a4:,.2f}  -> {ok_a}")
else:
    print(f"\n[info] {table2_path} not found; consistency check skipped."
          f" Run table2_transactions_by_kind.py first.")
