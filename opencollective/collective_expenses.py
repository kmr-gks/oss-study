import psycopg2
import api
import csv
import os
import datetime
import json
import traceback

# ===== ログ設定 =====
os.makedirs("logs", exist_ok=True)
log_filename = datetime.datetime.now().strftime("logs/collective_expenses_%Y-%m-%d_%H-%M-%S.log")

def log(msg):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_filename, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(msg)

# ===== GraphQLクエリ =====
query = """
query ($slug: String!, $limit: Int!, $offset: Int!) {
  account(slug: $slug) {
    name
    slug
    expenses(limit: $limit, offset: $offset) {
      nodes {
        id
        type
        description
        status
        createdAt
        incurredAt
        amountV2 { valueInCents value currency }
        tags
        payee { slug name }
      }
    }
  }
}
"""

# ===== PostgreSQL接続 =====
conn = psycopg2.connect(
    host="localhost",
    dbname="opencollective",
    user="postgres",
    password=api.load_sql_password_from_credentials()
)
cur = conn.cursor()

# ===== CSV準備 =====
os.makedirs("outputs", exist_ok=True)
csv_filename = datetime.datetime.now().strftime("outputs/collective_expenses_%Y-%m-%d_%H-%M-%S.csv")
csv_fields = [
    "id", "project_slug", "project_name", "type", "description",
    "amount_value", "amount_currency", "created_at", "incurred_at",
    "tags", "payee_name", "payee_slug", "status"
]

with open(csv_filename, mode="w", newline="", encoding="utf-8") as csv_file:
    writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
    writer.writeheader()

    # ===== プロジェクト一覧を取得 =====
    cur.execute("SELECT slug, name FROM collectives;")
    projects = cur.fetchall()
    log(f"✅ Loaded {len(projects)} collectives from database")

    for slug, name in projects:
        try:
            log(f"Fetching expenses for {slug} ...")
            limit = 100
            offset = 0

            while True:
                variables = {"slug": slug, "limit": limit, "offset": offset}
                result = api.run_query(query, variables)

                account_data = result.get("data", {}).get("account")
                if not account_data:
                    break

                expenses = account_data["expenses"]["nodes"]
                if not expenses:
                    break

                for e in expenses:
                    amount = e.get("amountV2", {}) or {}
                    payee = e.get("payee", {}) or {}
                    tags_json = json.dumps(e.get("tags", []), ensure_ascii=False)

                    record = {
                        "id": e.get("id"),
                        "project_slug": slug,
                        "project_name": name,
                        "type": e.get("type"),
                        "description": e.get("description"),
                        "amount_value": amount.get("value"),
                        "amount_currency": amount.get("currency"),
                        "created_at": e.get("createdAt"),
                        "incurred_at": e.get("incurredAt"),
                        "tags": tags_json,
                        "payee_name": payee.get("name"),
                        "payee_slug": payee.get("slug"),
                        "status": e.get("status"),
                    }

                    # SQL挿入
                    cur.execute("""
                        INSERT INTO collective_expenses VALUES (
                            %(id)s, %(project_slug)s, %(project_name)s,
                            %(type)s, %(description)s,
                            %(amount_value)s, %(amount_currency)s,
                            %(created_at)s, %(incurred_at)s,
                            %(tags)s, %(payee_name)s, %(payee_slug)s, %(status)s
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            project_slug = EXCLUDED.project_slug,
                            project_name = EXCLUDED.project_name,
                            type = EXCLUDED.type,
                            description = EXCLUDED.description,
                            amount_value = EXCLUDED.amount_value,
                            amount_currency = EXCLUDED.amount_currency,
                            created_at = EXCLUDED.created_at,
                            incurred_at = EXCLUDED.incurred_at,
                            tags = EXCLUDED.tags,
                            payee_name = EXCLUDED.payee_name,
                            payee_slug = EXCLUDED.payee_slug,
                            status = EXCLUDED.status;
                    """, record)

                    # CSVにも書き込み
                    writer.writerow(record)

                conn.commit()
                log(f"✅ Inserted {len(expenses)} expenses (slug={slug}, offset={offset})")
                offset += limit

        except Exception as e:
            log(f"❌ Error processing {slug}: {e}")
            log(traceback.format_exc())

cur.close()
conn.close()
log("🎉 All expenses inserted successfully and saved to CSV.")
