import api
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
from forex_python.converter import CurrencyRates
from scipy.stats import mannwhitneyu

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
WINDOW_MONTHS_LIST = [6, 12]
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

# 0-30%, 30-60%, 60-100% にビン分け
bins, labels = [0.0, 0.3, 0.6, 1.0], ["0-30%", "30-60%", "60-100%"]

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
# 3. Open Collective 登録前後6ヶ月・12ヶ月のコミット数を計算
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

print("\n===== Commit analysis base target =====")
print("Matched projects:", len(df_matched))

commits_by_repo = {
    repo_name: group["commit_time"].sort_values().reset_index(drop=True)
    for repo_name, group in df_commits.groupby("repo_name")
}


# ============================================================
# 4. 統計検定用関数
# ============================================================

def cliffs_delta(x, y):
    """
    Cliff's delta を計算する。
    x > y の割合 - x < y の割合。
    """
    x = np.asarray(x)
    y = np.asarray(y)

    n_x = len(x)
    n_y = len(y)

    greater = 0
    less = 0

    for x_i in x:
        greater += np.sum(x_i > y)
        less += np.sum(x_i < y)

    return (greater - less) / (n_x * n_y)


def test_growth_rate_between_bins(
    df,
    bin_col,
    value_col="growth_rate_pct",
    window_months=None
):
    """
    0-30% と 30-60% の growth_rate_pct を比較する。
    """

    group_low = (
        df.loc[df[bin_col] == "0-30%", value_col]
        .dropna()
    )

    group_mid = (
        df.loc[df[bin_col] == "30-60%", value_col]
        .dropna()
    )

    title_suffix = f" ({window_months}m)" if window_months is not None else ""
    print(f"\n===== Mann-Whitney U test: {bin_col}{title_suffix} =====")

    print("0-30%:")
    print(f"  n      = {len(group_low)}")
    print(f"  median = {group_low.median():.3f}")
    print(f"  mean   = {group_low.mean():.3f}")
    print(f"  q1     = {group_low.quantile(0.25):.3f}")
    print(f"  q3     = {group_low.quantile(0.75):.3f}")

    print("30-60%:")
    print(f"  n      = {len(group_mid)}")
    print(f"  median = {group_mid.median():.3f}")
    print(f"  mean   = {group_mid.mean():.3f}")
    print(f"  q1     = {group_mid.quantile(0.25):.3f}")
    print(f"  q3     = {group_mid.quantile(0.75):.3f}")

    if len(group_low) == 0 or len(group_mid) == 0:
        print("Skipping test because one of the groups is empty.")
        return {
            "window_months": window_months,
            "bin_col": bin_col,
            "n_0_30": len(group_low),
            "n_30_60": len(group_mid),
            "median_0_30": np.nan,
            "median_30_60": np.nan,
            "mean_0_30": np.nan,
            "mean_30_60": np.nan,
            "q1_0_30": np.nan,
            "q3_0_30": np.nan,
            "q1_30_60": np.nan,
            "q3_30_60": np.nan,
            "mannwhitney_u_greater": np.nan,
            "mannwhitney_p_greater": np.nan,
            "mannwhitney_u_two_sided": np.nan,
            "mannwhitney_p_two_sided": np.nan,
            "cliffs_delta": np.nan,
            "effect_size_label": "NA",
        }

    u_result_greater = mannwhitneyu(
        group_mid,
        group_low,
        alternative="greater"
    )

    u_result_two_sided = mannwhitneyu(
        group_mid,
        group_low,
        alternative="two-sided"
    )

    delta = cliffs_delta(group_mid, group_low)

    print("\nMann-Whitney U test")
    print(f"  U statistic, greater   = {u_result_greater.statistic:.3f}")
    print(f"  p-value, greater       = {u_result_greater.pvalue:.6f}")
    print(f"  U statistic, two-sided = {u_result_two_sided.statistic:.3f}")
    print(f"  p-value, two-sided     = {u_result_two_sided.pvalue:.6f}")

    print("\nEffect size")
    print(f"  Cliff's delta = {delta:.3f}")

    if abs(delta) < 0.147:
        effect_size_label = "negligible"
    elif abs(delta) < 0.33:
        effect_size_label = "small"
    elif abs(delta) < 0.474:
        effect_size_label = "medium"
    else:
        effect_size_label = "large"

    print(f"  Effect size label = {effect_size_label}")

    return {
        "window_months": window_months,
        "bin_col": bin_col,
        "n_0_30": len(group_low),
        "n_30_60": len(group_mid),
        "median_0_30": group_low.median(),
        "median_30_60": group_mid.median(),
        "mean_0_30": group_low.mean(),
        "mean_30_60": group_mid.mean(),
        "q1_0_30": group_low.quantile(0.25),
        "q3_0_30": group_low.quantile(0.75),
        "q1_30_60": group_mid.quantile(0.25),
        "q3_30_60": group_mid.quantile(0.75),
        "mannwhitney_u_greater": u_result_greater.statistic,
        "mannwhitney_p_greater": u_result_greater.pvalue,
        "mannwhitney_u_two_sided": u_result_two_sided.statistic,
        "mannwhitney_p_two_sided": u_result_two_sided.pvalue,
        "cliffs_delta": delta,
        "effect_size_label": effect_size_label,
    }


