import pandas as pd
import json
from openai import OpenAI
from sklearn.metrics import accuracy_score, f1_score, classification_report
import os
import api
import psycopg2


# ===== 設定 =====
MODEL = "gpt-5.4-mini-2026-03-17"
OUTPUT_PATH = "predictions.csv"
if os.path.exists(OUTPUT_PATH):
	print(f"{OUTPUT_PATH} already exists.")
	exit(1)
    
client = OpenAI()

# ===== プロンプト =====
def build_prompt(description):
    return f"""
You are a classifier for OSS project expenses.

Select the SINGLE most appropriate category from the list below.

Categories:
- development: Compensation paid to official project members for direct software development and maintenance.
- bounty: Rewards or fees paid to external contributors (non-members) for specific tasks, bug fixes, or feature implementations.
- marketing-promotion: Expenses for project outreach and visibility, such as advertising and sponsorships.
- travel: All costs associated with transportation, lodging, and conference attendance (including registration fees).
- non-tech-service: Payments for essential activities that are not directly related to coding, such as documentation, and technical writing.
- infra-subscription: Recurring costs for cloud hosting, internet connectivity, and other software-as-a-service (SaaS) subscriptions.
- equipment: Purchase of physical hardware and assets directly used for development activities, such as laptops and servers.
- food-supplies: Purchase of consumables, meals, and general physical items that are not directly related to development.
- legal-admin: Expenditures for project governance, such as incorporation fees, trademark filings, tax preparation, and legal consultations.
- miscellaneous: Expenditures where the purpose is identified but does not fit into any of the specific categories above (e.g., bank fees).
- unknown: Expenditures where the purpose cannot be determined at all due to missing or insufficient information.

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

# DB接続
conn = psycopg2.connect(
    dbname="opencollective",
    user="postgres",
    password=api.load_sql_password_from_credentials(),
    host="localhost",
    port="5432"
)

cur = conn.cursor()

cur.execute(
    """
ALTER TABLE collective_transactions
ADD COLUMN IF NOT EXISTS expense_label_LLM TEXT;
	"""
)

# SQL実行
query = """
SELECT id, expense_description
FROM public.collective_transactions
WHERE kind = 'EXPENSE'
ORDER BY id ASC;
"""

cur.execute(query)

# 取得して表示
rows = cur.fetchall()

for i, row in enumerate(rows):
    print(f"{i+1}/{len(rows)}: {row[0]}, {row[1]}")
    output = classify(row[1])
    label = parse_label(output)
    #SQLのexpense_label_LLMを更新するコード例
    update_query = """
    UPDATE public.collective_transactions
    SET expense_label_LLM = %s
    WHERE id = %s;
    """
    cur.execute(update_query, (label, row[0]))
    if (i + 1) % 100 == 0:
        conn.commit()

conn.commit()

# 後処理
cur.close()
conn.close()

exit(0)
