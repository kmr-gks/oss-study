import api
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sqlalchemy import create_engine


PROJECT_COL = "project_slug"


ANALYSIS_CONFIGS = [
    {
        "analysis_label": "individual_development_payment",
        "description": "When an individual receives money for only development purposes",
        "where_extra": "AND is_development = true",
    },
    {
        "analysis_label": "individual_any_payment",
        "description": "When an individual receives any payment",
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


def make_dev_payments_sql(where_extra):
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


def output_paths(analysis_label):
    prefix = f"rq1_{analysis_label}"
    return {
        "detail_csv": f"{prefix}_first_payment_vs_first_commit_detail.csv",
        "summary_csv": f"{prefix}_first_payment_vs_first_commit_summary.csv",
        "match_summary_csv": f"{prefix}_matching_summary.csv",
        "timing_bar_png": f"{prefix}_developer_timing_type_bar.png",
        "days_hist_png": f"{prefix}_days_from_first_commit_to_first_payment_hist.png",
    }


def database_engine():
    password = api.load_sql_password_from_credentials()
    return create_engine(
        f"postgresql+psycopg2://postgres:{password}@localhost:5432/opencollective"
    )


def normalize_name(value):
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


def load_common_data(engine):
    df_collectives = pd.read_sql(COLLECTIVES_SQL, engine)
    df_commits = pd.read_sql(COMMIT_HISTORY_SQL, engine)

    df_collectives["created_at"] = pd.to_datetime(
        df_collectives["created_at"],
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

    df_commits["author_name_norm"] = df_commits["author_name"].map(normalize_name)

    print("\n===== Loaded common data =====")
    print("Collectives:", len(df_collectives))
    print("Commit rows:", len(df_commits))

    return df_collectives, df_commits


def load_payments(engine, where_extra):
    df_payments = pd.read_sql(make_dev_payments_sql(where_extra), engine)

    df_payments["payment_created_at"] = pd.to_datetime(
        df_payments["payment_created_at"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

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

    return df_payments


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


def build_first_payments(df_payments):
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
            num_payments=("transaction_id", "count"),
            total_payment_amount=("amount_abs", "sum"),
            num_development_labeled_payments=("is_development", lambda s: (s == True).sum()),
            num_non_development_labeled_payments=("is_development", lambda s: (s == False).sum()),
        )
        .reset_index()
    )

    print("\n===== Payment base =====")
    print("Payment rows:", len(df_payments))
    print("Project-payee pairs:", len(df_first_payments))
    print("Projects with payments:", df_first_payments[PROJECT_COL].nunique())
    print("Payees with payments:", df_first_payments["to_account_slug"].nunique())

    return df_first_payments


def build_commit_authors(df_project_commits):
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
        "num_payments",
        "total_payment_amount",
        "num_development_labeled_payments",
        "num_non_development_labeled_payments",
    ]

    return (
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


def match_payees_to_commits(df_first_payments, df_project_commits):
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
        "num_payments",
        "total_payment_amount",
        "num_development_labeled_payments",
        "num_non_development_labeled_payments",
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
    print(
        "Matched commit authors:",
        df_matches_raw[["author_name", "author_email"]]
        .drop_duplicates()
        .shape[0],
    )
    print("\nMatch method distribution:")
    print(df_matches_raw["match_method"].value_counts().to_string())

    df_matched_payees = aggregate_matches_to_project_payee(df_matches_raw)

    return df_matched_payees, df_matches_raw


def classify_timing(row):
    if pd.isna(row["first_commit_at"]):
        return "matched_but_no_commit_time"

    if row["first_commit_at"] < row["first_payment_at"]:
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


def summarize_matching(df_first_payments, df_matched_payees, paths):
    total_project_payees = df_first_payments[
        [PROJECT_COL, "to_account_slug"]
    ].drop_duplicates()

    matched_project_payees = df_matched_payees[
        [PROJECT_COL, "to_account_slug"]
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

    df_summary.to_csv(paths["match_summary_csv"], index=False)
    print(f"Saved: {paths['match_summary_csv']}")

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
            median_num_payments=("num_payments", "median"),
            mean_num_payments=("num_payments", "mean"),
            median_total_payment_amount=("total_payment_amount", "median"),
            mean_total_payment_amount=("total_payment_amount", "mean"),
        )
        .reset_index()
    )

    total = len(df_detail)
    summary["ratio"] = summary["n_project_payees"] / total if total else np.nan

    return summary.sort_values("developer_timing_type").reset_index(drop=True)


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


def save_timing_type_bar(df_summary, paths, description):
    fig, ax = plt.subplots(figsize=(9, 5))

    ax.bar(
        df_summary["developer_timing_type"],
        df_summary["n_project_payees"],
    )

    ax.set_xlabel("Developer timing type")
    ax.set_ylabel("Number of project-payee pairs")
    ax.set_title(f"Timing of first commit relative to first payment\n{description}")
    ax.tick_params(axis="x", rotation=20)
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(paths["timing_bar_png"], dpi=300)
    plt.close(fig)

    print(f"Saved: {paths['timing_bar_png']}")


def save_days_histogram(df_detail, paths, description):
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
        "Distribution of timing difference between first commit and first payment\n"
        f"{description}"
    )
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(paths["days_hist_png"], dpi=300)
    plt.close(fig)

    print(f"Saved: {paths['days_hist_png']}")


def run_analysis(config, engine, df_project_commits):
    analysis_label = config["analysis_label"]
    description = config["description"]
    where_extra = config["where_extra"]
    paths = output_paths(analysis_label)

    print("\n\n" + "=" * 80)
    print(f"===== Analysis: {analysis_label} =====")
    print(f"===== Meaning: {description} =====")
    print("=" * 80)

    df_payments = load_payments(engine, where_extra)

    print("\n===== Loaded payments =====")
    print("Payment rows:", len(df_payments))
    print("Projects:", df_payments[PROJECT_COL].nunique())
    print("Payees:", df_payments["to_account_slug"].nunique())

    if "is_development" in df_payments.columns:
        print("\n===== is_development distribution in target payments =====")
        print(df_payments["is_development"].value_counts(dropna=False).to_string())

    df_first_payments = build_first_payments(df_payments)

    df_matched_payees, df_matches_raw = match_payees_to_commits(
        df_first_payments,
        df_project_commits,
    )

    if df_matched_payees.empty:
        print("No matched payees. Stop this analysis.")
        return None

    summarize_matching(df_first_payments, df_matched_payees, paths)

    df_detail = add_timing_columns(df_matched_payees)
    df_detail.insert(0, "analysis_label", analysis_label)
    df_detail.insert(1, "analysis_description", description)

    df_summary = summarize_timing(df_detail)
    df_summary.insert(0, "analysis_label", analysis_label)
    df_summary.insert(1, "analysis_description", description)

    print_key_summary(df_detail, df_summary)

    df_detail.to_csv(paths["detail_csv"], index=False)
    df_summary.to_csv(paths["summary_csv"], index=False)

    print(f"\nSaved: {paths['detail_csv']}")
    print(f"Saved: {paths['summary_csv']}")

    save_timing_type_bar(df_summary, paths, description)
    save_days_histogram(df_detail, paths, description)

    return {
        "analysis_label": analysis_label,
        "description": description,
        "detail": df_detail,
        "summary": df_summary,
    }


def save_combined_summary(results):
    summaries = [
        result["summary"]
        for result in results
        if result is not None and result.get("summary") is not None
    ]

    if not summaries:
        return

    df_combined_summary = pd.concat(summaries, ignore_index=True)
    output_path = "rq1_combined_individual_payment_timing_summary.csv"
    df_combined_summary.to_csv(output_path, index=False)

    print("\n===== Combined summary =====")
    print(
        df_combined_summary[
            [
                "analysis_label",
                "developer_timing_type",
                "n_project_payees",
                "ratio",
                "n_projects",
                "n_payees",
                "median_days_from_first_commit_to_first_payment",
            ]
        ].to_string(index=False)
    )
    print(f"Saved: {output_path}")


def main():
    engine = database_engine()

    df_collectives, df_commits = load_common_data(engine)

    df_project_commits = build_project_commit_base(
        df_collectives,
        df_commits,
    )

    results = []

    for config in ANALYSIS_CONFIGS:
        result = run_analysis(
            config=config,
            engine=engine,
            df_project_commits=df_project_commits,
        )
        results.append(result)

    save_combined_summary(results)


if __name__ == "__main__":
    main()