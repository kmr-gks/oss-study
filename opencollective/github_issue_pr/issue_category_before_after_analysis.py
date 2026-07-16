import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from statsmodels.stats.multitest import multipletests


PROJECT_COL = "project_slug"


def build_category_before_after_counts(
    df_unambiguous_matches: pd.DataFrame,
    df_period_issues: pd.DataFrame,
    df_issue_categories: pd.DataFrame,
    window_months: int = 12,
) -> pd.DataFrame:
    """
    project-payee × category単位で、
    初回支払い前後のIssue数と構成比を計算する。

    Parameters
    ----------
    df_unambiguous_matches:
        一意にGitHub loginへマッチしたproject-payee。

    df_period_issues:
        支払い前後12か月に作成されたIssue明細。
        period列に before / after が入っている。

    df_issue_categories:
        1 Issue × 1 category の分類結果。

    Returns
    -------
    pd.DataFrame
        1行:
            project-payee × category
    """

    pair_columns = [
        PROJECT_COL,
        "repo_name",
        "to_account_slug",
        "to_account_name",
        "github_login",
        "first_payment_at",
    ]

    required_match_columns = set(pair_columns)

    missing_match_columns = (
        required_match_columns
        - set(df_unambiguous_matches.columns)
    )

    if missing_match_columns:
        raise ValueError(
            "df_unambiguous_matches is missing columns: "
            f"{sorted(missing_match_columns)}"
        )

    required_issue_columns = {
        PROJECT_COL,
        "repo_name",
        "github_login",
        "number",
        "period",
    }

    missing_issue_columns = (
        required_issue_columns
        - set(df_period_issues.columns)
    )

    if missing_issue_columns:
        raise ValueError(
            "df_period_issues is missing columns: "
            f"{sorted(missing_issue_columns)}"
        )

    required_category_columns = {
        PROJECT_COL,
        "repo_name",
        "github_login",
        "number",
        "category",
    }

    missing_category_columns = (
        required_category_columns
        - set(df_issue_categories.columns)
    )

    if missing_category_columns:
        raise ValueError(
            "df_issue_categories is missing columns: "
            f"{sorted(missing_category_columns)}"
        )

    df_pairs = (
        df_unambiguous_matches[
            pair_columns
        ]
        .drop_duplicates()
        .copy()
    )

    # 今回実際に存在する全カテゴリ
    categories = sorted(
        df_issue_categories["category"]
        .dropna()
        .unique()
        .tolist()
    )

    # 全project-payee × 全categoryの組合せを作る
    df_category_master = pd.DataFrame(
        {"category": categories}
    )

    df_pairs["_join_key"] = 1
    df_category_master["_join_key"] = 1

    df_pair_categories = (
        df_pairs
        .merge(
            df_category_master,
            on="_join_key",
            how="inner",
        )
        .drop(columns="_join_key")
    )

    # Issueのperiodをカテゴリ表へ付与
    issue_identity_columns = [
        PROJECT_COL,
        "repo_name",
        "to_account_slug",
        "github_login",
        "number",
    ]

    df_issue_period = (
        df_period_issues[
            issue_identity_columns
            + ["period"]
        ]
        .drop_duplicates()
    )

    if "period" in df_issue_categories.columns:
        # classify_issue_labels() の時点で
        # period列が引き継がれている場合
        df_categories_with_period = (
            df_issue_categories[
                issue_identity_columns
                + ["category", "period"]
            ]
            .drop_duplicates(
                subset=(
                    issue_identity_columns
                    + ["category", "period"]
                )
            )
            .copy()
        )
    else:
        # period列がカテゴリ表にない場合だけ結合する
        df_categories_with_period = (
            df_issue_categories
            .merge(
                df_issue_period,
                on=issue_identity_columns,
                how="inner",
            )
            .drop_duplicates(
                subset=(
                    issue_identity_columns
                    + ["category", "period"]
                )
            )
        )

    # カテゴリ別件数
    df_category_counts_long = (
        df_categories_with_period
        .groupby(
            [
                PROJECT_COL,
                "repo_name",
                "github_login",
                "category",
                "period",
            ],
            dropna=False,
        )
        .agg(
            category_issue_count=(
                "number",
                "nunique",
            )
        )
        .reset_index()
    )

    df_category_counts_wide = (
        df_category_counts_long
        .pivot_table(
            index=[
                PROJECT_COL,
                "repo_name",
                "github_login",
                "category",
            ],
            columns="period",
            values="category_issue_count",
            fill_value=0,
            aggfunc="sum",
        )
        .reset_index()
    )

    df_category_counts_wide.columns.name = None

    df_category_counts_wide = (
        df_category_counts_wide.rename(
            columns={
                "before": "before_category_count",
                "after": "after_category_count",
            }
        )
    )

    for column in [
        "before_category_count",
        "after_category_count",
    ]:
        if column not in df_category_counts_wide.columns:
            df_category_counts_wide[column] = 0

    # project-payeeごとの全Issue数
    df_total_counts_long = (
        df_period_issues
        .groupby(
            [
                PROJECT_COL,
                "repo_name",
                "github_login",
                "period",
            ],
            dropna=False,
        )
        .agg(
            total_issue_count=(
                "number",
                "nunique",
            )
        )
        .reset_index()
    )

    df_total_counts_wide = (
        df_total_counts_long
        .pivot_table(
            index=[
                PROJECT_COL,
                "repo_name",
                "github_login",
            ],
            columns="period",
            values="total_issue_count",
            fill_value=0,
            aggfunc="sum",
        )
        .reset_index()
    )

    df_total_counts_wide.columns.name = None

    df_total_counts_wide = (
        df_total_counts_wide.rename(
            columns={
                "before": "before_total_issue_count",
                "after": "after_total_issue_count",
            }
        )
    )

    for column in [
        "before_total_issue_count",
        "after_total_issue_count",
    ]:
        if column not in df_total_counts_wide.columns:
            df_total_counts_wide[column] = 0

    # 全project-payee × categoryへ件数を結合
    df_result = (
        df_pair_categories
        .merge(
            df_category_counts_wide,
            on=[
                PROJECT_COL,
                "repo_name",
                "github_login",
                "category",
            ],
            how="left",
        )
        .merge(
            df_total_counts_wide,
            on=[
                PROJECT_COL,
                "repo_name",
                "github_login",
            ],
            how="left",
        )
    )

    count_columns = [
        "before_category_count",
        "after_category_count",
        "before_total_issue_count",
        "after_total_issue_count",
    ]

    df_result[count_columns] = (
        df_result[count_columns]
        .fillna(0)
        .astype(int)
    )

    df_result["category_count_difference"] = (
        df_result["after_category_count"]
        - df_result["before_category_count"]
    )

    df_result["category_growth_rate_pct"] = np.where(
        df_result["before_category_count"] > 0,
        (
            df_result["category_count_difference"]
            / df_result["before_category_count"]
            * 100
        ),
        np.nan,
    )

    df_result["before_category_share"] = np.where(
        df_result["before_total_issue_count"] > 0,
        (
            df_result["before_category_count"]
            / df_result["before_total_issue_count"]
        ),
        np.nan,
    )

    df_result["after_category_share"] = np.where(
        df_result["after_total_issue_count"] > 0,
        (
            df_result["after_category_count"]
            / df_result["after_total_issue_count"]
        ),
        np.nan,
    )

    df_result["category_share_difference"] = (
        df_result["after_category_share"]
        - df_result["before_category_share"]
    )

    df_result["activity_status"] = np.select(
        [
            (
                df_result["before_category_count"] > 0
            )
            & (
                df_result["after_category_count"]
                > df_result["before_category_count"]
            ),
            (
                df_result["before_category_count"] > 0
            )
            & (
                df_result["after_category_count"]
                < df_result["before_category_count"]
            ),
            (
                df_result["before_category_count"] > 0
            )
            & (
                df_result["after_category_count"]
                == df_result["before_category_count"]
            ),
            (
                df_result["before_category_count"] == 0
            )
            & (
                df_result["after_category_count"] > 0
            ),
        ],
        [
            "increased",
            "decreased",
            "unchanged",
            "new_after",
        ],
        default="no_activity",
    )

    df_result["window_months"] = window_months

    return (
        df_result
        .sort_values(
            [
                "category",
                PROJECT_COL,
                "github_login",
            ]
        )
        .reset_index(drop=True)
    )


