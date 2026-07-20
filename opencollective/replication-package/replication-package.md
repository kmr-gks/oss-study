TODO

methodology

1. 381件のデータ2回分(手動ラベリング結果、LLMラベリング結果)
data1.csv
data2.csv

カッパ係数計算
rq1_cohen_kappa_score.py

2. 1784件のデータを2回分抽出する
rq1_random_1784sampling.py
正解率計算
rq1_accuracy_calculation.py

3. 2つの1784件のデータに対してラベリングを行う
rq1_labeling_1784samples.py
rq1_labeling_1784samples2.py


table I
`python3 tableI.py`

rq1
TABLE III
`python3 tableIII.py`

table IV
`python3 tableIV.py`

table V
`python3 tableV.py`

table VI
`python3 tableVI.py`

table VIII
`python3 tableVIII.py`

`python3 rq1_cohen_kappa_score.py`
methodologyのcohen kappa score

`python3 rq1_random_1784sampling.py`
methodologyのランダムに1784件のサンプルを抽出するコード

`python3 rq1_labeling_1784samples.py`
methodologyの1784件のサンプルに支出ラベルを付け、多値分類するコード


`python3 pq1_overview.py`
rq1 fig1
rq2 fig2,fig3

`python3 rq2_impact_of_joining_openc.py`
no use

`python3 rq2_monthly_commit_activity.py`
no use

rq3

`python3 rq3_github_issue_pr_fig.py`
no use

`python3 rq3_issue_label_graph_before_after.py`
no use


`python3 rq3_run_registration_analysis.py`
fig4
github_activity_analysis/median_growth_rate_by_window.pdf

`python3 rq3_run_issue_label_tertile_analysis.py`
fig5, kruskal-wallis test
issue_category_composition_by_development_spending_tertile_12m.pdf


table VII
registration_issue_pr_wilcoxon_tests_holm_positive_before_only.csv
