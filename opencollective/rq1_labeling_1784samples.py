import pandas as pd
import json
from openai import OpenAI
from sklearn.metrics import accuracy_score, f1_score, classification_report
import os

# ===== モデル =====
#MODEL = "gpt-5.4-mini"
MODEL = "gpt-5.4"
#MODEL = "gpt-5.5"

#ファイル名の末尾に日付時刻を付与
OUTPUT_PATH = f"predictions_3rd_{pd.Timestamp.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
if os.path.exists(OUTPUT_PATH):
	print(f"{OUTPUT_PATH} already exists.")
	exit(1)

client = OpenAI()

# ===== CSV読み込み =====
df = pd.read_csv("expenses_random_order_3rd.csv")

# filter only first 10 rows for testing
df = df.head(10)

# ===== プロンプト =====
def build_prompt(description):
    return f"""
You are a classifier for OSS project expenses.

Context:
This classification is used to analyze how funds received by OSS projects are actually used. The goal is to understand the real allocation of funds across different types of activities.

Expense descriptions are often short and may be ambiguous. In many cases, the description is written by the person who received or used the funds, and may reflect their own perspective.

Select the SINGLE most appropriate category from the list below.

Categories:
- development: Compensation paid to official project members for direct software development, PR (Pull Request), and maintenance.
- infra-subscription: Recurring costs for cloud hosting, internet connectivity, and other software-as-a-service (SaaS) subscriptions.
- equipment: Purchase of physical hardware and assets directly used for development activities, such as laptops and servers.
- food-supplies: Purchase of consumables, meals, and general physical items that are not directly related to development.
- marketing-events: Costs for organizing or participating in events to promote the project and recruit new developers (includes marketing, social media promotion, transportation, conference registration fees).
- non-tech-activities: Essential project-related tasks that are not directly linked to coding, such as documentation, translation, technical writing, legal or tax compliance, accounting, and general administrative work.
IMPORTANT:
If the expense is related to creating or improving project documentation, treat it as "non-tech-activities", even if it involves participation in a program or event.
For example, participation in programs such as Google Season of Docs (GSoD) should be classified as "non-tech-activities" when the purpose is documentation work for the project.
- unknown: Use when the meaning of the description itself cannot be understood or confidence is very low. When the label cannot confidently be assigned.

If the description is understandable but its relation to development is unclear, use "unknown".

Descriptions may appear vague or incomplete. However, in many cases, they refer to development-related activities.
If the purpose is not explicitly stated, infer the most likely purpose by reasonably completing the context (e.g., missing subject or implicit meaning).
When making such inferences:
- Use common patterns in OSS projects (e.g., contributions, maintenance, works, docs).
- Only infer when the inferred word is highly confident based on context.

However:
- Do NOT guess randomly.
- If confidence is not high, choose "unknown".

Rules:
- Choose exactly ONE category
- If no clear purpose, choose unknown

Guidelines for confidence:
- High (0.8–1.0): Explicit keywords strongly match a category (e.g., "AWS", "server", "bug bounty")
- Medium (0.5–0.8): Some evidence but ambiguity exists
- Low (0.0–0.5): Vague description or weak signals

Reason guidelines:
- Explain briefly WHY the category was selected (1–2 sentences).
- Cite specific words or phrases from the description as evidence.
- Do NOT repeat the full description.

Few-shot examples:

Description: "Miriam Suzanne (OddBird) consulting"
Output:{{"label":"unknown","reason":"The description is vague and does not provide enough information to confidently classify it into any specific category. 'consulting' could relate to various activities such as development, marketing, or non-tech tasks. Without additional context, it is safest to classify this as 'unknown'."}}

Description: "Medical (Kidney Dialysis)"

Output:
{{"label":"non-tech-activities","reason":"The expense purpose is clearly medical support. Although its direct relation to OSS development is unclear, it is still an identifiable operational/community-related expense rather than an unknown description."}}

Description: "Pizza for SysOps/DevOps Poland MeetUp in Warsaw on 22.02.2019"

Output:
{{"label":"food-supplies","reason":"The primary expense is food prepared for the meetup, not participation in the event itself. Therefore, the expense should be classified as food and supplies."}}

Description: "Mail Chimp Email List - August 2018"

Output:
{{"label":"marketing-events","reason":"Mailchimp mailing lists are primarily used for project outreach, announcements, and promotion rather than infrastructure or development activities."}}

Description: "Zoom (Feb-Nov)"

Output:
{{"label":"non-tech-activities","reason":"Zoom is most plausibly used for communication and coordination among project members rather than infrastructure hosting or direct software development."}}

Description: "Co-Organizer Tasks and Trainings"

Output:
{{"label":"development","reason":"The terms 'Tasks' and 'Trainings' are most plausibly related to OSS development activities and contributor onboarding rather than general administration or outreach."}}

Description: "UX Research Work"

Output:
{{"label":"development","reason":"UX-related work is treated as part of the software development process because it directly contributes to product and interface improvement."}}

Output format:
{{"label": "...", "confidence": "0.0-1.0", "reason": "..."}}

description: "{description}"
→
"""

# ===== API呼び出し =====
def classify(description):
    prompt = build_prompt(description)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        #temperature=0
    )
    return response.choices[0].message.content


# ===== 出力パース =====
def parse_label(output):
    try:
        result = json.loads(output)
        return result["label"], result["confidence"], result["reason"]
    except:
        return "unknown", "0.0", ""


# ===== 推論 =====
results = []

for i, row in df.iterrows():
    desc = row["expense_description"]

    output = classify(desc)
    label, confidence, reason = parse_label(output)

    results.append({
        "index": i,
        "expense_description": desc,
        "predicted_label": label,
        "confidence": confidence,
        "reason": reason,
    })

    print(f"{i},{label},{confidence}")  # 進捗確認

    # --- 途中保存（10件ごと） ---
    if i % 10 == 0:
        pd.DataFrame(results).to_csv(OUTPUT_PATH, index=False)


# ===== 最終保存 =====
results_df = pd.DataFrame(results)
results_df.to_csv(OUTPUT_PATH, index=False)

print(f"\nSaved to {OUTPUT_PATH}")

# count data which confidence is 0.9 or higher
print("# of samples with confidence >= 0.9:", len(results_df[results_df["confidence"].astype(float) >= 0.9]))
