from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
import api
import re
import unicodedata

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, inspect


PROJECT_COL = "project_slug"
ISSUE_PR_TABLE = "github_issue_pr_items"
ISSUE_PR_SCHEMA = "public"


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


def make_payments_sql(where_extra):
    return f"""
SELECT
    id AS transaction_id,
    project_slug,
    project_name,
    created_at AS payment_created_at,
    amount_value,
    amount_currency,
    to_account_slug,
    to_account_name,
    to_account_type,
    is_development
FROM public.collective_transactions
WHERE kind = 'EXPENSE'
  AND to_account_type = 'INDIVIDUAL'
  AND to_account_slug IS NOT NULL
  AND to_account_name IS NOT NULL
  AND created_at IS NOT NULL
  {where_extra}
"""


def database_engine():
    password = api.load_sql_password_from_credentials()

    return create_engine(
        "postgresql+psycopg2://"
        f"postgres:{password}"
        "@localhost:5432/opencollective"
    )


def normalize_name(value):
    """
    Open Collectiveの名前・slugとGitHub loginを
    比較するための正規化。

    例:
        foo-bar
        foo_bar
        Foo Bar

    はすべて foobar になる。
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


def get_issue_table_columns(engine):
    inspector = inspect(engine)

    column_information = inspector.get_columns(
        ISSUE_PR_TABLE,
        schema=ISSUE_PR_SCHEMA,
    )

    columns = [
        column["name"]
        for column in column_information
    ]

    print("\n===== github_issue_pr_items columns =====")

    for column in columns:
        print(column)

    return columns


def detect_issue_actor_columns(columns):
    """
    Issueをopenした人・closeした人の列を検出する。

    openした人は通常 author_login。

    closeした人については、実際のDBに保存されている
    列名を候補から探す。
    """
    opener_candidates = [
        "author_login",
        "creator_login",
        "opened_by_login",
        "user_login",
    ]

    closer_candidates = [
        "closed_by_login",
        "closer_login",
        "closed_by",
        "closed_user_login",
    ]

    opener_column = next(
        (
            column
            for column in opener_candidates
            if column in columns
        ),
        None,
    )

    closer_column = next(
        (
            column
            for column in closer_candidates
            if column in columns
        ),
        None,
    )

    if opener_column is None:
        raise ValueError(
            "Issue opener column could not be found. "
            f"Candidates: {opener_candidates}"
        )

    print("\n===== Detected actor columns =====")
    print("Issue opener column:", opener_column)
    print(
        "Issue closer column:",
        closer_column
        if closer_column is not None
        else "Not found",
    )

    return opener_column, closer_column


def make_issues_sql(
    opener_column,
    closer_column,
):
    closer_select = (
        f"{closer_column} AS closer_login"
        if closer_column is not None
        else "NULL::text AS closer_login"
    )

    return f"""
SELECT
    collective_id,
    project_slug,
    project_name,
    repo_name,
    number,
    created_at,
    closed_at,
    {opener_column} AS opener_login,
    {closer_select}
FROM public.github_issue_pr_items
WHERE item_type = 'issue'
  AND repo_name IS NOT NULL
  AND number IS NOT NULL
  AND created_at IS NOT NULL
