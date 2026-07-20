import pandas as pd
from duckdb_util import database_engine

WINDOW_MONTHS = 12


def normalize_name(value):
    if pd.isna(value):
        return ""

    value = str(value).lower().strip()

    for char in [
        " ", "\t", "\n", "\r", "-", "_", ".", ",",
        "'", '"', "`", "(", ")", "[", "]", "{", "}",
        "/", "\\",
    ]:
        value = value.replace(char, "")

    return value


engine = database_engine()

try:
    collectives = pd.read_sql(
        """
        SELECT slug AS project_slug, github_account
        FROM public.collectives
        WHERE github_account IS NOT NULL
          AND github_account <> ''
        """,
        engine,
    )

    collectives = collectives[
        collectives["github_account"].str.contains("/", na=False)
    ].copy()

    collectives["repo_name"] = (
        collectives["github_account"]
        .astype(str)
        .str.strip()
        .str.replace("/", "-", regex=False)
    )

    payments = pd.read_sql(
        """
        SELECT
            project_slug,
            to_account_slug,
            to_account_name,
            created_at AS payment_created_at
        FROM public.collective_transactions
        WHERE kind = 'EXPENSE'
          AND to_account_type = 'INDIVIDUAL'
          AND is_development = true
          AND project_slug IS NOT NULL
          AND to_account_slug IS NOT NULL
          AND to_account_name IS NOT NULL
          AND created_at IS NOT NULL
        """,
        engine,
    )

    payments["payment_created_at"] = pd.to_datetime(
        payments["payment_created_at"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    payments["to_account_name_norm"] = (
        payments["to_account_name"].map(normalize_name)
    )
    payments["to_account_slug_norm"] = (
        payments["to_account_slug"].map(normalize_name)
    )

    first_payments = (
        payments
        .groupby(
            [
                "project_slug",
                "to_account_slug",
                "to_account_name",
                "to_account_name_norm",
                "to_account_slug_norm",
            ],
            as_index=False,
        )
        .agg(
            first_payment_at=("payment_created_at", "min")
        )
    )

    commits = pd.read_sql(
        """
        SELECT
            repo_name,
            commit_hash,
            author_name,
            commit_time
        FROM public.commit_history
        WHERE repo_name IS NOT NULL
          AND commit_hash IS NOT NULL
          AND author_name IS NOT NULL
          AND commit_time IS NOT NULL
        """,
        engine,
    )

    commits["commit_time"] = pd.to_datetime(
        commits["commit_time"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    commits["author_name_norm"] = (
        commits["author_name"].map(normalize_name)
    )

    project_commits = commits.merge(
        collectives[["project_slug", "repo_name"]],
        on="repo_name",
        how="inner",
    )

    commit_columns = [
        "project_slug",
        "commit_hash",
        "commit_time",
        "author_name_norm",
    ]

    name_matches = first_payments.merge(
        project_commits[commit_columns],
        left_on=[
            "project_slug",
            "to_account_name_norm",
        ],
        right_on=[
            "project_slug",
            "author_name_norm",
        ],
        how="inner",
    )

    slug_matches = first_payments.merge(
        project_commits[commit_columns],
        left_on=[
            "project_slug",
            "to_account_slug_norm",
        ],
        right_on=[
            "project_slug",
            "author_name_norm",
        ],
        how="inner",
    )

    matches = pd.concat(
        [name_matches, slug_matches],
        ignore_index=True,
    )

    matches = matches.drop_duplicates(
        subset=[
            "project_slug",
            "to_account_slug",
            "commit_hash",
        ]
    )

    matches["window_start"] = (
        matches["first_payment_at"]
        - pd.DateOffset(months=WINDOW_MONTHS)
    )
    matches["window_end"] = (
        matches["first_payment_at"]
        + pd.DateOffset(months=WINDOW_MONTHS)
    )

    matches["before_commit_hash"] = matches["commit_hash"].where(
        (matches["commit_time"] >= matches["window_start"])
        & (matches["commit_time"] < matches["first_payment_at"])
    )

    matches["after_commit_hash"] = matches["commit_hash"].where(
        (matches["commit_time"] >= matches["first_payment_at"])
        & (matches["commit_time"] < matches["window_end"])
    )

    counts = (
        matches
        .groupby(
            ["project_slug", "to_account_slug"],
            as_index=False,
        )
        .agg(
            commits_before=(
                "before_commit_hash",
                "nunique",
            ),
            commits_after=(
                "after_commit_hash",
                "nunique",
            ),
        )
    )

    def classify(row):
        before = row["commits_before"]
        after = row["commits_after"]

        if before == 0 and after == 0:
            return "No commits before or after payment"

        if before == 0 and after > 0:
            return "New contributor after payment"

        if after > before:
            return "Prior contributor, increased commits"

        return "Prior contributor, decreased or unchanged commits"

    counts["category"] = counts.apply(classify, axis=1)

    category_order = [
        "Prior contributor, increased commits",
        "Prior contributor, decreased or unchanged commits",
        "New contributor after payment",
        "No commits before or after payment",
    ]

    result = (
        counts["category"]
        .value_counts()
        .reindex(category_order, fill_value=0)
        .rename("Count")
        .reset_index()
        .rename(columns={"index": "Category"})
    )

    result["Percentage"] = (
        result["Count"] / result["Count"].sum() * 100
    )

    result.to_csv(
        "table_vi.csv",
        index=False,
        float_format="%.3f",
    )

finally:
    engine.dispose()
