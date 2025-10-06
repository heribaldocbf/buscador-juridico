import pandas as pd
from sqlalchemy import create_engine

db_url = "postgresql://postgres:Badinho201.@db.rxmctzxlemptfaydemkw.supabase.co:5432/postgres"
engine = create_engine(db_url)

df_stj = pd.read_csv("RepercussaoGeral.csv", sep=';', encoding='latin1')
df_stj.to_sql('temas_stf', engine, if_exists='replace', index=False)

print("Dados do STF importados com sucesso!")