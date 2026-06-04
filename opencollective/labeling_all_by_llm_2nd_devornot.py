import pandas as pd
import json
from openai import OpenAI
import os
import api
import psycopg2


# ===== モデル =====
MODEL = "gpt-5.4-mini"
#MODEL = "gpt-5.4"
#MODEL = "gpt-5.5"

#ファイル名の末尾に日付時刻を付与
OUTPUT_PATH = f"predictions_2nd_all_devornot_{pd.Timestamp.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
if os.path.exists(OUTPUT_PATH):
	print(f"{OUTPUT_PATH} already exists.")
	exit(1)

client = OpenAI()

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
- others: Expenses that are not directly for software development. This includes infrastructure, hosting, SaaS subscriptions, equipment, food, travel, events, marketing, documentation, translation, legal work, tax/accounting, administration, community support, medical or personal support, general meetings, and unclear or ambiguous expenses.
IMPORTANT:
Classify as "development" only when the description clearly indicates direct work on the software product or technical maintenance of the project.

Descriptions may appear vague or incomplete. However, in many cases, they refer to development-related activities.
If the purpose is not explicitly stated, infer the most likely purpose by reasonably completing the context (e.g., missing subject or implicit meaning).
When making such inferences:
- Use common patterns in OSS projects (e.g., contributions, maintenance, works, docs).
- Only infer when the inferred word is highly confident based on context.

However:
- Do NOT guess randomly.

Rules:
- Choose exactly ONE category

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
Output:{{"label":"others","reason":"The description is vague and does not provide enough information to confidently classify it into any specific category. 'consulting' could relate to various activities such as development, marketing, or non-tech tasks. Without additional context, it is safest to classify this as 'others'."}}

Description: "Medical (Kidney Dialysis)"

Output:
{{"label":"others","reason":"The expense purpose is clearly medical support. Although its direct relation to OSS development is unclear, it is still an identifiable operational/community-related expense rather than an unknown description."}}

Description: "Pizza for SysOps/DevOps Poland MeetUp in Warsaw on 22.02.2019"

Output:
{{"label":"others","reason":"The primary expense is food prepared for the meetup, not participation in the event itself. Therefore, the expense should be classified as others."}}

Description: "Mail Chimp Email List - August 2018"

Output:
{{"label":"others","reason":"Mailchimp mailing lists are primarily used for project outreach, announcements, and promotion rather than infrastructure or development activities."}}

Description: "Zoom (Feb-Nov)"

Output:
{{"label":"others","reason":"Zoom is most plausibly used for communication and coordination among project members rather than infrastructure hosting or direct software development."}}

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


# DB接続
conn = psycopg2.connect(
    dbname="opencollective",
    user="postgres",
    password=api.load_sql_password_from_credentials(),
    host="localhost",
    port="5432"
)

cur = conn.cursor()

# SQL実行
query = """
SELECT id, project_slug, expense_description
FROM public.collective_transactions
WHERE kind = 'EXPENSE'
ORDER BY id ASC;
"""

cur.execute(query)

# 取得して表示
rows = cur.fetchall()

results = []
for i, row in enumerate(rows):
    project_slug = row[1]
    desc = row[2]
    print(f"{i+1}/{len(rows)}: {row[0]}, {project_slug}, {desc}")
    output = classify(desc)
    label, confidence, reason = parse_label(output)

    results.append({
        "index": i,
        "project_slug": project_slug,
        "expense_description": desc,
        "predicted_label": label,
        "confidence": confidence,
        "reason": reason,
    })

    # --- 途中保存（10件ごと） ---
    if i % 10 == 0:
        pd.DataFrame(results).to_csv(OUTPUT_PATH, index=False)

# 後処理
cur.close()
conn.close()

# ===== 最終保存 =====
results_df = pd.DataFrame(results)
results_df.to_csv(OUTPUT_PATH, index=False)

print(f"\nSaved to {OUTPUT_PATH}")

exit(0)