def summarize_by_bin(df, bin_col):
    """
    ビンごとの growth_rate_pct の記述統計を返す。
    """
    return (
        df
        .groupby(bin_col, observed=False)
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
            mean_total_expense_amount_usd=("total_expense_amount_usd", "mean"),
            median_total_expense_amount_usd=("total_expense_amount_usd", "median"),
            mean_development_expense_amount_usd=("development_expense_amount_usd", "mean"),
            median_development_expense_amount_usd=("development_expense_amount_usd", "median"),
        )
        .reset_index()
    )


def save_boxplot(
    df,
    bin_col,
    filename,
    xlabel,
    title,
    labels,
    y_quantile_min=0.01,
    y_quantile_max=0.95
):
    """
    growth_rate_pct の箱ひげ図を保存する。
    """

    plot_data = [
        df.loc[df[bin_col] == label, "growth_rate_pct"].dropna()
        for label in labels
    ]

    valid_growth_rates = df["growth_rate_pct"].dropna()
    y_min = valid_growth_rates.quantile(y_quantile_min)
    y_max = valid_growth_rates.quantile(y_quantile_max)

    plt.figure(figsize=(10, 6))

    plt.boxplot(
        plot_data,
        tick_labels=labels,
        showmeans=True,
        showfliers=False
    )

    plt.axhline(
        y=0,
        linestyle="--",
        linewidth=1
    )

    plt.ylim(y_min, y_max)

    plt.xlabel(xlabel)
    plt.ylabel("Commit growth rate (%)")
    plt.title(title)
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    plt.savefig(filename, dpi=300)
    plt.show()

    print(f"Saved figure: {filename}")


# ============================================================
# 5. 前後6ヶ月・12ヶ月の分析を実行
# ============================================================

all_test_results = []
all_count_summaries = []
all_amount_summaries = []
all_analysis_results = []

