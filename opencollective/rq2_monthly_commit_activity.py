import api
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
from scipy.stats import wilcoxon, ttest_rel

engine = create_engine(
    f"postgresql+psycopg2://postgres:{api.load_sql_password_from_credentials()}@localhost:5432/opencollective"
)

# =========================
# 1. データ取得
# =========================

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

# =========================
# 2. リポジトリ名の正規化
# collective テーブルでは owner/repo
# commit_history では owner-repo
# =========================

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

# timezone が混在していても扱いやすいように UTC 経由で naive datetime にする
df_collectives["created_at"] = pd.to_datetime(
    df_collectives["created_at"], utc=True
).dt.tz_convert(None)

df_commits["commit_time"] = pd.to_datetime(
    df_commits["commit_time"], utc=True
).dt.tz_convert(None)

# =========================
# 3. commit_history とマッチするプロジェクトだけ残す
# =========================

commit_repos = set(df_commits["repo_name"].unique())

df_matched = df_collectives[
    df_collectives["repo_name"].isin(commit_repos)
].copy()

print("Collectives with owner/repo:", len(df_collectives))
print("Repos in commit_history:", df_commits["repo_name"].nunique())
print("Matched projects:", len(df_matched))
print("Match rate:", len(df_matched) / len(df_collectives))

# =========================
# 4. commit_history の観測期間を確認
# =========================

commit_data_start = df_commits["commit_time"].min()
commit_data_end = df_commits["commit_time"].max()

print("\nCommit data start:", commit_data_start)
print("Commit data end:", commit_data_end)

# =========================
# 5. 加入前後1年を完全に観測できるプロジェクトだけ残す
# =========================

df_matched["window_start"] = df_matched["created_at"] - pd.DateOffset(months=12)
df_matched["window_end"] = df_matched["created_at"] + pd.DateOffset(months=12)

df_analyzable = df_matched[
    (df_matched["window_start"] >= commit_data_start) &
    (df_matched["window_end"] <= commit_data_end)
].copy()

print("\n===== Monthly commit analysis around Open Collective registration =====")
print("Analyzable projects:", len(df_analyzable))
print("Analyzable rate among matched:", len(df_analyzable) / len(df_matched))

# =========================
# 6. 高速化のため repo_name ごとに commit_time をまとめる
# =========================

commits_by_repo = {
    repo_name: group["commit_time"].sort_values().reset_index(drop=True)
    for repo_name, group in df_commits.groupby("repo_name")
}

# =========================
# 7. 各プロジェクトについて相対月ごとのコミット数を計算
# =========================

monthly_results = []

relative_months = list(range(-12, 12))  # -12, -11, ..., -1, 0, ..., 11

for idx, row in enumerate(df_analyzable.itertuples(index=False), start=1):
    repo_name = row.repo_name
    created_at = row.created_at

    repo_commits = commits_by_repo.get(
        repo_name,
        pd.Series(dtype="datetime64[ns]")
    )

    for relative_month in relative_months:
        month_start = created_at + pd.DateOffset(months=relative_month)
        month_end = created_at + pd.DateOffset(months=relative_month + 1)

        commit_count = (
            (repo_commits >= month_start) &
            (repo_commits < month_end)
        ).sum()

        monthly_results.append({
            "id": row.id,
            "name": row.name,
            "slug": row.slug,
            "github_account": row.github_account,
            "repo_name": repo_name,
            "created_at": created_at,
            "relative_month": relative_month,
            "period": "before" if relative_month < 0 else "after",
            "month_start": month_start,
            "month_end": month_end,
            "commit_count": commit_count,
        })

    if idx % 100 == 0 or idx == len(df_analyzable):
        print(f"Processed {idx} / {len(df_analyzable)} projects")

df_monthly = pd.DataFrame(monthly_results)

# =========================
# 8. 相対月ごとの平均・中央値を計算
# =========================

df_summary = (
    df_monthly
    .groupby("relative_month")
    .agg(
        mean_commits=("commit_count", "mean"),
        median_commits=("commit_count", "median"),
        std_commits=("commit_count", "std"),
        min_commits=("commit_count", "min"),
        max_commits=("commit_count", "max"),
        n_projects=("commit_count", "count"),
    )
    .reset_index()
)

# グラフ表示用の相対月
# 内部的には -12〜11 のまま計算し、
# 表示上だけ after 側を 0〜11 から 1〜12 に変換する
df_summary["plot_month"] = df_summary["relative_month"].apply(
    lambda x: x if x < 0 else x + 1
)

print("\n===== Monthly summary =====")
print(df_summary)

# =========================
# 8.5 print表示
# =========================

# 12ヶ月単位で見たコミットの平均と中央値
#    各プロジェクトについて、加入前12ヶ月・加入後12ヶ月の合計コミット数を出してから、
#    その平均・中央値を計算する
df_12month_project = (
    df_monthly
    .groupby(["id", "repo_name", "period"])
    .agg(
        total_commits_12m=("commit_count", "sum")
    )
    .reset_index()
)

