from functools import reduce

import api
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from forex_python.converter import CurrencyRates
from scipy.stats import mannwhitneyu
from sqlalchemy import create_engine


PROJECT_COL = "project_slug"
CONFIDENCE_THRESHOLD = 0.9
WINDOW_MONTHS_LIST = [6, 12]
BASE_CURRENCY = "USD"

CSV_FILES = [f"predictions_2nd_all_devornot_{i}.csv" for i in range(1, 6)]
RATIO_BINS = [0.0, 0.3, 0.6, 1.0]
RATIO_LABELS = ["0-30%", "30-60%", "60-100%"]

REQUIRED_EXPENSE_COLS = {
    "index",
    "expense_description",
    "predicted_label",
    "confidence",
    PROJECT_COL,
    "amount_value",
    "amount_currency",
}

PROJECT_SUMMARY_COLS = [
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

RATIO_ANALYSES = [
    (
        "development_count_ratio_bin",
        "count",
        "development_expense_count_ratio",
        "Share of expenses classified as development",
        "development expense count ratio",
    ),
    (
        "development_amount_ratio_bin",
        "amount",
        "development_expense_amount_ratio",
        "Share of expense amount classified as development",
        "development expense amount ratio",
    ),
]

STAT_FUNCS = [
    ("median", lambda s: s.median()),
    ("mean", lambda s: s.mean()),
    ("q1", lambda s: s.quantile(0.25)),
    ("q3", lambda s: s.quantile(0.75)),
]

COLLECTIVES_SQL = """
SELECT id, name, slug, type, created_at, github_account
FROM public.collectives
WHERE github_account IS NOT NULL
"""

COMMIT_HISTORY_SQL = """
SELECT repo_name, commit_time
FROM public.commit_history
WHERE repo_name IS NOT NULL
  AND commit_time IS NOT NULL
"""


def clean_text(series, lower=False):
    result = series.astype(str).str.strip()
    return result.str.lower() if lower else result.str.upper()


def database_engine():
    password = api.load_sql_password_from_credentials()
    return create_engine(
        f"postgresql+psycopg2://postgres:{password}@localhost:5432/opencollective"
    )


def read_prediction_run(path, run_no):
    df = pd.read_csv(path)
    missing_cols = REQUIRED_EXPENSE_COLS - set(df.columns)
    if missing_cols:
        raise ValueError(f"{path} に必要な列がありません: {missing_cols}")

    flag_col = f"is_development_run{run_no}"
    df = df.copy()
    df["predicted_label"] = clean_text(df["predicted_label"], lower=True)
    df[["confidence", "amount_value"]] = df[["confidence", "amount_value"]].apply(
        pd.to_numeric,
        errors="coerce",
    )
    df[flag_col] = (
        df["predicted_label"].eq("development")
        & df["confidence"].ge(CONFIDENCE_THRESHOLD)
    )

    cols = ["index", PROJECT_COL, "amount_value", "amount_currency", flag_col]
    if run_no == 1:
        cols.insert(1, "expense_description")
        return df[cols]

    return df[cols].rename(
        columns={
            PROJECT_COL: f"{PROJECT_COL}_run{run_no}",
            "amount_value": f"amount_value_run{run_no}",
            "amount_currency": f"amount_currency_run{run_no}",
        }
    )


def load_expense_predictions(paths):
    dfs = [read_prediction_run(path, i) for i, path in enumerate(paths, start=1)]
    df_expense = reduce(
        lambda left, right: left.merge(
            right,
            on="index",
            how="inner",
            validate="one_to_one",
        ),
        dfs,
    )

    for i in range(2, len(paths) + 1):
        project_mismatches = df_expense[PROJECT_COL].ne(
            df_expense[f"{PROJECT_COL}_run{i}"]
        ).sum()
        if project_mismatches:
            raise ValueError(
                f"run{i} で project_slug が一致しない行があります: "
                f"{project_mismatches} rows"
            )

        amount_mismatches = df_expense["amount_value"].fillna("__NA__").astype(
            str
        ).ne(
            df_expense[f"amount_value_run{i}"].fillna("__NA__").astype(str)
        ).sum()
        if amount_mismatches:
            print(
                f"Warning: run{i} で amount_value が一致しない行があります: "
                f"{amount_mismatches} rows"
            )

    print("\n===== Amount currency distribution in run1 =====")
    print(df_expense["amount_currency"].value_counts(dropna=False))

    run_cols = [f"is_development_run{i}" for i in range(1, len(paths) + 1)]
    df_expense["is_development"] = df_expense[run_cols].all(axis=1)
    return df_expense


def fetch_exchange_rates_to_usd(currencies):
    currency_rates = CurrencyRates()
    exchange_rates = {}

    for currency in sorted(currencies):
        if currency == BASE_CURRENCY:
            exchange_rates[currency] = 1.0
            continue
        try:
            exchange_rates[currency] = currency_rates.get_rate(currency, BASE_CURRENCY)
        except Exception as e:
            print(f"Warning: failed to get exchange rate {currency} -> USD: {e}")
            exchange_rates[currency] = np.nan

    print("\n===== Exchange rates to USD =====")
    for currency, rate in exchange_rates.items():
        print(f"{currency} -> USD: {rate}")

    return exchange_rates


def add_expense_amount_usd(df_expense):
    df_expense = df_expense.copy()
    df_expense["amount_currency"] = clean_text(df_expense["amount_currency"])
    df_expense["expense_amount_original"] = df_expense["amount_value"].abs()

    df_expense = df_expense[
        df_expense["expense_amount_original"].notna()
        & df_expense["expense_amount_original"].gt(0)
        & df_expense["amount_currency"].notna()
        & df_expense["amount_currency"].ne("")
        & df_expense["amount_currency"].ne("NAN")
    ].copy()

    exchange_rates = fetch_exchange_rates_to_usd(
        df_expense["amount_currency"].dropna().unique()
    )
    df_expense["exchange_rate_to_usd"] = df_expense["amount_currency"].map(
        exchange_rates
    )

    missing_rate_rows = df_expense["exchange_rate_to_usd"].isna().sum()
    if missing_rate_rows:
        print(
            f"\nWarning: excluding rows with missing exchange rates: "
            f"{missing_rate_rows}"
        )

    df_expense = df_expense[df_expense["exchange_rate_to_usd"].notna()].copy()
    df_expense["expense_amount_usd"] = (
        df_expense["expense_amount_original"] * df_expense["exchange_rate_to_usd"]
    )

    print("\n===== Expense amount summary =====")
    print("Total expense rows:", len(df_expense))
    print("Total expense amount USD:", df_expense["expense_amount_usd"].sum())
    print(
        "Development expense amount USD:",
        df_expense.loc[df_expense["is_development"], "expense_amount_usd"].sum(),
    )
    return df_expense


def build_project_spending(df_expense):
    df_expense = df_expense.assign(
        development_amount_usd=np.where(
            df_expense["is_development"],
            df_expense["expense_amount_usd"],
            0.0,
        )
    )
    df_project_spending = (
        df_expense.groupby(PROJECT_COL)
        .agg(
            total_expense_count=("index", "count"),
            development_expense_count=("is_development", "sum"),
            total_expense_amount_usd=("expense_amount_usd", "sum"),
            development_expense_amount_usd=("development_amount_usd", "sum"),
        )
        .reset_index()
    )

    df_project_spending["development_count_ratio"] = (
        df_project_spending["development_expense_count"]
        / df_project_spending["total_expense_count"]
    )
    df_project_spending["development_amount_ratio"] = (
        df_project_spending["development_expense_amount_usd"]
        / df_project_spending["total_expense_amount_usd"]
    )

    for ratio_col in ["development_count_ratio", "development_amount_ratio"]:
        df_project_spending[f"{ratio_col}_bin"] = pd.cut(
            df_project_spending[ratio_col],
            bins=RATIO_BINS,
            labels=RATIO_LABELS,
            include_lowest=True,
            right=True,
        )

    print("\n===== Project development ratio summary =====")
    print("Projects with expense data:", len(df_project_spending))
    print(df_project_spending[PROJECT_SUMMARY_COLS].head())

    for kind in ["count", "amount"]:
        col = f"development_{kind}_ratio_bin"
        print(f"\n===== Number of projects by development {kind} ratio bin =====")
        print(df_project_spending[col].value_counts().sort_index())

    return df_project_spending


def load_commit_base(engine):
    df_collectives = pd.read_sql(COLLECTIVES_SQL, engine)
    df_commits = pd.read_sql(COMMIT_HISTORY_SQL, engine)

    df_collectives = df_collectives[
        df_collectives["github_account"].notna()
        & df_collectives["github_account"].str.contains("/", na=False)
    ].copy()
    df_collectives["repo_name"] = (
        df_collectives["github_account"].str.strip().str.replace("/", "-", regex=False)
    )
    df_collectives["created_at"] = pd.to_datetime(
        df_collectives["created_at"],
        utc=True,
    ).dt.tz_convert(None)
    df_commits["commit_time"] = pd.to_datetime(
        df_commits["commit_time"],
        utc=True,
    ).dt.tz_convert(None)

    commit_repos = set(df_commits["repo_name"].unique())
    df_matched = df_collectives[df_collectives["repo_name"].isin(commit_repos)].copy()
    commits_by_repo = {
        repo_name: group["commit_time"].sort_values().reset_index(drop=True)
        for repo_name, group in df_commits.groupby("repo_name")
    }

    print("\n===== Commit analysis base target =====")
    print("Matched projects:", len(df_matched))

    return (
        df_matched,
        commits_by_repo,
        df_commits["commit_time"].min(),
        df_commits["commit_time"].max(),
    )


def cliffs_delta(x, y):
    x = np.asarray(x)
    y = np.asarray(y)
    greater_less = (np.sum(x_i > y) - np.sum(x_i < y) for x_i in x)
    return sum(greater_less) / (len(x) * len(y))


def effect_size_label(delta):
    for threshold, label in [
        (0.147, "negligible"),
        (0.33, "small"),
        (0.474, "medium"),
    ]:
        if abs(delta) < threshold:
            return label
    return "large"


def print_group_stats(label, group):
    print(f"{label}:")
    print(f"  n      = {len(group)}")
    for name, func in STAT_FUNCS:
        print(f"  {name:<6} = {func(group):.3f}")


def stats_for_result(group_low, group_mid, include_stats=True):
    result = {"n_0_30": len(group_low), "n_30_60": len(group_mid)}
    for name, func in STAT_FUNCS:
        result[f"{name}_0_30"] = func(group_low) if include_stats else np.nan
        result[f"{name}_30_60"] = func(group_mid) if include_stats else np.nan
    return result


def test_growth_rate_between_bins(
    df,
    bin_col,
    value_col="growth_rate_pct",
    window_months=None,
):
    group_low = df.loc[df[bin_col] == "0-30%", value_col].dropna()
    group_mid = df.loc[df[bin_col] == "30-60%", value_col].dropna()

    title_suffix = f" ({window_months}m)" if window_months is not None else ""
    print(f"\n===== Mann-Whitney U test: {bin_col}{title_suffix} =====")
    print_group_stats("0-30%", group_low)
    print_group_stats("30-60%", group_mid)

    has_both_groups = len(group_low) > 0 and len(group_mid) > 0
    result = {
        "window_months": window_months,
        "bin_col": bin_col,
        **stats_for_result(group_low, group_mid, include_stats=has_both_groups),
    }

    if not has_both_groups:
        print("Skipping test because one of the groups is empty.")
        result.update(
            {
                "mannwhitney_u_greater": np.nan,
                "mannwhitney_p_greater": np.nan,
                "mannwhitney_u_two_sided": np.nan,
                "mannwhitney_p_two_sided": np.nan,
                "cliffs_delta": np.nan,
                "effect_size_label": "NA",
            }
        )
        return result

    u_result_greater = mannwhitneyu(group_mid, group_low, alternative="greater")
    u_result_two_sided = mannwhitneyu(group_mid, group_low, alternative="two-sided")
    delta = cliffs_delta(group_mid, group_low)
    label = effect_size_label(delta)

    print("\nMann-Whitney U test")
    print(f"  U statistic, greater   = {u_result_greater.statistic:.3f}")
    print(f"  p-value, greater       = {u_result_greater.pvalue:.6f}")
    print(f"  U statistic, two-sided = {u_result_two_sided.statistic:.3f}")
    print(f"  p-value, two-sided     = {u_result_two_sided.pvalue:.6f}")
    print("\nEffect size")
    print(f"  Cliff's delta = {delta:.3f}")
    print(f"  Effect size label = {label}")

    result.update(
        {
            "mannwhitney_u_greater": u_result_greater.statistic,
            "mannwhitney_p_greater": u_result_greater.pvalue,
            "mannwhitney_u_two_sided": u_result_two_sided.statistic,
            "mannwhitney_p_two_sided": u_result_two_sided.pvalue,
            "cliffs_delta": delta,
            "effect_size_label": label,
        }
    )
    return result


def summarize_by_bin(df, bin_col):
    return (
        df.groupby(bin_col, observed=False)
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
            mean_development_expense_amount_usd=(
                "development_expense_amount_usd",
                "mean",
            ),
            median_development_expense_amount_usd=(
                "development_expense_amount_usd",
                "median",
            ),
        )
        .reset_index()
    )


