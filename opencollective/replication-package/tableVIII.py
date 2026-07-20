import numpy as np
import pandas as pd
from forex_python.converter import CurrencyRates
from scipy.stats import kruskal, mannwhitneyu
from duckdb_util import database_engine


PROJECT_COL = "project_slug"
WINDOW_MONTHS_LIST = [12]
BASE_CURRENCY = "USD"
SIGNIFICANCE_LEVEL = 0.05

SPEND_TERTILE_COL = "development_spend_amount_tertile"
SPEND_TERTILE_LABELS = [
    "Bottom 33%",
    "Middle 33%",
    "Top 33%",
]

EXPENSE_SQL = """
SELECT
    id AS expense_id,
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

COLLECTIVES_SQL = """
SELECT
    id,
    name,
    slug,
    type,
    created_at,
    github_account
FROM public.collectives
WHERE github_account IS NOT NULL
"""

COMMIT_HISTORY_SQL = """
SELECT
    repo_name,
    commit_time
FROM public.commit_history
WHERE repo_name IS NOT NULL
  AND commit_time IS NOT NULL
"""


def clean_text(series):
    return series.astype(str).str.strip().str.upper()

def load_expenses(engine):
    df_expense = pd.read_sql(
        EXPENSE_SQL,
        engine,
    )

    df_expense["amount_value"] = pd.to_numeric(
        df_expense["amount_value"],
        errors="coerce",
    )

    df_expense["amount_currency"] = clean_text(
        df_expense["amount_currency"]
    )

    df_expense["is_development"] = (
        df_expense["is_development"]
        .astype("boolean")
    )

    print("\n===== Expense data loaded from SQL =====")
    print("Expense rows:", len(df_expense))
    print(
        "Projects:",
        df_expense[PROJECT_COL].nunique(),
    )

    print("\n===== is_development distribution =====")
    print(
        df_expense["is_development"]
        .value_counts(dropna=False)
        .to_string()
    )

    return df_expense


def fetch_exchange_rates_to_usd(currencies):
    currency_rates = CurrencyRates()
    exchange_rates = {}

    for currency in sorted(currencies):
        if currency == BASE_CURRENCY:
            exchange_rates[currency] = 1.0
            continue

        try:
            exchange_rates[currency] = (
                currency_rates.get_rate(
                    currency,
                    BASE_CURRENCY,
                )
            )
        except Exception as error:
            print(
                f"Warning: failed to get exchange rate "
                f"{currency} -> USD: {error}"
            )
            exchange_rates[currency] = np.nan

    print("\n===== Exchange rates to USD =====")

    for currency, rate in exchange_rates.items():
        print(f"{currency} -> USD: {rate}")

    return exchange_rates


def add_expense_amount_usd(df_expense):
    df_expense = df_expense.copy()

    df_expense["amount_currency"] = clean_text(
        df_expense["amount_currency"]
    )

    df_expense["expense_amount_original"] = (
        df_expense["amount_value"].abs()
    )

    df_expense = df_expense[
        df_expense["expense_amount_original"].notna()
        & df_expense["expense_amount_original"].gt(0)
        & df_expense["amount_currency"].notna()
        & df_expense["amount_currency"].ne("")
        & df_expense["amount_currency"].ne("NAN")
    ].copy()

    exchange_rates = fetch_exchange_rates_to_usd(
        df_expense[
            "amount_currency"
        ].dropna().unique()
    )

    df_expense["exchange_rate_to_usd"] = (
        df_expense["amount_currency"].map(
            exchange_rates
        )
    )

    missing_rate_rows = (
        df_expense[
            "exchange_rate_to_usd"
        ].isna().sum()
    )

    if missing_rate_rows:
        print(
            "\nWarning: excluding rows with "
            "missing exchange rates:",
            missing_rate_rows,
        )

    df_expense = df_expense[
        df_expense[
            "exchange_rate_to_usd"
        ].notna()
    ].copy()

    df_expense["expense_amount_usd"] = (
        df_expense["expense_amount_original"]
        * df_expense["exchange_rate_to_usd"]
    )

    print("\n===== Expense amount summary =====")
    print(
        "Total expense rows:",
        len(df_expense),
    )
    print(
        "Total expense amount USD:",
        df_expense[
            "expense_amount_usd"
        ].sum(),
    )
    print(
        "Development expense amount USD:",
        df_expense.loc[
            df_expense[
                "is_development"
            ].eq(True),
            "expense_amount_usd",
        ].sum(),
    )

    return df_expense


def build_project_spending(df_expense):
    df_expense = df_expense.copy()

    df_expense["development_amount_usd"] = (
        np.where(
            df_expense[
                "is_development"
            ].eq(True),
            df_expense[
                "expense_amount_usd"
            ],
            0.0,
        )
    )

    df_project_spending = (
        df_expense
        .groupby(PROJECT_COL)
        .agg(
            total_expense_count=(
                "expense_id",
                "count",
            ),
            development_expense_count=(
                "is_development",
                lambda values:
                    values.eq(True).sum(),
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
        .reset_index()
    )

    df_project_spending[
        "development_count_ratio"
    ] = (
        df_project_spending[
            "development_expense_count"
        ]
        / df_project_spending[
            "total_expense_count"
        ]
    )

    df_project_spending[
        "development_amount_ratio"
    ] = (
        df_project_spending[
            "development_expense_amount_usd"
        ]
        / df_project_spending[
            "total_expense_amount_usd"
        ]
    )
    return df_project_spending


def load_commit_base(engine):
    df_collectives = pd.read_sql(
        COLLECTIVES_SQL,
        engine,
    )

    df_commits = pd.read_sql(
        COMMIT_HISTORY_SQL,
        engine,
    )

    df_collectives = df_collectives[
        df_collectives[
            "github_account"
        ].notna()
        & df_collectives[
            "github_account"
        ].str.contains(
            "/",
            na=False,
        )
    ].copy()

    df_collectives["repo_name"] = (
        df_collectives[
            "github_account"
        ]
        .astype(str)
        .str.strip()
        .str.replace(
            "/",
            "-",
            regex=False,
        )
    )

    df_collectives["created_at"] = (
        pd.to_datetime(
            df_collectives["created_at"],
            utc=True,
            errors="coerce",
        ).dt.tz_convert(None)
    )

    df_commits["commit_time"] = (
        pd.to_datetime(
            df_commits["commit_time"],
            utc=True,
            errors="coerce",
        ).dt.tz_convert(None)
    )

    df_collectives = df_collectives[
        df_collectives[
            "created_at"
        ].notna()
    ].copy()

    df_commits = df_commits[
        df_commits[
            "commit_time"
        ].notna()
    ].copy()

    commit_repos = set(
        df_commits[
            "repo_name"
        ].unique()
    )

    df_matched = df_collectives[
        df_collectives[
            "repo_name"
        ].isin(commit_repos)
    ].copy()

    commits_by_repo = {
        repo_name: group[
            "commit_time"
        ]
        .sort_values()
        .reset_index(drop=True)
        for repo_name, group
        in df_commits.groupby(
            "repo_name"
        )
    }

    print("\n===== Commit analysis base =====")
    print(
        "Matched projects:",
        len(df_matched),
    )
    print(
        "Commit data start:",
        df_commits[
            "commit_time"
        ].min(),
    )
    print(
        "Commit data end:",
        df_commits[
            "commit_time"
        ].max(),
    )

    return (
        df_matched,
        commits_by_repo,
        df_commits[
            "commit_time"
        ].min(),
        df_commits[
            "commit_time"
        ].max(),
    )


def cliffs_delta(x, y):
    x = np.asarray(x)
    y = np.asarray(y)

    if len(x) == 0 or len(y) == 0:
        return np.nan

    greater_less = (
        np.sum(x_value > y)
        - np.sum(x_value < y)
        for x_value in x
    )

    return sum(greater_less) / (
        len(x) * len(y)
    )


def effect_size_label(delta):
    if pd.isna(delta):
        return "NA"

    if abs(delta) < 0.147:
        return "negligible"

    if abs(delta) < 0.33:
        return "small"

    if abs(delta) < 0.474:
        return "medium"

    return "large"


def print_group_stats(label, group):
    print(f"\n{label}")
    print(f"  N      = {len(group)}")

    if len(group) == 0:
        return

    print(
        f"  Median = {group.median():.3f}"
    )
    print(
        f"  Mean   = {group.mean():.3f}"
    )
    print(
        f"  Q1     = "
        f"{group.quantile(0.25):.3f}"
    )
    print(
        f"  Q3     = "
        f"{group.quantile(0.75):.3f}"
    )


def pairwise_mannwhitney_between_tertiles(
    groups,
    window_months,
):
    pair_labels = [
        (
            SPEND_TERTILE_LABELS[0],
            SPEND_TERTILE_LABELS[1],
        ),
        (
            SPEND_TERTILE_LABELS[0],
            SPEND_TERTILE_LABELS[2],
        ),
        (
            SPEND_TERTILE_LABELS[1],
            SPEND_TERTILE_LABELS[2],
        ),
    ]

    pairwise_results = []

    print(
        "\n===== Pairwise Mann-Whitney U "
        "tests ====="
    )

    for group_a_label, group_b_label in pair_labels:
        group_a = (
            groups[
                group_a_label
            ].dropna()
        )

        group_b = (
            groups[
                group_b_label
            ].dropna()
        )

        print(
            f"\n--- {group_a_label} "
            f"vs {group_b_label} ---"
        )

        if len(group_a) == 0 or len(group_b) == 0:
            pairwise_results.append(
                {
                    "Window months":
                        window_months,
                    "Group A":
                        group_a_label,
                    "Group B":
                        group_b_label,
                    "N A":
                        len(group_a),
                    "N B":
                        len(group_b),
                    "Median growth A":
                        np.nan,
                    "Median growth B":
                        np.nan,
                    "P-value":
                        np.nan,
                    "Adjusted p-value":
                        np.nan,
                    "Significant":
                        "NA",
                    "Cliff's delta":
                        np.nan,
                    "Effect size":
                        "NA",
                }
            )
            continue

        test_result = mannwhitneyu(
            group_a,
            group_b,
            alternative="two-sided",
        )

        adjusted_p_value = min(
            test_result.pvalue * 3,
            1.0,
        )

        significant = (
            "Yes"
            if adjusted_p_value
            < SIGNIFICANCE_LEVEL
            else "No"
        )

        delta = cliffs_delta(
            group_b,
            group_a,
        )

        effect_label = (
            effect_size_label(delta)
        )

        print(
            "Raw p-value:",
            f"{test_result.pvalue:.6f}",
        )
        print(
            "Bonferroni-adjusted p-value:",
            f"{adjusted_p_value:.6f}",
        )
        print(
            "Significant:",
            significant,
        )
        print(
            "Cliff's delta:",
            f"{delta:.3f}",
        )
        print(
            "Effect size:",
            effect_label,
        )

        pairwise_results.append(
            {
                "Window months":
                    window_months,
                "Group A":
                    group_a_label,
                "Group B":
                    group_b_label,
                "N A":
                    len(group_a),
                "N B":
                    len(group_b),
                "Median growth A":
                    group_a.median(),
                "Median growth B":
                    group_b.median(),
                "P-value":
                    test_result.pvalue,
                "Adjusted p-value":
                    adjusted_p_value,
                "Significant":
                    significant,
                "Cliff's delta":
                    delta,
                "Effect size":
                    effect_label,
            }
        )

    return pd.DataFrame(
        pairwise_results
    )


def test_growth_rate_between_spend_tertiles(
    df,
    window_months,
):
    groups = {
        label: df.loc[
            df[
                SPEND_TERTILE_COL
            ] == label,
            "growth_rate_pct",
        ].dropna()
        for label
        in SPEND_TERTILE_LABELS
    }

    print(
        "\n===== Kruskal-Wallis test ====="
    )

    for label in SPEND_TERTILE_LABELS:
        print_group_stats(
            label,
            groups[label],
        )

    has_all_groups = all(
        len(groups[label]) > 0
        for label in SPEND_TERTILE_LABELS
    )

    if not has_all_groups:
        print(
            "\nKruskal-Wallis test skipped "
            "because at least one group is empty."
        )

        test_result = {
            "Window months":
                window_months,
            "Test":
                "Kruskal-Wallis",
            "H statistic":
                np.nan,
            "P-value":
                np.nan,
            "Significant":
                "NA",
            "Epsilon squared":
                np.nan,
        }

        return (
            test_result,
            pd.DataFrame(),
        )

    kruskal_result = kruskal(
        groups[
            SPEND_TERTILE_LABELS[0]
        ],
        groups[
            SPEND_TERTILE_LABELS[1]
        ],
        groups[
            SPEND_TERTILE_LABELS[2]
        ],
    )

    h_statistic = (
        kruskal_result.statistic
    )

    p_value = (
        kruskal_result.pvalue
    )

    group_count = len(
        SPEND_TERTILE_LABELS
    )

    total_count = sum(
        len(groups[label])
        for label in SPEND_TERTILE_LABELS
    )

    epsilon_squared = (
        (
            h_statistic
            - group_count
            + 1
        )
        / (
            total_count
            - group_count
        )
        if total_count > group_count
        else np.nan
    )

    significant = (
        "Yes"
        if p_value < SIGNIFICANCE_LEVEL
        else "No"
    )

    print("\nKruskal-Wallis test result")
    print(
        "H statistic:",
        f"{h_statistic:.3f}",
    )
    print(
        "P-value:",
        f"{p_value:.6f}",
    )
    print(
        "Significant:",
        significant,
    )
    print(
        "Epsilon squared:",
        f"{epsilon_squared:.3f}",
    )

    test_result = {
        "Window months":
            window_months,
        "Test":
            "Kruskal-Wallis",
        "H statistic":
            h_statistic,
        "P-value":
            p_value,
        "Significant":
            significant,
        "Epsilon squared":
            epsilon_squared,
    }

    pairwise_result = (
        pairwise_mannwhitney_between_tertiles(
            groups,
            window_months,
        )
    )

    return (
        test_result,
        pairwise_result,
    )


def summarize_by_bin(df):
    summary = (
        df
        .groupby(
            SPEND_TERTILE_COL,
            observed=False,
        )
        .agg(
            N=(
                "growth_rate_pct",
                "count",
            ),
            growth_pct=(
                "growth_rate_pct",
                "median",
            ),
            mean_dev_exp=(
                "development_expense_amount_usd",
                "mean",
            ),
            median_dev_exp=(
                "development_expense_amount_usd",
                "median",
            ),
        )
        .reset_index()
        .rename(
            columns={
                SPEND_TERTILE_COL:
                    "Group",
                "growth_pct":
                    "Growth(%)",
                "mean_dev_exp":
                    "Mean dev. exp.",
                "median_dev_exp":
                    "Median dev. exp.",
            }
        )
    )

    return summary[
        [
            "Group",
            "N",
            "Growth(%)",
            "Mean dev. exp.",
            "Median dev. exp.",
        ]
    ]

def projects_with_complete_window(
    df_matched,
    window_months,
    commit_data_start,
    commit_data_end,
):
    df_window = df_matched.copy()

    df_window["before_start"] = (
        df_window["created_at"]
        - pd.DateOffset(
            months=window_months
        )
    )

    df_window["before_end"] = (
        df_window["created_at"]
    )

    df_window["after_start"] = (
        df_window["created_at"]
    )

    df_window["after_end"] = (
        df_window["created_at"]
        + pd.DateOffset(
            months=window_months
        )
    )

    return df_window[
        df_window[
            "before_start"
        ].ge(commit_data_start)
        & df_window[
            "after_end"
        ].le(commit_data_end)
    ].copy()


def count_commits_between(
    repo_commits,
    start,
    end,
):
    return (
        repo_commits.ge(start)
        & repo_commits.lt(end)
    ).sum()


def add_development_spend_tertiles(df):
    df = df.copy()

    tertiles = pd.Series(
        index=df.index,
        dtype="object",
    )

    ordered_index = df.sort_values(
        [
            "development_expense_amount_usd",
            PROJECT_COL,
        ],
        ascending=[
            True,
            True,
        ],
    ).index

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

    df[
        SPEND_TERTILE_COL
    ] = pd.Categorical(
        tertiles,
        categories=
            SPEND_TERTILE_LABELS,
        ordered=True,
    )

    return df


def build_commit_change(
    df_analyzable,
    commits_by_repo,
    window_months,
):
    rows = []

    empty_commits = pd.Series(
        dtype="datetime64[ns]"
    )

    for index, row in enumerate(
        df_analyzable.itertuples(
            index=False
        ),
        start=1,
    ):
        repo_commits = (
            commits_by_repo.get(
                row.repo_name,
                empty_commits,
            )
        )

        commits_before = (
            count_commits_between(
                repo_commits,
                row.before_start,
                row.before_end,
            )
        )

        commits_after = (
            count_commits_between(
                repo_commits,
                row.after_start,
                row.after_end,
            )
        )

        growth_rate_pct = (
            np.nan
            if commits_before == 0
            else (
                commits_after
                - commits_before
            )
            / commits_before
            * 100
        )

        rows.append(
            {
                "id":
                    row.id,
                "name":
                    row.name,
                "slug":
                    row.slug,
                "github_account":
                    row.github_account,
                "repo_name":
                    row.repo_name,
                "created_at":
                    row.created_at,
                "window_months":
                    window_months,
                "commits_before":
                    commits_before,
                "commits_after":
                    commits_after,
                "growth_rate_pct":
                    growth_rate_pct,
            }
        )

        if (
            index % 100 == 0
            or index
            == len(df_analyzable)
        ):
            print(
                f"Processed {index} / "
                f"{len(df_analyzable)} "
                "projects"
            )

    return pd.DataFrame(rows)


def analyze_window(
    window_months,
    df_matched,
    commits_by_repo,
    commit_data_start,
    commit_data_end,
    df_project_spending,
):
    print(
        f"\n\n===== Window: "
        f"{window_months} months ====="
    )

    df_analyzable = (
        projects_with_complete_window(
            df_matched,
            window_months,
            commit_data_start,
            commit_data_end,
        )
    )

    print(
        "Analyzable projects:",
        len(df_analyzable),
    )

    df_commit_change = (
        build_commit_change(
            df_analyzable,
            commits_by_repo,
            window_months,
        )
    )

    df_merged = (
        df_commit_change.merge(
            df_project_spending,
            left_on="slug",
            right_on=PROJECT_COL,
            how="inner",
        )
    )

    n_growth_rate_nan = (
        df_merged[
            "growth_rate_pct"
        ].isna().sum()
    )

    df_analysis = (
        df_merged[
            df_merged[
                "growth_rate_pct"
            ].notna()
        ].copy()
    )

    df_analysis = (
        add_development_spend_tertiles(
            df_analysis
        )
    )

    print(
        "\n===== Merged analysis data ====="
    )
    print(
        "Projects merged:",
        len(df_merged),
    )
    print(
        "Projects with commits_before = 0 "
        "excluded:",
        n_growth_rate_nan,
    )
    print(
        "Projects used in final analysis:",
        len(df_analysis),
    )

    print(
        "\n===== Projects by development "
        "spending tertile ====="
    )
    print(
        df_analysis[
            SPEND_TERTILE_COL
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    summary = summarize_by_bin(
        df_analysis
    )

    print(
        "\n===== Table output ====="
    )
    print(
        summary.to_string(
            index=False,
            float_format=lambda value:
                f"{value:,.3f}",
        )
    )

    summary_filename = ("table_viii.csv")

    summary.to_csv(
        summary_filename,
        index=False,
        float_format="%.3f",
    )

    (
        test_result,
        pairwise_result,
    ) = (
        test_growth_rate_between_spend_tertiles(
            df_analysis,
            window_months,
        )
    )

    return (
        test_result,
        pairwise_result,
        summary,
        df_analysis,
    )


def save_all_windows(
    test_results,
    pairwise_results,
):
    df_test_results = pd.DataFrame(
        test_results
    )

    print(
        "\n===== Kruskal-Wallis results ====="
    )
    print(
        df_test_results.to_string(
            index=False,
            float_format=lambda value:
                f"{value:.6f}",
        )
    )

    non_empty_pairwise = [
        result
        for result in pairwise_results
        if (
            result is not None
            and not result.empty
        )
    ]

    if not non_empty_pairwise:
        return

    df_pairwise_results = pd.concat(
        non_empty_pairwise,
        ignore_index=True,
    )

    print(
        "\n===== Pairwise Mann-Whitney "
        "results ====="
    )
    print(
        df_pairwise_results.to_string(
            index=False,
            float_format=lambda value:
                f"{value:.6f}",
        )
    )



def main():
    engine = database_engine()

    try:
        df_expense = load_expenses(
            engine
        )

        df_expense = (
            add_expense_amount_usd(
                df_expense
            )
        )

        df_project_spending = (
            build_project_spending(
                df_expense
            )
        )

        commit_args = load_commit_base(
            engine
        )

        all_test_results = []
        all_pairwise_results = []

        for window_months in (
            WINDOW_MONTHS_LIST
        ):
            (
                test_result,
                pairwise_result,
                _,
                _,
            ) = analyze_window(
                window_months,
                *commit_args,
                df_project_spending,
            )

            all_test_results.append(
                test_result
            )

            all_pairwise_results.append(
                pairwise_result
            )

        save_all_windows(
            all_test_results,
            all_pairwise_results,
        )

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
