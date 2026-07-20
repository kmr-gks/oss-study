import pandas as pd

file1 = "data3.csv"
file2 = "data4.csv"

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

label_counts["percentage"] = (
    label_counts["count"] / label_counts["count"].sum() * 100
)

print(label_counts)
