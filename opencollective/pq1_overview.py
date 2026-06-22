import api
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
from forex_python.converter import CurrencyRates

# ============================================================
# 設定
# ============================================================

DB_NAME = "opencollective"

# 資金移動データのテーブル名
MONEY_TABLE = "public.collective_transactions"

DATE_COL = "created_at"
AMOUNT_COL = "amount_value"
CURRENCY_COL = "amount_currency"
FROM_TYPE_COL = "from_account_type"
TO_TYPE_COL = "to_account_type"

BASE_CURRENCY = "USD"

# 「OSSに貢献された資金」とみなす to_account_type
# 必要に応じて追加・変更してください
OPEN_SOURCE_TO_ACCOUNT_TYPES = [
    "COLLECTIVE",
    "PROJECT",
]

# 支出・送金額が負値で入っている場合もあるため、金額は絶対値で扱う
USE_ABSOLUTE_AMOUNT = True

# ============================================================
# 1. DB接続
# ============================================================

engine = create_engine(
    f"postgresql+psycopg2://postgres:{api.load_sql_password_from_credentials()}@localhost:5432/{DB_NAME}"
)


# ============================================================
# 2. 資金移動データ取得
# ============================================================

query_money = f"""
SELECT
    {DATE_COL} AS created_at,
    {AMOUNT_COL} AS amount_value,
    {CURRENCY_COL} AS amount_currency,
    {FROM_TYPE_COL} AS from_account_type,
    {TO_TYPE_COL} AS to_account_type,
    kind
FROM {MONEY_TABLE}
WHERE {AMOUNT_COL} IS NOT NULL
  AND {CURRENCY_COL} IS NOT NULL
  AND {DATE_COL} IS NOT NULL
  AND {FROM_TYPE_COL} IS NOT NULL
  AND {TO_TYPE_COL} IS NOT NULL
  AND kind IS NOT NULL
"""

df_money = pd.read_sql(query_money, engine)

print("Loaded money records:", len(df_money))
print("\n===== Raw currency distribution =====")
print(df_money["amount_currency"].value_counts(dropna=False))


# ============================================================
# 3. 前処理
# ============================================================

df_money["created_at"] = pd.to_datetime(
    df_money["created_at"],
    utc=True,
    errors="coerce"
).dt.tz_convert(None)

df_money["amount_value"] = pd.to_numeric(
    df_money["amount_value"],
    errors="coerce"
)

df_money["amount_currency"] = (
    df_money["amount_currency"]
    .astype(str)
    .str.strip()
    .str.upper()
)

df_money["from_account_type"] = (
    df_money["from_account_type"]
    .astype(str)
    .str.strip()
    .str.upper()
)

df_money["to_account_type"] = (
    df_money["to_account_type"]
    .astype(str)
    .str.strip()
    .str.upper()
)

df_money["kind"] = (
    df_money["kind"]
    .astype(str)
    .str.strip()
    .str.upper()
)

df_money = df_money[
    df_money["created_at"].notna() &
    df_money["amount_value"].notna() &
    df_money["amount_currency"].notna() &
    (df_money["amount_currency"] != "") &
    (df_money["amount_currency"] != "NAN")
].copy()

if USE_ABSOLUTE_AMOUNT:
    df_money["amount_original"] = df_money["amount_value"].abs()
else:
    df_money["amount_original"] = df_money["amount_value"]

df_money = df_money[
    df_money["amount_original"].notna() &
    (df_money["amount_original"] > 0)
].copy()


# ============================================================
# 4. 現在レートで USD に変換
# ============================================================

currency_rates = CurrencyRates()

unique_currencies = sorted(df_money["amount_currency"].dropna().unique())

exchange_rates_to_usd = {}

for currency in unique_currencies:
    if currency == BASE_CURRENCY:
        exchange_rates_to_usd[currency] = 1.0
    else:
        try:
            exchange_rates_to_usd[currency] = currency_rates.get_rate(
                currency,
                BASE_CURRENCY
            )
        except Exception as e:
            print(f"Warning: failed to get exchange rate {currency} -> USD: {e}")
            exchange_rates_to_usd[currency] = np.nan

print("\n===== Exchange rates to USD =====")
for currency, rate in exchange_rates_to_usd.items():
    print(f"{currency} -> USD: {rate}")

df_money["exchange_rate_to_usd"] = (
    df_money["amount_currency"]
    .map(exchange_rates_to_usd)
)

