import os
import pandas as pd
import warnings
from db_config import create_db_engine

# Ignora avisos
warnings.filterwarnings("ignore")

# --- CONFIGURAÇÃO ---
engine = create_db_engine()
PASTA_TEMAS = "Temas STF"  # Certifique-se que a pasta está neste local e contém as 16 planilhas

def reclassificar_tudo():
    print(f"--- 🔄 INICIANDO RECLASSIFICAÇÃO E LIMPEZA ---")
    
    # 1. Carregar o Banco de Dados Atual
    print("Lendo banco de dados...")
    try:
        df_banco = pd.read_sql("SELECT * FROM temas_stf", engine)
        if df_banco.empty:
            print("O banco está vazio. Nada a reclassificar.")
            return
        print(f"Banco carregado com {len(df_banco)} temas.")
    except Exception as e:
        print(f"Erro ao ler banco: {e}")
        return

    # Garante que a coluna Tema é número inteiro
    df_banco['Tema'] = pd.to_numeric(df_banco['Tema'], errors='coerce').fillna(0).astype(int)

    # 2. Ler os arquivos da pasta para criar o Mapa "Gabarito"
    mapa_temas_ramos = {}
    
    if not os.path.exists(PASTA_TEMAS):
        print(f"Erro: Pasta '{PASTA_TEMAS}' não encontrada.")
        return

    arquivos = [f for f in os.listdir(PASTA_TEMAS) if f.endswith('.xls') or f.endswith('.xlsx')]
    
    # Exibe quais ramos serão considerados OFICIAIS
    ramos_oficiais = [os.path.splitext(f)[0] for f in arquivos]
    print(f"Encontrados {len(arquivos)} arquivos. Ramos Oficiais: {ramos_oficiais}")

    for arquivo in arquivos:
        nome_ramo = os.path.splitext(arquivo)[0] 
        caminho_completo = os.path.join(PASTA_TEMAS, arquivo)
        
        try:
            try: df_temp = pd.read_excel(caminho_completo)
            except: df_temp = pd.read_html(caminho_completo, header=0)[0]
            
            col_tema = next((c for c in df_temp.columns if 'tema' in c.lower() and 'situa' not in c.lower()), None)
            
            if col_tema:
                temas_arquivo = pd.to_numeric(df_temp[col_tema], errors='coerce').dropna().astype(int).tolist()
                for t in temas_arquivo:
                    mapa_temas_ramos[t] = nome_ramo
            else:
                print(f"⚠️ Coluna 'Tema' não encontrada em {arquivo}")
                
        except Exception as e:
            print(f"Erro ao ler {arquivo}: {e}")

    print(f"Mapeados {len(mapa_temas_ramos)} temas a partir das planilhas (Gabarito).")

    # --- GERAR LISTA DOS NÃO ENCONTRADOS (Mantive sua funcionalidade) ---
    temas_nas_planilhas = set(mapa_temas_ramos.keys())
    df_nao_encontrados = df_banco[~df_banco['Tema'].isin(temas_nas_planilhas)].copy()
    
    if not df_nao_encontrados.empty:
        nome_arquivo_saida = "Lista_177_Nao_Encontrados.xlsx"
        df_nao_encontrados.to_excel(nome_arquivo_saida, index=False)
        print(f"📁 Arquivo de auditoria criado: '{nome_arquivo_saida}'")
    # ---------------------------------------------------

    # 3. Aplicar a reclassificação (COM LIMPEZA DE SUJEIRA)
    def atualizar_ramo(row):
        tema = row['Tema']
        
        if tema in mapa_temas_ramos:
            # Caso 1: Encontrado nas planilhas -> Usa o nome da planilha (Padronizado)
            return mapa_temas_ramos[tema]
        else:
            # Caso 2: NÃO encontrado -> Força "Não Classificado"
            # ISSO CORRIGE O DROPDOWN: Remove nomes antigos que não existem mais na pasta
            return "Não Classificado"

    df_banco['Ramo do Direito'] = df_banco.apply(atualizar_ramo, axis=1)

    # 4. Salvar de volta no Banco
    print("Salvando atualizações no banco...")
    df_banco.to_sql('temas_stf', engine, if_exists='replace', index=False)
    print("✅ PROCESSO CONCLUÍDO! O filtro do site deve estar limpo agora.")

if __name__ == "__main__":
    reclassificar_tudo()