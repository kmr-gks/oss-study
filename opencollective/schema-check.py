from api import *

query = """
{
  __type(name: "Account") {
    name
    kind
    fields {
      name
      type {
        kind
        name
        ofType {
          kind
          name
        }
      }
    }
  }
}
"""

# 実行
result = run_query(query)

# 生のJSONを整形して表示
show_json(result)
