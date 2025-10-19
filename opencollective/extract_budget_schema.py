import json
import re

INPUT_FILE = "full_schema.json"
OUTPUT_FILE = "budget_schema.json"

# 予算関連キーワード
KEYWORDS = [
    "account", "stats", "transaction", "expense",
    "order", "amount", "payment", "payout",
    "balance", "budget", "currency"
]

def matches_budget(name):
    if not name:
        return False
    return any(re.search(k, name, re.IGNORECASE) for k in KEYWORDS)

def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        schema = json.load(f)

    filtered = []
    for t in schema["types"]:
        if matches_budget(t["name"]):
            fields = [
                f for f in (t.get("fields") or [])
                if matches_budget(f["name"]) or matches_budget(f["type"].get("name"))
            ]
            if fields:
                filtered.append({"name": t["name"], "fields": fields})

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(filtered, f, ensure_ascii=False, indent=2)

    print(f"✅ {len(filtered)} 個の予算関連型を {OUTPUT_FILE} に保存しました。")

if __name__ == "__main__":
    main()