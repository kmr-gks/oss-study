import time
import json
import api
import requests
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import api


# =========================
# 設定
# =========================

DB_NAME = "opencollective"

OUTPUT_ITEMS_CSV = "github_issue_pr_items.csv"
OUTPUT_MONTHLY_CSV = "github_issue_pr_monthly_counts_around_opencollective.csv"
OUTPUT_FAILED_REPOS_CSV = "github_issue_pr_failed_repos.csv"

# まず試すなら小さめにする
# 全件取得したい場合は None
MAX_REPOS = None
# MAX_REPOS = 10

# GitHub GraphQL API
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
GITHUB_TOKEN = api.load_github_token_from_credentials()

if not GITHUB_TOKEN:
    raise ValueError(
        "GITHUB_TOKEN is empty."
    )

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Content-Type": "application/json",
}


# =========================
# DB接続
# =========================

engine = create_engine(
    f"postgresql+psycopg2://postgres:{api.load_sql_password_from_credentials()}@localhost:5432/{DB_NAME}"
)


# =========================
# 1. Open Collective登録プロジェクトを取得
# =========================

query_collectives = """
SELECT
    id,
    name,
    slug,
    type,
    created_at,
    github_account
FROM public.collectives
WHERE github_account IS NOT NULL
"""

df_collectives = pd.read_sql(query_collectives, engine)

df_collectives = df_collectives[
    df_collectives["github_account"].notna()
].copy()

df_collectives["github_account"] = (
    df_collectives["github_account"]
    .astype(str)
    .str.strip()
)

df_collectives = df_collectives[
    df_collectives["github_account"].str.contains("/", na=False)
].copy()

# owner/repo に分割
df_collectives[["owner", "repo"]] = df_collectives["github_account"].str.split(
    "/",
    n=1,
    expand=True
)

df_collectives["owner"] = df_collectives["owner"].str.strip()
df_collectives["repo"] = df_collectives["repo"].str.strip()

# commit_history と同じ owner-repo 形式
df_collectives["repo_name"] = (
    df_collectives["owner"] + "-" + df_collectives["repo"]
)

df_collectives["opencollective_created_at"] = pd.to_datetime(
    df_collectives["created_at"],
    utc=True
).dt.tz_convert(None)

df_collectives = df_collectives[
    df_collectives["owner"].notna()
    & df_collectives["repo"].notna()
    & (df_collectives["owner"] != "")
    & (df_collectives["repo"] != "")
].copy()

# 同じ GitHub repo が複数 collectives に紐づく場合に備えて、一旦そのまま残す
# 必要ならここで drop_duplicates してもよい
if MAX_REPOS is not None:
    df_collectives = df_collectives.head(MAX_REPOS).copy()

print("Target collectives:", len(df_collectives))
print("Unique GitHub repos:", df_collectives["github_account"].nunique())


# =========================
# 2. GraphQL API helper
# =========================

def run_graphql_query(query, variables, max_retries=5):
    """
    GitHub GraphQL APIを実行する。
    rate limitや一時的なエラーに対して簡単にリトライする。
    """
    for attempt in range(max_retries):
        response = requests.post(
            GITHUB_GRAPHQL_URL,
            headers=HEADERS,
            json={
                "query": query,
                "variables": variables,
            },
            timeout=60,
        )

        # GitHub側の二次制限や一時エラー対策
        if response.status_code in [502, 503, 504]:
            wait_sec = 10 * (attempt + 1)
            print(f"Temporary server error {response.status_code}. Sleep {wait_sec}s and retry.")
            time.sleep(wait_sec)
            continue

        if response.status_code == 403:
            print("403 Forbidden. Response:")
            print(response.text)
            raise RuntimeError("GitHub API 403 Forbidden. Rate limit or permission issue may have occurred.")

        if response.status_code != 200:
            print("GraphQL request failed.")
            print("Status code:", response.status_code)
            print(response.text)
            raise RuntimeError(f"GraphQL request failed with status code {response.status_code}")

        result = response.json()

        if "errors" in result:
            # repoが存在しない、名前変更、権限なしなどもここに来ることがある
            return result

        return result

    raise RuntimeError("GraphQL request failed after retries.")


