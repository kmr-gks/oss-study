import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

df = pd.read_csv("predictions_2nd_.csv")

true_col,pred_col = "true_label", "predicted_label"

# データ結合
df = pd.DataFrame({
    true_col: df[true_col],
    pred_col: df[pred_col]
})

print(df[[true_col, pred_col]].head(20))

ct = pd.crosstab(df[true_col], df[pred_col])
print(ct)

plt.figure()
sns.heatmap(ct, annot=True, fmt="d", cmap="Reds")
plt.imshow(ct.values)

plt.xticks(range(len(ct.columns)), ct.columns, rotation=45, ha="right")
plt.yticks(range(len(ct.index)), ct.index)

plt.xlabel("Predicted")
plt.ylabel("True")
plt.title("Confusion Matrix")

plt.tight_layout()
plt.savefig("heatmap_label1.png")
plt.show()
