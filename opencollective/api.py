import requests
import json

def load_token_from_credentials(file_path="credentials.json", service="opencollective"):
    """
    credentials.json から API トークンを読み込む。
    {
      "opencollective": { "api_token": "xxxxx" }
    }
    の形式を想定。
    """
    with open(file_path, "r", encoding="utf-8") as f:
        creds = json.load(f)

    try:
        token = creds[service]["api_token"]
    except KeyError:
        raise KeyError(f"credentials.json 内に {service} の api_token が見つかりません。")

    if not token:
        raise ValueError(f"{service} の api_token が空です。")

    return token.strip()


def run_query(query: str, variables: dict = None, credentials_file="credentials.json"):
    """
    OpenCollective GraphQL API にクエリを送信し、生のJSONを返す。
    variables がある場合はGraphQL変数として渡す。
    """
    url = "https://api.opencollective.com/graphql/v2"
    token = load_token_from_credentials(credentials_file)

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
