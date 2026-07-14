import pandas as pd

from config import METRICS, RELATIVE_MONTHS


PROJECT_ID_COLUMNS = [
    "collective_id",
    "project_slug",
    "project_name",
    "repo_name",
    "github_account",
    "opencollective_created_at",
]


def count_metric_in_window(
    df_items: pd.DataFrame,
    metric_config: dict,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> int:
    date_column = metric_config["date_column"]
    item_type = metric_config["item_type"]

    mask = (
        df_items["item_type"].eq(item_type)
        & df_items[date_column].notna()
        & df_items[date_column].ge(window_start)
        & df_items[date_column].lt(window_end)
    )

    return int(mask.sum())


def build_monthly_activity(
    df_items: pd.DataFrame,
    df_projects: pd.DataFrame,
    baseline_column: str = "opencollective_created_at",
) -> pd.DataFrame:
    """
    プロジェクト×相対月の月次活動表を作る。

    baseline_columnを変更すれば、将来
    first_contribution_at
    first_expense_at
    first_development_expense_at
    などにも流用できる。
    """
    monthly_rows = []

    grouped_items = {
        key: group
        for key, group in df_items.groupby("collective_id")
    }

    for index, project in enumerate(
        df_projects.itertuples(index=False),
        start=1,
    ):
        project_items = grouped_items.get(
            project.collective_id,
            df_items.iloc[0:0],
        )

        baseline_date = getattr(project, baseline_column)

        for relative_month in RELATIVE_MONTHS:
            month_start = (
                baseline_date
                + pd.DateOffset(months=relative_month)
            )
            month_end = (
                baseline_date
                + pd.DateOffset(months=relative_month + 1)
            )

            row = {
                "collective_id": project.collective_id,
                "project_slug": project.project_slug,
                "project_name": project.project_name,
                "repo_name": project.repo_name,
                "github_account": project.github_account,
                "baseline_at": baseline_date,
                "relative_month": relative_month,
                "period": (
                    "before"
                    if relative_month < 0
                    else "after"
                ),
                "month_start": month_start,
                "month_end": month_end,
            }

            for metric_name, metric_config in METRICS.items():
                row[metric_name] = count_metric_in_window(
                    project_items,
                    metric_config,
                    month_start,
                    month_end,
                )

            monthly_rows.append(row)

        if index % 100 == 0 or index == len(df_projects):
            print(
                f"Processed {index} / "
                f"{len(df_projects)} projects"
            )

    return pd.DataFrame(monthly_rows)


def summarize_monthly_activity(
    df_monthly: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for relative_month, group in df_monthly.groupby(
        "relative_month"
    ):
        row = {
            "relative_month": relative_month,
            "plot_month": (
                relative_month
                if relative_month < 0
                else relative_month + 1
            ),
            "n_projects": group["collective_id"].nunique(),
        }

        for metric_name in METRICS:
            row[f"mean_{metric_name}"] = (
                group[metric_name].mean()
            )
            row[f"median_{metric_name}"] = (
                group[metric_name].median()
            )
            row[f"q1_{metric_name}"] = (
                group[metric_name].quantile(0.25)
            )
            row[f"q3_{metric_name}"] = (
                group[metric_name].quantile(0.75)
            )

        rows.append(row)

    return (
        pd.DataFrame(rows)
        .sort_values("relative_month")
        .reset_index(drop=True)
    )


def identify_top_activity_repositories(
    df_monthly: pd.DataFrame,
    quantile: float = 0.99,
) -> tuple[set, pd.DataFrame]:
    """
    前後24か月の全指標合計を用いて、
    活動量上位1%のリポジトリを特定する。

    月ごとに別々のプロジェクトを除外するのではなく、
    分析全体で同じ巨大リポジトリを除外する。
    """
    metric_columns = list(METRICS.keys())

    df_repo_activity = (
        df_monthly
        .groupby(
            ["collective_id", "repo_name"],
            as_index=False,
        )[metric_columns]
        .sum()
    )

    df_repo_activity["total_activity"] = (
        df_repo_activity[metric_columns].sum(axis=1)
    )

    threshold = df_repo_activity[
        "total_activity"
    ].quantile(quantile)

    df_repo_activity["is_top_activity"] = (
        df_repo_activity["total_activity"] > threshold
    )

    excluded_ids = set(
        df_repo_activity.loc[
            df_repo_activity["is_top_activity"],
            "collective_id",
        ]
    )

    print("\n===== Top-activity exclusion =====")
    print("Quantile:", quantile)
    print("Threshold:", threshold)
    print("Excluded projects:", len(excluded_ids))
    print(
        df_repo_activity
        .sort_values("total_activity", ascending=False)
        .head(20)
        .to_string(index=False)
    )

    return excluded_ids, df_repo_activity


def exclude_projects(
    df_monthly: pd.DataFrame,
    excluded_collective_ids: set,
) -> pd.DataFrame:
    return df_monthly[
        ~df_monthly["collective_id"].isin(
            excluded_collective_ids
        )
    ].copy()