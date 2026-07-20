import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from forex_python.converter import CurrencyRates
from output_util import FIGURES_DIR

from duckdb_util import database_engine


MONEY_TABLE = "public.collective_transactions"
BASE_CURRENCY = "USD"
OUTPUT_PDF = FIGURES_DIR / "Fig1.pdf"

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

    converter = CurrencyRates()
    rates = {}

    for currency in sorted(
        df["amount_currency"].dropna().unique()
    ):
        try:
            rates[currency] = (
                1.0
                if currency == BASE_CURRENCY
                else converter.get_rate(
                    currency,
                    BASE_CURRENCY,
                )
            )
        except Exception:
            rates[currency] = np.nan

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

    fig, ax = plt.subplots(
        figsize=(5, 3.5),
        constrained_layout=True,
    )

    ax.plot(
        yearly["year"],
        yearly["total_contributed_usd"],
        marker="o",
        label="Yearly contribution amount",
    )

    ax.set_xlabel("Year")
    ax.set_ylabel(
        "Contribution amount in millions (USD)"
    )

    ax.yaxis.set_major_formatter(
        lambda value, position:
            f"{value / 1e6:.1f}"
    )

    ax.grid(
        True,
        alpha=0.3,
    )

    ax.legend()

    fig.savefig(
        OUTPUT_PDF,
        bbox_inches="tight",
    )

    plt.close(fig)


if __name__ == "__main__":
    main()