"""


def load_collectives(engine):
    df_collectives = pd.read_sql(
        COLLECTIVES_SQL,
        engine,
    )

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

    print("\n===== Loaded collectives =====")
    print("Collectives:", len(df_collectives))
    print(
        "Repositories:",
        df_collectives["repo_name"].nunique(),
    )

    return df_collectives


def load_issue_actors(
    engine,
    opener_column,
    closer_column,
):
    query = make_issues_sql(
        opener_column=opener_column,
        closer_column=closer_column,
    )

    df_issues = pd.read_sql(
        query,
        engine,
    )

    df_issues["repo_name"] = (
        df_issues["repo_name"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    for column in [
        "opener_login",
        "closer_login",
    ]:
        df_issues[column] = (
            df_issues[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        )

        df_issues[
            f"{column}_norm"
        ] = df_issues[column].map(
            normalize_name
        )

    print("\n===== Loaded Issue actors =====")
    print("Issue rows:", len(df_issues))
    print(
        "Repositories:",
        df_issues["repo_name"].nunique(),
    )
    print(
        "Unique opener logins:",
        df_issues.loc[
            df_issues["opener_login"].ne(""),
            "opener_login",
        ].nunique(),
    )
    print(
        "Unique closer logins:",
        df_issues.loc[
            df_issues["closer_login"].ne(""),
            "closer_login",
        ].nunique(),
    )

    return df_issues


def build_project_issue_base(
    df_collectives,
    df_issues,
):
    """
    collectives.github_accountから作ったrepo_nameを使用して、
    IssueをOpen Collectiveプロジェクトへ対応付ける。
    """
    df_projects = (
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
                "id": "collective_id",
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

    df_project_issues = (
        df_issues
        .drop(columns=issue_columns_to_drop)
        .merge(
            df_projects,
            on="repo_name",
            how="inner",
            validate="many_to_many",
        )
    )

    print("\n===== Project Issue base =====")
    print("Original Issue rows:", len(df_issues))
    print(
        "Project-linked Issue rows:",
        len(df_project_issues),
    )
    print(
        "Matched projects:",
        df_project_issues[
            PROJECT_COL
        ].nunique(),
    )
    print(
        "Matched repositories:",
        df_project_issues[
            "repo_name"
        ].nunique(),
    )

    return df_project_issues


def load_payments(
    engine,
    where_extra,
):
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

    df_payments[
        "to_account_name_norm"
    ] = df_payments[
        "to_account_name"
    ].map(normalize_name)

    df_payments[
        "to_account_slug_norm"
    ] = df_payments[
        "to_account_slug"
    ].map(normalize_name)

    return df_payments


def build_first_payments(df_payments):
    group_columns = [
        PROJECT_COL,
        "project_name",
        "to_account_slug",
        "to_account_name",
        "to_account_type",
        "to_account_name_norm",
        "to_account_slug_norm",
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


def build_project_actor_table(
    df_project_issues,
):
    """
    1行を
        project × repo × GitHub login × actor type
    にする。

    同じ人物がIssueをopen・closeしている場合は、
    actor_typeが異なる2行になる。
    """
    opener_rows = (
        df_project_issues.loc[
            df_project_issues[
                "opener_login_norm"
            ].ne(""),
            [
                PROJECT_COL,
                "repo_name",
                "github_account",
                "opener_login",
                "opener_login_norm",
            ],
        ]
        .rename(
            columns={
                "opener_login": "github_login",
                "opener_login_norm":
                    "github_login_norm",
            }
        )
        .drop_duplicates()
    )

    opener_rows["actor_type"] = "opener"

    closer_rows = (
        df_project_issues.loc[
            df_project_issues[
                "closer_login_norm"
            ].ne(""),
            [
                PROJECT_COL,
                "repo_name",
                "github_account",
                "closer_login",
                "closer_login_norm",
            ],
        ]
        .rename(
            columns={
                "closer_login": "github_login",
                "closer_login_norm":
                    "github_login_norm",
            }
        )
        .drop_duplicates()
    )

    closer_rows["actor_type"] = "closer"

    df_actors = pd.concat(
        [
            opener_rows,
            closer_rows,
        ],
        ignore_index=True,
    )

    df_actors = (
        df_actors
        .drop_duplicates(
            [
                PROJECT_COL,
                "repo_name",
                "github_login",
                "actor_type",
            ]
        )
        .reset_index(drop=True)
    )

    print("\n===== Project Issue actor table =====")
    print("Actor rows:", len(df_actors))
    print(
        "Unique project-login pairs:",
        df_actors[
            [
                PROJECT_COL,
                "github_login",
            ]
        ].drop_duplicates().shape[0],
    )

    print("\nActor type distribution:")
    print(
        df_actors[
            "actor_type"
        ].value_counts().to_string()
    )

    return df_actors


def match_payees_to_issue_actors(
    df_first_payments,
    df_project_actors,
):
    payment_columns = [
        PROJECT_COL,
        "project_name",
        "to_account_slug",
        "to_account_name",
        "to_account_type",
        "to_account_name_norm",
        "to_account_slug_norm",
        "first_payment_at",
        "last_payment_at",
        "num_payments",
        "total_payment_amount",
        "num_development_labeled_payments",
        "num_non_development_labeled_payments",
    ]

    # Open Collective表示名とGitHub loginの一致
    name_matches = (
        df_first_payments[
            payment_columns
        ]
        .merge(
            df_project_actors,
            left_on=[
                PROJECT_COL,
                "to_account_name_norm",
            ],
            right_on=[
                PROJECT_COL,
                "github_login_norm",
            ],
            how="inner",
        )
    )

    name_matches["match_method"] = (
        "normalized_name_to_github_login"
    )

    # Open Collective slugとGitHub loginの一致
    slug_matches = (
        df_first_payments[
            payment_columns
        ]
        .merge(
            df_project_actors,
            left_on=[
                PROJECT_COL,
                "to_account_slug_norm",
            ],
            right_on=[
                PROJECT_COL,
                "github_login_norm",
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
        return pd.DataFrame(), pd.DataFrame()

    match_priority = {
        "normalized_slug_to_github_login": 1,
        "normalized_name_to_github_login": 2,
    }

    df_matches_raw["match_priority"] = (
        df_matches_raw[
            "match_method"
        ].map(match_priority)
    )

    # 同じproject-payee、login、actor_typeについて
    # slug一致を優先して1行にする
    df_matches_raw = (
        df_matches_raw
        .sort_values("match_priority")
        .drop_duplicates(
            subset=[
                PROJECT_COL,
                "to_account_slug",
                "github_login",
                "actor_type",
            ],
            keep="first",
        )
        .drop(
            columns=["match_priority"]
        )
        .reset_index(drop=True)
    )

    # opener/closerをまとめたproject-payee-login単位
    df_matched_logins = (
        df_matches_raw
        .groupby(
            [
                PROJECT_COL,
                "project_name",
                "repo_name",
                "github_account",
                "to_account_slug",
                "to_account_name",
                "first_payment_at",
                "github_login",
            ],
            dropna=False,
        )
        .agg(
            matched_as_opener=(
                "actor_type",
                lambda values:
                    "opener"
                    in set(values),
            ),
            matched_as_closer=(
                "actor_type",
                lambda values:
                    "closer"
                    in set(values),
            ),
            match_methods=(
                "match_method",
                lambda values:
                    "; ".join(
                        sorted(
                            set(values)
                        )
                    ),
            ),
        )
        .reset_index()
    )

    # 1つのproject-payeeが複数loginへ一致していないか確認
    login_counts = (
        df_matched_logins
        .groupby(
            [
                PROJECT_COL,
                "to_account_slug",
            ],
            as_index=False,
        )
        .agg(
            matched_login_count=(
                "github_login",
                "nunique",
            )
        )
    )

    df_matched_logins = (
        df_matched_logins
        .merge(
            login_counts,
            on=[
                PROJECT_COL,
                "to_account_slug",
            ],
            how="left",
        )
    )

    return (
        df_matched_logins,
        df_matches_raw,
    )


def summarize_matching(
    df_first_payments,
    df_matched_logins,
):
    total_pairs = (
        df_first_payments[
            [
                PROJECT_COL,
                "to_account_slug",
            ]
        ]
        .drop_duplicates()
    )

    if df_matched_logins.empty:
        matched_any_pairs = total_pairs.iloc[0:0]
        matched_opener_pairs = total_pairs.iloc[0:0]
        matched_closer_pairs = total_pairs.iloc[0:0]
        unambiguous_pairs = total_pairs.iloc[0:0]
    else:
        matched_any_pairs = (
            df_matched_logins[
                [
                    PROJECT_COL,
                    "to_account_slug",
                ]
            ]
            .drop_duplicates()
        )

        matched_opener_pairs = (
            df_matched_logins.loc[
                df_matched_logins[
                    "matched_as_opener"
                ],
                [
                    PROJECT_COL,
                    "to_account_slug",
                ],
            ]
            .drop_duplicates()
        )

        matched_closer_pairs = (
            df_matched_logins.loc[
                df_matched_logins[
                    "matched_as_closer"
                ],
                [
                    PROJECT_COL,
                    "to_account_slug",
                ],
            ]
            .drop_duplicates()
        )

        unambiguous_pairs = (
            df_matched_logins.loc[
                df_matched_logins[
                    "matched_login_count"
                ].eq(1),
                [
                    PROJECT_COL,
                    "to_account_slug",
                ],
            ]
            .drop_duplicates()
        )

    total_count = len(total_pairs)

    def rate(count):
        if total_count == 0:
            return np.nan

        return count / total_count

    df_summary = pd.DataFrame(
        [
            {
                "target":
                    "INDIVIDUAL project-payee pairs",
                "total_project_payees":
                    total_count,
                "matched_any_issue_actor":
                    len(matched_any_pairs),
                "match_rate_any_issue_actor":
                    rate(len(matched_any_pairs)),
                "matched_issue_openers":
                    len(matched_opener_pairs),
                "match_rate_issue_openers":
                    rate(len(matched_opener_pairs)),
                "matched_issue_closers":
                    len(matched_closer_pairs),
                "match_rate_issue_closers":
                    rate(len(matched_closer_pairs)),
                "unambiguous_matches":
                    len(unambiguous_pairs),
                "unambiguous_match_rate":
                    rate(len(unambiguous_pairs)),
                "unmatched_project_payees":
                    total_count
                    - len(matched_any_pairs),
            }
        ]
    )

    return df_summary


def summarize_match_patterns(
    df_matched_logins,
):
    if df_matched_logins.empty:
        return pd.DataFrame()

    df = df_matched_logins.copy()

    df["actor_match_type"] = np.select(
        [
            (
                df["matched_as_opener"]
                & df["matched_as_closer"]
            ),
            (
                df["matched_as_opener"]
                & ~df["matched_as_closer"]
            ),
            (
                ~df["matched_as_opener"]
                & df["matched_as_closer"]
            ),
        ],
        [
            "both_opener_and_closer",
            "opener_only",
            "closer_only",
        ],
        default="neither",
    )

    return (
        df.groupby(
            [
                "actor_match_type",
                "matched_login_count",
            ],
            dropna=False,
        )
        .agg(
            n_project_payee_logins=(
                "github_login",
                "size",
            ),
            n_projects=(
                PROJECT_COL,
                "nunique",
            ),
            n_payees=(
                "to_account_slug",
                "nunique",
            ),
        )
        .reset_index()
        .sort_values(
            [
                "actor_match_type",
                "matched_login_count",
            ]
        )
    )


def output_paths(analysis_label):
    prefix = (
        f"issue_actor_matching_"
        f"{analysis_label}"
    )

    return {
        "summary":
            f"{prefix}_summary.csv",
        "patterns":
            f"{prefix}_patterns.csv",
        "matched_detail":
            f"{prefix}_matched_detail.csv",
    }


def run_analysis(
    config,
    engine,
    df_project_actors,
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

    paths = output_paths(
        analysis_label
    )

    print("\n\n" + "=" * 80)
    print(
        f"===== Analysis: "
        f"{analysis_label} ====="
    )
    print(
        f"===== Meaning: "
        f"{description} ====="
    )
    print("=" * 80)

    df_payments = load_payments(
        engine,
        where_extra,
    )

    print("\n===== Loaded payments =====")
    print("Payment rows:", len(df_payments))
    print(
        "Projects:",
        df_payments[
            PROJECT_COL
        ].nunique(),
    )
    print(
        "Payees:",
        df_payments[
            "to_account_slug"
        ].nunique(),
    )

    df_first_payments = (
        build_first_payments(
            df_payments
        )
    )

    (
        df_matched_logins,
        df_matches_raw,
    ) = match_payees_to_issue_actors(
        df_first_payments,
        df_project_actors,
    )

    df_summary = summarize_matching(
        df_first_payments,
        df_matched_logins,
    )

    df_patterns = summarize_match_patterns(
        df_matched_logins
    )

    print("\n===== Matching summary =====")
    print(
        df_summary.to_string(
            index=False
        )
    )

    if not df_patterns.empty:
        print("\n===== Match patterns =====")
        print(
            df_patterns.to_string(
                index=False
            )
        )

    if not df_matched_logins.empty:
        print(
            "\n===== Match method distribution ====="
        )
        print(
            df_matches_raw[
                "match_method"
            ].value_counts().to_string()
        )

        print(
            "\n===== Matched-login-count distribution ====="
        )
        print(
            df_matched_logins[
                [
                    PROJECT_COL,
                    "to_account_slug",
                    "matched_login_count",
                ]
            ]
            .drop_duplicates()
            [
                "matched_login_count"
            ]
            .value_counts()
            .sort_index()
            .to_string()
        )
    
    # ========================================================
    # マッチした開発者が全期間に作成したIssue数
    # ========================================================

    df_created_issue_counts = (
        count_issues_created_by_matched_payees(
            df_project_issues=
                df_project_issues,
            df_matched_logins=
                df_matched_logins,
        )
    )

    df_created_issue_summary = (
        summarize_created_issue_counts(
            df_created_issue_counts
        )
    )

    df_created_issue_bins = (
        summarize_created_issue_count_bins(
            df_created_issue_counts
        )
    )

    print(
        "\n===== Issues created by matched payees ====="
    )

    print(
        df_created_issue_summary.to_string(
            index=False
        )
    )

    print(
        "\n===== Issue count distribution ====="
    )

    print(
        df_created_issue_bins.to_string(
            index=False
        )
    )
    
    issue_count_detail_path = (
        f"issue_actor_matching_"
        f"{analysis_label}_"
        f"created_issue_counts.csv"
    )

    issue_count_summary_path = (
        f"issue_actor_matching_"
        f"{analysis_label}_"
        f"created_issue_summary.csv"
    )

    issue_count_bins_path = (
        f"issue_actor_matching_"
        f"{analysis_label}_"
        f"created_issue_count_bins.csv"
    )

    df_created_issue_counts.to_csv(
        issue_count_detail_path,
        index=False,
    )

    df_created_issue_summary.to_csv(
        issue_count_summary_path,
        index=False,
    )

    df_created_issue_bins.to_csv(
        issue_count_bins_path,
        index=False,
    )

    print("Saved:", issue_count_detail_path)
    print("Saved:", issue_count_summary_path)
    print("Saved:", issue_count_bins_path)

    # マッチング確認用なので、現段階では
    # 結果をCSVにも出して目視確認できるようにする
    df_summary.to_csv(
        paths["summary"],
        index=False,
    )

    df_patterns.to_csv(
        paths["patterns"],
        index=False,
    )

    df_matched_logins.to_csv(
        paths["matched_detail"],
        index=False,
    )

    print("\nSaved:", paths["summary"])
    print("Saved:", paths["patterns"])
    print("Saved:", paths["matched_detail"])

    return {
        "analysis_label":
            analysis_label,
        "summary":
            df_summary,
        "patterns":
            df_patterns,
        "matched_detail":
            df_matched_logins,
        "created_issue_counts":
            df_created_issue_counts,
        "created_issue_summary":
            df_created_issue_summary,
        "created_issue_bins":
            df_created_issue_bins,
    }


def main():
    engine = database_engine()

    columns = get_issue_table_columns(
        engine
    )

    (
        opener_column,
        closer_column,
    ) = detect_issue_actor_columns(
        columns
    )

    df_collectives = load_collectives(
        engine
    )

    df_issues = load_issue_actors(
        engine,
        opener_column=opener_column,
        closer_column=closer_column,
    )

    df_project_issues = (
        build_project_issue_base(
            df_collectives,
            df_issues,
        )
    )

    df_project_actors = (
        build_project_actor_table(
            df_project_issues
        )
    )

    results = []

    for config in ANALYSIS_CONFIGS:
        result = run_analysis(
            config=config,
            engine=engine,
            df_project_actors=
                df_project_actors,
            df_project_issues=
                df_project_issues
        )

        results.append(result)

    combined_summaries = [
        result["summary"].assign(
            analysis_label=
                result["analysis_label"]
        )
        for result in results
    ]

    df_combined = pd.concat(
        combined_summaries,
        ignore_index=True,
    )

    output_path = (
        "issue_actor_matching_"
        "combined_summary.csv"
    )

    df_combined.to_csv(
        output_path,
        index=False,
    )

    print("\n===== Combined summary =====")
    print(
        df_combined.to_string(
            index=False
        )
    )
    print("Saved:", output_path)

def count_issues_created_by_matched_payees(
    df_project_issues,
    df_matched_logins,
):
    """
    マッチングできた支払い受取人が、
    同一プロジェクト内で全期間に作成したIssue数を集計する。

    1行:
        project × payee × GitHub login
    """
    if df_matched_logins.empty:
        return pd.DataFrame()

    # 複数loginに一致した曖昧なケースは除外
    df_unambiguous_matches = (
        df_matched_logins.loc[
            df_matched_logins[
                "matched_login_count"
            ].eq(1),
            [
                PROJECT_COL,
                "project_name",
                "repo_name",
                "github_account",
                "to_account_slug",
                "to_account_name",
                "first_payment_at",
                "github_login",
                "matched_as_opener",
                "matched_as_closer",
                "match_methods",
            ],
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

    # マッチしたGitHub loginが作成したIssueを抽出
    df_matched_issues = (
        df_project_issues
        .merge(
            df_unambiguous_matches,
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
            suffixes=(
                "_issue",
                "_payee",
            ),
        )
    )

    # 同じIssueがmergeで重複した場合に備えて除去
    df_matched_issues = (
        df_matched_issues
        .drop_duplicates(
            subset=[
                PROJECT_COL,
                "repo_name",
                "github_login",
                "number",
            ]
        )
        .copy()
    )

    print("\n===== Matched Issue merge columns =====")
    print(
        df_matched_issues.columns.tolist()
    )

    # 開発者・プロジェクト単位でIssue数を集計
    #
    # github_accountはmerge後に
    # github_account_issue / github_account_payee
    # となる可能性があるため、groupbyには含めない。
    df_issue_counts = (
        df_matched_issues
        .groupby(
            [
                PROJECT_COL,
                "project_name",
                "repo_name",
                "to_account_slug",
                "to_account_name",
                "github_login",
                "first_payment_at",
                "matched_as_opener",
                "matched_as_closer",
                "match_methods",
            ],
            dropna=False,
        )
        .agg(
            first_issue_created_at=(
                "created_at",
                "min",
            ),
            last_issue_created_at=(
                "created_at",
                "max",
            ),
            total_issues_created=(
                "number",
                "nunique",
            ),
        )
        .reset_index()
    )

    # マッチしたがIssue作成者ではなかったcloser_onlyも残す。
    # その場合、Issue作成数は0になる。
    df_issue_counts = (
        df_unambiguous_matches
        .merge(
            df_issue_counts,
            on=[
                PROJECT_COL,
                "project_name",
                "repo_name",
                "to_account_slug",
                "to_account_name",
                "first_payment_at",
                "github_login",
                "matched_as_opener",
                "matched_as_closer",
                "match_methods",
            ],
            how="left",
        )
    )

    df_issue_counts[
        "total_issues_created"
    ] = (
        df_issue_counts[
            "total_issues_created"
        ]
        .fillna(0)
        .astype(int)
    )

    return (
        df_issue_counts
        .sort_values(
            "total_issues_created",
            ascending=False,
        )
        .reset_index(drop=True)
    )


def summarize_created_issue_counts(
    df_issue_counts,
):
    if df_issue_counts.empty:
        return pd.DataFrame()

    issue_counts = (
        df_issue_counts[
            "total_issues_created"
        ]
    )

    df_summary = pd.DataFrame(
        [
            {
                "n_project_payees":
                    len(df_issue_counts),

                "n_projects":
                    df_issue_counts[
                        PROJECT_COL
                    ].nunique(),

                "n_payees":
                    df_issue_counts[
                        "to_account_slug"
                    ].nunique(),

                "n_github_logins":
                    df_issue_counts[
                        "github_login"
                    ].nunique(),

                "total_issues_created":
                    issue_counts.sum(),

                "mean_issues_created":
                    issue_counts.mean(),

                "median_issues_created":
                    issue_counts.median(),

                "q1_issues_created":
                    issue_counts.quantile(0.25),

                "q3_issues_created":
                    issue_counts.quantile(0.75),

                "min_issues_created":
                    issue_counts.min(),

                "max_issues_created":
                    issue_counts.max(),

                "n_created_zero_issues":
                    int(
                        (
                            issue_counts == 0
                        ).sum()
                    ),

                "n_created_at_least_one_issue":
                    int(
                        (
                            issue_counts > 0
                        ).sum()
                    ),

                "ratio_created_at_least_one_issue":
                    (
                        (issue_counts > 0).mean()
                        if len(issue_counts)
                        else np.nan
                    ),
            }
        ]
    )

    return df_summary


def summarize_created_issue_count_bins(
    df_issue_counts,
):
    if df_issue_counts.empty:
        return pd.DataFrame()

    df = df_issue_counts.copy()

    df["issue_count_bin"] = pd.cut(
        df["total_issues_created"],
        bins=[
            -1,
            0,
            1,
            5,
            10,
            50,
            100,
            np.inf,
        ],
        labels=[
            "0",
            "1",
            "2-5",
            "6-10",
            "11-50",
            "51-100",
            "101+",
        ],
    )

    df_bins = (
        df.groupby(
            "issue_count_bin",
            observed=False,
        )
        .agg(
            n_project_payees=(
                "total_issues_created",
                "size",
            ),
            n_projects=(
                PROJECT_COL,
                "nunique",
            ),
            n_payees=(
                "to_account_slug",
                "nunique",
            ),
        )
        .reset_index()
    )

    total = len(df)

    df_bins["ratio"] = (
        df_bins["n_project_payees"]
        / total
        if total
        else np.nan
    )

    return df_bins



if __name__ == "__main__":
    main()