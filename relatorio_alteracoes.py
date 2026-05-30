import pandas as pd
import os
import warnings
from sentence_transformers import SentenceTransformer, util
import torch
import numpy as np
import unicodedata
import re
from db_config import create_db_engine

warnings.filterwarnings("ignore")

# --- 1. CONFIGURAÇÃO ---
engine = create_db_engine()

ARQUIVO_STJ = "relatorio.csv"
ARQUIVO_STF = "RepercussaoGeral.xls"

# --- 2. PRECISÃO (REGRAS E FUNÇÕES) ---
# Copiamos as mesmas regras do importador para garantir que a comparação seja justa
PALAVRAS_TIRO_CERTO = {
    'pis': 'Direito Tributário', 'cofins': 'Direito Tributário', 'irpj': 'Direito Tributário',
    'csll': 'Direito Tributário', 'lucro presumido': 'Direito Tributário', 'lucro real': 'Direito Tributário',
    'tributo': 'Direito Tributário', 'tributaria': 'Direito Tributário', 'imposto': 'Direito Tributário',
    'icms': 'Direito Tributário', 'ipi': 'Direito Tributário', 'iss': 'Direito Tributário',
    'execucao fiscal': 'Direito Tributário', 'inss': 'Direito Previdenciário',
    'previdencia': 'Direito Previdenciário', 'beneficio assistencial': 'Direito Previdenciário',
    'servidor publico': 'Direito Administrativo', 'improbidade': 'Direito Administrativo',
    'penal': 'Direito Penal', 'crime': 'Direito Penal', 'pena': 'Direito Penal'
}

def normalizar_texto_regex(texto):
    if not isinstance(texto, str): return ""
    nfkd = unicodedata.normalize('NFKD', texto)
    texto = u"".join([c for c in nfkd if not unicodedata.combining(c)])
    return texto.lower()

def carregar_arquivo_universal(caminho):
    print(f"Lendo arquivo original: {caminho}...")
    try: return pd.read_html(caminho, encoding='utf-8', header=0)[0]
    except: pass
    try: return pd.read_html(caminho, encoding='latin1', header=0)[0]
    except: pass
    try: return pd.read_excel(caminho)
    except: return None

# --- 3. GERAÇÃO DO PADRÃO (IA) ---
def gerar_classificacao_padrao():
    print("--- Recalculando padrão da IA para comparação ---")
    
    # Carrega Modelo
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2', device='cpu')
    
    # Carrega STJ
    if not os.path.exists(ARQUIVO_STJ): return None
    df_stj = pd.read_csv(ARQUIVO_STJ, sep=';', encoding='latin1', on_bad_lines='skip')
    df_stj.columns = [c.strip() for c in df_stj.columns]
    
    col_ramo = next((c for c in df_stj.columns if 'ramo' in c.lower()), None)
    cols_texto_stj = [c for c in df_stj.columns if any(x in c.lower() for x in ['assuntos', 'questão', 'tese'])]
    
    textos_por_ramo = {}
    for _, row in df_stj.iterrows():
        if pd.isna(row[col_ramo]): continue
        ramo = str(row[col_ramo]).replace("DIREITO", "").strip().title()
        ramo = f"Direito {ramo}"
        conteudo = " ".join([str(row[c]) for c in cols_texto_stj if pd.notna(row[c])])
        if ramo not in textos_por_ramo: textos_por_ramo[ramo] = ""
        if len(textos_por_ramo[ramo]) < 50000: textos_por_ramo[ramo] += " " + conteudo
            
    nomes_ramos = list(textos_por_ramo.keys())
    embeddings_ramos = model.encode(list(textos_por_ramo.values()), convert_to_tensor=True)
    
    # Carrega STF Original
    df_stf = carregar_arquivo_universal(ARQUIVO_STF)
    
    # Mapeia colunas
    mapa = {}
    for c in df_stf.columns:
        if 'tema' in c.lower() and 'situa' not in c.lower(): mapa[c] = 'Tema'
        elif 'título' in c.lower(): mapa[c] = 'Título'
        elif 'descri' in c.lower(): mapa[c] = 'Descrição'
        elif 'tese' in c.lower() and 'data' not in c.lower(): mapa[c] = 'Tese'
        elif 'assunto' in c.lower(): mapa[c] = 'Assuntos'
    df_stf = df_stf.rename(columns=mapa)
    
    # Classifica
    print("Classificando original...")
    ramos_ia = []
    cols_texto = ['Título', 'Descrição', 'Tese', 'Assuntos']
    indices_ia = []
    textos_ia = []
    
    for idx, row in df_stf.iterrows():
        # Regra de Ouro
        txt_completo = " ".join([str(row.get(c, '')) for c in cols_texto])
        txt_limpo = normalizar_texto_regex(txt_completo)
        
        achou = None
        for p, r in PALAVRAS_TIRO_CERTO.items():
            if re.search(r"\b" + re.escape(p) + r"\b", txt_limpo):
                achou = r
                break
        
        if achou:
            ramos_ia.append(achou)
        else:
            ramos_ia.append(None)
            indices_ia.append(idx)
            textos_ia.append(txt_completo)
            
    # Completa com IA
    if indices_ia:
        emb_stf = model.encode(textos_ia, convert_to_tensor=True)
        res = util.cos_sim(emb_stf, embeddings_ramos)
        idxs = res.argmax(dim=1).cpu().detach().numpy().flatten()
        for i, real_idx in enumerate(indices_ia):
            ramos_ia[real_idx] = nomes_ramos[idxs[i]]
            
    df_stf['Ramo_Padrao_IA'] = ramos_ia
    
    # Limpa Tema para int
    df_stf['Tema'] = pd.to_numeric(df_stf['Tema'], errors='coerce').fillna(0).astype(int)
    
    return df_stf[['Tema', 'Título', 'Ramo_Padrao_IA']]

