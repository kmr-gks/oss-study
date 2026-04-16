import pandas as pd
import json
from openai import OpenAI
from sklearn.metrics import accuracy_score, f1_score, classification_report

# ===== 設定 =====
MODEL = "gpt-5.4-mini-2026-03-17"

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
- If unclear between development and bounty → choose bounty
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
predictions = []
print("index,description,predicted_label")  # CSV形式で出力
for i, row in df.iterrows():
    desc = row["expense_description"]

    output = classify(desc)
    label = parse_label(output)

    predictions.append(label)

    print(f"{i},{desc},{label}")  # 進捗確認


# ===== 評価 =====
y_true = df["major_category_decided"].tolist()
y_pred = predictions

print("\n=== Evaluation ===")
print("Accuracy:", accuracy_score(y_true, y_pred))
print("Macro F1:", f1_score(y_true, y_pred, average="macro"))

print("\n=== Classification Report ===")
print(classification_report(y_true, y_pred))
