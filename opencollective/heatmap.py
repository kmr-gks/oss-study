import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

#df=pd.read_excel("expenses_random_order_v1.xlsx")
#true_col, pred_col = "major_category_decided", "predicted_label_by_LLM"

df=pd.read_excel("expenses_random_order_v2.xlsx")
true_col, pred_col = "manual_label_v2", "predicted_label_by_LLM"


print(df[[true_col, pred_col]].head(20))

ct = pd.crosstab(df[true_col], df[pred_col])
print(ct)

plt.figure()
sns.heatmap(ct, annot=True, fmt="d", cmap="Reds")
plt.imshow(ct.values)

plt.xticks(range(len(ct.columns)), ct.columns, rotation=45)
plt.yticks(range(len(ct.index)), ct.index)

plt.xlabel("Predicted")
plt.ylabel("True")
plt.title("Confusion Matrix")

plt.tight_layout()
plt.show()
plt.savefig("heatmap_label1.png")
