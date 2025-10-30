import api
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

project_slug = "legal-fees"

# --- DB接続情報 ---
engine= create_engine('postgresql+psycopg2://postgres:{}@localhost:5432/opencollective'.format(api.load_sql_password_from_credentials()))

# --- SQL実行 ---
query = f"""
SELECT DATE(created_at) AS date, SUM(amount_value) AS total_amount
FROM transactions
WHERE project_slug = '{project_slug}' AND type = 'CREDIT'
GROUP BY DATE(created_at)
ORDER BY DATE(created_at);
"""
df=pd.read_sql(query, engine)

# --- データ確認 ---
print(df.head())
print("データ件数:", len(df))

# --- グラフ描画 ---
if not df.empty:
    median_value = df["total_amount"].median()

    plt.figure(figsize=(10,5))
    plt.plot(df["date"], df["total_amount"], marker="o", label="Daily received amount")
    plt.axhline(y=median_value, color='red', linestyle='--', label=f"Median = {median_value:.2f}")
    plt.title("Daily Funding Received by {}".format(project_slug))
    plt.xlabel("Date")
    plt.ylabel("Amount")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()
else:
    print("⚠️ データが存在しません。project_slug または type を確認してください。")
