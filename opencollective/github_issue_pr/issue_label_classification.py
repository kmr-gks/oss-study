import re
import unicodedata
import numpy as np
import pandas as pd


PROJECT_COL = "project_slug"


ISSUE_CATEGORY_KEYS = {
    "bug_fixing": {
        "bug",
        "typebug",
        "0kindbug",
        "kindbug",
        "issuebug",
        "abug",
        "cbug",
        "tbug",
        "idefect",
        "p3minorbug",
        "bugbug",
    },

    "feature_development": {
        "enhancement",
        "feature",
        "featurerequest",
        "typeenhancement",
        "typefeature",
        "tenhancement",
        "cfeature",
        "improvement",
        "abilities",
        "visuals",
        "ui",
        "performance",
        "newfeaturerequest",
        "featuregui",
        "unicornfeaturerequest",
        "featuremultiworld",
        "awish",
        "rssenhancement",
        "enhancementfeature",
    },

    "contributor_recruitment": {
        "helpwanted",
        "goodfirstissue",
        "acceptingprs",
        "statusacceptingprs",
        "hacktoberfest",
    },

"documentation": {
    "documentation",
    "areadocumentation",
    "cdocs",
    "doc",
},

    "question_support": {
        "question",
        "discussion",
        "brainstorm",
    },

    "maintenance": {
        "repomaintenance",
        "arearepositorytooling",
        "typechore",
        "pipeline",
        "breakingchange",
        "refactoring",
        "crefactor",
        "ci",
        "cinfra",
        "portability",
    },

    "issue_triage_closure": {
        "stale",
        "2statusstale",
        "outdated",
        "invalid",
        "duplicate",
        "wontfix",
        "lockedduetoage",
        "triage",
    },
}


def normalize_label(value) -> str:
    """
    Issueラベルを分類用のキーへ正規化する。

    例:
        "Type: Bug"       -> "typebug"
        "help wanted"     -> "helpwanted"
        "good-first-issue" -> "goodfirstissue"
    """
    if pd.isna(value):
        return ""

    value = unicodedata.normalize(
        "NFKC",
        str(value),
    )

    value = value.lower().strip()

    return re.sub(
        r"[^a-z0-9]+",
        "",
        value,
    )


