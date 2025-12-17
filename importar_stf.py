import pandas as pd
from sqlalchemy import create_engine
import re
import os
import warnings
import unicodedata
from collections import Counter

# Ignora avisos
warnings.filterwarnings("ignore")

# --- 1. CONFIGURAÇÃO ---
db_url = "postgresql://postgres:Badinho201.@db.rxmctzxlemptfaydemkw.supabase.co:5432/postgres"
engine = create_engine(db_url)

# --- 2. LISTA DE COLUNAS (ORDEM EXATA A -> O) ---
COLUNAS_CORRETAS = [
    'Tema', 'Leading Case', 'Relator', 'Título', 'Descrição', 
    'Assuntos', 'Manifestação', 'Acórdão', 'Plenário Virtual', 
    'Há Repercussão', 'Data do Julgamento', 'Situação do Tema', 
    'Tese', 'Data da Tese', 'Observação'
]

# --- 3. ALGORITMO DE APRENDIZADO (TREINAMENTO COM STJ) ---
def normalizar_texto(texto):
    """Remove acentos, caracteres especiais e coloca em minúsculas."""
    if not isinstance(texto, str): return ""
    # Normaliza unicode (á -> a)
    nfkd = unicodedata.normalize('NFKD', texto)
    texto_sem_acento = u"".join([c for c in nfkd if not unicodedata.combining(c)])
    # Remove tudo que não for letra ou número
    texto_limpo = re.sub(r'[^a-zA-Z0-9\s]', '', texto_sem_acento)
    return texto_limpo.lower()

def treinar_com_stj(caminho_csv_stj):
    print("🧠 Iniciando aprendizado com a base do STJ...")
    try:
        df_stj = pd.read_csv(caminho_csv_stj, sep=';', encoding='latin1')
    except Exception as e:
        print(f"Erro ao ler CSV do STJ: {e}")
        return None

    # Dicionário para armazenar a frequência das palavras por ramo
    # Ex: {'direito tributario': {'icms': 50, 'tributo': 30}, ...}
    modelo = {}
    
    # Palavras irrelevantes para ignorar (stopwords)
    stopwords = {
        'de', 'a', 'o', 'que', 'e', 'do', 'da', 'em', 'um', 'para', 'com', 'nao', 'uma', 'os', 'no', 
        'se', 'na', 'por', 'mais', 'as', 'dos', 'como', 'mas', 'ao', 'ele', 'das', 'tem', 'seu', 
        'sua', 'ou', 'ser', 'quando', 'muito', 'nos', 'ja', 'esta', 'eu', 'tambem', 'só', 'pelo', 
        'pela', 'ate', 'isso', 'ela', 'entre', 'depois', 'sem', 'mesmo', 'aos', 'ter', 'seus', 'quem', 
        'nas', 'me', 'esse', 'eles', 'voce', 'essa', 'num', 'nem', 'suas', 'meu', 'as', 'minha', 
        'numa', 'pelos', 'elas', 'qual', 'nos', 'lhe', 'deles', 'essas', 'esses', 'pelas', 'este', 
        'dele', 'tu', 'te', 'voces', 'vos', 'lhes', 'meus', 'minhas', 'teu', 'tua', 'teus', 'tuas', 
        'nosso', 'nossa', 'nossos', 'nossas', 'dela', 'delas', 'esta', 'estes', 'estas', 'aquele', 
        'aquela', 'aqueles', 'aquelas', 'isto', 'aquilo', 'estou', 'sobre', 'lei', 'art', 'artigo',
        'federal', 'n', 'cpc', 'código', 'codigo', 'processo', 'civil', 'direito' # 'direito' é muito comum, melhor tirar
    }

    # Itera sobre o STJ para aprender
    colunas_texto = ['Assuntos', 'Questão submetida a julgamento', 'Tese Firmada']
    
    for _, row in df_stj.iterrows():
        ramo = row['Ramo do direito']
        if pd.isna(ramo): continue
        
        # Limpa o nome do ramo (ex: "DIREITO TRIBUTÁRIO" -> "Direito Tributário")
        ramo = ramo.strip().title() 
        
        if ramo not in modelo:
            modelo[ramo] = Counter()
        
        # Junta todo texto útil da linha para aprender
        texto_linha = ""
        for col in colunas_texto:
            if col in df_stj.columns:
                texto_linha += " " + str(row[col])
        
        palavras = normalizar_texto(texto_linha).split()
        
        # Conta as palavras relevantes
        palavras_uteis = [p for p in palavras if p not in stopwords and len(p) > 2]
        modelo[ramo].update(palavras_uteis)

    print("✅ Aprendizado concluído. Classificador pronto.")
    return modelo

