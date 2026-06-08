import api
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
from forex_python.converter import CurrencyRates

# ============================================================
# 設定
# ============================================================

CSV_FILES = [
    "predictions_2nd_all_devornot_1.csv",
    "predictions_2nd_all_devornot_2.csv",
    "predictions_2nd_all_devornot_3.csv",
    "predictions_2nd_all_devornot_4.csv",
    "predictions_2nd_all_devornot_5.csv",
]

PROJECT_COL = "project_slug"
CONFIDENCE_THRESHOLD = 0.9
WINDOW_MONTHS = 12
BASE_CURRENCY = "USD"

# ============================================================
# 1. 5つのCSVを読み込み、5回すべて development かつ confidence >= 0.9 を判定
# ============================================================

dfs = []

for i, path in enumerate(CSV_FILES, start=1):
    df = pd.read_csv(path)

    required_cols = {
        "index",
        "expense_description",
        "predicted_label",
        "confidence",
        PROJECT_COL,
        "amount_value",
        "amount_currency",
    }
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        raise ValueError(f"{path} に必要な列がありません: {missing_cols}")

    df = df.copy()

    df["predicted_label"] = (
        df["predicted_label"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce")
    df["amount_value"] = pd.to_numeric(df["amount_value"], errors="coerce")

    df[f"is_development_run{i}"] = (
        (df["predicted_label"] == "development") &
        (df["confidence"] >= CONFIDENCE_THRESHOLD)
    )

    if i == 1:
        dfs.append(
            df[
                [
                    "index",
                    "expense_description",
                    PROJECT_COL,
                    "amount_value",
                    "amount_currency",
                    f"is_development_run{i}",
                ]
            ]
        )
    else:
        # 整合性確認用に project_slug, amount_value, amount_currency も残す
        dfs.append(
            df[
                [
                    "index",
                    PROJECT_COL,
                    "amount_value",
                    "amount_currency",
                    f"is_development_run{i}",
                ]
            ].rename(
                columns={
                    PROJECT_COL: f"{PROJECT_COL}_run{i}",
                    "amount_value": f"amount_value_run{i}",
                    "amount_currency": f"amount_currency_run{i}",
                }
            )
        )

# index をキーに横結合
df_expense = dfs[0]

for i in range(1, 5):
    df_expense = df_expense.merge(
        dfs[i],
        on="index",
        how="inner",
        validate="one_to_one"
    )

# project_slug が5ファイルで一致しているか確認
for i in range(2, 6):
    mismatch_count = (
        df_expense[PROJECT_COL] != df_expense[f"{PROJECT_COL}_run{i}"]
    ).sum()

    if mismatch_count > 0:
        raise ValueError(
            f"run{i} で project_slug が一致しない行があります: {mismatch_count} rows"
        )

# amount_value が5ファイルで一致しているか確認
# NaN 同士は一致扱いにする
for i in range(2, 6):
    mismatch_count = ~(
        df_expense["amount_value"].fillna("__NA__").astype(str)
        ==
        df_expense[f"amount_value_run{i}"].fillna("__NA__").astype(str)
    )

    mismatch_count = mismatch_count.sum()

    if mismatch_count > 0:
        print(
            f"Warning: run{i} で amount_value が一致しない行があります: "
            f"{mismatch_count} rows"
        )

# amount_currency は今回は無視するが、分布だけ確認
print("\n===== Amount currency distribution in run1 =====")
print(df_expense["amount_currency"].value_counts(dropna=False))

# 5回すべて development かつ confidence >= 0.9
run_cols = [f"is_development_run{i}" for i in range(1, 6)]
df_expense["is_development"] = df_expense[run_cols].all(axis=1)

# ============================================================
# amount_currency を使って支出額を USD に変換
# ============================================================

df_expense["amount_currency"] = (
    df_expense["amount_currency"]
    .astype(str)
    .str.strip()
    .str.upper()
)

# 支出額は負の値なので絶対値にする
# 誤って正の値になっている場合も abs() により支出額として扱う
df_expense["expense_amount_original"] = df_expense["amount_value"].abs()

# amount_value が欠損、0、または通貨コード欠損の行は除外
df_expense = df_expense[
    df_expense["expense_amount_original"].notna() &
    (df_expense["expense_amount_original"] > 0) &
    df_expense["amount_currency"].notna() &
    (df_expense["amount_currency"] != "") &
    (df_expense["amount_currency"] != "NAN")
].copy()

currency_rates = CurrencyRates()

unique_currencies = sorted(df_expense["amount_currency"].dropna().unique())

exchange_rates_to_usd = {}

for currency in unique_currencies:
    if currency == BASE_CURRENCY:
        exchange_rates_to_usd[currency] = 1.0
    else:
        try:
            exchange_rates_to_usd[currency] = currency_rates.get_rate(
                currency,
                BASE_CURRENCY
            )
        except Exception as e:
            print(f"Warning: failed to get exchange rate {currency} -> USD: {e}")
            exchange_rates_to_usd[currency] = np.nan

print("\n===== Exchange rates to USD =====")
for currency, rate in exchange_rates_to_usd.items():
    print(f"{currency} -> USD: {rate}")

df_expense["exchange_rate_to_usd"] = (
    df_expense["amount_currency"]
    .map(exchange_rates_to_usd)
)

# 為替レートを取得できなかった通貨は除外
missing_rate_rows = df_expense["exchange_rate_to_usd"].isna().sum()

if missing_rate_rows > 0:
    print(
        f"\nWarning: excluding rows with missing exchange rates: "
        f"{missing_rate_rows}"
    )

df_expense = df_expense[
    df_expense["exchange_rate_to_usd"].notna()
].copy()

# USD換算後の支出額
df_expense["expense_amount_usd"] = (
    df_expense["expense_amount_original"] *
    df_expense["exchange_rate_to_usd"]
)

print("\n===== Expense amount summary =====")
print("Total expense rows:", len(df_expense))
print("Total expense amount USD:", df_expense["expense_amount_usd"].sum())
print(
    "Development expense amount USD:",
    df_expense.loc[df_expense["is_development"], "expense_amount_usd"].sum()
)

# ============================================================
# 2. プロジェクトごとの development 使用割合を計算
#    - 回数ベース
#    - 金額ベース
# ============================================================

df_expense["development_amount_usd"] = np.where(
    df_expense["is_development"],
    df_expense["expense_amount_usd"],
    0.0
)

df_project_spending = (
    df_expense
    .groupby(PROJECT_COL)
    .agg(
        total_expense_count=("index", "count"),
        development_expense_count=("is_development", "sum"),
        total_expense_amount_usd=("expense_amount_usd", "sum"),
        development_expense_amount_usd=("development_amount_usd", "sum"),
    )
    .reset_index()
)

# 回数ベースの割合
df_project_spending["development_count_ratio"] = (
    df_project_spending["development_expense_count"] /
    df_project_spending["total_expense_count"]
)

# 金額ベースの割合
df_project_spending["development_amount_ratio"] = (
    df_project_spending["development_expense_amount_usd"] /
    df_project_spending["total_expense_amount_usd"]
)

# 0-10%, 10-20%, ..., 90-100% にビン分け
bins = np.arange(0, 1.0 + 0.1, 0.1)
labels = [
    f"{int(bins[i] * 100)}-{int(bins[i + 1] * 100)}%"
    for i in range(len(bins) - 1)
]

df_project_spending["development_count_ratio_bin"] = pd.cut(
    df_project_spending["development_count_ratio"],
    bins=bins,
    labels=labels,
    include_lowest=True,
    right=True
)

df_project_spending["development_amount_ratio_bin"] = pd.cut(
    df_project_spending["development_amount_ratio"],
    bins=bins,
    labels=labels,
    include_lowest=True,
    right=True
)

print("\n===== Project development ratio summary =====")
print("Projects with expense data:", len(df_project_spending))

print(
    df_project_spending[
        [
            PROJECT_COL,
            "total_expense_count",
            "development_expense_count",
            "development_count_ratio",
            "development_count_ratio_bin",
            "total_expense_amount_usd",
            "development_expense_amount_usd",
            "development_amount_ratio",
            "development_amount_ratio_bin",
        ]
    ].head()
)

print("\n===== Number of projects by development count ratio bin =====")
print(
    df_project_spending["development_count_ratio_bin"]
    .value_counts()
    .sort_index()
)

print("\n===== Number of projects by development amount ratio bin =====")
print(
    df_project_spending["development_amount_ratio_bin"]
    .value_counts()
    .sort_index()
)

# ============================================================
# 3. Open Collective 登録前後12ヶ月のコミット数を計算
# ============================================================

engine = create_engine(
    f"postgresql+psycopg2://postgres:{api.load_sql_password_from_credentials()}@localhost:5432/opencollective"
)

query_collectives = """
SELECT id, name, slug, type, created_at, github_account
FROM public.collectives
WHERE github_account IS NOT NULL
"""

query_commit_history = """
SELECT repo_name, commit_time
FROM public.commit_history
WHERE repo_name IS NOT NULL
  AND commit_time IS NOT NULL
"""

df_collectives = pd.read_sql(query_collectives, engine)
df_commits = pd.read_sql(query_commit_history, engine)

df_collectives = df_collectives[
    df_collectives["github_account"].notna()
].copy()

df_collectives = df_collectives[
    df_collectives["github_account"].str.contains("/", na=False)
].copy()

df_collectives["repo_name"] = (
    df_collectives["github_account"]
    .str.strip()
    .str.replace("/", "-", regex=False)
)

df_collectives["created_at"] = pd.to_datetime(
    df_collectives["created_at"],
    utc=True
).dt.tz_convert(None)

df_commits["commit_time"] = pd.to_datetime(
    df_commits["commit_time"],
    utc=True
).dt.tz_convert(None)

commit_data_start = df_commits["commit_time"].min()
commit_data_end = df_commits["commit_time"].max()

commit_repos = set(df_commits["repo_name"].unique())

df_matched = df_collectives[
    df_collectives["repo_name"].isin(commit_repos)
].copy()

df_matched["before_start"] = (
    df_matched["created_at"] - pd.DateOffset(months=WINDOW_MONTHS)
)
df_matched["before_end"] = df_matched["created_at"]
df_matched["after_start"] = df_matched["created_at"]
df_matched["after_end"] = (
    df_matched["created_at"] + pd.DateOffset(months=WINDOW_MONTHS)
)

df_analyzable = df_matched[
    (df_matched["before_start"] >= commit_data_start) &
    (df_matched["after_end"] <= commit_data_end)
].copy()

print("\n===== Commit analysis target =====")
print("Matched projects:", len(df_matched))
print("Analyzable projects:", len(df_analyzable))

commits_by_repo = {
    repo_name: group["commit_time"].sort_values().reset_index(drop=True)
    for repo_name, group in df_commits.groupby("repo_name")
}

commit_results = []

for idx, row in enumerate(df_analyzable.itertuples(index=False), start=1):
    repo_commits = commits_by_repo.get(
        row.repo_name,
        pd.Series(dtype="datetime64[ns]")
    )

    commits_before = (
        (repo_commits >= row.before_start) &
        (repo_commits < row.before_end)
    ).sum()

    commits_after = (
        (repo_commits >= row.after_start) &
        (repo_commits < row.after_end)
    ).sum()

    # コミット数の増加率（%）
    # before が 0 の場合は増加率を定義できないため NaN にする
    if commits_before == 0:
        growth_rate_pct = np.nan
    else:
        growth_rate_pct = ((commits_after - commits_before) / commits_before) * 100

    commit_results.append({
        "id": row.id,
        "name": row.name,
        "slug": row.slug,
        "github_account": row.github_account,
        "repo_name": row.repo_name,
        "created_at": row.created_at,
        "commits_before_12m": commits_before,
        "commits_after_12m": commits_after,
        "growth_rate_pct": growth_rate_pct,
    })

    if idx % 100 == 0 or idx == len(df_analyzable):
        print(f"Processed {idx} / {len(df_analyzable)} projects")

df_commit_change = pd.DataFrame(commit_results)

# ============================================================
# 4. development 使用回数割合データとコミット変化量を結合
# ============================================================

df_analysis = df_commit_change.merge(
    df_project_spending,
    left_on="slug",
    right_on=PROJECT_COL,
    how="inner"
)

df_analysis = df_analysis[
    df_analysis["development_count_ratio_bin"].notna()
].copy()

print("\n===== Merged analysis data =====")
print("Projects used in final analysis:", len(df_analysis))

# ============================================================
# 5. ビンごとの記述統計を表示
# ============================================================

df_box_summary = (
    df_analysis
    .groupby("development_count_ratio_bin", observed=False)
    .agg(
        n_projects=("growth_rate_pct", "count"),
        mean_growth_rate_pct=("growth_rate_pct", "mean"),
        min_growth_rate_pct=("growth_rate_pct", "min"),
        q1_growth_rate_pct=("growth_rate_pct", lambda x: x.quantile(0.25)),
        median_growth_rate_pct=("growth_rate_pct", "median"),
        q3_growth_rate_pct=("growth_rate_pct", lambda x: x.quantile(0.75)),
        max_growth_rate_pct=("growth_rate_pct", "max"),
        mean_total_expense_count=("total_expense_count", "mean"),
        median_total_expense_count=("total_expense_count", "median"),
        mean_development_expense_count=("development_expense_count", "mean"),
        median_development_expense_count=("development_expense_count", "median"),
    )
    .reset_index()
)

print("\n===== Growth rate (%) summary by development count ratio bin =====")
print(df_box_summary.to_string(index=False))

df_analysis.to_csv(
    "rq2_development_count_ratio_and_commit_growth_rate_pct_project_level.csv",
    index=False
)

df_box_summary.to_csv(
    "rq2_development_count_ratio_and_commit_growth_rate_pct_boxplot_summary.csv",
    index=False
)

# ============================================================
# 5.5 金額ベースのビンごとの記述統計を表示
# ============================================================

df_amount_box_summary = (
    df_analysis
    .groupby("development_amount_ratio_bin", observed=False)
    .agg(
        n_projects=("growth_rate_pct", "count"),
        mean_growth_rate_pct=("growth_rate_pct", "mean"),
        min_growth_rate_pct=("growth_rate_pct", "min"),
        q1_growth_rate_pct=("growth_rate_pct", lambda x: x.quantile(0.25)),
        median_growth_rate_pct=("growth_rate_pct", "median"),
        q3_growth_rate_pct=("growth_rate_pct", lambda x: x.quantile(0.75)),
        max_growth_rate_pct=("growth_rate_pct", "max"),
        mean_total_expense_amount_usd=("total_expense_amount_usd", "mean"),
        median_total_expense_amount_usd=("total_expense_amount_usd", "median"),
        mean_development_expense_amount_usd=("development_expense_amount_usd", "mean"),
        median_development_expense_amount_usd=("development_expense_amount_usd", "median"),
        mean_total_expense_count=("total_expense_count", "mean"),
        median_total_expense_count=("total_expense_count", "median"),
    )
    .reset_index()
)

print("\n===== Growth rate (%) summary by development amount ratio bin =====")
print(df_amount_box_summary.to_string(index=False))

df_amount_box_summary.to_csv(
    "rq2_development_amount_ratio_and_commit_growth_rate_pct_boxplot_summary.csv",
    index=False
)


# ============================================================
# 6. 箱ひげ図を描画
# ============================================================

plot_data = [
    df_analysis.loc[
        df_analysis["development_count_ratio_bin"] == label,
        "growth_rate_pct"
    ].dropna()
    for label in labels
]

plt.figure(figsize=(14, 7))

plt.boxplot(
    plot_data,
    labels=labels,
    showmeans=True
)

plt.axhline(
    y=0,
    linestyle="--",
    linewidth=1
)

plt.xlabel("Share of expenses classified as development")
plt.ylabel("Commit growth rate (%)")
plt.title("Commit growth rate by development expense count ratio")
plt.xticks(rotation=45)
plt.grid(axis="y", alpha=0.3)
plt.tight_layout()

plt.savefig(
    "rq2_boxplot_commit_growth_rate_pct_by_development_expense_count_ratio.png",
    dpi=300
)

plt.show()

# ============================================================
# 6.5 金額ベースの箱ひげ図を描画
# ============================================================

amount_plot_data = [
    df_analysis.loc[
        df_analysis["development_amount_ratio_bin"] == label,
        "growth_rate_pct"
    ].dropna()
    for label in labels
]

plt.figure(figsize=(14, 7))

plt.boxplot(
    amount_plot_data,
    labels=labels,
    showmeans=True
)

plt.axhline(
    y=0,
    linestyle="--",
    linewidth=1
)

plt.xlabel("Share of expense amount classified as development")
plt.ylabel("Commit growth rate (%)")
plt.title("Commit growth rate by development expense amount ratio")
plt.xticks(rotation=45)
plt.grid(axis="y", alpha=0.3)
plt.tight_layout()

plt.savefig(
    "rq2_boxplot_commit_growth_rate_pct_by_development_expense_amount_ratio.png",
    dpi=300
)

plt.show()

n_growth_rate_nan = df_analysis["growth_rate_pct"].isna().sum()

print("\n===== Growth rate availability =====")
print("Projects used in final analysis:", len(df_analysis))
print("Projects with commits_before_12m = 0 excluded from growth rate stats:", n_growth_rate_nan)
print("Projects with valid growth_rate_pct:", df_analysis["growth_rate_pct"].notna().sum())
