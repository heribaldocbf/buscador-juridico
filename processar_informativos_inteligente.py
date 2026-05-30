import pandas as pd
from sqlalchemy import text
from pathlib import Path
from docx import Document
import json
import os
from datetime import datetime
from db_config import create_db_engine

# --- CONFIGURAÇÕES ---
# Defina o caminho para a sua pasta principal de informativos.
PASTA_PRINCIPAL_INFORMATIVOS = r"G:\Meu Drive\Direito\Informativos"

# 3. Nome do arquivo que guardará o estado do processamento.
ARQUIVO_ESTADO = "processamento_estado.json"

def carregar_estado():
    """Carrega o estado do último processamento (datas de modificação)."""
    if os.path.exists(ARQUIVO_ESTADO):
        with open(ARQUIVO_ESTADO, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {} # Retorna um dicionário vazio se o JSON estiver corrompido
    return {}

def salvar_estado(estado):
    """Salva o novo estado do processamento."""
    with open(ARQUIVO_ESTADO, 'w', encoding='utf-8') as f:
        json.dump(estado, f, indent=4)

def extrair_dados_docx(docx_path):
    """Extrai os dados de um único arquivo .docx."""
    dados_extraidos = []
    nome_arquivo, orgao = docx_path.name, docx_path.parent.name
    
    document = Document(docx_path)
    current_disciplina, current_assunto = "NÃO CLASSIFICADO", "NÃO CLASSIFICADO"
    capturando_tese = False

    for para in document.paragraphs:
        texto_paragrafo = para.text.strip()
        if not texto_paragrafo: continue

        estilo = para.style.name
        
        if estilo.startswith(('Heading 1', 'Título 1')):
            current_disciplina = texto_paragrafo
            current_assunto = "NÃO CLASSIFICADO"
            capturando_tese = False
        
        elif estilo.startswith(('Heading 2', 'Título 2')):
            current_assunto = texto_paragrafo
            capturando_tese = True
        
        elif capturando_tese:
            dados_extraidos.append({
                "arquivo_fonte": nome_arquivo,
                "orgao": orgao,
                "disciplina": current_disciplina,
                "assunto": current_assunto,
                "tese": texto_paragrafo
            })
            capturando_tese = False
    return dados_extraidos

def main():
    print("--- INICIANDO PROCESSADOR INTELIGENTE DE INFORMATIVOS ---")
    
    estado_anterior = carregar_estado()
    novo_estado = estado_anterior.copy()
    
    p = Path(PASTA_PRINCIPAL_INFORMATIVOS)
    if not p.exists():
        print(f"ERRO: A pasta de informativos não foi encontrada em '{PASTA_PRINCIPAL_INFORMATIVOS}'.")
        return

    todos_os_arquivos_locais = list(p.rglob("*.docx"))
    arquivos_para_processar = []
    arquivos_modificados = []

    print(f"\nVerificando {len(todos_os_arquivos_locais)} arquivos locais...")

    for docx_path in todos_os_arquivos_locais:
        nome_arquivo = docx_path.name
        mod_time_timestamp = os.path.getmtime(docx_path)
        mod_time_iso = datetime.fromtimestamp(mod_time_timestamp).isoformat()

        if nome_arquivo not in estado_anterior:
            print(f"  - NOVO: '{nome_arquivo}'")
            arquivos_para_processar.append(docx_path)
            novo_estado[nome_arquivo] = mod_time_iso
        elif estado_anterior[nome_arquivo] < mod_time_iso:
            print(f"  - MODIFICADO: '{nome_arquivo}'")
            arquivos_para_processar.append(docx_path)
            arquivos_modificados.append(nome_arquivo)
            novo_estado[nome_arquivo] = mod_time_iso

    if not arquivos_para_processar:
        print("\nNenhum arquivo novo ou modificado para processar. Tudo atualizado!")
        print("--- FINALIZADO ---")
        return

    engine = create_db_engine()
    try:
        # --- INÍCIO DA LÓGICA DE TRANSAÇÃO CORRIGIDA ---
        with engine.connect() as connection:
            with connection.begin() as transaction: # Começa uma transação
                try:
                    # Passo 1: Apagar dados antigos de arquivos modificados
                    if arquivos_modificados:
                        print(f"\nApagando {len(arquivos_modificados)} registro(s) antigo(s) do banco de dados...")
                        # Usar placeholders para segurança
                        placeholders = ', '.join([f":file{i}" for i in range(len(arquivos_modificados))])
                        params = {f"file{i}": filename for i, filename in enumerate(arquivos_modificados)}
                        query = text(f"DELETE FROM informativos WHERE arquivo_fonte IN ({placeholders})")
                        connection.execute(query, params)
                        print("Registros antigos apagados.")

                    # Passo 2: Processar e preparar novos dados
                    print(f"\nProcessando {len(arquivos_para_processar)} arquivo(s)...")
                    todos_os_novos_dados = []
                    for docx_path in arquivos_para_processar:
                        print(f"  - Extraindo de '{docx_path.name}'")
                        todos_os_novos_dados.extend(extrair_dados_docx(docx_path))
                    
                    if todos_os_novos_dados:
                        df_novos_dados = pd.DataFrame(todos_os_novos_dados)
                        df_novos_dados = df_novos_dados[
                            (df_novos_dados['disciplina'] != 'NÃO CLASSIFICADO') & 
                            (df_novos_dados['assunto'] != 'NÃO CLASSIFICADO') & 
                            (df_novos_dados['disciplina'] != 'ÍNDICE')
                        ]

                        # Passo 3: Inserir novos dados no banco de dados
                        print(f"\nInserindo {len(df_novos_dados)} novo(s) registro(s) no banco de dados...")
                        df_novos_dados.to_sql('informativos', connection, if_exists='append', index=False, method='multi')
                        print("Novos registros inseridos com sucesso.")
                    
                    # Se tudo correu bem, o 'with' fará o commit da transação
                    # transaction.commit() é chamado automaticamente ao sair do bloco 'with' sem erros
                    
                    # Passo 4: Salvar o novo estado apenas se a transação for bem-sucedida
                    salvar_estado(novo_estado)
                    print(f"\nEstado de processamento atualizado em '{ARQUIVO_ESTADO}'.")

                except Exception as e:
                    print(f"\n!!!! OCORREU UM ERRO DURANTE A OPERAÇÃO COM O BANCO DE DADOS !!!!")
                    print("A transação foi revertida (rollback). Nenhuma alteração foi salva no banco de dados.")
                    print(f"Detalhes do erro: {e}")
                    # transaction.rollback() é chamado automaticamente ao sair do bloco 'with' com um erro
                    raise # Re-lança a exceção para interromper o script

    except Exception as e:
        print(f"\n!!!! OCORREU UM ERRO GERAL !!!!")
        print(f"Detalhes do erro: {e}")

    print("\n--- PROCESSAMENTO FINALIZADO ---")

if __name__ == "__main__":
    main()