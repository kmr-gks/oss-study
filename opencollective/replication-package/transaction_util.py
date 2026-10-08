"""
Loads Open Collective transactions and applies the preprocessing shared by
all scripts.

Main steps:
  1. Normalize currency codes (so that exchange-rate lookups match).
  2. Convert amounts to USD with the fixed rates in data/exchange_rates_to_usd.json.
  3. Remove the counterpart entries of double-entry records
     (keep only one type per kind).

Double-entry records:
  The Open Collective ledger records each transfer as a DEBIT entry on the
  paying side and a CREDIT entry on the receiving side. When both sides are
  in the dataset (e.g., transfers between collectives), counting all rows
  would count the same transfer twice. Therefore, for each kind, only the
  type that represents the transaction is kept.
"""

import json
from pathlib import Path

import pandas as pd

from duckdb_util import DATA_DIR, database_engine
from output_util import TABLES_DIR

BASE_CURRENCY = "USD"

# Fixed exchange rates shared by all scripts, so that re-running them
# reproduces the same values.
RATE_CACHE_PATH = Path(DATA_DIR) / "exchange_rates_to_usd.json"

# Type kept for each kind.
# CONTRIBUTION: money received (CREDIT); EXPENSE: money paid (DEBIT).
# For kinds not listed here, the majority type is used and a warning is printed.
KIND_TO_TYPE = {
    "CONTRIBUTION": "CREDIT",
    "EXPENSE": "DEBIT",
    "HOST_FEE": "DEBIT",
    "PAYMENT_PROCESSOR_FEE": "DEBIT",
    "ADDED_FUNDS": "CREDIT",
}


def _fetch_rates(currencies):
    """Return {currency: rate to USD}; None if the rate cannot be retrieved (excluded later)."""
    # Imported here so that runs that only use the cached rates
    # (data/exchange_rates_to_usd.json) need neither forex-python
    # nor an Internet connection.
    from forex_python.converter import CurrencyRates
    converter = CurrencyRates()
    rates = {}
    for currency in sorted(currencies):
        try:
            rates[currency] = 1.0 if currency == BASE_CURRENCY else converter.get_rate(currency, BASE_CURRENCY)
        except Exception:
            rates[currency] = None
    return rates


def _load_or_fetch_rates(currencies, refresh=False):
    """Read the rates from the file; retrieve and add rates for currencies that are missing."""
    currencies = sorted(set(currencies))

    if RATE_CACHE_PATH.exists() and not refresh:
        with open(RATE_CACHE_PATH, encoding="utf-8") as f:
            cached = json.load(f)
        missing = [c for c in currencies if c not in cached]
        if not missing:
            print(f"[rates] Using fixed rates: {RATE_CACHE_PATH}")
            return cached
        print(f"[rates] Retrieving rates for {len(missing)} currencies not in the file")
        cached.update(_fetch_rates(missing))
        rates = cached
    else:
        print("[rates] Retrieving exchange rates")
        rates = _fetch_rates(currencies)

    RATE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RATE_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(rates, f, ensure_ascii=False, indent=2, sort_keys=True)
    return rates


def get_exchange_rates(currencies, refresh=False):
    """
    Return {currency: rate to USD} from the shared cache
    (data/exchange_rates_to_usd.json).

    All scripts use this function so that every table, figure, and number
    in the paper is computed with the same fixed exchange rates.
    Currencies without a rate are returned as NaN and are excluded by the caller.
    """
    currencies = [str(c).strip().upper() for c in currencies if str(c).strip()]
    rates = _load_or_fetch_rates(currencies, refresh=refresh)
    return {
        c: (float(r) if r is not None else float("nan"))
        for c, r in rates.items()
    }


def _resolve_kind_to_type(df, verbose=True):
    """Decide the type kept for each kind; use the majority type for unlisted kinds."""
    mapping = dict(KIND_TO_TYPE)

    for kind in df["kind"].dropna().unique():
        if kind in mapping:
            continue
        counts = df.loc[df["kind"] == kind, "type"].value_counts()
        if counts.empty:
            continue
        chosen = counts.idxmax()
        mapping[kind] = chosen
        if verbose:
            share = counts.max() / counts.sum() * 100
            print(f"[WARN] kind='{kind}' is not in KIND_TO_TYPE; "
                  f"using the majority type '{chosen}' ({share:.1f}%).")

    return mapping


def load_transactions(refresh_rates=False, verbose=True):
    """
    Return the preprocessed transactions.

    The returned DataFrame has the columns:
        kind, type, amount_currency, amount_value, exchange_rate, amount_usd

    amount_usd keeps the original sign (positive for CONTRIBUTION,
    negative for EXPENSE).
    """
    engine = database_engine()
    raw = pd.read_sql(
        """
        SELECT kind, type, amount_value, amount_currency
        FROM public.collective_transactions
        """,
        engine,
    )
    engine.dispose()

    n_raw = len(raw)
    df = raw.copy()

    # --- Normalize types and notation ---
    df["kind"] = df["kind"].astype("string").str.strip().str.upper()
    df["type"] = df["type"].astype("string").str.strip().str.upper()
    df["amount_currency"] = df["amount_currency"].astype("string").str.strip().str.upper()
    df["amount_value"] = pd.to_numeric(df["amount_value"], errors="coerce")

    # --- Drop NULL values ---
    df = df.dropna(subset=["amount_value", "amount_currency", "kind", "type"])
    n_after_null = len(df)

    # --- Convert to USD ---
    rates = _load_or_fetch_rates(df["amount_currency"].unique(), refresh=refresh_rates)
    df["exchange_rate"] = df["amount_currency"].map(rates)

    missing = df[df["exchange_rate"].isna()]
    if verbose and not missing.empty:
        print("[WARN] Currencies without an exchange rate (excluded):")
        print(missing.groupby("amount_currency").size().to_string())

    df = df.dropna(subset=["exchange_rate"])
    n_after_rate = len(df)

    df["amount_usd"] = df["amount_value"] * df["exchange_rate"]

    # --- Remove counterpart entries of double-entry records ---
    if verbose:
        print("\n[Records by kind and type (before filtering)]")
        breakdown = (
            df.groupby(["kind", "type"])
              .agg(Count=("amount_usd", "size"), Total_USD=("amount_usd", "sum"))
              .sort_values("Count", ascending=False)
        )
        print(breakdown.to_string(float_format=lambda x: f"{x:,.2f}"))
        print()

    mapping = _resolve_kind_to_type(df, verbose=verbose)
    keep = df.apply(lambda r: r["type"] == mapping.get(r["kind"]), axis=1)

    dropped = df[~keep]
    df = df[keep].copy()
    n_after_type = len(df)

    if verbose:
        print("\n[Exclusion summary]")
        print(f"  Rows loaded                 : {n_raw:,}")
        print(f"  After dropping NULLs        : {n_after_null:,}  (-{n_raw - n_after_null:,})")
        print(f"  After dropping missing rates: {n_after_rate:,}  (-{n_after_null - n_after_rate:,})")
        print(f"  After removing counterparts : {n_after_type:,}  (-{n_after_rate - n_after_type:,})")
        if not dropped.empty:
            print("\n  Removed counterpart entries:")
            print(dropped.groupby(["kind", "type"])
                         .agg(Count=("amount_usd", "size"), Total_USD=("amount_usd", "sum"))
                         .to_string(float_format=lambda x: f"{x:,.2f}"))
        print()

    return df.reset_index(drop=True)