# =========================
# 3. GraphQL query
# =========================
# issues と pullRequests を別々に取得する
# first: 100 がGraphQL connectionの一般的な最大ページサイズ
# labels は1件あたり最大20個まで取得

ISSUES_QUERY = """
query($owner: String!, $repo: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    issues(first: 100, after: $cursor, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        number
        title
        createdAt
        closedAt
        state
        url
        author {
          login
        }
        labels(first: 20) {
          nodes {
            name
          }
        }
      }
    }
  }
  rateLimit {
    cost
    remaining
    resetAt
  }
}
"""

PULL_REQUESTS_QUERY = """
query($owner: String!, $repo: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequests(first: 100, after: $cursor, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        number
        title
        createdAt
        closedAt
        mergedAt
        state
        merged
        url
        author {
          login
        }
        labels(first: 20) {
          nodes {
            name
          }
        }
      }
    }
  }
  rateLimit {
    cost
    remaining
    resetAt
  }
}
"""


# =========================
# 4. 1リポジトリ分の Issue / PR を取得
# =========================

def labels_to_string(label_connection):
    if not label_connection:
        return ""

    nodes = label_connection.get("nodes") or []
    labels = [
        node.get("name", "")
        for node in nodes
        if node and node.get("name")
    ]

    return ";".join(labels)


def fetch_issues_for_repo(owner, repo):
    rows = []
    cursor = None

    while True:
        variables = {
            "owner": owner,
            "repo": repo,
            "cursor": cursor,
        }

        result = run_graphql_query(ISSUES_QUERY, variables)

        if "errors" in result:
            raise RuntimeError(json.dumps(result["errors"], ensure_ascii=False))

        repository = result["data"]["repository"]
        if repository is None:
            raise RuntimeError("repository is None")

        issues = repository["issues"]
        nodes = issues["nodes"]

        for node in nodes:
            author = node.get("author") or {}

            rows.append({
                "item_type": "issue",
                "number": node.get("number"),
                "title": node.get("title"),
                "created_at": node.get("createdAt"),
                "closed_at": node.get("closedAt"),
                "merged_at": None,
                "state": str(node.get("state")).lower() if node.get("state") else None,
                "is_merged": False,
                "labels": labels_to_string(node.get("labels")),
                "author_login": author.get("login"),
                "url": node.get("url"),
            })

        rate = result["data"].get("rateLimit", {})
        remaining = rate.get("remaining")
        cost = rate.get("cost")
        reset_at = rate.get("resetAt")

        print(f"    issues fetched: {len(rows)}, cost: {cost}, remaining: {remaining}, resetAt: {reset_at}")

        if remaining is not None and remaining < 100:
            print("    Rate limit remaining is low. Sleep 60 seconds.")
            time.sleep(60)

        page_info = issues["pageInfo"]

        if not page_info["hasNextPage"]:
            break

        cursor = page_info["endCursor"]

    return rows


def fetch_pull_requests_for_repo(owner, repo):
    rows = []
    cursor = None

    while True:
        variables = {
            "owner": owner,
            "repo": repo,
            "cursor": cursor,
        }

        result = run_graphql_query(PULL_REQUESTS_QUERY, variables)

        if "errors" in result:
            raise RuntimeError(json.dumps(result["errors"], ensure_ascii=False))

        repository = result["data"]["repository"]
        if repository is None:
            raise RuntimeError("repository is None")

        prs = repository["pullRequests"]
        nodes = prs["nodes"]

        for node in nodes:
            author = node.get("author") or {}

            state = str(node.get("state")).lower() if node.get("state") else None

            # GraphQLのstateは open/closed だが、merged=trueなら分析上 merged にしておく
            if node.get("merged"):
                state_for_analysis = "merged"
            else:
                state_for_analysis = state

            rows.append({
                "item_type": "pull_request",
                "number": node.get("number"),
                "title": node.get("title"),
                "created_at": node.get("createdAt"),
                "closed_at": node.get("closedAt"),
                "merged_at": node.get("mergedAt"),
                "state": state_for_analysis,
                "is_merged": bool(node.get("merged")),
                "labels": labels_to_string(node.get("labels")),
                "author_login": author.get("login"),
                "url": node.get("url"),
            })

        rate = result["data"].get("rateLimit", {})
        remaining = rate.get("remaining")
        cost = rate.get("cost")
        reset_at = rate.get("resetAt")

        print(f"    pull requests fetched: {len(rows)}, cost: {cost}, remaining: {remaining}, resetAt: {reset_at}")

        if remaining is not None and remaining < 100:
            print("    Rate limit remaining is low. Sleep 60 seconds.")
            time.sleep(60)

        page_info = prs["pageInfo"]

        if not page_info["hasNextPage"]:
            break

        cursor = page_info["endCursor"]

    return rows


