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

psql -U postgres -d opencollective -f .\compare-by-max-use.sql -v var1="'30 days'" > commit-num-by-30days-of-max-use.csv
psql -U postgres -d opencollective -f .\compare-by-max-use.sql -v var1="'180 days'" > commit-num-by-180days-of-max-use.csv
python .\commit_rate_by_max_contribution.py

#rule-based labeling
psql -U postgres -d opencollective -f .\count_expense_breakdown.sql >results.txt
#random sampling for manual labeling
psql -U postgres -d opencollective -f .\random_sampling.sql > label_sample_expense_100.csv

#教師あり学習を行うため支出のデータをcsvに出力
psql -U postgres -d opencollective -f .\export_transactions.sql > transactions.csv
#ラベル分類を実施
python .\ml-labeling.py
#分類結果をまとめる
python .\expense-labeling-results.py

#labeling by using LLM
psql -U postgres -d opencollective -f .\select_rows_randomly.sql > expenses_random_order.csv

export OPENAI_API_KEY="your-api-key"
python labeling_by_llm.py
python heatmap.py

# PQ1
psql -U postgres -d opencollective -f .\pq1.sql
python pq1histgram.py

#2nd random sampling
python random_sampling_2nd.py

#RQ1

#RQ2

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

pg\_dumpall -U postgres -f ".\logs\pg\_all\_\$(Get-Date -Format yyyyMMdd\_HHmm).sql"

### password

\~\AppData\Roaming\postgresql\pgpass.conf

```
localhost:5432:*:postgres:your_password
```

### SIGSS 202607 のアブストラクト

オープンソースプロジェクトにおける資金提供と開発活動に与える影響の分析

OSSの持続可能性確保に向け資金援助が活発化しているが、その規模や使途、開発への影響は不明である。本研究は資金提供の実態解明を試みた。具体的には、資金提供の全体規模とプロジェクトごとの偏りを提示し、支出データを開発費や活動費等に分類して使途を精査する。さらに、資金獲得前後での開発活動の変化を比較・検証する。本成果は、今後の持続可能なOSS支援エコシステムを設計する指針となる。

An Analysis of Funding and Its Impact on Development Activities in Open Source Projects

Financial support for ensuring the sustainability of Open Source Software (OSS) has been growing. However, its overall scale, how the funds are used, and its impact on development remain unclear. This study aims to clarify the reality of OSS funding. Specifically, we reveal the total scale of funding and its unequal distribution among projects. We also examine how funds are used by classifying expense data into categories such as development and non-technical activities. Furthermore, we compare and analyze changes in development activities before and after receiving funds. Our findings will provide a guideline for designing a sustainable OSS support ecosystem in the future.