def summarize_category_before_after(
    df_category_counts: pd.DataFrame,
) -> pd.DataFrame:
    """
    カテゴリごとの前後集計。
    """
    rows = []

    for category, group in df_category_counts.groupby(
        "category",
        sort=True,
    ):
        before = group[
            "before_category_count"
        ]

        after = group[
            "after_category_count"
        ]

        difference = group[
            "category_count_difference"
        ]

        valid_growth = group[
            "category_growth_rate_pct"
        ].dropna()

        valid_before_share = group[
            "before_category_share"
        ].dropna()

        valid_after_share = group[
            "after_category_share"
        ].dropna()

        valid_share_difference = group[
            "category_share_difference"
        ].dropna()

        status_counts = (
            group["activity_status"]
            .value_counts()
        )

        n_pairs = len(group)

        rows.append({
            "category":
                category,

            "window_months":
                group["window_months"].iloc[0],

            "n_project_payees":
                n_pairs,

            "total_before_category_issues":
                before.sum(),

            "total_after_category_issues":
                after.sum(),

            "mean_before_category_count":
                before.mean(),

            "median_before_category_count":
                before.median(),

            "mean_after_category_count":
                after.mean(),

            "median_after_category_count":
                after.median(),

            "mean_category_difference":
                difference.mean(),

            "median_category_difference":
                difference.median(),

            "n_growth_rate_valid":
                len(valid_growth),

            "median_growth_rate_pct":
                valid_growth.median(),

            "q1_growth_rate_pct":
                valid_growth.quantile(0.25),

            "q3_growth_rate_pct":
                valid_growth.quantile(0.75),

            "median_before_category_share":
                valid_before_share.median(),

            "median_after_category_share":
                valid_after_share.median(),

            "median_category_share_difference":
                valid_share_difference.median(),

            "increased_count":
                status_counts.get(
                    "increased",
                    0,
                ),

            "decreased_count":
                status_counts.get(
                    "decreased",
                    0,
                ),

            "unchanged_count":
                status_counts.get(
                    "unchanged",
                    0,
                ),

            "new_after_count":
                status_counts.get(
                    "new_after",
                    0,
                ),

            "no_activity_count":
                status_counts.get(
                    "no_activity",
                    0,
                ),

            "increased_ratio":
                status_counts.get(
                    "increased",
                    0,
                ) / n_pairs,

            "decreased_ratio":
                status_counts.get(
                    "decreased",
                    0,
                ) / n_pairs,

            "new_after_ratio":
                status_counts.get(
                    "new_after",
                    0,
                ) / n_pairs,
        })

    return (
        pd.DataFrame(rows)
        .sort_values(
            "total_before_category_issues",
            ascending=False,
        )
        .reset_index(drop=True)
    )


