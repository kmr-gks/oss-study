import api
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sqlalchemy import create_engine


PROJECT_COL = "project_slug"

OUTPUT_DETAIL_CSV = "rq1_paid_individual_developer_first_payment_vs_first_commit_detail.csv"
OUTPUT_SUMMARY_CSV = "rq1_paid_individual_developer_first_payment_vs_first_commit_summary.csv"
OUTPUT_MATCH_SUMMARY_CSV = "rq1_paid_individual_developer_matching_summary.csv"
OUTPUT_TIMING_HIST_PNG = "rq1_days_from_first_commit_to_first_payment_hist.png"
OUTPUT_TIMING_TYPE_BAR_PNG = "rq1_developer_timing_type_bar.png"


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

DEV_PAYMENTS_SQL = """
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
    description
FROM public.collective_transactions
WHERE kind = 'EXPENSE'
  AND is_development = true
  AND to_account_type = 'INDIVIDUAL'
  AND to_account_slug IS NOT NULL
  AND to_account_name IS NOT NULL
  AND created_at IS NOT NULL
"""

COMMIT_HISTORY_SQL = """
SELECT
    repo_name,
    commit_hash,
    author_name,
    author_email,
    author_time,
    commit_time
FROM public.commit_history
WHERE repo_name IS NOT NULL
  AND commit_hash IS NOT NULL
  AND author_name IS NOT NULL
  AND commit_time IS NOT NULL
"""


def database_engine():
    password = api.load_sql_password_from_credentials()
    return create_engine(
        f"postgresql+psycopg2://postgres:{password}@localhost:5432/opencollective"
    )


def normalize_name(value):
    """
    Open Collective の to_account_name / to_account_slug と、
    Git の author_name を比較するための簡易正規化。
    """
    if pd.isna(value):
        return ""

    value = str(value).lower().strip()

    chars_to_remove = [
        " ",
        "\t",
        "\n",
        "\r",
        "-",
        "_",
        ".",
        ",",
        "'",
        '"',
        "`",
        "(",
        ")",
        "[",
        "]",
        "{",
        "}",
        "/",
        "\\",
    ]

    for ch in chars_to_remove:
        value = value.replace(ch, "")

    return value


