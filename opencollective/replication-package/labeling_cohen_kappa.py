import pandas as pd
from sklearn.metrics import cohen_kappa_score
from output_util import TABLES_DIR

# =========================
# Settings
# =========================

INPUT_FILE = "data2.csv"

AUTHOR1_COL = "manual_label_author1"
AUTHOR2_COL = "manual_label_author2"

df = pd.read_csv(INPUT_FILE)

required_cols = {AUTHOR1_COL, AUTHOR2_COL}
missing_cols = required_cols - set(df.columns)

if missing_cols:
    raise ValueError(f"Missing required columns: {missing_cols}")

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

kappa = cohen_kappa_score(
    df_valid[AUTHOR1_COL],
    df_valid[AUTHOR2_COL]
)

print("\n===== Cohen's kappa =====")
print("Kappa:", kappa)

agreement_rate = (
    df_valid[AUTHOR1_COL] == df_valid[AUTHOR2_COL]
).mean()

print("\n===== Simple agreement =====")
print("Agreement rate:", agreement_rate)
print("Agreement rate (%):", agreement_rate * 100)

pd.DataFrame([{
    "input_file": INPUT_FILE,
    "n_records": len(df_valid),
    "cohen_kappa": kappa,
    "agreement_pct": agreement_rate * 100,
}]).to_csv(TABLES_DIR / "labeling_cohen_kappa.csv", index=False)
