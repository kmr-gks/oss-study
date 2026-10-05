import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from statsmodels.stats.multitest import multipletests
from output_util import FIGURES_DIR, TABLES_DIR

from duckdb_util import database_engine
from fig5 import (
    CATEGORY_KEYS,
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    WINDOW_MONTHS,
    convert_expenses_to_usd,
    load_data,
    normalize_label,
)
from tableVIII import cliffs_delta, effect_size_label


GROUP_COL = "development_spend_presence"
NO_DEV_LABEL = "No dev. expense"
DEV_LABEL = "Dev. expense observed"
GROUPS = [NO_DEV_LABEL, DEV_LABEL]


def build_projects(expenses, collectives, issues):
    expenses = expenses.copy()

    expenses["development_amount_usd"] = np.where(
        expenses["is_development"].eq(True),
        expenses["amount_usd"],
        0.0,
    )

    spending = (
        expenses.groupby("project_slug", as_index=False)
        .agg(
            development_expense_count=(
                "is_development",
                lambda values: values.eq(True).sum(),
            ),
            development_expense_amount_usd=(
                "development_amount_usd",
                "sum",
            ),
        )
    )

    collectives = collectives.copy()

    collectives["registration_at"] = pd.to_datetime(
        collectives["registration_at"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    collectives["repo_name"] = (
        collectives["github_account"]
        .astype(str)
        .str.strip()
        .str.replace("/", "-", regex=False)
    )

    issues = issues.copy()

    issues["created_at"] = pd.to_datetime(
        issues["created_at"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    projects = (
        collectives[
            [
                "project_slug",
                "repo_name",
                "registration_at",
            ]
        ]
        .dropna()
        .drop_duplicates(
            ["project_slug", "repo_name"],
            keep="first",
        )
        .merge(
            spending,
            on="project_slug",
            how="inner",
        )
    )

    projects[GROUP_COL] = pd.Categorical(
        np.where(
            projects["development_expense_count"].gt(0),
            DEV_LABEL,
            NO_DEV_LABEL,
        ),
        categories=GROUPS,
        ordered=True,
    )

    issues_after = issues.merge(
        projects,
        on="repo_name",
        how="inner",
    )

    issues_after = issues_after[
        issues_after["created_at"].ge(
            issues_after["registration_at"]
        )
        & issues_after["created_at"].lt(
            issues_after["registration_at"]
            + pd.DateOffset(months=WINDOW_MONTHS)
        )
    ].copy()

    issues_after = issues_after.drop_duplicates(
        ["project_slug", "repo_name", "number"]
    )

    print("\n===== Projects with issues in window =====")
    print(
        issues_after[["project_slug", "repo_name", GROUP_COL]]
        .drop_duplicates()[GROUP_COL]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print("\n===== Issues in window =====")
    print(
        issues_after[GROUP_COL]
        .value_counts()
        .sort_index()
        .to_string()
    )

    return issues_after


def classify_issues(issues):
    rows = []

    for issue in issues.itertuples(index=False):
        raw_labels = (
            []
            if pd.isna(issue.labels) or not str(issue.labels).strip()
            else str(issue.labels).split(";")
        )

        normalized_labels = {
            normalize_label(label)
            for label in raw_labels
            if normalize_label(label)
        }

        categories = {
            category
            for category, keys in CATEGORY_KEYS.items()
            if normalized_labels & keys
        }

        if not normalized_labels:
            categories = {"unlabeled"}
        elif not categories:
            categories = {"other_labeled"}

        for category in categories:
            rows.append(
                {
                    "project_slug": issue.project_slug,
                    "repo_name": issue.repo_name,
                    "number": issue.number,
                    GROUP_COL: getattr(issue, GROUP_COL),
                    "category": category,
                }
            )

    return pd.DataFrame(rows)


def build_category_summary(categories):
    counts = (
        categories.groupby(
            [GROUP_COL, "category"],
            observed=False,
            as_index=False,
        )
        .agg(n=("number", "count"))
    )

    counts["share"] = (
        counts["n"]
        / counts.groupby(
            GROUP_COL,
            observed=False,
        )["n"].transform("sum")
    )

    return counts


def build_project_category_ratios(issues, categories):
    project_totals = (
        issues.groupby(
            ["project_slug", "repo_name", GROUP_COL],
            observed=True,
            as_index=False,
        )
        .agg(total_issues=("number", "nunique"))
    )

    category_counts = (
        categories.drop_duplicates(
            ["project_slug", "repo_name", "number", "category"]
        )
        .groupby(
            [
                "project_slug",
                "repo_name",
                GROUP_COL,
                "category",
            ],
            observed=True,
            as_index=False,
        )
        .agg(category_issues=("number", "count"))
    )

    category_master = pd.DataFrame(
        {"category": CATEGORY_ORDER}
    )

    ratios = (
        project_totals.merge(
            category_master,
            how="cross",
        )
        .merge(
            category_counts,
            on=[
                "project_slug",
                "repo_name",
                GROUP_COL,
                "category",
            ],
            how="left",
        )
    )

    ratios["category_issues"] = (
        ratios["category_issues"]
        .fillna(0)
        .astype(int)
    )

    ratios["category_ratio"] = (
        ratios["category_issues"]
        / ratios["total_issues"]
    )

    return ratios


def run_mannwhitney(ratios):
    rows = []

    for category in CATEGORY_ORDER:
        category_data = ratios[
            ratios["category"].eq(category)
        ]

        group_no_dev, group_dev = [
            category_data.loc[
                category_data[GROUP_COL].eq(label),
                "category_ratio",
            ].dropna()
            for label in GROUPS
        ]

        if group_no_dev.empty or group_dev.empty:
            statistic = np.nan
            p_value = np.nan
            delta = np.nan
        elif category_data["category_ratio"].nunique() <= 1:
            statistic = np.nan
            p_value = 1.0
            delta = 0.0
        else:
            result = mannwhitneyu(
                group_dev,
                group_no_dev,
                alternative="two-sided",
            )
            statistic = result.statistic
            p_value = result.pvalue
            # Positive delta: the category ratio tends to be higher
            # when development expense is observed.
            delta = cliffs_delta(group_dev, group_no_dev)

        rows.append(
            {
                "Category": CATEGORY_LABELS[category],
                "N no dev.": len(group_no_dev),
                "N dev.": len(group_dev),
                "Mean ratio no dev.": group_no_dev.mean(),
                "Mean ratio dev.": group_dev.mean(),
                "U": statistic,
                "p-value": p_value,
                "Cliff's delta": delta,
                "Effect size": effect_size_label(delta),
            }
        )

    results = pd.DataFrame(rows)
    valid = results["p-value"].notna()

    results["Holm-adjusted p-value"] = np.nan
    results["Significant"] = "NA"

    if valid.any():
        reject, adjusted, _, _ = multipletests(
            results.loc[valid, "p-value"],
            alpha=0.05,
            method="holm",
        )

        results.loc[valid, "Holm-adjusted p-value"] = adjusted
        results.loc[valid, "Significant"] = np.where(
            reject,
            "Yes",
            "No",
        )

    print("\n===== Mann-Whitney U tests by category =====")
    print(
        results.to_string(
            index=False,
            float_format=lambda value: f"{value:.6f}",
        )
    )

    results.to_csv(
        TABLES_DIR / "fig5_dev_presence_tests.csv",
        index=False,
        float_format="%.6f",
    )


def save_plot(summary):
    plot_data = (
        summary.pivot_table(
            index=GROUP_COL,
            columns="category",
            values="share",
            fill_value=0,
            observed=False,
        )
        .reindex(
            index=GROUPS,
            columns=CATEGORY_ORDER,
            fill_value=0,
        )
    )

    print("\n===== Share of category assignments =====")
    print(
        plot_data.rename(columns=CATEGORY_LABELS)
        .T.to_string(float_format=lambda value: f"{value:.3f}")
    )

    fig, ax = plt.subplots(
        figsize=(6.3, 2.3),
        layout="constrained",
    )
    left = np.zeros(len(plot_data))

    for category in CATEGORY_ORDER:
        values = plot_data[category].to_numpy()

        ax.barh(
            plot_data.index.astype(str),
            values,
            left=left,
            height=0.62,
            label=CATEGORY_LABELS[category],
            edgecolor="white",
            linewidth=0.5,
        )

        left += values

    ax.set_xlim(0, 1)
    ax.set_xlabel("Share of category assignments")
    ax.set_ylabel("Development spending")
    ax.xaxis.set_major_formatter(
        lambda value, _: f"{value * 100:.0f}%"
    )
    ax.grid(axis="x", linestyle=":", alpha=0.6)
    ax.set_axisbelow(True)
    ax.legend(
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        ncol=1,
        frameon=False,
        fontsize=8,
    )

    fig.savefig(
        FIGURES_DIR / "issue_category_composition.pdf",
        bbox_inches="tight",
        pad_inches=0.02,
    )
    plt.close(fig)


def main():
    engine = database_engine()

    try:
        expenses, collectives, issues = load_data(engine)
    finally:
        engine.dispose()

    expenses = convert_expenses_to_usd(expenses)
    issues = build_projects(expenses, collectives, issues)
    categories = classify_issues(issues)

    save_plot(build_category_summary(categories))

    ratios = build_project_category_ratios(
        issues,
        categories,
    )

    run_mannwhitney(ratios)


if __name__ == "__main__":
    main()
