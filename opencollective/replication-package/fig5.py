import re
import unicodedata

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from forex_python.converter import CurrencyRates
from scipy.stats import kruskal
from statsmodels.stats.multitest import multipletests

from duckdb_util import database_engine


WINDOW_MONTHS = 12
TERTILE_COL = "development_spend_amount_tertile"
TERTILES = ["Bottom 33%", "Middle 33%", "Top 33%"]

CATEGORY_LABELS = {
    "feature_development": "Feature development",
    "bug_fixing": "Bug fixing",
    "contributor_recruitment": "Contributor-oriented",
    "documentation": "Documentation",
    "maintenance": "Maintenance",
    "issue_triage_closure": "Issue triage / closure",
    "question_support": "Question / support",
    "other_labeled": "Other labeled",
    "unlabeled": "Unlabeled",
}

CATEGORY_ORDER = list(CATEGORY_LABELS)

CATEGORY_KEYS = {
    "bug_fixing": {
        "bug", "typebug", "0kindbug", "kindbug", "issuebug",
        "abug", "cbug", "tbug", "idefect", "p3minorbug",
        "bugbug",
    },
    "feature_development": {
        "enhancement", "feature", "featurerequest",
        "typeenhancement", "typefeature", "tenhancement",
        "cfeature", "improvement", "abilities", "visuals",
        "ui", "performance", "newfeaturerequest",
        "featuregui", "unicornfeaturerequest",
        "featuremultiworld", "awish", "rssenhancement",
        "enhancementfeature",
    },
    "contributor_recruitment": {
        "helpwanted", "goodfirstissue", "acceptingprs",
        "statusacceptingprs", "hacktoberfest",
    },
    "documentation": {
        "documentation", "areadocumentation", "cdocs", "doc",
    },
    "question_support": {
        "question", "discussion", "brainstorm",
    },
    "maintenance": {
        "repomaintenance", "arearepositorytooling", "typechore",
        "pipeline", "breakingchange", "refactoring", "crefactor",
        "ci", "cinfra", "portability",
    },
    "issue_triage_closure": {
        "stale", "2statusstale", "outdated", "invalid",
        "duplicate", "wontfix", "lockedduetoage", "triage",
    },
}


def normalize_label(value):
    value = unicodedata.normalize("NFKC", str(value)).lower()
    return re.sub(r"[^a-z0-9]+", "", value)


def load_data(engine):
    expenses = pd.read_sql(
        """
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
        """,
        engine,
    )

    collectives = pd.read_sql(
        """
        SELECT
            slug AS project_slug,
            created_at AS registration_at,
            github_account
        FROM public.collectives
        WHERE slug IS NOT NULL
          AND created_at IS NOT NULL
          AND github_account LIKE '%%/%%'
        """,
        engine,
    )

    issues = pd.read_sql(
        """
        SELECT
            repo_name,
            number,
            created_at,
            labels
        FROM public.github_issue_pr_items
        WHERE item_type = 'issue'
          AND repo_name IS NOT NULL
          AND number IS NOT NULL
          AND created_at IS NOT NULL
        """,
        engine,
    )

    return expenses, collectives, issues


