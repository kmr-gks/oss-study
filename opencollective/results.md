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

支出のデータを対象にして、タグの値を調査した。
一部のデータでweb setvicesやtravelなど具体的な説明がなされている。

`psql -U postgres -d opencollective -f .\count_expense_tags.sql`

| expense_tags                                   | count |
| ---------------------------------------------- | ----- |
| (null)                                         | 36433 |
| engineering                                    | 2338  |
| web services                                   | 1097  |
| travel                                         | 585   |
| infrastructure                                 | 571   |
| communications                                 | 434   |
| food & beverage                                | 364   |
| hardware                                       | 262   |
| hosting                                        | 240   |
| core developer                                 | 222   |
| marketing                                      | 198   |
| development                                    | 195   |
| supplies & materials                           | 185   |
| other                                          | 147   |
| bounty                                         | 136   |
| holiday gift drive, m, aor, mmip family, aor-m | 131   |
| software                                       | 129   |
| office                                         | 125   |
| team                                           | 123   |
| aws                                            | 105   |

金額ベースで調査
expense_tagsで指定されているそれぞれのタグについて、支出の総額(USD)を集計した。

`psql -U postgres -d opencollective -f .\count_expense_value.sql`

| expense_tags         | count | total_usd   |
| -------------------- | ----- | ----------- |
| (null)               | 30743 | 45292184.98 |
| engineering          | 2317  | 4964367.65  |
| core developer       | 222   | 1038784.75  |
| maintenance          | 85    | 459741.33   |
| communications       | 434   | 282103.83   |
| travel               | 577   | 244007.66   |
| employment           | 23    | 223536.73   |
| other                | 147   | 197021.29   |
| coordination         | 48    | 164472.07   |
| core-coordinated     | 35    | 155765.58   |
| nsf-oac1835443       | 5     | 152026      |
| infrastructure       | 571   | 146135.18   |
| development          | 186   | 141636.77   |
| subcontract          | 11    | 136415.50   |
| project_manager      | 17    | 134922.5    |
| salary               | 34    | 104359.20   |
| engine               | 32    | 96157.9     |
| supplies & materials | 185   | 92701.35    |
| marketing            | 198   | 82276.18    |
| maintainer-stipend   | 85    | 82189.94    |

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

1. それぞれのプロジェクトについて、いつ最も多くの資金を個人に使用したのかを調査
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
# 個人に資金を1回以上使用し、基準より30日前、30日後で1回以上のコミットがあるプロジェクトの数
30 days: 461
# 個人に資金を1回以上使用し、基準より180日前、180日後で1回以上のコミットがあるプロジェクトの数
180 days: 577
```

それぞれのプロジェクトについて、前後30日でコミット数が何倍になったかを計算

41%のプロジェクトでコミット数が増加

```
[±30 days]
projects: 461
ratio mean (arith): 1.5302098932116444
ratio mean (geom): 0.8771979056883573
ratio median: 0.8794326241134751
ratio > 1: 0.41865509761388287
ratio < 1: 0.544468546637744
```

それぞれのプロジェクトについて、前後180日でコミット数が何倍になったかを計算

33%のプロジェクトでコミット数が増加

```
[±180 days]
projects: 577
ratio mean (arith): 1.5319230088456992
ratio mean (geom): 0.6757836889443227
ratio median: 0.75
ratio > 1: 0.32062391681109187
ratio < 1: 0.6724436741767764
```

受け取った資金の使い道分析
collective_transactionsのレコードのうち、kind = 'EXPENSE'のものを対象にし、ルールベースで分類した。
`psql -U postgres -d opencollective -f .\count_expense_breakdown.sql >results.txt`

| FROM collective_transactions | Purpose          | Transaction Count | Amount (USD) |
| ---------------------------- | ---------------- | ----------------- | ------------ |
| INDIVIDUAL                   | INDIVIDUAL_OTHER | 14265             | -5496780.13  |
| INDIVIDUAL                   | COMPENSATION     | 18488             | -31702794.38 |
| ORGANIZATION                 | MARKETING        | 18                | -8195.49     |
| ORGANIZATION                 | INFRA            | 119               | -269162.02   |
| ORGANIZATION                 | GOVERNANCE       | 31                | -277295.79   |
| ORGANIZATION                 | ORG_OTHER        | 3876              | -15590876.88 |
| OTHER                        | UNKNOWN          | 30                | -4924.64     |
| VENDOR                       | ECOMMERCE        | 159               | -44086.03    |
| VENDOR                       | CLOUD_OR_SAAS    | 1959              | -181326.89   |
| VENDOR                       | VENDOR_OTHER     | 4448              | -4360332.87  |



#### 教師あり学習を用いて支出を分類
支出を分類するため、以下の大カテゴリを定義する。
* development
* infra
* communication
* governance
* travel
* supplies
* marketing
* food
* other
expense_tagsが設定されているデータを対象にして教師データを作成した。
支出の全データ: 43393件
expense_tagsが設定されているデータ: 2338件
支出内容を推定しやすいexpense_tagsが設定されているデータ: 7003件
上記の7003件のデータを教師データとして、機械学習モデルを用いて支出の内容を推定した。
以下のカラムを特徴量として使用した。
* from_account_type
* to_account_name
* to_account_type
* expense_type
* description
* expense_description



#### LLMを用いた支出の分類

LLM(gpt-5.4-mini-2026-03-17)を用いて、支出の内容を推定した。
プロンプトとコード:
```py
MODEL = "gpt-5.4-mini-2026-03-17"