# --- 4. FUNÇÃO DE CLASSIFICAÇÃO ---
def classificar_pelo_modelo(texto, modelo):
    if not modelo or not isinstance(texto, str):
        return "Outros"
    
    texto_norm = normalizar_texto(texto)
    palavras = set(texto_norm.split()) # set para palavras únicas no texto
    
    melhor_ramo = "Outros"
    maior_pontuacao = 0
    
    for ramo, contador_palavras in modelo.items():
        pontuacao = 0
        for palavra in palavras:
            # Se a palavra existe no ramo, soma a frequência dela como pontuação
            if palavra in contador_palavras:
                # O peso é a frequência da palavra naquele ramo
                pontuacao += contador_palavras[palavra]
        
        if pontuacao > maior_pontuacao:
            maior_pontuacao = pontuacao
            melhor_ramo = ramo
            
    # Se a pontuação for muito baixa (ex: nenhuma palavra chave encontrada), joga para Outros
    if maior_pontuacao < 2: # Ajuste esse limiar se necessário
        return "Outros"
        
    return melhor_ramo

# --- 5. EXECUÇÃO PRINCIPAL ---

# 1. Carrega e Treina com o STJ
caminho_stj = "relatorio.csv" # Certifique-se que o arquivo está na mesma pasta
modelo_treinado = treinar_com_stj(caminho_stj)

# 2. Carrega o Excel do STF
try:
    # Procura arquivos xlsx na pasta
    arquivos = [f for f in os.listdir('.') if f.endswith('.xlsx') or f.endswith('.xls')]
    if not arquivos:
        raise Exception("Nenhum arquivo Excel encontrado.")
    
    arquivo_fonte = arquivos[0]
    print(f"Lendo arquivo STF: {arquivo_fonte}")
    
    df_novo = pd.read_excel(arquivo_fonte)
    
    # Remove linhas vazias
    df_novo = df_novo.dropna(how='all')
    
    # Ajusta colunas para garantir que temos todas
    for col in COLUNAS_CORRETAS:
        if col not in df_novo.columns:
            df_novo[col] = None
            
    # Garante a ordem e quantidade
    df_novo = df_novo[COLUNAS_CORRETAS]

except Exception as e:
    print(f"Erro ao carregar Excel do STF: {e}")
    exit()

# 3. Classifica os dados do STF
print("Classificando temas do STF baseados no padrão STJ...")

def aplicar_classificacao(row):
    # Junta Título, Descrição e Assuntos para dar mais contexto ao classificador
    texto_completo = f"{str(row['Título'])} {str(row['Descrição'])} {str(row['Assuntos'])}"
    return classificar_pelo_modelo(texto_completo, modelo_treinado)

df_novo['Ramo do Direito'] = df_novo.apply(aplicar_classificacao, axis=1)

# --- 6. SALVAR NO BANCO ---
print("Salvando no banco de dados...")
try:
    # Remove aspas se houver na coluna Tema para garantir inteiro
    df_novo['Tema'] = pd.to_numeric(df_novo['Tema'], errors='coerce').fillna(0).astype(int)
    
    # Envia para o banco (substitui a tabela inteira ou usa append conforme sua lógica)
    # Aqui estou usando 'replace' para garantir que a estrutura nova entre
    df_novo.to_sql('temas_stf', engine, if_exists='replace', index=False)
    print("Sucesso! Dados do STF classificados e importados.")
    
    # Exibe uma amostra para você ver se funcionou
    print("\n--- Amostra da Classificação ---")
    print(df_novo[['Tema', 'Ramo do Direito']].head(10))

except Exception as e:
    print(f"Erro ao salvar no banco: {e}")