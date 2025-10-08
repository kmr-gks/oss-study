#!/bin/bash

#api-key.txtから読み込む
MY_TOKEN=$(cat api-key.txt)

#自分のアカウント
curl https://api.opencollective.com/graphql/v2 \
	-H "Content-Type: application/json" \
	-H "Personal-Token: $MY_TOKEN" \
	-d '{"query":"query{ loggedInAccount{ id name slug type } }"}'
