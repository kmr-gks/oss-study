from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_COL = "project_slug"
WINDOW_MONTHS = 12

TERTILE_ORDER = [
    "Bottom 33%",
    "Middle 33%",
    "Top 33%",
]

CATEGORY_ORDER = [
    "feature_development",
    "bug_fixing",
    "contributor_recruitment",
    "documentation",
    "maintenance",
    "issue_triage_closure",
    "question_support",
    "other_labeled",
    "unlabeled",
]

CATEGORY_LABELS = {
    "feature_development":
        "Feature development",
    "bug_fixing":
        "Bug fixing",
    "contributor_recruitment":
        "Contributor-oriented",
    "documentation":
        "Documentation",
    "maintenance":
        "Maintenance",
    "issue_triage_closure":
        "Issue triage / closure",
    "question_support":
        "Question / support",
    "other_labeled":
        "Other labeled",
    "unlabeled":
        "Unlabeled",
}


def build_project_development_spend_share(
    df_individual_expenses: pd.DataFrame,
    amount_column: str = "amount_usd",
) -> pd.DataFrame:
    """
    各プロジェクトについて、個人への支出額のうち
    開発目的の支出額が占める割合を計算する。

    必要な列:
        project_slug
        is_development
        amount_usd

    is_development:
        True  = 開発目的
        False = その他
    """
    required_columns = {
        PROJECT_COL,
        "is_development",
        amount_column,
    }

    missing_columns = (
        required_columns
        - set(df_individual_expenses.columns)
    )

    if missing_columns:
        raise ValueError(
            "df_individual_expenses is missing columns: "
            f"{sorted(missing_columns)}"
        )

    df = df_individual_expenses.copy()

    df[amount_column] = pd.to_numeric(
        df[amount_column],
        errors="coerce",
    ).abs()

    df = df[
        df[PROJECT_COL].notna()
        & df[amount_column].notna()
        & df["is_development"].notna()
    ].copy()

    # プロジェクトへの個人支出総額
    df_total = (
        df.groupby(
            PROJECT_COL,
            as_index=False,
        )
        .agg(
            total_individual_expense_usd=(
                amount_column,
                "sum",
            ),
            total_individual_expense_count=(
                amount_column,
                "size",
            ),
        )
    )

    # 開発目的の個人支出
    df_development = (
        df.loc[
            df["is_development"].eq(True)
        ]
        .groupby(
            PROJECT_COL,
            as_index=False,
        )
        .agg(
            development_individual_expense_usd=(
                amount_column,
                "sum",
            ),
            development_individual_expense_count=(
                amount_column,
                "size",
            ),
        )
    )

    df_project = df_total.merge(
        df_development,
        on=PROJECT_COL,
        how="left",
    )

    fill_columns = [
        "development_individual_expense_usd",
        "development_individual_expense_count",
    ]

    df_project[fill_columns] = (
        df_project[fill_columns]
        .fillna(0)
    )

    df_project[
        "development_spend_share"
    ] = (
        df_project[
            "development_individual_expense_usd"
        ]
        / df_project[
            "total_individual_expense_usd"
        ]
    )

    # 支出総額が0のものは除外
    df_project = df_project[
        df_project[
            "total_individual_expense_usd"
        ].gt(0)
    ].copy()

    return (
        df_project
        .sort_values(
            "development_spend_share"
        )
        .reset_index(drop=True)
    )


def assign_development_share_tertiles(
    df_project_spend: pd.DataFrame,
) -> pd.DataFrame:
    """
    プロジェクトを開発支出割合の順位で3等分する。

    同じ割合が多数存在しても、可能な限り
    各グループの件数が同程度になるようrankを使う。
    """
    if df_project_spend.empty:
        return df_project_spend.copy()

    df = df_project_spend.copy()

    # 同率値が多くてもqcutできるよう順位を使う
    df["_share_rank"] = (
        df["development_spend_share"]
        .rank(
            method="first",
            ascending=True,
        )
    )

    df["development_share_tertile"] = pd.qcut(
        df["_share_rank"],
        q=3,
        labels=TERTILE_ORDER,
    )

    df["development_share_tertile"] = pd.Categorical(
        df["development_share_tertile"],
        categories=TERTILE_ORDER,
        ordered=True,
    )

    return (
        df.drop(columns="_share_rank")
        .sort_values(
            [
                "development_share_tertile",
                "development_spend_share",
            ]
        )
        .reset_index(drop=True)
    )


