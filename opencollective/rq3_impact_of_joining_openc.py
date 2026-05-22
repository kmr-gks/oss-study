import api
import pandas as pd
import numpy as np
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
# collectiveテーブルではgithubアカウント名とリポジトリ名が'/'で区切られているが、commit_historyでは'-'で区切られていることに注意。

# =========================
df_collectives = df_collectives[
    df_collectives["github_account"].notna()
]
df_collectives = df_collectives[
    df_collectives["github_account"].str.contains("/", na=False)
]
df_collectives["repo_name"] = (
    df_collectives["github_account"]
    .str.strip()
    .str.replace("/", "-", regex=False)
)

df_collectives["created_at"] = pd.to_datetime(df_collectives["created_at"])
df_commits["commit_time"] = pd.to_datetime(df_commits["commit_time"])

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
# 5. 前後3ヶ月が観測可能なプロジェクトだけ残す
# =========================

df_matched["before_start"] = df_matched["created_at"] - pd.DateOffset(months=3)
df_matched["before_end"] = df_matched["created_at"]
df_matched["after_start"] = df_matched["created_at"]
df_matched["after_end"] = df_matched["created_at"] + pd.DateOffset(months=3)

df_analyzable = df_matched[
    (df_matched["before_start"] >= commit_data_start) &
    (df_matched["after_end"] <= commit_data_end)
].copy()

print("\nAnalyzable projects:", len(df_analyzable))
print(
    "Analyzable rate among matched:",
    len(df_analyzable) / len(df_matched)
)

# =========================
# 6. 前後3ヶ月のコミット数を計算
# =========================

results = []

for _, row in df_analyzable.iterrows():
    repo_name = row["repo_name"]
    created_at = row["created_at"]

    before_start = row["before_start"]
    before_end = row["before_end"]
    after_start = row["after_start"]
    after_end = row["after_end"]

    repo_commits = df_commits[df_commits["repo_name"] == repo_name]

    commits_before_3m = repo_commits[
        (repo_commits["commit_time"] >= before_start) &
        (repo_commits["commit_time"] < before_end)
    ].shape[0]

    commits_after_3m = repo_commits[
        (repo_commits["commit_time"] >= after_start) &
        (repo_commits["commit_time"] < after_end)
    ].shape[0]

    diff = commits_after_3m - commits_before_3m

    if commits_before_3m == 0:
        growth_rate = np.nan
    else:
        growth_rate = diff / commits_before_3m

    log_change = np.log1p(commits_after_3m) - np.log1p(commits_before_3m)

    if commits_after_3m > commits_before_3m:
        change_category = "increased"
    elif commits_after_3m < commits_before_3m:
        change_category = "decreased"
    else:
        change_category = "unchanged"

    results.append({
        "id": row["id"],
        "name": row["name"],
        "slug": row["slug"],
        "github_account": row["github_account"],
        "repo_name": repo_name,
        "created_at": created_at,
        "commits_before_3m": commits_before_3m,
        "commits_after_3m": commits_after_3m,
        "diff": diff,
        "growth_rate": growth_rate,
        "log_change": log_change,
        "change_category": change_category,
    })
    print(f"Processed project: {len(results)} / {len(df_analyzable)} {repo_name}, commits before: {commits_before_3m}, commits after: {commits_after_3m}, diff: {diff}")

df_rq3 = pd.DataFrame(results)

# =========================
# 7. 記述統計
# =========================

N = len(df_rq3)

mean_before = df_rq3["commits_before_3m"].mean()
median_before = df_rq3["commits_before_3m"].median()

mean_after = df_rq3["commits_after_3m"].mean()
median_after = df_rq3["commits_after_3m"].median()

mean_diff = df_rq3["diff"].mean()
median_diff = df_rq3["diff"].median()

mean_log_change = df_rq3["log_change"].mean()
median_log_change = df_rq3["log_change"].median()

increased_count = (df_rq3["change_category"] == "increased").sum()
decreased_count = (df_rq3["change_category"] == "decreased").sum()
unchanged_count = (df_rq3["change_category"] == "unchanged").sum()

increase_rate = increased_count / N
decrease_rate = decreased_count / N
unchanged_rate = unchanged_count / N

# =========================
# 8. 統計検定
# =========================

# Wilcoxon signed-rank test
# 前後差がすべて0の場合はエラーになる可能性があるため分岐
if (df_rq3["diff"] != 0).any():
    wilcoxon_result = wilcoxon(
        df_rq3["commits_after_3m"],
        df_rq3["commits_before_3m"],
        alternative="two-sided"
    )
    wilcoxon_stat = wilcoxon_result.statistic
    wilcoxon_p = wilcoxon_result.pvalue
else:
    wilcoxon_stat = np.nan
    wilcoxon_p = np.nan

# paired t-test
ttest_result = ttest_rel(
    df_rq3["commits_after_3m"],
    df_rq3["commits_before_3m"]
)

ttest_stat = ttest_result.statistic
ttest_p = ttest_result.pvalue

# =========================
# 9. 結果表示
# =========================

print("\n===== RQ3: Commit Activity Around Open Collective Registration =====")

print(f"N analyzed: {N}")

print("\n--- Before / After commits ---")
print(f"Mean commits before 3m: {mean_before:.3f}")
print(f"Median commits before 3m: {median_before:.3f}")
print(f"Mean commits after 3m: {mean_after:.3f}")
print(f"Median commits after 3m: {median_after:.3f}")

print("\n--- Change ---")
print(f"Mean diff: {mean_diff:.3f}")
print(f"Median diff: {median_diff:.3f}")
print(f"Mean log_change: {mean_log_change:.3f}")
print(f"Median log_change: {median_log_change:.3f}")

print("\n--- Direction of change ---")
print(f"Increased projects: {increased_count} ({increase_rate:.2%})")
print(f"Decreased projects: {decreased_count} ({decrease_rate:.2%})")
print(f"Unchanged projects: {unchanged_count} ({unchanged_rate:.2%})")

print("\n--- Statistical tests ---")
print(f"Wilcoxon statistic: {wilcoxon_stat:.3f}")
print(f"Wilcoxon p-value: {wilcoxon_p:.6f}")
print(f"Paired t-test statistic: {ttest_stat:.3f}")
print(f"Paired t-test p-value: {ttest_p:.6f}")

# =========================
# 10. 結果をCSVに保存
# =========================

df_rq3.to_csv("rq3_commit_change_around_opencollective_registration.csv", index=False)

summary = pd.DataFrame([{
    "n_analyzed": N,
    "mean_commits_before_3m": mean_before,
    "median_commits_before_3m": median_before,
    "mean_commits_after_3m": mean_after,
    "median_commits_after_3m": median_after,
    "mean_diff": mean_diff,
    "median_diff": median_diff,
    "mean_log_change": mean_log_change,
    "median_log_change": median_log_change,
    "increased_count": increased_count,
    "decreased_count": decreased_count,
    "unchanged_count": unchanged_count,
    "increase_rate": increase_rate,
    "decrease_rate": decrease_rate,
    "unchanged_rate": unchanged_rate,
    "wilcoxon_statistic": wilcoxon_stat,
    "wilcoxon_p_value": wilcoxon_p,
    "paired_t_statistic": ttest_stat,
    "paired_t_p_value": ttest_p,
}])

summary.to_csv("rq3_commit_change_summary.csv", index=False)
