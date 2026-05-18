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

# RQ1
psql -U postgres -d opencollective -f .\rq1.sql
python rq1histgram.py

#2nd random sampling
python random_sampling_2nd.py
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

OSSプロジェクトの資金活用実態の解明

【概要】
現代のITインフラはオープンソースソフトウェア（OSS）に深く依存しているが、多くのプロジェクトは少数のコア開発者に依存しており、開発者の離反やそれによる脆弱性の放置といった持続可能性の危機に直面している。この解決策として企業や個人による資金援助が活発化しているものの、提供された資金が具体的にどのような使途に配分されているかという実態は十分に解明されていない。
本研究は、資金管理プラットフォームOpen Collectiveから取得した約4万件の支出データを対象に、資金の活用パターンを定量的に明らかにすることを目的とする。LLMを用いて支出データにラベル付けを行い、使途を分類した。プロジェクトメンバーへの直接的な開発費、外部貢献者への報奨金（Bounty）、広告宣伝費、non-tech活動費などを明確に区別するカテゴリを定義した。

現代のIT社会においてオープンソースソフトウェア（OSS）は不可欠な基盤であるが、多くのプロジェクトは少数の開発者の献身に依存しており、その持続可能性の確保が急務となっている。この課題に対し、企業や個人による資金援助プラットフォームを介した支援が活発化しているものの、その資金規模の実態、具体的な使途、そして資金提供が実際の発達活動に与える影響については十分に解明されていない。本研究では、これらの中核的な疑問を3つの研究質問（RQ）として定義し、多角的な定量的アプローチによりOSSエコシステムの資金循環の実態解明を試みた。
まず、資金提供の全体規模を明らかにするため、プラットフォームOpen Collectiveから1,915個のプロジェクト、合計4万件以上の資金提供データを収集・分析した。その結果、資金規模に著しい偏りとばらつきが存在することを定量的に示した。
次に、提供された資金の使途を精査するため、LLMを用いた支出データのラベリングを行う。プロジェクトメンバーへの直接的な開発費、外部貢献者への報奨金（Bounty）、宣伝や新規開発者獲得のためのマーケティング・イベント費、および開発以外の活動費などのカテゴリを定義した。
最後に、資金獲得が開発活動に与える直接的な影響を評価するため、各プロジェクトにおいて最大の資金提供が行われた基準日を特定し、その前後のGitHubにおけるコミット数を比較・分析する手法を設計した。これにより、資金提供が開発アクティビティの活性化や持続性にどのように寄与するかを時系列で明らかにする予定である。
本研究は、資金の規模と使途の解明から開発活動への影響評価までを検証するものであり、今後の持続可能なOSS支援エコシステムを設計する上で、実践的かつ学術的に重要な指針を提供する。