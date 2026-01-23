`psql -U postgres -d opencollective`

`\dt`

    テーブル一覧

| スキーマ | 名前                    | タイプ   | 所有者   |
| -------- | ----------------------- | -------- | -------- |
| public   | collective_expenses     | テーブル | postgres |
| public   | collective_transactions | テーブル | postgres |
| public   | collectives             | テーブル | postgres |
| public   | projects                | テーブル | postgres |
| public   | transactions            | テーブル | postgres |

`select * from information_schema.columns where table_name='collectives';`

| column_name             | ordinal_position | column_default     | is_nullable | data_type                   | character_octet_length | numeric_precision_radix | datetime_precision | udt_name  | dtd_identifier |
| ----------------------- | ---------------- | ------------------ | ----------- | --------------------------- | ---------------------- | ----------------------- | ------------------ | --------- | -------------- |
| is_active               | 6                |                    | YES         | boolean                     |                        |                         |                    | bool      | 6              |
| total_spent_value       | 16               |                    | YES         | numeric                     |                        | 10                      |                    | numeric   | 16             |
| social_links            | 11               |                    | YES         | jsonb                       |                        |                         |                    | jsonb     | 11             |
| yearly_budget_value     | 18               |                    | YES         | numeric                     |                        | 10                      |                    | numeric   | 18             |
| balance_value           | 12               |                    | YES         | numeric                     |                        | 10                      |                    | numeric   | 12             |
| created_at              | 5                |                    | YES         | timestamp without time zone |                        |                         | 6                  | timestamp | 5              |
| total_received_value    | 14               |                    | YES         | numeric                     |                        | 10                      |                    | numeric   | 14             |
| twitter_handle          | 10               |                    | YES         | text                        | 1073741824             |                         |                    | text      | 10             |
| balance_currency        | 13               |                    | YES         | text                        | 1073741824             |                         |                    | text      | 13             |
| total_received_currency | 15               |                    | YES         | text                        | 1073741824             |                         |                    | text      | 15             |
| total_spent_currency    | 17               |                    | YES         | text                        | 1073741824             |                         |                    | text      | 17             |
| yearly_budget_currency  | 19               |                    | YES         | text                        | 1073741824             |                         |                    | text      | 19             |
| host_slug               | 20               | 'opensource'::text | YES         | text                        | 1073741824             |                         |                    | text      | 20             |
| id                      | 1                |                    | NO          | text                        | 1073741824             |                         |                    | text      | 1              |
| github_account          | 21               |                    | YES         | text                        | 1073741824             |                         |                    | text      | 21             |
| slug                    | 2                |                    | NO          | text                        | 1073741824             |                         |                    | text      | 2              |
| name                    | 3                |                    | YES         | text                        | 1073741824             |                         |                    | text      | 3              |
| type                    | 4                |                    | YES         | text                        | 1073741824             |                         |                    | text      | 4              |
| description             | 7                |                    | YES         | text                        | 1073741824             |                         |                    | text      | 7              |
| website                 | 8                |                    | YES         | text                        | 1073741824             |                         |                    | text      | 8              |
| github_handle           | 9                |                    | YES         | text                        | 1073741824             |                         |                    | text      | 9              |

`select * from information_schema.columns where table_name='collective_transactions';`

