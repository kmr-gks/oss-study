#!/bin/bash

curl https://api.opencollective.com/graphql/v2 \
	-H "Content-Type: application/json" \
	-d '{"query":"query{ accounts(limit:1, offset:0, type:[PROJECT]){ totalCount } }"}'
