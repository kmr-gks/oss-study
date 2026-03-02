## 研究内容

OpenCollectiveのAPIを利用して、オープンソースプロジェクトの財務データを収集・分析する。

## 環境構築

* postgreSQLのインストール(path登録も行う)

```bash
psql -U postgres -f sqlsetup.sql
```

## How to run

credentials.jsonを作成する。

```json
{
	"opencollective": {
		"api_token": "your_api_token_here"
	},
	"postgresql": {
		"password": "your_postgresql_password_here",
	}
}

```

```PowerShell
cd opencollective
python project-counter.py
python save_project_data.py
# mine collective data
python save_collective_data.py
cd ~\Desktop\oss-study\opencollective
python .\collective_expenses.py
# mine transactions data
python .\collective_transactions.py
pg_dumpall -U postgres -f ".\logs\pg_all_$(Get-Date -Format yyyyMMdd_HHmm).sql"
# add github column
psql -U postgres -d opencollective -f .\add-github.sql
psql -U postgres -d opencollective -f .\set_unique_repos.sql
psql -U postgres -d opencollective -f .\expense_ranking.sql
python .\clone-repos.py
psql -U postgres -d opencollective -f .\commit_table.sql
# mine commits data
python .\mine_commits.py
psql -U postgres -d opencollective -f .\expense_ranking.sql
psql -U postgres -d opencollective -f .\expense_amount_ranking.sql

psql -U postgres -d opencollective -f .\compare-by-max-contribution.sql -v var1="'30 days'" > commit-num-by-30days-of-max-use.csv
psql -U postgres -d opencollective -f .\compare-by-max-contribution.sql -v var1="'180 days'" > commit-num-by-180days-of-max-use.csv
python .\commit_rate_by_max_contribution.py

#rule-based labeling
psql -U postgres -d opencollective -f .\count_expense_breakdown.sql >results.txt
#random sampling for manual labeling
psql -U postgres -d opencollective -f .\random_sampling.sql > label_sample_expense_100.csv
```

## ファイル構成

api-key.txt - OpenCollectiveのAPIキーを保存するテキストファイル。
設定の開発者向けにあるパーソナルトークンを使用してください。

`my-account.py`

OpenCollectiveのAPIを利用して、自分のアカウント情報を取得する。

`project-counter.py`

OpenCollectiveのAPIを利用して、すべてのプロジェクトの数をカウントする。

`schema-check.py`

OpenCollectiveのAPIを利用して、プロジェクト(Account型)のスキーマ情報を取得し、表示する。

`get-balance.py`

OpenCollectiveのAPIを利用して、特定のプロジェクトの残高などの情報を取得する。

`save_project_data.py`

OpenCollectiveのAPIを利用して、特定のプロジェクトの財務データをPostgreSQLデータベースに保存する。

`add-github.sql`
他のカラムからリポジトリ名を取得する。　

`count_unique_repos.sql`
ユニークなリポジトリ数をカウントする。

### backup:

pg_dumpall -U postgres -f ".\logs\pg_all_$(Get-Date -Format yyyyMMdd_HHmm).sql"

### password

~\AppData\Roaming\postgresql\pgpass.conf

```
localhost:5432:*:postgres:your_password
```
