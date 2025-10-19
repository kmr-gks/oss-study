import requests
import json

ENDPOINT = "https://api.opencollective.com/graphql/v2"

INTROSPECTION_QUERY = """
{
  __schema {
    types {
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
              ofType {
                kind
                name
              }
            }
          }
        }
      }
    }
  }
}
"""

print("▶ スキーマを取得中...")
response = requests.post(ENDPOINT, json={"query": INTROSPECTION_QUERY})
response.raise_for_status()
data = response.json()["data"]["__schema"]

with open("full_schema.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("✅ full_schema.json にスキーマ全体を保存しました。")