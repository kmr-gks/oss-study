from pathlib import Path

DB_NAME = "opencollective"
ITEM_TABLE = "public.github_issue_pr_items"

MONTHS_BEFORE = 12
MONTHS_AFTER = 12

RELATIVE_MONTHS = list(range(-MONTHS_BEFORE, MONTHS_AFTER))

OUTPUT_DIR = Path("github_activity_analysis")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 分析対象指標
METRICS = {
    "opened_issues": {
        "label": "Opened issues",
        "date_column": "created_at",
        "item_type": "issue",
    },
    "closed_issues": {
        "label": "Closed issues",
        "date_column": "closed_at",
        "item_type": "issue",
    },
    "opened_pull_requests": {
        "label": "Opened pull requests",
        "date_column": "created_at",
        "item_type": "pull_request",
    },
    "closed_pull_requests": {
        "label": "Closed pull requests",
        "date_column": "closed_at",
        "item_type": "pull_request",
    },
    "merged_pull_requests": {
        "label": "Merged pull requests",
        "date_column": "merged_at",
        "item_type": "pull_request",
    },
}

# 外れ値除外
TOP_ACTIVITY_PERCENTILE = 0.99

# 統計検定
AFTER_WINDOWS = [1, 3, 6, 12]
ANALYSIS_WINDOWS = [3, 6, 9, 12]
ALPHA = 0.05
COMMIT_TABLE = "public.commit_history"
METRICS = {
    "commits": {
        "label": "Commits",
    },
    "opened_issues": {
        "label": "Opened issues",
        "date_column": "created_at",
        "item_type": "issue",
    },
    "closed_issues": {
        "label": "Closed issues",
        "date_column": "closed_at",
        "item_type": "issue",
    },
    "opened_pull_requests": {
        "label": "Opened pull requests",
        "date_column": "created_at",
        "item_type": "pull_request",
    },
    "closed_pull_requests": {
        "label": "Closed pull requests",
        "date_column": "closed_at",
        "item_type": "pull_request",
    },
    "merged_pull_requests": {
        "label": "Merged pull requests",
        "date_column": "merged_at",
        "item_type": "pull_request",
    },
}