| column_name         | ordinal_position | is_nullable | data_type                   | character_octet_length | numeric_precision_radix | datetime_precision | udt_name  | dtd_identifier |
| ------------------- | ---------------- | ----------- | --------------------------- | ---------------------- | ----------------------- | ------------------ | --------- | -------------- |
| amount_value        | 8                | YES         | numeric                     |                        | 10                      |                    | numeric   | 8              |
| created_at          | 7                | YES         | timestamp without time zone |                        |                         | 6                  | timestamp | 7              |
| expense_tags        | 18               | YES         | jsonb                       |                        |                         |                    | jsonb     | 18             |
| type                | 4                | YES         | text                        | 1073741824             |                         |                    | text      | 4              |
| kind                | 5                | YES         | text                        | 1073741824             |                         |                    | text      | 5              |
| description         | 6                | YES         | text                        | 1073741824             |                         |                    | text      | 6              |
| amount_currency     | 9                | YES         | text                        | 1073741824             |                         |                    | text      | 9              |
| id                  | 1                | NO          | text                        | 1073741824             |                         |                    | text      | 1              |
| from_account_name   | 11               | YES         | text                        | 1073741824             |                         |                    | text      | 11             |
| from_account_type   | 12               | YES         | text                        | 1073741824             |                         |                    | text      | 12             |
| to_account_slug     | 13               | YES         | text                        | 1073741824             |                         |                    | text      | 13             |
| to_account_name     | 14               | YES         | text                        | 1073741824             |                         |                    | text      | 14             |
| to_account_type     | 15               | YES         | text                        | 1073741824             |                         |                    | text      | 15             |
| expense_type        | 16               | YES         | text                        | 1073741824             |                         |                    | text      | 16             |
| expense_description | 17               | YES         | text                        | 1073741824             |                         |                    | text      | 17             |
| from_account_slug   | 10               | YES         | text                        | 1073741824             |                         |                    | text      | 10             |
| project_slug        | 2                | YES         | text                        | 1073741824             |                         |                    | text      | 2              |
| project_name        | 3                | YES         | text                        | 1073741824             |                         |                    | text      | 3              |

`psql -U postgres -d opencollective -f .\count_description.sql`

| description                                                      | count  |
| ---------------------------------------------------------------- | ------ |
| Host Fee                                                         | 821988 |
| Stripe payment processor fee                                     | 275301 |
| PayPal payment processor fee                                     | 128936 |
| Monthly financial contribution to Logseq (Backers)               | 122761 |
| Monthly financial contribution to PHP Foundation (Backers)       | 18547  |
| Monthly financial contribution to webpack (Backer)               | 15571  |
| monthly recurring subscription                                   | 14098  |
| Monthly financial contribution to Destiny Item Manager (Backers) | 12906  |
| Monthly financial contribution to Eleventy (Backer)              | 10638  |
| Monthly financial contribution to JHipster (Backer)              | 10146  |
| Monthly financial contribution to Dark Reader (backer)           | 9881   |
| Monthly financial contribution to socket.io (Sponsors)           | 9811   |
| Other Payment Processor payment processor fee                    | 9684   |
| Monthly financial contribution to AnkiDroid (backer)             | 9253   |
| Monthly financial contribution to Babel (Backers)                | 8453   |
| Monthly financial contribution to Mocha (Backers)                | 8187   |
| Financial contribution to AnkiDroid                              | 7455   |
| Monthly financial contribution to Jest (backer)                  | 7431   |
| Monthly financial contribution to Qubes OS (Backers)             | 7253   |
| Monthly financial contribution to nest (Backers ��)          | 7225   |

`psql -U postgres -d opencollective -f .\count_expense_description.sql`

| expense_description                         | count   |
| ------------------------------------------- | ------- |
| [null]                                      | 2326366 |
| Bounty Payout                               | 818     |
| Virtual Card charge: DIGITALOCEAN.COM       | 303     |
| Virtual Card charge: GITHUB                 | 302     |
| Virtual Card charge: Amazon web services    | 301     |
| Virtual Card charge: HETZNER.COM            | 217     |
| Development                                 | 213     |
| Virtual Card charge: CLOUDFLARE             | 206     |
| BLTF Wellness Provider                      | 199     |
| TAP Contributing Provider                   | 135     |
| Virtual Card charge: GITHUB, INC.           | 127     |
| Development Expense                         | 112     |
| Maintenance                                 | 101     |
| Yii 3 development                           | 89      |
| Virtual Card charge: Discourse              | 86      |
| Quarterly Homebrew Maintenance              | 78      |
| Virtual Card charge: AMZN Mktp US*2X0349O72 | 77      |
| Virtual Card charge: AWS EMEA               | 77      |
| Virtual Card charge: infomaniak.com         | 75      |
| Cloudflare                                  | 72      |

