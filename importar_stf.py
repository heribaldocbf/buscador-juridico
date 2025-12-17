import pandas as pd
from sqlalchemy import create_engine
import os
import warnings
from sentence_transformers import SentenceTransformer, util
import torch
import numpy as np
import unicodedata
import re

# Ignora avisos
warnings.filterwarnings("ignore")

# --- 1. CONFIGURAÇÃO ---
db_url = "postgresql://postgres:Badinho201.@db.rxmctzxlemptfaydemkw.supabase.co:5432/postgres"
engine = create_engine(db_url)

ARQUIVO_STJ = "relatorio.csv"
ARQUIVO_STF = "RepercussaoGeral.xls"

# --- 2. LISTA DE "TIRO CERTO" ---
PALAVRAS_TIRO_CERTO = {
    'pis': 'Direito Tributário',
    'cofins': 'Direito Tributário',
    'irpj': 'Direito Tributário',
    'csll': 'Direito Tributário',
    'lucro presumido': 'Direito Tributário',
    'lucro real': 'Direito Tributário',
    'tributo': 'Direito Tributário',
    'tributaria': 'Direito Tributário',
    'tributario': 'Direito Tributário',
    'imposto': 'Direito Tributário',
    'icms': 'Direito Tributário',
    'ipi': 'Direito Tributário',
    'iss': 'Direito Tributário',
    'ipva': 'Direito Tributário',
    'iptu': 'Direito Tributário',
    'itbi': 'Direito Tributário',
    'execucao fiscal': 'Direito Tributário',
    'imunidade tributaria': 'Direito Tributário',
    'simples nacional': 'Direito Tributário',
    'fisco': 'Direito Tributário',
    'fazenda publica': 'Direito Tributário',
    'cdra': 'Direito Tributário',
    'inss': 'Direito Previdenciário',
    'previdencia': 'Direito Previdenciário',
    'previdenciario': 'Direito Previdenciário',
    'aposentadoria': 'Direito Previdenciário',
    'beneficio assistencial': 'Direito Previdenciário',
    'loas': 'Direito Previdenciário',
    'auxilio-doenca': 'Direito Previdenciário',
    'auxilio doenca': 'Direito Previdenciário',
    'rgps': 'Direito Previdenciário',
    'servidor publico': 'Direito Administrativo',
    'improbidade': 'Direito Administrativo',
    'licitacao': 'Direito Administrativo',
    'concurso publico': 'Direito Administrativo',
    'desapropriacao': 'Direito Administrativo',
    'tcu': 'Direito Administrativo',
    'penal': 'Direito Penal',
    'crime': 'Direito Penal',
    'pena': 'Direito Penal',
    'habeas corpus': 'Direito Penal',
    'prisional': 'Direito Penal'
}

# --- 3. FUNÇÕES DE LIMPEZA E LEITURA ---
def normalizar_texto_regex(texto):
    if not isinstance(texto, str): return ""
    nfkd = unicodedata.normalize('NFKD', texto)
    texto = u"".join([c for c in nfkd if not unicodedata.combining(c)])
    return texto.lower()

def carregar_arquivo_universal(caminho):
    print(f"Lendo arquivo: {caminho}...")
    try: return pd.read_html(caminho, encoding='utf-8', header=0)[0]
    except: pass
    try: return pd.read_html(caminho, encoding='latin1', header=0)[0]
    except: pass
    try: return pd.read_excel(caminho)
    except: pass
    try: return pd.read_csv(caminho, sep='\t', encoding='latin1')
    except: return None

# --- 4. PREPARAÇÃO DA IA ---
def criar_perfis_ramos_stj():
    print(f"\n--- 🧠 INICIANDO CÉREBRO DIGITAL ---")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2', device='cpu')
    
    if not os.path.exists(ARQUIVO_STJ): return None, None, None

    try:
        df = pd.read_csv(ARQUIVO_STJ, sep=';', encoding='latin1', on_bad_lines='skip')
        df.columns = [c.strip() for c in df.columns]
    except: return None, None, None

    col_ramo = next((c for c in df.columns if 'ramo' in c.lower()), None)
    cols_texto = [c for c in df.columns if any(x in c.lower() for x in ['assuntos', 'questão', 'tese'])]

    textos_por_ramo = {}
    print("Aprendendo perfis com STJ...")
    for _, row in df.iterrows():
        ramo_bruto = row[col_ramo]
        if pd.isna(ramo_bruto): continue
        ramo = str(ramo_bruto).replace("DIREITO", "").strip().title()
        ramo = f"Direito {ramo}"
        conteudo = " ".join([str(row[c]) for c in cols_texto if pd.notna(row[c])])
        if ramo not in textos_por_ramo: textos_por_ramo[ramo] = ""
        if len(textos_por_ramo[ramo]) < 50000: textos_por_ramo[ramo] += " " + conteudo

    nomes = list(textos_por_ramo.keys())
    embeddings = model.encode(list(textos_por_ramo.values()), convert_to_tensor=True)
    return model, nomes, embeddings

