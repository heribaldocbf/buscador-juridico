import pandas as pd
from db_config import create_db_engine

engine = create_db_engine()

df_stj = pd.read_csv("relatorio.csv", sep=';', encoding='latin1')
df_stj.to_sql('temas_stj', engine, if_exists='replace', index=False)

print("Dados do STJ importados com sucesso!")