df_12month_summary = (
    df_12month_project
    .groupby("period")
    .agg(
        mean_commits_12m=("total_commits_12m", "mean"),
        median_commits_12m=("total_commits_12m", "median"),
        n_projects=("total_commits_12m", "count")
    )
    .reset_index()
)

# before, after の順で表示する
df_12month_summary["period"] = pd.Categorical(
    df_12month_summary["period"],
    categories=["before", "after"],
    ordered=True
)

df_12month_summary = df_12month_summary.sort_values("period")

print("\n===== 12-month total commit counts: before vs after =====")
print(df_12month_summary.to_string(index=False))


# =========================
# 8.6 加入前12ヶ月 vs 加入後12ヶ月の統計検定
# =========================

df_before_after = (
    df_12month_project
    .pivot(index=["id", "repo_name"], columns="period", values="total_commits_12m")
    .reset_index()
)

df_before_after = df_before_after.dropna(subset=["before", "after"]).copy()

df_before_after["diff"] = df_before_after["after"] - df_before_after["before"]
df_before_after["growth_rate"] = np.where(
    df_before_after["before"] == 0,
    np.nan,
    (df_before_after["after"] - df_before_after["before"]) / df_before_after["before"]
)
df_before_after["log_change"] = (
    np.log1p(df_before_after["after"]) -
    np.log1p(df_before_after["before"])
)

print("\n===== Statistical test: before 12m vs after 12m =====")
print("N projects:", len(df_before_after))

print("\n--- Descriptive statistics ---")
print("Mean commits before:", df_before_after["before"].mean())
print("Median commits before:", df_before_after["before"].median())
print("Mean commits after:", df_before_after["after"].mean())
print("Median commits after:", df_before_after["after"].median())
print("Mean diff:", df_before_after["diff"].mean())
print("Median diff:", df_before_after["diff"].median())
print("Mean log_change:", df_before_after["log_change"].mean())
print("Median log_change:", df_before_after["log_change"].median())

# Wilcoxon signed-rank test
# コミット数分布は外れ値が大きいため、主検定としてはこちらを推奨
if (df_before_after["diff"] != 0).any():
    wilcoxon_result = wilcoxon(
        df_before_after["after"],
        df_before_after["before"],
        alternative="two-sided"
    )

    wilcoxon_result_greater = wilcoxon(
        df_before_after["after"],
        df_before_after["before"],
        alternative="greater"
    )

    wilcoxon_result_less = wilcoxon(
        df_before_after["after"],
        df_before_after["before"],
        alternative="less"
    )

    print("\n--- Wilcoxon signed-rank test ---")
    print("Two-sided statistic:", wilcoxon_result.statistic)
    print("Two-sided p-value:", wilcoxon_result.pvalue)
    print("Greater p-value, after > before:", wilcoxon_result_greater.pvalue)
    print("Less p-value, after < before:", wilcoxon_result_less.pvalue)

# Paired t-test
# 平均差の検定。ただし外れ値の影響を強く受けるため補助的に使う
ttest_result = ttest_rel(
    df_before_after["after"],
    df_before_after["before"]
)

print("\n--- Paired t-test ---")
print("t statistic:", ttest_result.statistic)
print("p-value:", ttest_result.pvalue)

# 増加・減少プロジェクト数
increased = (df_before_after["after"] > df_before_after["before"]).sum()
decreased = (df_before_after["after"] < df_before_after["before"]).sum()
unchanged = (df_before_after["after"] == df_before_after["before"]).sum()

print("\n--- Direction of change ---")
print("Increased:", increased, f"({increased / len(df_before_after):.2%})")
print("Decreased:", decreased, f"({decreased / len(df_before_after):.2%})")
print("Unchanged:", unchanged, f"({unchanged / len(df_before_after):.2%})")

df_before_after.to_csv(
    "rq2_commit_before_after_12m_statistical_test_project_level.csv",
    index=False
)


# =========================
# 9. CSV保存
# =========================

df_monthly.to_csv(
    "rq2_monthly_commits_around_opencollective_registration_project_level.csv",
    index=False
)

df_summary.to_csv(
    "rq2_monthly_commits_around_opencollective_registration_summary.csv",
    index=False
)

# =========================
# 10. グラフ化：平均と中央値
# =========================

plt.figure(figsize=(12, 6))

plt.plot(
    df_summary["plot_month"],
    df_summary["mean_commits"],
    marker="o",
    label="Mean commits"
)

plt.plot(
    df_summary["plot_month"],
    df_summary["median_commits"],
    marker="o",
    label="Median commits"
)

# Open Collective 加入タイミング
plt.axvline(x=0, linestyle="--", linewidth=1)
plt.text(
    0.1,
    plt.ylim()[1] * 0.95,
    "Open Collective registration",
    rotation=90,
    va="top"
)

plot_months = list(range(-12, 0)) + list(range(1, 13))
plt.xticks(plot_months)
plt.xlabel("Months before / after Open Collective registration")
plt.ylabel("Monthly commit count")
plt.title("Monthly commit activity before and after Open Collective registration")
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()

plt.savefig(
    "rq2_monthly_commits_around_opencollective_registration_mean_median.png",
    dpi=300
)

plt.show()