`psql -U postgres -d opencollective -f .\count_expense_tags.sql`

| tag                  | count   |
| -------------------- | ------- |
| []                   | 2372450 |
| engineering          | 2610    |
| web services         | 1212    |
| travel               | 765     |
| infrastructure       | 752     |
| approved             | 489     |
| communications       | 470     |
| hosting              | 404     |
| food & beverage      | 381     |
| hardware             | 380     |
| development          | 355     |
| core developer       | 321     |
| marketing            | 293     |
| bounty               | 222     |
| team                 | 219     |
| supplies & materials | 200     |
| infra                | 200     |
| samu                 | 187     |
| aws                  | 181     |
| maintainer-stipend   | 170     |

`psql -U postgres -d opencollective -f .\count_expense_type.sql`

| expense_type | count   |
| ------------ | ------- |
| [null]       | 2326366 |
| INVOICE      | 31059   |
| RECEIPT      | 22156   |
| CHARGE       | 5995    |
| UNCLASSIFIED | 2336    |
| GRANT        | 1447    |
| SETTLEMENT   | 3       |

`psql -U postgres -d opencollective -f .\count_kind.sql`

| kind                    | count   | total_amount_value(USD) |
| ----------------------- | ------- | ----------------------- |
| CONTRIBUTION            | 1080778 | 42499620.50             |
| HOST_FEE                | 825224  | -5145731.71             |
| PAYMENT_PROCESSOR_FEE   | 413958  | -664918.74              |
| EXPENSE                 | 50458   | -74319625.39            |
| ADDED_FUNDS             | 14522   | 65255380.16             |
| PAYMENT_PROCESSOR_COVER | 3383    | 10571.91                |
| BALANCE_TRANSFER        | 974     | -812051.16              |
| PREPAID_PAYMENT_METHOD  | 45      | 126457.86               |
| TAX                     | 19      | -468.50                 |
| PLATFORM_TIP            | 1       | -50                     |

`psql -U postgres -d opencollective -f .\expense_ranking.sql`

受け取った資金を何に使用しているか（どんな種類のアカウントに送金しているか）

```sql
SELECT to_account_type, COUNT(*) AS count
FROM collective_transactions
WHERE kind = 'EXPENSE' AND amount_currency = 'USD'
GROUP BY to_account_type ORDER BY count DESC;
```

| to_account_type | count |
| --------------- | ----- |
| INDIVIDUAL      | 32753 |
| VENDOR          | 6566  |
| ORGANIZATION    | 2862  |
| COLLECTIVE      | 645   |
| PROJECT         | 537   |
| FUND            | 25    |
| EVENT           | 5     |

受け取った資金を何に使用しているか（どのアカウントに送金しているか）

```sql
SELECT to_account_name, COUNT(*) AS count
FROM collective_transactions
WHERE kind = 'EXPENSE'  AND amount_currency = 'USD'
GROUP BY to_account_name ORDER BY count DESC
LIMIT 20;
```

| to_account_name      | count |
| -------------------- | ----- |
| NumFOCUS             | 360   |
| DIGITALOCEAN.COM     | 303   |
| GITHUB               | 303   |
| Amazon web services  | 301   |
| Velocity Global/Pebl | 295   |
| HETZNER.COM          | 248   |
| CLOUDFLARE           | 205   |
| Rob Eisenberg        | 198   |
| Marcelo Boveto Shima | 164   |
| Richard Littauer     | 159   |
| Hyunsu Cho           | 137   |
| Vladimir Kharlampidi | 134   |
| Quentin Monmert      | 132   |
| Will Pine            | 132   |
| GITHUB, INC.         | 125   |
| Samson               | 124   |
| Aperio Software      | 122   |
| Andrew Nesbitt       | 120   |
| Hﾃ･kan Edling      | 114   |
| Fred Kleuver         | 109   |

