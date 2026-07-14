from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
import api
import re
import unicodedata
import pandas as pd
from sqlalchemy import create_engine


# =========================
# 設定
# =========================

DB_NAME = "opencollective"
ITEM_TABLE = "public.github_issue_pr_items"

OUTPUT_DETAIL_CSV = "issue_labels_normalized_detail.csv"
OUTPUT_COUNT_CSV = "issue_label_counts_normalized.csv"
OUTPUT_VARIATION_CSV = "issue_label_raw_variations.csv"


# =========================
# DB接続
# =========================

engine = create_engine(
    "postgresql+psycopg2://"
    f"postgres:{api.load_sql_password_from_credentials()}"
    f"@localhost:5432/{DB_NAME}"
)


# =========================
# ラベル正規化関数
# =========================

def normalize_label_text(label: str) -> str:
    """
    人間が確認しやすい正規化ラベルを作る。

    処理:
    - Unicode表記を統一
    - 小文字化
    - 英数字以外を空白に置換
    - 連続した空白を1個にする

    例:
        "Type: Bug"       -> "type bug"
        "type/bug"        -> "type bug"
        "🐛 Type-(Bug)"   -> "type bug"
        "Help-Wanted"     -> "help wanted"
    """
    if label is None:
        return ""

    text = unicodedata.normalize("NFKC", str(label))
    text = text.lower().strip()

    # ASCII英数字以外を空白に置換
    text = re.sub(r"[^a-z0-9]+", " ", text)

    # 連続した空白を1個に統一
    text = re.sub(r"\s+", " ", text).strip()

    return text


def normalize_label_key(label: str) -> str:
    """
    機械的な集計・照合に使うキーを作る。

    例:
        "type: bug"   -> "typebug"
        "type/bug"    -> "typebug"
        "Type (Bug)"  -> "typebug"
        "help wanted" -> "helpwanted"
    """
    normalized_text = normalize_label_text(label)
    return normalized_text.replace(" ", "")


# =========================
# 1. IssueデータをSQLから取得
# =========================

query = f"""
SELECT
    collective_id,
    repo_name,
    number,
    labels
FROM {ITEM_TABLE}
WHERE item_type = 'issue'
"""

df_issues = pd.read_sql(query, engine)

print("Total issue records:", len(df_issues))
print(
    "Unique issues:",
    df_issues[["repo_name", "number"]]
    .drop_duplicates()
    .shape[0]
)


# =========================
# 2. ラベルなしIssueを確認
# =========================

df_issues["labels"] = df_issues["labels"].fillna("")

unlabeled_mask = df_issues["labels"].str.strip().eq("")

n_unlabeled = (
    df_issues.loc[unlabeled_mask, ["repo_name", "number"]]
    .drop_duplicates()
    .shape[0]
)

n_labeled = (
    df_issues.loc[~unlabeled_mask, ["repo_name", "number"]]
    .drop_duplicates()
    .shape[0]
)

print("\n===== Label availability =====")
print("Labeled issues:", n_labeled)
print("Unlabeled issues:", n_unlabeled)


# =========================
# 3. セミコロンで分割
# =========================

df_labels = (
    df_issues
    .assign(raw_label=df_issues["labels"].str.split(";"))
    .explode("raw_label")
)

df_labels["raw_label"] = (
    df_labels["raw_label"]
    .fillna("")
    .astype(str)
    .str.strip()
)

# 空ラベルを除外
df_labels = df_labels[
    df_labels["raw_label"].ne("")
].copy()


# =========================
# 4. 正規化
# =========================

df_labels["normalized_label"] = (
    df_labels["raw_label"]
    .apply(normalize_label_text)
)

df_labels["normalized_key"] = (
    df_labels["raw_label"]
    .apply(normalize_label_key)
)

# 記号だけのラベルなど、正規化後に空になったものを除外
df_labels = df_labels[
    df_labels["normalized_key"].ne("")
].copy()


# =========================
# 5. 同一Issue内の重複ラベルを除去
# =========================
# 例:
# 1件のIssueに
#   "Bug;bug;🐛 Bug"
# が付いていても、正規化後のbug Issueは1件として数える。