def save_boxplot(df, bin_col, filename, xlabel, title):
    plot_data = [
        df.loc[df[bin_col] == label, "growth_rate_pct"].dropna()
        for label in RATIO_LABELS
    ]
    valid_growth_rates = df["growth_rate_pct"].dropna()
    y_min = valid_growth_rates.quantile(0.01)
    y_max = valid_growth_rates.quantile(0.95)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.boxplot(
        plot_data,
        tick_labels=RATIO_LABELS,
        showmeans=True,
        showfliers=False,
    )
    ax.axhline(y=0, linestyle="--", linewidth=1)
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Commit growth rate (%)")
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(filename, dpi=300)
    plt.show()
    print(f"Saved figure: {filename}")


def projects_with_complete_window(
    df_matched,
    window_months,
    commit_data_start,
    commit_data_end,
):
    df_window = df_matched.copy()
    df_window["before_start"] = (
        df_window["created_at"] - pd.DateOffset(months=window_months)
    )
    df_window["before_end"] = df_window["created_at"]
    df_window["after_start"] = df_window["created_at"]
    df_window["after_end"] = (
        df_window["created_at"] + pd.DateOffset(months=window_months)
    )
    return df_window[
        df_window["before_start"].ge(commit_data_start)
        & df_window["after_end"].le(commit_data_end)
    ].copy()


