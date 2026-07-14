from config import METRICS, OUTPUT_DIR
from database import (
    build_project_table,
    create_db_engine,
    load_issue_pr_items,
)
from monthly_activity import (
    build_monthly_activity,
    exclude_projects,
    identify_top_activity_repositories,
    summarize_monthly_activity,
)
from plotting import (
    plot_all_metrics,
    plot_metric_mean_median,
    plot_original_vs_excluding_top,
)
from statistical_tests import test_before_after_windows


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
    df_tests_excluded, df_test_projects_excluded = (
        test_before_after_windows(
            df_monthly_excluding_top
        )
    )

    df_tests_excluded[
        "analysis_scope"
    ] = "excluding_top1"

    save_dataframe(
        df_tests_excluded,
        "registration_statistical_tests_"
        "excluding_top1.csv",
    )
    save_dataframe(
        df_test_projects_excluded,
        "registration_statistical_tests_"
        "project_level_excluding_top1.csv",
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