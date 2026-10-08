import pandas as pd
from output_util import TABLES_DIR

df = pd.read_csv("data2.csv")

manual = df["manual_true_label"].astype(str).str.strip().str.lower()
predicted = df["LLM1_predicted_label"].astype(str).str.strip().str.lower()

correct = pd.Series(
    [predicted_value==manual_value for manual_value, predicted_value in zip(manual, predicted)],
    index=df.index,
)

high_confidence = pd.to_numeric(
    df["LLM1_confidence"],
    errors="coerce",
).ge(0.9)

print("All data")
print(f"Correct: {correct.sum()}")
print(f"Total: {len(df)}")
print(f"Accuracy: {correct.mean():.2%}")

print("\nConfidence >= 0.9")
print(f"Correct: {correct[high_confidence].sum()}")
print(f"Total: {high_confidence.sum()}")
print(f"Accuracy: {correct[high_confidence].mean():.2%}")

pd.DataFrame([
    {
        "subset": "all",
        "correct": int(correct.sum()),
        "total": len(df),
        "accuracy_pct": correct.mean() * 100,
    },
    {
        "subset": "confidence_ge_0.9",
        "correct": int(correct[high_confidence].sum()),
        "total": int(high_confidence.sum()),
        "accuracy_pct": correct[high_confidence].mean() * 100,
    },
]).to_csv(TABLES_DIR / "labeling_llm_accuracy.csv", index=False)
