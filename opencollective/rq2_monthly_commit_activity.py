import api
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
from scipy.stats import wilcoxon, ttest_rel
from matplotlib.ticker import MaxNLocator

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
# 8.6 加入前12ヶ月平均 vs 加入後1/3/6/12ヶ月平均の統計検定
# =========================

from scipy.stats import wilcoxon, ttest_rel

# 各プロジェクト × relative_month の形を横持ちにする
df_monthly_wide = (
    df_monthly
    .pivot_table(
        index=["id", "repo_name"],
        columns="relative_month",
        values="commit_count",
        aggfunc="sum"
    )
    .reset_index()
)

# 加入前12ヶ月: relative_month -12 〜 -1
before_months = list(range(-12, 0))

# 加入後の比較窓
# after 1m  : relative_month 0
# after 3m  : relative_month 0, 1, 2
# after 6m  : relative_month 0〜5
# after 12m : relative_month 0〜11
after_windows = {
    1: list(range(0, 1)),
    3: list(range(0, 3)),
    6: list(range(0, 6)),
    12: list(range(0, 12)),
}

# 加入前12ヶ月の月平均
df_monthly_wide["before_12m_total"] = df_monthly_wide[before_months].sum(axis=1)
df_monthly_wide["before_12m_monthly_avg"] = (
    df_monthly_wide["before_12m_total"] / 12
)

test_results = []

