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

                           description                            | count  
------------------------------------------------------------------ | --------
 Host Fee                                                         | 821988
 Stripe payment processor fee                                     | 275301
 PayPal payment processor fee                                     | 128936
 Monthly financial contribution to Logseq (Backers)               | 122761
 Monthly financial contribution to PHP Foundation (Backers)       |  18547
 Monthly financial contribution to webpack (Backer)               |  15571
 monthly recurring subscription                                   |  14098
 Monthly financial contribution to Destiny Item Manager (Backers) |  12906
 Monthly financial contribution to Eleventy (Backer)              |  10638
 Monthly financial contribution to JHipster (Backer)              |  10146
 Monthly financial contribution to Dark Reader (backer)           |   9881
 Monthly financial contribution to socket.io (Sponsors)           |   9811
 Other Payment Processor payment processor fee                    |   9684
 Monthly financial contribution to AnkiDroid (backer)             |   9253
 Monthly financial contribution to Babel (Backers)                |   8453
 Monthly financial contribution to Mocha (Backers)                |   8187
 Financial contribution to AnkiDroid                              |   7455
 Monthly financial contribution to Jest (backer)                  |   7431
 Monthly financial contribution to Qubes OS (Backers)             |   7253
 Monthly financial contribution to nest (Backers ��)              |   7225

`psql -U postgres -d opencollective -f .\count_expense_description.sql`

             expense_description             |  count  
--------------------------------------------- | ---------
 [null]                                      | 2326366
 Bounty Payout                               |     818
 Virtual Card charge: DIGITALOCEAN.COM       |     303
 Virtual Card charge: GITHUB                 |     302
 Virtual Card charge: Amazon web services    |     301
 Virtual Card charge: HETZNER.COM            |     217
 Development                                 |     213
 Virtual Card charge: CLOUDFLARE             |     206
 BLTF Wellness Provider                      |     199
 TAP Contributing Provider                   |     135
 Virtual Card charge: GITHUB, INC.           |     127
 Development Expense                         |     112
 Maintenance                                 |     101
 Yii 3 development                           |      89
 Virtual Card charge: Discourse              |      86
 Quarterly Homebrew Maintenance              |      78
 Virtual Card charge: AMZN Mktp US*2X0349O72 |      77
 Virtual Card charge: AWS EMEA               |      77
 Virtual Card charge: infomaniak.com         |      75
 Cloudflare                                  |      72

`psql -U postgres -d opencollective -f .\count_expense_tags.sql`

         tag          |  count  
---------------------- | ---------
 []                   | 2372450
 engineering          |    2610
 web services         |    1212
 travel               |     765
 infrastructure       |     752
 approved             |     489
 communications       |     470
 hosting              |     404
 food & beverage      |     381
 hardware             |     380
 development          |     355
 core developer       |     321
 marketing            |     293
 bounty               |     222
 team                 |     219
 supplies & materials |     200
 infra                |     200
 samu                 |     187
 aws                  |     181
 maintainer-stipend   |     170

`psql -U postgres -d opencollective -f .\count_expense_type.sql`

 expense_type |  count  
-------------- | ---------
 [null]       | 2326366
 INVOICE      |   31059
 RECEIPT      |   22156
 CHARGE       |    5995
 UNCLASSIFIED |    2336
 GRANT        |    1447
 SETTLEMENT   |       3

`psql -U postgres -d opencollective -f .\count_kind.sql`


          kind           |  count  | total_amount_value 
-------------------------|---------|--------------------
 CONTRIBUTION            | 1080778 |        42499620.50
 HOST_FEE                |  825224 |        -5145731.71
 PAYMENT_PROCESSOR_FEE   |  413958 |         -664918.74
 EXPENSE                 |   50458 |       -74319625.39
 ADDED_FUNDS             |   14522 |        65255380.16
 PAYMENT_PROCESSOR_COVER |    3383 |           10571.91
 BALANCE_TRANSFER        |     974 |         -812051.16
 PREPAID_PAYMENT_METHOD  |      45 |          126457.86
 TAX                     |      19 |            -468.50
 PLATFORM_TIP            |       1 |                -50