df_issue_labels_unique = (
    df_labels[
        [
            "collective_id",
            "repo_name",
            "number",
            "normalized_key",
        ]
    ]
    .drop_duplicates()
    .copy()
)


# =========================
# 6. 正規化キーごとの代表表示名を選ぶ
# =========================
# 最も頻繁に現れた normalized_label を代表名にする。

df_representative_label = (
    df_labels
    .groupby(
        ["normalized_key", "normalized_label"],
        as_index=False,
    )
    .size()
    .rename(columns={"size": "variation_count"})
    .sort_values(
        ["normalized_key", "variation_count"],
        ascending=[True, False],
    )
    .drop_duplicates("normalized_key")
    [
        [
            "normalized_key",
            "normalized_label",
        ]
    ]
)


# =========================
# 7. ラベルごとのIssue数を集計
# =========================

df_label_counts = (
    df_issue_labels_unique
    .groupby("normalized_key", as_index=False)
    .agg(
        issue_count=("number", "size"),
        repository_count=("repo_name", "nunique"),
        collective_count=("collective_id", "nunique"),
    )
    .merge(
        df_representative_label,
        on="normalized_key",
        how="left",
    )
)


# =========================
# 8. 元ラベルの表記揺れ数を追加
# =========================

df_variation_counts = (
    df_labels
    .groupby("normalized_key", as_index=False)
    .agg(
        raw_label_variation_count=(
            "raw_label",
            "nunique",
        )
    )
)

df_label_counts = (
    df_label_counts
    .merge(
        df_variation_counts,
        on="normalized_key",
        how="left",
    )
    .sort_values(
        "issue_count",
        ascending=False,
    )
    .reset_index(drop=True)
)


# =========================
# 9. 元ラベルごとの内訳
# =========================

df_raw_variations = (
    df_labels
    .groupby(
        [
            "normalized_key",
            "normalized_label",
            "raw_label",
        ],
        as_index=False,
    )
    .agg(
        label_occurrence_count=("number", "size"),
        issue_count=(
            "number",
            lambda values: values.nunique(),
        ),
        repository_count=("repo_name", "nunique"),
    )
    .sort_values(
        [
            "normalized_key",
            "label_occurrence_count",
        ],
        ascending=[True, False],
    )
)


# =========================
# 10. unlabeledを集計結果に追加
# =========================

unlabeled_row = pd.DataFrame([
    {
        "normalized_key": "unlabeled",
        "issue_count": n_unlabeled,
        "repository_count": (
            df_issues.loc[
                unlabeled_mask,
                "repo_name",
            ].nunique()
        ),
        "collective_count": (
            df_issues.loc[
                unlabeled_mask,
                "collective_id",
            ].nunique()
        ),
        "normalized_label": "unlabeled",
        "raw_label_variation_count": 0,
    }
])

df_label_counts_with_unlabeled = pd.concat(
    [
        df_label_counts,
        unlabeled_row,
    ],
    ignore_index=True,
)

df_label_counts_with_unlabeled = (
    df_label_counts_with_unlabeled
    .sort_values(
        "issue_count",
        ascending=False,
    )
    .reset_index(drop=True)
)


# =========================
# 11. CSV保存
# =========================

df_labels.to_csv(
    OUTPUT_DETAIL_CSV,
    index=False,
)

df_label_counts_with_unlabeled.to_csv(
    OUTPUT_COUNT_CSV,
    index=False,
)

df_raw_variations.to_csv(
    OUTPUT_VARIATION_CSV,
    index=False,
)

print("\nSaved:")
print(OUTPUT_DETAIL_CSV)
print(OUTPUT_COUNT_CSV)
print(OUTPUT_VARIATION_CSV)


# =========================
# 12. 上位100件を表示
# =========================

print("\n===== Top normalized labels =====")
print(
    df_label_counts_with_unlabeled[
        [
            "normalized_key",
            "normalized_label",
            "issue_count",
            "repository_count",
            "collective_count",
            "raw_label_variation_count",
        ]
    ]
    .head(100)
    .to_string(index=False)
)