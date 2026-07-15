from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
import api

import re
import unicodedata
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from sqlalchemy import create_engine
from statsmodels.stats.multitest import multipletests


# ============================================================
# 設定
# ============================================================

DB_NAME = "opencollective"

PROJECT_COL = "project_slug"

ANALYSIS_WINDOWS = [3, 6, 12]

OUTPUT_DIR = Path("paid_developer_issue_category_analysis")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


ANALYSIS_CONFIGS = [
    {
        "analysis_label": "individual_development_payment",
        "description": (
            "When an individual receives money "
            "for development purposes"
        ),
        "where_extra": "AND is_development = true",
    },
    {
        "analysis_label": "individual_any_payment",
        "description": (
            "When an individual receives any payment"
        ),
        "where_extra": "",
    },
]


# ============================================================
# Issueカテゴリ
# ============================================================
#
# normalized_key:
#   小文字化し、英数字以外をすべて除去した値
#
# 1つのIssueが複数カテゴリに所属することを許す。
# 例:
#   bug;help wanted
# は bug と contributor_recruitment の両方に数えられる。
#

ISSUE_CATEGORY_KEYS = {
    "bug_fixing": {
        "bug",
        "typebug",
        "0kindbug",
        "kindbug",
        "issuebug",
        "tbug",
        "defect",
        "regression",
        "crash",
    },

    "feature_development": {
        "enhancement",
        "typeenhancement",
        "feature",
        "featurerequest",
        "typefeature",
    },

    "contributor_recruitment": {
        "helpwanted",
        "goodfirstissue",
    },

    "documentation": {
        "documentation",
        "docs",
        "typedocumentation",
        "documentationneeded",
    },

    "question_support": {
        "question",
        "typequestion",
        "support",
        "needsinfo",
        "moreinformationneeded",
    },

    "dependency_maintenance": {
        "dependencies",
        "dependency",
        "areadependencies",
        "maintenance",
        "typemaintenance",
        "refactor",
        "typerefactor",
    },

    "security": {
        "security",
        "typsecurity",
        "severitysecurity",
        "1severitysecurity",
        "vulnerability",
    },
}


# ============================================================
# SQL
# ============================================================

COLLECTIVES_SQL = """
SELECT
    id,
    slug,
    name,
    type,
    created_at,
    github_account
FROM public.collectives
WHERE github_account IS NOT NULL
  AND github_account <> ''
"""


ISSUES_SQL = """
SELECT
    collective_id,
    project_slug,
    project_name,
    repo_name,
    number,
    created_at,
    author_login,
    labels
FROM public.github_issue_pr_items
WHERE item_type = 'issue'
  AND repo_name IS NOT NULL
  AND number IS NOT NULL
  AND created_at IS NOT NULL
  AND author_login IS NOT NULL
  AND author_login <> ''
"""


def make_payments_sql(where_extra: str) -> str:
    return f"""
SELECT
    id AS transaction_id,
    project_slug,
    project_name,
    created_at AS payment_created_at,
    amount_value,
    amount_currency,
    from_account_slug,
    from_account_name,
    from_account_type,
    to_account_slug,
    to_account_name,
    to_account_type,
    expense_type,
    expense_description,
    description,
    is_development
FROM public.collective_transactions
WHERE kind = 'EXPENSE'
  AND to_account_type = 'INDIVIDUAL'
  AND to_account_slug IS NOT NULL
  AND to_account_name IS NOT NULL
  AND created_at IS NOT NULL
  {where_extra}
"""


# ============================================================
# 共通関数
# ============================================================

def database_engine():
    password = api.load_sql_password_from_credentials()

    return create_engine(
        "postgresql+psycopg2://"
        f"postgres:{password}"
        f"@localhost:5432/{DB_NAME}"
    )