def extract_issues_within_one_year_after_joining(
    df_project_issues: pd.DataFrame,
    df_project_tertiles: pd.DataFrame,
    window_months: int = WINDOW_MONTHS,
) -> pd.DataFrame:
    """
    Open Collective加入後12か月以内にopenされたIssueを抽出する。

    必要な列:
        project_slug
        repo_name
        number
        created_at
        opencollective_created_at
        labels
    """
    required_columns = {
        PROJECT_COL,
        "repo_name",
        "number",
        "created_at",
        "opencollective_created_at",
        "labels",
    }

    missing_columns = (
        required_columns
        - set(df_project_issues.columns)
    )

    if missing_columns:
        raise ValueError(
            "df_project_issues is missing columns: "
            f"{sorted(missing_columns)}"
        )

    tertile_columns = [
        PROJECT_COL,
        "development_share_tertile",
        "development_spend_share",
        "total_individual_expense_usd",
        "development_individual_expense_usd",
    ]

    df = df_project_issues.merge(
        df_project_tertiles[tertile_columns],
        on=PROJECT_COL,
        how="inner",
    )

    df["created_at"] = pd.to_datetime(
        df["created_at"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    df["opencollective_created_at"] = pd.to_datetime(
        df["opencollective_created_at"],
        utc=True,
        errors="coerce",
    ).dt.tz_convert(None)

    df["analysis_end_at"] = (
        df["opencollective_created_at"]
        + pd.DateOffset(
            months=window_months
        )
    )

    df = df[
        df["created_at"].ge(
            df["opencollective_created_at"]
        )
        & df["created_at"].lt(
            df["analysis_end_at"]
        )
    ].copy()

    # 同じリポジトリの同じIssueが重複した場合に備える
    df = (
        df.drop_duplicates(
            subset=[
                PROJECT_COL,
                "repo_name",
                "number",
            ]
        )
        .reset_index(drop=True)
    )

    return df


def classify_post_join_issues(
    df_post_join_issues: pd.DataFrame,
) -> pd.DataFrame:
    """
    既存のclassify_issue_labels()を使用して分類する。

    戻り値は、
        1 Issue × 1 category

    1つのIssueが複数カテゴリに所属することを許す。
    """
    from issue_label_classification import (
        classify_issue_labels,
    )

    df_categories = classify_issue_labels(
        df_post_join_issues
    )

    issue_keys = [
        PROJECT_COL,
        "repo_name",
        "number",
    ]

    # classify_issue_labelsの結果にtertileがない場合は付与
    if (
        "development_share_tertile"
        not in df_categories.columns
    ):
        df_issue_groups = (
            df_post_join_issues[
                issue_keys
                + [
                    "development_share_tertile",
                    "development_spend_share",
                ]
            ]
            .drop_duplicates(
                subset=issue_keys
            )
        )

        df_categories = df_categories.merge(
            df_issue_groups,
            on=issue_keys,
            how="left",
        )

    return df_categories


def build_tertile_category_summary(
    df_post_join_issues: pd.DataFrame,
    df_issue_categories: pd.DataFrame,
) -> pd.DataFrame:
    """
    各tertileについて、カテゴリ割当数と割合を集計する。

    複数カテゴリを許すため、帯グラフでは
    「全カテゴリ割当数」に対する割合を用いる。
    """
    issue_keys = [
        PROJECT_COL,
        "repo_name",
        "number",
    ]

    df_categories = (
        df_issue_categories[
            issue_keys
            + [
                "development_share_tertile",
                "category",
            ]
        ]
        .drop_duplicates(
            subset=(
                issue_keys
                + ["category"]
            )
        )
        .copy()
    )

    df_category_counts = (
        df_categories
        .groupby(
            [
                "development_share_tertile",
                "category",
            ],
            observed=False,
            as_index=False,
        )
        .agg(
            n_category_assignments=(
                "number",
                "count",
            ),
            n_projects=(
                PROJECT_COL,
                "nunique",
            ),
        )
    )

    # 全tertile × 全categoryを作る
    full_index = pd.MultiIndex.from_product(
        [
            TERTILE_ORDER,
            CATEGORY_ORDER,
        ],
        names=[
            "development_share_tertile",
            "category",
        ],
    )

    df_category_counts = (
        df_category_counts
        .set_index(
            [
                "development_share_tertile",
                "category",
            ]
        )
        .reindex(
            full_index,
            fill_value=0,
        )
        .reset_index()
    )

    df_assignment_totals = (
        df_category_counts
        .groupby(
            "development_share_tertile",
            observed=False,
            as_index=False,
        )
        .agg(
            total_category_assignments=(
                "n_category_assignments",
                "sum",
            )
        )
    )

    df_issue_totals = (
        df_post_join_issues
        .groupby(
            "development_share_tertile",
            observed=False,
            as_index=False,
        )
        .agg(
            total_unique_issues=(
                "number",
                "count",
            ),
            total_projects_with_issues=(
                PROJECT_COL,
                "nunique",
            ),
        )
    )

    df_summary = (
        df_category_counts
        .merge(
            df_assignment_totals,
            on="development_share_tertile",
            how="left",
        )
        .merge(
            df_issue_totals,
            on="development_share_tertile",
            how="left",
        )
    )

    df_summary[
        "category_assignment_share"
    ] = np.where(
        df_summary[
            "total_category_assignments"
        ].gt(0),
        (
            df_summary[
                "n_category_assignments"
            ]
            / df_summary[
                "total_category_assignments"
            ]
        ),
        0,
    )

    df_summary[
        "issue_category_ratio"
    ] = np.where(
        df_summary[
            "total_unique_issues"
        ].gt(0),
        (
            df_summary[
                "n_category_assignments"
            ]
            / df_summary[
                "total_unique_issues"
            ]
        ),
        0,
    )

    return df_summary


def build_tertile_descriptive_summary(
    df_project_tertiles: pd.DataFrame,
    df_post_join_issues: pd.DataFrame,
) -> pd.DataFrame:
    """
    各グループのプロジェクト数、開発割合、
    加入後12か月のIssue数を要約する。
    """
    df_project_summary = (
        df_project_tertiles
        .groupby(
            "development_share_tertile",
            observed=False,
            as_index=False,
        )
        .agg(
            n_projects=(
                PROJECT_COL,
                "nunique",
            ),
            min_development_share=(
                "development_spend_share",
                "min",
            ),
            median_development_share=(
                "development_spend_share",
                "median",
            ),
            max_development_share=(
                "development_spend_share",
                "max",
            ),
            median_total_expense_usd=(
                "total_individual_expense_usd",
                "median",
            ),
            median_development_expense_usd=(
                "development_individual_expense_usd",
                "median",
            ),
        )
    )

    df_issue_summary = (
        df_post_join_issues
        .groupby(
            "development_share_tertile",
            observed=False,
            as_index=False,
        )
        .agg(
            n_projects_with_issues=(
                PROJECT_COL,
                "nunique",
            ),
            total_issues_after_joining=(
                "number",
                "count",
            ),
        )
    )

    return df_project_summary.merge(
        df_issue_summary,
        on="development_share_tertile",
        how="left",
    )


def plot_tertile_category_bands(
    df_category_summary: pd.DataFrame,
    df_tertile_summary: pd.DataFrame,
    output_path: Path,
) -> None:
    """
    3つのtertileを100%積み上げ帯グラフで表示する。
    """
    df_plot = (
        df_category_summary
        .pivot_table(
            index="development_share_tertile",
            columns="category",
            values="category_assignment_share",
            fill_value=0,
            observed=False,
        )
        .reindex(
            index=TERTILE_ORDER,
            columns=CATEGORY_ORDER,
            fill_value=0,
        )
    )

    fig, ax = plt.subplots(
        figsize=(9.0, 5.0)
    )

    left = np.zeros(
        len(df_plot)
    )

    for category in CATEGORY_ORDER:
        values = df_plot[category].to_numpy()

        ax.barh(
            df_plot.index.astype(str),
            values,
            left=left,
            height=0.62,
            label=CATEGORY_LABELS.get(
                category,
                category,
            ),
            edgecolor="white",
            linewidth=0.5,
        )

        left = left + values

    ax.set_xlim(0, 1)

    ax.set_xlabel(
        "Share of category assignments"
    )

    ax.set_ylabel(
        "Development spending share"
    )

    ax.xaxis.set_major_formatter(
        lambda value, position: (
            f"{value * 100:.0f}%"
        )
    )

    ax.grid(
        axis="x",
        linestyle=":",
        linewidth=0.7,
        alpha=0.6,
    )

    ax.set_axisbelow(True)

    summary_by_group = (
        df_tertile_summary
        .set_index(
            "development_share_tertile"
        )
    )

    for y_position, group_name in enumerate(
        TERTILE_ORDER
    ):
        if group_name not in summary_by_group.index:
            continue

        row = summary_by_group.loc[
            group_name
        ]

        label = (
            f"projects = {int(row['n_projects']):,}, "
            f"issues = "
            f"{int(row['total_issues_after_joining']):,}"
        )

        ax.text(
            1.01,
            y_position,
            label,
            va="center",
            ha="left",
            transform=ax.get_yaxis_transform(),
            fontsize=8.5,
        )

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.19),
        ncol=3,
        frameon=False,
        fontsize=8,
    )

    fig.subplots_adjust(
        left=0.20,
        right=0.78,
        top=0.96,
        bottom=0.31,
    )

    fig.savefig(
        output_path,
        bbox_inches="tight",
    )

    plt.close(fig)

    print(f"Saved: {output_path}")


