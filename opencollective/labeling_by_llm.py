import pandas as pd
import json
from openai import OpenAI
from sklearn.metrics import accuracy_score, f1_score, classification_report
import os

# ===== 設定 =====
MODEL = "gpt-4o-search-preview-2025-03-11"
#ファイル名の末尾に日付時刻を付与
OUTPUT_PATH = f"predictions_{pd.Timestamp.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
if os.path.exists(OUTPUT_PATH):
	print(f"{OUTPUT_PATH} already exists.")
	exit(1)

client = OpenAI()

# ===== CSV読み込み =====
#df = pd.read_csv("expenses_random_order_v1.csv")
#df = df[["expense_description", "major_category_decided"]].dropna()
df = pd.read_csv("expenses_random_order_v2.csv")
df = df[["expense_description", "manual_label_v2"]].dropna()

# ===== プロンプト =====
def build_prompt(description):
    return f"""
You are a classifier for OSS project expenses.

Select the SINGLE most appropriate category from the list below.

Categories:
- development: Compensation paid to official project members for direct software development and maintenance.
- bounty: Rewards or fees paid to external contributors (non-members) for specific tasks, bug fixes, feature implementations, or general contributions.
- infra-subscription: Recurring costs for cloud hosting, internet connectivity, and other software-as-a-service (SaaS) subscriptions.
- equipment: Purchase of physical hardware and assets directly used for development activities, such as laptops and servers.
- food-supplies: Purchase of consumables, meals, and general physical items that are not directly related to development.
- marketing-events: Costs for organizing or participating in events to promote the project and recruit new developers (includes marketing, social media promotion, transportation, conference registration fees).
- non-tech-activities: Essential project-related tasks that are not directly linked to coding, such as documentation, translation, technical writing, legal or tax compliance, accounting, and general administrative work.
IMPORTANT:
If the expense is related to creating or improving project documentation, treat it as "non-tech-activities", even if it involves participation in a program or event.
For example, participation in programs such as Google Season of Docs (GSoD) should be classified as "non-tech-activities" when the purpose is documentation work for the project.

- unknown: Expenditures where the purpose cannot be determined at all due to missing or insufficient information.

Rules:
- Choose exactly ONE category
- If you're unsure, feel free to use a web search. If you still can't find the answer after searching, choose unknown.

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
                    web_search_options={
                "user_location": {
                    "type": "approximate",
                    "approximate": {
                        "country": "JP",
                        "city": "Tokyo",
                        "region": "Tokyo",
                    },
                },
            },
        messages=[{"role": "user", "content": prompt}],
        #temperature=0
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
        "true_label": row["manual_label_v2"],
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
