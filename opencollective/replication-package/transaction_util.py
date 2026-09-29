"""
Open Collective の取引データを読み込み、Table III / Table IV で共通の前処理を行う。

主な処理:
  1. 通貨コードの正規化（カラム側で行い、辞書引きのキー不一致を防ぐ）
  2. 為替レートの取得とキャッシュ（両表で同一のレートを使うため）
  3. 複式簿記の対向仕訳の除去（kind ごとに片側の type だけを残す）

複式簿記について:
  Open Collective の台帳は、1つの資金移動に対して支払側の DEBIT 行と
  受取側の CREDIT 行を記録する。取引の双方が本データセットに含まれる場合
  （collective 間の移転など）は両方の行が入るため、そのまま集計すると
  同じ資金移動を二重に数えてしまう。そこで kind ごとに、
  当該取引を代表する側の type だけを残す。
"""

import json
from pathlib import Path

import pandas as pd
from forex_python.converter import CurrencyRates

from duckdb_util import database_engine
from output_util import TABLES_DIR

BASE_CURRENCY = "USD"

# 為替レートのキャッシュ先。両スクリプトが同一のレートを使い、
# 再実行しても同じ数値が再現されるようにする。
RATE_CACHE_PATH = Path(TABLES_DIR) / "exchange_rates.json"

# kind ごとに残す type。
# CONTRIBUTION は入ってきた金 (CREDIT)、EXPENSE は出ていった金 (DEBIT) を採用する。
# 未登録の kind は多数派の type を自動採用し、警告を出す（要目視確認）。
KIND_TO_TYPE = {
    "CONTRIBUTION": "CREDIT",
    "EXPENSE": "DEBIT",
    "HOST_FEE": "DEBIT",
    "PAYMENT_PROCESSOR_FEE": "DEBIT",
    "ADDED_FUNDS": "CREDIT",
}


def _fetch_rates(currencies):
    """通貨コード -> USD レート。取得失敗は None（後段で除外）。"""
    converter = CurrencyRates()
    rates = {}
    for currency in sorted(currencies):
        try:
            rates[currency] = 1.0 if currency == BASE_CURRENCY else converter.get_rate(currency, BASE_CURRENCY)
        except Exception:
            rates[currency] = None
    return rates


def _load_or_fetch_rates(currencies, refresh=False):
    """キャッシュがあれば読み、なければ取得して保存する。"""
    currencies = sorted(set(currencies))

    if RATE_CACHE_PATH.exists() and not refresh:
        with open(RATE_CACHE_PATH, encoding="utf-8") as f:
            cached = json.load(f)
        missing = [c for c in currencies if c not in cached]
        if not missing:
            print(f"[rates] キャッシュを使用: {RATE_CACHE_PATH}")
            return cached
        print(f"[rates] キャッシュに未登録の通貨 {len(missing)} 件を追加取得")
        cached.update(_fetch_rates(missing))
        rates = cached
    else:
        print("[rates] 為替レートを取得")
        rates = _fetch_rates(currencies)

    RATE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RATE_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(rates, f, ensure_ascii=False, indent=2, sort_keys=True)
    return rates


def _resolve_kind_to_type(df, verbose=True):
    """kind ごとに残す type を決める。未登録の kind は多数派を採用。"""
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
            print(f"[WARN] kind='{kind}' は KIND_TO_TYPE に未登録。"
                  f"多数派の '{chosen}' を採用 ({share:.1f}%)。要確認。")

    return mapping


def load_transactions(refresh_rates=False, verbose=True):
    """
    前処理済みの取引データを返す。

    返り値の DataFrame は以下のカラムを持つ:
        kind, type, amount_currency, amount_value, exchange_rate, amount_usd

    amount_usd は元の符号を保持する（CONTRIBUTION は正、EXPENSE は負）。
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

    # --- 型と表記の正規化 ---
    df["kind"] = df["kind"].astype("string").str.strip().str.upper()
    df["type"] = df["type"].astype("string").str.strip().str.upper()
    df["amount_currency"] = df["amount_currency"].astype("string").str.strip().str.upper()
    df["amount_value"] = pd.to_numeric(df["amount_value"], errors="coerce")

    # --- NULL 除外 ---
    df = df.dropna(subset=["amount_value", "amount_currency", "kind", "type"])
    n_after_null = len(df)

    # --- 為替換算 ---
    rates = _load_or_fetch_rates(df["amount_currency"].unique(), refresh=refresh_rates)
    df["exchange_rate"] = df["amount_currency"].map(rates)

    missing = df[df["exchange_rate"].isna()]
    if verbose and not missing.empty:
        print("[WARN] 為替レートを取得できなかった通貨:")
        print(missing.groupby("amount_currency").size().to_string())

    df = df.dropna(subset=["exchange_rate"])
    n_after_rate = len(df)

    df["amount_usd"] = df["amount_value"] * df["exchange_rate"]

    # --- 対向仕訳の除去 ---
    if verbose:
        print("\n[type 内訳（フィルタ前）]")
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
        print("\n[除外サマリ]")
        print(f"  取得行数          : {n_raw:,}")
        print(f"  NULL 除外後       : {n_after_null:,}  (-{n_raw - n_after_null:,})")
        print(f"  レート除外後      : {n_after_rate:,}  (-{n_after_null - n_after_rate:,})")
        print(f"  対向仕訳の除去後  : {n_after_type:,}  (-{n_after_rate - n_after_type:,})")
        if not dropped.empty:
            print("\n  除去した対向仕訳の内訳:")
            print(dropped.groupby(["kind", "type"])
                         .agg(Count=("amount_usd", "size"), Total_USD=("amount_usd", "sum"))
                         .to_string(float_format=lambda x: f"{x:,.2f}"))
        print()

    return df.reset_index(drop=True)