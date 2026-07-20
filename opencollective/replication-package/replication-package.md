# Replication Package

本パッケージには、論文中の表、図および統計検定結果を再現するためのデータとPythonスクリプトが含まれています。

## 1. 動作環境

本パッケージはPython 3を使用します。

必要なPythonパッケージは、次のコマンドでインストールできます。

```bash
python3 -m pip install -r requirements.txt
```

各スクリプトは、replication packageのルートディレクトリから実行してください。

例：

```bash
cd replication-package
python3 tableI.py
```

## 2. データ

### 2.1 プロンプトチューニング用データ

プロンプトチューニングでは、381件の支出データからなる異なる2つのデータセットを使用しました。

* `data1.csv`
  1回目のプロンプトチューニングに使用した381件の支出データです。著者による手動ラベリング結果と、LLMによるラベリング結果を含みます。

* `data2.csv`
  2回目のプロンプトチューニングに使用した、`data1.csv`とは異なる381件の支出データです。著者による手動ラベリング結果と、LLMによるラベリング結果を含みます。

### 2.2 支出目的の分類に使用したデータ

実際の支出目的の分析では、1,784件の支出データに対してLLMによる分類を2回実施しました。

* `data3.csv`
  1回目のLLMラベリング結果です。

* `data4.csv`
  2回目のLLMラベリング結果です。

### 2.3 分析用Parquetファイル

データベースから抽出した分析用データを、次のParquetファイルとして`data`ディレクトリに格納しています。

```text
data/
├── collectives.parquet
├── collective_transactions.parquet
├── commit_history.parquet
└── github_issue_pr_items.parquet
```

`duckdb_util.py`は、これらのParquetファイルをDuckDB上の次の仮想テーブルとして登録します。

```text
public.collectives
public.collective_transactions
public.commit_history
public.github_issue_pr_items
```

したがって、本パッケージの実行にPostgreSQLのインストールやデータベースの復元は必要ありません。

## 3. ラベリング結果の評価

### 3.1 著者間一致度

`data2.csv`に含まれる2名の著者による手動分類結果について、Cohenのカッパ係数と単純一致率を計算します。

```bash
python3 cohen_kappa_score.py
```

結果は標準出力に表示されます。

### 3.2 LLMラベリングの正解率

`data2.csv`に含まれる手動正解ラベルとLLMラベリング結果を比較し、全データおよび信頼度が0.9以上のデータについて正解率を計算します。

```bash
python3 accuracy_calculation.py
```

結果は標準出力に表示されます。

## 4. 論文中の表の再現

### Table I

```bash
python3 tableI.py
```

出力：

```text
table_i.csv
```

### Table III

```bash
python3 tableIII.py
```

出力：

```text
table_iii.csv
```

### Table IV

```bash
python3 tableIV.py
```

出力：

```text
table_iv.csv
```

### Table V

```bash
python3 tableV.py
```

出力：

```text
table_v.csv
```

### Table VI

```bash
python3 tableVI.py
```

出力：

```text
table_vi.csv
```

### Table VII

```bash
python3 fig4-tableVII.py
```

出力：

```text
table_vii.csv
Fig4.pdf
```

このスクリプトは、Table VIIとFig. 4を同時に生成します。

### Table VIII

```bash
python3 tableVIII.py
```

出力：

```text
table_viii.csv
```

Kruskal–Wallis検定の結果は標準出力に表示されます。

## 5. 論文中の図の再現

### Fig. 1

```bash
python3 fig1.py
```

出力：

```text
Fig1.pdf
```

### Fig. 2

```bash
python3 fig2.py
```

出力：

```text
Fig2.pdf
```

### Fig. 3

```bash
python3 fig3.py
```

出力：

```text
Fig3.pdf
```

### Fig. 4

```bash
python3 fig4-tableVII.py
```

出力：

```text
Fig4.pdf
table_vii.csv
```

このスクリプトは、Fig. 4とTable VIIを同時に生成します。

### Fig. 5

```bash
python3 fig5.py
```

出力：

```text
Fig5.pdf
```

Issueカテゴリ割合に対するKruskal–Wallis検定およびHolm補正の結果は、標準出力に表示されます。検定結果はファイルとして保存されません。

## 6. ファイル構成

```text
replication-package/
├── README.md
├── requirements.txt
├── accuracy_calculation.py
├── cohen_kappa_score.py
├── duckdb_util.py
├── data1.csv
├── data2.csv
├── data3.csv
├── data4.csv
├── tableI.py
├── tableIII.py
├── tableIV.py
├── tableV.py
├── tableVI.py
├── tableVIII.py
├── fig1.py
├── fig2.py
├── fig3.py
├── fig4-tableVII.py
├── fig5.py
└── data/
    ├── collectives.parquet
    ├── collective_transactions.parquet
    ├── commit_history.parquet
    └── github_issue_pr_items.parquet
```

## 7. 一括実行

すべての表と図を生成する場合は、replication packageのルートディレクトリで次のコマンドを順に実行します。

```bash
python3 tableI.py
python3 tableIII.py
python3 tableIV.py
python3 tableV.py
python3 tableVI.py
python3 fig4-tableVII.py
python3 tableVIII.py
python3 fig1.py
python3 fig2.py
python3 fig3.py
python3 fig5.py
```

`fig4-tableVII.py`はTable VIIとFig. 4の両方を生成するため、一度だけ実行します。

## 8. 注意事項

* 各スクリプトは、replication packageのルートディレクトリから実行してください。
* 図はPDF形式、表はCSV形式で出力されます。
* 一部の統計検定結果は、ファイルではなく標準出力に表示されます。
* 為替換算を行うスクリプトは、`forex-python`を使用してUSDへの為替レートを取得します。そのため、実行時にはインターネット接続が必要です。
* 為替レートは取得時点によって変化するため、実行時期によって金額に関する結果が論文中の値とわずかに異なる可能性があります。
* 浮動小数点演算やライブラリのバージョンの違いにより、結果の最終桁がわずかに異なる場合があります。
* PDFのフォント、余白および改行位置は、OSやMatplotlibのバージョンによってわずかに異なる場合があります。
