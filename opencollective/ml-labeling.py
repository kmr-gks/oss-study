'''
transactions.csvには、以下のカラムが含まれています。
from_account_type
to_account_name
to_account_type
expense_type
expense_tags
description
expense_description

bigcategory_map.csvには、以下のカラムが含まれています。
expense_tags
big_category (大分類の名前、othersまたは空白)
count
'''

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import json

# =========================
# 1. CSV読み込み
# =========================
transactions = pd.read_csv("transactions.csv")
tag_map = pd.read_csv("bigcategory_map.csv")

# タグをパースする関数
def parse_tag(tag):
    try:
        tags = json.loads(tag)
        if len(tags) == 0:
            return None
        return tags[0]   # 最初のタグだけ使う
    except:
        return None
transactions["expense_tags"] = transactions["expense_tags"].apply(parse_tag)

# 列名の前後空白対策
transactions.columns = transactions.columns.str.strip()
tag_map.columns = tag_map.columns.str.strip()

# 文字列列の前後空白対策
for col in ["expense_tags", "big_category"]:
    if col in tag_map.columns:
        tag_map[col] = tag_map[col].fillna("").astype(str).str.strip()

if "expense_tags" in transactions.columns:
    transactions["expense_tags"] = transactions["expense_tags"].fillna("").astype(str).str.strip()

# =========================
# 2. マップと結合して教師データ作成
# =========================
df = transactions.merge(
    tag_map[["expense_tags", "big_category"]],
    on="expense_tags",
    how="left"
)

# big_category が空白でない行を教師データ候補にする
labeled = df[df["big_category"].fillna("").str.strip() != ""].copy()

# 必要なら "others" を除外
# 研究方針によっては残してもよい
labeled = labeled[labeled["big_category"].str.lower() != "others"].copy()

print("All rows:", len(df))
print("Labeled rows:", len(labeled))
print("\nCategory distribution:")
print(labeled["big_category"].value_counts())
print("Total labeled rows:", labeled["big_category"].count())

# =========================
# 3. 特徴量テキスト作成
# =========================
feature_cols = [
    "from_account_type",
    "to_account_name",
    "to_account_type",
    "expense_type",
    "description",
    "expense_description",
]

for col in feature_cols:
    labeled[col] = labeled[col].fillna("").astype(str)

labeled["text"] = (
    labeled["from_account_type"] + " " +
    labeled["to_account_name"] + " " +
    labeled["to_account_type"] + " " +
    labeled["expense_type"] + " " +
    labeled["description"] + " " +
    labeled["expense_description"]
)

X = labeled["text"]
y = labeled["big_category"]

# =========================
# 4. train / test に分割
# =========================
X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
    X,
    y,
    labeled.index,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# =========================
# 5. モデル作成・学習
# =========================
model = Pipeline([
    ("tfidf", TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        min_df=2
    )),
    ("clf", LogisticRegression(
        max_iter=2000,
        class_weight="balanced"
    ))
])

model.fit(X_train, y_train)

# =========================
# 6. 評価
# =========================
y_pred = model.predict(X_test)

print("\nAccuracy:", accuracy_score(y_test, y_pred))
print("\nClassification report:")
print(classification_report(y_test, y_pred))

print("\nConfusion matrix:")
print(confusion_matrix(y_test, y_pred))

# =========================
# 7. ラベルなしデータに予測
# =========================
unlabeled = df[df["big_category"].fillna("").str.strip() == ""].copy()

for col in feature_cols:
    unlabeled[col] = unlabeled[col].fillna("").astype(str)

unlabeled["text"] = (
    unlabeled["from_account_type"] + " " +
    unlabeled["to_account_name"] + " " +
    unlabeled["to_account_type"] + " " +
    unlabeled["expense_type"] + " " +
    unlabeled["description"] + " " +
    unlabeled["expense_description"]
)

if len(unlabeled) > 0:
    unlabeled["predicted_big_category"] = model.predict(unlabeled["text"])

    # 予測確率も保存
    proba = model.predict_proba(unlabeled["text"])
    unlabeled["prediction_confidence"] = proba.max(axis=1)

    print("\nUnlabeled rows predicted:", len(unlabeled))
    print("Category distribution of predicted unlabeled rows:")
    print(unlabeled["predicted_big_category"].value_counts())
    print("Total predicted rows:", unlabeled["predicted_big_category"].count())

    # 保存
    unlabeled.to_csv("unlabeled_predicted.csv", index=False, encoding="utf-8-sig")
    print("Saved: unlabeled_predicted.csv")

# =========================
# 8. 教師データ側の予測結果も保存
# =========================
labeled_test_result = labeled.loc[idx_test].copy()

labeled_test_result["true_label"] = y_test.values
labeled_test_result["pred_label"] = y_pred

labeled_test_result.to_csv("test_predictions.csv", index=False, encoding="utf-8-sig")
print("Saved: test_predictions.csv")
