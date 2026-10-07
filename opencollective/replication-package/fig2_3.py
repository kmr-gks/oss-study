import matplotlib
import numpy as np
import matplotlib.pyplot as plt
from output_util import FIGURES_DIR

from fig2 import load_contributions, convert_to_usd
from fig3 import load_expenses


OUTPUT_PDF = FIGURES_DIR / "rq2_money_flow.pdf"


def build_flow_table(df):
    return df.pivot_table(
        index="from_account_type",
        columns="to_account_type",
        values="amount_usd",
        aggfunc="sum",
        fill_value=0,
    )


def main():
    matplotlib.rcParams['pdf.fonttype'] = 42
    matplotlib.rcParams['ps.fonttype'] = 42
    contribution_table = build_flow_table(
        convert_to_usd(load_contributions())
    )
    expense_table = build_flow_table(
        convert_to_usd(load_expenses())
    )

    # Use the same row/column order in both panels
    # so that the y-axis can be shared.
    from_types = sorted(
        set(contribution_table.index)
        | set(expense_table.index)
    )
    to_types = sorted(
        set(contribution_table.columns)
        | set(expense_table.columns)
    )

    panels = [
        ("(a) CONTRIBUTION", contribution_table),
        ("(b) EXPENSE", expense_table),
    ]

    log_tables = [
        np.log10(
            table.reindex(
                index=from_types,
                columns=to_types,
                fill_value=0,
            ).values+1
        )
        for _, table in panels
    ]

    # Common color scale for a single, unified colorbar.
    vmin = 0
    vmax = max(values.max() for values in log_tables)

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(6.3, 3.3),
        sharey=True,
        constrained_layout=True,
    )
    fig.get_layout_engine().set(
        w_pad=0.01,
        wspace=0.02,
    )

    for ax, (title, _), log_values in zip(
        axes, panels, log_tables
    ):
        image = ax.imshow(
            log_values,
            aspect="auto",
            vmin=vmin,
            vmax=vmax,
        )

        ax.set_xticks(
            np.arange(len(to_types))
        )
        ax.set_xticklabels(
            to_types,
            rotation=90,
        )

        ax.set_title(title)

    axes[0].set_yticks(
        np.arange(len(from_types))
    )
    axes[0].set_yticklabels(
        from_types
    )
    axes[0].set_ylabel("From account type")

    # One shared x-label instead of one per panel.
    fig.supxlabel(
        "To account type",
        fontsize=plt.rcParams["axes.labelsize"],
    )

    colorbar = fig.colorbar(
        image,
        ax=axes,
        fraction=0.04,
        pad=0.01,
    )
    colorbar.set_label(r"$\log_{10}(1 + \mathrm{total\ amount\ [USD]})$")

    fig.savefig(
        OUTPUT_PDF,
        bbox_inches="tight",
        pad_inches=0.02,
    )

    plt.close(fig)


if __name__ == "__main__":
    main()
