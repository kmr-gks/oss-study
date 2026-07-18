from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
import api
import api
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from forex_python.converter import CurrencyRates
from sqlalchemy import create_engine

from issue_label_classification import (
    classify_project_issue_labels,
    summarize_project_issue_categories,
    summarize_project_issue_category_overlap,
)


PROJECT_COL = "project_slug"
BASE_CURRENCY = "USD"
WINDOW_MONTHS = 12

TERTILE_COL = "development_spend_amount_tertile"

TERTILE_LABELS = [
    "Bottom 33%",
    "Middle 33%",
    "Top 33%",
]

CATEGORY_ORDER = [
    "feature_development",
    "bug_fixing",
    "contributor_recruitment",
    "documentation",
    "maintenance",
    "issue_triage_closure",
    "question_support",
    "other_labeled",
    "unlabeled",
]

CATEGORY_LABELS = {
    "feature_development":
        "Feature development",
    "bug_fixing":
        "Bug fixing",
    "contributor_recruitment":
        "Contributor-oriented",
    "documentation":
        "Documentation",
    "maintenance":
        "Maintenance",
    "issue_triage_closure":
        "Issue triage / closure",
    "question_support":
        "Question / support",
    "other_labeled":
        "Other labeled",
    "unlabeled":
        "Unlabeled",
}


EXPENSE_SQL = """
SELECT
    project_slug,
    amount_value,
    amount_currency,
    is_development
FROM public.collective_transactions
WHERE kind = 'EXPENSE'
  AND project_slug IS NOT NULL
  AND amount_value IS NOT NULL
  AND amount_currency IS NOT NULL
  AND is_development IS NOT NULL
"""


COLLECTIVE_SQL = """
SELECT
    slug AS project_slug,
    created_at AS opencollective_created_at,
    github_account
FROM public.collectives
WHERE slug IS NOT NULL
  AND created_at IS NOT NULL
  AND github_account IS NOT NULL
  AND github_account LIKE '%%/%%'
"""


