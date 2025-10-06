import pandas as pd
from sqlalchemy import create_engine

db_url = "postgresql://postgres:Badinho201.@db.rxmctzxlemptfaydemkw.supabase.co:5432/postgres"
engine = create_engine(db_url)

df_stj = pd.read_csv("relatorio.csv", sep=';', encoding='latin1')
df_stj.to_sql('temas_stj', engine, if_exists='replace', index=False)

print("Dados do STJ importados com sucesso!")