def normalize_identifier(value) -> str:
    """
    名前・slug・GitHub loginの照合用。

    - Unicode正規化
    - 小文字化
    - ASCII英数字以外をすべて除去

    例:
        Foo-Bar      -> foobar
        foo_bar      -> foobar
        Foo (Bar)    -> foobar
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


def normalize_label_key(value) -> str:
    """
    Issueラベルのカテゴリ照合用。
    """
    return normalize_identifier(value)


def unique_join(series: pd.Series) -> str:
    values = (
        series
        .dropna()
        .astype(str)
        .sort_values()
        .unique()
        .tolist()
    )

    return "; ".join(values)


def save_dataframe(
    df: pd.DataFrame,
    analysis_label: str,
    suffix: str,
) -> None:
    output_path = (
        OUTPUT_DIR
        / f"{analysis_label}_{suffix}.csv"
    )

    df.to_csv(
        output_path,
        index=False,
    )

    print("Saved:", output_path)


# ============================================================
# データ読み込み
# ============================================================

def load_common_data(engine):
    df_collectives = pd.read_sql(
        COLLECTIVES_SQL,
        engine,
    )

    df_issues = pd.read_sql(
        ISSUES_SQL,
        engine,
    )

    df_collectives["created_at"] = pd.to_datetime(
        df_collectives["created_at"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    df_issues["created_at"] = pd.to_datetime(
        df_issues["created_at"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    df_collectives = df_collectives[
        df_collectives["github_account"].notna()
        & df_collectives[
            "github_account"
        ].str.contains("/", na=False)
    ].copy()

    df_collectives["repo_name"] = (
        df_collectives["github_account"]
        .astype(str)
        .str.strip()
        .str.replace("/", "-", regex=False)
        .str.lower()
    )

    df_issues["repo_name"] = (
        df_issues["repo_name"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df_issues["author_login"] = (
        df_issues["author_login"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df_issues["author_login_norm"] = (
        df_issues["author_login"]
        .map(normalize_identifier)
    )

    df_issues["labels"] = (
        df_issues["labels"]
        .fillna("")
        .astype(str)
    )

    print("\n===== Loaded common data =====")
    print("Collectives:", len(df_collectives))
    print("Issue rows:", len(df_issues))
    print(
        "Issue repositories:",
        df_issues["repo_name"].nunique(),
    )
    print(
        "Issue authors:",
        df_issues["author_login"].nunique(),
    )

    return df_collectives, df_issues


def load_payments(
    engine,
    where_extra: str,
) -> pd.DataFrame:
    df_payments = pd.read_sql(
        make_payments_sql(where_extra),
        engine,
    )

    df_payments["payment_created_at"] = (
        pd.to_datetime(
            df_payments["payment_created_at"],
            utc=True,
            errors="coerce",
        ).dt.tz_convert(None)
    )

    df_payments["amount_abs"] = pd.to_numeric(
        df_payments["amount_value"],
        errors="coerce",
    ).abs()

    df_payments["to_account_name_norm"] = (
        df_payments["to_account_name"]
        .map(normalize_identifier)
    )

    df_payments["to_account_slug_norm"] = (
        df_payments["to_account_slug"]
        .map(normalize_identifier)
    )

    return df_payments


# ============================================================
# Issueとプロジェクトの対応
# ============================================================

def build_project_issue_base(
    df_collectives: pd.DataFrame,
    df_issues: pd.DataFrame,
) -> pd.DataFrame:
    """
    collectives.slugを正式なproject_slugとして使用する。

    github_issue_pr_itemsに既にproject_slugがあるが、
    collectivesとの対応を明示的に確認する。
    """
    collective_columns = (
        df_collectives[
            [
                "id",
                "slug",
                "name",
                "github_account",
                "repo_name",
            ]
        ]
        .rename(
            columns={
                "id": "collective_id_from_collectives",
                "slug": PROJECT_COL,
                "name": "collective_name",
            }
        )
    )

    issue_columns_to_drop = [
        column
        for column in [
            "collective_id",
            "project_slug",
            "project_name",
        ]
        if column in df_issues.columns
    ]

    df_issue_base = (
        df_issues
        .drop(columns=issue_columns_to_drop)
        .merge(
            collective_columns,
            on="repo_name",
            how="inner",
            validate="many_to_many",
        )
    )

    print("\n===== Project issue base =====")
    print("Original issue rows:", len(df_issues))
    print(
        "Project-linked issue rows:",
        len(df_issue_base),
    )
    print(
        "Matched projects:",
        df_issue_base[PROJECT_COL].nunique(),
    )
    print(
        "Matched repositories:",
        df_issue_base["repo_name"].nunique(),
    )

    return df_issue_base


# ============================================================
# 最初の支払い
# ============================================================

def build_first_payments(
    df_payments: pd.DataFrame,
) -> pd.DataFrame:
    group_columns = [
        PROJECT_COL,
        "project_name",
        "to_account_slug",
        "to_account_name",
        "to_account_type",
        "to_account_name_norm",
        "to_account_slug_norm",
        "amount_currency",
    ]

    df_first_payments = (
        df_payments
        .dropna(
            subset=["payment_created_at"]
        )
        .groupby(
            group_columns,
            dropna=False,
        )
        .agg(
            first_payment_at=(
                "payment_created_at",
                "min",
            ),
            last_payment_at=(
                "payment_created_at",
                "max",
            ),
            num_payments=(
                "transaction_id",
                "count",
            ),
            total_payment_amount=(
                "amount_abs",
                "sum",
            ),
            num_development_labeled_payments=(
                "is_development",
                lambda values: (
                    values == True
                ).sum(),
            ),
            num_non_development_labeled_payments=(
                "is_development",
                lambda values: (
                    values == False
                ).sum(),
            ),
        )
        .reset_index()
    )

    print("\n===== Payment base =====")
    print("Payment rows:", len(df_payments))
    print(
        "Project-payee pairs:",
        len(df_first_payments),
    )
    print(
        "Projects:",
        df_first_payments[
            PROJECT_COL
        ].nunique(),
    )
    print(
        "Payees:",
        df_first_payments[
            "to_account_slug"
        ].nunique(),
    )

    return df_first_payments


# ============================================================
# 受取人とIssue作成者のマッチング
# ============================================================

def build_issue_authors(
    df_project_issues: pd.DataFrame,
) -> pd.DataFrame:
    return (
        df_project_issues[
            [
                PROJECT_COL,
                "repo_name",
                "github_account",
                "author_login",
                "author_login_norm",
            ]
        ]
        .dropna(
            subset=["author_login_norm"]
        )
        .drop_duplicates()
        .copy()
    )


def match_payees_to_issue_authors(
    df_first_payments: pd.DataFrame,
    df_project_issues: pd.DataFrame,
):
    """
    同一プロジェクト内で次を照合する。

    1. Open Collective受取人名
       == GitHub author_login

    2. Open Collective受取人slug
       == GitHub author_login

    複数のGitHub loginへ一致したproject-payeeは
    曖昧なため主分析から除外する。
    """
    payment_columns = [
        PROJECT_COL,
        "project_name",
        "to_account_slug",
        "to_account_name",
        "to_account_type",
        "to_account_name_norm",
        "to_account_slug_norm",
        "amount_currency",
        "first_payment_at",
        "last_payment_at",
        "num_payments",
        "total_payment_amount",
        "num_development_labeled_payments",
        "num_non_development_labeled_payments",
    ]

    df_issue_authors = build_issue_authors(
        df_project_issues
    )

    name_matches = (
        df_first_payments[payment_columns]
        .merge(
            df_issue_authors,
            left_on=[
                PROJECT_COL,
                "to_account_name_norm",
            ],
            right_on=[
                PROJECT_COL,
                "author_login_norm",
            ],
            how="inner",
        )
    )

    name_matches["match_method"] = (
        "normalized_name_to_github_login"
    )

    slug_matches = (
        df_first_payments[payment_columns]
        .merge(
            df_issue_authors,
            left_on=[
                PROJECT_COL,
                "to_account_slug_norm",
            ],
            right_on=[
                PROJECT_COL,
                "author_login_norm",
            ],
            how="inner",
        )
    )

    slug_matches["match_method"] = (
        "normalized_slug_to_github_login"
    )

    df_matches_raw = pd.concat(
        [
            name_matches,
            slug_matches,
        ],
        ignore_index=True,
    )

    if df_matches_raw.empty:
        print("\nNo payees matched to Issue authors.")

        return (
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
        )

    match_priority = {
        "normalized_slug_to_github_login": 1,
        "normalized_name_to_github_login": 2,
    }

    df_matches_raw["match_priority"] = (
        df_matches_raw["match_method"]
        .map(match_priority)
    )

    # 同じ方法で同じloginに重複一致した行を除去
    df_matches_raw = (
        df_matches_raw
        .sort_values("match_priority")
        .drop_duplicates(
            subset=[
                PROJECT_COL,
                "to_account_slug",
                "author_login",
            ],
            keep="first",
        )
        .drop(columns=["match_priority"])
        .reset_index(drop=True)
    )

    # 1つのproject-payeeが何個のloginに一致したか
    df_match_counts = (
        df_matches_raw
        .groupby(
            [
                PROJECT_COL,
                "to_account_slug",
            ],
            as_index=False,
        )
        .agg(
            matched_login_count=(
                "author_login",
                "nunique",
            )
        )
    )

    df_matches_raw = df_matches_raw.merge(
        df_match_counts,
        on=[
            PROJECT_COL,
            "to_account_slug",
        ],
        how="left",
    )

    # 複数loginへ一致したケース
    df_ambiguous = df_matches_raw[
        df_matches_raw[
            "matched_login_count"
        ] > 1
    ].copy()

    # 一意にloginを決められたケースだけ残す
    df_unambiguous = df_matches_raw[
        df_matches_raw[
            "matched_login_count"
        ] == 1
    ].copy()

    group_columns = [
        PROJECT_COL,
        "project_name",
        "repo_name",
        "github_account",
        "to_account_slug",
        "to_account_name",
        "to_account_type",
        "amount_currency",
        "first_payment_at",
        "last_payment_at",
        "num_payments",
        "total_payment_amount",
        "num_development_labeled_payments",
        "num_non_development_labeled_payments",
        "author_login",
    ]

    df_matched_payees = (
        df_unambiguous
        .groupby(
            group_columns,
            dropna=False,
        )
        .agg(
            match_methods=(
                "match_method",
                unique_join,
            )
        )
        .reset_index()
        .rename(
            columns={
                "author_login": "github_login",
            }
        )
    )

    print("\n===== Payee-Issue author matching =====")
    print(
        "Raw matching rows:",
        len(df_matches_raw),
    )
    print(
        "Matched project-payee pairs:",
        df_matches_raw[
            [
                PROJECT_COL,
                "to_account_slug",
            ]
        ].drop_duplicates().shape[0],
    )
    print(
        "Unambiguous matches:",
        len(df_matched_payees),
    )
    print(
        "Ambiguous project-payee pairs:",
        df_ambiguous[
            [
                PROJECT_COL,
                "to_account_slug",
            ]
        ].drop_duplicates().shape[0],
    )

    print("\nMatch method distribution:")
    print(
        df_matches_raw[
            "match_method"
        ].value_counts().to_string()
    )

    return (
        df_matched_payees,
        df_matches_raw,
        df_ambiguous,
    )


# ============================================================
# マッチした開発者が作成したIssueを抽出
# ============================================================

def extract_matched_developer_issues(
    df_project_issues: pd.DataFrame,
    df_matched_payees: pd.DataFrame,
) -> pd.DataFrame:
    match_columns = (
        df_matched_payees[
            [
                PROJECT_COL,
                "repo_name",
                "to_account_slug",
                "to_account_name",
                "github_login",
                "first_payment_at",
                "last_payment_at",
                "num_payments",
                "total_payment_amount",
            ]
        ]
        .drop_duplicates()
    )

    df_developer_issues = (
        df_project_issues
        .merge(
            match_columns,
            left_on=[
                PROJECT_COL,
                "repo_name",
                "author_login",
            ],
            right_on=[
                PROJECT_COL,
                "repo_name",
                "github_login",
            ],
            how="inner",
        )
    )

    df_developer_issues = (
        df_developer_issues
        .drop_duplicates(
            subset=[
                PROJECT_COL,
                "repo_name",
                "github_login",
                "number",
            ]
        )
        .reset_index(drop=True)
    )

    print("\n===== Matched developer Issues =====")
    print(
        "Issue rows:",
        len(df_developer_issues),
    )
    print(
        "Developer-project pairs:",
        df_developer_issues[
            [
                PROJECT_COL,
                "github_login",
            ]
        ].drop_duplicates().shape[0],
    )
    print(
        "Developers:",
        df_developer_issues[
            "github_login"
        ].nunique(),
    )
    print(
        "Projects:",
        df_developer_issues[
            PROJECT_COL
        ].nunique(),
    )

    return df_developer_issues


# ============================================================
# ラベル展開・カテゴリ分類
# ============================================================

def classify_issue_categories(
    df_developer_issues: pd.DataFrame,
) -> pd.DataFrame:
    """
    出力:
        1 Issue × 1 category

    同じIssueが複数カテゴリに属することを許す。
    """
    issue_id_columns = [
        PROJECT_COL,
        "repo_name",
        "github_login",
        "number",
        "created_at",
    ]

    df_labels = (
        df_developer_issues
        .assign(
            raw_label=(
                df_developer_issues["labels"]
                .fillna("")
                .str.split(";")
            )
        )
        .explode("raw_label")
    )

    df_labels["raw_label"] = (
        df_labels["raw_label"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df_labels = df_labels[
        df_labels["raw_label"].ne("")
    ].copy()

    df_labels["normalized_key"] = (
        df_labels["raw_label"]
        .map(normalize_label_key)
    )

    df_labels = df_labels[
        df_labels["normalized_key"].ne("")
    ].copy()

    # 同一Issue内で同じ正規化ラベルが複数回あっても1回
    df_labels = (
        df_labels
        .drop_duplicates(
            subset=(
                issue_id_columns
                + ["normalized_key"]
            )
        )
    )

    category_rows = []

    for category, keys in ISSUE_CATEGORY_KEYS.items():
        matched = df_labels[
            df_labels[
                "normalized_key"
            ].isin(keys)
        ][issue_id_columns].drop_duplicates()

        if matched.empty:
            continue

        matched = matched.copy()
        matched["category"] = category

        category_rows.append(matched)

    if category_rows:
        df_categories = pd.concat(
            category_rows,
            ignore_index=True,
        )
    else:
        df_categories = pd.DataFrame(
            columns=(
                issue_id_columns
                + ["category"]
            )
        )

    df_categories = (
        df_categories
        .drop_duplicates(
            subset=(
                issue_id_columns
                + ["category"]
            )
        )
        .reset_index(drop=True)
    )

    # -------------------------
    # unlabeled
    # -------------------------

    unlabeled_mask = (
        df_developer_issues["labels"]
        .fillna("")
        .str.strip()
        .eq("")
    )

    df_unlabeled = (
        df_developer_issues.loc[
            unlabeled_mask,
            issue_id_columns,
        ]
        .drop_duplicates()
        .copy()
    )

    df_unlabeled["category"] = "unlabeled"

    # -------------------------
    # other_labeled
    # -------------------------

    classified_issue_ids = (
        df_categories[
            issue_id_columns
        ]
        .drop_duplicates()
        .assign(is_classified=True)
    )

    df_other = (
        df_developer_issues.loc[
            ~unlabeled_mask,
            issue_id_columns,
        ]
        .drop_duplicates()
        .merge(
            classified_issue_ids,
            on=issue_id_columns,
            how="left",
        )
    )

    df_other = df_other[
        df_other["is_classified"].isna()
    ][issue_id_columns].copy()

    df_other["category"] = "other_labeled"

    df_categories = pd.concat(
        [
            df_categories,
            df_unlabeled,
            df_other,
        ],
        ignore_index=True,
    )

    df_categories = (
        df_categories
        .drop_duplicates(
            subset=(
                issue_id_columns
                + ["category"]
            )
        )
        .reset_index(drop=True)
    )

    print("\n===== Category distribution =====")
    print(
        df_categories[
            "category"
        ].value_counts().to_string()
    )

    return df_categories


# ============================================================
# 初回支払い前後の集計
# ============================================================

def classify_activity_status(
    before_count: int,
    after_count: int,
) -> str:
    if before_count > 0 and after_count > before_count:
        return "increased"

    if before_count > 0 and after_count < before_count:
        return "decreased"

    if before_count > 0 and after_count == before_count:
        return "unchanged"

    if before_count == 0 and after_count > 0:
        return "new_after"

    return "no_activity"


def build_before_after_counts(
    df_matched_payees: pd.DataFrame,
    df_developer_issues: pd.DataFrame,
    df_categories: pd.DataFrame,
) -> pd.DataFrame:
    """
    分析単位:
        project × paid developer × window × category
    """
    all_categories = (
        list(ISSUE_CATEGORY_KEYS.keys())
        + [
            "other_labeled",
            "unlabeled",
        ]
    )

    issues_grouped = {
        key: group
        for key, group in df_developer_issues.groupby(
            [
                PROJECT_COL,
                "repo_name",
                "github_login",
            ]
        )
    }

    categories_grouped = {
        key: group
        for key, group in df_categories.groupby(
            [
                PROJECT_COL,
                "repo_name",
                "github_login",
            ]
        )
    }

    empty_issues = df_developer_issues.iloc[0:0]
    empty_categories = df_categories.iloc[0:0]

    rows = []

    for index, pair in enumerate(
        df_matched_payees.itertuples(
            index=False
        ),
        start=1,
    ):
        pair_key = (
            getattr(pair, PROJECT_COL),
            pair.repo_name,
            pair.github_login,
        )

        pair_issues = issues_grouped.get(
            pair_key,
            empty_issues,
        )

        pair_categories = categories_grouped.get(
            pair_key,
            empty_categories,
        )

        first_payment_at = pair.first_payment_at

        for window in ANALYSIS_WINDOWS:
            before_start = (
                first_payment_at
                - pd.DateOffset(months=window)
            )

            before_end = first_payment_at

            after_start = first_payment_at

            after_end = (
                first_payment_at
                + pd.DateOffset(months=window)
            )

            before_issues = pair_issues[
                pair_issues["created_at"].ge(
                    before_start
                )
                & pair_issues["created_at"].lt(
                    before_end
                )
            ]

            after_issues = pair_issues[
                pair_issues["created_at"].ge(
                    after_start
                )
                & pair_issues["created_at"].lt(
                    after_end
                )
            ]

            total_before = (
                before_issues["number"]
                .nunique()
            )

            total_after = (
                after_issues["number"]
                .nunique()
            )

            for category in all_categories:
                before_category = pair_categories[
                    pair_categories[
                        "category"
                    ].eq(category)
                    & pair_categories[
                        "created_at"
                    ].ge(before_start)
                    & pair_categories[
                        "created_at"
                    ].lt(before_end)
                ]

                after_category = pair_categories[
                    pair_categories[
                        "category"
                    ].eq(category)
                    & pair_categories[
                        "created_at"
                    ].ge(after_start)
                    & pair_categories[
                        "created_at"
                    ].lt(after_end)
                ]

                before_count = (
                    before_category["number"]
                    .nunique()
                )

                after_count = (
                    after_category["number"]
                    .nunique()
                )

                difference = (
                    after_count - before_count
                )

                growth_rate_pct = (
                    difference
                    / before_count
                    * 100
                    if before_count > 0
                    else np.nan
                )

                before_share = (
                    before_count / total_before
                    if total_before > 0
                    else np.nan
                )

                after_share = (
                    after_count / total_after
                    if total_after > 0
                    else np.nan
                )

                share_difference = (
                    after_share - before_share
                    if pd.notna(before_share)
                    and pd.notna(after_share)
                    else np.nan
                )

                rows.append({
                    PROJECT_COL:
                        getattr(pair, PROJECT_COL),

                    "repo_name":
                        pair.repo_name,

                    "to_account_slug":
                        pair.to_account_slug,

                    "to_account_name":
                        pair.to_account_name,

                    "github_login":
                        pair.github_login,

                    "first_payment_at":
                        first_payment_at,

                    "window_months":
                        window,

                    "category":
                        category,

                    "total_issues_before":
                        total_before,

                    "total_issues_after":
                        total_after,

                    "before_count":
                        before_count,

                    "after_count":
                        after_count,

                    "difference":
                        difference,

                    "growth_rate_pct":
                        growth_rate_pct,

                    "before_share":
                        before_share,

                    "after_share":
                        after_share,

                    "share_difference":
                        share_difference,

                    "activity_status":
                        classify_activity_status(
                            before_count,
                            after_count,
                        ),
                })

        if (
            index % 100 == 0
            or index == len(df_matched_payees)
        ):
            print(
                f"Processed {index} / "
                f"{len(df_matched_payees)} "
                "project-payee pairs"
            )

    return pd.DataFrame(rows)


# ============================================================
# 要約
# ============================================================

def summarize_before_after_counts(
    df_counts: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for (
        category,
        window,
    ), group in df_counts.groupby(
        [
            "category",
            "window_months",
        ],
        sort=True,
    ):
        valid_growth = group[
            "growth_rate_pct"
        ].dropna()

        valid_share_difference = group[
            "share_difference"
        ].dropna()

        status_counts = (
            group["activity_status"]
            .value_counts()
        )

        rows.append({
            "category": category,
            "window_months": window,

            "n_project_payees": len(group),

            "median_total_issues_before":
                group[
                    "total_issues_before"
                ].median(),

            "median_total_issues_after":
                group[
                    "total_issues_after"
                ].median(),

            "median_before_count":
                group["before_count"].median(),

            "median_after_count":
                group["after_count"].median(),

            "median_difference":
                group["difference"].median(),

            "n_growth_rate_valid":
                len(valid_growth),

            "median_growth_rate_pct":
                valid_growth.median(),

            "q1_growth_rate_pct":
                valid_growth.quantile(0.25),

            "q3_growth_rate_pct":
                valid_growth.quantile(0.75),

            "median_before_share":
                group["before_share"].median(),

            "median_after_share":
                group["after_share"].median(),

            "median_share_difference":
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
        })

    return (
        pd.DataFrame(rows)
        .sort_values(
            [
                "category",
                "window_months",
            ]
        )
        .reset_index(drop=True)
    )


# ============================================================
# 統計検定
# ============================================================

def safe_wilcoxon(
    after: pd.Series,
    before: pd.Series,
    alternative: str = "two-sided",
):
    after = pd.to_numeric(
        after,
        errors="coerce",
    )

    before = pd.to_numeric(
        before,
        errors="coerce",
    )

    valid_mask = (
        after.notna()
        & before.notna()
    )

    after = after[valid_mask]
    before = before[valid_mask]

    difference = after - before

    if len(difference) == 0:
        return np.nan, np.nan

    if not difference.ne(0).any():
        return 0.0, 1.0

    result = wilcoxon(
        after,
        before,
        alternative=alternative,
        zero_method="wilcox",
        method="auto",
    )

    return (
        result.statistic,
        result.pvalue,
    )


def add_holm_correction(
    df_results: pd.DataFrame,
) -> pd.DataFrame:
    df_results = df_results.copy()

    df_results["p_value_holm"] = np.nan
    df_results["significant_holm"] = False

    valid_mask = (
        df_results["p_value_raw"].notna()
    )

    if valid_mask.any():
        reject, adjusted, _, _ = (
            multipletests(
                df_results.loc[
                    valid_mask,
                    "p_value_raw",
                ],
                alpha=0.05,
                method="holm",
            )
        )

        df_results.loc[
            valid_mask,
            "p_value_holm",
        ] = adjusted

        df_results.loc[
            valid_mask,
            "significant_holm",
        ] = reject

    return df_results


def run_category_tests(
    df_counts: pd.DataFrame,
):
    """
    件数と構成比について、それぞれ両側Wilcoxon検定。

    件数と構成比は異なる仮説なので、
    それぞれ別の検定ファミリーとしてHolm補正する。
    """
    count_rows = []
    share_rows = []

    for (
        category,
        window,
    ), group in df_counts.groupby(
        [
            "category",
            "window_months",
        ],
        sort=True,
    ):
        # -------------------------
        # 件数
        # -------------------------

        count_statistic, count_p = (
            safe_wilcoxon(
                after=group["after_count"],
                before=group["before_count"],
                alternative="two-sided",
            )
        )

        count_difference = (
            group["after_count"]
            - group["before_count"]
        )

        count_rows.append({
            "category": category,
            "window_months": window,
            "n_project_payees": len(group),

            "median_before_count":
                group["before_count"].median(),

            "median_after_count":
                group["after_count"].median(),

            "median_difference":
                count_difference.median(),

            "increased_count":
                int(
                    (
                        count_difference > 0
                    ).sum()
                ),

            "decreased_count":
                int(
                    (
                        count_difference < 0
                    ).sum()
                ),

            "unchanged_count":
                int(
                    (
                        count_difference == 0
                    ).sum()
                ),

            "wilcoxon_statistic":
                count_statistic,

            "p_value_raw":
                count_p,
        })

        # -------------------------
        # 構成比
        # -------------------------

        share_group = group[
            group["before_share"].notna()
            & group["after_share"].notna()
        ].copy()

        share_statistic, share_p = (
            safe_wilcoxon(
                after=share_group[
                    "after_share"
                ],
                before=share_group[
                    "before_share"
                ],
                alternative="two-sided",
            )
        )

        share_difference = (
            share_group["after_share"]
            - share_group["before_share"]
        )

        share_rows.append({
            "category": category,
            "window_months": window,

            "n_project_payees":
                len(share_group),

            "median_before_share":
                share_group[
                    "before_share"
                ].median(),

            "median_after_share":
                share_group[
                    "after_share"
                ].median(),

            "median_share_difference":
                share_difference.median(),

            "wilcoxon_statistic":
                share_statistic,

            "p_value_raw":
                share_p,
        })

    df_count_tests = add_holm_correction(
        pd.DataFrame(count_rows)
    )

    df_share_tests = add_holm_correction(
        pd.DataFrame(share_rows)
    )

    return (
        df_count_tests,
        df_share_tests,
    )


# ============================================================
# 1分析条件の実行
# ============================================================

def run_analysis(
    config,
    engine,
    df_project_issues,
):
    analysis_label = config[
        "analysis_label"
    ]

    description = config[
        "description"
    ]

    where_extra = config[
        "where_extra"
    ]

    print("\n\n" + "=" * 80)
    print(
        f"===== Analysis: {analysis_label} ====="
    )
    print(
        f"===== Meaning: {description} ====="
    )
    print("=" * 80)

    # -------------------------
    # 支払い
    # -------------------------

    df_payments = load_payments(
        engine,
        where_extra,
    )

    df_first_payments = build_first_payments(
        df_payments
    )

    # -------------------------
    # 実行時にマッチング
    # -------------------------

    (
        df_matched_payees,
        df_matches_raw,
        df_ambiguous,
    ) = match_payees_to_issue_authors(
        df_first_payments,
        df_project_issues,
    )

    if df_matched_payees.empty:
        print(
            "No unambiguous matched payees. "
            "Stop this analysis."
        )
        return None

    # マッチング結果はファイル保存しない
    # 実行中のDataFrameとしてのみ使用する

    # -------------------------
    # 対象Issue
    # -------------------------

    df_developer_issues = (
        extract_matched_developer_issues(
            df_project_issues,
            df_matched_payees,
        )
    )

    # -------------------------
    # カテゴリ分類
    # -------------------------

    df_categories = (
        classify_issue_categories(
            df_developer_issues
        )
    )

    # -------------------------
    # 前後集計
    # -------------------------

    df_counts = build_before_after_counts(
        df_matched_payees=
            df_matched_payees,

        df_developer_issues=
            df_developer_issues,

        df_categories=
            df_categories,
    )

    df_summary = (
        summarize_before_after_counts(
            df_counts
        )
    )

    # -------------------------
    # 統計検定
    # -------------------------

    (
        df_count_tests,
        df_share_tests,
    ) = run_category_tests(
        df_counts
    )

    # -------------------------
    # 結果保存
    # -------------------------

    save_dataframe(
        df_developer_issues,
        analysis_label,
        "matched_developer_issues",
    )

    save_dataframe(
        df_categories,
        analysis_label,
        "issue_categories",
    )

    save_dataframe(
        df_counts,
        analysis_label,
        "before_after_detail",
    )

    save_dataframe(
        df_summary,
        analysis_label,
        "before_after_summary",
    )

    save_dataframe(
        df_count_tests,
        analysis_label,
        "count_wilcoxon_holm",
    )

    save_dataframe(
        df_share_tests,
        analysis_label,
        "share_wilcoxon_holm",
    )

    print("\n===== Category summary =====")
    print(
        df_summary.to_string(index=False)
    )

    print("\n===== Count tests =====")
    print(
        df_count_tests.to_string(index=False)
    )

    print("\n===== Share tests =====")
    print(
        df_share_tests.to_string(index=False)
    )

    return {
        "analysis_label": analysis_label,
        "matched_payee_count":
            len(df_matched_payees),
        "matched_issue_count":
            len(df_developer_issues),
        "summary":
            df_summary,
        "count_tests":
            df_count_tests,
        "share_tests":
            df_share_tests,
    }


# ============================================================
# main
# ============================================================

def main():
    engine = database_engine()

    (
        df_collectives,
        df_issues,
    ) = load_common_data(engine)

    df_project_issues = (
        build_project_issue_base(
            df_collectives,
            df_issues,
        )
    )

    results = []

    for config in ANALYSIS_CONFIGS:
        result = run_analysis(
            config=config,
            engine=engine,
            df_project_issues=
                df_project_issues,
        )

        if result is not None:
            results.append(result)

    print("\n\n===== Combined result =====")

    for result in results:
        print(
            result["analysis_label"],
            "matched payees:",
            result["matched_payee_count"],
            "matched issues:",
            result["matched_issue_count"],
        )


if __name__ == "__main__":
    main()
