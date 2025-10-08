from api import *

query = """
query {
	accounts(limit: 1, offset: 0, type: [PROJECT]) {
		totalCount
	}
}
"""

# 実行
result = run_query(query)

# 生のJSONを整形して表示
show_json(result)
