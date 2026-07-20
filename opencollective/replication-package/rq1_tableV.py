import pandas as pd

file1 = "predictions_3rd_2026-06-07_23-38-28.csv"
file2 = "predictions_4th_2026-06-08_14-27-03.csv"

df1 = pd.read_csv(file1)
df2 = pd.read_csv(file2)

df = pd.concat([df1, df2], ignore_index=True)

df = df[df["confidence"] >= 0.9]

label_counts = (
    df["predicted_label"]
    .value_counts()
    .rename_axis("predicted_label")
    .reset_index(name="count")
)

print(label_counts)

label_counts["percentage"] = (
    label_counts["count"] / label_counts["count"].sum() * 100
)

print(label_counts)