# --- 5. CLASSIFICAÇÃO HÍBRIDA ---
def classificar_hibrido(df_stf, model, nomes_ramos, embeddings_ramos):
    print("\n--- CLASSIFICANDO ---")
    ramos_finais = []
    cols_texto = ['Título', 'Descrição', 'Tese', 'Assuntos']
    indices_para_ia = []
    textos_para_ia = []
    
    for idx, row in df_stf.iterrows():
        cols_validas = [c for c in cols_texto if c in df_stf.columns]
        texto_completo = " ".join([str(row.get(c, '')).lower() for c in cols_validas])
        texto_limpo = normalizar_texto_regex(texto_completo)
        
        ramo_detectado = None
        for palavra, ramo in PALAVRAS_TIRO_CERTO.items():
            padrao = r"\b" + re.escape(palavra) + r"\b"
            if re.search(padrao, texto_limpo):
                ramo_detectado = ramo
                break 
        
        if ramo_detectado:
            ramos_finais.append(ramo_detectado)
        else:
            ramos_finais.append(None)
            indices_para_ia.append(idx)
            textos_para_ia.append(texto_completo)
            
    if indices_para_ia:
        print(f"IA processando {len(indices_para_ia)} casos...")
        embeddings_stf = model.encode(textos_para_ia, convert_to_tensor=True)
        resultados = util.cos_sim(embeddings_stf, embeddings_ramos)
        indices_ganhadores = resultados.argmax(dim=1).cpu().detach().numpy().flatten()
        for i, idx_real in enumerate(indices_para_ia):
            idx_ramo = indices_ganhadores[i]
            ramos_finais[idx_real] = nomes_ramos[idx_ramo]
            
    return ramos_finais

# --- 6. EXECUÇÃO ---

# A. IA e Arquivos
model, nomes_ramos, embeddings_ramos = criar_perfis_ramos_stj()
if not model: exit()

df_stf = carregar_arquivo_universal(ARQUIVO_STF)
if df_stf is None: exit()

# Renomeia
mapa = {}
for c in df_stf.columns:
    c_low = c.lower()
    if 'título' in c_low or 'titulo' in c_low: mapa[c] = 'Título'
    elif 'tema' in c_low and 'situa' not in c_low: mapa[c] = 'Tema'
    elif 'descri' in c_low: mapa[c] = 'Descrição'
    elif 'tese' in c_low and 'data' not in c_low: mapa[c] = 'Tese'
    elif 'assunto' in c_low: mapa[c] = 'Assuntos'
    elif 'situa' in c_low: mapa[c] = 'Situação do Tema'
    elif 'julga' in c_low: mapa[c] = 'Data do Julgamento'
    elif 'leading' in c_low: mapa[c] = 'Leading Case'

df_stf = df_stf.rename(columns=mapa)
df_stf = df_stf.loc[:, ~df_stf.columns.duplicated()]

# C. Classifica TUDO (Como se fosse novo)
print("Gerando classificação sugerida para todos os itens...")
df_stf['Ramo do Direito'] = classificar_hibrido(df_stf, model, nomes_ramos, embeddings_ramos)

# ==============================================================================
# 🛡️ D. O PULO DO GATO: PROTEÇÃO DE EDIÇÕES MANUAIS
# ==============================================================================
print("\n--- 4. Verificando edições manuais no Banco de Dados ---")

try:
    # 1. Lê o que já existe no banco hoje
    df_banco_atual = pd.read_sql("SELECT * FROM temas_stf", engine)
    
    if not df_banco_atual.empty:
        print(f"Banco atual tem {len(df_banco_atual)} registros. Preservando edições...")
        
        # Cria um dicionário {TEMA: RAMO_NO_BANCO}
        # Garante que Tema seja inteiro para bater certo
        df_banco_atual['Tema'] = pd.to_numeric(df_banco_atual['Tema'], errors='coerce').fillna(0).astype(int)
        mapa_preservacao = dict(zip(df_banco_atual['Tema'], df_banco_atual['Ramo do Direito']))
        
        # 2. Função que decide qual ramo usar
        def mesclar_inteligente(row):
            try:
                tema_atual = int(row['Tema'])
            except:
                return row['Ramo do Direito'] # Se não tiver tema, usa o novo
            
            # Se esse tema JÁ EXISTE no banco, usamos o que está no banco (Manual)
            if tema_atual in mapa_preservacao:
                ramo_banco = mapa_preservacao[tema_atual]
                # Pequena segurança: se o banco estiver vazio/nulo, usa o novo
                if ramo_banco and str(ramo_banco).strip() != '' and str(ramo_banco) != 'None':
                    return ramo_banco
            
            # Se é tema novo OU o banco estava vazio, usa a classificação nova da IA
            return row['Ramo do Direito']

        # Aplica a mesclagem
        df_stf['Ramo do Direito'] = df_stf.apply(mesclar_inteligente, axis=1)
        print("✅ Mesclagem concluída: Edições manuais antigas foram mantidas.")
    else:
        print("Banco vazio. Usando 100% das classificações novas.")

except Exception as e:
    print(f"⚠️ Aviso: Não consegui ler o banco atual (pode ser a primeira execução). Erro: {e}")


# E. Salvar
print("\n--- Salvando no Banco ---")
try:
    cols_possiveis = ['Tema', 'Título', 'Descrição', 'Tese', 'Assuntos', 'Ramo do Direito', 'Leading Case', 'Situação do Tema', 'Data do Julgamento']
    cols_finais = [c for c in cols_possiveis if c in df_stf.columns]
    
    df_final = df_stf[cols_finais].copy()
    
    for col in df_final.columns:
        if col == 'Tema':
            df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0).apply(lambda x: int(x))
        else:
            df_final[col] = df_final[col].astype(str).replace({'nan': '', 'None': '', '<NA>': ''})

    df_final.to_sql('temas_stf', engine, if_exists='replace', index=False)
    print("✅ SUCESSO! Banco atualizado (Novos inseridos, Manuais preservados).")

except Exception as e:
    print(f"❌ Erro ao salvar: {e}")

# Se o arquivo do STF ficar gigante no futuro (tipo 50.000 linhas) e começar a demorar muito, me avise. Podemos alterar o código para a IA ignorar o que já está no banco e calcular apenas os Temas Novos.
#Mas, por enquanto, do jeito que está é mais seguro, pois garante que qualquer melhoria que você faça no código (novas regras) seja aplicada retroativamente em tudo o que não foi travado manualmente.