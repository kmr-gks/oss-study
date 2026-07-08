import api
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
from matplotlib.ticker import MaxNLocator

# =========================
# 設定
# =========================

DB_NAME = "opencollective"

ITEM_TABLE = "public.github_issue_pr_items"

OUTPUT_PROJECT_MONTHLY_CSV = "github_issue_pr_monthly_counts_project_level_from_sql.csv"
OUTPUT_SUMMARY_CSV = "github_issue_pr_monthly_counts_summary_from_sql.csv"

OUTPUT_FIG_OPENED_ISSUES_PDF = "github_opened_issues_monthly_around_opencollective.pdf"
OUTPUT_FIG_OPENED_PRS_PDF = "github_opened_pull_requests_monthly_around_opencollective.pdf"
OUTPUT_FIG_CLOSED_ISSUES_PDF = "github_closed_issues_monthly_around_opencollective.pdf"
OUTPUT_FIG_MERGED_PRS_PDF = "github_merged_pull_requests_monthly_around_opencollective.pdf"
OUTPUT_FIG_ALL_MEAN_MEDIAN_PDF = "github_issue_pr_monthly_all_mean_median_around_opencollective.pdf"

RELATIVE_MONTHS = list(range(-12, 12))  # -12 ... -1, 0 ... 11

# =========================
# DB接続
# =========================

engine = create_engine(
    f"postgresql+psycopg2://postgres:{api.load_sql_password_from_credentials()}@localhost:5432/{DB_NAME}"
)

# =========================
# 1. SQLから取得済みデータを読み込む
# =========================

query_items = f"""
SELECT
    collective_id,
    project_slug,
    project_name,
    repo_name,
    github_account,
    item_type,
    number,
    created_at,
    closed_at,
    merged_at,
    state,
    is_merged,
    opencollective_created_at
FROM {ITEM_TABLE}
WHERE repo_name IS NOT NULL
  AND github_account IS NOT NULL
  AND opencollective_created_at IS NOT NULL
"""

df_items = pd.read_sql(query_items, engine)

print("Loaded issue/PR item rows:", len(df_items))

if len(df_items) == 0:
    raise ValueError("github_issue_pr_items にデータがありません。")

# =========================
# 2. datetime変換
# =========================

datetime_cols = [
    "created_at",
    "closed_at",
    "merged_at",
    "opencollective_created_at",
]

for col in datetime_cols:
    df_items[col] = pd.to_datetime(
        df_items[col],
        utc=True,
        errors="coerce"
    ).dt.tz_convert(None)

df_items = df_items[
    df_items["opencollective_created_at"].notna()
].copy()

print("Rows after datetime cleaning:", len(df_items))

# =========================
# 3. 現時点で取得済みのプロジェクト一覧を作る
# =========================
# 注意:
# この方法では、Issue/PRが1件以上あるrepoのみが対象になる。
# Issue/PRが0件の取得済みrepoを含めたい場合は、取得完了repoテーブルを別途作る必要がある。

df_projects = (
    df_items[
        [
            "collective_id",
            "project_slug",
            "project_name",
            "repo_name",
            "github_account",
            "opencollective_created_at",
        ]
    ]
    .drop_duplicates()
    .copy()
)

print("\n===== Project scope =====")
print("Projects with at least one issue/PR item:", len(df_projects))
print("Unique repos:", df_projects["repo_name"].nunique())

# =========================
# 4. プロジェクト × relative_month の24か月枠を作る
# =========================

monthly_rows = []

for idx, row in enumerate(df_projects.itertuples(index=False), start=1):
    project_items = df_items[
        df_items["collective_id"] == row.collective_id
    ].copy()

    oc_date = row.opencollective_created_at

    for relative_month in RELATIVE_MONTHS:
        month_start = oc_date + pd.DateOffset(months=relative_month)
        month_end = oc_date + pd.DateOffset(months=relative_month + 1)

        created_in_month = project_items[
            (project_items["created_at"] >= month_start)
            & (project_items["created_at"] < month_end)
        ]

        closed_in_month = project_items[
            (project_items["closed_at"] >= month_start)
            & (project_items["closed_at"] < month_end)
        ]

        merged_in_month = project_items[
            (project_items["merged_at"] >= month_start)
            & (project_items["merged_at"] < month_end)
        ]

        opened_issues = (
            created_in_month["item_type"].eq("issue").sum()
        )

        opened_pull_requests = (
            created_in_month["item_type"].eq("pull_request").sum()
        )

        closed_issues = (
            closed_in_month["item_type"].eq("issue").sum()
        )

        closed_pull_requests = (
            closed_in_month["item_type"].eq("pull_request").sum()
        )

        merged_pull_requests = (
            merged_in_month["item_type"].eq("pull_request").sum()
        )

        monthly_rows.append({
            "collective_id": row.collective_id,
            "project_slug": row.project_slug,
            "project_name": row.project_name,
            "repo_name": row.repo_name,
            "github_account": row.github_account,
            "opencollective_created_at": oc_date,
            "relative_month": relative_month,
            "period": "before" if relative_month < 0 else "after",
            "month_start": month_start,
            "month_end": month_end,
            "opened_issues": int(opened_issues),
            "closed_issues": int(closed_issues),
            "opened_pull_requests": int(opened_pull_requests),
            "closed_pull_requests": int(closed_pull_requests),
            "merged_pull_requests": int(merged_pull_requests),
        })

    if idx % 100 == 0 or idx == len(df_projects):
        print(f"Processed {idx} / {len(df_projects)} projects")

df_monthly = pd.DataFrame(monthly_rows)

# =========================
# 5. relative_monthごとの平均・中央値を計算
# =========================

