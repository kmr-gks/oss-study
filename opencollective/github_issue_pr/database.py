from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
import api
import pandas as pd
from sqlalchemy import create_engine

from config import DB_NAME, ITEM_TABLE


def create_db_engine():
    return create_engine(
        "postgresql+psycopg2://"
        f"postgres:{api.load_sql_password_from_credentials()}"
        f"@localhost:5432/{DB_NAME}"
    )


def load_issue_pr_items(engine) -> pd.DataFrame:
    query = f"""
    SELECT
        collective_id,
        project_slug,
        project_name,
        repo_name,
        github_account,
        item_type,
        number,
        created_at,
        closed_at,
        merged_at,
        state,
        is_merged,
        labels,
        author_login,
        closed_by_login,
        merged_by_login,
        opencollective_created_at
    FROM {ITEM_TABLE}
    WHERE repo_name IS NOT NULL
      AND github_account IS NOT NULL
      AND opencollective_created_at IS NOT NULL
    """

    df = pd.read_sql(query, engine)

    datetime_columns = [
        "created_at",
        "closed_at",
        "merged_at",
        "opencollective_created_at",
    ]

    for column in datetime_columns:
        df[column] = pd.to_datetime(
            df[column],
            utc=True,
            errors="coerce",
        ).dt.tz_convert(None)

    df = df[
        df["opencollective_created_at"].notna()
    ].copy()

    return df


def build_project_table(df_items: pd.DataFrame) -> pd.DataFrame:
    """
    現在のテーブルから、取得済みプロジェクト一覧を作る。

    注意:
    Issue/PRが一度もないリポジトリはitemsテーブルに現れない。
    将来的には取得完了repoを記録するstatusテーブルを使う方がよい。
    """
    project_columns = [
        "collective_id",
        "project_slug",
        "project_name",
        "repo_name",
        "github_account",
        "opencollective_created_at",
    ]

    return (
        df_items[project_columns]
        .drop_duplicates()
        .reset_index(drop=True)
    )