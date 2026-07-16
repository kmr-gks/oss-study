from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


# ============================================================
# Settings
# ============================================================

INPUT_FILES = {
    "Development payments": Path(
        "issue_actor_matching_"
        "individual_development_payment_"
        "category_period_comparison_12m.csv"
    ),
    "Any payments": Path(
        "issue_actor_matching_"
        "individual_any_payment_"
        "category_period_comparison_12m.csv"
    ),
}

OUTPUT_DIR = Path("paid_developer_issue_category_analysis")
OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

# 論文・発表で示す順番
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

# 表示名
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

# 前後の全Issue数
# 前回の集計結果から取得
TOTAL_ISSUES = {
    "Development payments": {
        "Before": 3090,
        "After": 2822,
    },
    "Any payments": {
        "Before": 6237,
        "After": 5203,
    },
}


def load_category_comparison(
    csv_path: Path,
) -> pd.DataFrame:
    """
    カテゴリ前後比較CSVを読み込む。
    """
    if not csv_path.exists():
        raise FileNotFoundError(
            f"File not found: {csv_path}"
        )

    df = pd.read_csv(csv_path)

    required_columns = {
        "category",
        "before_n_issues",
        "after_n_issues",
        "before_issue_ratio",
        "after_issue_ratio",
    }

    missing_columns = (
        required_columns - set(df.columns)
    )

    if missing_columns:
        raise ValueError(
            f"{csv_path} is missing columns: "
            f"{sorted(missing_columns)}"
        )

    df = df[
        df["category"].isin(CATEGORY_ORDER)
    ].copy()

    df["category"] = pd.Categorical(
        df["category"],
        categories=CATEGORY_ORDER,
        ordered=True,
    )

    return (
        df
        .sort_values("category")
        .reset_index(drop=True)
    )


def prepare_plot_data(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Before / Afterを行、
    categoryを列とした割合表に変換する。
    """
    rows = []

    for _, row in df.iterrows():
        category = row["category"]

        rows.append({
            "period": "Before",
            "category": category,
            "ratio": row[
                "before_issue_ratio"
            ],
        })

        rows.append({
            "period": "After",
            "category": category,
            "ratio": row[
                "after_issue_ratio"
            ],
        })

    df_long = pd.DataFrame(rows)

    df_plot = (
        df_long
        .pivot_table(
            index="period",
            columns="category",
            values="ratio",
            fill_value=0,
            observed=False,
        )
        .reindex(
            index=[
                "Before",
                "After",
            ],
            columns=CATEGORY_ORDER,
            fill_value=0,
        )
    )

    return df_plot


def plot_100_percent_stacked_bar(
    df_plot: pd.DataFrame,
    analysis_title: str,
    total_issues: dict[str, int],
    output_path: Path,
) -> None:
    """
    支払い前後のカテゴリ構成を
    100%積み上げ棒グラフとして出力する。
    """
    fig, ax = plt.subplots(
        figsize=(5, 3.5)
    )

    # 複数カテゴリ所属を許しているため、
    # 元のcategory ratioの合計は1を超える場合がある。
    # 帯グラフでは各期間の合計を1へ再正規化する。
    normalized = df_plot.div(
        df_plot.sum(axis=1),
        axis=0,
    )

    left = pd.Series(
        0.0,
        index=normalized.index,
    )

    for category in CATEGORY_ORDER:
        values = normalized[category]

        ax.barh(
            normalized.index,
            values,
            left=left,
            label=CATEGORY_LABELS.get(
                category,
                category,
            ),
            height=0.58,
            edgecolor="white",
            linewidth=0.5,
        )

        left = left + values

    ax.set_xlim(0, 1)

    ax.set_xlabel(
        "Share of category assignments"
    )

    ax.set_ylabel("")

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

    # 各期間の全Issue数を右側に表示
    for y_position, period in enumerate(
        normalized.index
    ):
        n_issues = total_issues[period]

        ax.text(
            1.01,
            y_position,
            f"n = {n_issues:,}",
            va="center",
            ha="left",
            transform=ax.get_yaxis_transform(),
            fontsize=9,
        )

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.20),
        ncol=3,
        frameon=False,
        fontsize=8,
    )


    fig.subplots_adjust(
        left=0.15,
        right=0.88,
        top=0.88,
        bottom=0.33,
    )

    fig.tight_layout()

    fig.savefig(
        output_path,
        bbox_inches="tight",
    )

    plt.close(fig)

    print(f"Saved: {output_path}")


def print_composition_changes(
    df: pd.DataFrame,
    analysis_title: str,
) -> None:
    """
    構成比の前後差を確認する。
    """
    result = df[
        [
            "category",
            "before_issue_ratio",
            "after_issue_ratio",
            "issue_ratio_difference",
        ]
    ].copy()

    result["before_pct"] = (
        result["before_issue_ratio"]
        * 100
    )

    result["after_pct"] = (
        result["after_issue_ratio"]
        * 100
    )

    result["difference_point"] = (
        result["issue_ratio_difference"]
        * 100
    )

    result["category"] = (
        result["category"]
        .astype(str)
        .map(CATEGORY_LABELS)
    )

    result = result[
        [
            "category",
            "before_pct",
            "after_pct",
            "difference_point",
        ]
    ]

    print(
        f"\n===== {analysis_title} ====="
    )

    print(
        result.to_string(
            index=False,
            formatters={
                "before_pct":
                    lambda value: (
                        f"{value:.1f}%"
                    ),
                "after_pct":
                    lambda value: (
                        f"{value:.1f}%"
                    ),
                "difference_point":
                    lambda value: (
                        f"{value:+.1f} pt"
                    ),
            },
        )
    )


def main() -> None:
    for analysis_title, csv_path in (
        INPUT_FILES.items()
    ):
        df = load_category_comparison(
            csv_path
        )

        print_composition_changes(
            df,
            analysis_title,
        )

        df_plot = prepare_plot_data(df)

        output_name = (
            analysis_title
            .lower()
            .replace(" ", "_")
        )

        output_path = (
            OUTPUT_DIR
            / (
                f"issue_category_composition_"
                f"{output_name}_"
                f"12m_before_after.pdf"
            )
        )

        plot_100_percent_stacked_bar(
            df_plot=df_plot,
            analysis_title=analysis_title,
            total_issues=TOTAL_ISSUES[
                analysis_title
            ],
            output_path=output_path,
        )


if __name__ == "__main__":
    main()