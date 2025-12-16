set client_encoding to UTF8;

BEGIN;

-- 1) カラム追加（既にあれば何もしない）
ALTER TABLE collectives
ADD COLUMN IF NOT EXISTS github_account TEXT;

-- 2) github_account を埋める（github.com を削除）
UPDATE collectives c
SET github_account = COALESCE(
	NULLIF(c.github_handle, ''),

	-- social_links の type=GITHUB の url
	(
		SELECT replace(e->>'url', 'https://github.com/', '')
		FROM jsonb_array_elements(c.social_links::jsonb) AS e
		WHERE (e->>'type') = 'GITHUB'
		LIMIT 1
	),

	-- website に github.com を含む場合のみ、prefix を削除
	CASE
		WHEN c.website ILIKE '%github.com/%'
			THEN replace(c.website, 'https://github.com/', '')
		ELSE NULL
	END,

	-- description に github.com を含む場合のみ、prefix を削除
	CASE
		WHEN c.description ILIKE '%github.com/%'
			THEN replace(c.description, 'https://github.com/', '')
		ELSE NULL
	END
);

COMMIT;