def build_category_period_totals(
    df_period_issues: pd.DataFrame,
    df_issue_categories: pd.DataFrame,
) -> pd.DataFrame:
    """
    before / afterごとのカテゴリ総件数と割合。

    project-payee単位ではなく、
    対象Issue全体の内訳を見るための表。
    """
    issue_identity_columns = [
        PROJECT_COL,
        "repo_name",
        "to_account_slug",
        "github_login",
        "number",
    ]

    df_issue_period = (
        df_period_issues[
            issue_identity_columns
            + ["period"]
        ]
        .drop_duplicates()
    )

    if "period" in df_issue_categories.columns:
        df_categories_with_period = (
            df_issue_categories[
                issue_identity_columns
                + ["period", "category"]
            ]
            .drop_duplicates(
                subset=(
                    issue_identity_columns
                    + ["period", "category"]
                )
            )
            .copy()
        )
    else:
        df_categories_with_period = (
            df_issue_categories
            .merge(
                df_issue_period,
                on=issue_identity_columns,
                how="inner",
            )
            .drop_duplicates(
                subset=(
                    issue_identity_columns
                    + ["period", "category"]
                )
            )
        )

    df_category_totals = (
        df_categories_with_period
        .groupby(
            [
                "period",
                "category",
            ],
            as_index=False,
        )
        .agg(
            n_issues=(
                "number",
                "count",
            ),
            n_projects=(
                PROJECT_COL,
                "nunique",
            ),
            n_developers=(
                "github_login",
                "nunique",
            ),
        )
    )

    df_period_totals = (
        df_issue_period
        .groupby(
            "period",
            as_index=False,
        )
        .agg(
            total_unique_issues=(
                "number",
                "count",
            )
        )
    )

    df_result = (
        df_category_totals
        .merge(
            df_period_totals,
            on="period",
            how="left",
        )
    )

    df_result["issue_ratio"] = (
        df_result["n_issues"]
        / df_result["total_unique_issues"]
    )

    return (
        df_result
        .sort_values(
            [
                "period",
                "n_issues",
            ],
            ascending=[
                True,
                False,
            ],
        )
        .reset_index(drop=True)
    )


