import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

df_true = pd.read_excel("expenses_random_order_v2.xlsx")
df_pred = pd.read_csv("predictions_.csv")

true_col,pred_col = "manual_label_v2", "predicted_label"

# 長さチェック
if len(df_true) != len(df_pred):
    raise ValueError("行数が一致していません")

# データ結合
df = pd.DataFrame({
    true_col: df_true[true_col],
    pred_col: df_pred[pred_col]
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
