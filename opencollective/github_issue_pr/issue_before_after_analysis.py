import numpy as np
import pandas as pd


PROJECT_COL = "project_slug"
ANALYSIS_WINDOW_MONTHS = 12


def prepare_unambiguous_payee_matches(
    df_matched_logins: pd.DataFrame,
) -> pd.DataFrame:
    """
    1つのproject-payeeに対して、
    GitHub loginが一意に決まったケースだけを残す。

    分析単位:
        project_slug × to_account_slug × github_login
    """
    if df_matched_logins.empty:
        return pd.DataFrame()

    required_columns = {
        PROJECT_COL,
        "repo_name",
        "to_account_slug",
        "to_account_name",
        "github_login",
        "first_payment_at",
        "matched_login_count",
    }

    missing_columns = (
        required_columns
        - set(df_matched_logins.columns)
    )

    if missing_columns:
        raise ValueError(
            "df_matched_logins is missing columns: "
            f"{sorted(missing_columns)}"
        )

    columns_to_keep = [
        PROJECT_COL,
        "repo_name",
        "to_account_slug",
        "to_account_name",
        "github_login",
        "first_payment_at",
        "matched_as_opener",
        "matched_as_closer",
        "match_methods",
    ]

    # 存在する列だけ残す
    columns_to_keep = [
        column
        for column in columns_to_keep
        if column in df_matched_logins.columns
    ]

    df = (
        df_matched_logins.loc[
            df_matched_logins[
                "matched_login_count"
            ].eq(1),
            columns_to_keep,
        ]
        .drop_duplicates(
            subset=[
                PROJECT_COL,
                "to_account_slug",
                "github_login",
            ]
        )
        .copy()
    )

    df["first_payment_at"] = pd.to_datetime(
        df["first_payment_at"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    df["github_login"] = (
        df["github_login"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df["repo_name"] = (
        df["repo_name"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df = df[
        df["first_payment_at"].notna()
        & df["github_login"].ne("")
        & df["repo_name"].ne("")
    ].copy()

    return df.reset_index(drop=True)


def extract_issues_created_by_matched_payees(
    df_project_issues: pd.DataFrame,
    df_unambiguous_matches: pd.DataFrame,
) -> pd.DataFrame:
    """
    マッチングできた受取人本人が、
    同じプロジェクトで作成したIssueだけを抽出する。

    Issue作成者:
        opener_login
    """
    if (
        df_project_issues.empty
        or df_unambiguous_matches.empty
    ):
        return pd.DataFrame()

    required_issue_columns = {
        PROJECT_COL,
        "repo_name",
        "number",
        "created_at",
        "opener_login",
    }

    missing_columns = (
        required_issue_columns
        - set(df_project_issues.columns)
    )

    if missing_columns:
        raise ValueError(
            "df_project_issues is missing columns: "
            f"{sorted(missing_columns)}"
        )

    match_columns = [
        PROJECT_COL,
        "repo_name",
        "to_account_slug",
        "to_account_name",
        "github_login",
        "first_payment_at",
    ]

    df_matches = (
        df_unambiguous_matches[
            match_columns
        ]
        .drop_duplicates()
        .copy()
    )

    df_issues = df_project_issues.copy()

    df_issues["created_at"] = pd.to_datetime(
        df_issues["created_at"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    df_issues["opener_login"] = (
        df_issues["opener_login"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df_issues["repo_name"] = (
        df_issues["repo_name"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df_matched_issues = (
        df_issues
        .merge(
            df_matches,
            left_on=[
                PROJECT_COL,
                "repo_name",
                "opener_login",
            ],
            right_on=[
                PROJECT_COL,
                "repo_name",
                "github_login",
            ],
            how="inner",
        )
    )

    # 同じIssueが重複した場合に備える
    df_matched_issues = (
        df_matched_issues
        .drop_duplicates(
            subset=[
                PROJECT_COL,
                "repo_name",
                "to_account_slug",
                "github_login",
                "number",
            ]
        )
        .reset_index(drop=True)
    )

    return df_matched_issues


def classify_issue_period(
    df_matched_issues: pd.DataFrame,
    window_months: int = ANALYSIS_WINDOW_MONTHS,
) -> pd.DataFrame:
    """
    Issueを初回支払い前後の期間へ分類する。

    before:
        payment - N months <= created_at < payment

    after:
        payment <= created_at < payment + N months

    window外のIssueは除外する。
    """
    if df_matched_issues.empty:
        return pd.DataFrame()

    df = df_matched_issues.copy()

    df["before_start"] = (
        df["first_payment_at"]
        - pd.DateOffset(months=window_months)
    )

    df["after_end"] = (
        df["first_payment_at"]
        + pd.DateOffset(months=window_months)
    )

    before_mask = (
        df["created_at"].ge(
            df["before_start"]
        )
        & df["created_at"].lt(
            df["first_payment_at"]
        )
    )

    after_mask = (
        df["created_at"].ge(
            df["first_payment_at"]
        )
        & df["created_at"].lt(
            df["after_end"]
        )
    )

    df["period"] = np.select(
        [
            before_mask,
            after_mask,
        ],
        [
            "before",
            "after",
        ],
        default="outside",
    )

    df = df[
        df["period"].isin(
            ["before", "after"]
        )
    ].copy()

    df["window_months"] = window_months

    return df.reset_index(drop=True)


def build_issue_before_after_counts(
    df_unambiguous_matches: pd.DataFrame,
    df_period_issues: pd.DataFrame,
    window_months: int = ANALYSIS_WINDOW_MONTHS,
) -> pd.DataFrame:
    """
    project-payee単位で、
    支払い前後Nか月のIssue作成数を集計する。

    Issueが0件の人も残す。
    """
    pair_columns = [
        PROJECT_COL,
        "repo_name",
        "to_account_slug",
        "to_account_name",
        "github_login",
        "first_payment_at",
    ]

    df_pairs = (
        df_unambiguous_matches[
            pair_columns
        ]
        .drop_duplicates()
        .copy()
    )

    if df_period_issues.empty:
        df_pairs["before_issue_count"] = 0
        df_pairs["after_issue_count"] = 0
    else:
        df_counts_long = (
            df_period_issues
            .groupby(
                pair_columns
                + ["period"],
                dropna=False,
            )
            .agg(
                issue_count=(
                    "number",
                    "nunique",
                )
            )
            .reset_index()
        )

        df_counts_wide = (
            df_counts_long
            .pivot_table(
                index=pair_columns,
                columns="period",
                values="issue_count",
                fill_value=0,
                aggfunc="sum",
            )
            .reset_index()
        )

        df_counts_wide.columns.name = None

        rename_columns = {
            "before": "before_issue_count",
            "after": "after_issue_count",
        }

        df_counts_wide = (
            df_counts_wide.rename(
                columns=rename_columns
            )
        )

        for column in [
            "before_issue_count",
            "after_issue_count",
        ]:
            if column not in df_counts_wide.columns:
                df_counts_wide[column] = 0

        df_pairs = df_pairs.merge(
            df_counts_wide,
            on=pair_columns,
            how="left",
        )

        df_pairs[
            [
                "before_issue_count",
                "after_issue_count",
            ]
        ] = (
            df_pairs[
                [
                    "before_issue_count",
                    "after_issue_count",
                ]
            ]
            .fillna(0)
            .astype(int)
        )

    df_pairs["issue_count_difference"] = (
        df_pairs["after_issue_count"]
        - df_pairs["before_issue_count"]
    )

    df_pairs["issue_growth_rate_pct"] = np.where(
        df_pairs["before_issue_count"] > 0,
        (
            df_pairs["issue_count_difference"]
            / df_pairs["before_issue_count"]
            * 100
        ),
        np.nan,
    )

    df_pairs["activity_status"] = np.select(
        [
            (
                df_pairs["before_issue_count"] > 0
            )
            & (
                df_pairs["after_issue_count"]
                > df_pairs["before_issue_count"]
            ),
            (
                df_pairs["before_issue_count"] > 0
            )
            & (
                df_pairs["after_issue_count"]
                < df_pairs["before_issue_count"]
            ),
            (
                df_pairs["before_issue_count"] > 0
            )
            & (
                df_pairs["after_issue_count"]
                == df_pairs["before_issue_count"]
            ),
            (
                df_pairs["before_issue_count"] == 0
            )
            & (
                df_pairs["after_issue_count"] > 0
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

    df_pairs["window_months"] = window_months

    return (
        df_pairs
        .sort_values(
            [
                "after_issue_count",
                "before_issue_count",
            ],
            ascending=False,
        )
        .reset_index(drop=True)
    )


def summarize_issue_before_after_counts(
    df_counts: pd.DataFrame,
) -> pd.DataFrame:
    """
    全project-payeeについて記述統計を出す。
    """
    if df_counts.empty:
        return pd.DataFrame()

    before = df_counts[
        "before_issue_count"
    ]

    after = df_counts[
        "after_issue_count"
    ]

    difference = df_counts[
        "issue_count_difference"
    ]

    growth = df_counts[
        "issue_growth_rate_pct"
    ].dropna()

    status_counts = (
        df_counts["activity_status"]
        .value_counts()
    )

    n_pairs = len(df_counts)

    return pd.DataFrame(
        [
            {
                "window_months":
                    df_counts[
                        "window_months"
                    ].iloc[0],

                "n_project_payees":
                    n_pairs,

                "n_projects":
                    df_counts[
                        PROJECT_COL
                    ].nunique(),

                "n_payees":
                    df_counts[
                        "to_account_slug"
                    ].nunique(),

                "total_before_issues":
                    before.sum(),

                "total_after_issues":
                    after.sum(),

                "mean_before_issues":
                    before.mean(),

                "median_before_issues":
                    before.median(),

                "q1_before_issues":
                    before.quantile(0.25),

                "q3_before_issues":
                    before.quantile(0.75),

                "mean_after_issues":
                    after.mean(),

                "median_after_issues":
                    after.median(),

                "q1_after_issues":
                    after.quantile(0.25),

                "q3_after_issues":
                    after.quantile(0.75),

                "mean_difference":
                    difference.mean(),

                "median_difference":
                    difference.median(),

                "n_growth_rate_valid":
                    len(growth),

                "median_growth_rate_pct":
                    growth.median(),

                "q1_growth_rate_pct":
                    growth.quantile(0.25),

                "q3_growth_rate_pct":
                    growth.quantile(0.75),

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
            }
        ]
    )


def run_issue_before_after_analysis(
    df_project_issues: pd.DataFrame,
    df_matched_logins: pd.DataFrame,
    window_months: int = ANALYSIS_WINDOW_MONTHS,
):
    """
    前後Issue件数分析をまとめて実行する。
    """
    df_matches = (
        prepare_unambiguous_payee_matches(
            df_matched_logins
        )
    )

    df_matched_issues = (
        extract_issues_created_by_matched_payees(
            df_project_issues,
            df_matches,
        )
    )

    df_period_issues = (
        classify_issue_period(
            df_matched_issues,
            window_months=window_months,
        )
    )

    df_counts = (
        build_issue_before_after_counts(
            df_unambiguous_matches=
                df_matches,
            df_period_issues=
                df_period_issues,
            window_months=
                window_months,
        )
    )

    df_summary = (
        summarize_issue_before_after_counts(
            df_counts
        )
    )

    return {
        "matches": df_matches,
        "matched_issues": df_matched_issues,
        "period_issues": df_period_issues,
        "counts": df_counts,
        "summary": df_summary,
    }