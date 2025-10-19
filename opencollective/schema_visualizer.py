import json
import networkx as nx
from pyvis.network import Network

with open("graphql_schema_fields.json", encoding="utf-8") as f:
    data = json.load(f)

keywords = ["Amount", "Transaction", "Expense", "Payment", "Payout", "Currency", "Balance", "Stats"]

G = nx.DiGraph()
for r in data:
    parent = r["parent_type"]
    child = r["field_type"]
    if not parent or not child:
        continue
    if any(k.lower() in parent.lower() or k.lower() in child.lower() for k in keywords):
        G.add_edge(parent, child)

print(f"Filtered: {len(G.nodes())} nodes, {len(G.edges())} edges")

net = Network(height="900px", width="100%", directed=True)
net.from_nx(G)
net.show("budget_network.html", notebook=False)

import pandas as pd

df = pd.read_json("graphql_schema_fields.json")
df_budget = df[
    df["field_type"].str.contains("Amount|Transaction|Expense|Payment|Payout|Currency|Balance|Stats", case=False, na=False)
]
df_budget.to_csv("budget_relations.csv", index=False)
