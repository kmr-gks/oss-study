import psycopg2
import api
import datetime
import csv
import os
import traceback

# ===== ログ出力設定 =====
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_filename = os.path.join(log_dir, datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S.log"))

def log(message):
    """ログメッセージをファイルとコンソールに出力"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = f"[{timestamp}] {message}"
    print(text)
    with open(log_filename, "a", encoding="utf-8") as f:
        f.write(text + "\n")

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

try:
    # ===== PostgreSQL接続 =====
    conn = psycopg2.connect(
        host="localhost",
        dbname="opencollective",
        user="postgres",
        password=api.load_sql_password_from_credentials()
    )
    cur = conn.cursor()
    log("✅ PostgreSQL connected successfully.")

    # ===== CSV設定 =====
    csv_filename = datetime.datetime.now().strftime("transactions_data_%Y-%m-%d_%H-%M-%S.csv")
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
        log("🆕 CSV header written.")

    # ===== プロジェクト一覧を取得 =====
    cur.execute("SELECT slug, name FROM projects;")
    projects = cur.fetchall()
    log(f"📦 Loaded {len(projects)} projects from database.")

    for slug, name in projects:
        log(f"Fetching transactions for {slug} ...")

        limit = 100
        offset = 0
        while True:
            variables = {"slug": slug, "limit": limit, "offset": offset}
            try:
                result = api.run_query(query, variables)
            except Exception as e:
                log(f"❌ GraphQL query failed for {slug}: {e}")
                traceback.print_exc(file=open(log_filename, "a", encoding="utf-8"))
                break

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

                try:
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

                except Exception as e:
                    log(f"⚠️ DB insert failed for transaction {tx.get('id')}: {e}")
                    traceback.print_exc(file=open(log_filename, "a", encoding="utf-8"))

            conn.commit()
            log(f"✅ Inserted {len(nodes)} transactions for {slug} (offset={offset})")
            offset += limit

# ===== 終了処理 =====
    csv_file.close()
    cur.close()
    conn.close()
    log("🎉 All transactions inserted into DB and saved to CSV!")

except Exception as e:
    log(f"💥 Unexpected error: {e}")
    traceback.print_exc(file=open(log_filename, "a", encoding="utf-8"))
