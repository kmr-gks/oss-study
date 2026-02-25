`psql -U postgres -d opencollective`

`\dt`

    テーブル一覧

| スキーマ | 名前                    | タイプ   | 所有者   | 説明                                                                            |
| -------- | ----------------------- | -------- | -------- | ------------------------------------------------------------------------------- |
| public   | collective_transactions | テーブル | postgres | transactionsというクエリを使用してマイニングしたデータのテーブル。238万件ある。 |
| public   | collectives             | テーブル | postgres | collectiveのテーブル。3476件ある。                                              |
| public   | commit_history          | テーブル | postgres | collectiveに対応したリポジトリのコミット履歴。767万件ある。                     |

テーブルのcolumn一覧

`select * from information_schema.columns where table_name='collective_transactions';`

Columns of collective_transactions

| column_name         | 意味                                                                         | data_type                   |
| ------------------- | ---------------------------------------------------------------------------- | --------------------------- |
| amount_value        | 送金金額                                                                     | numeric                     |
| amount_currency     | 通貨                                                                         | text                        |
| created_at          | 送金時間                                                                     | timestamp without time zone |
| expense_tags        | 支出の種類(OpenCollectiveによって定義された値ではなく、自然言語で表現される) | jsonb                       |
| type                | debit or credit(収入か支出を区別する)                                        | text                        |
| kind                | 送金の種類(資金の受け取りか、資金の使用か、手数料の支払いかを区別する)       | text                        |
| description         | 説明文(自然言語)                                                             | text                        |
| id                  | id                                                                           | text                        |
| from_account_name   | 送金元の名前                                                                 | text                        |
| from_account_type   | 送金元のタイプ                                                               | text                        |
| to_account_slug     | 送金先のスラグ(一意に区別する文字列)                                         | text                        |
| to_account_name     | 送金先の名前                                                                 | text                        |
| to_account_type     | 送金先のタイプ                                                               | text                        |
| expense_type        | 送金の種類(どういう形で支払いが発生したか)                                   | text                        |
| expense_description | 説明文(自然言語)                                                             | text                        |
| from_account_slug   | 送金元のスラグ(一意に区別する文字列)                                         | text                        |
| project_slug        | プロジェクトのスラグ(一意に区別する文字列)                                   | text                        |
| project_name        | プロジェクト名                                                               | text                        |

`select * from information_schema.columns where table_name='collectives';`

Columns of collectives