def convert_expenses_to_usd(expenses):
    expenses = expenses.copy()

    expenses["amount_value"] = pd.to_numeric(
        expenses["amount_value"],
        errors="coerce",
    ).abs()

    expenses["amount_currency"] = (
        expenses["amount_currency"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    expenses = expenses[
        expenses["amount_value"].gt(0)
        & expenses["amount_currency"].ne("")
        & expenses["amount_currency"].ne("NAN")
    ].copy()

    converter = CurrencyRates()
    rates = {}

    for currency in expenses["amount_currency"].unique():
        try:
            rates[currency] = (
                1.0
                if currency == "USD"
                else converter.get_rate(currency, "USD")
            )
        except Exception:
            rates[currency] = np.nan

    expenses["amount_usd"] = (
        expenses["amount_value"]
        * expenses["amount_currency"].map(rates)
    )

    return expenses.dropna(subset=["amount_usd"])


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
            development_expense_amount_usd=(
                "development_amount_usd",
                "sum",
            )
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

    candidate_issues = issues.merge(
        projects,
        on="repo_name",
        how="inner",
    )

    candidate_issues = candidate_issues[
        candidate_issues["created_at"].ge(
            candidate_issues["registration_at"]
        )
        & candidate_issues["created_at"].lt(
            candidate_issues["registration_at"]
            + pd.DateOffset(months=WINDOW_MONTHS)
        )
    ].copy()

    projects_with_issues = candidate_issues[
        ["project_slug", "repo_name"]
    ].drop_duplicates()

    projects = projects.merge(
        projects_with_issues,
        on=["project_slug", "repo_name"],
        how="inner",
    )

    ordered_indexes = projects.sort_values(
        [
            "development_expense_amount_usd",
            "project_slug",
        ]
    ).index

    projects[TERTILE_COL] = pd.NA

    for label, indexes in zip(
        TERTILES,
        np.array_split(ordered_indexes, 3),
    ):
        projects.loc[indexes, TERTILE_COL] = label

    projects[TERTILE_COL] = pd.Categorical(
        projects[TERTILE_COL],
        categories=TERTILES,
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

    return issues_after.drop_duplicates(
        ["project_slug", "repo_name", "number"]
    )


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
                    TERTILE_COL: getattr(issue, TERTILE_COL),
                    "category": category,
                }
            )

    return pd.DataFrame(rows)


def build_category_summary(categories):
    counts = (
        categories.groupby(
            [TERTILE_COL, "category"],
            observed=False,
            as_index=False,
        )
        .agg(n=("number", "count"))
    )

    counts["share"] = (
        counts["n"]
        / counts.groupby(
            TERTILE_COL,
            observed=False,
        )["n"].transform("sum")
    )

    return counts


def build_project_category_ratios(issues, categories):
    project_totals = (
        issues.groupby(
            ["project_slug", "repo_name", TERTILE_COL],
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
                TERTILE_COL,
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
        project_totals.assign(key=1)
        .merge(
            category_master.assign(key=1),
            on="key",
        )
        .drop(columns="key")
        .merge(
            category_counts,
            on=[
                "project_slug",
                "repo_name",
                TERTILE_COL,
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


def run_kruskal_wallis(ratios):
    rows = []

    for category in CATEGORY_ORDER:
        category_data = ratios[
            ratios["category"].eq(category)
        ]

        groups = [
            category_data.loc[
                category_data[TERTILE_COL].eq(label),
                "category_ratio",
            ].dropna()
            for label in TERTILES
        ]

        if any(group.empty for group in groups):
            statistic = np.nan
            p_value = np.nan
        elif category_data["category_ratio"].nunique() <= 1:
            statistic = np.nan
            p_value = 1.0
        else:
            result = kruskal(*groups)
            statistic = result.statistic
            p_value = result.pvalue

        rows.append(
            {
                "Category": CATEGORY_LABELS[category],
                "H": statistic,
                "p-value": p_value,
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

    print(
        results.to_string(
            index=False,
            float_format=lambda value: f"{value:.6f}",
        )
    )


def save_plot(summary):
    plot_data = (
        summary.pivot_table(
            index=TERTILE_COL,
            columns="category",
            values="share",
            fill_value=0,
            observed=False,
        )
        .reindex(
            index=TERTILES,
            columns=CATEGORY_ORDER,
            fill_value=0,
        )
    )

    fig, ax = plt.subplots(figsize=(6, 3.5))
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
    ax.set_ylabel("Development spending amount")
    ax.xaxis.set_major_formatter(
        lambda value, _: f"{value * 100:.0f}%"
    )
    ax.grid(axis="x", linestyle=":", alpha=0.6)
    ax.set_axisbelow(True)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.20),
        ncol=3,
        frameon=False,
        fontsize=8,
    )

    fig.tight_layout()
    fig.savefig("Fig5.pdf", bbox_inches="tight")
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

    run_kruskal_wallis(ratios)


if __name__ == "__main__":
    main()