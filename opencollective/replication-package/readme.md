# Replication Package

This package contains the data and Python scripts needed to reproduce every table, figure, and number reported in the paper
*Beyond Receiving Funding: How Financial Allocation Relates to Development and Maintenance in Open Source Projects* (QuASoQ 2026).

## 1. Requirements

* Python 3
* The packages listed in `requirements.txt`:

```bash
python3 -m pip install -r requirements.txt
```

Run all scripts from the root directory of this package. No database server and no Internet connection are needed:
the data are read from Parquet files through DuckDB, and all monetary values are converted with the fixed exchange rates in
`data/exchange_rates_to_usd.json` (see Section 6).

`table5_activity_tests.py` and `text_recipient_commit_activity.py` load the full commit history
(`data/commit_history.parquet`) and need more memory than the other scripts (more than 4 GB of RAM).

## 2. Reproducing all results

```bash
# Tables
python3 table2_transactions_by_kind.py
python3 table3_contribution_expense_stats.py   # run after table2 (consistency check)
python3 table4_expense_purposes.py
python3 table5_activity_tests.py
python3 table6_commit_growth_by_dev_spending.py

# Figures
python3 fig1_money_flow.py
python3 fig2_issue_categories.py

# Numbers reported in the text
python3 text_dataset_summary.py
python3 text_yearly_contributions.py
python3 text_recipient_commit_activity.py
python3 labeling_cohen_kappa.py
python3 labeling_llm_accuracy.py
```

Each script prints its result to the terminal and writes it to `results/tables/` (CSV) or `results/figures/` (PDF).
Existing files with the same names are overwritten.

## 3. Correspondence between the paper and the scripts

### Tables and figures

