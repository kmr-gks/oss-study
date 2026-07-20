import api
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(
    "postgresql+psycopg2://postgres:"
    f"{api.load_sql_password_from_credentials()}"
    "@localhost:5432/opencollective"
)

try:
    collectives = pd.read_sql(
        """
        SELECT
            *
        FROM public.collectives
        WHERE github_account IS NOT NULL
        """,
        engine,
    )

    transactions = pd.read_sql(
        """
        SELECT
            *
        FROM public.collective_transactions
        WHERE kind IN ('EXPENSE', 'CONTRIBUTION')
        """,
        engine,
    )

    commit_history = pd.read_sql(
        """
        SELECT
            *
        FROM public.commit_history
        WHERE repo_name IS NOT NULL
          AND commit_time IS NOT NULL
        """,
        engine,
    )

    github_issue_pr_items = pd.read_sql(
        """
        SELECT *
        FROM public.github_issue_pr_items
        """,
        engine,
    )



    collectives.to_parquet(
        "data/collectives.parquet",
        index=False,
        compression="zstd",
    )

    transactions.to_parquet(
        "data/collective_transactions.parquet",
        index=False,
        compression="zstd",
    )

    commit_history.to_parquet(
        "data/commit_history.parquet",
        index=False,
        compression="zstd",
    )

    github_issue_pr_items.to_parquet(
        "data/github_issue_pr_items.parquet",
        index=False,
        compression="zstd",
    )

finally:
    engine.dispose()

print("Export completed.")