| column_name             | 意味                                                                                                   | data_type                   |
| ----------------------- | ------------------------------------------------------------------------------------------------------ | --------------------------- |
| is_active               | アクティブかどうか(3476個のコレクティブの中で、アクティブでないものは1個だった)                        | boolean                     |
| total_spent_value       | 今までの支出の累計金額                                                                                 | numeric                     |
| total_spent_currency    | 通貨                                                                                                   |                             |
| social_links            | ソーシャルメディア(Webサイト, github, twitterなど)のリンク                                             | jsonb                       |
| yearly_budget_value     | 1年間に受け取る資金の予想金額 (https://docs.opencollective.com/help/collectives/budget?q=yearlyBudget) | numeric                     |
| yearly_budget_currency  | 通貨                                                                                                   |                             |
| balance_value           | 残高                                                                                                   | numeric                     |
| balance_currency        | 通貨                                                                                                   |                             |
| created_at              | 登録日                                                                                                 | timestamp without time zone |
| total_received_value    | 今まで受け取った金額                                                                                   | numeric                     |
| total_received_currency | 通貨                                                                                                   |                             |
| twitter_handle          | twitterの登録名                                                                                        | text                        |
| host_slug               | fiscal hostのこと。今回はhost_slugがopensourceのものを対象にしている。                                 | text                        |
| id                      | collectiveのid                                                                                         | text                        |
| github_account          | githubアカウント                                                                                       | text                        |
| slug                    | collectiveのslug                                                                                       | text                        |
| name                    | collectiveの名前                                                                                       | text                        |
| type                    | collective, projectなどの種類                                                                          | text                        |
| description             | 説明文                                                                                                 | text                        |
| website                 | ウェブサイトのURL                                                                                      | text                        |
| github_handle           | githubのアカウント                                                                                     | text                        |

`select * from information_schema.columns where table_name='commit_history';`

Columns of commit_history

| column_name     | 意味                                     | data_type                   |
| --------------- | ---------------------------------------- | --------------------------- |
| author_name     | コミットの編集を行った人                 | text                        |
| author_email    | メールアドレス                           | text                        |
| author_time     | 最初にコミットが行われた日時             | timestamp without time zone |
| committer_name  | コミットの編集をした人                   | text                        |
| committer_email | メールアドレス                           | text                        |
| commit_time     | コミットの編集(rebaseなど)が行われた日時 | timestamp without time zone |
| mined_at        | マイニングを行った日時                   | timestamp without time zone |
| repo_path       | リポジトリのパス                         | text                        |
| subject         | コミットメッセージ                       | text                        |
| body            | コミットの説明文                         | text                        |
| repo_name       | リポジトリ名                             | text                        |
| commit_hash     | コミットハッシュ                         | text                        |
| parent_hashes   | 親コミットのハッシュ                     | text                        |

収入、支出を含めたすべての取引を対象としたdescriptionのランキング

抽象的な説明が多く、これだけでは資金提供、資金使用の理由は読み取れない。

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

収入、支出を含めたすべての取引を対象としたexpense_descriptionのランキング

全体の9割以上がnullだが、一部のデータでは支払先（使い道）がわかる場合がある：github, AWS, cloudflareなど

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

expense_tagsで指定されているタグを集計

全体の9割以上がnullだが、一部のデータでweb setvicesやtravelなど具体的な説明がなされている。

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

expense_typeで指定されているタグを集計

全体の9割以上がnullであり、一部のデータでINVOICEやRECEIPTが指定されているが、資金の具体的な使い道はわからなかった。

それぞれのtypeの説明: [https://graphql-docs-v2.opencollective.com/types/ExpenseType](https://graphql-docs-v2.opencollective.com/types/ExpenseType)

`psql -U postgres -d opencollective -f .\count_expense_type.sql`

| expense_type | description                                                                                                                   | count   |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------- | ------- |
| [null]       |                                                                                                                               | 2326366 |
| INVOICE      | Charge for your time or get paid in advance. 開発者に(前もって)支払われるお金、人件費                                         | 31059   |
| RECEIPT      | Get paid back for a purchase already made.後から払う費用、人件費以外と思われる                                                | 22156   |
| CHARGE       | Payment done using an issued (virtual) credit card issued by your Fiscal Host. 会計ホストが発行したカードで支払い、インフラ代 | 5995    |
| UNCLASSIFIED | Unclassified expense                                                                                                          | 2336    |
| GRANT        | Request funding for a project or initiative. 他の開発者、グループに払ったお金                                                 | 1447    |
| SETTLEMENT   | expense generated by Open Collective to collect money owed by Fiscal Hosts.                                                   | 3       |

kindで指定されるタグを集計

kindの説明: [https://docs.opencollective.com/help/product/ledger/individual-transactions](https://docs.opencollective.com/help/product/ledger/individual-transactions)

 `psql -U postgres -d opencollective -f .\count_kind.sql`

| kind                    | description                                                                                                                                                                                                      | count   | total_amount_value(USD) |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ----------------------- |
| CONTRIBUTION            | Records a contribution made through the platform. 資金流入                                                                                                                                                       | 1080778 | 42499620.50             |
| HOST_FEE                | Records a host fee allocated to the host in relation either a CONTRIBUTION or ADDED_FUNDS (会計ホストへの)手数料                                                                                                 | 825224  | -5145731.71             |
| PAYMENT_PROCESSOR_FEE   | Records a fee charged by a payment processor.手数料(stripe, paypalへの)                                                                                                                                          | 413958  | -664918.74              |
| EXPENSE                 | Records an expense made through the platform.支出                                                                                                                                                                | 50458   | -74319625.39            |
| ADDED_FUNDS             | Funds that have been added to a collective account by a fiscal host.資金流入(会計ホストから)                                                                                                                     | 14522   | 65255380.16             |
| PAYMENT_PROCESSOR_COVER | Records payment processor fees that are covered by a fiscal host when a transaction is refunded (the payment processor do not refund the fees related to the original transaction). 取引キャンセル時の手数料返還 | 3383    | 10571.91                |
| BALANCE_TRANSFER        | Usually done when emptying balance (Collective to Host, Project or Event to Collective). Or in some cases, moving balance between Fiscal Hosts. プロジェクト、コレクティブ間の資金移動                           | 974     | -812051.16              |
| PREPAID_PAYMENT_METHOD  | [LEGACY] records a transaction used for implementing gift cards.                                                                                                                                                 | 45      | 126457.86               |
| TAX                     |                                                                                                                                                                                                                  | 19      | -468.50                 |
| PLATFORM_TIP            | Records a platform tip added by a contributor to their contribution.                                                                                                                                             | 1       | -50                     |

`psql -U postgres -d opencollective -f .\expense_ranking.sql`

受け取った資金を何に使用しているか（どんな種類のアカウントに送金しているか）

account_typeの説明: [https://docs.opencollective.com/help/about/terminology](https://docs.opencollective.com/help/about/terminology)

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

account_typeの説明: [https://docs.opencollective.com/help/about/terminology](https://docs.opencollective.com/help/about/terminology)

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
   * 前の30日間のコミット数
   * 後の30日間のコミット数
   * 前の180日間のコミット数
   * 後の180日間のコミット数
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
