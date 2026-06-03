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

df_collectives["created_at"] = pd.to_datetime(df_collectives["created_at"])
df_commits["commit_time"] = pd.to_datetime(df_commits["commit_time"])

# timezone が混在した場合に備える
df_collectives["created_at"] = df_collectives["created_at"].dt.tz_localize(None)
df_commits["commit_time"] = df_commits["commit_time"].dt.tz_localize(None)

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
# 5. 高速化のため repo_name ごとに commit をまとめておく
# =========================

commits_by_repo = {
    repo_name: group["commit_time"].sort_values().reset_index(drop=True)
    for repo_name, group in df_commits.groupby("repo_name")
}

# =========================
# 6. 分析関数
# =========================

def analyze_commit_change(window_months: int):
    """
    Open Collective 登録日前後 window_months ヶ月のコミット数変化を分析する。
    """

    label = f"{window_months}m"

    df_window = df_matched.copy()

    df_window["before_start"] = df_window["created_at"] - pd.DateOffset(months=window_months)
    df_window["before_end"] = df_window["created_at"]
    df_window["after_start"] = df_window["created_at"]
    df_window["after_end"] = df_window["created_at"] + pd.DateOffset(months=window_months)

    # 前後 window_months ヶ月が commit_history の観測範囲に入っているプロジェクトだけ残す
    df_analyzable = df_window[
        (df_window["before_start"] >= commit_data_start) &
        (df_window["after_end"] <= commit_data_end)
    ].copy()

    print(f"\n===== Window: {window_months} months =====")
    print("Analyzable projects:", len(df_analyzable))
    print("Analyzable rate among matched:", len(df_analyzable) / len(df_matched))

    results = []

    for idx, row in enumerate(df_analyzable.itertuples(index=False), start=1):
        repo_name = row.repo_name

        before_start = row.before_start
        before_end = row.before_end
        after_start = row.after_start
        after_end = row.after_end

        repo_commits = commits_by_repo.get(repo_name, pd.Series(dtype="datetime64[ns]"))

        commits_before = (
            (repo_commits >= before_start) &
            (repo_commits < before_end)
        ).sum()

        commits_after = (
            (repo_commits >= after_start) &
            (repo_commits < after_end)
        ).sum()

        diff = commits_after - commits_before

        if commits_before == 0:
            growth_rate = np.nan
        else:
            growth_rate = diff / commits_before

        log_change = np.log1p(commits_after) - np.log1p(commits_before)

        if commits_after > commits_before:
            change_category = "increased"
        elif commits_after < commits_before:
            change_category = "decreased"
        else:
            change_category = "unchanged"

        results.append({
            "id": row.id,
            "name": row.name,
            "slug": row.slug,
            "github_account": row.github_account,
            "repo_name": repo_name,
            "created_at": row.created_at,
            "window_months": window_months,
            f"commits_before_{label}": commits_before,
            f"commits_after_{label}": commits_after,
            "commits_before": commits_before,
            "commits_after": commits_after,
            "diff": diff,
            "growth_rate": growth_rate,
            "log_change": log_change,
            "change_category": change_category,
        })

        if idx % 100 == 0 or idx == len(df_analyzable):
            print(f"Processed {idx} / {len(df_analyzable)} projects")

    df_result = pd.DataFrame(results)

    # =========================
    # 記述統計
    # =========================

    N = len(df_result)

    mean_before = df_result["commits_before"].mean()
    median_before = df_result["commits_before"].median()

    mean_after = df_result["commits_after"].mean()
    median_after = df_result["commits_after"].median()

    mean_diff = df_result["diff"].mean()
    median_diff = df_result["diff"].median()

    mean_log_change = df_result["log_change"].mean()
    median_log_change = df_result["log_change"].median()

    increased_count = (df_result["change_category"] == "increased").sum()
    decreased_count = (df_result["change_category"] == "decreased").sum()
    unchanged_count = (df_result["change_category"] == "unchanged").sum()

    increase_rate = increased_count / N if N > 0 else np.nan
    decrease_rate = decreased_count / N if N > 0 else np.nan
    unchanged_rate = unchanged_count / N if N > 0 else np.nan

    # =========================
    # 統計検定
    # =========================

    if N > 0 and (df_result["diff"] != 0).any():
        wilcoxon_result = wilcoxon(
            df_result["commits_after"],
            df_result["commits_before"],
            alternative="two-sided"
        )
        wilcoxon_stat = wilcoxon_result.statistic
        wilcoxon_p = wilcoxon_result.pvalue
    else:
        wilcoxon_stat = np.nan
        wilcoxon_p = np.nan

    if N > 1:
        ttest_result = ttest_rel(
            df_result["commits_after"],
            df_result["commits_before"]
        )
        ttest_stat = ttest_result.statistic
        ttest_p = ttest_result.pvalue
    else:
        ttest_stat = np.nan
        ttest_p = np.nan

    # =========================
    # 結果表示
    # =========================

    print(f"\n===== RQ2: Commit Activity Around Open Collective Registration ({window_months} months) =====")
    print(f"N analyzed: {N}")

    print("\n--- Before / After commits ---")
    print(f"Mean commits before {label}: {mean_before:.3f}")
    print(f"Median commits before {label}: {median_before:.3f}")
    print(f"Mean commits after {label}: {mean_after:.3f}")
    print(f"Median commits after {label}: {median_after:.3f}")

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
    # CSV保存
    # =========================

    result_filename = f"rq2_commit_change_around_opencollective_registration_{label}.csv"
    summary_filename = f"rq2_commit_change_summary_{label}.csv"

    df_result.to_csv(result_filename, index=False)

    summary = pd.DataFrame([{
        "window_months": window_months,
        "n_analyzed": N,
        "mean_commits_before": mean_before,
        "median_commits_before": median_before,
        "mean_commits_after": mean_after,
        "median_commits_after": median_after,
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

    summary.to_csv(summary_filename, index=False)

    return df_result, summary


# =========================
# 7. 3ヶ月・6ヶ月・12ヶ月で分析
# =========================

all_summaries = []
all_results = []

for window_months in [3, 6, 12]:
    df_result, summary = analyze_commit_change(window_months)

    all_results.append(df_result)
    all_summaries.append(summary)

# =========================
# 8. 全期間のsummaryをまとめて保存
# =========================

df_all_summaries = pd.concat(all_summaries, ignore_index=True)
df_all_results = pd.concat(all_results, ignore_index=True)

df_all_summaries.to_csv("rq2_commit_change_summary_all_windows.csv", index=False)
df_all_results.to_csv("rq2_commit_change_all_windows.csv", index=False)

print("\n===== Summary across all windows =====")
print(df_all_summaries)
