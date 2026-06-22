import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix, classification_report

# =========================
# 設定
# =========================

INPUT_FILE = "expenses_random_order_2nd.xlsx"

AUTHOR1_COL = "manual_label_gkimura"
AUTHOR2_COL = "manual_label_nourry-o"

# =========================
# 1. Excel読み込み
# =========================

df = pd.read_excel(INPUT_FILE)

# =========================
# 2. 前処理
# =========================

required_cols = {AUTHOR1_COL, AUTHOR2_COL}
missing_cols = required_cols - set(df.columns)

if missing_cols:
    raise ValueError(f"必要な列がありません: {missing_cols}")

df[AUTHOR1_COL] = (
    df[AUTHOR1_COL]
    .astype(str)
    .str.strip()
    .str.lower()
)

df[AUTHOR2_COL] = (
    df[AUTHOR2_COL]
    .astype(str)
    .str.strip()
    .str.lower()
)

# 空欄やnan文字列を除外
df_valid = df[
    df[AUTHOR1_COL].notna()
    & df[AUTHOR2_COL].notna()
    & (df[AUTHOR1_COL] != "")
    & (df[AUTHOR2_COL] != "")
    & (df[AUTHOR1_COL] != "nan")
    & (df[AUTHOR2_COL] != "nan")
].copy()

print("Total rows:", len(df))
print("Rows used for Cohen's kappa:", len(df_valid))

# =========================
# 3. Cohen's kappa
# =========================

kappa = cohen_kappa_score(
    df_valid[AUTHOR1_COL],
    df_valid[AUTHOR2_COL]
)

print("\n===== Cohen's kappa =====")
print("Kappa:", kappa)

# =========================
# 4. 一致率
# =========================

agreement_rate = (
    df_valid[AUTHOR1_COL] == df_valid[AUTHOR2_COL]
).mean()

print("\n===== Simple agreement =====")
print("Agreement rate:", agreement_rate)
print("Agreement rate (%):", agreement_rate * 100)

# =========================
# 5. ラベルごとの混同行列
# =========================

labels = sorted(
    set(df_valid[AUTHOR1_COL].unique())
    | set(df_valid[AUTHOR2_COL].unique())
)

cm = confusion_matrix(
    df_valid[AUTHOR1_COL],
    df_valid[AUTHOR2_COL],
    labels=labels
)

df_cm = pd.DataFrame(
    cm,
    index=[f"author1_{label}" for label in labels],
    columns=[f"author2_{label}" for label in labels]
)

print("\n===== Confusion matrix =====")
print(df_cm)

df_cm.to_csv("manual_label_confusion_matrix.csv")

# =========================
# 6. 不一致データの保存
# =========================

df_disagreement = df_valid[
    df_valid[AUTHOR1_COL] != df_valid[AUTHOR2_COL]
].copy()

df_disagreement.to_csv(
    "manual_label_disagreements.csv",
    index=False
)

print("\nSaved:")
print("manual_label_confusion_matrix.csv")
print("manual_label_disagreements.csv")