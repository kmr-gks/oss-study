import os
import api
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

engine = create_engine(
	f"postgresql+psycopg2://postgres:{api.load_sql_password_from_credentials()}@localhost:5432/opencollective"
)

projects = pd.read_sql("SELECT DISTINCT project_slug FROM collective_transactions;", engine)
print(f"検出されたプロジェクト数: {len(projects)}")
