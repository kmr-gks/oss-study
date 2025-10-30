import psycopg2
import api
import pandas as pd
import matplotlib.pyplot as plt

# --- DB接続情報 ---
conn = psycopg2.connect(
    dbname="opencollective",
    user="postgres",
    password=api.load_sql_password_from_credentials(),
    host="localhost",
    port=5432
)

# --- SQL実行 ---
query = """
SELECT DATE(created_at) AS date, SUM(amount_value) AS total_amount
FROM transactions
WHERE project_slug = 'legal-fees' AND type = 'CREDIT'
GROUP BY DATE(created_at)
ORDER BY DATE(created_at);
"""
df = pd.read_sql(query, conn)
conn.close()

# --- データ確認 ---
print(df.head())
print("データ件数:", len(df))

# --- グラフ描画 ---
if not df.empty:
    median_value = df["total_amount"].median()

    plt.figure(figsize=(10,5))
    plt.plot(df["date"], df["total_amount"], marker="o", label="Daily received amount")
    plt.axhline(y=median_value, color='red', linestyle='--', label=f"Median = {median_value:.2f}")
    plt.title("Daily Funding Received by legal-fees")
    plt.xlabel("Date")
    plt.ylabel("Amount")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()
else:
    print("⚠️ データが存在しません。project_slug または type を確認してください。")
