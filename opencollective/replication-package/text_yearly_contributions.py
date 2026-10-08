import numpy as np
import pandas as pd
from output_util import TABLES_DIR

from duckdb_util import database_engine
from transaction_util import KIND_TO_TYPE, get_exchange_rates


MONEY_TABLE = "public.collective_transactions"
BASE_CURRENCY = "USD"

def load_contributions():
    engine = database_engine()

    try:
        df = pd.read_sql(
            f"""
            SELECT
                created_at,
                amount_value,
                amount_currency
            FROM {MONEY_TABLE}
            WHERE kind = 'CONTRIBUTION'
              -- Keep only the receiving side of each double-entry
              -- record so that the same transfer is not counted twice.
              AND type = '{KIND_TO_TYPE["CONTRIBUTION"]}'
              AND created_at IS NOT NULL
              AND amount_value IS NOT NULL
              AND amount_currency IS NOT NULL
            """,
            engine,
        )
    finally:
        engine.dispose()

    return df


def convert_to_usd(df):
    df = df.copy()

    df["created_at"] = pd.to_datetime(
        df["created_at"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    df["amount_value"] = pd.to_numeric(
        df["amount_value"],
        errors="coerce",
    )

    df["amount_currency"] = (
        df["amount_currency"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df = df[
        df["created_at"].notna()
        & df["amount_value"].notna()
        & df["amount_currency"].notna()
        & df["amount_currency"].ne("")
        & df["amount_currency"].ne("NAN")
    ].copy()

    df["amount_original"] = df["amount_value"].abs()

    df = df[
        df["amount_original"].gt(0)
    ].copy()

    rates = get_exchange_rates(
        df["amount_currency"].dropna().unique()
    )

    df["exchange_rate_to_usd"] = (
        df["amount_currency"].map(rates)
    )

    df = df[
        df["exchange_rate_to_usd"].notna()
    ].copy()

    df["amount_usd"] = (
        df["amount_original"]
        * df["exchange_rate_to_usd"]
    )

    df["year"] = df["created_at"].dt.year

    return df


def main():
    df = load_contributions()
    df = convert_to_usd(df)

    yearly = (
        df.groupby(
            "year",
            as_index=False,
        )
        .agg(
            total_contributed_usd=(
                "amount_usd",
                "sum",
            ),
            n_transactions=(
                "amount_usd",
                "count",
            ),
        )
        .sort_values("year")
    )

    print("===== Yearly contribution amount (USD) =====")
    print(
        yearly.to_string(
            index=False,
            formatters={
                "total_contributed_usd":
                    lambda value: f"{value:,.2f}",
                "n_transactions":
                    lambda value: f"{value:,}",
            },
        )
    )
    yearly.rename(
        columns={"total_contributed_usd": "amount_usd"}
    ).to_csv(
        TABLES_DIR / "text_yearly_contributions.csv",
        index=False,
    )

    print(
        "Total: "
        f"{yearly['total_contributed_usd'].sum():,.2f} USD "
        f"({yearly['n_transactions'].sum():,} transactions)"
    )


if __name__ == "__main__":
    main()