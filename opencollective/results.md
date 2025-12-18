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
