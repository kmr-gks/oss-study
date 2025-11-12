import psycopg2
import api
import csv
import os
import datetime
import traceback

# ===== ログ設定 =====
os.makedirs("logs", exist_ok=True)
log_filename = datetime.datetime.now().strftime("logs/collective_transactions_%Y-%m-%d_%H-%M-%S.log")

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
    transactions(limit: $limit, offset: $offset) {
      totalCount
      nodes {
        id
        type
        kind
        description
        createdAt
        amount { value currency }
        fromAccount { slug name type }
        toAccount   { slug name type }
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
csv_filename = datetime.datetime.now().strftime("outputs/collective_transactions_%Y-%m-%d_%H-%M-%S.csv")
csv_fields = [
    "id", "project_slug", "project_name", "type", "kind", "description",
    "created_at", "amount_value", "amount_currency",
    "from_account_slug", "from_account_name", "from_account_type",
    "to_account_slug", "to_account_name", "to_account_type"
]

with open(csv_filename, mode="w", newline="", encoding="utf-8") as csv_file:
    writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
    writer.writeheader()

    # ===== プロジェクト一覧を取得 =====
    cur.execute("SELECT slug, name FROM projects;")
    projects = cur.fetchall()
    log(f"✅ Loaded {len(projects)} collectives from database")

    for slug, name in projects:
        try:
            log(f"Fetching transactions for {slug} ...")
            limit = 100
            offset = 0

            while True:
                variables = {"slug": slug, "limit": limit, "offset": offset}
                result = api.run_query(query, variables)

                account_data = result.get("data", {}).get("account")
                if not account_data:
                    break

                transactions = account_data["transactions"]["nodes"]
                if not transactions:
                    break

                for tx in transactions:
                    amount = tx.get("amount", {}) or {}
                    from_acc = tx.get("fromAccount", {}) or {}
                    to_acc = tx.get("toAccount", {}) or {}

                    record = {
                        "id": tx.get("id"),
                        "project_slug": slug,
                        "project_name": name,
                        "type": tx.get("type"),
                        "kind": tx.get("kind"),
                        "description": tx.get("description"),
                        "created_at": tx.get("createdAt"),
                        "amount_value": amount.get("value"),
                        "amount_currency": amount.get("currency"),
                        "from_account_slug": from_acc.get("slug"),
                        "from_account_name": from_acc.get("name"),
                        "from_account_type": from_acc.get("type"),
                        "to_account_slug": to_acc.get("slug"),
                        "to_account_name": to_acc.get("name"),
                        "to_account_type": to_acc.get("type"),
                    }

                    # SQL挿入
                    cur.execute("""
                        INSERT INTO collective_transactions VALUES (
                            %(id)s, %(project_slug)s, %(project_name)s,
                            %(type)s, %(kind)s, %(description)s,
                            %(created_at)s, %(amount_value)s, %(amount_currency)s,
                            %(from_account_slug)s, %(from_account_name)s, %(from_account_type)s,
                            %(to_account_slug)s, %(to_account_name)s, %(to_account_type)s
                        )
                        ON CONFLICT (id) DO NOTHING;
                    """, record)

                    # CSVにも保存
                    writer.writerow(record)

                conn.commit()
                log(f"✅ Inserted {len(transactions)} records (slug={slug}, offset={offset})")
                offset += limit

        except Exception as e:
            log(f"❌ Error processing {slug}: {e}")
            log(traceback.format_exc())

cur.close()
conn.close()
log("🎉 All transactions inserted successfully and saved to CSV.")
