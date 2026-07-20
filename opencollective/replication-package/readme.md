# Replication Package

This replication package contains the datasets and Python scripts required to reproduce the tables, figures, and statistical analyses reported in the paper.

## 1. Requirements

Python 3 is required.

Install the required Python packages by running:

```bash
python3 -m pip install -r requirements.txt
```

The scripts should be executed from the root directory of the replication package.

Example:

```bash
python3 tableI.py
```

## 2. Package Structure

```text
replication-package/
├── README.md
├── requirements.txt
├── accuracy_calculation.py
├── cohen_kappa_score.py
├── duckdb_util.py
├── output_util.py
├── data1.csv
├── data2.csv
├── data3.csv
├── data4.csv
├── fig1.py
├── fig2.py
├── fig3.py
├── fig4-tableVII.py
├── fig5.py
├── tableI.py
├── tableIII.py
├── tableIV.py
├── tableV.py
├── tableVI.py
├── tableVIII.py
├── data/
│   ├── collectives.parquet
│   ├── collective_transactions.parquet
│   ├── commit_history.parquet
│   └── github_issue_pr_items.parquet
└── results/
    ├── figures/
    │   ├── Fig1.pdf
    │   ├── Fig2.pdf
    │   ├── Fig3.pdf
    │   ├── Fig4.pdf
    │   └── Fig5.pdf
    └── tables/
        ├── table_i.csv
        ├── table_iii.csv
        ├── table_iv.csv
        ├── table_v.csv
        ├── table_vi.csv
        ├── table_vii.csv
        └── table_viii.csv
```

The files in the `results` directory are pre-generated outputs provided for convenience. Running the corresponding scripts regenerates these files.

## 3. Datasets

### 3.1 Data Used for Prompt Tuning

Two different datasets, each containing 381 expense records, were used during prompt tuning.

* `data1.csv`
  The first set of 381 expense records. This file contains the manual labeling results and the corresponding LLM labeling results.

* `data2.csv`
  A second set of 381 expense records that is different from `data1.csv`. This file contains the manual labeling results and the corresponding LLM labeling results.

### 3.2 Data Used for Expense-Purpose Classification

For the main expense-purpose analysis, 1,784 expense records were classified by the LLM in two separate runs.

* `data3.csv`
  Results of the first LLM classification run.

* `data4.csv`
  Results of the second LLM classification run.

### 3.3 Parquet Data

The data extracted from the original database are stored as Parquet files in the `data` directory.

* `data/collectives.parquet`
* `data/collective_transactions.parquet`
* `data/commit_history.parquet`
* `data/github_issue_pr_items.parquet`

The `duckdb_util.py` module registers these files as the following virtual tables in DuckDB:

```text
public.collectives
public.collective_transactions
public.commit_history
public.github_issue_pr_items
```

PostgreSQL does not need to be installed, and the original PostgreSQL database does not need to be restored.

## 4. Evaluation of the Labeling Results

### 4.1 Inter-Rater Agreement

The following script calculates Cohen's kappa coefficient and the simple agreement rate between the manual classifications performed by two authors.

```bash
python3 cohen_kappa_score.py
```

The results are displayed in the terminal.

### 4.2 Accuracy of the LLM Classification

The following script compares the manually assigned ground-truth labels and the LLM-generated labels in `data2.csv`.

```bash
python3 accuracy_calculation.py
```

The script reports accuracy for:

* all records; and
* records with an LLM confidence score of at least 0.9.

The results are displayed in the terminal.

## 5. Reproducing the Tables

### Table I

Run:

```bash
python3 tableI.py
```

Output:

```text
results/tables/table_i.csv
```

### Table III

Run:

```bash
python3 tableIII.py
```

Output:

```text
results/tables/table_iii.csv
```

### Table IV

Run:

```bash
python3 tableIV.py
```

Output:

```text
results/tables/table_iv.csv
```

### Table V

Run:

```bash
python3 tableV.py
```

Output:

```text
results/tables/table_v.csv
```

### Table VI

Run:

```bash
python3 tableVI.py
```

Output:

```text
results/tables/table_vi.csv
```

### Table VII

Run:

```bash
python3 fig4-tableVII.py
```

Outputs:

```text
results/tables/table_vii.csv
results/figures/Fig4.pdf
```

This script generates both Table VII and Fig. 4.

### Table VIII

Run:

```bash
python3 tableVIII.py
```

Output:

```text
results/tables/table_viii.csv
```

The Kruskal–Wallis test result is displayed in the terminal.

## 6. Reproducing the Figures

### Fig. 1

Run:

```bash
python3 fig1.py
```

Output:

```text
results/figures/Fig1.pdf
```

### Fig. 2

Run:

```bash
python3 fig2.py
```

Output:

```text
results/figures/Fig2.pdf
```

### Fig. 3

Run:

```bash
python3 fig3.py
```

Output:

```text
results/figures/Fig3.pdf
```

### Fig. 4

Run:

```bash
python3 fig4-tableVII.py
```

Outputs:

```text
results/figures/Fig4.pdf
results/tables/table_vii.csv
```

This script generates both Fig. 4 and Table VII.

### Fig. 5

Run:

```bash
python3 fig5.py
```

Output:

```text
results/figures/Fig5.pdf
```

The script also performs Kruskal–Wallis tests on the project-level issue-category ratios across the three development-spending groups. The raw and Holm-adjusted p-values are displayed in the terminal and are not saved to a separate file.

## 7. Running All Analyses

To reproduce all tables and figures, run the following commands from the root directory of the replication package:

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

The `fig4-tableVII.py` script only needs to be run once because it generates both Table VII and Fig. 4.

## 8. Output Directories

Generated tables are saved in:

```text
results/tables/
```

Generated figures are saved in:

```text
results/figures/
```

The `output_util.py` module defines and creates these output directories.

Existing files with the same names may be overwritten when the scripts are rerun.

## 9. Python Dependencies

The required packages are listed in `requirements.txt`.

```text
pandas
numpy
matplotlib
scipy
statsmodels
scikit-learn
SQLAlchemy
duckdb
duckdb-engine
pyarrow
forex-python
```

## 10. Notes on Reproducibility

* Run all scripts from the root directory of the replication package.
* Tables are generated as CSV files, and figures are generated as PDF files.
* Some statistical test results are displayed only in the terminal.
* Scripts that perform currency conversion use `forex-python` to retrieve exchange rates against the US dollar.
* An Internet connection is therefore required when running scripts that retrieve exchange rates.
* Because exchange rates may change over time, monetary results generated at a later date may differ slightly from the pre-generated results and the values reported in the paper.
* Minor numerical differences may also occur because of floating-point arithmetic or differences in Python package versions.
* The visual appearance of generated PDF files, including fonts, margins, and line breaks, may vary slightly depending on the operating system and Matplotlib version.
* The pre-generated files in the `results` directory represent the outputs produced for this replication package.
