import numpy as np
import pandas as pd

from config import ANALYSIS_WINDOWS, METRICS


def calculate_growth_rates(
    df_monthly: pd.DataFrame,
) -> pd.DataFrame:
    """
    各プロジェクトについて、基準日前後の同じ長さの期間を比較する。

    例:
        window=3
        before = relative_month -3, -2, -1 の合計
        after  = relative_month  0,  1,  2 の合計

    growth_rate_pct =
        (after_count - before_count) / before_count * 100

    before_count == 0 の場合は増加率をNaNとし、
    activity_statusで区別する。
    """
    result_rows = []

    for metric_name in METRICS:
        df_wide = (
            df_monthly
            .pivot_table(
                index=[
                    "collective_id",
                    "repo_name",
                ],
                columns="relative_month",
                values=metric_name,
                aggfunc="sum",
                fill_value=0,
            )
            .reset_index()
        )

        for window in ANALYSIS_WINDOWS:
            before_months = list(range(-window, 0))
            after_months = list(range(0, window))

            before_count = df_wide[before_months].sum(axis=1)
            after_count = df_wide[after_months].sum(axis=1)

            difference = after_count - before_count

            growth_rate_pct = np.where(
                before_count > 0,
                difference / before_count * 100,
                np.nan,
            )

            # 0件の扱いを明示する
            activity_status = np.select(
                [
                    (before_count > 0) & (after_count > before_count),
                    (before_count > 0) & (after_count == before_count),
                    (before_count > 0) & (after_count < before_count),
                    (before_count == 0) & (after_count > 0),
                    (before_count == 0) & (after_count == 0),
                ],
                [
                    "increased",
                    "unchanged",
                    "decreased",
                    "new_after",
                    "no_activity",
                ],
                default="unknown",
            )

            # 0件を含めて扱える補助指標
            log_change = (
                np.log1p(after_count)
                - np.log1p(before_count)
            )

            for index in range(len(df_wide)):
                result_rows.append({
                    "collective_id":
                        df_wide.iloc[index]["collective_id"],
                    "repo_name":
                        df_wide.iloc[index]["repo_name"],
                    "metric": metric_name,
                    "window_months": window,
                    "before_count": int(before_count.iloc[index]),
                    "after_count": int(after_count.iloc[index]),
                    "difference": int(difference.iloc[index]),
                    "growth_rate_pct":
                        growth_rate_pct[index],
                    "log_change": log_change.iloc[index],
                    "activity_status":
                        activity_status[index],
                })

    return pd.DataFrame(result_rows)


def summarize_growth_rates(
    df_growth: pd.DataFrame,
) -> pd.DataFrame:
    """
    指標・期間ごとに増加率を集計する。

    growth_rate_pctはbefore_count > 0のプロジェクトのみ。
    new_afterとno_activityは別に件数・割合を出す。
    """
    summary_rows = []

    grouped = df_growth.groupby(
        ["metric", "window_months"],
        sort=True,
    )

    for (metric, window), group in grouped:
        valid_growth = group[
            group["growth_rate_pct"].notna()
        ]["growth_rate_pct"]

        status_counts = (
            group["activity_status"]
            .value_counts()
        )

        n_total = len(group)
        n_growth_valid = len(valid_growth)

        summary_rows.append({
            "metric": metric,
            "window_months": window,
            "n_projects_total": n_total,
            "n_growth_rate_valid": n_growth_valid,

            "mean_growth_rate_pct":
                valid_growth.mean(),
            "median_growth_rate_pct":
                valid_growth.median(),
            "q1_growth_rate_pct":
                valid_growth.quantile(0.25),
            "q3_growth_rate_pct":
                valid_growth.quantile(0.75),
            "min_growth_rate_pct":
                valid_growth.min(),
            "max_growth_rate_pct":
                valid_growth.max(),

            "mean_before_count":
                group["before_count"].mean(),
            "median_before_count":
                group["before_count"].median(),
            "mean_after_count":
                group["after_count"].mean(),
            "median_after_count":
                group["after_count"].median(),

            "increased_count":
                status_counts.get("increased", 0),
            "decreased_count":
                status_counts.get("decreased", 0),
            "unchanged_count":
                status_counts.get("unchanged", 0),
            "new_after_count":
                status_counts.get("new_after", 0),
            "no_activity_count":
                status_counts.get("no_activity", 0),

            "increased_rate_all":
                status_counts.get("increased", 0) / n_total,
            "decreased_rate_all":
                status_counts.get("decreased", 0) / n_total,
            "new_after_rate_all":
                status_counts.get("new_after", 0) / n_total,
            "no_activity_rate_all":
                status_counts.get("no_activity", 0) / n_total,

            "mean_log_change":
                group["log_change"].mean(),
            "median_log_change":
                group["log_change"].median(),
        })

    return (
        pd.DataFrame(summary_rows)
        .sort_values(["metric", "window_months"])
        .reset_index(drop=True)
    )
