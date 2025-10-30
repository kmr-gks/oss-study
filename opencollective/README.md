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
python transaction_history.py
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

### backup:

pg_dumpall -U postgres -f ".\logs\pg_all_$(Get-Date -Format yyyyMMdd_HHmm).sql"

### password

~\AppData\Roaming\postgresql\pgpass.conf

```
localhost:5432:*:postgres:your_password
```
