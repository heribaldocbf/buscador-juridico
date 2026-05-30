import pandas as pd
from sqlalchemy import create_engine
import os
import warnings
from sentence_transformers import SentenceTransformer, util
import re
import unicodedata
from db_config import create_db_engine

# Ignora avisos
warnings.filterwarnings("ignore")

# --- 1. CONFIGURAÇÃO ---
engine = create_db_engine()

ARQUIVO_STF = "RepercussaoGeral.xls"
PASTA_TREINAMENTO = "Temas STF" # Pasta com os xls divididos por ramo

# --- 2. NOVA LISTA DE RAMOS E TIRO CERTO ---
# Atualizei para bater com seus novos ramos. 
# Você pode adicionar mais palavras-chave aqui se quiser forçar certas classificações.
PALAVRAS_TIRO_CERTO = {
    # Tributário
    'tributo': 'Direito Tributário', 'icms': 'Direito Tributário', 'pis': 'Direito Tributário', 
    'cofins': 'Direito Tributário', 'ipva': 'Direito Tributário', 'iptu': 'Direito Tributário',
    'imunidade tributaria': 'Direito Tributário', 'execucao fiscal': 'Direito Tributário',
    
    # Previdenciário (Não está na sua lista explícita nova, mas se cair em algum ramo, deve ser definido. 
    # Se "Previdenciário" não for um ramo final, ele vai cair provavelmente em Administrativo ou terá que treinar a IA)
    # *Nota*: Se Direito Previdenciário não existe mais, remova ou mapeie para outro. 
    # Vou manter comentado caso queira mapear para "Direito Administrativo" ou outro.
    # 'inss': 'Direito Administrativo', 
    
    # Administrativo
    'servidor': 'Direito Administrativo', 'concurso': 'Direito Administrativo', 
    'improbidade': 'Direito Administrativo', 'licitacao': 'Direito Administrativo',
    'desapropriacao': 'Direito Administrativo',
    
    # Penal
    'penal': 'Direito Penal', 'crime': 'Direito Penal', 'pena': 'Direito Penal', 
    'habeas corpus': 'Direito Penal', 'prisional': 'Direito Penal',
    
    # Trabalhista
    'trabalho': 'Direito do Trabalho', 'trabalhista': 'Direito do Trabalho',
    'fgts': 'Direito do Trabalho', 'terceirizacao': 'Direito do Trabalho',
    
    # Eleitoral
    'eleicao': 'Direito Eleitoral', 'candidato': 'Direito Eleitoral', 'partido politico': 'Direito Eleitoral',
    
    # Consumidor
    'consumidor': 'Direito do Consumidor', 'banco': 'Direito do Consumidor', 'telefonia': 'Direito do Consumidor',
    
    # Ambiental
    'ambiental': 'Direito Ambiental', 'meio ambiente': 'Direito Ambiental', 'florestal': 'Direito Ambiental'
}

# --- 3. FUNÇÕES UTILITÁRIAS ---
def normalizar_texto_regex(texto):
    if not isinstance(texto, str): return ""
    nfkd = unicodedata.normalize('NFKD', texto)
    texto = u"".join([c for c in nfkd if not unicodedata.combining(c)])
    return texto.lower()

def carregar_arquivo_universal(caminho):
    print(f"Lendo arquivo STF: {caminho}...")
    try: return pd.read_html(caminho, encoding='utf-8', header=0)[0]
    except: pass
    try: return pd.read_excel(caminho)
    except: return None

# --- 4. PREPARAÇÃO DA IA (Treinando com sua pasta "Temas STF") ---
def treinar_ia_com_pasta_local():
    print(f"\n--- 🧠 TREINANDO CÉREBRO COM ARQUIVOS DA PASTA '{PASTA_TREINAMENTO}' ---")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2', device='cpu')
    
    if not os.path.exists(PASTA_TREINAMENTO):
        print(f"Erro: Pasta {PASTA_TREINAMENTO} não encontrada. A IA não terá base de comparação.")
        return None, None, None

    arquivos = [f for f in os.listdir(PASTA_TREINAMENTO) if f.endswith('.xls') or f.endswith('.xlsx')]
    
    textos_por_ramo = {}
    
    print(f"Lendo {len(arquivos)} arquivos de ramos para aprendizado...")
    
    for arquivo in arquivos:
        ramo = os.path.splitext(arquivo)[0] # O nome do arquivo vira o nome do Ramo
        caminho = os.path.join(PASTA_TREINAMENTO, arquivo)
        
        try:
            try: df = pd.read_excel(caminho)
            except: df = pd.read_html(caminho, header=0)[0]
            
            # Pega colunas de texto para aprender o vocabulário
            cols_texto = [c for c in df.columns if any(x in c.lower() for x in ['titulo', 'título', 'descri', 'tese', 'assunto'])]
            
            # Junta todo o texto desse ramo num "sacão" de palavras
            conteudo_list = []
            for c in cols_texto:
                conteudo_list.extend(df[c].dropna().astype(str).tolist())
            
            # Limita tamanho para não estourar memória, mas pega bastante texto
            texto_consolidado = " ".join(conteudo_list[:3000]) 
            
            textos_por_ramo[ramo] = texto_consolidado
        except Exception as e:
            print(f"Erro ao ler {arquivo} para treino: {e}")

    nomes_ramos = list(textos_por_ramo.keys())
    print(f"Ramos aprendidos: {nomes_ramos}")
    
    embeddings_ramos = model.encode(list(textos_por_ramo.values()), convert_to_tensor=True)
    return model, nomes_ramos, embeddings_ramos

