import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import wilcoxon
from statsmodels.stats.multitest import multipletests

from duckdb_util import database_engine

ANALYSIS_WINDOWS = [3, 6, 9, 12]

METRICS = {
    "commits": "Commits",
    "opened_issues": "Opened issues",
    "closed_issues": "Closed issues",
    "opened_pull_requests": "Opened pull requests",
    "closed_pull_requests": "Closed pull requests",
    "merged_pull_requests": "Merged pull requests",
}

ITEM_METRICS = {
    "opened_issues": ("issue", "created_at"),
    "closed_issues": ("issue", "closed_at"),
    "opened_pull_requests": ("pull_request", "created_at"),
    "closed_pull_requests": ("pull_request", "closed_at"),
    "merged_pull_requests": ("pull_request", "merged_at"),
}


def load_data():
    engine = database_engine()

    try:
        items = pd.read_sql(
            """
            SELECT
                collective_id,
                repo_name,
                item_type,
                created_at,
                closed_at,
                merged_at,
                opencollective_created_at
            FROM public.github_issue_pr_items
            WHERE collective_id IS NOT NULL
              AND repo_name IS NOT NULL
              AND opencollective_created_at IS NOT NULL
            """,
            engine,
        )

        commits = pd.read_sql(
            """
            SELECT DISTINCT
                repo_name,
                commit_hash,
                commit_time
            FROM public.commit_history
            WHERE repo_name IS NOT NULL
              AND commit_time IS NOT NULL
            """,
            engine,
        )
    finally:
        engine.dispose()

    for column in [
        "created_at",
        "closed_at",
        "merged_at",
        "opencollective_created_at",
    ]:
        items[column] = pd.to_datetime(
            items[column],
            utc=True,
            errors="coerce",
        ).dt.tz_convert(None)

    commits["commit_time"] = pd.to_datetime(
        commits["commit_time"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    items = items[
        items["opencollective_created_at"].notna()
    ].copy()

    commits = commits[
        commits["commit_time"].notna()
    ].copy()

    projects = (
        items[
            [
                "collective_id",
                "repo_name",
                "opencollective_created_at",
            ]
        ]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    commit_repositories = set(
        commits["repo_name"].unique()
    )

    projects = projects[
        projects["repo_name"].isin(
            commit_repositories
        )
    ].copy()

    items = items[
        items["repo_name"].isin(
            commit_repositories
        )
    ].copy()

    return items, commits, projects


def count_activity(
    data,
    date_column,
    baseline,
    window,
    before,
):
    if before:
        start = baseline - pd.DateOffset(months=window)
        end = baseline
    else:
        start = baseline
        end = baseline + pd.DateOffset(months=window)

    return int(
        (
            data[date_column].notna()
            & data[date_column].ge(start)
            & data[date_column].lt(end)
        ).sum()
    )


def calculate_growth_rates(items, commits, projects):
    items_by_project = {
        key: group
        for key, group in items.groupby(
            ["collective_id", "repo_name"]
        )
    }

    commits_by_repo = {
        repo_name: group
        for repo_name, group in commits.groupby(
            "repo_name"
        )
    }

    empty_items = items.iloc[0:0]
    empty_commits = commits.iloc[0:0]

    rows = []

    for project in projects.itertuples(index=False):
        project_items = items_by_project.get(
            (
                project.collective_id,
                project.repo_name,
            ),
            empty_items,
        )

        project_commits = commits_by_repo.get(
            project.repo_name,
            empty_commits,
        )

        baseline = project.opencollective_created_at

        for window in ANALYSIS_WINDOWS:
            commit_before = count_activity(
                project_commits,
                "commit_time",
                baseline,
                window,
                before=True,
            )

            commit_after = count_activity(
                project_commits,
                "commit_time",
                baseline,
                window,
                before=False,
            )

            rows.append(
                make_growth_row(
                    project,
                    "commits",
                    window,
                    commit_before,
                    commit_after,
                )
            )

            for metric, (
                item_type,
                date_column,
            ) in ITEM_METRICS.items():
                metric_items = project_items[
                    project_items["item_type"].eq(
                        item_type
                    )
                ]

                before_count = count_activity(
                    metric_items,
                    date_column,
                    baseline,
                    window,
                    before=True,
                )

                after_count = count_activity(
                    metric_items,
                    date_column,
                    baseline,
                    window,
                    before=False,
                )

                rows.append(
                    make_growth_row(
                        project,
                        metric,
                        window,
                        before_count,
                        after_count,
                    )
                )

    return pd.DataFrame(rows)


def make_growth_row(
    project,
    metric,
    window,
    before_count,
    after_count,
):
    growth_rate = (
        (after_count - before_count)
        / before_count
        * 100
        if before_count > 0
        else np.nan
    )

    return {
        "collective_id": project.collective_id,
        "repo_name": project.repo_name,
        "metric": metric,
        "window_months": window,
        "before_count": before_count,
        "after_count": after_count,
        "growth_rate_pct": growth_rate,
    }


def run_wilcoxon_tests(growth):
    rows = []

    for metric in METRICS:
        for window in ANALYSIS_WINDOWS:
            group = growth[
                growth["metric"].eq(metric)
                & growth["window_months"].eq(window)
                & growth["before_count"].gt(0)
            ].copy()

            before = group["before_count"].astype(float)
            after = group["after_count"].astype(float)
            difference = after - before

            if group.empty:
                statistic = np.nan
                p_value = np.nan
            elif difference.ne(0).sum() == 0:
                statistic = 0.0
                p_value = 1.0
            else:
                result = wilcoxon(
                    after,
                    before,
                    alternative="greater",
                    zero_method="wilcox",
                    method="auto",
                )

                statistic = result.statistic
                p_value = result.pvalue

            valid_growth = group[
                "growth_rate_pct"
            ].dropna()

            rows.append(
                {
                    "metric": metric,
                    "window_months": window,
                    "n_projects_tested": len(group),
                    "n_nonzero_differences": int(
                        difference.ne(0).sum()
                    ),
                    "median_before_count": before.median(),
                    "median_after_count": after.median(),
                    "median_difference": difference.median(),
                    "median_growth_rate_pct": (
                        valid_growth.median()
                    ),
                    "wilcoxon_statistic": statistic,
                    "p_value_raw": p_value,
                }
            )

    tests = pd.DataFrame(rows)

    valid = tests["p_value_raw"].notna()

    tests["p_value_holm"] = np.nan
    tests["significant_holm"] = False

    if valid.any():
        reject, adjusted_p, _, _ = multipletests(
            tests.loc[valid, "p_value_raw"],
            alpha=0.05,
            method="holm",
        )

        tests.loc[valid, "p_value_holm"] = adjusted_p
        tests.loc[valid, "significant_holm"] = reject

    tests["test_alternative"] = (
        "after_count > before_count"
    )
    tests["include_zero_before"] = False

    return tests


def save_median_growth_plot(growth, output_path):
    summary = (
        growth[
            growth["before_count"].gt(0)
            & growth["growth_rate_pct"].notna()
        ]
        .groupby(
            ["metric", "window_months"],
            as_index=False,
        )
        .agg(
            median_growth_rate_pct=(
                "growth_rate_pct",
                "median",
            )
        )
    )

    fig, ax = plt.subplots(figsize=(5, 4.5))

    for metric, label in METRICS.items():
        metric_data = (
            summary[
                summary["metric"].eq(metric)
            ]
            .sort_values("window_months")
        )

        ax.plot(
            metric_data["window_months"],
            metric_data[
                "median_growth_rate_pct"
            ],
            marker="o",
            label=label,
        )

    ax.axhline(
        y=0,
        linestyle="--",
        linewidth=1,
    )

    ax.set_xticks(ANALYSIS_WINDOWS)
    ax.set_xlabel(
        "Window size before and after registration (months)"
    )
    ax.set_ylabel("Median growth rate (%)")
    ax.grid(True, alpha=0.3)
    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, -0.5),
        ncol=2,
    )

    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)