def run_project_tertile_issue_analysis(
    df_individual_expenses: pd.DataFrame,
    df_project_issues: pd.DataFrame,
    output_dir: str = "project_issue_tertile_results",
    amount_column: str = "amount_usd",
):
    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    df_project_spend = (
        build_project_development_spend_share(
            df_individual_expenses=
                df_individual_expenses,
            amount_column=
                amount_column,
        )
    )

    df_project_tertiles = (
        assign_development_share_tertiles(
            df_project_spend
        )
    )

    df_post_join_issues = (
        extract_issues_within_one_year_after_joining(
            df_project_issues=
                df_project_issues,
            df_project_tertiles=
                df_project_tertiles,
            window_months=12,
        )
    )

    df_issue_categories = (
        classify_post_join_issues(
            df_post_join_issues
        )
    )

    df_category_summary = (
        build_tertile_category_summary(
            df_post_join_issues=
                df_post_join_issues,
            df_issue_categories=
                df_issue_categories,
        )
    )

    df_tertile_summary = (
        build_tertile_descriptive_summary(
            df_project_tertiles=
                df_project_tertiles,
            df_post_join_issues=
                df_post_join_issues,
        )
    )

    project_path = (
        output_dir
        / "project_development_spend_tertiles.csv"
    )

    issue_path = (
        output_dir
        / "issues_12m_after_joining.csv"
    )

    category_detail_path = (
        output_dir
        / "issue_category_detail_12m_after_joining.csv"
    )

    category_summary_path = (
        output_dir
        / "issue_category_summary_by_tertile.csv"
    )

    tertile_summary_path = (
        output_dir
        / "project_tertile_summary.csv"
    )

    figure_pdf_path = (
        output_dir
        / "issue_category_composition_by_"
          "development_spend_tertile_12m.pdf"
    )

    figure_png_path = (
        output_dir
        / "issue_category_composition_by_"
          "development_spend_tertile_12m.png"
    )

    df_project_tertiles.to_csv(
        project_path,
        index=False,
    )

    df_post_join_issues.to_csv(
        issue_path,
        index=False,
    )

    df_issue_categories.to_csv(
        category_detail_path,
        index=False,
    )

    df_category_summary.to_csv(
        category_summary_path,
        index=False,
    )

    df_tertile_summary.to_csv(
        tertile_summary_path,
        index=False,
    )

    plot_tertile_category_bands(
        df_category_summary=
            df_category_summary,
        df_tertile_summary=
            df_tertile_summary,
        output_path=
            figure_pdf_path,
    )

    plot_tertile_category_bands(
        df_category_summary=
            df_category_summary,
        df_tertile_summary=
            df_tertile_summary,
        output_path=
            figure_png_path,
    )

    print(
        "\n===== Project tertile summary ====="
    )

    print(
        df_tertile_summary
        .to_string(index=False)
    )

    print(
        "\n===== Category summary ====="
    )

    print(
        df_category_summary[
            [
                "development_share_tertile",
                "category",
                "n_category_assignments",
                "category_assignment_share",
                "issue_category_ratio",
            ]
        ]
        .to_string(index=False)
    )

    return {
        "project_tertiles":
            df_project_tertiles,
        "post_join_issues":
            df_post_join_issues,
        "issue_categories":
            df_issue_categories,
        "category_summary":
            df_category_summary,
        "tertile_summary":
            df_tertile_summary,
    }