| Paper | Script | Output |
|---|---|---|
| Table 1: Definitions of expense categories | – (category definitions given to the LLM) | – |
| Table 2: Transaction records by kind | `table2_transactions_by_kind.py` | `results/tables/table2_transactions_by_kind.csv` |
| Table 3: Transaction statistics for contributions and expenses | `table3_contribution_expense_stats.py` | `results/tables/table3_contribution_expense_stats.csv` |
| Table 4: Expense purpose distribution | `table4_expense_purposes.py` | `results/tables/table4_expense_purposes.csv` |
| Table 5: Holm-adjusted *p*-values for pre-/post-registration activity | `table5_activity_tests.py` | `results/tables/table5_activity_tests.csv`<br>`results/tables/table5_activity_tests_detail.csv` (all test statistics and raw *p*-values) |
| Table 6: Commit growth by development-spending group | `table6_commit_growth_by_dev_spending.py` | `results/tables/table6_commit_growth_by_dev_spending.csv`<br>`results/tables/table6_commit_growth_test.csv` (Mann–Whitney U test, Cliff's delta) |
| Fig. 1: Money flow by account type | `fig1_money_flow.py` | `results/figures/fig1_money_flow.pdf`<br>`results/tables/fig1_money_flow_amounts.csv` (amount of each cell) |
| Fig. 2: Issue-category composition | `fig2_issue_categories.py` | `results/figures/fig2_issue_categories.pdf`<br>`results/tables/fig2_category_shares.csv` (aggregate shares)<br>`results/tables/fig2_sample_sizes.csv` (projects and issues per group)<br>`results/tables/fig2_category_tests.csv` (project-level Mann–Whitney U tests with Holm correction) |

### Numbers reported in the text

| Paper | Script | Output |
|---|---|---|
| Dataset size (Section 3.1) | `text_dataset_summary.py` | `results/tables/text_dataset_summary.csv` |
| Inter-rater agreement, Cohen's κ (Section 3.3) | `labeling_cohen_kappa.py` | `results/tables/labeling_cohen_kappa.csv` |
| Accuracy of the LLM classifier (Section 3.3) | `labeling_llm_accuracy.py` | `results/tables/labeling_llm_accuracy.csv` |
| Yearly contribution amounts and counts (Section 4.1, RQ1) | `text_yearly_contributions.py` | `results/tables/text_yearly_contributions.csv` |
| Commit activity of matched payment recipients (Section 4.2, RQ2) | `text_recipient_commit_activity.py` | `results/tables/text_recipient_commit_activity.csv` |
| Number of high-confidence expense classifications (Section 3.3) | `table4_expense_purposes.py` | sum of `count` in `results/tables/table4_expense_purposes.csv` |
| Mean of `ADDED_FUNDS` records (Section 4.1) | `table2_transactions_by_kind.py` | `amount_musd` / `count` of `ADDED_FUNDS` |

## 4. Input data

### 4.1 Parquet data (`data/`)

Data extracted from the original PostgreSQL database. `duckdb_util.py` registers them as virtual tables in DuckDB,
so PostgreSQL does not need to be installed.

| File | Virtual table | Content |
|---|---|---|
| `data/collectives.parquet` | `public.collectives` | Open Collective accounts (collectives and their project sub-accounts) |
| `data/collective_transactions.parquet` | `public.collective_transactions` | Transactions, including the binary development-related classification (`is_development`) |
| `data/commit_history.parquet` | `public.commit_history` | Commit histories of the linked GitHub repositories |
| `data/github_issue_pr_items.parquet` | `public.github_issue_pr_items` | Issues and pull requests of the linked GitHub repositories |
| `data/exchange_rates_to_usd.json` | – | Fixed exchange rates to USD used by all scripts |

### 4.2 Labeling data (CSV in the root directory)

| File | Records | Content |
|---|---|---|
| `data1.csv` | 381 | First random sample of expenses, used to design the expense categories. Manual labels of two authors and the LLM label. |
| `data2.csv` | 381 | Second, distinct random sample. Manual labels of two authors, consensus label (`manual_true_label`), and the labels and confidence scores of the LLM runs. Used for Cohen's κ and the accuracy of the LLM classifier. |
| `data3.csv` | 1,784 | Expense-purpose classification by the LLM, first run (label and confidence). |
| `data4.csv` | 1,784 | Expense-purpose classification by the LLM, second run on a different random subset. |

`table4_expense_purposes.py` combines `data3.csv` and `data4.csv` and keeps the records with a confidence score of at least 0.90.

### 4.3 LLM prompts (`prompts/`)

| File | Model | Used for |
|---|---|---|
| `prompts/expense_purpose_prompt.txt` | GPT-5.4 | Expense-purpose classification into the seven categories of Table 1 (`data2.csv`, `data3.csv`, `data4.csv`) |
| `prompts/development_binary_prompt.txt` | GPT-5.4 mini | Binary classification (development vs. others) stored as `is_development` in `data/collective_transactions.parquet` |

`{description}` in each prompt is replaced by the expense description. The LLM returns a JSON object with a label,
a confidence score, and a short reason. The prompts were taken verbatim from the scripts that produced the data.

## 5. Output format

* Tables are written as CSV (UTF-8, comma-separated, one header row, no index column).
* Column names are in `snake_case` and state their unit where relevant
  (`_usd` = US dollars, `_musd` = million US dollars, `_pct` = percent).
* Values are stored **unrounded**; the paper rounds them for presentation.
  For example, `table5_activity_tests.csv` contains the exact Holm-adjusted *p*-values that are shown as "<.001" in the paper.
* Rows and columns follow the order used in the paper.
* Figures are written as PDF with TrueType fonts embedded.

## 6. Notes on reproducibility

* **Double-entry records.** Open Collective records each transfer as a `CREDIT` entry and a `DEBIT` entry. All scripts keep only one
  side of each record (`CREDIT` for `CONTRIBUTION`, `DEBIT` for `EXPENSE`; see `KIND_TO_TYPE` in `transaction_util.py`) so that the same
  transfer is not counted twice.
* **Exchange rates.** All amounts are converted to USD with the rates in `data/exchange_rates_to_usd.json`. Using these fixed rates,
  re-running the scripts yields the values reported in the paper. Transactions in currencies without a rate in this file
  (shown as `null`) are excluded. If a currency is missing from the file, `transaction_util.py` retrieves its current rate with
  `forex-python` (Internet connection required) and adds it to the file; this does not happen for the data in this package.
* Minor numerical differences may occur because of floating-point arithmetic or different package versions.
* The appearance of the generated PDF files may vary slightly with the operating system and the Matplotlib version.

## 7. Shared modules

These modules are imported by the scripts above and are not run directly.

| Module | Purpose |
|---|---|
| `duckdb_util.py` | Registers the Parquet files as DuckDB tables |
| `output_util.py` | Defines and creates the output directories |
| `transaction_util.py` | Removes double-entry counterparts and provides the fixed exchange rates |
| `money_flow_util.py` | Loads contributions and expenses for Fig. 1 |
| `commit_growth_util.py` | Expense loading, commit windows, and effect sizes for Table 6 and Fig. 2 |
| `issue_category_util.py` | Issue-label categories and data loading for Fig. 2 |

`commit_growth_util.py` and `issue_category_util.py` also contain functions from an earlier three-group (tertile) version of the
analysis that is not reported in the paper.
