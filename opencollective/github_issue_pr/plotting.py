import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import MaxNLocator

from config import METRICS, OUTPUT_DIR


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

    markers = ["o", "s", "^", "v", "D"]

    for marker, metric_name in zip(
        markers,
        METRICS.keys(),
    ):
        label = METRICS[metric_name]["label"]

        plt.plot(
            df_summary["plot_month"],
            df_summary[f"mean_{metric_name}"],
            marker=marker,
            linestyle="-",
            label=f"Mean {label}",
        )

        plt.plot(
            df_summary["plot_month"],
            df_summary[f"median_{metric_name}"],
            marker=marker,
            linestyle="--",
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