# --- 5. CLASSIFICAÇÃO ---
def classificar_novos(df_novos, model, nomes_ramos, embeddings_ramos):
    print(f"\n--- CLASSIFICANDO {len(df_novos)} ITENS NOVOS ---")
    ramos_finais = []
    
    # Colunas onde procurar texto
    cols_texto = [c for c in df_novos.columns if any(x in c.lower() for x in ['titulo', 'título', 'descri', 'tese', 'assunto'])]
    
    indices_para_ia = []
    textos_para_ia = []
    
    for idx, row in df_novos.iterrows():
        texto_completo = " ".join([str(row.get(c, '')).lower() for c in cols_texto])
        texto_limpo = normalizar_texto_regex(texto_completo)
        
        # 1. Tenta Regex (Tiro Certo)
        ramo_detectado = None
        for palavra, ramo in PALAVRAS_TIRO_CERTO.items():
            padrao = r"\b" + re.escape(palavra) + r"\b"
            if re.search(padrao, texto_limpo):
                ramo_detectado = ramo
                break 
        
        if ramo_detectado:
            ramos_finais.append(ramo_detectado)
        else:
            # Se não achou por palavra-chave, manda pra IA
            ramos_finais.append(None) 
            indices_para_ia.append(len(ramos_finais) - 1) # Guarda o índice atual na lista ramos_finais
            textos_para_ia.append(texto_completo)
            
    # 2. Processa IA em lote
    if indices_para_ia and model:
        print(f"IA processando {len(indices_para_ia)} casos complexos...")
        embeddings_stf = model.encode(textos_para_ia, convert_to_tensor=True)
        resultados = util.cos_sim(embeddings_stf, embeddings_ramos)
        indices_ganhadores = resultados.argmax(dim=1).cpu().detach().numpy().flatten()
        
        for i, idx_lista in enumerate(indices_para_ia):
            idx_ramo = indices_ganhadores[i]
            ramos_finais[idx_lista] = nomes_ramos[idx_ramo]
    
    # Fallback se IA falhar ou não estiver carregada
    for i in range(len(ramos_finais)):
        if ramos_finais[i] is None:
            ramos_finais[i] = "Não Classificado"

    return ramos_finais

# --- 6. EXECUÇÃO PRINCIPAL ---

# A. Carregar dados atuais do STF (Arquivo novo baixado)
df_stf_completo = carregar_arquivo_universal(ARQUIVO_STF)
if df_stf_completo is None: exit()

# Renomeia colunas para padrão
mapa = {}
for c in df_stf_completo.columns:
    c_low = c.lower()
    if 'título' in c_low or 'titulo' in c_low: mapa[c] = 'Título'
    elif 'tema' in c_low and 'situa' not in c_low: mapa[c] = 'Tema'
    elif 'descri' in c_low: mapa[c] = 'Descrição'
    elif 'tese' in c_low and 'data' not in c_low: mapa[c] = 'Tese'
    elif 'assunto' in c_low: mapa[c] = 'Assuntos'
    elif 'situa' in c_low: mapa[c] = 'Situação do Tema'
    elif 'julga' in c_low: mapa[c] = 'Data do Julgamento'
    elif 'leading' in c_low: mapa[c] = 'Leading Case'

df_stf_completo = df_stf_completo.rename(columns=mapa)
# Garante Tema como int
df_stf_completo['Tema'] = pd.to_numeric(df_stf_completo['Tema'], errors='coerce').fillna(0).astype(int)

# B. Verificar o que já existe no Banco
print("Verificando banco de dados para atualizações incrementais...")
try:
    temas_existentes = pd.read_sql("SELECT \"Tema\" FROM temas_stf", engine)
    lista_ids_existentes = temas_existentes['Tema'].astype(int).tolist()
    print(f"Existem {len(lista_ids_existentes)} temas no banco.")
except:
    lista_ids_existentes = []
    print("Banco parece vazio ou tabela não existe.")

# C. Filtrar APENAS OS NOVOS
df_novos = df_stf_completo[~df_stf_completo['Tema'].isin(lista_ids_existentes)].copy()

if df_novos.empty:
    print("✅ Nenhum tema novo encontrado. Banco já está atualizado.")
    # Se quiser atualizar colunas não-classificatórias (como Situação) de temas velhos, 
    # seria necessário um código extra de UPDATE aqui, mas para classificação, paramos aqui.
    exit()

print(f"⚠️ Encontrados {len(df_novos)} NOVOS temas para cadastrar.")

# D. Treinar IA e Classificar apenas os novos
model, nomes_ramos, embeddings_ramos = treinar_ia_com_pasta_local()
if model:
    df_novos['Ramo do Direito'] = classificar_novos(df_novos, model, nomes_ramos, embeddings_ramos)
else:
    print("Erro no carregamento da IA. Novos temas ficarão sem classificação.")
    df_novos['Ramo do Direito'] = "A Classificar"

# Data de alteração para os novos
df_novos['data_ultima_alteracao'] = None 

# E. Salvar apenas os novos (Append)
print("Inserindo novos temas no banco...")

cols_possiveis = ['Tema', 'Título', 'Descrição', 'Tese', 'Assuntos', 'Ramo do Direito', 'Leading Case', 'Situação do Tema', 'Data do Julgamento', 'data_ultima_alteracao']
cols_finais = [c for c in cols_possiveis if c in df_novos.columns]
df_final_novos = df_novos[cols_finais].copy()

# Limpeza final antes de inserir
for col in df_final_novos.columns:
    if col != 'Tema' and col != 'data_ultima_alteracao':
         df_final_novos[col] = df_final_novos[col].astype(str).replace({'nan': '', 'None': '', '<NA>': ''})

df_final_novos.to_sql('temas_stf', engine, if_exists='append', index=False)
print(f"✅ SUCESSO! {len(df_final_novos)} novos temas adicionados.")