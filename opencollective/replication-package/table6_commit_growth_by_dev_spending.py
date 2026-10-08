import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from duckdb_util import database_engine
from output_util import TABLES_DIR
from commit_growth_util import (
    PROJECT_COL,
    SIGNIFICANCE_LEVEL,
    add_expense_amount_usd,
    build_commit_change,
    build_project_spending,
    cliffs_delta,
    effect_size_label,
    load_commit_base,
    load_expenses,
    print_group_stats,
    projects_with_complete_window,
)


WINDOW_MONTHS_LIST = [12]

DEV_PRESENCE_COL = "development_spend_presence"
NO_DEV_LABEL = "No dev. expense"
DEV_LABEL = "Dev. expense observed"
DEV_PRESENCE_LABELS = [
    NO_DEV_LABEL,
    DEV_LABEL,
]


def add_development_spend_presence(df):
    df = df.copy()

    df[DEV_PRESENCE_COL] = pd.Categorical(
        np.where(
            df["development_expense_count"].gt(0),
            DEV_LABEL,
            NO_DEV_LABEL,
        ),
        categories=DEV_PRESENCE_LABELS,
        ordered=True,
    )

    return df


def summarize_by_presence(df):
    summary = (
        df
        .groupby(
            DEV_PRESENCE_COL,
            observed=False,
        )
        .agg(
            N=("growth_rate_pct", "count"),
            growth_pct=("growth_rate_pct", "median"),
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
                DEV_PRESENCE_COL: "group",
                "N": "n",
                "growth_pct": "median_growth_pct",
                "mean_dev_exp": "mean_dev_expense_usd",
                "median_dev_exp": "median_dev_expense_usd",
            }
        )
    )

    return summary[
        [
            "group",
            "n",
            "median_growth_pct",
            "mean_dev_expense_usd",
            "median_dev_expense_usd",
        ]
    ]


def test_growth_rate_between_presence_groups(
    df,
    window_months,
):
    groups = {
        label: df.loc[
            df[DEV_PRESENCE_COL] == label,
            "growth_rate_pct",
        ].dropna()
        for label in DEV_PRESENCE_LABELS
    }

    group_no_dev = groups[NO_DEV_LABEL]
    group_dev = groups[DEV_LABEL]

    print("\n===== Mann-Whitney U test =====")

    for label in DEV_PRESENCE_LABELS:
        print_group_stats(label, groups[label])

    if len(group_no_dev) == 0 or len(group_dev) == 0:
        print(
            "\nMann-Whitney U test skipped "
            "because at least one group is empty."
        )
        p_value = np.nan
        u_statistic = np.nan
        significant = "NA"
        delta = np.nan
    else:
        test_result = mannwhitneyu(
            group_dev,
            group_no_dev,
            alternative="two-sided",
        )
        u_statistic = test_result.statistic
        p_value = test_result.pvalue
        significant = (
            "Yes"
            if p_value < SIGNIFICANCE_LEVEL
            else "No"
        )
        # Positive delta: growth tends to be higher when dev. expense is observed.
        delta = cliffs_delta(group_dev, group_no_dev)

        print("\nMann-Whitney U test result")
        print("U statistic:", f"{u_statistic:.3f}")
        print("P-value:", f"{p_value:.6f}")
        print("Significant:", significant)
        print("Cliff's delta:", f"{delta:.3f}")
        print("Effect size:", effect_size_label(delta))

    return {
        "Window months": window_months,
        "Group A": NO_DEV_LABEL,
        "Group B": DEV_LABEL,
        "N A": len(group_no_dev),
        "N B": len(group_dev),
        "Median growth A": (
            group_no_dev.median()
            if len(group_no_dev)
            else np.nan
        ),
        "Median growth B": (
            group_dev.median()
            if len(group_dev)
            else np.nan
        ),
        "U statistic": u_statistic,
        "P-value": p_value,
        "Significant": significant,
        "Cliff's delta": delta,
        "Effect size": effect_size_label(delta),
    }


def analyze_window(
    window_months,
    df_matched,
    commits_by_repo,
    commit_data_start,
    commit_data_end,
    df_project_spending,
):
    print(f"\n\n===== Window: {window_months} months =====")

    df_analyzable = projects_with_complete_window(
        df_matched,
        window_months,
        commit_data_start,
        commit_data_end,
    )

    print("Analyzable projects:", len(df_analyzable))

    df_commit_change = build_commit_change(
        df_analyzable,
        commits_by_repo,
        window_months,
    )

    df_merged = df_commit_change.merge(
        df_project_spending,
        left_on="slug",
        right_on=PROJECT_COL,
        how="inner",
    )

    n_growth_rate_nan = df_merged["growth_rate_pct"].isna().sum()

    df_analysis = df_merged[
        df_merged["growth_rate_pct"].notna()
    ].copy()

    df_analysis = add_development_spend_presence(df_analysis)

    print("\n===== Merged analysis data =====")
    print("Projects merged:", len(df_merged))
    print(
        "Projects with commits_before = 0 excluded:",
        n_growth_rate_nan,
    )
    print("Projects used in final analysis:", len(df_analysis))

    print("\n===== Projects by development spending presence =====")
    print(
        df_analysis[DEV_PRESENCE_COL]
        .value_counts()
        .sort_index()
        .to_string()
    )

    summary = summarize_by_presence(df_analysis)

    print("\n===== Table output =====")
    print(
        summary.to_string(
            index=False,
            float_format=lambda value: f"{value:,.3f}",
        )
    )

    summary.to_csv(
        TABLES_DIR / "table6_commit_growth_by_dev_spending.csv",
        index=False,
    )

    test_result = test_growth_rate_between_presence_groups(
        df_analysis,
        window_months,
    )

    return test_result, summary, df_analysis


def main():
    engine = database_engine()

    try:
        df_expense = load_expenses(engine)
        df_expense = add_expense_amount_usd(df_expense)
        df_project_spending = build_project_spending(df_expense)

        commit_args = load_commit_base(engine)

        all_test_results = []

        for window_months in WINDOW_MONTHS_LIST:
            test_result, _, _ = analyze_window(
                window_months,
                *commit_args,
                df_project_spending,
            )
            all_test_results.append(test_result)

        pd.DataFrame(all_test_results).rename(
            columns={
                "Window months": "window_months",
                "Group A": "group_a",
                "Group B": "group_b",
                "N A": "n_a",
                "N B": "n_b",
                "Median growth A": "median_growth_pct_a",
                "Median growth B": "median_growth_pct_b",
                "U statistic": "u_statistic",
                "P-value": "p_value",
                "Significant": "significant",
                "Cliff's delta": "cliffs_delta",
                "Effect size": "effect_size",
            }
        ).to_csv(
            TABLES_DIR / "table6_commit_growth_test.csv",
            index=False,
        )

        print("\n===== Mann-Whitney U results =====")
        print(
            pd.DataFrame(all_test_results).to_string(
                index=False,
                float_format=lambda value: f"{value:.6f}",
            )
        )

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
