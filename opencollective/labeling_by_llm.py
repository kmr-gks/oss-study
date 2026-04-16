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
- Development: Compensation paid to official project members for software development and maintenance.
- Bounty: Payments to external contributors for specific tasks (bug fixes, features).
- Marketing & Promotion: Advertising, sponsorships, outreach.
- Travel: Transportation, accommodation, conference costs.
- Non-tech Service: Documentation, writing, translation.
- Infra-subscription: Cloud, hosting, SaaS.
- Equipment: Hardware such as laptops or servers.
- Food & Supplies: Meals, consumables, general supplies.
- Legal & Admin: Legal, tax, administrative costs.
- Miscellaneous: Known purpose but does not fit above.
- Unknown: Purpose cannot be determined.

Rules:
- Choose exactly ONE category
- If unclear between Development and Bounty → choose Bounty
- If no clear purpose → choose Unknown

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
        return "Unknown"


# ===== 推論 =====
predictions = []

for i, row in df.iterrows():
    desc = row["expense_description"]

    output = classify(desc)
    label = parse_label(output)

    predictions.append(label)

    print(f"{i}: {label}")  # 進捗確認


# ===== 評価 =====
y_true = df["major_category_decided"].tolist()
y_pred = predictions

print("\n=== Evaluation ===")
print("Accuracy:", accuracy_score(y_true, y_pred))
print("Macro F1:", f1_score(y_true, y_pred, average="macro"))

print("\n=== Classification Report ===")
print(classification_report(y_true, y_pred))