def count_commits_between(repo_commits, start, end):
    return (repo_commits.ge(start) & repo_commits.lt(end)).sum()


def build_commit_change(df_analyzable, commits_by_repo, window_months):
    rows = []
    label = f"{window_months}m"
    empty_commits = pd.Series(dtype="datetime64[ns]")

    for idx, row in enumerate(df_analyzable.itertuples(index=False), start=1):
        repo_commits = commits_by_repo.get(row.repo_name, empty_commits)
        commits_before = count_commits_between(
            repo_commits,
            row.before_start,
            row.before_end,
        )
        commits_after = count_commits_between(
            repo_commits,
            row.after_start,
            row.after_end,
        )
        growth_rate_pct = (
            np.nan
            if commits_before == 0
            else (commits_after - commits_before) / commits_before * 100
        )

        rows.append(
            {
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
            }
        )

        if idx % 100 == 0 or idx == len(df_analyzable):
            print(f"Processed {idx} / {len(df_analyzable)} projects")

    return pd.DataFrame(rows)


def analyze_window(
    window_months,
    df_matched,
    commits_by_repo,
    commit_data_start,
    commit_data_end,
    df_project_spending,
):
    label = f"{window_months}m"
    print(f"\n\n===== Window: {window_months} months =====")

    df_analyzable = projects_with_complete_window(
        df_matched,
        window_months,
        commit_data_start,
        commit_data_end,
    )
    print("Analyzable projects:", len(df_analyzable))

    df_analysis = (
        build_commit_change(df_analyzable, commits_by_repo, window_months)
        .merge(df_project_spending, left_on="slug", right_on=PROJECT_COL, how="inner")
        .loc[lambda df: df["development_count_ratio_bin"].notna()]
        .copy()
    )

    print("\n===== Merged analysis data =====")
    print("Projects used in final analysis:", len(df_analysis))
    print(
        "Projects with commits_before = 0 excluded from growth rate stats:",
        df_analysis["growth_rate_pct"].isna().sum(),
    )
    print(
        "Projects with valid growth_rate_pct:",
        df_analysis["growth_rate_pct"].notna().sum(),
    )

    test_results = [
        test_growth_rate_between_bins(
            df_analysis,
            bin_col=bin_col,
            window_months=window_months,
        )
        for bin_col, *_ in RATIO_ANALYSES
    ]

    summaries = {}
    for bin_col, kind, _, _, _ in RATIO_ANALYSES:
        summary = summarize_by_bin(df_analysis, bin_col=bin_col)
        summary["window_months"] = window_months
        summaries[kind] = summary
        print(f"\n===== Growth rate (%) summary by development {kind} ratio bin ({label}) =====")
        print(summary.to_string(index=False))

    df_analysis.to_csv(
        f"rq2_development_ratio_and_commit_growth_rate_pct_project_level_{label}.csv",
        index=False,
    )

    for bin_col, kind, filename_part, xlabel, title_part in RATIO_ANALYSES:
        summaries[kind].to_csv(
            f"rq2_development_{kind}_ratio_and_commit_growth_rate_pct_boxplot_summary_{label}.csv",
            index=False,
        )
        save_boxplot(
            df=df_analysis,
            bin_col=bin_col,
            filename=f"rq2_boxplot_commit_growth_rate_pct_by_{filename_part}_{label}.png",
            xlabel=xlabel,
            title=f"Commit growth rate by {title_part} ({window_months} months)",
        )

    return test_results, summaries["count"], summaries["amount"], df_analysis


