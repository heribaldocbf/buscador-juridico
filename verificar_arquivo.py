from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma

PASTA_BANCO_DE_DADOS = "banco_de_dados_juridico"
NOME_ARQUIVO_PARA_VERIFICAR = "info-980-stf.docx"
ARQUIVO_SAIDA = "resultado_verificacao.txt"

print(f"Inspecionando '{NOME_ARQUIVO_PARA_VERIFICAR}' e salvando em '{ARQUIVO_SAIDA}'...")

try:
    embeddings_model = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
    db = Chroma(persist_directory=PASTA_BANCO_DE_DADOS, embedding_function=embeddings_model)
    
    resultados = db.get(where={"arquivo_fonte": NOME_ARQUIVO_PARA_VERIFICAR}, include=["documents"])
    documentos = resultados.get('documents', [])

    with open(ARQUIVO_SAIDA, 'w', encoding='utf-8') as f:
        if not documentos:
            f.write(f"ERRO: Nenhum conteúdo encontrado para o arquivo '{NOME_ARQUIVO_PARA_VERIFICAR}'.\n")
        else:
            f.write(f"--- Conteúdo de '{NOME_ARQUIVO_PARA_VERIFICAR}' encontrado no banco de dados ---\n\n")
            for i, doc_content in enumerate(documentos):
                f.write(f"--- Pedaço (Chunk) {i+1} ---\n")
                f.write(doc_content + "\n")
                f.write("-" * 20 + "\n")
            f.write(f"\nVerificação concluída. Encontrados {len(documentos)} pedaços de texto.\n")
    
    print(f"Verificação concluída. Abra o arquivo '{ARQUIVO_SAIDA}' para ver o resultado.")

except Exception as e:
    print(f"Ocorreu um erro: {e}")