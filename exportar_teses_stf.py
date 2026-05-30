import pandas as pd
from db_config import create_db_engine

# Nome do arquivo de saída
ARQUIVO_SAIDA = "teses_stf_completo.csv"

def exportar_teses_stf():
    print("Conectando ao banco de dados...")
    try:
        engine = create_db_engine()
        
        # Consulta SQL atualizada para incluir "Ramo do Direito" e ordenar as colunas
        # As aspas duplas são importantes para nomes de colunas com espaços no PostgreSQL
        query = 'SELECT "Tema", "Ramo do Direito", "Título", "Tese" FROM temas_stf ORDER BY "Tema" ASC'
        
        print("Lendo dados da tabela 'temas_stf'...")
        df = pd.read_sql_query(query, engine)
        
        # Renomeia a coluna 'Tema' para 'Número do Tema' como solicitado
        df = df.rename(columns={'Tema': 'Número do Tema'})
        
        # Garante que o número do tema seja inteiro (remove .0 se houver)
        df['Número do Tema'] = pd.to_numeric(df['Número do Tema'], errors='coerce').fillna(0).astype(int)

        print(f"Encontrados {len(df)} registros.")
        
        # Salva em CSV
        print(f"Salvando arquivo '{ARQUIVO_SAIDA}'...")
        df.to_csv(ARQUIVO_SAIDA, index=False, encoding='utf-8-sig', sep=';')
        
        print("\n✅ Sucesso! Arquivo gerado com sucesso.")
        print(f"Você pode encontrar o arquivo '{ARQUIVO_SAIDA}' na mesma pasta deste script.")

    except Exception as e:
        print(f"\n❌ Ocorreu um erro: {e}")

if __name__ == "__main__":
    exportar_teses_stf()