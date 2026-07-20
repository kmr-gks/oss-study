
import api
import pandas as pd
from sqlalchemy import create_engine
from forex_python.converter import CurrencyRates
from duckdb_util import database_engine

BASE_CURRENCY = "USD"
DB_NAME = "opencollective"

def fetch_current_exchange_rates_to_usd(currencies):
    converter = CurrencyRates()
    rates = {}
    for currency in sorted(currencies):
        currency = str(currency).strip().upper()
        try:
            rates[currency] = 1.0 if currency == BASE_CURRENCY else converter.get_rate(currency, BASE_CURRENCY)
        except Exception:
            rates[currency] = 0
    return rates

engine = database_engine()

sql_query = """
SELECT kind, amount_currency, SUM(amount_value) AS amount, COUNT(*) AS count
FROM public.collective_transactions
GROUP BY kind, amount_currency
"""

df = pd.read_sql(sql_query, engine)
rates = fetch_current_exchange_rates_to_usd(df["amount_currency"].unique())
df["amount_usd"] = df.apply(lambda row: row["amount"] * rates.get(row["amount_currency"], 0), axis=1)

result = df.groupby("kind", as_index=False).agg(Count=("count", "sum"), Amount_USD=("amount_usd", "sum"))
result = result.sort_values("Count", ascending=False).reset_index(drop=True)

if len(result) > 5:
    others = pd.DataFrame([{
        "kind": "Others",
        "Count": result.loc[5:, "Count"].sum(),
        "Amount_USD": result.loc[5:, "Amount_USD"].sum(),
    }])
    result = pd.concat([result.iloc[:5], others], ignore_index=True)

result["Amount_USD"] = result["Amount_USD"] / 1e6
result.to_csv("table_iii.csv", index=False)

print("TABLE III")
print(result.to_string(index=False))
