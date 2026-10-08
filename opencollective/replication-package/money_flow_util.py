"""
Shared helpers for Fig. 1 (money flow by account type).

Loads CONTRIBUTION and EXPENSE transactions (one side of each double-entry
record) and converts their amounts to USD with the fixed exchange rates.
This module is imported by fig1_money_flow.py and is not run directly.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

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
                amount_value,
                amount_currency,
                from_account_type,
                to_account_type
            FROM {MONEY_TABLE}
            WHERE kind = 'CONTRIBUTION'
              -- Keep only the receiving side of each double-entry
              -- record so that the same transfer is not counted twice.
              AND type = '{KIND_TO_TYPE["CONTRIBUTION"]}'
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


def load_expenses():
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
            WHERE kind = 'EXPENSE'
              -- Keep only the paying side of each double-entry
              -- record so that the same transfer is not counted twice.
              AND type = '{KIND_TO_TYPE["EXPENSE"]}'
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

    return df
