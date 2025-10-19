import json

INPUT_FILE = "budget_schema.json"
OUTPUT_FILE = "budget_field_paths.json"

def build_field_map(data):
    return {t["name"]: t["fields"] for t in data}

def dfs(field_map, node, path, results):
    fields = field_map.get(node)
    if not fields:
        return
    for f in fields:
        name = f["name"]
        ftype = f["type"].get("name") or f["type"].get("ofType", {}).get("name")
        new_path = path + [name]
        if f["type"]["kind"] == "SCALAR":
            results.append(".".join(new_path))
        else:
            dfs(field_map, ftype, new_path, results)

def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    fmap = build_field_map(data)
    results = []
    dfs(fmap, "Account", ["account"], results)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(set(results)), f, ensure_ascii=False, indent=2)
    print(f"✅ {len(results)} 個のフィールドパスを {OUTPUT_FILE} に保存しました。")

if __name__ == "__main__":
    main()