from pathlib import Path

from sqlalchemy import create_engine, event


ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"

PARQUET_TABLES = {
    "collectives": "collectives.parquet",
    "collective_transactions": "collective_transactions.parquet",
    "commit_history": "commit_history.parquet",
    "github_issue_pr_items": "github_issue_pr_items.parquet",
}


def _sql_path(path):
    return path.resolve().as_posix().replace("'", "''")


def database_engine(data_dir=DATA_DIR):
    data_dir = Path(data_dir).resolve()

    missing_files = [
        data_dir / file_name
        for file_name in PARQUET_TABLES.values()
        if not (data_dir / file_name).exists()
    ]

    if missing_files:
        missing_text = "\n".join(
            f"- {path}" for path in missing_files
        )
        raise FileNotFoundError(
            "Required Parquet files were not found:\n"
            f"{missing_text}"
        )

    engine = create_engine(
        "duckdb:///:memory:"
    )

    @event.listens_for(engine, "connect")
    def register_parquet_views(
        dbapi_connection,
        connection_record,
    ):
        cursor = dbapi_connection.cursor()

        cursor.execute(
            "CREATE SCHEMA IF NOT EXISTS public"
        )

        for table_name, file_name in PARQUET_TABLES.items():
            parquet_path = _sql_path(
                data_dir / file_name
            )

            cursor.execute(
                f"""
                CREATE OR REPLACE VIEW public.{table_name} AS
                SELECT *
                FROM read_parquet('{parquet_path}')
                """
            )

        cursor.close()

    return engine