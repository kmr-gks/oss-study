import requests
import json

def load_token(file_path="api-key.txt"):
    """APIトークンをファイルから読み込む"""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()

def run_query(query: str, variables: dict = None, token_file="api-key.txt"):
    """
    OpenCollective GraphQL API にクエリを送信し、生のJSONを返す。
    variables がある場合はGraphQL変数として渡す。
    """
    url = "https://api.opencollective.com/graphql/v2"
    token = load_token(token_file)

    headers = {
        "Content-Type": "application/json",
        "Personal-Token": token
    }

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()  # HTTPエラー時に例外

    return response.json()  # JSONのまま返す

def show_json(result: json):
    print(json.dumps(result, indent=2))