def build_category_period_comparison(
    df_category_period_totals: pd.DataFrame,
) -> pd.DataFrame:
    """
    beforeとafterの総件数・割合を横並びにする。
    """
    count_table = (
        df_category_period_totals
        .pivot_table(
            index="category",
            columns="period",
            values="n_issues",
            fill_value=0,
        )
        .reset_index()
    )

    count_table.columns.name = None

    count_table = count_table.rename(
        columns={
            "before": "before_n_issues",
            "after": "after_n_issues",
        }
    )

    ratio_table = (
        df_category_period_totals
        .pivot_table(
            index="category",
            columns="period",
            values="issue_ratio",
            fill_value=0,
        )
        .reset_index()
    )

    ratio_table.columns.name = None

    ratio_table = ratio_table.rename(
        columns={
            "before": "before_issue_ratio",
            "after": "after_issue_ratio",
        }
    )

    df_comparison = count_table.merge(
        ratio_table,
        on="category",
        how="outer",
    )

    for column in [
        "before_n_issues",
        "after_n_issues",
        "before_issue_ratio",
        "after_issue_ratio",
    ]:
        if column not in df_comparison.columns:
            df_comparison[column] = 0

    df_comparison["issue_count_difference"] = (
        df_comparison["after_n_issues"]
        - df_comparison["before_n_issues"]
    )

    df_comparison["issue_count_change_pct"] = np.where(
        df_comparison["before_n_issues"] > 0,
        (
            df_comparison["issue_count_difference"]
            / df_comparison["before_n_issues"]
            * 100
        ),
        np.nan,
    )

    df_comparison["issue_ratio_difference"] = (
        df_comparison["after_issue_ratio"]
        - df_comparison["before_issue_ratio"]
    )

    return (
        df_comparison
        .sort_values(
            "before_n_issues",
            ascending=False,
        )
        .reset_index(drop=True)
    )


MAIN_CATEGORIES = [
    "feature_development",
    "bug_fixing",
    "contributor_recruitment",
    "documentation",
    "maintenance",
    "issue_triage_closure",
]


def test_category_share_before_after(
    df_category_counts: pd.DataFrame,
    categories: list[str] = MAIN_CATEGORIES,
) -> pd.DataFrame:
    """
    project-payeeごとのカテゴリ構成比について、
    支払い前後をWilcoxon符号付順位検定で比較する。

    前後の全Issue数がともに1件以上ある対象だけを使用する。
    """
    rows = []

    for category in categories:
        group = df_category_counts[
            df_category_counts[
                "category"
            ].eq(category)
        ].copy()

        # 前後どちらにもIssue作成活動がある人に限定
        group = group[
            group["before_total_issue_count"].gt(0)
            & group["after_total_issue_count"].gt(0)
        ].copy()

        group = group[
            group["before_category_share"].notna()
            & group["after_category_share"].notna()
        ].copy()

        before = group[
            "before_category_share"
        ].astype(float)

        after = group[
            "after_category_share"
        ].astype(float)

        difference = after - before

        n_equal = int(
            difference.eq(0).sum()
        )
        n_increased = int(
            difference.gt(0).sum()
        )
        n_decreased = int(
            difference.lt(0).sum()
        )

        # 全員の差が0ならWilcoxonを実行できない
        if difference.ne(0).sum() == 0:
            statistic = 0.0
            p_value = 1.0
        else:
            result = wilcoxon(
                after,
                before,
                alternative="two-sided",
                zero_method="wilcox",
                method="auto",
            )

            statistic = float(
                result.statistic
            )
            p_value = float(
                result.pvalue
            )

        rows.append({
            "category": category,
            "n_project_payees": len(group),
            "n_increased_share": n_increased,
            "n_decreased_share": n_decreased,
            "n_unchanged_share": n_equal,
            "mean_before_share":
                before.mean(),
            "mean_after_share":
                after.mean(),
            "median_before_share":
                before.median(),
            "median_after_share":
                after.median(),
            "mean_share_difference":
                difference.mean(),
            "median_share_difference":
                difference.median(),
            "wilcoxon_statistic":
                statistic,
            "p_value":
                p_value,
        })

    df_result = pd.DataFrame(rows)

    # その分析条件内の6カテゴリでHolm補正
    reject, adjusted_p, _, _ = multipletests(
        df_result["p_value"],
        alpha=0.05,
        method="holm",
    )

    df_result[
        "holm_adjusted_p_value"
    ] = adjusted_p

    df_result[
        "significant_after_holm"
    ] = reject

    return (
        df_result
        .sort_values(
            "holm_adjusted_p_value"
        )
        .reset_index(drop=True)
    )