def explode_issue_labels(
    df_issues: pd.DataFrame,
) -> pd.DataFrame:
    """
    セミコロン区切りのlabels列を展開する。

    出力:
        1 Issue × 1 raw label
    """
    required_columns = {
        PROJECT_COL,
        "repo_name",
        "github_login",
        "number",
        "created_at",
        "labels",
    }

    missing_columns = (
        required_columns
        - set(df_issues.columns)
    )

    if missing_columns:
        raise ValueError(
            "df_issues is missing columns: "
            f"{sorted(missing_columns)}"
        )

    df = df_issues.copy()

    df["labels"] = (
        df["labels"]
        .fillna("")
        .astype(str)
    )

    df_labels = (
        df.assign(
            raw_label=df["labels"].str.split(";")
        )
        .explode("raw_label")
    )

    df_labels["raw_label"] = (
        df_labels["raw_label"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df_labels["normalized_label"] = (
        df_labels["raw_label"]
        .map(normalize_label)
    )

    return df_labels.reset_index(drop=True)


def classify_issue_labels(
    df_issues: pd.DataFrame,
) -> pd.DataFrame:
    """
    Issueをカテゴリ分類する。

    1つのIssueが複数カテゴリに属することを許す。

    例:
        bug;help wanted

    は、
        bug_fixing
        contributor_recruitment

    の両方に分類される。
    """
    issue_id_columns = [
        PROJECT_COL,
        "repo_name",
        "github_login",
        "number",
        "created_at",
    ]

    optional_columns = [
        "to_account_slug",
        "to_account_name",
        "first_payment_at",
        "period",
        "window_months",
        "title",
        "url",
    ]

    issue_columns = (
        issue_id_columns
        + [
            column
            for column in optional_columns
            if column in df_issues.columns
        ]
    )

    df_labels = explode_issue_labels(
        df_issues
    )

    category_rows = []

    for category, label_keys in (
        ISSUE_CATEGORY_KEYS.items()
    ):
        df_category = df_labels[
            df_labels[
                "normalized_label"
            ].isin(label_keys)
        ][issue_columns].drop_duplicates()

        if df_category.empty:
            continue

        df_category = df_category.copy()
        df_category["category"] = category

        category_rows.append(
            df_category
        )

    if category_rows:
        df_classified = pd.concat(
            category_rows,
            ignore_index=True,
        )
    else:
        df_classified = pd.DataFrame(
            columns=issue_columns + ["category"]
        )

    df_classified = (
        df_classified
        .drop_duplicates(
            subset=(
                issue_id_columns
                + ["category"]
            )
        )
        .reset_index(drop=True)
    )

    # -------------------------
    # ラベルなし
    # -------------------------

    label_presence = (
        df_labels.groupby(
            issue_id_columns,
            dropna=False,
        )
        .agg(
            has_label=(
                "normalized_label",
                lambda values: (
                    values.ne("")
                ).any(),
            )
        )
        .reset_index()
    )

    df_issue_base = (
        df_issues[
            issue_columns
        ]
        .drop_duplicates(
            subset=issue_id_columns
        )
        .merge(
            label_presence,
            on=issue_id_columns,
            how="left",
        )
    )

    df_unlabeled = df_issue_base[
        ~df_issue_base[
            "has_label"
        ].fillna(False)
    ][issue_columns].copy()

    df_unlabeled["category"] = "unlabeled"

    # -------------------------
    # ラベル付きだが未分類
    # -------------------------

    classified_ids = (
        df_classified[
            issue_id_columns
        ]
        .drop_duplicates()
        .assign(is_classified=True)
    )

    df_other = (
        df_issue_base[
            df_issue_base[
                "has_label"
            ].fillna(False)
        ]
        .merge(
            classified_ids,
            on=issue_id_columns,
            how="left",
        )
    )

    df_other = df_other[
        df_other[
            "is_classified"
        ].isna()
    ][issue_columns].copy()

    df_other["category"] = "other_labeled"

    df_result = pd.concat(
        [
            df_classified,
            df_unlabeled,
            df_other,
        ],
        ignore_index=True,
    )

    return (
        df_result
        .drop_duplicates(
            subset=(
                issue_id_columns
                + ["category"]
            )
        )
        .reset_index(drop=True)
    )


def summarize_issue_categories(
    df_issues: pd.DataFrame,
    df_categories: pd.DataFrame,
) -> pd.DataFrame:
    """
    カテゴリごとのIssue数と割合を集計する。

    複数カテゴリ所属を許すため、
    category_ratioの合計は100%を超える場合がある。
    """
    issue_id_columns = [
        PROJECT_COL,
        "repo_name",
        "github_login",
        "number",
    ]

    total_issue_count = (
        df_issues[
            issue_id_columns
        ]
        .drop_duplicates()
        .shape[0]
    )

    df_summary = (
        df_categories
        .groupby(
            "category",
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

    df_summary["issue_ratio"] = (
        df_summary["n_issues"]
        / total_issue_count
        if total_issue_count > 0
        else 0
    )

    return (
        df_summary
        .sort_values(
            "n_issues",
            ascending=False,
        )
        .reset_index(drop=True)
    )


def summarize_issue_category_overlap(
    df_categories: pd.DataFrame,
) -> pd.DataFrame:
    """
    1つのIssueがいくつのカテゴリへ分類されたかを確認する。
    """
    issue_id_columns = [
        PROJECT_COL,
        "repo_name",
        "github_login",
        "number",
    ]

    df_overlap = (
        df_categories
        .groupby(
            issue_id_columns,
            as_index=False,
        )
        .agg(
            n_categories=(
                "category",
                "nunique",
            ),
            categories=(
                "category",
                lambda values: ";".join(
                    sorted(
                        set(values)
                    )
                ),
            ),
        )
    )

    df_summary = (
        df_overlap
        .groupby(
            "n_categories",
            as_index=False,
        )
        .agg(
            n_issues=(
                "number",
                "count",
            )
        )
    )

    total = df_summary[
        "n_issues"
    ].sum()

    df_summary["ratio"] = (
        df_summary["n_issues"] / total
        if total > 0
        else 0
    )

    return df_summary

def summarize_other_labeled_keys(
    df_issues: pd.DataFrame,
    df_categories: pd.DataFrame,
) -> pd.DataFrame:
    """
    other_labeledに分類されたIssueに付いている
    正規化ラベルの頻度を集計する。
    """
    issue_id_columns = [
        PROJECT_COL,
        "repo_name",
        "github_login",
        "number",
    ]

    other_issue_ids = (
        df_categories.loc[
            df_categories["category"].eq(
                "other_labeled"
            ),
            issue_id_columns,
        ]
        .drop_duplicates()
    )

    df_labels = explode_issue_labels(
        df_issues
    )

    df_other_labels = df_labels.merge(
        other_issue_ids,
        on=issue_id_columns,
        how="inner",
    )

    df_other_labels = df_other_labels[
        df_other_labels[
            "normalized_label"
        ].ne("")
    ].copy()

    return (
        df_other_labels
        .groupby(
            "normalized_label",
            as_index=False,
        )
        .agg(
            n_issues=(
                "number",
                "nunique",
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
        .sort_values(
            "n_issues",
            ascending=False,
        )
        .reset_index(drop=True)
    )

def classify_project_issue_labels(
    df_issues: pd.DataFrame,
    group_columns=None,
) -> pd.DataFrame:
    """
    プロジェクト単位のIssueをカテゴリ分類する。

    既存のclassify_issue_labels()はgithub_loginを必須とするため、
    github_loginが存在しない場合は内部的に固定値を追加して利用する。

    Parameters
    ----------
    df_issues:
        最低限、以下の列を持つDataFrame。

        project_slug
        repo_name
        number
        created_at
        labels

    group_columns:
        分類結果に残したい追加列。

        例:
            [
                "development_spend_amount_tertile",
                "development_expense_amount_usd",
            ]

    Returns
    -------
    pd.DataFrame
        1 Issue × 1 categoryのDataFrame。
        1つのIssueが複数カテゴリに属することを許す。
    """
    required_columns = {
        PROJECT_COL,
        "repo_name",
        "number",
        "created_at",
        "labels",
    }

    missing_columns = (
        required_columns
        - set(df_issues.columns)
    )

    if missing_columns:
        raise ValueError(
            "df_issues is missing columns: "
            f"{sorted(missing_columns)}"
        )

    if group_columns is None:
        group_columns = []

    missing_group_columns = (
        set(group_columns)
        - set(df_issues.columns)
    )

    if missing_group_columns:
        raise ValueError(
            "df_issues is missing group columns: "
            f"{sorted(missing_group_columns)}"
        )

    df = df_issues.copy()

    added_dummy_login = False

    if "github_login" not in df.columns:
        df["github_login"] = (
            "__project_level_issue__"
        )
        added_dummy_login = True

    df_categories = classify_issue_labels(
        df
    )

    issue_id_columns = [
        PROJECT_COL,
        "repo_name",
        "github_login",
        "number",
    ]

    if group_columns:
        df_group_values = (
            df[
                issue_id_columns
                + group_columns
            ]
            .drop_duplicates(
                subset=issue_id_columns
            )
        )

        df_categories = (
            df_categories.merge(
                df_group_values,
                on=issue_id_columns,
                how="left",
                validate="many_to_one",
            )
        )

    if added_dummy_login:
        df_categories = (
            df_categories.drop(
                columns="github_login"
            )
        )

    result_id_columns = [
        PROJECT_COL,
        "repo_name",
        "number",
        "category",
    ]

    return (
        df_categories
        .drop_duplicates(
            subset=result_id_columns
        )
        .reset_index(drop=True)
    )


def summarize_project_issue_categories(
    df_issues: pd.DataFrame,
    df_categories: pd.DataFrame,
    group_column: str,
    group_order=None,
) -> pd.DataFrame:
    """
    プロジェクト単位のIssueカテゴリをグループ別に集計する。

    例:
        group_column =
            "development_spend_amount_tertile"

    出力する割合:
        issue_category_ratio:
            グループ内のユニークIssue数に対する割合。
            複数カテゴリ所属があるため、
            カテゴリ合計は100%を超える場合がある。

        category_assignment_share:
            全カテゴリ割当数に対する割合。
            帯グラフではこちらを使用し、
            各グループ内で合計100%になる。
    """
    required_issue_columns = {
        PROJECT_COL,
        "repo_name",
        "number",
        group_column,
    }

    missing_issue_columns = (
        required_issue_columns
        - set(df_issues.columns)
    )

    if missing_issue_columns:
        raise ValueError(
            "df_issues is missing columns: "
            f"{sorted(missing_issue_columns)}"
        )

    required_category_columns = {
        PROJECT_COL,
        "repo_name",
        "number",
        "category",
        group_column,
    }

    missing_category_columns = (
        required_category_columns
        - set(df_categories.columns)
    )

    if missing_category_columns:
        raise ValueError(
            "df_categories is missing columns: "
            f"{sorted(missing_category_columns)}"
        )

    issue_id_columns = [
        PROJECT_COL,
        "repo_name",
        "number",
    ]

    df_unique_issues = (
        df_issues[
            issue_id_columns
            + [group_column]
        ]
        .drop_duplicates(
            subset=issue_id_columns
        )
    )

    df_unique_categories = (
        df_categories[
            issue_id_columns
            + [
                group_column,
                "category",
            ]
        ]
        .drop_duplicates(
            subset=(
                issue_id_columns
                + ["category"]
            )
        )
    )

    df_category_counts = (
        df_unique_categories
        .groupby(
            [
                group_column,
                "category",
            ],
            observed=False,
            as_index=False,
        )
        .agg(
            n_category_assignments=(
                "number",
                "count",
            ),
            n_projects=(
                PROJECT_COL,
                "nunique",
            ),
        )
    )

    df_issue_totals = (
        df_unique_issues
        .groupby(
            group_column,
            observed=False,
            as_index=False,
        )
        .agg(
            total_unique_issues=(
                "number",
                "count",
            ),
            n_projects_with_issues=(
                PROJECT_COL,
                "nunique",
            ),
        )
    )

    df_assignment_totals = (
        df_category_counts
        .groupby(
            group_column,
            observed=False,
            as_index=False,
        )
        .agg(
            total_category_assignments=(
                "n_category_assignments",
                "sum",
            )
        )
    )

    df_summary = (
        df_category_counts
        .merge(
            df_issue_totals,
            on=group_column,
            how="left",
            validate="many_to_one",
        )
        .merge(
            df_assignment_totals,
            on=group_column,
            how="left",
            validate="many_to_one",
        )
    )

    df_summary[
        "issue_category_ratio"
    ] = np.where(
        df_summary[
            "total_unique_issues"
        ].gt(0),
        (
            df_summary[
                "n_category_assignments"
            ]
            / df_summary[
                "total_unique_issues"
            ]
        ),
        0.0,
    )

    df_summary[
        "category_assignment_share"
    ] = np.where(
        df_summary[
            "total_category_assignments"
        ].gt(0),
        (
            df_summary[
                "n_category_assignments"
            ]
            / df_summary[
                "total_category_assignments"
            ]
        ),
        0.0,
    )

    if group_order is not None:
        df_summary[group_column] = (
            pd.Categorical(
                df_summary[group_column],
                categories=group_order,
                ordered=True,
            )
        )

        df_summary = (
            df_summary.sort_values(
                [
                    group_column,
                    "n_category_assignments",
                ],
                ascending=[
                    True,
                    False,
                ],
            )
        )
    else:
        df_summary = (
            df_summary.sort_values(
                [
                    group_column,
                    "n_category_assignments",
                ],
                ascending=[
                    True,
                    False,
                ],
            )
        )

    return df_summary.reset_index(
        drop=True
    )

def summarize_project_issue_category_overlap(
    df_categories: pd.DataFrame,
    group_column: str,
) -> pd.DataFrame:
    """
    各グループについて、1つのIssueが
    いくつのカテゴリに分類されたかを集計する。
    """
    required_columns = {
        PROJECT_COL,
        "repo_name",
        "number",
        "category",
        group_column,
    }

    missing_columns = (
        required_columns
        - set(df_categories.columns)
    )

    if missing_columns:
        raise ValueError(
            "df_categories is missing columns: "
            f"{sorted(missing_columns)}"
        )

    issue_id_columns = [
        PROJECT_COL,
        "repo_name",
        "number",
    ]

    df_unique = (
        df_categories[
            issue_id_columns
            + [
                group_column,
                "category",
            ]
        ]
        .drop_duplicates(
            subset=(
                issue_id_columns
                + ["category"]
            )
        )
    )

    # observed=Trueが重要
    df_overlap = (
        df_unique
        .groupby(
            issue_id_columns
            + [group_column],
            observed=True,
            as_index=False,
        )
        .agg(
            n_categories=(
                "category",
                "nunique",
            ),
            categories=(
                "category",
                lambda values: ";".join(
                    sorted(set(values))
                ),
            ),
        )
    )

    df_summary = (
        df_overlap
        .groupby(
            [
                group_column,
                "n_categories",
            ],
            observed=True,
            as_index=False,
        )
        .agg(
            n_issues=(
                "number",
                "count",
            )
        )
    )

    df_summary["total_issues"] = (
        df_summary
        .groupby(
            group_column,
            observed=True,
        )["n_issues"]
        .transform("sum")
    )

    df_summary["ratio"] = (
        df_summary["n_issues"]
        / df_summary["total_issues"]
    )

    return (
        df_summary
        .sort_values(
            [
                group_column,
                "n_categories",
            ]
        )
        .reset_index(drop=True)
    )
