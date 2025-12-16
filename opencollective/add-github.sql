set client_encoding to UTF8;

BEGIN;

-- 1) カラム追加（既にあれば何もしない）
ALTER TABLE collectives
ADD COLUMN IF NOT EXISTS github_account TEXT;

-- 2) github_account を埋める（チェックなし、正規化なし）
UPDATE collectives c
SET github_account = COALESCE(
	NULLIF(c.github_handle, ''),
	-- social_links の type=GITHUB の url を入れる（そのまま）
	(
		SELECT e->>'url'
		FROM jsonb_array_elements(c.social_links::jsonb) AS e
		WHERE (e->>'type') = 'GITHUB'
		LIMIT 1
	),
	NULLIF(c.website, ''),
	NULLIF(c.description, '')
);

COMMIT;