def load_data(engine):
    df_collectives = pd.read_sql(COLLECTIVES_SQL, engine)
    df_payments = pd.read_sql(DEV_PAYMENTS_SQL, engine)
    df_commits = pd.read_sql(COMMIT_HISTORY_SQL, engine)

    df_collectives["created_at"] = pd.to_datetime(
        df_collectives["created_at"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    df_payments["payment_created_at"] = pd.to_datetime(
        df_payments["payment_created_at"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    df_commits["commit_time"] = pd.to_datetime(
        df_commits["commit_time"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    df_commits["author_time"] = pd.to_datetime(
        df_commits["author_time"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    df_collectives = df_collectives[
        df_collectives["github_account"].notna()
        & df_collectives["github_account"].str.contains("/", na=False)
    ].copy()

    df_collectives["repo_name"] = (
        df_collectives["github_account"]
        .astype(str)
        .str.strip()
        .str.replace("/", "-", regex=False)
    )

    df_payments["amount_abs"] = pd.to_numeric(
        df_payments["amount_value"],
        errors="coerce",
    ).abs()

    df_payments["to_account_name_norm"] = df_payments["to_account_name"].map(
        normalize_name
    )
    df_payments["to_account_slug_norm"] = df_payments["to_account_slug"].map(
        normalize_name
    )

    df_commits["author_name_norm"] = df_commits["author_name"].map(normalize_name)

    print("\n===== Loaded data =====")
    print("Collectives:", len(df_collectives))
    print("Development payments to individuals:", len(df_payments))
    print("Commit rows:", len(df_commits))

    return df_collectives, df_payments, df_commits


def build_project_commit_base(df_collectives, df_commits):
    df_project_commits = df_commits.merge(
        df_collectives[
            [
                "id",
                "slug",
                "name",
                "github_account",
                "repo_name",
            ]
        ].rename(
            columns={
                "id": "collective_id",
                "slug": PROJECT_COL,
                "name": "collective_name",
            }
        ),
        on="repo_name",
        how="inner",
        validate="many_to_many",
    )

    print("\n===== Project commit base =====")
    print("Commit rows:", len(df_commits))
    print("Project-linked commit rows:", len(df_project_commits))
    print("Matched projects:", df_project_commits[PROJECT_COL].nunique())
    print("Matched repos:", df_project_commits["repo_name"].nunique())

    return df_project_commits


def build_first_development_payments(df_payments):
    """
    project_slug × to_account_slug 単位で初回開発支払いを作る。
    """
    group_cols = [
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
        .dropna(subset=["payment_created_at"])
        .groupby(group_cols, dropna=False)
        .agg(
            first_payment_at=("payment_created_at", "min"),
            last_payment_at=("payment_created_at", "max"),
            num_development_payments=("transaction_id", "count"),
            total_development_payment_amount=("amount_abs", "sum"),
        )
        .reset_index()
    )

    print("\n===== Development payment base =====")
    print("Development payment rows:", len(df_payments))
    print("Project-payee pairs:", len(df_first_payments))
    print("Projects with development payments:", df_first_payments[PROJECT_COL].nunique())
    print("Payees with development payments:", df_first_payments["to_account_slug"].nunique())

    return df_first_payments


def build_commit_authors(df_project_commits):
    """
    project_slug 内の author_name 単位で、コミット作者候補を作る。
    author_email は後で project-payee 単位に統合するため、ここでは保持する。
    """
    return (
        df_project_commits[
            [
                PROJECT_COL,
                "repo_name",
                "github_account",
                "author_name",
                "author_name_norm",
                "author_email",
                "commit_hash",
                "commit_time",
            ]
        ]
        .dropna(subset=["author_name_norm"])
        .copy()
    )


def match_payees_to_commits(df_first_payments, df_project_commits):
    """
    project_slug × to_account_slug の支払い先に対して、
    同じ project_slug 内で一致する commit author の全コミットを紐づける。

    一致条件:
      1. normalized(to_account_name) = normalized(author_name)
      2. normalized(to_account_slug) = normalized(author_name)

    最終的には project_slug × to_account_slug 単位に戻す。
    """
    pay_cols = [
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
        "num_development_payments",
        "total_development_payment_amount",
    ]

    df_commit_authors = build_commit_authors(df_project_commits)

    name_matches = df_first_payments[pay_cols].merge(
        df_commit_authors,
        left_on=[PROJECT_COL, "to_account_name_norm"],
        right_on=[PROJECT_COL, "author_name_norm"],
        how="inner",
    )
    name_matches["match_method"] = "normalized_name"

    slug_matches = df_first_payments[pay_cols].merge(
        df_commit_authors,
        left_on=[PROJECT_COL, "to_account_slug_norm"],
        right_on=[PROJECT_COL, "author_name_norm"],
        how="inner",
    )
    slug_matches["match_method"] = "normalized_slug_to_author_name"

    df_matches_raw = pd.concat([name_matches, slug_matches], ignore_index=True)

    if df_matches_raw.empty:
        print("\nNo payees matched to commit authors.")
        return pd.DataFrame(), df_matches_raw

    # 同じ project-payee-commit が複数の方法で一致した場合は重複を除く。
    # name一致を優先する。
    match_priority = {
        "normalized_name": 1,
        "normalized_slug_to_author_name": 2,
    }
    df_matches_raw["match_priority"] = df_matches_raw["match_method"].map(
        match_priority
    )

    df_matches_raw = (
        df_matches_raw
        .sort_values("match_priority")
        .drop_duplicates(
            subset=[
                PROJECT_COL,
                "to_account_slug",
                "commit_hash",
            ],
            keep="first",
        )
        .drop(columns=["match_priority"])
        .reset_index(drop=True)
    )

    print("\n===== Raw payee-commit matching =====")
    print("Matched rows:", len(df_matches_raw))
    print(
        "Matched project-payee pairs:",
        df_matches_raw[[PROJECT_COL, "to_account_slug"]].drop_duplicates().shape[0],
    )
    print("Matched projects:", df_matches_raw[PROJECT_COL].nunique())
    print("Matched commit authors:", df_matches_raw[["author_name", "author_email"]].drop_duplicates().shape[0])
    print("\nMatch method distribution:")
    print(df_matches_raw["match_method"].value_counts().to_string())

    df_matched_payees = aggregate_matches_to_project_payee(df_matches_raw)

    return df_matched_payees, df_matches_raw


def unique_join(series):
    values = (
        series
        .dropna()
        .astype(str)
        .sort_values()
        .unique()
        .tolist()
    )
    return "; ".join(values)


def aggregate_matches_to_project_payee(df_matches_raw):
    """
    project_slug × to_account_slug に戻す。
    複数 author_name / author_email に一致した場合、その全コミットを統合する。
    """
    group_cols = [
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
        "num_development_payments",
        "total_development_payment_amount",
    ]

    df_matched_payees = (
        df_matches_raw
        .groupby(group_cols, dropna=False)
        .agg(
            first_commit_at=("commit_time", "min"),
            last_commit_at=("commit_time", "max"),
            total_commits=("commit_hash", "nunique"),
            matched_author_names=("author_name", unique_join),
            matched_author_emails=("author_email", unique_join),
            matched_author_name_count=("author_name", lambda s: s.dropna().nunique()),
            matched_author_email_count=("author_email", lambda s: s.dropna().nunique()),
            match_methods=("match_method", unique_join),
        )
        .reset_index()
    )

    return df_matched_payees


def classify_timing(row):
    first_commit_at = row["first_commit_at"]
    first_payment_at = row["first_payment_at"]

    if pd.isna(first_commit_at):
        return "matched_but_no_commit_time"

    if first_commit_at < first_payment_at:
        return "pre_existing_contributor"

    return "started_after_payment"


def add_timing_columns(df_matched_payees):
    df = df_matched_payees.copy()

    df["days_from_first_commit_to_first_payment"] = (
        df["first_payment_at"] - df["first_commit_at"]
    ).dt.total_seconds() / (60 * 60 * 24)

    df["developer_timing_type"] = df.apply(classify_timing, axis=1)

    df["first_commit_after_first_payment"] = (
        df["first_commit_at"] >= df["first_payment_at"]
    )

    return df


def summarize_matching(df_first_payments, df_matched_payees):
    total_project_payees = df_first_payments[
        [
            PROJECT_COL,
            "to_account_slug",
        ]
    ].drop_duplicates()

    matched_project_payees = df_matched_payees[
        [
            PROJECT_COL,
            "to_account_slug",
        ]
    ].drop_duplicates()

    matched = matched_project_payees.merge(
        total_project_payees,
        on=[PROJECT_COL, "to_account_slug"],
        how="inner",
    )

    df_summary = pd.DataFrame(
        [
            {
                "target": "INDIVIDUAL project-payee pairs",
                "total_project_payees": len(total_project_payees),
                "matched_project_payees": len(matched),
                "unmatched_project_payees": len(total_project_payees) - len(matched),
                "match_rate": (
                    np.nan
                    if len(total_project_payees) == 0
                    else len(matched) / len(total_project_payees)
                ),
            }
        ]
    )

    print("\n===== Matching summary =====")
    print(df_summary.to_string(index=False))

    df_summary.to_csv(OUTPUT_MATCH_SUMMARY_CSV, index=False)
    print(f"Saved: {OUTPUT_MATCH_SUMMARY_CSV}")

    return df_summary


def summarize_timing(df_detail):
    summary = (
        df_detail
        .groupby("developer_timing_type", dropna=False)
        .agg(
            n_project_payees=("developer_timing_type", "count"),
            n_projects=(PROJECT_COL, "nunique"),
            n_payees=("to_account_slug", "nunique"),
            median_days_from_first_commit_to_first_payment=(
                "days_from_first_commit_to_first_payment",
                "median",
            ),
            mean_days_from_first_commit_to_first_payment=(
                "days_from_first_commit_to_first_payment",
                "mean",
            ),
            q1_days_from_first_commit_to_first_payment=(
                "days_from_first_commit_to_first_payment",
                lambda s: s.quantile(0.25),
            ),
            q3_days_from_first_commit_to_first_payment=(
                "days_from_first_commit_to_first_payment",
                lambda s: s.quantile(0.75),
            ),
            median_total_commits=("total_commits", "median"),
            mean_total_commits=("total_commits", "mean"),
            median_num_development_payments=("num_development_payments", "median"),
            mean_num_development_payments=("num_development_payments", "mean"),
            median_total_development_payment_amount=(
                "total_development_payment_amount",
                "median",
            ),
            mean_total_development_payment_amount=(
                "total_development_payment_amount",
                "mean",
            ),
        )
        .reset_index()
    )

    total = len(df_detail)
    summary["ratio"] = summary["n_project_payees"] / total if total else np.nan

    summary = summary.sort_values(
        "developer_timing_type",
        ascending=True,
    ).reset_index(drop=True)

    return summary


def print_key_summary(df_detail, df_summary):
    print("\n===== Detail rows =====")
    print("Project-payee rows:", len(df_detail))
    print("Projects:", df_detail[PROJECT_COL].nunique())
    print("Payees:", df_detail["to_account_slug"].nunique())

    print("\n===== Timing summary =====")
    display_cols = [
        "developer_timing_type",
        "n_project_payees",
        "ratio",
        "n_projects",
        "n_payees",
        "median_days_from_first_commit_to_first_payment",
        "q1_days_from_first_commit_to_first_payment",
        "q3_days_from_first_commit_to_first_payment",
        "median_total_commits",
    ]
    print(df_summary[display_cols].to_string(index=False))

    n_total = len(df_detail)
    n_pre_existing = (
        df_detail["developer_timing_type"] == "pre_existing_contributor"
    ).sum()
    n_started_after = (
        df_detail["developer_timing_type"] == "started_after_payment"
    ).sum()

    print("\n===== Main result =====")
    print(f"Matched individual project-payees: {n_total}")
    print(
        "Pre-existing contributors:",
        n_pre_existing,
        f"({n_pre_existing / n_total:.3%})" if n_total else "",
    )
    print(
        "Started after payment:",
        n_started_after,
        f"({n_started_after / n_total:.3%})" if n_total else "",
    )

    if n_total:
        print(
            "Median days from first commit to first payment:",
            df_detail["days_from_first_commit_to_first_payment"].median(),
        )


def save_timing_type_bar(df_summary):
    fig, ax = plt.subplots(figsize=(9, 5))

    ax.bar(
        df_summary["developer_timing_type"],
        df_summary["n_project_payees"],
    )

    ax.set_xlabel("Developer timing type")
    ax.set_ylabel("Number of project-payee pairs")
    ax.set_title("Timing of first commit relative to first development payment")
    ax.tick_params(axis="x", rotation=20)
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(OUTPUT_TIMING_TYPE_BAR_PNG, dpi=300)
    plt.show()

    print(f"Saved: {OUTPUT_TIMING_TYPE_BAR_PNG}")


def save_days_histogram(df_detail):
    values = df_detail["days_from_first_commit_to_first_payment"].dropna()

    if values.empty:
        print("Skipping histogram because there are no timing values.")
        return

    lower = values.quantile(0.01)
    upper = values.quantile(0.99)
    values_clipped = values[(values >= lower) & (values <= upper)]

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.hist(values_clipped, bins=50)
    ax.axvline(x=0, linestyle="--", linewidth=1)

    ax.set_xlabel("Days from first commit to first payment")
    ax.set_ylabel("Number of project-payee pairs")
    ax.set_title(
        "Distribution of timing difference between first commit and first payment"
    )
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(OUTPUT_TIMING_HIST_PNG, dpi=300)
    plt.show()

    print(f"Saved: {OUTPUT_TIMING_HIST_PNG}")


def main():
    engine = database_engine()

    df_collectives, df_payments, df_commits = load_data(engine)

    df_project_commits = build_project_commit_base(
        df_collectives,
        df_commits,
    )

    df_first_payments = build_first_development_payments(df_payments)

    df_matched_payees, df_matches_raw = match_payees_to_commits(
        df_first_payments,
        df_project_commits,
    )

    if df_matched_payees.empty:
        print("No matched payees. Stop analysis.")
        return

    summarize_matching(df_first_payments, df_matched_payees)

    df_detail = add_timing_columns(df_matched_payees)
    df_summary = summarize_timing(df_detail)

    print_key_summary(df_detail, df_summary)

    df_detail.to_csv(OUTPUT_DETAIL_CSV, index=False)
    df_summary.to_csv(OUTPUT_SUMMARY_CSV, index=False)

    print(f"\nSaved: {OUTPUT_DETAIL_CSV}")
    print(f"Saved: {OUTPUT_SUMMARY_CSV}")

    save_timing_type_bar(df_summary)
    save_days_histogram(df_detail)


if __name__ == "__main__":
    main()