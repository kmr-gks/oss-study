import psycopg2
import api
import json
import datetime
import csv
import os
import time

# ===== GraphQLクエリ =====
query = """
query ($limit: Int!, $offset: Int!) {
  accounts(host: { slug: "opensource" }, limit: $limit, offset: $offset) {
    totalCount
    nodes {
      id
      slug
      name
      type
      createdAt
      isActive
      description
      website
      githubHandle
      twitterHandle
      socialLinks { type url }
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

# ===== PostgreSQL接続 =====
conn = psycopg2.connect(
    host="localhost",
    dbname="opencollective",
    user="postgres",
    password=api.load_sql_password_from_credentials()
)
cur = conn.cursor()

# ===== CSV設定 =====
timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
csv_filename = f"outputs/collectives_{timestamp}.csv"
os.makedirs("outputs", exist_ok=True)

csv_fields = [
    "id", "slug", "name", "type", "created_at", "is_active", "description",
    "website", "github_handle", "twitter_handle", "social_links",
    "balance_value", "balance_currency",
    "total_received_value", "total_received_currency",
    "total_spent_value", "total_spent_currency",
    "yearly_budget_value", "yearly_budget_currency",
    "host_slug"
]

csv_file = open(csv_filename, mode="w", newline="", encoding="utf-8")
csv_writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
csv_writer.writeheader()

# ===== ページネーション設定 =====
limit = 100
offset = 0
total = 10000  # 仮の上限（実際の数より多めに）

# ===== ループ開始 =====
while True:
    print(f"Fetching collectives {offset} ~ {offset + limit - 1} ...")
    variables = {"limit": limit, "offset": offset}
    result = api.run_query(query, variables)
    print(f"total: {account_data["totalCount"]}")

    account_data = result.get("data", {}).get("accounts")
    if not account_data:
        print("No account data found — stopping.")
        break

    nodes = account_data["nodes"]
    if not nodes:
        print("No more nodes — done.")
        break

    print(f"  → {len(nodes)} records fetched")

    for node in nodes:
        stats = node.get("stats", {}) or {}
        balance = stats.get("balance", {}) or {}
        total_recv = stats.get("totalAmountReceived", {}) or {}
        total_spent = stats.get("totalAmountSpent", {}) or {}
        yearly = stats.get("yearlyBudget", {}) or {}

        record = {
            "id": node.get("id"),
            "slug": node.get("slug"),
            "name": node.get("name"),
            "type": node.get("type"),
            "created_at": node.get("createdAt"),
            "is_active": node.get("isActive"),
            "description": node.get("description"),
            "website": node.get("website"),
            "github_handle": node.get("githubHandle"),
            "twitter_handle": node.get("twitterHandle"),
            "social_links": json.dumps(node.get("socialLinks", []), ensure_ascii=False),
            "balance_value": balance.get("value"),
            "balance_currency": balance.get("currency"),
            "total_received_value": total_recv.get("value"),
            "total_received_currency": total_recv.get("currency"),
            "total_spent_value": total_spent.get("value"),
            "total_spent_currency": total_spent.get("currency"),
            "yearly_budget_value": yearly.get("value"),
            "yearly_budget_currency": yearly.get("currency"),
            "host_slug": "opensource"
        }

        # === SQLへ保存 ===
        cur.execute("""
            INSERT INTO collectives (
                id, slug, name, type, created_at, is_active, description,
                website, github_handle, twitter_handle, social_links,
                balance_value, balance_currency,
                total_received_value, total_received_currency,
                total_spent_value, total_spent_currency,
                yearly_budget_value, yearly_budget_currency,
                host_slug
            )
            VALUES (
                %(id)s, %(slug)s, %(name)s, %(type)s, %(created_at)s, %(is_active)s, %(description)s,
                %(website)s, %(github_handle)s, %(twitter_handle)s, %(social_links)s,
                %(balance_value)s, %(balance_currency)s,
                %(total_received_value)s, %(total_received_currency)s,
                %(total_spent_value)s, %(total_spent_currency)s,
                %(yearly_budget_value)s, %(yearly_budget_currency)s,
                %(host_slug)s
            )
            ON CONFLICT (id) DO UPDATE SET
                slug = EXCLUDED.slug,
                name = EXCLUDED.name,
                type = EXCLUDED.type,
                created_at = EXCLUDED.created_at,
                is_active = EXCLUDED.is_active,
                description = EXCLUDED.description,
                website = EXCLUDED.website,
                github_handle = EXCLUDED.github_handle,
                twitter_handle = EXCLUDED.twitter_handle,
                social_links = EXCLUDED.social_links,
                balance_value = EXCLUDED.balance_value,
                balance_currency = EXCLUDED.balance_currency,
                total_received_value = EXCLUDED.total_received_value,
                total_received_currency = EXCLUDED.total_received_currency,
                total_spent_value = EXCLUDED.total_spent_value,
                total_spent_currency = EXCLUDED.total_spent_currency,
                yearly_budget_value = EXCLUDED.yearly_budget_value,
                yearly_budget_currency = EXCLUDED.yearly_budget_currency,
                host_slug = EXCLUDED.host_slug;
        """, record)

        # === CSVにも書き込み ===
        csv_writer.writerow(record)

    conn.commit()
    print(f"✅ Inserted and saved {len(nodes)} records (offset={offset})")

    offset += limit
    time.sleep(1)  # API負荷を抑える

# ===== 終了処理 =====
csv_file.close()
cur.close()
conn.close()
print(f"🎉 All collectives saved to PostgreSQL and {csv_filename}")
