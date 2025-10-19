import json

INPUT_FILE = "budget_schema.json"
OUTPUT_FILE = "budget_query.graphql"

def build_type_map(schema):
    """型名→フィールドリストの辞書を構築"""
    return {t["name"]: t.get("fields", []) for t in schema}

def build_query_block(type_map, typename, indent=4, visited=None):
    """指定された型を再帰的にGraphQLクエリブロックに変換（循環防止付き）"""
    if visited is None:
        visited = set()
    if typename in visited:
        # 再帰防止
        return " " * indent + f"# (循環参照省略: {typename})"
    visited.add(typename)

    fields = type_map.get(typename, [])
    if not fields:
        return ""

    lines = []
    for f in fields:
        field_name = f["name"]
        ftype = f["type"]
        kind = ftype.get("kind")
        child = ftype.get("name") or ftype.get("ofType", {}).get("name")

        # Collection系（TransactionCollectionなど）
        if child and "Collection" in child:
            inner_type = child.replace("Collection", "")
            lines.append(" " * indent + f"{field_name}(limit: 3) {{")
            lines.append(" " * (indent + 2) + "nodes {")
            lines.append(build_query_block(type_map, inner_type, indent + 4, visited.copy()))
            lines.append(" " * (indent + 2) + "}")
            lines.append(" " * indent + "}")

        # 通常のオブジェクト
        elif kind == "OBJECT" and child in type_map:
            lines.append(" " * indent + f"{field_name} {{")
            lines.append(build_query_block(type_map, child, indent + 2, visited.copy()))
            lines.append(" " * indent + "}")

        # スカラ型（Float, Int, String, Booleanなど）
        elif kind == "SCALAR":
            lines.append(" " * indent + field_name)

    return "\n".join(lines)

def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        schema = json.load(f)

    type_map = build_type_map(schema)
    query_body = build_query_block(type_map, "Account", indent=4)

    query = f"""
query ($slug: String!) {{
  account(slug: $slug) {{
{query_body}
  }}
}}
"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(query)

    print(f"✅ 正しいGraphQLクエリを {OUTPUT_FILE} に出力しました。")

if __name__ == "__main__":
    main()