# =========================
# 5. 全リポジトリから取得
# =========================

all_rows = []
failed_repos = []

for idx, row in enumerate(df_collectives.itertuples(index=False), start=1):
    owner = row.owner
    repo = row.repo

    print(f"\n[{idx}/{len(df_collectives)}] Fetching {owner}/{repo}")

    try:
        issue_rows = fetch_issues_for_repo(owner, repo)
        pr_rows = fetch_pull_requests_for_repo(owner, repo)

        repo_rows = issue_rows + pr_rows

        for item in repo_rows:
            item["collective_id"] = row.id
            item["project_slug"] = row.slug
            item["project_name"] = row.name
            item["github_account"] = row.github_account
            item["repo_name"] = row.repo_name
            item["opencollective_created_at"] = row.opencollective_created_at

        all_rows.extend(repo_rows)

        print(f"  total items for repo: {len(repo_rows)}")

    except Exception as e:
        print(f"  Failed: {owner}/{repo}")
        print(f"  Error: {e}")

        failed_repos.append({
            "collective_id": row.id,
            "project_slug": row.slug,
            "project_name": row.name,
            "github_account": row.github_account,
            "repo_name": row.repo_name,
            "error": str(e),
        })
    
    if idx % 10 == 0:
        #save temp CSV every 10 repos
        df_items_temp = pd.DataFrame(all_rows)
        df_items_temp.to_csv("github_temp_issue_pr_items.csv", index=False)

df_items = pd.DataFrame(all_rows)
df_failed = pd.DataFrame(failed_repos)

print("\n===== Fetch finished =====")
print("Fetched item rows:", len(df_items))
print("Failed repos:", len(df_failed))


# =========================
# 6. item-level CSV整形
# =========================

if len(df_items) > 0:
    df_items["created_at"] = pd.to_datetime(
        df_items["created_at"],
        utc=True,
        errors="coerce"
    ).dt.tz_convert(None)

    df_items["closed_at"] = pd.to_datetime(
        df_items["closed_at"],
        utc=True,
        errors="coerce"
    ).dt.tz_convert(None)

    df_items["merged_at"] = pd.to_datetime(
        df_items["merged_at"],
        utc=True,
        errors="coerce"
    ).dt.tz_convert(None)

    df_items["opencollective_created_at"] = pd.to_datetime(
        df_items["opencollective_created_at"],
        errors="coerce"
    )

    # Open Collective登録日から見た相対月
    # 例:
    # -1 = 登録日前1か月
    #  0 = 登録日から1か月後まで
    #  1 = 登録後2か月目
    df_items["relative_month"] = (
        (df_items["created_at"].dt.year - df_items["opencollective_created_at"].dt.year) * 12
        + (df_items["created_at"].dt.month - df_items["opencollective_created_at"].dt.month)
    )

    # 月境界を厳密に登録日基準で扱いたい場合は、後段のmonthly集計でDateOffsetを使う
    df_items["period"] = np.where(
        df_items["created_at"] < df_items["opencollective_created_at"],
        "before",
        "after"
    )

    # 列順
    item_cols = [
        "collective_id",
        "project_slug",
        "project_name",
        "repo_name",
        "github_account",
        "item_type",
        "number",
        "title",
        "created_at",
        "closed_at",
        "merged_at",
        "state",
        "is_merged",
        "labels",
        "author_login",
        "url",
        "opencollective_created_at",
        "relative_month",
        "period",
    ]

    df_items = df_items[item_cols].copy()

    df_items.to_csv(OUTPUT_ITEMS_CSV, index=False)

