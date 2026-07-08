import time
import json
import api
import requests
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import api
import sys


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


def create_github_issue_pr_tables(engine):
    create_items_table_sql = """
    CREATE TABLE IF NOT EXISTS public.github_issue_pr_items (
        collective_id TEXT,
        project_slug TEXT,
        project_name TEXT,
        repo_name TEXT NOT NULL,
        github_account TEXT NOT NULL,

        item_type TEXT NOT NULL,
        number INTEGER NOT NULL,
        title TEXT,

        created_at TIMESTAMP,
        closed_at TIMESTAMP,
        merged_at TIMESTAMP,

        state TEXT,
        is_merged BOOLEAN,
        labels TEXT,

        author_login TEXT,
        author_email TEXT,
        author_url TEXT,

        closed_by_login TEXT,
        closed_by_email TEXT,
        closed_by_url TEXT,

        merged_by_login TEXT,
        merged_by_email TEXT,
        merged_by_url TEXT,

        url TEXT,

        opencollective_created_at TIMESTAMP,
        relative_month INTEGER,
        period TEXT,

        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        PRIMARY KEY (repo_name, item_type, number)
    );
    """

    with engine.begin() as conn:
        conn.execute(text(create_items_table_sql))

    print("Tables are ready.")
create_github_issue_pr_tables(engine)

# =========================
# 1. Open Collective登録プロジェクトを取得
#    ただし、commit_history に存在するリポジトリだけを対象にする
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

query_commit_repos = """
SELECT DISTINCT
    repo_name
FROM public.commit_history
WHERE repo_name IS NOT NULL
"""

df_collectives = pd.read_sql(query_collectives, engine)
df_commit_repos = pd.read_sql(query_commit_repos, engine)

# -------------------------
# collectives 側の前処理
# -------------------------

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

# -------------------------
# commit_history 側の前処理
# -------------------------

df_commit_repos["repo_name"] = (
    df_commit_repos["repo_name"]
    .str.strip()
)

commit_repo_set = set(df_commit_repos["repo_name"].dropna().unique())

# -------------------------
# commit_history に存在するリポジトリだけ残す
# -------------------------

n_before_filter = len(df_collectives)
unique_before_filter = df_collectives["repo_name"].nunique()

df_collectives = df_collectives[
    df_collectives["repo_name"].isin(commit_repo_set)
].copy()

n_after_filter = len(df_collectives)
unique_after_filter = df_collectives["repo_name"].nunique()

print("===== Repository filtering by commit_history =====")
print("Collectives with owner/repo:", n_before_filter)
print("Unique repos before filtering:", unique_before_filter)
print("Repos in commit_history:", len(commit_repo_set))
print("Collectives matched with commit_history:", n_after_filter)
print("Unique repos matched with commit_history:", unique_after_filter)
print("Match rate among collectives:", n_after_filter / n_before_filter)

if MAX_REPOS is not None:
    df_collectives = df_collectives.head(MAX_REPOS).copy()

print("Target collectives:", len(df_collectives))
print("Unique GitHub repos:", df_collectives["github_account"].nunique())


# =========================
# 2. GraphQL API helper
# =========================

