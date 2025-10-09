import psycopg2
from api import run_query
import time

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
    password="password"     # ← あなたのパスワード
)
cur = conn.cursor()

# ===== ページネーション設定 =====
limit = 100
offset = 0
total = 5547

# ===== データ収集ループ =====
while offset < total:
    print(f"Fetching projects {offset} ~ {offset + limit - 1} ...")
    variables = {"limit": limit, "offset": offset}
    result = run_query(query, variables)

    # 取得データ
    nodes = result["data"]["accounts"]["nodes"]
    print(f"  → {len(nodes)} records fetched")

    for node in nodes:
        stats = node.get("stats", {})
        balance = stats.get("balance", {})
        total_recv = stats.get("totalAmountReceived", {})
        total_spent = stats.get("totalAmountSpent", {})
        yearly = stats.get("yearlyBudget", {})
        monthly_spending = stats.get("monthlySpending", {})
        total_paid_expenses = stats.get("totalPaidExpenses", {})
        managed_amount = stats.get("managedAmount", {}) or {}
        contributors_count = stats.get("contributorsCount")
        contributions_count = stats.get("contributionsCount")

        cur.execute("""
            INSERT INTO projects VALUES (
                %(id)s, %(slug)s, %(name)s, %(type)s,
                %(created_at)s, %(is_active)s,
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
        """, {
            "id": node.get("id"),
            "slug": node.get("slug"),
            "name": node.get("name"),
            "type": node.get("type"),
            "created_at": node.get("createdAt"),
            "is_active": node.get("isActive"),
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
        })

    conn.commit()
    print(f"✅ Inserted {len(nodes)} records (offset={offset})")

    offset += limit
    time.sleep(1)  # API負荷を避けるため1秒待機

# ===== 終了処理 =====
cur.close()
conn.close()

print("🎉 All projects inserted successfully!")
