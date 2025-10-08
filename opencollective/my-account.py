from api import *

query = """
query{
	loggedInAccount{
		id
		name
		slug
		type
	}
}
"""

# 実行
result = run_query(query)

# 生のJSONを整形して表示
show_json(result)
