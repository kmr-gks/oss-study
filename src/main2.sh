#!/bin/bash

# ossをクローンする
# truck-factorを使用してコア開発者情報を抽出する

#ossのリストをファイルから読み込む
oss_list=()
while IFS= read -r line; do
	oss_list+=("$line")
done < ../output/oss-fuzz-projects.txt

#ファイルがある場所をカレントディレクトリに設定
cd "$(dirname "$0")"

# 出力先を指定
exec > ../output/truck-factor-results.txt

cd ../truck-factor/gittruckfactor
mvn package

# 各OSSをクローンしてtruck-factorを実行
for oss in "${oss_list[@]}"; do
	dir_name=$(basename "$oss" .git)
	repo_full_name=$(echo "$oss" | sed -E 's/.*\.com\/(.*)/\1/')
	echo "dir_name: $dir_name, repo_full_name: $repo_full_name"

	if [ ! -d "$dir_name" ]; then
		git clone "$oss"
	fi

	( cd scripts && ./commit_log_script.sh ../"$dir_name" )
	java -jar target/gittruckfactor-1.0.jar "$dir_name" "$repo_full_name"
done
