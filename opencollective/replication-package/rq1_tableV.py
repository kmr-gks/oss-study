import api
import pandas as pd
from forex_python.converter import CurrencyRates
from sqlalchemy import create_engine

DB_NAME = "opencollective"

df = pd.concat([
    pd.read_csv("data3.csv"),
    pd.read_csv("data4.csv"),
], ignore_index=True)

df = df[df["confidence"] >= 0.9].copy()

engine = create_engine(
    f"postgresql+psycopg2://postgres:{api.load_sql_password_from_credentials()}@localhost:5432/{DB_NAME}"
)

transactions = pd.read_sql(
    """
    SELECT id, amount_currency
    FROM public.collective_transactions
    WHERE id = ANY(%(ids)s)
    """,
    engine,
    params={"ids": df["id"].dropna().tolist()},
)

df = df.merge(transactions, on="id", how="inner", validate="many_to_one")
df["amount_value"] = df["amount_value"].abs()
df["amount_currency"] = df["amount_currency"].str.strip().str.upper()

converter = CurrencyRates()
rates = {}

for currency in df["amount_currency"].dropna().unique():
    try:
        rates[currency] = 1.0 if currency == "USD" else converter.get_rate(currency, "USD")
    except Exception as error:
        print(f"Warning: {currency} -> USD failed: {error}")
        rates[currency] = None

df["rate_to_usd"] = df["amount_currency"].map(rates)
df = df.dropna(subset=["amount_value", "rate_to_usd"])
df["amount_usd"] = df["amount_value"] * df["rate_to_usd"]

result = (
    df.groupby("predicted_label", as_index=False)
    .agg(
        Count=("id", "count"),
        Amount=("amount_usd", "sum"),
    )
    .rename(columns={"predicted_label": "Category"})
    .sort_values("Count", ascending=False)
    .reset_index(drop=True)
)

result["Count(%)"] = result["Count"] / result["Count"].sum() * 100
result["Amount(%)"] = result["Amount"] / result["Amount"].sum() * 100
result = result[["Category", "Count", "Count(%)", "Amount(%)"]]

print(result.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

result.to_csv(
    "table_v.csv",
    index=False,
    float_format="%.2f",
)

engine.dispose()
