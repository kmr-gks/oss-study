import json
import requests
import time
import api

ENDPOINT = "https://api.opencollective.com/graphql/v2"

INPUT_FILE = "budget_related_fields.json"
OUTPUT_FILE = "mined_budget_data.json"

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

def main():
    # 抽出済みスキーマを読み込み
    with open(INPUT_FILE, encoding="utf-8") as f:
        schema = json.load(f)

    # 型名をユニークに抽出
    type_names = sorted(set([r["field_type"] for r in schema if r.get("field_type")]))
    print(f"対象となる型: {len(type_names)} 個")

    mined = {}

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

            if "data" in data and data["data"]["__type"]:
                mined[type_name] = data["data"]["__type"]
            else:
                print(f"⚠️ {type_name}: データなし")

            # API優しめ: 0.3秒待機
            time.sleep(0.3)
        except Exception as e:
            print(f"❌ {type_name} 取得失敗: {e}")

    # 出力
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(mined, f, ensure_ascii=False, indent=2)

    print(f"✅ すべての型情報を {OUTPUT_FILE} に保存しました。")

if __name__ == "__main__":
    main()
