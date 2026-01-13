import requests
import json
import time
import random
import os

def load_token_from_credentials(file_path=None, service=None):
    """
    credentials.json から API トークンを読み込む。
    {
      "opencollective": { "api_token": "xxxxx" }
    }
    の形式を想定。
    """
    if file_path is None:
        parent_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(parent_dir, "credentials.json")
    if service is None:
        service = "postgresql"
    with open(file_path, "r", encoding="utf-8") as f:
        creds = json.load(f)

    try:
        token = creds[service]["api_token"]
    except KeyError:
        raise KeyError(f"credentials.json 内に {service} の api_token が見つかりません。")

    if not token:
        raise ValueError(f"{service} の api_token が空です。")

    return token.strip()

def load_sql_password_from_credentials(file_path=None, service=None):
    """
    credentials.json からデータベースのパスワードを読み込む。
    {
      "postgresql": { "password": "xxxxx" }
    }
    の形式を想定。
    """
    if file_path is None:
        parent_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(parent_dir, "credentials.json")
    if service is None:
        service = "postgresql"
    print(f"Loading SQL password for service '{service}' from {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        creds = json.load(f)

    try:
        password = creds[service]["password"]
    except KeyError:
        raise KeyError(f"credentials.json 内に {service} の password が見つかりません。")

    if not password:
        raise ValueError(f"{service} の password が空です。")

    return password.strip()

def run_query(query: str, variables: dict = None, credentials_file="credentials.json"):
    """
    OpenCollective GraphQL API にクエリを送信し、生のJSONを返す。
    失敗時には一定時間待ってリトライ（指数バックオフ）を行う。
    それでもエラーが発生するときは空のJSONを返す。
    """
    max_retries=5
    backoff_base=2.0
    url = "https://api.opencollective.com/graphql/v2"
    token = load_token_from_credentials(credentials_file)

    headers = {
        "Content-Type": "application/json",
        "Personal-Token": token
    }

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            # ステータスコードがエラーの場合は例外を投げる
            response.raise_for_status()

            # API固有のエラーもチェック（GraphQLの "errors" フィールド）
            result = response.json()
            if "errors" in result:
                raise Exception(result["errors"])
            return result  # 成功時に結果を返す

        except requests.exceptions.RequestException as e:
            # ネットワーク系 or ステータスエラー（429など）
            wait = backoff_base ** attempt * random.uniform(0, 1)
            print(f"リクエスト失敗 ({type(e).__name__}): {e}")
            if attempt < max_retries:
                print(f"{wait:.1f}秒待って再試行します... ({attempt}/{max_retries})")
                time.sleep(wait)
            else:
                print("最大リトライ回数に達しました。再試行を終了します。")
                return {}

        except Exception as e:
            # GraphQLレベルのエラーもリトライ対象に含める
            wait = backoff_base ** attempt * random.uniform(0, 1)
            print(f"GraphQLエラー: {e}")
            if attempt < max_retries:
                print(f"{wait:.1f}秒待って再試行します... ({attempt}/{max_retries})")
                time.sleep(wait)
            else:
                print("最大リトライ回数に達しました。再試行を終了します。")
                return {}

def show_json(result: json):
    print(json.dumps(result, indent=2))