ISSUE_SQL = """
SELECT
    repo_name,
    number,
    created_at,
    labels,
    title,
    url
FROM public.github_issue_pr_items
WHERE item_type = 'issue'
  AND repo_name IS NOT NULL
  AND number IS NOT NULL
  AND created_at IS NOT NULL
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


def normalize_currency(
    series: pd.Series,
) -> pd.Series:
    return (
        series
        .astype(str)
        .str.strip()
        .str.upper()
    )


def fetch_exchange_rates_to_usd(
    currencies,
) -> dict:
    """
    前の実験と同じく、forex_pythonを使って
    各通貨からUSDへの現在の換算レートを取得する。
    """
    converter = CurrencyRates()
    exchange_rates = {}

    for currency in sorted(currencies):
        if currency == BASE_CURRENCY:
            exchange_rates[currency] = 1.0
            continue

        try:
            exchange_rates[currency] = (
                converter.get_rate(
                    currency,
                    BASE_CURRENCY,
                )
            )
        except Exception as error:
            print(
                "Warning: failed to get exchange rate "
                f"{currency} -> USD: {error}"
            )

            exchange_rates[currency] = np.nan

    print("\n===== Exchange rates to USD =====")

    for currency, rate in exchange_rates.items():
        print(
            f"{currency} -> USD: {rate}"
        )

    return exchange_rates


def load_and_convert_expenses(
    engine,
) -> pd.DataFrame:
    """
    collective_transactionsから支出を読み込み、
    USDへ換算する。

    is_development=Trueの支出だけを
    開発向け支出として扱う。
    """
    df = pd.read_sql(
        EXPENSE_SQL,
        engine,
    )

    print("\n===== Loaded expenses =====")
    print("Expense rows:", len(df))
    print(
        "Projects:",
        df[PROJECT_COL].nunique(),
    )

    df["amount_value"] = pd.to_numeric(
        df["amount_value"],
        errors="coerce",
    )

    df["amount_currency"] = (
        normalize_currency(
            df["amount_currency"]
        )
    )

    # 支出額は負値の場合があるため絶対値を使う
    df["expense_amount_original"] = (
        df["amount_value"].abs()
    )

    df = df[
        df["expense_amount_original"].notna()
        & df["expense_amount_original"].gt(0)
        & df["amount_currency"].notna()
        & df["amount_currency"].ne("")
        & df["amount_currency"].ne("NAN")
    ].copy()

    print(
        "\n===== Currency distribution ====="
    )

    print(
        df["amount_currency"]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    exchange_rates = (
        fetch_exchange_rates_to_usd(
            df["amount_currency"].unique()
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
            "\nWarning: excluding rows with "
            "missing exchange rates:",
            missing_rate_rows,
        )

    df = df[
        df["exchange_rate_to_usd"].notna()
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
            df["is_development"].eq(True),
            "expense_amount_usd",
        ].sum(),
    )

    return df


def build_project_spending(
    df_expenses: pd.DataFrame,
) -> pd.DataFrame:
    """
    プロジェクトごとの全支出額と
    開発向け支出額を計算する。
    """
    df = df_expenses.copy()

    df["development_amount_usd"] = (
        np.where(
            df["is_development"].eq(True),
            df["expense_amount_usd"],
            0.0,
        )
    )

    df_project_spending = (
        df.groupby(
            PROJECT_COL,
            as_index=False,
        )
        .agg(
            total_expense_count=(
                "expense_amount_usd",
                "size",
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

    df_project_spending[
        "development_amount_ratio"
    ] = np.where(
        df_project_spending[
            "total_expense_amount_usd"
        ].gt(0),
        (
            df_project_spending[
                "development_expense_amount_usd"
            ]
            / df_project_spending[
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
        len(df_project_spending),
    )

    print(
        df_project_spending[
            [
                PROJECT_COL,
                "total_expense_amount_usd",
                "development_expense_amount_usd",
                "development_amount_ratio",
            ]
        ]
        .head()
        .to_string(index=False)
    )

    return df_project_spending


def add_development_spending_tertiles(
    df_project_spending: pd.DataFrame,
) -> pd.DataFrame:
    """
    開発向け支出額の小さい順にプロジェクトを並べ、
    プロジェクト数がほぼ同じになるよう3群に分割する。

    以前のコミット分析と同じ分割方法。
    """
    df = df_project_spending.copy()

    tertiles = pd.Series(
        index=df.index,
        dtype="object",
    )

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

    index_chunks = np.array_split(
        ordered_index,
        3,
    )

    for label, indexes in zip(
        TERTILE_LABELS,
        index_chunks,
    ):
        tertiles.loc[indexes] = label

    df[TERTILE_COL] = pd.Categorical(
        tertiles,
        categories=TERTILE_LABELS,
        ordered=True,
    )

    print(
        "\n===== Projects by development "
        "spending tertile ====="
    )

    print(
        df[TERTILE_COL]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print(
        "\n===== Development spending amount "
        "by tertile ====="
    )

    print(
        df.groupby(
            TERTILE_COL,
            observed=False,
        )[
            "development_expense_amount_usd"
        ]
        .agg(
            [
                "count",
                "min",
                "median",
                "mean",
                "max",
            ]
        )
        .to_string()
    )

    return df


def load_collectives(
    engine,
) -> pd.DataFrame:
    df = pd.read_sql(
        COLLECTIVE_SQL,
        engine,
    )

    df["github_account"] = (
        df["github_account"]
        .astype(str)
        .str.strip()
    )

    # commit_history等で使っている形式にそろえる
    # owner/repository -> owner-repository
    df["repo_name"] = (
        df["github_account"]
        .str.replace(
            "/",
            "-",
            regex=False,
        )
    )

    df[
        "opencollective_created_at"
    ] = pd.to_datetime(
        df["opencollective_created_at"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    df = df[
        df[
            "opencollective_created_at"
        ].notna()
    ].copy()

    # 同じproject_slugが複数存在した場合に備える
    df = (
        df.sort_values(
            "opencollective_created_at"
        )
        .drop_duplicates(
            subset=[
                PROJECT_COL,
                "repo_name",
            ],
            keep="first",
        )
        .reset_index(drop=True)
    )

    print("\n===== Loaded collectives =====")
    print("Collective rows:", len(df))
    print(
        "Projects:",
        df[PROJECT_COL].nunique(),
    )

    return df


def load_issues(
    engine,
) -> pd.DataFrame:
    df = pd.read_sql(
        ISSUE_SQL,
        engine,
    )

    df["created_at"] = pd.to_datetime(
        df["created_at"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    df = df[
        df["created_at"].notna()
    ].copy()

    print("\n===== Loaded issues =====")
    print("Issue rows:", len(df))
    print(
        "Repositories:",
        df["repo_name"].nunique(),
    )

    return df

def extract_issues_after_registration(
    df_target_projects: pd.DataFrame,
    df_issues: pd.DataFrame,
    window_months: int = WINDOW_MONTHS,
) -> pd.DataFrame:
    """
    すでに3群へ分類された対象プロジェクトについて、
    Open Collective加入後12か月のIssueを抽出する。
    """
    df = df_issues.merge(
        df_target_projects,
        on="repo_name",
        how="inner",
        validate="many_to_many",
    )

    df["analysis_end_at"] = (
        df["opencollective_created_at"]
        + pd.DateOffset(
            months=window_months
        )
    )

    df = df[
        df["created_at"].ge(
            df["opencollective_created_at"]
        )
        & df["created_at"].lt(
            df["analysis_end_at"]
        )
    ].copy()

    df = (
        df.drop_duplicates(
            subset=[
                PROJECT_COL,
                "repo_name",
                "number",
            ]
        )
        .reset_index(drop=True)
    )

    print(
        "\n===== Issues within "
        f"{window_months} months after registration ====="
    )

    print(
        df.groupby(
            TERTILE_COL,
            observed=False,
        )
        .agg(
            n_projects=(
                PROJECT_COL,
                "nunique",
            ),
            n_repositories=(
                "repo_name",
                "nunique",
            ),
            n_issues=(
                "number",
                "count",
            ),
        )
        .to_string()
    )

    return df


def build_tertile_summary(
    df_target_projects: pd.DataFrame,
    df_issues_after: pd.DataFrame,
) -> pd.DataFrame:
    """
    Issueが1件以上ある分析対象について、
    3群ごとのプロジェクト数・支出額・Issue数を要約する。
    """
    df_spending_summary = (
        df_target_projects
        .groupby(
            TERTILE_COL,
            observed=False,
            as_index=False,
        )
        .agg(
            n_projects=(
                PROJECT_COL,
                "nunique",
            ),
            min_development_expense_usd=(
                "development_expense_amount_usd",
                "min",
            ),
            median_development_expense_usd=(
                "development_expense_amount_usd",
                "median",
            ),
            mean_development_expense_usd=(
                "development_expense_amount_usd",
                "mean",
            ),
            max_development_expense_usd=(
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

    df_issue_summary = (
        df_issues_after
        .groupby(
            TERTILE_COL,
            observed=False,
            as_index=False,
        )
        .agg(
            n_projects_with_issues=(
                PROJECT_COL,
                "nunique",
            ),
            n_issues_after_registration=(
                "number",
                "count",
            ),
        )
    )

    return (
        df_spending_summary
        .merge(
            df_issue_summary,
            on=TERTILE_COL,
            how="left",
            validate="one_to_one",
        )
    )


def plot_category_bands(
    df_category_summary: pd.DataFrame,
    df_tertile_summary: pd.DataFrame,
    output_path: str,
) -> None:
    """
    Bottom/Middle/Topの3本の100%帯グラフを作成する。

    1つのIssueが複数カテゴリに所属できるため、
    全カテゴリ割当数に占める割合を使用する。
    """
    df_plot = (
        df_category_summary
        .pivot_table(
            index=TERTILE_COL,
            columns="category",
            values="category_assignment_share",
            fill_value=0,
            observed=False,
        )
        .reindex(
            index=TERTILE_LABELS,
            columns=CATEGORY_ORDER,
            fill_value=0,
        )
    )

    fig, ax = plt.subplots(
        figsize=(6, 3.5)
    )

    left = np.zeros(
        len(df_plot)
    )

    for category in CATEGORY_ORDER:
        values = (
            df_plot[category]
            .fillna(0)
            .to_numpy()
        )

        ax.barh(
            df_plot.index.astype(str),
            values,
            left=left,
            height=0.62,
            label=CATEGORY_LABELS.get(
                category,
                category,
            ),
            edgecolor="white",
            linewidth=0.5,
        )

        left += values

    ax.set_xlim(
        0,
        1,
    )

    ax.set_xlabel(
        "Share of category assignments"
    )

    ax.set_ylabel(
        "Development spending amount"
    )

    ax.xaxis.set_major_formatter(
        lambda value, position:
            f"{value * 100:.0f}%"
    )

    ax.grid(
        axis="x",
        linestyle=":",
        linewidth=0.7,
        alpha=0.6,
    )

    ax.set_axisbelow(True)

    summary_by_group = (
        df_tertile_summary
        .set_index(TERTILE_COL)
    )

    for position, label in enumerate(
        TERTILE_LABELS
    ):
        if label not in summary_by_group.index:
            continue

        row = summary_by_group.loc[label]

        n_projects = int(
            row["n_projects"]
        )

        n_issues = row[
            "n_issues_after_registration"
        ]

        n_issues = (
            0
            if pd.isna(n_issues)
            else int(n_issues)
        )

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(
            0.5,
            -0.20,
        ),
        ncol=3,
        frameon=False,
        fontsize=8,
    )

    fig.subplots_adjust(
        left=0.20,
        right=0.78,
        top=0.96,
        bottom=0.32,
    )

    fig.tight_layout()

    fig.savefig(
        output_path,
        bbox_inches="tight",
    )

    plt.close(fig)

    print(
        f"Saved figure: {output_path}"
    )

def main():
    engine = database_engine()

    try:
        # --------------------------------------------------
        # 1. 支出をUSDへ換算
        # --------------------------------------------------

        df_expenses = (
            load_and_convert_expenses(
                engine
            )
        )

        # --------------------------------------------------
        # 2. プロジェクトごとの開発向け支出額
        # --------------------------------------------------

        df_project_spending = (
            build_project_spending(
                df_expenses
            )
        )

        # --------------------------------------------------
        # 3. Open CollectiveとIssueを読み込む
        # --------------------------------------------------

        df_collectives = load_collectives(
            engine
        )

        df_issues = load_issues(
            engine
        )

        # --------------------------------------------------
        # 4. 加入後12か月にIssueがあるプロジェクトへ限定
        # --------------------------------------------------

        df_target_projects = (
            build_target_projects_with_issues(
                df_collectives=
                    df_collectives,
                df_issues=
                    df_issues,
                df_project_spending=
                    df_project_spending,
                window_months=
                    WINDOW_MONTHS,
            )
        )

        # --------------------------------------------------
        # 5. Issueがある対象だけを開発支出額で3等分
        # --------------------------------------------------

        df_target_projects = (
            add_development_spending_tertiles(
                df_target_projects
            )
        )

        # --------------------------------------------------
        # 6. 加入後12か月のIssueを抽出
        # --------------------------------------------------

        df_issues_after = (
            extract_issues_after_registration(
                df_target_projects=
                    df_target_projects,
                df_issues=
                    df_issues,
                window_months=
                    WINDOW_MONTHS,
            )
        )

        # --------------------------------------------------
        # 7. Issueラベルを分類
        # --------------------------------------------------

        df_categories = (
            classify_project_issue_labels(
                df_issues_after,
                group_columns=[
                    TERTILE_COL,
                    "development_expense_amount_usd",
                ],
            )
        )

        # --------------------------------------------------
        # 8. 3群ごとのカテゴリ構成
        # --------------------------------------------------

        df_category_summary = (
            summarize_project_issue_categories(
                df_issues=
                    df_issues_after,
                df_categories=
                    df_categories,
                group_column=
                    TERTILE_COL,
                group_order=
                    TERTILE_LABELS,
            )
        )

        # --------------------------------------------------
        # 9. 複数カテゴリ所属
        # --------------------------------------------------

        df_overlap_summary = (
            summarize_project_issue_category_overlap(
                df_categories=
                    df_categories,
                group_column=
                    TERTILE_COL,
            )
        )

        # --------------------------------------------------
        # 10. 3群の要約
        # --------------------------------------------------

        df_tertile_summary = (
            build_tertile_summary(
                df_target_projects=
                    df_target_projects,
                df_issues_after=
                    df_issues_after,
            )
        )

        print(
            "\n===== Tertile summary ====="
        )

        print(
            df_tertile_summary
            .to_string(index=False)
        )

        print(
            "\n===== Issue category summary ====="
        )

        print(
            df_category_summary[
                [
                    TERTILE_COL,
                    "category",
                    "n_category_assignments",
                    "total_unique_issues",
                    "issue_category_ratio",
                    "category_assignment_share",
                ]
            ]
            .to_string(index=False)
        )

        print(
            "\n===== Category overlap summary ====="
        )

        print(
            df_overlap_summary
            .to_string(index=False)
        )

        # --------------------------------------------------
        # 11. CSV保存
        # --------------------------------------------------

        df_target_projects.to_csv(
            "issue_target_projects_by_"
            "development_spending_tertile.csv",
            index=False,
        )

        df_tertile_summary.to_csv(
            "project_development_"
            "spending_tertile_summary.csv",
            index=False,
        )

        df_issues_after.to_csv(
            "issues_12m_after_registration_"
            "by_development_spending_tertile.csv",
            index=False,
        )

        df_categories.to_csv(
            "issue_categories_12m_after_"
            "registration_by_development_"
            "spending_tertile.csv",
            index=False,
        )

        df_category_summary.to_csv(
            "issue_category_summary_by_"
            "development_spending_tertile.csv",
            index=False,
        )

        df_overlap_summary.to_csv(
            "issue_category_overlap_by_"
            "development_spending_tertile.csv",
            index=False,
        )

        # --------------------------------------------------
        # 12. 帯グラフ
        # --------------------------------------------------

        plot_category_bands(
            df_category_summary=
                df_category_summary,
            df_tertile_summary=
                df_tertile_summary,
            output_path=(
                "issue_category_composition_by_"
                "development_spending_tertile_"
                "12m.pdf"
            ),
        )

        plot_category_bands(
            df_category_summary=
                df_category_summary,
            df_tertile_summary=
                df_tertile_summary,
            output_path=(
                "issue_category_composition_by_"
                "development_spending_tertile_"
                "12m.png"
            ),
        )

    finally:
        engine.dispose()


def build_target_projects_with_issues(
    df_collectives: pd.DataFrame,
    df_issues: pd.DataFrame,
    df_project_spending: pd.DataFrame,
    window_months: int = WINDOW_MONTHS,
) -> pd.DataFrame:
    """
    Open Collective加入後12か月にIssueが1件以上あり、
    かつ支出データが存在するプロジェクトを抽出する。

    この関数の結果を開発向け支出額で3等分する。
    """
    collective_columns = [
        PROJECT_COL,
        "repo_name",
        "opencollective_created_at",
    ]

    spending_columns = [
        PROJECT_COL,
        "total_expense_count",
        "development_expense_count",
        "total_expense_amount_usd",
        "development_expense_amount_usd",
        "development_amount_ratio",
    ]

    df_target_projects = (
        df_collectives[
            collective_columns
        ]
        .merge(
            df_project_spending[
                spending_columns
            ],
            on=PROJECT_COL,
            how="inner",
            validate="many_to_one",
        )
    )

    df_project_issues = df_issues.merge(
        df_target_projects,
        on="repo_name",
        how="inner",
        validate="many_to_many",
    )

    df_project_issues["analysis_end_at"] = (
        df_project_issues[
            "opencollective_created_at"
        ]
        + pd.DateOffset(
            months=window_months
        )
    )

    df_project_issues = df_project_issues[
        df_project_issues["created_at"].ge(
            df_project_issues[
                "opencollective_created_at"
            ]
        )
        & df_project_issues["created_at"].lt(
            df_project_issues[
                "analysis_end_at"
            ]
        )
    ].copy()

    # 加入後12か月にIssueがあるプロジェクトだけ
    project_ids_with_issues = (
        df_project_issues[
            [
                PROJECT_COL,
                "repo_name",
            ]
        ]
        .drop_duplicates()
    )

    df_target_projects = (
        df_target_projects.merge(
            project_ids_with_issues,
            on=[
                PROJECT_COL,
                "repo_name",
            ],
            how="inner",
            validate="one_to_one",
        )
    )

    print(
        "\n===== Target projects with at least "
        "one issue after registration ====="
    )

    print(
        "Projects:",
        df_target_projects[
            PROJECT_COL
        ].nunique(),
    )

    print(
        "Repositories:",
        df_target_projects[
            "repo_name"
        ].nunique(),
    )

    print(
        "Zero development spending:",
        df_target_projects[
            "development_expense_amount_usd"
        ].eq(0).sum(),
    )

    print(
        "Positive development spending:",
        df_target_projects[
            "development_expense_amount_usd"
        ].gt(0).sum(),
    )

    return (
        df_target_projects
        .drop_duplicates(
            subset=[
                PROJECT_COL,
                "repo_name",
            ]
        )
        .reset_index(drop=True)
    )

if __name__ == "__main__":
    main()