# ===== プロンプト =====
def build_prompt(description):
    return f"""
You are a classifier for OSS project expenses.

Select the SINGLE most appropriate category from the list below.

Categories:
- development: Compensation paid to official project members for software development and maintenance.
- bounty: Payments to external contributors for specific tasks (bug fixes, features).
- marketing-promotion: Advertising, sponsorships, outreach.
- travel: Transportation, accommodation, conference costs.
- non-tech-service: Documentation, writing, translation.
- infra-subscription: Cloud, hosting, SaaS.
- equipment: Hardware such as laptops or servers.
- food-supplies: Meals, consumables, general supplies.
- legal-admin: Legal, tax, administrative costs.
- miscellaneous: Known purpose but does not fit above.
- unknown: Purpose cannot be determined.

Rules:
- Choose exactly ONE category
- If no clear purpose → choose unknown

Output format:
{{"label": "..."}}

description: "{description}"
→
"""

# ===== API呼び出し =====
def classify(description):
    prompt = build_prompt(description)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    return response.choices[0].message.content
```

上記の{description}の部分にcollective_transactionsのexpense_descriptionカラムの値を入れて、LLMに支出の内容を推定させた。
ランダムに選んだ381件のデータについて、LLMが推定したラベルと我々が手動で付与した正解ラベルを比較して、LLMの推定精度を評価した。

結果
```
=== Evaluation ===
Accuracy: 0.7165354330708661
Macro F1: 0.6545982404169286

=== Classification Report ===
                     precision    recall  f1-score   support

             bounty       0.81      0.81      0.81        16
        development       0.91      0.85      0.88        96
          equipment       0.73      1.00      0.84         8
      food-supplies       0.82      0.82      0.82        28
 infra-subscription       0.90      0.91      0.91        80
        legal-admin       0.40      0.67      0.50         3
marketing-promotion       0.59      0.61      0.60        38
      miscellaneous       0.26      0.36      0.30        22
   non-tech-service       0.22      0.21      0.21        29
             travel       0.77      0.89      0.83        19
            unknown       0.58      0.43      0.49        42

           accuracy                           0.72       381
          macro avg       0.64      0.69      0.65       381
       weighted avg       0.72      0.72      0.72       381
```


#### LLMにweb検索を許可し、分類させた結果

プロンプトとコード
```python
MODEL = "gpt-4o-search-preview-2025-03-11"
# ===== プロンプト =====
def build_prompt(description):
    return f"""
You are a classifier for OSS project expenses.

Select the SINGLE most appropriate category from the list below.

Categories:
- development: Compensation paid to official project members for direct software development and maintenance.
- bounty: Rewards or fees paid to external contributors (non-members) for specific tasks, bug fixes, feature implementations, or general contributions.
- infra-subscription: Recurring costs for cloud hosting, internet connectivity, and other software-as-a-service (SaaS) subscriptions.
- equipment: Purchase of physical hardware and assets directly used for development activities, such as laptops and servers.
- food-supplies: Purchase of consumables, meals, and general physical items that are not directly related to development.
- marketing-events: Costs for organizing or participating in events to promote the project and recruit new developers (includes marketing, social media promotion, transportation, conference registration fees).
- non-tech-activities: Essential project-related tasks that are not directly linked to coding, such as documentation, translation, technical writing, legal or tax compliance, accounting, and general administrative work.
IMPORTANT:
If the expense is related to creating or improving project documentation, treat it as "non-tech-activities", even if it involves participation in a program or event.
For example, participation in programs such as Google Season of Docs (GSoD) should be classified as "non-tech-activities" when the purpose is documentation work for the project.

- unknown: Expenditures where the purpose cannot be determined at all due to missing or insufficient information.

Rules:
- Choose exactly ONE category
- If you're unsure, feel free to use a web search. If you still can't find the answer after searching, choose unknown.

Output format:
{{"label": "..."}}

description: "{description}"
→
"""

# ===== API呼び出し =====
def classify(description):
    prompt = build_prompt(description)

    response = client.chat.completions.create(
        model=MODEL,
                    web_search_options={
                "user_location": {
                    "type": "approximate",
                    "approximate": {
                        "country": "JP",
                        "city": "Tokyo",
                        "region": "Tokyo",
                    },
                },
            },
        messages=[{"role": "user", "content": prompt}],
        #temperature=0
    )

    return response.choices[0].message.content
```
結果
```
=== Evaluation ===
Accuracy: 0.6272965879265092
Macro F1: 0.6500617807345042

=== Classification Report ===
                     precision    recall  f1-score   support

             bounty       0.65      0.69      0.67        16
        development       0.95      0.65      0.77        96
          equipment       0.58      0.88      0.70         8
      food-supplies       0.91      0.75      0.82        28
 infra-subscription       0.85      0.66      0.75        80
   marketing-events       0.82      0.56      0.67        57
non-tech-activities       0.54      0.35      0.43        54
            unknown       0.27      0.81      0.40        42

           accuracy                           0.63       381
          macro avg       0.70      0.67      0.65       381
       weighted avg       0.76      0.63      0.66       381
```
ラベル分類の性能が良くなかった上、1回動かしただけでクレジットを$10消費した。

