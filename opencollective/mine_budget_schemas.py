import json
import requests
import time
import api

ENDPOINT = "https://api.opencollective.com/graphql/v2"

INPUT_FILE = "budget_related_fields.json"
OUTPUT_SCHEMA = "mined_budget_data.json"
OUTPUT_NUMERIC = "numeric_fields.json"

# introspection クエリ
INTROSPECTION_QUERY = """
query GetType($name: String!) {
  __type(name: $name) {
    name
    kind
    fields {
      name
      type {
        kind
        name
        ofType {
          kind
          name
          ofType {
            kind
            name
          }
        }
      }
    }
  }
}
"""

def unwrap_type(t):
    """ofTypeを再帰的に辿って最も内側の型名を取得"""
    if not t:
        return None
    return t.get("name") or unwrap_type(t.get("ofType"))

def main():
    # 抽出済みスキーマを読み込み
    with open(INPUT_FILE, encoding="utf-8") as f:
        schema = json.load(f)

    # 型名をユニークに抽出
    type_names = sorted(set([r["field_type"] for r in schema if r.get("field_type")]))
    print(f"対象となる型: {len(type_names)} 個")

    mined = {}
    numeric_fields = []

    for i, type_name in enumerate(type_names, 1):
        print(f"[{i}/{len(type_names)}] {type_name}")
        try:
            '''
            res = requests.post(
                ENDPOINT,
                json={"query": INTROSPECTION_QUERY, "variables": {"name": type_name}},
                timeout=15,
            )
            res.raise_for_status()
            data = res.json()
            '''
            data=api.run_query(INTROSPECTION_QUERY, {"limit": 100, "offset": 0,"name": type_name})

            tdata = data.get("data", {}).get("__type")
            if not tdata:
                print(f"⚠️ {type_name}: データなし")
                continue

            mined[type_name] = tdata

            # 数値フィールドを抽出
            for field in tdata.get("fields") or []:
                innermost = unwrap_type(field["type"])
                if innermost in ("Float", "Int", "Amount"):
                    numeric_fields.append({
                        "type": type_name,
                        "field": field["name"],
                        "field_type": innermost
                    })
            time.sleep(0.3)
        except Exception as e:
            print(f"❌ {type_name} 取得失敗: {e}")

    # 出力
    with open(OUTPUT_SCHEMA, "w", encoding="utf-8") as f:
        json.dump(mined, f, ensure_ascii=False, indent=2)
    with open(OUTPUT_NUMERIC, "w", encoding="utf-8") as f:
        json.dump(numeric_fields, f, ensure_ascii=False, indent=2)

    print(f"✅ 型定義を {OUTPUT_SCHEMA} に保存しました。")
    print(f"✅ 数値フィールド {len(numeric_fields)} 件を {OUTPUT_NUMERIC} に保存しました。")

if __name__ == "__main__":
    main()
