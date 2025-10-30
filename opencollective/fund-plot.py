import os
import api
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine


# --- 保存先ディレクトリ ---
os.makedirs("figs", exist_ok=True)

# --- DB接続情報 ---
engine = create_engine(
	f"postgresql+psycopg2://postgres:{api.load_sql_password_from_credentials()}@localhost:5432/opencollective"
)

# --- 全プロジェクト一覧を取得 ---
projects = pd.read_sql("SELECT DISTINCT project_slug FROM transactions;", engine)
print(f"検出されたプロジェクト数: {len(projects)}")

# --- フィルタ条件 ---
MIN_DAYS = 50  # len(df) がこの値以上のプロジェクトのみ保存

# --- 各プロジェクトを処理 ---
for slug in projects["project_slug"]:
	query = f"""
		SELECT DATE(created_at) AS date, SUM(amount_value) AS total_amount
		FROM transactions
		WHERE project_slug = '{slug}' AND type = 'CREDIT'
		GROUP BY DATE(created_at)
		ORDER BY DATE(created_at);
	"""
	df = pd.read_sql(query, engine)

	if len(df) < MIN_DAYS:
		#print(f"スキップ: {slug} (データ件数 {len(df)})")
		continue
	
	query_currency = f"""
		SELECT DISTINCT amount_currency
		FROM transactions
		WHERE project_slug = '{slug}' AND type = 'CREDIT'
		LIMIT 1;
	"""
	currency_df = pd.read_sql(query_currency, engine)
	currency=currency_df["amount_currency"].values[0]

	median_value = df["total_amount"].median()
	plt.figure(figsize=(10,5))
	plt.plot(df["date"], df["total_amount"], marker="o", label="Daily received amount")
	plt.axhline(y=median_value, color='red', linestyle='--', label=f"Median = {median_value:.2f} {currency}")
	plt.title(f"Daily Funding Received by {slug}")
	plt.xlabel("Date")
	plt.ylabel(f"Amount [{currency}]")
	plt.legend()
	plt.grid(True)
	plt.tight_layout()
	#plt.yscale("log")  # ログスケールに変更

	# 保存
	filename = f"figs/funding_plot_{slug}.png"
	plt.savefig(filename, dpi=300)
	plt.close()  # メモリ節約
	print(f"✅ 保存完了: {filename}")
