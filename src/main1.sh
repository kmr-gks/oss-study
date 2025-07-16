#!/bin/bash

# OSS-fuzzからオープンソースプロジェクトを抽出する

#ファイルがある場所をカレントディレクトリに設定
cd "$(dirname "$0")"

# 出力先を指定
mkdir -p ../output
exec > ../output/oss-fuzz-projects.txt

cd ../oss-fuzz/projects

# 各サブディレクトリをループして project.yaml から main_repo を抽出
for dir in */; do
	yaml="$dir/project.yaml"
	#yamlファイル内にmain_repo: が存在する場合、そのURLを表示する
	if [ -f "$yaml" ]; then
	url=$(grep '^main_repo:' "$yaml" | awk '{print $2}')
	#'や"で囲まれている場合はそれを除去
	url=$(echo "$url" | sed -e 's/^["'\'']//;s/["'\'']$//')
	#拡張子が .git の場合は除去
	url=$(echo "$url" | sed 's/\.git$//')
	#urlが"https://github.com/"で始まる場合のみ表示
	if [[ "$url" == https://github.com/* ]]; then
		echo "$url"
	fi
done
