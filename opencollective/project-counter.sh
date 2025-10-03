#!/bin/bash

#api-key.txtから読み込む
MY_TOKEN=$(cat api-key.txt)

#プロジェクトの個数を数える
curl https://api.opencollective.com/graphql/v2 \
	-H "Content-Type: application/json" \
	-H "Personal-Token: $MY_TOKEN" \
	-d '{"query":"query{ accounts(limit:1, offset:0, type:[PROJECT]){ totalCount } }"}'
