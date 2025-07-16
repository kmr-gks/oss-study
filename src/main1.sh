#!/bin/bash

# OSS-fuzzからオープンソースプロジェクトを抽出する

#ファイルがある場所をカレントディレクトリに設定
cd "$(dirname "$0")"

cd ../oss-fuzz/projects

# 各サブディレクトリをループして project.yaml から main_repo を抽出
for dir in */; do
	yaml="$dir/project.yaml"
	#yamlファイル内にmain_repo: が存在する場合、そのURLを表示する
	if [ -f "$yaml" ]; then
	url=$(grep '^main_repo:' "$yaml" | awk '{print $2}')
	echo $url
	fi
done
