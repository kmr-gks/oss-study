set client_encoding to UTF8;

WITH base AS (
  SELECT
    id,
    project_slug,
    created_at,
    amount_value,
    amount_currency,
    from_account_type,
    to_account_type,
    to_account_name,
    description,
    expense_description,
    expense_type,
    expense_tags
  FROM collective_transactions
  WHERE kind = 'EXPENSE'
),
classified AS (
  SELECT
    *,
    -- Level 1: payee category
    CASE
      WHEN to_account_type = 'VENDOR' THEN 'VENDOR'
      WHEN to_account_type = 'INDIVIDUAL' THEN 'INDIVIDUAL'
      WHEN to_account_type IN ('ORGANIZATION','COLLECTIVE','PROJECT') THEN 'ORGANIZATION'
      WHEN to_account_type IS NULL THEN 'UNKNOWN'
      ELSE 'OTHER'
    END AS l1_payee,

    -- Level 2: subcategory depends on l1
    CASE
      -- VENDOR: cloud vs e-commerce vs other
      WHEN to_account_type = 'VENDOR' AND (
        coalesce(to_account_name,'') ILIKE '%AWS%' OR
        coalesce(to_account_name,'') ILIKE '%AMAZON WEB SERVICES%' OR
        coalesce(to_account_name,'') ILIKE '%GITHUB%' OR
        coalesce(to_account_name,'') ILIKE '%DIGITALOCEAN%' OR
        coalesce(to_account_name,'') ILIKE '%CLOUDFLARE%' OR
        coalesce(to_account_name,'') ILIKE '%HETZNER%' OR
        coalesce(to_account_name,'') ILIKE '%GOOGLE CLOUD%' OR
        coalesce(to_account_name,'') ILIKE '%AZURE%' OR
        coalesce(expense_description,'') ILIKE '%Virtual Card charge:%'
      ) THEN 'CLOUD_OR_SAAS'

      WHEN to_account_type = 'VENDOR' AND (
        coalesce(to_account_name,'') ILIKE '%AMAZON%' OR
        coalesce(to_account_name,'') ILIKE '%WAL%MART%' OR
        coalesce(to_account_name,'') ILIKE '%EBAY%' OR
        coalesce(to_account_name,'') ILIKE '%ALIEXPRESS%'
      ) THEN 'ECOMMERCE'

      WHEN to_account_type = 'VENDOR' THEN 'VENDOR_OTHER'

      -- INDIVIDUAL: compensation vs other
      WHEN to_account_type = 'INDIVIDUAL' AND (
        coalesce(expense_description,'') ILIKE '%development%' OR
        coalesce(expense_description,'') ILIKE '%maintenance%' OR
        coalesce(expense_description,'') ILIKE '%bounty%' OR
        coalesce(description,'') ILIKE '%bounty%' OR
        expense_type = 'INVOICE'
      ) THEN 'COMPENSATION'

      WHEN to_account_type = 'INDIVIDUAL' THEN 'INDIVIDUAL_OTHER'

      -- ORGANIZATION: categorize by text cues
      WHEN to_account_type IN ('ORGANIZATION','COLLECTIVE','PROJECT') AND (
        coalesce(expense_description,'') ILIKE '%hosting%' OR
        coalesce(expense_description,'') ILIKE '%infrastructure%' OR
        coalesce(expense_description,'') ILIKE '%cloud%'
      ) THEN 'INFRA'

      WHEN to_account_type IN ('ORGANIZATION','COLLECTIVE','PROJECT') AND (
        coalesce(expense_description,'') ILIKE '%marketing%' OR
        coalesce(expense_description,'') ILIKE '%advertis%' OR
        coalesce(expense_description,'') ILIKE '%promotion%'
      ) THEN 'MARKETING'

      WHEN to_account_type IN ('ORGANIZATION','COLLECTIVE','PROJECT') AND (
        coalesce(expense_description,'') ILIKE '%legal%' OR
        coalesce(expense_description,'') ILIKE '%account%' OR
        coalesce(expense_description,'') ILIKE '%administration%' OR
        coalesce(expense_description,'') ILIKE '%committee%'
      ) THEN 'GOVERNANCE'

      WHEN to_account_type IN ('ORGANIZATION','COLLECTIVE','PROJECT') THEN 'ORG_OTHER'

      ELSE 'UNKNOWN'
    END AS l2_use
  FROM base
)
SELECT
  l1_payee,
  l2_use,
  COUNT(*) AS n_records,
  SUM(amount_value) AS sum_amount
FROM classified
where amount_currency='USD'
GROUP BY l1_payee, l2_use
ORDER BY l1_payee, sum_amount DESC;