df_summary = (
    df_monthly
    .groupby("relative_month")
    .agg(
        mean_opened_issues=("opened_issues", "mean"),
        median_opened_issues=("opened_issues", "median"),
        mean_closed_issues=("closed_issues", "mean"),
        median_closed_issues=("closed_issues", "median"),

        mean_opened_pull_requests=("opened_pull_requests", "mean"),
        median_opened_pull_requests=("opened_pull_requests", "median"),
        mean_closed_pull_requests=("closed_pull_requests", "mean"),
        median_closed_pull_requests=("closed_pull_requests", "median"),

        mean_merged_pull_requests=("merged_pull_requests", "mean"),
        median_merged_pull_requests=("merged_pull_requests", "median"),

        n_projects=("repo_name", "count"),
    )
    .reset_index()
)

# 表示用:
# relative_month 0 は登録後1か月目として 1 に表示する
df_summary["plot_month"] = df_summary["relative_month"].apply(
    lambda x: x if x < 0 else x + 1
)

print("\n===== Monthly summary =====")
print(df_summary.to_string(index=False))

# =========================
# 6. CSV保存
# =========================

df_monthly.to_csv(OUTPUT_PROJECT_MONTHLY_CSV, index=False)
df_summary.to_csv(OUTPUT_SUMMARY_CSV, index=False)

print("\nSaved:")
print(OUTPUT_PROJECT_MONTHLY_CSV)
print(OUTPUT_SUMMARY_CSV)

# =========================
# 7. グラフ関数
# =========================

def plot_mean_median(
    df_summary,
    mean_col,
    median_col,
    ylabel,
    title,
    output_path
):
    plt.figure(figsize=(5, 3.5))

    plt.plot(
        df_summary["plot_month"],
        df_summary[mean_col],
        marker="o",
        label="Mean"
    )

    plt.plot(
        df_summary["plot_month"],
        df_summary[median_col],
        marker="o",
        label="Median"
    )

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
    plt.ylabel(ylabel)
    plt.title(title)

    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.gca().xaxis.set_major_locator(MaxNLocator(integer=True))

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches="tight")
    plt.show()

    print("Saved figure:", output_path)

# =========================
# 8. 個別グラフ
# =========================

plot_mean_median(
    df_summary=df_summary,
    mean_col="mean_opened_issues",
    median_col="median_opened_issues",
    ylabel="Monthly opened issue count",
    title="Opened issues around Open Collective registration",
    output_path=OUTPUT_FIG_OPENED_ISSUES_PDF,
)

plot_mean_median(
    df_summary=df_summary,
    mean_col="mean_closed_issues",
    median_col="median_closed_issues",
    ylabel="Monthly closed issue count",
    title="Closed issues around Open Collective registration",
    output_path=OUTPUT_FIG_CLOSED_ISSUES_PDF,
)

plot_mean_median(
    df_summary=df_summary,
    mean_col="mean_opened_pull_requests",
    median_col="median_opened_pull_requests",
    ylabel="Monthly opened pull request count",
    title="Opened pull requests around Open Collective registration",
    output_path=OUTPUT_FIG_OPENED_PRS_PDF,
)

plot_mean_median(
    df_summary=df_summary,
    mean_col="mean_merged_pull_requests",
    median_col="median_merged_pull_requests",
    ylabel="Monthly merged pull request count",
    title="Merged pull requests around Open Collective registration",
    output_path=OUTPUT_FIG_MERGED_PRS_PDF,
)

# =========================
# 9. 1枚にまとめたグラフ
#    4種類の指標 × mean/median = 8本の線
# =========================

plt.figure(figsize=(8.0, 4.8))

# Issues: opened
plt.plot(
    df_summary["plot_month"],
    df_summary["mean_opened_issues"],
    marker="o",
    label="Mean opened issues"
)

plt.plot(
    df_summary["plot_month"],
    df_summary["median_opened_issues"],
    marker="o",
    linestyle="--",
    label="Median opened issues"
)

# Issues: closed
plt.plot(
    df_summary["plot_month"],
    df_summary["mean_closed_issues"],
    marker="s",
    linestyle="-",
    label="Mean closed issues"
)

plt.plot(
    df_summary["plot_month"],
    df_summary["median_closed_issues"],
    marker="s",
    linestyle="--",
    label="Median closed issues"
)

# PRs: opened
plt.plot(
    df_summary["plot_month"],
    df_summary["mean_opened_pull_requests"],
    marker="^",
    linestyle="-",
    label="Mean opened PRs"
)

plt.plot(
    df_summary["plot_month"],
    df_summary["median_opened_pull_requests"],
    marker="^",
    linestyle="--",
    label="Median opened PRs"
)

# PRs: merged
plt.plot(
    df_summary["plot_month"],
    df_summary["mean_merged_pull_requests"],
    marker="D",
    linestyle="-",
    label="Mean merged PRs"
)

plt.plot(
    df_summary["plot_month"],
    df_summary["median_merged_pull_requests"],
    marker="D",
    linestyle="--",
    label="Median merged PRs"
)

# Open Collective 登録タイミング
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
plt.ylabel("Monthly count")
plt.title("Issue and pull request activity around Open Collective registration")

plt.legend(
    fontsize=8,
    ncol=2,
    loc="upper right"
)

plt.grid(True, alpha=0.3)
plt.gca().xaxis.set_major_locator(MaxNLocator(integer=True))

plt.tight_layout()

plt.savefig(
    OUTPUT_FIG_ALL_MEAN_MEDIAN_PDF,
    bbox_inches="tight"
)

plt.show()

print("Saved figure:", OUTPUT_FIG_ALL_MEAN_MEDIAN_PDF)
