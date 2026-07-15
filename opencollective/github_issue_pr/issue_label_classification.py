import re
import unicodedata

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
