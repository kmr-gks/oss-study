import numpy as np
import pandas as pd
from scipy.stats import wilcoxon, ttest_rel

from config import (
    AFTER_WINDOWS,
    METRICS,
    MONTHS_BEFORE,
)


def safe_wilcoxon(
    after: pd.Series,
    before: pd.Series,
    alternative: str,
):
    differences = after - before

    if not differences.ne(0).any():
        return np.nan, np.nan

    result = wilcoxon(
        after,
        before,
        alternative=alternative,
    )

    return result.statistic, result.pvalue


def test_before_after_windows(
    df_monthly: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    各指標について、
    登録前12か月の月平均と
    登録後1/3/6/12か月の月平均を比較する。
    """
    project_rows = []
    test_rows = []

    for metric_name in METRICS:
        df_wide = (
            df_monthly
            .pivot_table(
                index=["collective_id", "repo_name"],
                columns="relative_month",
                values=metric_name,
                aggfunc="sum",
                fill_value=0,
            )
            .reset_index()
        )

        before_months = list(range(-MONTHS_BEFORE, 0))

        df_wide["before_12m_total"] = (
            df_wide[before_months].sum(axis=1)
        )
        df_wide["before_12m_monthly_avg"] = (
            df_wide["before_12m_total"]
            / MONTHS_BEFORE
        )

        for after_months in AFTER_WINDOWS:
            months = list(range(0, after_months))

            after_total = df_wide[months].sum(axis=1)
            after_average = after_total / after_months
            before_average = df_wide[
                "before_12m_monthly_avg"
            ]

            difference = after_average - before_average
            log_change = (
                np.log1p(after_average)
                - np.log1p(before_average)
            )

            two_stat, two_p = safe_wilcoxon(
                after_average,
                before_average,
                "two-sided",
            )
            greater_stat, greater_p = safe_wilcoxon(
                after_average,
                before_average,
                "greater",
            )
            less_stat, less_p = safe_wilcoxon(
                after_average,
                before_average,
                "less",
            )

            t_result = ttest_rel(
                after_average,
                before_average,
            )

            increased = int((difference > 0).sum())
            decreased = int((difference < 0).sum())
            unchanged = int((difference == 0).sum())
            n_projects = len(df_wide)

            test_rows.append({
                "metric": metric_name,
                "after_months": after_months,
                "n_projects": n_projects,
                "mean_before_12m_monthly_avg":
                    before_average.mean(),
                "median_before_12m_monthly_avg":
                    before_average.median(),
                "mean_after_monthly_avg":
                    after_average.mean(),
                "median_after_monthly_avg":
                    after_average.median(),
                "mean_difference":
                    difference.mean(),
                "median_difference":
                    difference.median(),
                "mean_log_change":
                    log_change.mean(),
                "median_log_change":
                    log_change.median(),
                "wilcoxon_statistic_two_sided":
                    two_stat,
                "wilcoxon_p_two_sided":
                    two_p,
                "wilcoxon_p_greater":
                    greater_p,
                "wilcoxon_p_less":
                    less_p,
                "paired_t_statistic":
                    t_result.statistic,
                "paired_t_p_value":
                    t_result.pvalue,
                "increased_count": increased,
                "decreased_count": decreased,
                "unchanged_count": unchanged,
                "increase_rate":
                    increased / n_projects,
                "decrease_rate":
                    decreased / n_projects,
                "unchanged_rate":
                    unchanged / n_projects,
            })

            for index in range(n_projects):
                project_rows.append({
                    "metric": metric_name,
                    "after_months": after_months,
                    "collective_id":
                        df_wide.iloc[index]["collective_id"],
                    "repo_name":
                        df_wide.iloc[index]["repo_name"],
                    "before_12m_total":
                        df_wide.iloc[index][
                            "before_12m_total"
                        ],
                    "before_12m_monthly_avg":
                        before_average.iloc[index],
                    "after_total":
                        after_total.iloc[index],
                    "after_monthly_avg":
                        after_average.iloc[index],
                    "difference":
                        difference.iloc[index],
                    "log_change":
                        log_change.iloc[index],
                })

    return (
        pd.DataFrame(test_rows),
        pd.DataFrame(project_rows),
    )