missing_rate_rows = df_money["exchange_rate_to_usd"].isna().sum()

if missing_rate_rows > 0:
    print(
        f"\nWarning: excluding rows with missing exchange rates: "
        f"{missing_rate_rows}"
    )

df_money = df_money[
    df_money["exchange_rate_to_usd"].notna()
].copy()

df_money["amount_usd"] = (
    df_money["amount_original"] *
    df_money["exchange_rate_to_usd"]
)

df_money["year"] = df_money["created_at"].dt.year

print("\n===== USD amount summary =====")
print("Rows used:", len(df_money))
print("Total amount USD:", df_money["amount_usd"].sum())


# ============================================================
# 5. Graph 1:
#    Money amount table: From account type --> To account type
#    kind 別に CONTRIBUTION / EXPENSE を分けて集計
# ============================================================

df_flow = (
    df_money
    .groupby(["kind", "from_account_type", "to_account_type"])
    .agg(
        total_amount_usd=("amount_usd", "sum"),
        n_transactions=("amount_usd", "count"),
    )
    .reset_index()
)

df_flow.to_csv(
    "pq1_money_flow_from_account_type_to_account_type_by_kind_usd_long.csv",
    index=False
)

print("\n===== Money flow table by kind: from_account_type -> to_account_type =====")
print(df_flow.to_string(index=False))

for kind_value in ["CONTRIBUTION", "EXPENSE"]:
    df_kind = df_money[df_money["kind"] == kind_value].copy()

    if df_kind.empty:
        print(f"\nNo records for kind = {kind_value}")
        continue

    df_flow_table = df_kind.pivot_table(
        index="from_account_type",
        columns="to_account_type",
        values="amount_usd",
        aggfunc="sum",
        fill_value=0
    )

    output_csv = f"pq1_money_flow_{kind_value.lower()}_from_account_type_to_account_type_usd.csv"
    output_png = f"rq2_money_flow_{kind_value.lower()}_from_account_type_to_account_type_usd_heatmap.pdf"

    df_flow_table.to_csv(output_csv)

    print(f"\n===== Money flow table: kind = {kind_value} =====")
    print(df_flow_table)

    flow_values_log = np.log1p(df_flow_table.values)

    plt.figure(figsize=(5, 3.5))

    im = plt.imshow(flow_values_log, aspect="auto")

    plt.xticks(
        ticks=np.arange(len(df_flow_table.columns)),
        labels=df_flow_table.columns,
        rotation=45,
        ha="right"
    )

    plt.yticks(
        ticks=np.arange(len(df_flow_table.index)),
        labels=df_flow_table.index
    )

    plt.colorbar(im, label="log1p(total amount in USD)")

    plt.xlabel("To account type")
    plt.ylabel("From account type")
    #plt.title(f"Money flow by account type, kind = {kind_value}, converted to USD")

    plt.tight_layout()
    plt.savefig(output_png, bbox_inches="tight")
    plt.show()

    print(f"Saved: {output_csv}")
    print(f"Saved: {output_png}")


# ============================================================
# 6. Graph 2:
#    Yearly graph of amount of money being contributed to Open-source
#    kind = CONTRIBUTION のみ
# ============================================================

df_contribution = df_money[
    df_money["kind"] == "CONTRIBUTION"
].copy()

df_yearly = (
    df_contribution
    .groupby("year")
    .agg(
        total_contributed_usd=("amount_usd", "sum"),
        n_transactions=("amount_usd", "count"),
    )
    .reset_index()
    .sort_values("year")
)

df_yearly.to_csv(
    "pq1_yearly_money_contributed_to_open_source_usd.csv",
    index=False
)

print("\n===== Yearly amount contributed to open-source =====")
print(df_yearly.to_string(index=False))

plt.figure(figsize=(5, 3.5),constrained_layout=True)

plt.plot(
    df_yearly["year"],
    df_yearly["total_contributed_usd"],
    marker="o",
    label="yearly contribution amount"
)

plt.xlabel("Year")
#y axis unit: millions of USD
plt.ylabel("Contribution amount in millions (USD)")
plt.gca().yaxis.set_major_formatter(lambda x, _: f"{x/1e6:.1f}")

#plt.title("Yearly amount of money contributed to open-source projects")
plt.grid(True, alpha=0.3)
plt.legend()

plt.savefig(
    "rq1_yearly_money_contributed_to_open_source_usd.pdf",
    bbox_inches="tight"
)

plt.show()