# --- 4. COMPARAÇÃO COM O BANCO ---
def gerar_relatorio():
    # 1. Pega o estado atual do Banco (Onde estão suas edições)
    print("Lendo Banco de Dados (Suas Edições)...")
    df_banco = pd.read_sql("SELECT * FROM temas_stf", engine)
    df_banco['Tema'] = pd.to_numeric(df_banco['Tema'], errors='coerce').fillna(0).astype(int)
    df_banco = df_banco[['Tema', 'Ramo do Direito']].rename(columns={'Ramo do Direito': 'Ramo_Atual_Banco'})
    
    # 2. Gera o que seria o padrão sem edição
    df_padrao = gerar_classificacao_padrao()
    
    if df_padrao is None: return

    # 3. Cruza os dados
    print("\n--- Comparando ---")
    df_final = pd.merge(df_banco, df_padrao, on='Tema', how='inner')
    
    # 4. Filtra onde é diferente
    # Normaliza strings para evitar erro de espaço (ex: "Penal " vs "Penal")
    df_final['Ramo_Atual_Banco'] = df_final['Ramo_Atual_Banco'].astype(str).str.strip()
    df_final['Ramo_Padrao_IA'] = df_final['Ramo_Padrao_IA'].astype(str).str.strip()
    
    alterados = df_final[df_final['Ramo_Atual_Banco'] != df_final['Ramo_Padrao_IA']]
    
    # Ordena por Tema
    alterados = alterados.sort_values(by='Tema')
    
    # --- RESULTADO ---
    print(f"\n✅ Encontrados {len(alterados)} temas com classificação manual (diferente da IA).")
    
    if not alterados.empty:
        print("\n--- LISTA DE TEMAS ALTERADOS ---")
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        
        # Mostra colunas bonitas
        view = alterados[['Tema', 'Ramo_Atual_Banco', 'Ramo_Padrao_IA', 'Título']]
        print(view.to_string(index=False))
        
        # Salva em Excel
        nome_arquivo = "relatorio_temas_alterados_manualmente.xlsx"
        view.to_excel(nome_arquivo, index=False)
        print(f"\n📄 Relatório salvo como: {nome_arquivo}")
    else:
        print("Nenhuma alteração manual detectada (O banco está igual à sugestão da IA).")

if __name__ == "__main__":
    gerar_relatorio()