for after_months, months in after_windows.items():
    after_total_col = f"after_{after_months}m_total"
    after_avg_col = f"after_{after_months}m_monthly_avg"
    diff_col = f"diff_after_{after_months}m_avg_minus_before_12m_avg"
    log_change_col = f"log_change_after_{after_months}m_avg_vs_before_12m_avg"

    # 加入後Nヶ月の合計・月平均
    df_monthly_wide[after_total_col] = df_monthly_wide[months].sum(axis=1)
    df_monthly_wide[after_avg_col] = (
        df_monthly_wide[after_total_col] / after_months
    )

    # 差分
    df_monthly_wide[diff_col] = (
        df_monthly_wide[after_avg_col] -
        df_monthly_wide["before_12m_monthly_avg"]
    )

    # log change
    df_monthly_wide[log_change_col] = (
        np.log1p(df_monthly_wide[after_avg_col]) -
        np.log1p(df_monthly_wide["before_12m_monthly_avg"])
    )

    df_test = df_monthly_wide[
        [
            "id",
            "repo_name",
            "before_12m_total",
            "before_12m_monthly_avg",
            after_total_col,
            after_avg_col,
            diff_col,
            log_change_col,
        ]
    ].dropna().copy()

    print(f"\n===== Statistical test: before 12m monthly avg vs after {after_months}m monthly avg =====")
    print("N projects:", len(df_test))

    print("\n--- Descriptive statistics ---")
    print("Mean before 12m monthly avg:", df_test["before_12m_monthly_avg"].mean())
    print("Median before 12m monthly avg:", df_test["before_12m_monthly_avg"].median())
    print(f"Mean after {after_months}m monthly avg:", df_test[after_avg_col].mean())
    print(f"Median after {after_months}m monthly avg:", df_test[after_avg_col].median())
    print("Mean diff:", df_test[diff_col].mean())
    print("Median diff:", df_test[diff_col].median())
    print("Mean log_change:", df_test[log_change_col].mean())
    print("Median log_change:", df_test[log_change_col].median())

    # Wilcoxon signed-rank test
    # 主検定: after の月平均が before 12m 月平均より高いか
    if (df_test[diff_col] != 0).any():
        wilcoxon_two_sided = wilcoxon(
            df_test[after_avg_col],
            df_test["before_12m_monthly_avg"],
            alternative="two-sided"
        )

        wilcoxon_greater = wilcoxon(
            df_test[after_avg_col],
            df_test["before_12m_monthly_avg"],
            alternative="greater"
        )

        wilcoxon_less = wilcoxon(
            df_test[after_avg_col],
            df_test["before_12m_monthly_avg"],
            alternative="less"
        )

        print("\n--- Wilcoxon signed-rank test ---")
        print("Two-sided statistic:", wilcoxon_two_sided.statistic)
        print("Two-sided p-value:", wilcoxon_two_sided.pvalue)
        print(f"Greater p-value, after {after_months}m avg > before 12m avg:", wilcoxon_greater.pvalue)
        print(f"Less p-value, after {after_months}m avg < before 12m avg:", wilcoxon_less.pvalue)
    else:
        wilcoxon_two_sided = None
        wilcoxon_greater = None
        wilcoxon_less = None

        print("\n--- Wilcoxon signed-rank test ---")
        print("Skipped because all differences are zero.")

    # Paired t-test
    # 平均差の検定。外れ値の影響が大きいため補助的に使う
    ttest_result = ttest_rel(
        df_test[after_avg_col],
        df_test["before_12m_monthly_avg"]
    )

    print("\n--- Paired t-test ---")
    print("t statistic:", ttest_result.statistic)
    print("p-value:", ttest_result.pvalue)

    # 増加・減少プロジェクト数
    increased = (df_test[after_avg_col] > df_test["before_12m_monthly_avg"]).sum()
    decreased = (df_test[after_avg_col] < df_test["before_12m_monthly_avg"]).sum()
    unchanged = (df_test[after_avg_col] == df_test["before_12m_monthly_avg"]).sum()

    print("\n--- Direction of change ---")
    print("Increased:", increased, f"({increased / len(df_test):.2%})")
    print("Decreased:", decreased, f"({decreased / len(df_test):.2%})")
    print("Unchanged:", unchanged, f"({unchanged / len(df_test):.2%})")

    test_results.append({
        "after_months": after_months,
        "n_projects": len(df_test),
        "mean_before_12m_monthly_avg": df_test["before_12m_monthly_avg"].mean(),
        "median_before_12m_monthly_avg": df_test["before_12m_monthly_avg"].median(),
        "mean_after_monthly_avg": df_test[after_avg_col].mean(),
        "median_after_monthly_avg": df_test[after_avg_col].median(),
        "mean_diff": df_test[diff_col].mean(),
        "median_diff": df_test[diff_col].median(),
        "mean_log_change": df_test[log_change_col].mean(),
        "median_log_change": df_test[log_change_col].median(),
        "wilcoxon_statistic_two_sided": (
            wilcoxon_two_sided.statistic if wilcoxon_two_sided is not None else np.nan
        ),
        "wilcoxon_p_two_sided": (
            wilcoxon_two_sided.pvalue if wilcoxon_two_sided is not None else np.nan
        ),
        "wilcoxon_p_greater": (
            wilcoxon_greater.pvalue if wilcoxon_greater is not None else np.nan
        ),
        "wilcoxon_p_less": (
            wilcoxon_less.pvalue if wilcoxon_less is not None else np.nan
        ),
        "paired_t_statistic": ttest_result.statistic,
        "paired_t_p_value": ttest_result.pvalue,
        "increased_count": increased,
        "decreased_count": decreased,
        "unchanged_count": unchanged,
        "increase_rate": increased / len(df_test),
        "decrease_rate": decreased / len(df_test),
        "unchanged_rate": unchanged / len(df_test),
    })

df_short_term_tests = pd.DataFrame(test_results)

print("\n===== Summary: before 12m monthly avg vs after short-term monthly avg =====")
print(df_short_term_tests.to_string(index=False))

df_short_term_tests.to_csv(
    "rq2_commit_before12m_avg_vs_after_1_3_6_12m_avg_statistical_tests.csv",
    index=False
)

df_monthly_wide.to_csv(
    "rq2_commit_before12m_avg_vs_after_1_3_6_12m_avg_project_level.csv",
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

plt.figure(figsize=(5,3.5))

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
#plt.title("Monthly commit activity before and after Open Collective registration")
plt.legend()
plt.grid(True, alpha=0.3)

plt.gca().xaxis.set_major_locator(MaxNLocator(integer=True))

plt.tight_layout()

plt.savefig(
    "rq3_monthly_commits_around_opencollective_registration_mean_median.pdf",
    bbox_inches="tight"
)

plt.show()
