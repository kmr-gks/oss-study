import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def load_and_clean(path):
    df = pd.read_csv(path)

    num_cols = [
        "max_contribution_usd",
        "commits_before",
        "commits_after",
        "diff",
        "ratio",
    ]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # 無効データ除外
    df = df[
        (df["commits_before"] > 0) &
        (df["ratio"] > 0) &
        np.isfinite(df["ratio"]) &
        (df["max_contribution_usd"] > 0)
    ]
    return df


df30  = load_and_clean("commit-num-by-30days-of-max-contribution.csv")
df180 = load_and_clean("commit-num-by-180days-of-max-contribution.csv")

print("30 days:", len(df30))
print("180 days:", len(df180))

all_ratios = np.concatenate([
    df30["ratio"].values,
    df180["ratio"].values
])
xmin = np.nanmin(all_ratios)
xmax = np.nanmax(all_ratios)

bins = np.linspace(xmin, xmax, 100)

fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)

for ax, df, label in zip(
    axes,
    [df30, df180],
    ["±30 days", "±180 days"]
):
    ax.hist(df["ratio"], bins=bins)
    ax.axvline(1.0, color="red", linestyle="--", label="ratio = 1")
    ax.set_xlim(xmin, xmax)
    ax.set_yscale("log")
    ax.set_title(label)
    ax.set_xlabel("Commit activity ratio")

axes[0].set_ylabel("Number of projects (log scale)")
fig.suptitle("Distribution of commit activity change around max funding event")
plt.tight_layout()
plt.savefig("commit_activity_ratio_histogram.png", dpi=300)
plt.close()

merged = df30.merge(
    df180,
    on="project_slug",
    suffixes=("_30", "_180")
)

plt.figure(figsize=(6, 6))
plt.scatter(
    merged["ratio_30"],
    merged["ratio_180"],
    alpha=0.4
)

max_val = max(merged["ratio_30"].max(), merged["ratio_180"].max())
plt.plot([0.1, max_val], [0.1, max_val], "r--")

plt.xscale("log")
plt.yscale("log")
plt.xlabel("Ratio (±30 days)")
plt.ylabel("Ratio (±180 days)")
plt.title("Short-term vs long-term impact of funding")
plt.tight_layout()
plt.savefig("short_vs_long_term_impact.png")
plt.close()

fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)

for ax, df, label in zip(
    axes,
    [df30, df180],
    ["±30 days", "±180 days"]
):
    ax.scatter(
        df["max_contribution_usd"],
        df["ratio"],
        alpha=0.4
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.axhline(1.0, color="red", linestyle="--")
    ax.set_title(label)
    ax.set_xlabel("Max contribution (USD, log)")

axes[0].set_ylabel("Commit activity ratio")
fig.suptitle("Funding amount vs change in commit activity")
plt.tight_layout()
plt.savefig("funding_vs_commit_activity.png")
plt.close()

def summarize(df, label):
    print(f"\n[{label}]")
    print("projects:", len(df))
    print("ratio mean (arith):", df["ratio"].mean())
    print("ratio mean (geom):", np.exp(np.log(df["ratio"]).mean()))
    print("ratio > 1:", (df["ratio"] > 1).mean())
    print("ratio < 1:", (df["ratio"] < 1).mean())

summarize(df30, "±30 days")
summarize(df180, "±180 days")
