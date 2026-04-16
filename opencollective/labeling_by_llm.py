import pandas as pd
import json
from openai import OpenAI
from sklearn.metrics import accuracy_score, f1_score, classification_report
import os

# ===== 設定 =====
MODEL = "gpt-5.4-mini-2026-03-17"
OUTPUT_PATH = "predictions.csv"
if os.path.exists(OUTPUT_PATH):
	print(f"{OUTPUT_PATH} already exists.")
	exit(1)

client = OpenAI()

# ===== CSV読み込み =====
df = pd.read_csv("expenses_random_order_v1.csv")
df = df[["expense_description", "major_category_decided"]].dropna()

# ===== プロンプト =====
def build_prompt(description):
    return f"""
You are a classifier for OSS project expenses.

Select the SINGLE most appropriate category from the list below.

Categories:
- development: Compensation paid to official project members for software development and maintenance.
- bounty: Payments to external contributors for specific tasks (bug fixes, features).
- marketing-promotion: Advertising, sponsorships, outreach.
- travel: Transportation, accommodation, conference costs.
- non-tech-service: Documentation, writing, translation.
- infra-subscription: Cloud, hosting, SaaS.
- equipment: Hardware such as laptops or servers.
- food-supplies: Meals, consumables, general supplies.
- legal-admin: Legal, tax, administrative costs.
- miscellaneous: Known purpose but does not fit above.
- unknown: Purpose cannot be determined.

Rules:
- Choose exactly ONE category
- If no clear purpose → choose unknown

Output format:
{{"label": "..."}}

description: "{description}"
→
"""

# ===== API呼び出し =====
def classify(description):
    prompt = build_prompt(description)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    return response.choices[0].message.content


# ===== 出力パース =====
def parse_label(output):
    try:
        return json.loads(output)["label"]
    except:
        return "unknown"


# ===== 推論 =====
results = []

for i, row in df.iterrows():
    desc = row["expense_description"]

    output = classify(desc)
    label = parse_label(output)

    results.append({
        "index": i,
        "expense_description": desc,
        "true_label": row["major_category_decided"],
        "predicted_label": label
    })

    print(f"{i}: {label}")  # 進捗確認

    # --- 途中保存（10件ごと） ---
    if i % 10 == 0:
        pd.DataFrame(results).to_csv(OUTPUT_PATH, index=False)


# ===== 最終保存 =====
results_df = pd.DataFrame(results)
results_df.to_csv(OUTPUT_PATH, index=False)

print(f"\nSaved to {OUTPUT_PATH}")


# ===== 評価 =====
y_true = results_df["true_label"].tolist()
y_pred = results_df["predicted_label"].tolist()

print("\n=== Evaluation ===")
print("Accuracy:", accuracy_score(y_true, y_pred))
print("Macro F1:", f1_score(y_true, y_pred, average="macro"))

print("\n=== Classification Report ===")
print(classification_report(y_true, y_pred))
