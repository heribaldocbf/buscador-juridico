import pandas as pd
from sqlalchemy import create_engine
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

# --- CONFIGURAÇÕES ---
# !!!! IMPORTANTE: Substitua a linha abaixo pela sua Connection String do Supabase !!!!
DB_CONNECTION_STRING = "postgresql://postgres.rxmctzxlemptfaydemkw:Badinho201.@aws-1-sa-east-1.pooler.supabase.com:5432/postgres"
NOME_ARQUIVO_TXT = "indice_analitico.txt"
NOME_ARQUIVO_XLSX = "indice_analitico.xlsx"

def extrair_indice_do_banco():
    """
    Conecta ao banco de dados, extrai os dados da tabela 'informativos'
    e retorna um DataFrame do Pandas.
    """
    print("Conectando ao banco de dados...")
    try:
        engine = create_engine(DB_CONNECTION_STRING)
        df = pd.read_sql_query("SELECT orgao, disciplina, assunto, arquivo_fonte FROM informativos", engine)
        print("Dados extraídos com sucesso!")
        return df
    except Exception as e:
        print(f"\n!!!! ERRO AO CONECTAR OU EXTRAIR DADOS !!!!")
        print(f"Detalhes do erro: {e}")
        return None

def gerar_arquivo_txt(df):
    """Gera um arquivo de texto formatado com o índice."""
    if df is None or df.empty: return
    print(f"Gerando o arquivo '{NOME_ARQUIVO_TXT}'...")
    
    df['num_inf'] = df['arquivo_fonte'].str.extract(r'(\d+)').fillna('0')

    with open(NOME_ARQUIVO_TXT, 'w', encoding='utf-8') as f:
        f.write("ÍNDICE ANALÍTICO DE DISCIPLINAS E ASSUNTOS POR ÓRGÃO\n")
        f.write("====================================================\n")
        for orgao in sorted(df['orgao'].unique()):
            f.write(f"\n\n--- {orgao.upper()} ---\n")
            df_orgao = df[df['orgao'] == orgao]
            for disciplina, grupo_disciplina_df in sorted(df_orgao.groupby('disciplina')):
                f.write(f"\nDISCIPLINA: {disciplina.upper()}\n")
                assuntos_agrupados = grupo_disciplina_df.groupby('assunto')['num_inf'].unique().apply(lambda nums: sorted(list(nums), key=int))
                for assunto, numeros in sorted(assuntos_agrupados.items()):
                    numeros_str = ", ".join(map(str, numeros))
                    f.write(f"  - {assunto} (Infs. {numeros_str})\n")
    print(f"Arquivo '{NOME_ARQUIVO_TXT}' criado com sucesso.")

def gerar_arquivo_xlsx(df):
    """Gera um arquivo Excel formatado com os temas em duas colunas (STF e STJ) alinhadas por disciplina."""
    if df is None or df.empty: return
    print(f"Gerando o arquivo '{NOME_ARQUIVO_XLSX}'...")

    # Estrutura os dados: {disciplina: {'STF': {assuntos}, 'STJ': {assuntos}}}
    disciplinas_dict = {}
    for _, row in df.iterrows():
        disciplina = row['disciplina']
        orgao = row['orgao']
        assunto = row['assunto']
        if disciplina not in disciplinas_dict:
            disciplinas_dict[disciplina] = {'STF': set(), 'STJ': set()}
        if orgao in ['STF', 'STJ']:
            disciplinas_dict[disciplina][orgao].add(assunto)
    
    # Cria o arquivo Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Índice Comparativo"

    # Estilos
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    disciplina_font = Font(bold=True, color="4F81BD")
    
    # Cabeçalho
    ws['A1'] = 'STF'
    ws['B1'] = 'STJ'
    ws['A1'].font = header_font
    ws['A1'].fill = header_fill
    ws['B1'].font = header_font
    ws['B1'].fill = header_fill

    # Preenche os dados
    current_row = 2
    sorted_disciplinas = sorted(disciplinas_dict.keys())

    for disciplina in sorted_disciplinas:
        temas_stf = sorted(list(disciplinas_dict[disciplina]['STF']))
        temas_stj = sorted(list(disciplinas_dict[disciplina]['STJ']))

        # Só processa se houver temas em pelo menos um dos órgãos
        if temas_stf or temas_stj:
            # Escreve o título da disciplina
            cell_stf = ws.cell(row=current_row, column=1, value=disciplina.upper())
            cell_stf.font = disciplina_font
            cell_stj = ws.cell(row=current_row, column=2, value=disciplina.upper())
            cell_stj.font = disciplina_font
            current_row += 1

            # Escreve os temas, alinhando as linhas
            max_len = max(len(temas_stf), len(temas_stj))
            for i in range(max_len):
                if i < len(temas_stf):
                    ws.cell(row=current_row + i, column=1, value=temas_stf[i])
                if i < len(temas_stj):
                    ws.cell(row=current_row + i, column=2, value=temas_stj[i])
            
            # Atualiza o contador de linha para a próxima disciplina
            current_row += max_len + 1 # Adiciona uma linha em branco

    # Ajusta a largura das colunas
    ws.column_dimensions['A'].width = 60
    ws.column_dimensions['B'].width = 60

    # Salva o arquivo
    wb.save(NOME_ARQUIVO_XLSX)
    print(f"Arquivo '{NOME_ARQUIVO_XLSX}' criado com sucesso.")


if __name__ == "__main__":
    dataframe_informativos = extrair_indice_do_banco()
    if dataframe_informativos is not None:
        # Garante que colunas essenciais não tenham valores nulos antes de processar
        dataframe_informativos.dropna(subset=['orgao', 'disciplina', 'assunto', 'arquivo_fonte'], inplace=True)
        
        gerar_arquivo_txt(dataframe_informativos)
        print("-" * 20)
        gerar_arquivo_xlsx(dataframe_informativos)