import csv
import psycopg2
from psycopg2.extras import execute_values
import api

conn = psycopg2.connect(
    dbname="opencollective",
    user="postgres",
    password=api.load_sql_password_from_credentials(),
    host="localhost",
    port=5432,
)

csv_files = [
    "predictions_2nd_all_devornot_1.csv",
    "predictions_2nd_all_devornot_2.csv",
    "predictions_2nd_all_devornot_3.csv",
    "predictions_2nd_all_devornot_4.csv",
    "predictions_2nd_all_devornot_5.csv",
]

try:
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE public.collective_transactions
                ADD COLUMN IF NOT EXISTS is_development boolean;

                CREATE TEMP TABLE preds (
                    run_no integer,
                    idx integer,
                    predicted_label text,
                    confidence numeric
                ) ON COMMIT DROP;
            """)

            rows = []

            for run_no, path in enumerate(csv_files, start=1):
                with open(path, encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        rows.append((
                            run_no,
                            int(r["index"]),
                            r["predicted_label"],
                            float(r["confidence"]),
                        ))

            execute_values(
                cur,
                """
                INSERT INTO preds (
                    run_no,
                    idx,
                    predicted_label,
                    confidence
                )
                VALUES %s
                """,
                rows,
            )

            cur.execute("""
                UPDATE public.collective_transactions
                SET is_development = NULL;

                WITH expense_rows AS (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (ORDER BY id) - 1 AS idx
                    FROM public.collective_transactions
                    WHERE kind = 'EXPENSE'
                ),
                agg AS (
                    SELECT
                        idx,
                        COUNT(*) FILTER (
                            WHERE predicted_label = 'development'
                              AND confidence >= 0.9
                        ) AS dev_count,
                        COUNT(*) AS total_count
                    FROM preds
                    GROUP BY idx
                )
                UPDATE public.collective_transactions ct
                SET is_development = (
                    agg.dev_count = 5
                    AND agg.total_count = 5
                )
                FROM expense_rows er
                JOIN agg ON er.idx = agg.idx
                WHERE ct.id = er.id;
            """)

    print("Done.")

finally:
    conn.close()