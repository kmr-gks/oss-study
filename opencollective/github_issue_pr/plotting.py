import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import MaxNLocator

from config import ANALYSIS_WINDOWS, METRICS, OUTPUT_DIR


def add_registration_marker():
    plt.axvline(
        x=0,
        linestyle="--",
        linewidth=1,
    )

    ylim = plt.ylim()

    plt.text(
        0.1,
        ylim[1] * 0.95,
        "Open Collective registration",
        rotation=90,
        va="top",
    )


def configure_month_axis():
    months = list(range(-12, 0)) + list(range(1, 13))

    plt.xticks(months)
    plt.xlabel(
        "Months before / after "
        "Open Collective registration"
    )
    plt.gca().xaxis.set_major_locator(
        MaxNLocator(integer=True)
    )
    plt.grid(True, alpha=0.3)


def plot_metric_mean_median(
    df_summary: pd.DataFrame,
    metric_name: str,
    output_suffix: str,
):
    metric_label = METRICS[metric_name]["label"]

    plt.figure(figsize=(5, 3.5))

    plt.plot(
        df_summary["plot_month"],
        df_summary[f"mean_{metric_name}"],
        marker="o",
        label="Mean",
    )

    plt.plot(
        df_summary["plot_month"],
        df_summary[f"median_{metric_name}"],
        marker="o",
        linestyle="--",
        label="Median",
    )

    add_registration_marker()
    configure_month_axis()

    plt.ylabel(f"Monthly {metric_label.lower()} count")
    plt.legend()
    plt.tight_layout()

    output_path = (
        OUTPUT_DIR
        / f"{metric_name}_{output_suffix}.pdf"
    )

    plt.savefig(
        output_path,
        bbox_inches="tight",
    )
    plt.close()

    print("Saved figure:", output_path)


def plot_all_metrics(
    df_summary: pd.DataFrame,
    output_suffix: str,
):
    plt.figure(figsize=(9, 5.5))

    for metric_name in METRICS.keys():
        label = METRICS[metric_name]["label"]

        plt.plot(
            df_summary["plot_month"],
            df_summary[f"mean_{metric_name}"],
            marker=".",
            linestyle="--",
            label=f"Mean {label}",
        )

        plt.plot(
            df_summary["plot_month"],
            df_summary[f"median_{metric_name}"],
            marker="o",
            label=f"Median {label}",
        )

    add_registration_marker()
    configure_month_axis()

    plt.ylabel("Monthly count")
    plt.legend(
        fontsize=7,
        ncol=2,
    )
    plt.tight_layout()

    output_path = (
        OUTPUT_DIR
        / f"all_metrics_{output_suffix}.pdf"
    )

    plt.savefig(
        output_path,
        bbox_inches="tight",
    )
    plt.close()

    print("Saved figure:", output_path)


def plot_all_metrics_median(
    df_summary: pd.DataFrame,
    output_suffix: str,
):
    plt.figure(figsize=(9, 5.5))

    for metric_name in METRICS.keys():
        label = METRICS[metric_name]["label"]

        plt.plot(
            df_summary["plot_month"],
            df_summary[f"median_{metric_name}"],
            marker="o",
            label=f"Median {label}",
        )

    add_registration_marker()
    configure_month_axis()

    plt.ylabel("Monthly count")
    plt.legend(
        fontsize=7,
        ncol=2,
    )
    plt.tight_layout()

    output_path = (
        OUTPUT_DIR
        / f"all_metrics_{output_suffix}.pdf"
    )

    plt.savefig(
        output_path,
        bbox_inches="tight",
    )
    plt.close()

    print("Saved figure:", output_path)


def plot_original_vs_excluding_top(
    df_original: pd.DataFrame,
    df_excluded: pd.DataFrame,
    metric_name: str,
):
    label = METRICS[metric_name]["label"]

    plt.figure(figsize=(5.5, 3.8))

    plt.plot(
        df_original["plot_month"],
        df_original[f"mean_{metric_name}"],
        marker="o",
        label="Mean: all projects",
    )

    plt.plot(
        df_excluded["plot_month"],
        df_excluded[f"mean_{metric_name}"],
        marker="o",
        linestyle="--",
        label="Mean: excluding top 1%",
    )

    plt.plot(
        df_original["plot_month"],
        df_original[f"median_{metric_name}"],
        marker="s",
        linestyle=":",
        label="Median: all projects",
    )

    add_registration_marker()
    configure_month_axis()

    plt.ylabel(f"Monthly {label.lower()} count")
    plt.legend(fontsize=8)
    plt.tight_layout()

    output_path = (
        OUTPUT_DIR
        / f"{metric_name}_top1_sensitivity.pdf"
    )

    plt.savefig(
        output_path,
        bbox_inches="tight",
    )
    plt.close()

    print("Saved figure:", output_path)


def plot_growth_rates(
    df_summary: pd.DataFrame,
    statistic: str = "median",
):
    """
    横軸: 前後比較期間（3, 6, 8, 12か月）
    縦軸: 増加率（%）

    statistic:
        "median" または "mean"
    """
    if statistic not in {"mean", "median"}:
        raise ValueError(
            "statistic must be 'mean' or 'median'"
        )

    value_column = f"{statistic}_growth_rate_pct"

    plt.figure(figsize=(6.5, 4.2))

    for metric_name, metric_config in METRICS.items():
        metric_data = (
            df_summary[
                df_summary["metric"].eq(metric_name)
            ]
            .sort_values("window_months")
        )

        plt.plot(
            metric_data["window_months"],
            metric_data[value_column],
            marker="o",
            label=metric_config["label"],
        )

    # 増減なしを示す基準線
    plt.axhline(
        y=0,
        linestyle="--",
        linewidth=1,
    )

    plt.xticks(ANALYSIS_WINDOWS)
    plt.xlabel("Window size before and after registration (months)")
    plt.ylabel(f"{statistic.capitalize()} growth rate (%)")

    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=8)
    plt.tight_layout()

    output_path = (
        OUTPUT_DIR
        / f"{statistic}_growth_rate_by_window.pdf"
    )

    plt.savefig(
        output_path,
        bbox_inches="tight",
    )
    plt.close()

    print("Saved figure:", output_path)

def plot_growth_rate_boxplot(
    df_growth: pd.DataFrame,
    metric_name: str,
):
    metric_data = df_growth[
        df_growth["metric"].eq(metric_name)
        & df_growth["growth_rate_pct"].notna()
    ].copy()

    boxplot_data = [
        metric_data.loc[
            metric_data["window_months"].eq(window),
            "growth_rate_pct",
        ].to_numpy()
        for window in ANALYSIS_WINDOWS
    ]

    plt.figure(figsize=(5.5, 4))

    plt.boxplot(
        boxplot_data,
        tick_labels=ANALYSIS_WINDOWS,
        showfliers=False,
    )

    plt.axhline(
        y=0,
        linestyle="--",
        linewidth=1,
    )

    plt.xlabel(
        "Window size before and after registration (months)"
    )
    plt.ylabel("Growth rate (%)")
    plt.tight_layout()

    output_path = (
        OUTPUT_DIR
        / f"{metric_name}_growth_rate_boxplot.pdf"
    )

    plt.savefig(
        output_path,
        bbox_inches="tight",
    )
    plt.close()

    print("Saved figure:", output_path)