else:
    print("No item rows fetched. Skip item CSV.")


if len(df_failed) > 0:
    df_failed.to_csv(OUTPUT_FAILED_REPOS_CSV, index=False)


# =========================
# 7. Open Collective登録前後12か月の月次集計
# =========================
# commit分析と同じように、登録日を起点に -12..11 の24か月を作る

monthly_rows = []

relative_months = list(range(-12, 12))

if len(df_items) > 0:
    for idx, row in enumerate(df_collectives.itertuples(index=False), start=1):
        repo_name = row.repo_name
        github_account = row.github_account
        project_slug = row.slug
        project_name = row.name
        collective_id = row.id
        oc_created_at = row.opencollective_created_at

        repo_items = df_items[
            df_items["collective_id"] == collective_id
        ].copy()

        for relative_month in relative_months:
            month_start = oc_created_at + pd.DateOffset(months=relative_month)
            month_end = oc_created_at + pd.DateOffset(months=relative_month + 1)

            created_in_month = repo_items[
                (repo_items["created_at"] >= month_start)
                & (repo_items["created_at"] < month_end)
            ]

            closed_in_month = repo_items[
                (repo_items["closed_at"] >= month_start)
                & (repo_items["closed_at"] < month_end)
            ]

            merged_in_month = repo_items[
                (repo_items["merged_at"] >= month_start)
                & (repo_items["merged_at"] < month_end)
            ]

            opened_issues = (
                created_in_month["item_type"].eq("issue").sum()
            )

            opened_pull_requests = (
                created_in_month["item_type"].eq("pull_request").sum()
            )

            closed_issues = (
                closed_in_month["item_type"].eq("issue").sum()
            )

            closed_pull_requests = (
                closed_in_month["item_type"].eq("pull_request").sum()
            )

            merged_pull_requests = (
                merged_in_month["item_type"].eq("pull_request").sum()
            )

            monthly_rows.append({
                "collective_id": collective_id,
                "project_slug": project_slug,
                "project_name": project_name,
                "repo_name": repo_name,
                "github_account": github_account,
                "opencollective_created_at": oc_created_at,
                "relative_month": relative_month,
                "period": "before" if relative_month < 0 else "after",
                "month_start": month_start,
                "month_end": month_end,
                "opened_issues": int(opened_issues),
                "closed_issues": int(closed_issues),
                "opened_pull_requests": int(opened_pull_requests),
                "closed_pull_requests": int(closed_pull_requests),
                "merged_pull_requests": int(merged_pull_requests),
            })

    df_monthly = pd.DataFrame(monthly_rows)

    df_monthly.to_csv(OUTPUT_MONTHLY_CSV, index=False)

    print("\nSaved:")
    print(OUTPUT_ITEMS_CSV)
    print(OUTPUT_MONTHLY_CSV)

    if len(df_failed) > 0:
        print(OUTPUT_FAILED_REPOS_CSV)

    print("\n===== Monthly summary preview =====")
    summary = (
        df_monthly
        .groupby("relative_month")
        .agg(
            mean_opened_issues=("opened_issues", "mean"),
            median_opened_issues=("opened_issues", "median"),
            mean_opened_pull_requests=("opened_pull_requests", "mean"),
            median_opened_pull_requests=("opened_pull_requests", "median"),
            mean_merged_pull_requests=("merged_pull_requests", "mean"),
            median_merged_pull_requests=("merged_pull_requests", "median"),
            n_projects=("repo_name", "count"),
        )
        .reset_index()
    )

    print(summary.to_string(index=False))

else:
    print("No item rows fetched. Skip monthly CSV.")
