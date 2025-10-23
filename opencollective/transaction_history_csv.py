import psycopg2
from api import run_query
import time

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

# ===== プロジェクト一覧を取得 =====
cur.execute("SELECT slug, name FROM projects;")
projects = cur.fetchall()

for slug, name in projects:
    print(f"Fetching transactions for {slug} ...")

    limit = 100
    offset = 0
    while True:
        variables = {"slug": slug, "limit": limit, "offset": offset}
        result = run_query(query, variables)
        nodes = result["data"]["account"]["transactions"]["nodes"]
        if not nodes:
            break

        for tx in nodes:
            amount = tx.get("amount", {})
            from_acc = tx.get("fromAccount", {}) or {}
            to_acc = tx.get("toAccount", {}) or {}

            cur.execute("""
                INSERT INTO transactions VALUES (
                    %(id)s, %(project_slug)s, %(project_name)s,
                    %(type)s, %(description)s, %(created_at)s,
                    %(amount_value)s, %(amount_currency)s,
                    %(from_slug)s, %(from_name)s,
                    %(to_slug)s, %(to_name)s
                )
                ON CONFLICT (id) DO NOTHING;
            """, {
                "id": tx.get("id"),
                "project_slug": slug,
                "project_name": name,
                "type": tx.get("type"),
                "description": tx.get("description"),
                "created_at": tx.get("createdAt"),
                "amount_value": amount.get("value"),
                "amount_currency": amount.get("currency"),
                "from_slug": from_acc.get("slug"),
                "from_name": from_acc.get("name"),
                "to_slug": to_acc.get("slug"),
                "to_name": to_acc.get("name"),
            })

        conn.commit()
        print(f"✅ Inserted {len(nodes)} transactions for {slug}")
        offset += limit
        time.sleep(0.5)

cur.close()
conn.close()
print("🎉 All transactions collected!")
