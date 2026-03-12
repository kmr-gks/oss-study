import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

# =========================
# 1. CSV読み込み
# =========================
test_df = pd.read_csv("test_predictions.csv")
pred_df = pd.read_csv("unlabeled_predicted.csv")

print("Test rows:", len(test_df))
print("Predicted rows:", len(pred_df))

# =========================
# 2. モデル精度
# =========================
y_true = test_df["true_label"]
y_pred = test_df["pred_label"]

print("\nAccuracy:")
print(accuracy_score(y_true, y_pred))

print("\nClassification report:")
print(classification_report(y_true, y_pred))

print("\nConfusion matrix:")
print(confusion_matrix(y_true, y_pred))

# =========================
# 3. 教師データの最終カテゴリ
# =========================
labeled = test_df.copy()

labeled["final_category"] = labeled["true_label"]

# =========================
# 4. 予測データの最終カテゴリ
# =========================
unlabeled = pred_df.copy()

unlabeled["final_category"] = unlabeled["predicted_big_category"]

# =========================
# 5. データ結合
# =========================
all_data = pd.concat([
    labeled,
    unlabeled
], ignore_index=True)

print("\nTotal rows used:", len(all_data))

# =========================
# 6. 金額を正にする
# =========================
all_data["amount"] = -all_data["amount_value"]

# =========================
# 7. カテゴリ別件数
# =========================
count_by_cat = all_data["final_category"].value_counts()

print("\nCategory counts:")
print(count_by_cat)

# =========================
# 8. カテゴリ別金額
# =========================
amount_by_cat = all_data.groupby("final_category")["amount"].sum()

print("\nTotal amount by category:")
print(amount_by_cat)

# =========================
# 9. カテゴリ別割合
# =========================
ratio = amount_by_cat / amount_by_cat.sum()

print("\nAmount ratio:")
print(ratio)

# =========================
# 10. 結果テーブル作成
# =========================
summary = pd.DataFrame({
    "count": count_by_cat,
    "total_amount": amount_by_cat,
    "ratio": ratio
})

summary = summary.sort_values("total_amount", ascending=False)

print("\nSummary table:")
print(summary)

# =========================
# 11. CSV保存
# =========================
summary.to_csv("expense_summary.csv", encoding="utf-8-sig")

print("\nSaved: expense_summary.csv")
