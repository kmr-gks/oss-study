from config import METRICS, OUTPUT_DIR
from database import (
    build_project_table,
    create_db_engine,
    load_issue_pr_items,
    load_commits,
)
from monthly_activity import (
    build_monthly_activity,
    build_monthly_commit_activity,
    exclude_projects,
    identify_top_activity_repositories,
    summarize_monthly_activity,
)
from growth_rate_analysis import (
    calculate_growth_rates,
    summarize_growth_rates,
)
from plotting import (
    plot_all_metrics,
    plot_metric_mean_median,
    plot_original_vs_excluding_top,
    plot_growth_rates,
    plot_growth_rate_boxplot,
    plot_all_metrics_median,
)
from statistical_tests import test_before_after_windows, run_issue_pr_growth_tests, print_test_summary


def save_dataframe(df, filename):
    output_path = OUTPUT_DIR / filename
    df.to_csv(output_path, index=False)
    print("Saved:", output_path)


def main():
    engine = create_db_engine()

    # 1. データ取得
    df_items = load_issue_pr_items(engine)
    df_projects = build_project_table(df_items)

    print("Loaded items:", len(df_items))
    print("Projects:", len(df_projects))
    print(
        "Unique repos:",
        df_projects["repo_name"].nunique(),
    )

    # 2. 通常の月次分析
    df_monthly = build_monthly_activity(
        df_items=df_items,
        df_projects=df_projects,
        baseline_column="opencollective_created_at",
    )

    #コミット情報の収集
    df_commits = load_commits(engine)

    print("Loaded commits:", len(df_commits))
    print(
        "Commit repositories:",
        df_commits["repo_name"].nunique(),
    )
    
    commit_repos = set(df_commits["repo_name"].unique())

    df_projects_common = df_projects[
        df_projects["repo_name"].isin(commit_repos)
    ].copy()

    df_monthly_issue_pr = build_monthly_activity(
        df_items,
        df_projects_common,
    )

    df_monthly_commits = build_monthly_commit_activity(
        df_commits,
        df_projects_common,
    )
    
    df_monthly = df_monthly_issue_pr.merge(
        df_monthly_commits,
        on=[
            "collective_id",
            "repo_name",
            "relative_month",
        ],
        how="left",
    )
    
    df_monthly["commits"] = (
        df_monthly["commits"]
        .fillna(0)
        .astype(int)
    )

    df_summary = summarize_monthly_activity(
        df_monthly
    )

    save_dataframe(
        df_monthly,
        "registration_monthly_project_level.csv",
    )
    save_dataframe(
        df_summary,
        "registration_monthly_summary.csv",
    )
    
    # =========================================
    # 前後3・6・8・12か月の増加率
    # =========================================
    
    df_growth = calculate_growth_rates(
        df_monthly
    )
    
    df_growth_summary = summarize_growth_rates(
        df_growth
    )
    
    save_dataframe(
        df_growth,
        "registration_growth_rates_project_level.csv",
    )
    
    save_dataframe(
        df_growth_summary,
        "registration_growth_rates_summary.csv",
    )
    
    plot_growth_rates(
        df_growth_summary,
        statistic="median",
    )
    
    plot_growth_rates(
        df_growth_summary,
        statistic="mean",
    )
    
    for metric_name in METRICS:
        plot_growth_rate_boxplot(
            df_growth,
            metric_name,
        )

    # 3. 上位1%リポジトリの特定・除外
    excluded_ids, df_repo_activity = (
        identify_top_activity_repositories(
            df_monthly,
            quantile=0.99,
        )
    )

    save_dataframe(
        df_repo_activity,
        "repository_total_activity.csv",
    )

    df_monthly_excluding_top = exclude_projects(
        df_monthly,
        excluded_ids,
    )

    df_summary_excluding_top = (
        summarize_monthly_activity(
            df_monthly_excluding_top
        )
    )

    save_dataframe(
        df_monthly_excluding_top,
        "registration_monthly_project_level_"
        "excluding_top1.csv",
    )
    save_dataframe(
        df_summary_excluding_top,
        "registration_monthly_summary_"
        "excluding_top1.csv",
    )

    # 4. 前後検定：全プロジェクト
    df_tests, df_test_projects = (
        test_before_after_windows(df_monthly)
    )

    df_tests["analysis_scope"] = "all_projects"

    save_dataframe(
        df_tests,
        "registration_statistical_tests.csv",
    )
    save_dataframe(
        df_test_projects,
        "registration_statistical_tests_"
        "project_level.csv",
    )

    # 5. 前後検定：上位1%除外
    # 主検定:
    # before_count == 0 のプロジェクトも含める

    df_tests = run_issue_pr_growth_tests(
        df_growth,
        include_zero_before=True,
    )

    save_dataframe(
        df_tests,
        "registration_issue_pr_"
        "wilcoxon_tests_holm.csv",
    )

    print_test_summary(df_tests)

    # 補足検定
    # 増加率を計算できるプロジェクトだけに限定。
    # 主検定と結果が大きく変わらないか確認する。

    df_tests_positive_before = (
        run_issue_pr_growth_tests(
            df_growth,
            include_zero_before=False,
        )
    )

    save_dataframe(
        df_tests_positive_before,
        "registration_issue_pr_"
        "wilcoxon_tests_holm_"
        "positive_before_only.csv",
    )

    # 6. グラフ
    """
    for metric_name in METRICS:
        plot_metric_mean_median(
            df_summary,
            metric_name,
            "all_projects",
        )

        plot_metric_mean_median(
            df_summary_excluding_top,
            metric_name,
            "excluding_top1",
        )

        plot_original_vs_excluding_top(
            df_summary,
            df_summary_excluding_top,
            metric_name,
        )
    """

    plot_all_metrics(
        df_summary,
        "all_projects",
    )

    plot_all_metrics_median(
        df_summary,
        "all_projects_median",
    )

    plot_all_metrics(
        df_summary_excluding_top,
        "excluding_top1",
    )

    print("\n===== Analysis finished =====")
    print(
        "All projects:",
        df_monthly["collective_id"].nunique(),
    )
    print(
        "Excluded top projects:",
        len(excluded_ids),
    )
    print(
        "Remaining projects:",
        df_monthly_excluding_top[
            "collective_id"
        ].nunique(),
    )


if __name__ == "__main__":
    main()