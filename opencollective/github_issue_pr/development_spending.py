from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
import api
import numpy as np
import pandas as pd
from forex_python.converter import CurrencyRates
from sqlalchemy import create_engine


PROJECT_COL = "project_slug"
BASE_CURRENCY = "USD"

SPEND_TERTILE_COL = (
    "development_spend_amount_tertile"
)

SPEND_TERTILE_LABELS = [
    "Bottom 33%",
    "Middle 33%",
    "Top 33%",
]


EXPENSE_SQL = """
SELECT
    id AS transaction_id,
    project_slug,
    amount_value,
    amount_currency,
    is_development
FROM public.collective_transactions
WHERE kind = 'EXPENSE'
  AND project_slug IS NOT NULL
  AND amount_value IS NOT NULL
  AND amount_currency IS NOT NULL
"""


def database_engine():
    password = (
        api.load_sql_password_from_credentials()
    )

    return create_engine(
        "postgresql+psycopg2://"
        f"postgres:{password}"
        "@localhost:5432/opencollective"
    )


def load_expenses(
    engine,
) -> pd.DataFrame:
    """
    collective_transactionsから
    EXPENSEを読み込む。
    """
    df = pd.read_sql(
        EXPENSE_SQL,
        engine,
    )

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

    # PostgreSQLのbooleanを明示的にbool化
    df["is_development"] = (
        df["is_development"]
        .fillna(False)
        .astype(bool)
    )

    df = df[
        df["amount_value"].notna()
        & df["amount_currency"].notna()
        & df["amount_currency"].ne("")
        & df["amount_currency"].ne("NAN")
    ].copy()

    print("\n===== Loaded expenses =====")
    print("Expense rows:", len(df))
    print(
        "Projects:",
        df[PROJECT_COL].nunique(),
    )

    print(
        "\nDevelopment flag:"
    )

    print(
        df["is_development"]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    print(
        "\nCurrency distribution:"
    )

    print(
        df["amount_currency"]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    return df


def fetch_exchange_rates_to_usd(
    currencies,
) -> dict:
    """
    各通貨からUSDへの為替レートを取得する。
    """
    currency_rates = CurrencyRates()
    exchange_rates = {}

    for currency in sorted(currencies):
        if currency == BASE_CURRENCY:
            exchange_rates[currency] = 1.0
            continue

        try:
            rate = currency_rates.get_rate(
                currency,
                BASE_CURRENCY,
            )

            exchange_rates[currency] = rate

        except Exception as exc:
            print(
                "Warning: failed to get "
                f"exchange rate "
                f"{currency} -> USD: {exc}"
            )

            exchange_rates[currency] = np.nan

    print(
        "\n===== Exchange rates to USD ====="
    )

    for currency, rate in (
        exchange_rates.items()
    ):
        print(
            f"{currency} -> USD: {rate}"
        )

    return exchange_rates


def add_expense_amount_usd(
    df_expense: pd.DataFrame,
) -> pd.DataFrame:
    """
    支出額をUSDへ換算する。

    EXPENSEは負の値で保存される場合があるため、
    絶対値を使用する。
    """
    df = df_expense.copy()

    df["expense_amount_original"] = (
        df["amount_value"].abs()
    )

    df = df[
        df["expense_amount_original"].gt(0)
    ].copy()

    exchange_rates = (
        fetch_exchange_rates_to_usd(
            df["amount_currency"]
            .dropna()
            .unique()
        )
    )

    df["exchange_rate_to_usd"] = (
        df["amount_currency"]
        .map(exchange_rates)
    )

    missing_rate_rows = (
        df["exchange_rate_to_usd"]
        .isna()
        .sum()
    )

    if missing_rate_rows > 0:
        print(
            "\nWarning: excluding rows "
            "with missing exchange rates:",
            missing_rate_rows,
        )

    df = df[
        df["exchange_rate_to_usd"]
        .notna()
    ].copy()

    df["expense_amount_usd"] = (
        df["expense_amount_original"]
        * df["exchange_rate_to_usd"]
    )

    print(
        "\n===== Expense amount summary ====="
    )

    print(
        "Total expense amount USD:",
        df["expense_amount_usd"].sum(),
    )

    print(
        "Development expense amount USD:",
        df.loc[
            df["is_development"],
            "expense_amount_usd",
        ].sum(),
    )

    return df


def build_project_spending(
    df_expense: pd.DataFrame,
) -> pd.DataFrame:
    """
    プロジェクトごとに、
    全支出額と開発支出額を集計する。
    """
    df = df_expense.copy()

    df["development_amount_usd"] = np.where(
        df["is_development"],
        df["expense_amount_usd"],
        0.0,
    )

    df_project = (
        df.groupby(
            PROJECT_COL,
            as_index=False,
        )
        .agg(
            total_expense_count=(
                "transaction_id",
                "count",
            ),
            development_expense_count=(
                "is_development",
                "sum",
            ),
            total_expense_amount_usd=(
                "expense_amount_usd",
                "sum",
            ),
            development_expense_amount_usd=(
                "development_amount_usd",
                "sum",
            ),
        )
    )

    df_project[
        "development_count_ratio"
    ] = (
        df_project[
            "development_expense_count"
        ]
        / df_project[
            "total_expense_count"
        ]
    )

    df_project[
        "development_amount_ratio"
    ] = np.where(
        df_project[
            "total_expense_amount_usd"
        ].gt(0),
        (
            df_project[
                "development_expense_amount_usd"
            ]
            / df_project[
                "total_expense_amount_usd"
            ]
        ),
        np.nan,
    )

    print(
        "\n===== Project spending summary ====="
    )

    print(
        "Projects with expense data:",
        len(df_project),
    )

    return df_project


def add_development_spend_tertiles(
    df_project_spending: pd.DataFrame,
) -> pd.DataFrame:
    """
    開発支出額の小さい順に並べ、
    プロジェクト数がほぼ等しくなるよう
    Bottom / Middle / Topへ分割する。

    同額の場合はproject_slugで順序を固定する。
    """
    df = df_project_spending.copy()

    ordered_index = (
        df.sort_values(
            [
                "development_expense_amount_usd",
                PROJECT_COL,
            ],
            ascending=[
                True,
                True,
            ],
        )
        .index
    )

    tertiles = pd.Series(
        index=df.index,
        dtype="object",
    )

    index_chunks = np.array_split(
        ordered_index,
        3,
    )

    for label, index_chunk in zip(
        SPEND_TERTILE_LABELS,
        index_chunks,
    ):
        tertiles.loc[
            index_chunk
        ] = label

    df[SPEND_TERTILE_COL] = pd.Categorical(
        tertiles,
        categories=
            SPEND_TERTILE_LABELS,
        ordered=True,
    )

    print(
        "\n===== Projects by development "
        "spending tertile ====="
    )

    print(
        df[SPEND_TERTILE_COL]
        .value_counts()
        .sort_index()
        .to_string()
    )

    return df


def summarize_spending_tertiles(
    df_project_spending: pd.DataFrame,
) -> pd.DataFrame:
    """
    各グループの支出額を確認するための集計。
    """
    return (
        df_project_spending
        .groupby(
            SPEND_TERTILE_COL,
            observed=False,
            as_index=False,
        )
        .agg(
            n_projects=(
                PROJECT_COL,
                "nunique",
            ),
            min_development_spend_usd=(
                "development_expense_amount_usd",
                "min",
            ),
            median_development_spend_usd=(
                "development_expense_amount_usd",
                "median",
            ),
            mean_development_spend_usd=(
                "development_expense_amount_usd",
                "mean",
            ),
            max_development_spend_usd=(
                "development_expense_amount_usd",
                "max",
            ),
            median_total_expense_usd=(
                "total_expense_amount_usd",
                "median",
            ),
            median_development_amount_ratio=(
                "development_amount_ratio",
                "median",
            ),
        )
    )


def create_project_spending_tertiles(
    engine,
):
    """
    支出取得からUSD換算、3群化までをまとめて実行する。
    """
    df_expense = load_expenses(
        engine
    )

    df_expense = add_expense_amount_usd(
        df_expense
    )

    df_project_spending = (
        build_project_spending(
            df_expense
        )
    )

    df_project_spending = (
        add_development_spend_tertiles(
            df_project_spending
        )
    )

    df_tertile_summary = (
        summarize_spending_tertiles(
            df_project_spending
        )
    )

    return (
        df_expense,
        df_project_spending,
        df_tertile_summary,
    )