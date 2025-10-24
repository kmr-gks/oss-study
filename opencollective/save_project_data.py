import psycopg2
import api
import time
import csv
import os

# ===== GraphQLクエリ =====
query = """
query ($limit: Int!, $offset: Int!) {
  accounts(type:[PROJECT], limit:$limit, offset:$offset) {
    nodes {
      id
      slug
      name
      type
      createdAt
      isActive
      stats {
        id
        balance { value currency }
        totalAmountReceived { value currency }
        totalAmountSpent { value currency }
        yearlyBudget { value currency }
        monthlySpending { value currency }
        totalPaidExpenses { value currency }
        managedAmount { value currency }
        contributorsCount
        contributionsCount
      }
    }
  }
}
"""

# ===== PostgreSQL接続 =====
conn = psycopg2.connect(
    host="localhost",
    dbname="opencollective",     # ← 作成したDB名
    user="postgres",             # ← あなたのPostgreSQLユーザー
    password=api.load_sql_password_from_credentials()
)
cur = conn.cursor()

# ===== CSV準備 =====
csv_filename = "projects_data.csv"
file_exists = os.path.isfile(csv_filename)

csv_fields = [
    "id", "slug", "name", "type", "created_at", "is_active", "stats_id",
    "balance_value", "balance_currency",
    "total_received_value", "total_received_currency",
    "total_spent_value", "total_spent_currency",
    "yearly_budget_value", "yearly_budget_currency",
    "monthly_spending_value", "monthly_spending_currency",
    "total_paid_expenses_value", "total_paid_expenses_currency",
    "managed_amount_value", "managed_amount_currency",
    "contributors_count", "contributions_count"
]

csv_file = open(csv_filename, mode="a", newline="", encoding="utf-8")
csv_writer = csv.DictWriter(csv_file, fieldnames=csv_fields)

# ファイルが存在しなければヘッダーを書き込む
if not file_exists:
    csv_writer.writeheader()

# ===== ページネーション設定 =====
limit = 100
offset = 0
total = 5547

# ===== データ収集ループ =====
while offset < total:
    print(f"Fetching projects {offset} ~ {offset + limit - 1} ...")
    variables = {"limit": limit, "offset": offset}
    result = api.run_query(query, variables)

    # 取得データ
    nodes = result["data"]["accounts"]["nodes"]
    print(f"  → {len(nodes)} records fetched")

    for node in nodes:
        stats = node.get("stats", {})
        stats_id = stats.get("id")
        balance = stats.get("balance", {})
        total_recv = stats.get("totalAmountReceived", {})
        total_spent = stats.get("totalAmountSpent", {})
        yearly = stats.get("yearlyBudget", {})
        monthly_spending = stats.get("monthlySpending", {})
        total_paid_expenses = stats.get("totalPaidExpenses", {})
        managed_amount = stats.get("managedAmount", {}) or {}
        contributors_count = stats.get("contributorsCount")
        contributions_count = stats.get("contributionsCount")
        record = {
            "id": node.get("id"),
            "slug": node.get("slug"),
            "name": node.get("name"),
            "type": node.get("type"),
            "created_at": node.get("createdAt"),
            "is_active": node.get("isActive"),
            "stats_id": stats_id,
            "balance_value": balance.get("value"),
            "balance_currency": balance.get("currency"),
            "total_received_value": total_recv.get("value"),
            "total_received_currency": total_recv.get("currency"),
            "total_spent_value": total_spent.get("value"),
            "total_spent_currency": total_spent.get("currency"),
            "yearly_budget_value": yearly.get("value"),
            "yearly_budget_currency": yearly.get("currency"),
            "monthly_spending_value": monthly_spending.get("value"),
            "monthly_spending_currency": monthly_spending.get("currency"),
            "total_paid_expenses_value": total_paid_expenses.get("value"),
            "total_paid_expenses_currency": total_paid_expenses.get("currency"),
            "managed_amount_value": managed_amount.get("value"),
            "managed_amount_currency": managed_amount.get("currency"),
            "contributors_count": contributors_count,
            "contributions_count": contributions_count,
        }

        # === SQLに挿入 ===
        cur.execute("""
            INSERT INTO projects VALUES (
                %(id)s, %(slug)s, %(name)s, %(type)s,
                %(created_at)s, %(is_active)s,
                %(stats_id)s,
                %(balance_value)s, %(balance_currency)s,
                %(total_received_value)s, %(total_received_currency)s,
                %(total_spent_value)s, %(total_spent_currency)s,
                %(yearly_budget_value)s, %(yearly_budget_currency)s,
                %(monthly_spending_value)s, %(monthly_spending_currency)s,
                %(total_paid_expenses_value)s, %(total_paid_expenses_currency)s,
                %(managed_amount_value)s, %(managed_amount_currency)s,
                %(contributors_count)s, %(contributions_count)s
            )
            ON CONFLICT (id) DO NOTHING;
        """, record)

        # === CSVに追記 ===
        csv_writer.writerow(record)

    conn.commit()
    print(f"✅ Inserted and saved {len(nodes)} records (offset={offset})")

    offset += limit
    time.sleep(1)  # API負荷を避けるため1秒待機

# ===== 終了処理 =====
csv_file.close()
cur.close()
conn.close()

print("🎉 All projects inserted successfully and saved to CSV!")