def format_tests_for_table(tests):
    metric_labels = {
        "opened_issues": "Opened issues",
        "closed_issues": "Closed issues",
        "opened_pull_requests": "Opened PRs",
        "closed_pull_requests": "Closed PRs",
        "merged_pull_requests": "Merged PRs",
        "commits": "Commits",
    }

    table = tests.pivot(
        index="metric",
        columns="window_months",
        values="p_value_holm",
    )

    table = table.reindex(
        [
            "opened_issues",
            "closed_issues",
            "opened_pull_requests",
            "closed_pull_requests",
            "merged_pull_requests",
            "commits",
        ]
    )

    table = table.rename(
        index=metric_labels,
        columns={
            3: "3 mo.",
            6: "6 mo.",
            9: "9 mo.",
            12: "12 mo.",
        },
    )

    table.index.name = "Metric"

    return table.reset_index()

def main():
    from pathlib import Path

    items, commits, projects = load_data()

    growth = calculate_growth_rates(
        items,
        commits,
        projects,
    )

    tests = run_wilcoxon_tests(growth)

    table = format_tests_for_table(tests)

    table.to_csv(
        "table_vii.csv",
        index=False,
        float_format="%.3f",
    )

    save_median_growth_plot(
        growth,
        "Fig4.pdf",
    )


if __name__ == "__main__":
    main()