import json

# 入力ファイルと出力ファイル
INPUT_FILE = "graphql_schema_fields.json"
OUTPUT_FILE = "budget_related_fields.json"

# 金銭・予算に関連しそうなキーワード
KEYWORDS = [
    "Amount", "Transaction", "Expense", "Payment", "Payout",
    "Currency", "Balance", "Stats"
]

def is_budget_related(record):
    """field_name が金銭関連キーワードを含むか"""
    text = (record.get("field_name", "")).lower()
    return any(k.lower() in text for k in KEYWORDS)

def main():
    # JSONを読み込み
    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    # 予算関連フィールドを抽出
    budget_related = [r for r in data if is_budget_related(r)]

    # 結果を保存
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(budget_related, f, ensure_ascii=False, indent=2)

    print(f"✅ {len(budget_related)} 件の予算関連フィールドを {OUTPUT_FILE} に保存しました。")

if __name__ == "__main__":
    main()
