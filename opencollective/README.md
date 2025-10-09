## 研究内容

OpenCollectiveのAPIを利用して、オープンソースプロジェクトの財務データを収集・分析する。

## 環境構築

* postgreSQLのインストール(path登録も行う)

```bash
psql -U postgres -f sqlsetup.sql
```

## ファイル構成

api-key.txt - OpenCollectiveのAPIキーを保存するテキストファイル。
設定の開発者向けにあるパーソナルトークンを使用してください。

`my-account.py`

OpenCollectiveのAPIを利用して、自分のアカウント情報を取得する。

`project-counter.py`

OpenCollectiveのAPIを利用して、すべてのプロジェクトの数をカウントする。

`get-balance.py`

OpenCollectiveのAPIを利用して、特定のプロジェクトの残高などの情報を取得する。

`save_project_data.py`

OpenCollectiveのAPIを利用して、特定のプロジェクトの財務データをPostgreSQLデータベースに保存する。
