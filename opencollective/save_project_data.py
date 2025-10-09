import psycopg2
from api import run_query
import json

# ====== GraphQLクエリ ======
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
      }
    }
  }
}
"""

# ====== GraphQLからデータ取得 ======
variables = {"limit": 3, "offset": 0}
result = run_query(query, variables)

# 結果をパース
node = result["data"]["accounts"]["nodes"][0]
stats = node.get("stats", {})
balance = stats.get("balance", {})
total_recv = stats.get("totalAmountReceived", {})
total_spent = stats.get("totalAmountSpent", {})
yearly = stats.get("yearlyBudget", {})

# ====== PostgreSQLへ接続 ======
conn = psycopg2.connect(
    host="localhost",
    dbname="opencollective",
    user="postgres",       # ←あなたのユーザー名に変更
    password="password"  # ←あなたのパスワードに変更
)
cur = conn.cursor()

# ====== データ挿入 ======
cur.execute("""
    INSERT INTO projects VALUES (
        %(id)s, %(slug)s, %(name)s, %(type)s,
        %(created_at)s, %(is_active)s,
        %(balance_value)s, %(balance_currency)s,
        %(total_received_value)s, %(total_received_currency)s,
        %(total_spent_value)s, %(total_spent_currency)s,
        %(yearly_budget_value)s, %(yearly_budget_currency)s
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
})

conn.commit()
cur.close()
conn.close()

print("✅ 1件のプロジェクトデータを挿入しました。")
