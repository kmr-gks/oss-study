import csv
import os
import subprocess
from pathlib import Path


# ===== 設定 =====
PSQL_USER = "postgres"
PSQL_DB = "opencollective"

# 作業ディレクトリ: カレントディレクトリ
WORK_DIR = Path(os.getcwd()) / "work"
CSV_PATH = WORK_DIR / "repos.csv"

CLONE_DIR = WORK_DIR / "cloned_repos"
FAILED_PATH = CLONE_DIR / "failed.txt"

# git clone を軽くする（履歴中心）
GIT_CLONE_ARGS = ["git", "clone", "--filter=blob:none", "--no-checkout"]


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a command and return CompletedProcess (no exception)."""
    return subprocess.run(cmd, text=True, capture_output=True, shell=False)
    #print(f"[CMD] {' '.join(cmd)}")
    #return 0


def export_repo_list_with_psql() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    # Windows path in psql \copy: backslashがあると面倒なので、/ に寄せる
    csv_path_for_psql = str(CSV_PATH).replace("\\", "/")

    sql = rf"""
\copy (
  SELECT DISTINCT
    split_part(github_account, '/', 1) AS owner,
    split_part(github_account, '/', 2) AS repo
  FROM collectives
  WHERE github_account LIKE '%/%'
) TO '{csv_path_for_psql}' WITH (FORMAT csv, HEADER true)
""".strip()

    print(f"[STEP1] Export repo list via psql -> {CSV_PATH}")

    # 重要：psql の -c は 1コマンドとして渡す（改行含んでOK）
    proc = run(["psql", "-U", PSQL_USER, "-d", PSQL_DB, "-v", "ON_ERROR_STOP=1", "-c", sql])

    if proc.returncode != 0:
        print("[ERROR] psql failed.")
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit(proc.returncode)

    if not CSV_PATH.exists():
        raise SystemExit(f"[ERROR] CSV was not created: {CSV_PATH}")


def iter_repos_from_csv():
    with CSV_PATH.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            owner = (row.get("owner") or "").strip()
            repo = (row.get("repo") or "").strip()
            if not owner or not repo:
                continue
            yield owner, repo


def clone_repos() -> None:
    CLONE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[STEP2] Clone repos into -> {CLONE_DIR}")

    for owner, repo in iter_repos_from_csv():
        url = f"https://github.com/{owner}/{repo}.git"
        target_dir = CLONE_DIR / f"{owner}-{repo}"

        if target_dir.exists():
            print(f"[SKIP] exists: {owner}/{repo}")
            continue

        print(f"[CLONE] {owner}/{repo}")

        proc = run(GIT_CLONE_ARGS + [url, str(target_dir)])

        if proc.returncode != 0:
            print(f"[FAIL] {owner}/{repo}")
            # 失敗ログ
            with FAILED_PATH.open("a", encoding="utf-8") as ff:
                ff.write(f"{owner}/{repo}\n")

            # デバッグ用に最後だけ少し出す（大量ログになりすぎるのを防ぐ）
            if proc.stderr:
                print(proc.stderr.strip().splitlines()[-1])
            continue


def main():
    export_repo_list_with_psql()
    clone_repos()
    print(f"[DONE] Failed list: {FAILED_PATH}")


if __name__ == "__main__":
    main()