def run_graphql_query(query, variables, max_retries=500):
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
            print(f"Temporary server error {response.status_code}. Sleep {wait_sec}s and retry.\r", end="")
            time.sleep(wait_sec)
            continue

        if response.status_code == 403:
            if "rate limit" in str(response.text):
                print(f"Rate limit exceeded. Sleep for {10*(attempt+1)}s and retry.\r", end="")
                time.sleep(10*(attempt+1))
                continue
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
            if result['errors'][0]['type'] == 'RATE_LIMIT':
                print(f"Rate limit exceeded. Sleep for {10*(attempt+1)}s and retry.\r", end="")
                time.sleep(10*(attempt+1))
                continue
            print(f"other GraphQL errors: {result['errors'][0]}")
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
          url
          ... on User {
            email
          }
        }
        labels(first: 20) {
          nodes {
            name
          }
        }
        timelineItems(
          first: 20,
          itemTypes: [CLOSED_EVENT]
        ) {
          nodes {
            __typename
            ... on ClosedEvent {
              createdAt
              actor {
                login
                url
                ... on User {
                  email
                }
              }
            }
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
          url
          ... on User {
            email
          }
        }
        mergedBy {
          login
          url
          ... on User {
            email
          }
        }
        labels(first: 20) {
          nodes {
            name
          }
        }
        timelineItems(
          first: 20,
          itemTypes: [CLOSED_EVENT]
        ) {
          nodes {
            __typename
            ... on ClosedEvent {
              createdAt
              actor {
                login
                url
                ... on User {
                  email
                }
              }
            }
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


def get_last_closed_event_actor(timeline_items):
    """
    timelineItems から最後の ClosedEvent の actor を取り出す。
    Issue/PR は reopen -> close があり得るため、最後の close を使う。
    """
    if not timeline_items:
        return None

    nodes = timeline_items.get("nodes") or []

    closed_events = [
        node for node in nodes
        if node and node.get("__typename") == "ClosedEvent"
    ]

    if not closed_events:
        return None

    closed_events = sorted(
        closed_events,
        key=lambda x: x.get("createdAt") or ""
    )

    return closed_events[-1].get("actor")


def actor_to_dict(actor, prefix):
    """
    GitHub GraphQL の Actor/User 情報を平坦なdictにする。
    email は User の公開メールアドレスがある場合のみ入る。
    Bot や Mannequin などでは email が存在しないことがある。
    """
    if not actor:
        return {
            f"{prefix}_login": None,
            f"{prefix}_email": None,
            f"{prefix}_url": None,
        }

    return {
        f"{prefix}_login": actor.get("login"),
        f"{prefix}_email": actor.get("email"),
        f"{prefix}_url": actor.get("url"),
    }


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
            author_info = actor_to_dict(node.get("author"), "author")

            closed_actor = get_last_closed_event_actor(
                node.get("timelineItems")
            )
            closed_by_info = actor_to_dict(closed_actor, "closed_by")

            row = {
                "item_type": "issue",
                "number": node.get("number"),
                "title": node.get("title"),
                "created_at": node.get("createdAt"),
                "closed_at": node.get("closedAt"),
                "merged_at": None,
                "state": str(node.get("state")).lower() if node.get("state") else None,
                "is_merged": False,
                "labels": labels_to_string(node.get("labels")),
                "url": node.get("url"),
                "merged_by_login": None,
                "merged_by_email": None,
                "merged_by_url": None,
            }

            row.update(author_info)
            row.update(closed_by_info)

            rows.append(row)

        rate = result["data"].get("rateLimit", {})
        remaining = rate.get("remaining")
        cost = rate.get("cost")
        reset_at = rate.get("resetAt")

        print(f"    issues fetched: {len(rows)}, cost: {cost}, remaining: {remaining}, resetAt: {reset_at}\r", end="")

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
            author_info = actor_to_dict(node.get("author"), "author")

            closed_actor = get_last_closed_event_actor(
                node.get("timelineItems")
            )
            closed_by_info = actor_to_dict(closed_actor, "closed_by")

            merged_by_info = actor_to_dict(node.get("mergedBy"), "merged_by")

            state = str(node.get("state")).lower() if node.get("state") else None

            if node.get("merged"):
                state_for_analysis = "merged"
            else:
                state_for_analysis = state

            row = {
                "item_type": "pull_request",
                "number": node.get("number"),
                "title": node.get("title"),
                "created_at": node.get("createdAt"),
                "closed_at": node.get("closedAt"),
                "merged_at": node.get("mergedAt"),
                "state": state_for_analysis,
                "is_merged": bool(node.get("merged")),
                "labels": labels_to_string(node.get("labels")),
                "url": node.get("url"),
            }

            row.update(author_info)
            row.update(closed_by_info)
            row.update(merged_by_info)
            rows.append(row)

        rate = result["data"].get("rateLimit", {})
        remaining = rate.get("remaining")
        cost = rate.get("cost")
        reset_at = rate.get("resetAt")

        print(f"    pull requests fetched: {len(rows)}, cost: {cost}, remaining: {remaining}, resetAt: {reset_at}\r", end="")


        page_info = prs["pageInfo"]

        if not page_info["hasNextPage"]:
            break

        cursor = page_info["endCursor"]

    return rows


def normalize_datetime_columns(df):
    datetime_cols = [
        "created_at",
        "closed_at",
        "merged_at",
        "opencollective_created_at",
    ]

    for col in datetime_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(
                df[col],
                utc=True,
                errors="coerce"
            ).dt.tz_convert(None)

    return df


def save_repo_items_to_db(engine, repo_rows):
    if not repo_rows:
        return 0

    df_repo = pd.DataFrame(repo_rows)

    df_repo = normalize_datetime_columns(df_repo)

    required_cols = [
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
        "author_email",
        "author_url",

        "closed_by_login",
        "closed_by_email",
        "closed_by_url",

        "merged_by_login",
        "merged_by_email",
        "merged_by_url",

        "url",
        "opencollective_created_at",
        "relative_month",
        "period",
    ]

    for col in required_cols:
        if col not in df_repo.columns:
            df_repo[col] = None

    df_repo = df_repo[required_cols].copy()

    insert_sql = text("""
        INSERT INTO public.github_issue_pr_items (
            collective_id,
            project_slug,
            project_name,
            repo_name,
            github_account,

            item_type,
            number,
            title,

            created_at,
            closed_at,
            merged_at,

            state,
            is_merged,
            labels,

            author_login,
            author_email,
            author_url,

            closed_by_login,
            closed_by_email,
            closed_by_url,

            merged_by_login,
            merged_by_email,
            merged_by_url,

            url,
            opencollective_created_at,
            relative_month,
            period
        )
        VALUES (
            :collective_id,
            :project_slug,
            :project_name,
            :repo_name,
            :github_account,

            :item_type,
            :number,
            :title,

            :created_at,
            :closed_at,
            :merged_at,

            :state,
            :is_merged,
            :labels,

            :author_login,
            :author_email,
            :author_url,

            :closed_by_login,
            :closed_by_email,
            :closed_by_url,

            :merged_by_login,
            :merged_by_email,
            :merged_by_url,

            :url,
            :opencollective_created_at,
            :relative_month,
            :period
        )
        ON CONFLICT (repo_name, item_type, number)
        DO UPDATE SET
            collective_id = EXCLUDED.collective_id,
            project_slug = EXCLUDED.project_slug,
            project_name = EXCLUDED.project_name,
            github_account = EXCLUDED.github_account,

            title = EXCLUDED.title,

            created_at = EXCLUDED.created_at,
            closed_at = EXCLUDED.closed_at,
            merged_at = EXCLUDED.merged_at,

            state = EXCLUDED.state,
            is_merged = EXCLUDED.is_merged,
            labels = EXCLUDED.labels,

            author_login = EXCLUDED.author_login,
            author_email = EXCLUDED.author_email,
            author_url = EXCLUDED.author_url,

            closed_by_login = EXCLUDED.closed_by_login,
            closed_by_email = EXCLUDED.closed_by_email,
            closed_by_url = EXCLUDED.closed_by_url,

            merged_by_login = EXCLUDED.merged_by_login,
            merged_by_email = EXCLUDED.merged_by_email,
            merged_by_url = EXCLUDED.merged_by_url,

            url = EXCLUDED.url,
            opencollective_created_at = EXCLUDED.opencollective_created_at,
            relative_month = EXCLUDED.relative_month,
            period = EXCLUDED.period,
            fetched_at = CURRENT_TIMESTAMP
    """)

    records = df_repo.replace({np.nan: None}).to_dict(orient="records")

    # ここが重要:
    # engine.begin() のブロック単位で transaction が張られ、
    # ブロックを抜けると commit される
    with engine.begin() as conn:
        conn.execute(insert_sql, records)

    return len(records)


def get_already_fetched_repos(engine):
    query = """
    SELECT DISTINCT repo_name
    FROM public.github_issue_pr_items
    WHERE repo_name IS NOT NULL
    """

    try:
        df = pd.read_sql(query, engine)
        return set(df["repo_name"].dropna().astype(str))
    except Exception:
        return set()


# =========================
# 5. 全リポジトリから取得して、1リポジトリごとにDB保存
# =========================
total_saved_rows = 0
failed_count = 0
from_idx, to_idx = int(sys.argv[1]), int(sys.argv[2])

already_fetched_repos = set()
already_fetched_repos = get_already_fetched_repos(engine)
print("Already fetched repos:", len(already_fetched_repos))

for idx, row in enumerate(df_collectives.itertuples(index=False), start=1):
    owner = row.owner
    repo = row.repo
    repo_name = row.repo_name

    if  repo_name in already_fetched_repos or idx < from_idx or idx > to_idx:
        continue

    print(f"\n[{idx}/{len(df_collectives)}]({from_idx}~{to_idx}) Fetching {owner}/{repo}")

    try:
        issue_rows = fetch_issues_for_repo(owner, repo)
        pr_rows = fetch_pull_requests_for_repo(owner, repo)

        repo_rows = issue_rows + pr_rows

        for item in repo_rows:
            item["collective_id"] = str(row.id)
            item["project_slug"] = row.slug
            item["project_name"] = row.name
            item["github_account"] = row.github_account
            item["repo_name"] = row.repo_name
            item["opencollective_created_at"] = row.opencollective_created_at

            created_at = pd.to_datetime(
                item.get("created_at"),
                utc=True,
                errors="coerce"
            )

            oc_created_at = pd.to_datetime(
                row.opencollective_created_at,
                utc=True,
                errors="coerce"
            )

            if pd.notna(created_at) and pd.notna(oc_created_at):
                created_at_naive = created_at.tz_convert(None)
                oc_created_at_naive = oc_created_at.tz_convert(None)

                item["relative_month"] = (
                    (created_at_naive.year - oc_created_at_naive.year) * 12
                    + (created_at_naive.month - oc_created_at_naive.month)
                )

                item["period"] = (
                    "before"
                    if created_at_naive < oc_created_at_naive
                    else "after"
                )
            else:
                item["relative_month"] = None
                item["period"] = None

        saved_rows = save_repo_items_to_db(engine, repo_rows)
        total_saved_rows += saved_rows

        print(f"  saved rows for repo: {saved_rows}.")
        print(f"  total saved rows so far: {total_saved_rows}.")

    except Exception as e:
        print(f"  Failed: {owner}/{repo}")
        print(f"  Error: {e}")

        failed_row = {
            "collective_id": str(row.id),
            "project_slug": row.slug,
            "project_name": row.name,
            "github_account": row.github_account,
            "repo_name": row.repo_name,
            "error": str(e),
        }
        failed_count += 1

print("\n===== Fetch finished =====")
print("Total saved rows:", total_saved_rows)
print("Failed repos:", failed_count)


df_items = pd.read_sql(
    """
    SELECT *
    FROM public.github_issue_pr_items
    WHERE relative_month BETWEEN -12 AND 11
    """,
    engine
)

df_monthly = (
    df_items
    .groupby(["project_slug", "repo_name", "relative_month", "period"])
    .agg(
        opened_issues=("item_type", lambda s: (s == "issue").sum()),
        opened_pull_requests=("item_type", lambda s: (s == "pull_request").sum()),
        merged_pull_requests=("is_merged", "sum"),
    )
    .reset_index()
)

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
