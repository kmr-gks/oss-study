import api
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

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
                    f"is_development_run{i}",
                ]
            ]
        )
    else:
        # 念のため project_slug も残して整合性確認に使う
        dfs.append(
            df[
                [
                    "index",
                    PROJECT_COL,
                    f"is_development_run{i}",
                ]
            ].rename(columns={PROJECT_COL: f"{PROJECT_COL}_run{i}"})
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

# 5回すべて development かつ confidence >= 0.9
run_cols = [f"is_development_run{i}" for i in range(1, 6)]
df_expense["is_development"] = df_expense[run_cols].all(axis=1)

print("\n===== Expense classification summary =====")
print("Total expense rows:", len(df_expense))
print("Development expense rows:", df_expense["is_development"].sum())
print("Non-development expense rows:", (~df_expense["is_development"]).sum())

# ============================================================
# 2. プロジェクトごとの development 使用回数割合を計算
# ============================================================

df_project_spending = (
    df_expense
    .groupby(PROJECT_COL)
    .agg(
        total_expense_count=("index", "count"),
        development_expense_count=("is_development", "sum"),
    )
    .reset_index()
)

df_project_spending["development_count_ratio"] = (
    df_project_spending["development_expense_count"] /
    df_project_spending["total_expense_count"]
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

print("\n===== Project development count ratio summary =====")
print("Projects with expense data:", len(df_project_spending))
print(
    df_project_spending[
        [
            PROJECT_COL,
            "total_expense_count",
            "development_expense_count",
            "development_count_ratio",
            "development_count_ratio_bin",
        ]
    ].head()
)

print("\n===== Number of projects by development count ratio bin =====")
print(
    df_project_spending["development_count_ratio_bin"]
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

    log_change = np.log1p(commits_after) - np.log1p(commits_before)

    commit_results.append({
        "id": row.id,
        "name": row.name,
        "slug": row.slug,
        "github_account": row.github_account,
        "repo_name": row.repo_name,
        "created_at": row.created_at,
        "commits_before_12m": commits_before,
        "commits_after_12m": commits_after,
        "log_change": log_change,
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
        n_projects=("log_change", "count"),
        mean_log_change=("log_change", "mean"),
        min_log_change=("log_change", "min"),
        q1_log_change=("log_change", lambda x: x.quantile(0.25)),
        median_log_change=("log_change", "median"),
        q3_log_change=("log_change", lambda x: x.quantile(0.75)),
        max_log_change=("log_change", "max"),
        mean_total_expense_count=("total_expense_count", "mean"),
        median_total_expense_count=("total_expense_count", "median"),
        mean_development_expense_count=("development_expense_count", "mean"),
        median_development_expense_count=("development_expense_count", "median"),
    )
    .reset_index()
)

print("\n===== Log change summary by development count ratio bin =====")
print(df_box_summary.to_string(index=False))

df_analysis.to_csv(
    "rq2_development_count_ratio_and_commit_log_change_project_level.csv",
    index=False
)

df_box_summary.to_csv(
    "rq2_development_count_ratio_and_commit_log_change_boxplot_summary.csv",
    index=False
)

# ============================================================
# 6. 箱ひげ図を描画
# ============================================================

plot_data = [
    df_analysis.loc[
        df_analysis["development_count_ratio_bin"] == label,
        "log_change"
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
plt.ylabel("Commit log change: log1p(after 12m) - log1p(before 12m)")
plt.title("Commit activity change by development expense count ratio")
plt.xticks(rotation=45)
plt.grid(axis="y", alpha=0.3)
plt.tight_layout()

plt.savefig(
    "rq2_boxplot_commit_log_change_by_development_expense_count_ratio.png",
    dpi=300
)

plt.show()