`psql -U postgres -d opencollective -f .\expense_amount_ranking.sql`

支出総額ランキング

```sql
SELECT to_account_type, count(*) AS count, SUM(amount_value) AS total_amount_value
FROM collective_transactions
WHERE kind = 'EXPENSE' AND amount_currency = 'USD'
GROUP BY to_account_type ORDER BY total_amount_value DESC;
```

| to_account_type | count | total_amount_value |
| --------------- | ----- | ------------------ |
| PROJECT         | 537   | 285842.24          |
| EVENT           | 5     | 104                |
| FUND            | 25    | -5028.64           |
| COLLECTIVE      | 645   | -917935.96         |
| VENDOR          | 6566  | -4585745.79        |
| ORGANIZATION    | 2862  | -15513436.46       |
| INDIVIDUAL      | 32753 | -37199574.51       |

支出総額ランキング

```sql
SELECT to_account_name, count(*) AS count, SUM(amount_value) AS total_amount_value
FROM collective_transactions
WHERE kind = 'EXPENSE' AND amount_currency = 'USD'
GROUP BY to_account_name ORDER BY total_amount_value
LIMIT 20;
```

| to_account_name         | count | total_amount_value |
| ----------------------- | ----- | ------------------ |
| Velocity Global/Pebl    | 295   | -2738237.60        |
| NumFOCUS                | 360   | -2152324.26        |
| Quansight LLC           | 77    | -1282834.60        |
| Least Authority         | 51    | -1170070.19        |
| OddBird                 | 51    | -1082663.49        |
| Aperio Software         | 122   | -964635.4          |
| Systema Development LLC | 99    | -871639.08         |
| DA DEVELOPPEMENT        | 58    | -720000.01         |
| Open Source Collective  | 65    | -616961.23         |
| Vladimir Kharlampidi    | 134   | -588632.02         |
| Kamil Mysliwiec         | 52    | -567907.01         |
| Oscar Dowson            | 26    | -560450.35         |
| TJ Consulting           | 33    | -551766.61         |
| Aleksander              | 93    | -503709.5          |
| Aspiration              | 4     | -486839.93         |
| Haoqun Jiang            | 57    | -461150.04         |
| Matthias Kurz           | 72    | -459646.90         |
| henry                   | 47    | -413019.21         |
| Logseq                  | 11    | -409400            |
| MeanIT Software Inc     | 44    | -397037.5          |

資金が使用される前と後でコミット数が変わるか比較

1. それぞれのプロジェクトについて、いつ最も多くの資金を使用したのかを調査
2. それぞれのプロジェクトについて、最も多くの資金を使用した日を基準に
   前の30日間のコミット数
   後の30日間のコミット数
   前の180日間のコミット数
   後の180日間のコミット数
   をcsvで記録する
3. 資金を使用することでコミット数が何倍になったのかを計算する

結果

有効なプロジェクト数

```
# 基準より30日前、30日後で1回以上のコミットがあるプロジェクトの数
30 days: 476
# 基準より180日前、180日後で1回以上のコミットがあるプロジェクトの数
180 days: 594
```

それぞれのプロジェクトについて、前後30日でコミット数が何倍になったかを計算

41%のプロジェクトでコミット数が増加

```
[±30 days]
projects: 476
ratio mean (arithmetic): 1.5767109770894032
ratio mean (geometric): 0.8930982407414004
ratio median: 0.8768939393939393
ratio > 1: 0.4117647058823529
ratio < 1: 0.5504201680672269
```

それぞれのプロジェクトについて、前後180日でコミット数が何倍になったかを計算

33%のプロジェクトでコミット数が増加

```
[±180 days]
projects: 594
ratio mean (arithmetic): 1.5325815018794329
ratio mean (geometric): 0.68452081913977
ratio median: 0.7533204610613773
ratio > 1: 0.3282828282828283
ratio < 1: 0.6632996632996633
```
