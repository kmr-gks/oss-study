import api
import pandas as pd
from sqlalchemy import create_engine
from forex_python.converter import CurrencyRates

BASE_CURRENCY = "USD"
DB_NAME = "opencollective"

def fetch_rates(currencies):
    converter = CurrencyRates()
    rates = {}
    for currency in currencies:
        currency = str(currency).strip().upper()
        try:
            rates[currency] = 1.0 if currency == "USD" else converter.get_rate(currency, "USD")
        except Exception as error:
            rates[currency] = None
    return rates

engine = create_engine(
    f"postgresql+psycopg2://postgres:{api.load_sql_password_from_credentials()}@localhost:5432/{DB_NAME}"
)

sql_query = """
SELECT kind, amount_value, amount_currency
FROM public.collective_transactions
WHERE kind IN ('CONTRIBUTION', 'EXPENSE')
  AND amount_value IS NOT NULL
  AND amount_currency IS NOT NULL
"""

df = pd.read_sql(sql_query, engine)
df["amount_currency"] = df["amount_currency"].str.strip().str.upper()
df["amount_value"] = pd.to_numeric(df["amount_value"], errors="coerce").abs()

rates = fetch_rates(df["amount_currency"].unique())
df["exchange_rate"] = df["amount_currency"].map(rates)
df = df.dropna(subset=["amount_value", "exchange_rate"])
df["amount_usd"] = df["amount_value"] * df["exchange_rate"]

result = df.groupby("kind").agg(
    Count=("amount_usd", "count"),
    Total_USD=("amount_usd", "sum"),
    Mean_USD=("amount_usd", "mean"),
    Median_USD=("amount_usd", "median"),
).T

print(result.to_string(float_format=lambda x: f"{x:,.2f}"))
result.to_csv("table_iv.csv")

engine.dispose()