def save_all_windows(test_results, count_summaries, amount_summaries, analysis_results):
    df_test_results = pd.DataFrame(test_results)
    df_count_summaries_all = pd.concat(count_summaries, ignore_index=True)
    df_amount_summaries_all = pd.concat(amount_summaries, ignore_index=True)
    df_analysis_all = pd.concat(analysis_results, ignore_index=True)

    print("\n===== Summary of statistical tests across windows =====")
    print(df_test_results.to_string(index=False))

    df_test_results.to_csv(
        "rq2_growth_rate_mannwhitney_0_30_vs_30_60_all_windows.csv",
        index=False,
    )
    df_count_summaries_all.to_csv(
        "rq2_development_count_ratio_and_commit_growth_rate_pct_boxplot_summary_all_windows.csv",
        index=False,
    )
    df_amount_summaries_all.to_csv(
        "rq2_development_amount_ratio_and_commit_growth_rate_pct_boxplot_summary_all_windows.csv",
        index=False,
    )
    df_analysis_all.to_csv(
        "rq2_development_ratio_and_commit_growth_rate_pct_project_level_all_windows.csv",
        index=False,
    )


def main():
    df_expense = add_expense_amount_usd(load_expense_predictions(CSV_FILES))
    df_project_spending = build_project_spending(df_expense)
    commit_args = load_commit_base(database_engine())

    all_test_results = []
    all_count_summaries = []
    all_amount_summaries = []
    all_analysis_results = []

    for window_months in WINDOW_MONTHS_LIST:
        test_results, count_summary, amount_summary, df_analysis = analyze_window(
            window_months,
            *commit_args,
            df_project_spending,
        )
        all_test_results.extend(test_results)
        all_count_summaries.append(count_summary)
        all_amount_summaries.append(amount_summary)
        all_analysis_results.append(df_analysis)

    save_all_windows(
        all_test_results,
        all_count_summaries,
        all_amount_summaries,
        all_analysis_results,
    )


if __name__ == "__main__":
    main()
