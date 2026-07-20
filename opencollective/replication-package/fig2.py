import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from forex_python.converter import CurrencyRates
from output_util import FIGURES_DIR

from duckdb_util import database_engine


MONEY_TABLE = "public.collective_transactions"
BASE_CURRENCY = "USD"
OUTPUT_PDF = FIGURES_DIR / "Fig2.pdf"


def load_contributions():
    engine = database_engine()

    try:
        df = pd.read_sql(
            f"""
            SELECT
                amount_value,
                amount_currency,
                from_account_type,
                to_account_type
            FROM {MONEY_TABLE}
            WHERE kind = 'CONTRIBUTION'
              AND amount_value IS NOT NULL
              AND amount_currency IS NOT NULL
              AND from_account_type IS NOT NULL
              AND to_account_type IS NOT NULL
            """,
            engine,
        )
    finally:
        engine.dispose()

    return df


def convert_to_usd(df):
    df = df.copy()

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

    df["from_account_type"] = (
        df["from_account_type"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["to_account_type"] = (
        df["to_account_type"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df = df[
        df["amount_value"].notna()
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

    return df


def main():
    df = load_contributions()
    df = convert_to_usd(df)

    flow_table = df.pivot_table(
        index="from_account_type",
        columns="to_account_type",
        values="amount_usd",
        aggfunc="sum",
        fill_value=0,
    )

    log_values = np.log1p(flow_table.values)

    fig, ax = plt.subplots(
        figsize=(5, 3.5)
    )

    image = ax.imshow(
        log_values,
        aspect="auto",
    )

    ax.set_xticks(
        np.arange(len(flow_table.columns))
    )
    ax.set_xticklabels(
        flow_table.columns,
        rotation=45,
        ha="right",
    )

    ax.set_yticks(
        np.arange(len(flow_table.index))
    )
    ax.set_yticklabels(
        flow_table.index
    )

    fig.colorbar(
        image,
        ax=ax,
        label="log1p(total amount in USD)",
    )

    ax.set_xlabel("To account type")
    ax.set_ylabel("From account type")

    fig.tight_layout()

    fig.savefig(
        OUTPUT_PDF,
        bbox_inches="tight",
    )

    plt.close(fig)


if __name__ == "__main__":
    main()