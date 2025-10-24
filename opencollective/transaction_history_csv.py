import psycopg2
from api import run_query
import time
import datetime
import csv
import os

# ===== GraphQLクエリ =====
query = """
query ($slug: String!, $limit: Int!, $offset: Int!) {
  account(slug: $slug) {
    name
    slug
    transactions(limit: $limit, offset: $offset) {
      nodes {
        id
        type
        description
        createdAt
        amount { value currency }
        fromAccount { slug name }
        toAccount { slug name }
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
    password="password"
)
cur = conn.cursor()

# ===== CSV設定 =====
csv_filename = "transactions_data.csv"
file_exists = os.path.isfile(csv_filename)

csv_fields = [
    "id", "project_slug", "project_name",
    "type", "description", "created_at",
    "amount_value", "amount_currency",
    "from_account_slug", "from_account_name",
    "to_account_slug", "to_account_name"
]

csv_file = open(csv_filename, mode="a", newline="", encoding="utf-8")
csv_writer = csv.DictWriter(csv_file, fieldnames=csv_fields)

# ファイルが存在しない場合のみヘッダーを書き込む
if not file_exists:
    csv_writer.writeheader()

# ===== プロジェクト一覧を取得 =====
cur.execute("SELECT slug, name FROM projects;")
projects = cur.fetchall()

for slug, name in projects:
    print(f"{datetime.datetime.now()}Fetching transactions for {slug} ...")

    limit = 100
    offset = 0
    while True:
        variables = {"slug": slug, "limit": limit, "offset": offset}
        result = run_query(query, variables)
        account_data = result.get("data", {}).get("account")
        if not account_data:
            break

        nodes = account_data["transactions"]["nodes"]
        if not nodes:
            break

        for tx in nodes:
            amount = tx.get("amount", {}) or {}
            from_acc = tx.get("fromAccount", {}) or {}
            to_acc = tx.get("toAccount", {}) or {}

            record = {
                "id": tx.get("id"),
                "project_slug": slug,
                "project_name": name,
                "type": tx.get("type"),
                "description": tx.get("description"),
                "created_at": tx.get("createdAt"),
                "amount_value": amount.get("value"),
                "amount_currency": amount.get("currency"),
                "from_account_slug": from_acc.get("slug"),
                "from_account_name": from_acc.get("name"),
                "to_account_slug": to_acc.get("slug"),
                "to_account_name": to_acc.get("name"),
            }

            # === SQL挿入 ===
            cur.execute("""
                INSERT INTO transactions VALUES (
                    %(id)s, %(project_slug)s, %(project_name)s,
                    %(type)s, %(description)s, %(created_at)s,
                    %(amount_value)s, %(amount_currency)s,
                    %(from_account_slug)s, %(from_account_name)s,
                    %(to_account_slug)s, %(to_account_name)s
                )
                ON CONFLICT (id) DO NOTHING;
            """, record)

            # === CSVにも書き込み ===
            csv_writer.writerow(record)

        conn.commit()
        print(f"Inserted {len(nodes)} transactions for {slug} (offset={offset})")
        offset += limit
        time.sleep(0.5)  # API負荷対策

# ===== 終了処理 =====
csv_file.close()
cur.close()
conn.close()
print("🎉 All transactions inserted into DB and saved to CSV!")
