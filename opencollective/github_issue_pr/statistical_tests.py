import numpy as np
import pandas as pd
from scipy.stats import wilcoxon, ttest_rel
from statsmodels.stats.multitest import multipletests

from config import (
    AFTER_WINDOWS,
    ANALYSIS_WINDOWS,
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


def run_issue_pr_growth_tests(
    df_growth: pd.DataFrame,
    include_zero_before: bool = True,
) -> pd.DataFrame:
    """
    各指標・各期間について、プロジェクト単位の活動件数を
    Open Collective参加前後で比較する。

    検定:
        片側Wilcoxon符号付順位検定

    帰無仮説:
        参加後の活動件数は参加前より多くない。

    対立仮説:
        参加後の活動件数が参加前より多い。

    Parameters
    ----------
    df_growth:
        calculate_growth_rates() が返すプロジェクト単位データ。

        必須列:
            collective_id
            repo_name
            metric
            window_months
            before_count
            after_count
            difference
            growth_rate_pct
            activity_status

    include_zero_before:
        True:
            before_count == 0 のプロジェクトも検定に含める。
            登録後に初めて活動したプロジェクトも検定対象になる。

        False:
            before_count > 0 のプロジェクトだけを検定する。
            増加率中央値と検定対象を揃えたい場合に使用する。

    Returns
    -------
    pd.DataFrame
        20検定の結果。
        Holm補正およびBonferroni補正済みp値を含む。
    """
    result_rows = []

    metric_names = list(METRICS.keys())

    for metric_name in metric_names:
        for window in ANALYSIS_WINDOWS:
            group = df_growth[
                df_growth["metric"].eq(metric_name)
                & df_growth["window_months"].eq(window)
            ].copy()

            group = group[
                group["before_count"].notna()
                & group["after_count"].notna()
            ].copy()

            if not include_zero_before:
                group = group[
                    group["before_count"] > 0
                ].copy()

            before = group["before_count"].astype(float)
            after = group["after_count"].astype(float)
            difference = after - before

            # 増加率はbefore_count > 0の場合のみ定義される
            valid_growth_rates = group.loc[
                group["before_count"] > 0,
                "growth_rate_pct",
            ].dropna()

            n_projects = len(group)
            n_nonzero_differences = int(
                difference.ne(0).sum()
            )

            if n_projects == 0:
                wilcoxon_statistic = np.nan
                p_value_raw = np.nan

            elif n_nonzero_differences == 0:
                # 全プロジェクトで前後差が0の場合
                wilcoxon_statistic = 0.0
                p_value_raw = 1.0

            else:
                test_result = wilcoxon(
                    after,
                    before,
                    alternative="greater",
                    zero_method="wilcox",
                    method="auto",
                )

                wilcoxon_statistic = test_result.statistic
                p_value_raw = test_result.pvalue

            increased_count = int((difference > 0).sum())
            decreased_count = int((difference < 0).sum())
            unchanged_count = int((difference == 0).sum())

            result_rows.append({
                "metric": metric_name,
                "window_months": window,

                "n_projects_tested": n_projects,
                "n_nonzero_differences":
                    n_nonzero_differences,
                "n_growth_rate_valid":
                    len(valid_growth_rates),

                "mean_before_count": before.mean(),
                "median_before_count": before.median(),
                "mean_after_count": after.mean(),
                "median_after_count": after.median(),

                "mean_difference": difference.mean(),
                "median_difference": difference.median(),

                "median_growth_rate_pct":
                    valid_growth_rates.median(),
                "q1_growth_rate_pct":
                    valid_growth_rates.quantile(0.25),
                "q3_growth_rate_pct":
                    valid_growth_rates.quantile(0.75),

                "increased_count": increased_count,
                "decreased_count": decreased_count,
                "unchanged_count": unchanged_count,

                "increased_rate":
                    increased_count / n_projects
                    if n_projects > 0 else np.nan,
                "decreased_rate":
                    decreased_count / n_projects
                    if n_projects > 0 else np.nan,
                "unchanged_rate":
                    unchanged_count / n_projects
                    if n_projects > 0 else np.nan,

                "wilcoxon_statistic":
                    wilcoxon_statistic,
                "p_value_raw":
                    p_value_raw,
            })

    df_results = pd.DataFrame(result_rows)

    # NaNを除いたp値だけ多重比較補正する
    valid_p_mask = df_results["p_value_raw"].notna()

    df_results["p_value_holm"] = np.nan
    df_results["significant_holm"] = False

    df_results["p_value_bonferroni"] = np.nan
    df_results["significant_bonferroni"] = False

    if valid_p_mask.any():
        raw_p_values = df_results.loc[
            valid_p_mask,
            "p_value_raw",
        ]

        reject_holm, p_holm, _, _ = multipletests(
            raw_p_values,
            alpha=0.05,
            method="holm",
        )

        reject_bonferroni, p_bonferroni, _, _ = (
            multipletests(
                raw_p_values,
                alpha=0.05,
                method="bonferroni",
            )
        )

        df_results.loc[
            valid_p_mask,
            "p_value_holm",
        ] = p_holm

        df_results.loc[
            valid_p_mask,
            "significant_holm",
        ] = reject_holm

        df_results.loc[
            valid_p_mask,
            "p_value_bonferroni",
        ] = p_bonferroni

        df_results.loc[
            valid_p_mask,
            "significant_bonferroni",
        ] = reject_bonferroni

    df_results["test_alternative"] = (
        "after_count > before_count"
    )

    df_results["include_zero_before"] = (
        include_zero_before
    )

    return (
        df_results
        .sort_values(
            ["metric", "window_months"]
        )
        .reset_index(drop=True)
    )


def print_test_summary(
    df_tests,
) -> None:
    display_columns = [
        "metric",
        "window_months",
        "n_projects_tested",
        "median_before_count",
        "median_after_count",
        "median_difference",
        "median_growth_rate_pct",
        "increased_rate",
        "decreased_rate",
        "p_value_raw",
        "p_value_holm",
        "significant_holm",
    ]

    print("\n===== Statistical test results =====")

    print(
        df_tests[display_columns]
        .to_string(index=False)
    )

    print("\n===== Holm significance summary =====")

    significance_summary = (
        df_tests
        .groupby("metric", as_index=False)
        .agg(
            n_tests=(
                "significant_holm",
                "size",
            ),
            n_significant_holm=(
                "significant_holm",
                "sum",
            ),
        )
    )

    print(
        significance_summary.to_string(
            index=False
        )
    )
