from api import *

query = """
query ($limit: Int!, $offset: Int!) {
  accounts(type:[PROJECT], limit:$limit, offset:$offset) {
    nodes {
      id
      slug
      name
      type
      createdAt
      isActive
        stats {
        balance { value currency }
        totalAmountReceived { value currency }
        totalAmountSpent { value currency }
        yearlyBudget { value currency }
      }
    }
  }
}
"""

# 実行
result = run_query(query,{"limit": 1, "offset": 0})

# 生のJSONを整形して表示
show_json(result)
