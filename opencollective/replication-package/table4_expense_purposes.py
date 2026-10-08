import pandas as pd
from sqlalchemy import bindparam, text
from output_util import TABLES_DIR

from duckdb_util import database_engine
from transaction_util import get_exchange_rates


df = pd.concat(
    [
        pd.read_csv("data3.csv"),
        pd.read_csv("data4.csv"),
    ],
    ignore_index=True,
)

df = df[df["confidence"] >= 0.9].copy()

ids = df["id"].dropna().astype(str).unique().tolist()

engine = database_engine()

try:
    sql = text(
        """
        SELECT id, amount_currency
        FROM public.collective_transactions
        WHERE id IN :ids
        """
    ).bindparams(
        bindparam("ids", expanding=True)
    )

    transactions = pd.read_sql(
        sql,
        engine,
        params={"ids": ids},
    )

    df["id"] = df["id"].astype(str)
    transactions["id"] = transactions["id"].astype(str)

    df = df.merge(
        transactions,
        on="id",
        how="inner",
        validate="many_to_one",
    )

    df["amount_value"] = pd.to_numeric(
        df["amount_value"],
        errors="coerce",
    ).abs()

    df["amount_currency"] = (
        df["amount_currency"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    rates = get_exchange_rates(
        df["amount_currency"].dropna().unique()
    )

    df["rate_to_usd"] = df["amount_currency"].map(rates)

    df = df.dropna(
        subset=[
            "amount_value",
            "rate_to_usd",
        ]
    )

    df["amount_usd"] = (
        df["amount_value"]
        * df["rate_to_usd"]
    )

    result = (
        df.groupby(
            "predicted_label",
            as_index=False,
        )
        .agg(
            Count=("id", "count"),
            Amount=("amount_usd", "sum"),
        )
        .rename(
            columns={
                "predicted_label": "Category"
            }
        )
        .sort_values(
            "Count",
            ascending=False,
        )
        .reset_index(drop=True)
    )

    result["Count(%)"] = (
        result["Count"]
        / result["Count"].sum()
        * 100
    )

    result["Amount(%)"] = (
        result["Amount"]
        / result["Amount"].sum()
        * 100
    )

    result = result[
        [
            "Category",
            "Count",
            "Count(%)",
            "Amount(%)",
        ]
    ]

    # Category names as used in the paper.
    result["Category"] = result["Category"].replace({
        "development": "Development",
        "infra-subscription": "Infra & Subscription",
        "marketing-events": "Marketing & Events",
        "non-tech-activities": "Non-tech Activities",
        "unknown": "Unknown",
        "equipment": "Equipment",
        "food-supplies": "Food & Supplies",
    })

    print(
        result.to_string(
            index=False,
            float_format=lambda x: f"{x:,.2f}",
        )
    )

    result.rename(
        columns={
            "Category": "category",
            "Count": "count",
            "Count(%)": "count_pct",
            "Amount(%)": "amount_pct",
        }
    ).to_csv(
        TABLES_DIR / "table4_expense_purposes.csv",
        index=False,
    )

finally:
    engine.dispose()