for window_months in WINDOW_MONTHS_LIST:
    label = f"{window_months}m"

    print(f"\n\n===== Window: {window_months} months =====")

    df_window = df_matched.copy()

    df_window["before_start"] = (
        df_window["created_at"] - pd.DateOffset(months=window_months)
    )
    df_window["before_end"] = df_window["created_at"]
    df_window["after_start"] = df_window["created_at"]
    df_window["after_end"] = (
        df_window["created_at"] + pd.DateOffset(months=window_months)
    )

    df_analyzable = df_window[
        (df_window["before_start"] >= commit_data_start) &
        (df_window["after_end"] <= commit_data_end)
    ].copy()

    print("Analyzable projects:", len(df_analyzable))

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

        if commits_before == 0:
            growth_rate_pct = np.nan
        else:
            growth_rate_pct = (
                (commits_after - commits_before) / commits_before
            ) * 100

        commit_results.append({
            "id": row.id,
            "name": row.name,
            "slug": row.slug,
            "github_account": row.github_account,
            "repo_name": row.repo_name,
            "created_at": row.created_at,
            "window_months": window_months,
            f"commits_before_{label}": commits_before,
            f"commits_after_{label}": commits_after,
            "commits_before": commits_before,
            "commits_after": commits_after,
            "growth_rate_pct": growth_rate_pct,
        })

        if idx % 100 == 0 or idx == len(df_analyzable):
            print(f"Processed {idx} / {len(df_analyzable)} projects")

    df_commit_change = pd.DataFrame(commit_results)

    df_analysis = df_commit_change.merge(
        df_project_spending,
        left_on="slug",
        right_on=PROJECT_COL,
        how="inner"
    )

    df_analysis = df_analysis[
        df_analysis["development_count_ratio_bin"].notna()
    ].copy()

    n_growth_rate_nan = df_analysis["growth_rate_pct"].isna().sum()

    print("\n===== Merged analysis data =====")
    print("Projects used in final analysis:", len(df_analysis))
    print("Projects with commits_before = 0 excluded from growth rate stats:", n_growth_rate_nan)
    print("Projects with valid growth_rate_pct:", df_analysis["growth_rate_pct"].notna().sum())

    # ========================================================
    # 統計検定
    # ========================================================

    all_test_results.append(
        test_growth_rate_between_bins(
            df_analysis,
            bin_col="development_count_ratio_bin",
            window_months=window_months
        )
    )

    all_test_results.append(
        test_growth_rate_between_bins(
            df_analysis,
            bin_col="development_amount_ratio_bin",
            window_months=window_months
        )
    )

    # ========================================================
    # 記述統計
    # ========================================================

    df_box_summary = summarize_by_bin(
        df_analysis,
        bin_col="development_count_ratio_bin"
    )
    df_box_summary["window_months"] = window_months

    print(f"\n===== Growth rate (%) summary by development count ratio bin ({label}) =====")
    print(df_box_summary.to_string(index=False))

    df_amount_box_summary = summarize_by_bin(
        df_analysis,
        bin_col="development_amount_ratio_bin"
    )
    df_amount_box_summary["window_months"] = window_months

    print(f"\n===== Growth rate (%) summary by development amount ratio bin ({label}) =====")
    print(df_amount_box_summary.to_string(index=False))

    all_count_summaries.append(df_box_summary)
    all_amount_summaries.append(df_amount_box_summary)
    all_analysis_results.append(df_analysis)

    # ========================================================
    # CSV保存
    # ========================================================

    df_analysis.to_csv(
        f"rq2_development_ratio_and_commit_growth_rate_pct_project_level_{label}.csv",
        index=False
    )

    df_box_summary.to_csv(
        f"rq2_development_count_ratio_and_commit_growth_rate_pct_boxplot_summary_{label}.csv",
        index=False
    )

    df_amount_box_summary.to_csv(
        f"rq2_development_amount_ratio_and_commit_growth_rate_pct_boxplot_summary_{label}.csv",
        index=False
    )

    # ========================================================
    # 箱ひげ図保存：回数ベース
    # ========================================================

    save_boxplot(
        df=df_analysis,
        bin_col="development_count_ratio_bin",
        filename=f"rq2_boxplot_commit_growth_rate_pct_by_development_expense_count_ratio_{label}.png",
        xlabel="Share of expenses classified as development",
        title=f"Commit growth rate by development expense count ratio ({window_months} months)",
        labels=labels
    )

    # ========================================================
    # 箱ひげ図保存：金額ベース
    # ========================================================

    save_boxplot(
        df=df_analysis,
        bin_col="development_amount_ratio_bin",
        filename=f"rq2_boxplot_commit_growth_rate_pct_by_development_expense_amount_ratio_{label}.png",
        xlabel="Share of expense amount classified as development",
        title=f"Commit growth rate by development expense amount ratio ({window_months} months)",
        labels=labels
    )


# ============================================================
# 6. 全windowの結果をまとめて保存
# ============================================================

df_test_results = pd.DataFrame(all_test_results)
df_count_summaries_all = pd.concat(all_count_summaries, ignore_index=True)
df_amount_summaries_all = pd.concat(all_amount_summaries, ignore_index=True)
df_analysis_all = pd.concat(all_analysis_results, ignore_index=True)

print("\n===== Summary of statistical tests across windows =====")
print(df_test_results.to_string(index=False))

df_test_results.to_csv(
    "rq2_growth_rate_mannwhitney_0_30_vs_30_60_all_windows.csv",
    index=False
)

df_count_summaries_all.to_csv(
    "rq2_development_count_ratio_and_commit_growth_rate_pct_boxplot_summary_all_windows.csv",
    index=False
)

df_amount_summaries_all.to_csv(
    "rq2_development_amount_ratio_and_commit_growth_rate_pct_boxplot_summary_all_windows.csv",
    index=False
)

df_analysis_all.to_csv(
    "rq2_development_ratio_and_commit_growth_rate_pct_project_level_all_windows.csv",
    index=False
)

