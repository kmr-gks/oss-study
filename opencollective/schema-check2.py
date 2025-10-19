import requests
import json

ENDPOINT = "https://api.opencollective.com/graphql/v2"
QUERY = """
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

def fetch_schema():
    r = requests.post(ENDPOINT, json={'query': QUERY})
    r.raise_for_status()
    return r.json()['data']['__schema']['types']

def flatten_type(t):
    """ofTypeを展開して最も内側の型名を返す"""
    if not t:
        return None
    if t.get('name'):
        return t['name']
    return flatten_type(t.get('ofType'))

def extract_fields(types):
    """すべての型・フィールドをフラットに展開"""
    records = []
    for t in types:
        if not t.get('fields'):
            continue
        for f in t['fields']:
            field_type = flatten_type(f['type'])
            records.append({
                'parent_type': t['name'],
                'field_name': f['name'],
                'field_kind': f['type']['kind'],
                'field_type': field_type,
            })
    return records

def main():
    types = fetch_schema()
    records = extract_fields(types)
    print(f"Extracted {len(records)} fields")
    with open("graphql_schema_fields.json", "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()