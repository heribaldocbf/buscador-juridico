import streamlit as st
from pathlib import Path
import pandas as pd
import math

# --- CONFIGURAÇÕES ---
PASTA_RAIZ = Path("G:/Meu Drive/Direito/Informativos")
ARQUIVO_INDICE_INFORMATIVOS = "indice_dados.csv"
ARQUIVO_TEMAS_STJ = "relatorio.csv"
ARQUIVO_TEMAS_STF = "RepercussaoGeral.csv"
ITEMS_PER_PAGE = 25

st.set_page_config(page_title="Hub Jurídico", page_icon="⚖️", layout="wide")

# --- FUNÇÕES DE CALLBACK PARA SINCRONIZAR PAGINAÇÃO ---
def sync_page_informativos():
    if 'page_informativos' in st.session_state and 'page_informativos_bottom' in st.session_state:
        if st.session_state.page_informativos != st.session_state.page_informativos_bottom:
             st.session_state.page_informativos_bottom = st.session_state.page_informativos

def sync_page_informativos_bottom():
    if 'page_informativos' in st.session_state and 'page_informativos_bottom' in st.session_state:
        if st.session_state.page_informativos != st.session_state.page_informativos_bottom:
             st.session_state.page_informativos = st.session_state.page_informativos_bottom

def sync_page_stf():
    if 'page_stf' in st.session_state and 'page_stf_bottom' in st.session_state:
        if st.session_state.page_stf != st.session_state.page_stf_bottom:
             st.session_state.page_stf_bottom = st.session_state.page_stf

def sync_page_stf_bottom():
    if 'page_stf' in st.session_state and 'page_stf_bottom' in st.session_state:
        if st.session_state.page_stf != st.session_state.page_stf_bottom:
             st.session_state.page_stf = st.session_state.page_stf_bottom

def sync_page_stj():
    if 'page_stj' in st.session_state and 'page_stj_bottom' in st.session_state:
        if st.session_state.page_stj != st.session_state.page_stj_bottom:
             st.session_state.page_stj_bottom = st.session_state.page_stj

def sync_page_stj_bottom():
    if 'page_stj' in st.session_state and 'page_stj_bottom' in st.session_state:
        if st.session_state.page_stj != st.session_state.page_stj_bottom:
             st.session_state.page_stj = st.session_state.page_stj_bottom

# --- FUNÇÕES DE CARREGAMENTO DE DADOS ---
@st.cache_data
def carregar_dados_informativos():
    caminho = Path(ARQUIVO_INDICE_INFORMATIVOS)
    if caminho.exists():
        df = pd.read_csv(caminho)
        if 'arquivo_fonte' in df.columns:
            df['num_inf'] = df['arquivo_fonte'].str.extract(r'(\d+)').astype(int)
            colunas_busca = ['disciplina', 'assunto', 'tese', 'orgao']
            df['busca'] = df[colunas_busca].fillna('').astype(str).apply(' '.join, axis=1).str.lower()
        return df
    return None

@st.cache_data
def carregar_dados_stf():
    caminho = PASTA_RAIZ / ARQUIVO_TEMAS_STF
    if not caminho.exists(): return None
    try:
        df = pd.read_csv(caminho, encoding='utf-8')
    except:
        df = pd.read_csv(caminho, sep=';', encoding='latin1')
    colunas_stf_busca = ["Tema", "Tese", "Leading Case", "Título", "Situação do Tema"]
    df['busca'] = df[colunas_stf_busca].fillna('').astype(str).apply(' '.join, axis=1).str.lower()
    return df

@st.cache_data
def carregar_dados_stj():
    caminho = PASTA_RAIZ / ARQUIVO_TEMAS_STJ
    if not caminho.exists(): return None
    try:
        df = pd.read_csv(caminho, sep=';', encoding='utf-8')
    except:
        df = pd.read_csv(caminho, sep=';', encoding='latin1')
    colunas_stj_busca = ["Tema", "Tese Firmada", "Processo", "Ramo do direito", "Situação do Tema"]
    df['busca'] = df[colunas_stj_busca].fillna('').astype(str).apply(' '.join, axis=1).str.lower()
    return df

# --- FUNÇÕES AUXILIARES DE EXIBIÇÃO ---
def exibir_item_informativo_agrupado(row):
    try:
        assunto_val = row.get('assunto', 'N/A')
        tese_val = row.get('tese', 'N/A')
        assunto_str = str(assunto_val) if pd.notna(assunto_val) else ""
        tese_str = str(tese_val) if pd.notna(tese_val) else ""
        arquivo_pdf = row['arquivo_fonte'].replace('.docx', '.pdf')
        full_path = PASTA_RAIZ / row['orgao'] / arquivo_pdf
        file_url = full_path.as_uri()
        link_html = f'<a href="{file_url}" target="_blank">{arquivo_pdf}</a>'
        
        st.markdown(f"**ASSUNTO:** {assunto_str.upper()}")
        st.markdown(f"**TESE:** {tese_str} em {link_html} **({row['orgao']})**", unsafe_allow_html=True)
        st.markdown("---")
    except Exception as e:
        st.markdown(f"**ERRO NA FORMATAÇÃO:** {e}")

def exibir_item_stj_agrupado(row):
    st.markdown(f"**TEMA:** {row.get('Tema', 'N/A')}")
    st.markdown(f"**TESE FIRMADA:** {row.get('Tese Firmada', 'N/A')}")
    with st.expander("Ver mais detalhes"):
        colunas_principais_stj = ["Tema", "Ramo do direito", "Tese Firmada"]
        colunas_todas_stj = ["Processo", "Situação do Tema", "Trânsito em Julgado", "Acórdão Publicado em"]
        for col in colunas_todas_stj:
            if col in row and pd.notna(row[col]):
                st.markdown(f"**{col}:** {row[col]}")
    st.markdown("---")

# --- INTERFACE PRINCIPAL ---
st.sidebar.title("Menu de Navegação")
pagina_selecionada = st.sidebar.radio("Escolha a ferramenta:", ["Navegador de Informativos", "Pesquisa de Temas (STF/STJ)", "Súmulas"])

# --- MÓDULO 1: NAVEGADOR DE INFORMATIVOS ---
if pagina_selecionada == "Navegador de Informativos":
    st.title("📚 Navegador de Índices Jurídicos")
    df_indice = carregar_dados_informativos()
    if df_indice is None:
        st.error(f"Arquivo de índice '{ARQUIVO_INDICE_INFORMATIVOS}' não encontrado.")
    else:
        st.header("Selecione os Filtros")
        # ... (código dos filtros do navegador de informativos) ...
        orgao_selecionado_cat = "Todos"
        disciplina_selecionada_cat = "Todos"
        assunto_selecionado_cat = "Todos"

        st.subheader("Filtrar por um Informativo Específico")
        col_org_inf, col_inf_select = st.columns(2)
        with col_org_inf:
            orgao_para_filtro_arquivo = st.radio("Escolha o Órgão:", options=["STF", "STJ"], horizontal=True, key="orgao_inf")
        with col_inf_select:
            informativos_disponiveis = ["Nenhum"]
            if orgao_para_filtro_arquivo:
                df_orgao_especifico = df_indice[df_indice['orgao'] == orgao_para_filtro_arquivo]
                informativos_disponiveis += sorted(df_orgao_especifico['arquivo_fonte'].str.replace('.docx', '.pdf').unique())
            informativo_selecionado = st.selectbox("Escolha o Informativo:", options=informativos_disponiveis, key="inf_select")

        disciplina_selecionada_dentro_inf = "Todas"
        assunto_selecionado_dentro_inf = "Todos"
        if informativo_selecionado != "Nenhum":
            st.markdown("##### Filtrar conteúdo dentro do informativo selecionado:")
            df_arquivo_selecionado = df_indice[df_indice['arquivo_fonte'] == informativo_selecionado.replace('.pdf', '.docx')]
            col_disc_inf, col_ass_inf = st.columns(2)
            with col_disc_inf:
                disciplinas_no_arquivo = ["Todas"] + sorted(df_arquivo_selecionado['disciplina'].unique())
                disciplina_selecionada_dentro_inf = st.selectbox("Disciplina:", options=disciplinas_no_arquivo, key="disc_dentro_inf")
            with col_ass_inf:
                assuntos_no_arquivo = ["Todos"]
                if disciplina_selecionada_dentro_inf != "Todas":
                    assuntos_no_arquivo += sorted(df_arquivo_selecionado[df_arquivo_selecionado['disciplina'] == disciplina_selecionada_dentro_inf]['assunto'].unique())
                assunto_selecionado_dentro_inf = st.selectbox("Assunto:", options=assuntos_no_arquivo, key="ass_dentro_inf")
        else:
            st.markdown("---")
            st.subheader("Ou Navegue por Categoria")
            col1, col2, col3 = st.columns(3)
            with col1:
                orgaos = ["Todos"] + sorted(df_indice['orgao'].unique())
                orgao_selecionado_cat = st.selectbox("Órgão:", options=orgaos, key="orgao_cat")
            with col2:
                df_filtrado1 = df_indice[df_indice['orgao'] == orgao_selecionado_cat] if orgao_selecionado_cat != "Todos" else df_indice
                disciplinas = ["Todas"] + sorted(df_filtrado1['disciplina'].unique())
                disciplina_selecionada_cat = st.selectbox("Disciplina:", options=disciplinas, key="disc_cat")
            with col3:
                df_filtrado2 = df_filtrado1[df_filtrado1['disciplina'] == disciplina_selecionada_cat] if disciplina_selecionada_cat != "Todas" else df_filtrado1
                assuntos = ["Todos"] + sorted(df_filtrado2['assunto'].unique())
                assunto_selecionado_cat = st.selectbox("Assunto:", options=assuntos, key="assunto_cat")
            
            st.subheader("Ou Busque por Palavra-Chave")
            termo_busca_informativos = st.text_input("Buscar por (Ctrl+F):", key="busca_informativos")

        st.markdown("---")
        if st.button("Buscar / Aplicar Filtros", type="primary"):
            df_final = pd.DataFrame()
            if informativo_selecionado != "Nenhum":
                df_final = df_indice[df_indice['arquivo_fonte'] == informativo_selecionado.replace('.pdf', '.docx')]
                if disciplina_selecionada_dentro_inf != "Todas": df_final = df_final[df_final['disciplina'] == disciplina_selecionada_dentro_inf]
                if assunto_selecionado_dentro_inf != "Todos": df_final = df_final[df_final['assunto'] == assunto_selecionado_dentro_inf]
                st.session_state.df_filtrado = df_final
                st.session_state.titulo_resultados = f"Conteúdo do Informativo: {informativo_selecionado}"
            else:
                df_final = df_indice
                if orgao_selecionado_cat != "Todos": df_final = df_final[df_final['orgao'] == orgao_selecionado_cat]
                if disciplina_selecionada_cat != "Todas": df_final = df_final[df_final['disciplina'] == disciplina_selecionada_cat]
                if assunto_selecionado_cat != "Todos": df_final = df_final[df_final['assunto'] == assunto_selecionado_cat]
                
                if 'termo_busca_informativos' in locals() and termo_busca_informativos:
                    df_final = df_final[df_final['busca'].str.contains(termo_busca_informativos.lower(), na=False)]

                st.session_state.df_filtrado = df_final
                st.session_state.titulo_resultados = "Resultados da Busca:"
            
            st.session_state.page_informativos = 1
            st.session_state.page_informativos_bottom = 1
            st.session_state.informativo_selecionado = informativo_selecionado
            st.session_state.orgao_selecionado_cat = orgao_selecionado_cat
            st.session_state.disciplina_selecionada_cat = disciplina_selecionada_cat

        if 'df_filtrado' in st.session_state and not st.session_state.df_filtrado.empty:
            df_final = st.session_state.df_filtrado
            st.subheader(st.session_state.titulo_resultados)
            
            st.subheader("Opções de Ordenação")
            
            sort_options = ["Padrão (Disciplina, Assunto)"]
            if st.session_state.informativo_selecionado == "Nenhum":
                if st.session_state.orgao_selecionado_cat == "Todos": sort_options.append("Órgão (A-Z)")
                sort_options.append("Informativo (Crescente)")
                sort_options.append("Informativo (Decrescente)")
            
            sort_by = st.selectbox("Ordenar por:", options=sort_options)
            
            if sort_by == "Padrão (Disciplina, Assunto)":
                df_final = df_final.sort_values(by=['disciplina', 'assunto'])
            elif "Informativo" in sort_by:
                ascending_order = [True, (sort_by == "Informativo (Crescente)")]
                df_final = df_final.sort_values(by=['disciplina', 'num_inf'], ascending=ascending_order)
            elif sort_by == "Órgão (A-Z)":
                df_final = df_final.sort_values(by=['disciplina', 'orgao', 'assunto'])

            total_items = len(df_final)
            total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1
            
            page_number = st.number_input('Página', min_value=1, max_value=total_pages, step=1, key='page_informativos', on_change=sync_page_informativos)
            st.write(f"Mostrando página {page_number} de {total_pages} ({total_items} resultados).")
            
            start_index = (page_number - 1) * ITEMS_PER_PAGE
            end_index = start_index + ITEMS_PER_PAGE
            df_pagina = df_final.iloc[start_index:end_index]
            st.divider()
            
            if not df_pagina.empty:
                grupos = df_pagina.groupby('disciplina', sort=False)
                for disciplina, grupo_df in grupos:
                    st.subheader(f"DISCIPLINA: {disciplina.upper()}")
                    with st.container(border=True):
                        for _, row in grupo_df.iterrows():
                            exibir_item_informativo_agrupado(row)

            if total_pages > 1:
                st.number_input('Página', min_value=1, max_value=total_pages, step=1, key='page_informativos_bottom', on_change=sync_page_informativos_bottom)

# --- MÓDULO 2: PESQUISA DE TEMAS (STF/STJ) ---
elif pagina_selecionada == "Pesquisa de Temas (STF/STJ)":
    st.title("🔎 Pesquisa de Temas de Repercussão Geral e Repetitivos")
    tab_stf, tab_stj = st.tabs(["**STF - Repercussão Geral**", "**STJ - Temas Repetitivos**"])

    with tab_stf:
        df_stf = carregar_dados_stf()
        if df_stf is not None:
            st.header("Pesquisar Temas do STF")
            termo_busca_stf = st.text_input("Buscar por (Ctrl+F):", key="busca_stf")
            df_resultado_stf = df_stf
            if termo_busca_stf:
                df_resultado_stf = df_stf[df_stf['busca'].str.contains(termo_busca_stf.lower(), na=False)]
            
            total_items_stf = len(df_resultado_stf)
            total_pages_stf = math.ceil(total_items_stf / ITEMS_PER_PAGE) if total_items_stf > 0 else 1

            if 'page_stf' not in st.session_state: st.session_state.page_stf = 1
            if 'page_stf_bottom' not in st.session_state: st.session_state.page_stf_bottom = 1

            page_number_stf = st.number_input('Página', min_value=1, max_value=total_pages_stf, step=1, key='page_stf', on_change=sync_page_stf)
            st.write(f"Mostrando página {page_number_stf} de {total_pages_stf} ({total_items_stf} temas encontrados).")
            
            start_index_stf = (page_number_stf - 1) * ITEMS_PER_PAGE
            end_index_stf = start_index_stf + ITEMS_PER_PAGE
            df_pagina_stf = df_resultado_stf.iloc[start_index_stf:end_index_stf]
            st.divider()
            
            for _, row in df_pagina_stf.iterrows():
                st.markdown(f"**Tema:** {row.get('Tema', 'N/A')}")
                st.markdown(f"**Título:** {row.get('Título', 'N/A')}")
                st.markdown(f"**Tese:** {row.get('Tese', 'N/A')}")
                with st.expander("Ver mais detalhes"):
                    colunas_principais_stf = ["Tema", "Título", "Tese"]
                    colunas_todas_stf = ["Tema", "Tese", "Leading Case", "Título", "Situação do Tema", "Data do Julgamento", "Data da Tese"]
                    for col in colunas_todas_stf:
                        if col not in colunas_principais_stf and col in row and pd.notna(row[col]):
                            st.markdown(f"**{col}:** {row[col]}")
                st.divider()

            if total_pages_stf > 1:
                st.number_input('Página', min_value=1, max_value=total_pages_stf, step=1, key='page_stf_bottom', on_change=sync_page_stf_bottom)

        else:
            st.error(f"Arquivo '{ARQUIVO_TEMAS_STF}' não encontrado.")

    with tab_stj:
        df_stj = carregar_dados_stj()
        if df_stj is not None:
            st.header("Pesquisar Temas do STJ")
            ramos_disponiveis = ["Todos"] + sorted(df_stj['Ramo do direito'].dropna().unique())
            ramo_selecionado = st.selectbox("Filtrar por Ramo do Direito:", options=ramos_disponiveis, key="ramo_stj")
            termo_busca_stj = st.text_input("Buscar por (Ctrl+F):", key="busca_stj")
            
            df_resultado_stj = df_stj
            if ramo_selecionado != "Todos":
                df_resultado_stj = df_resultado_stj[df_resultado_stj['Ramo do direito'] == ramo_selecionado]
            if termo_busca_stj:
                df_resultado_stj = df_resultado_stj[df_resultado_stj['busca'].str.contains(termo_busca_stj.lower(), na=False)]
            
            # Ordena para garantir que o groupby funcione corretamente
            df_resultado_stj = df_resultado_stj.sort_values(by=['Ramo do direito', 'Tema'])

            total_items_stj = len(df_resultado_stj)
            total_pages_stj = math.ceil(total_items_stj / ITEMS_PER_PAGE) if total_items_stj > 0 else 1

            if 'page_stj' not in st.session_state: st.session_state.page_stj = 1
            if 'page_stj_bottom' not in st.session_state: st.session_state.page_stj_bottom = 1

            page_number_stj = st.number_input('Página', min_value=1, max_value=total_pages_stj, step=1, key='page_stj', on_change=sync_page_stj)
            st.write(f"Mostrando página {page_number_stj} de {total_pages_stj} ({total_items_stj} temas encontrados).")
            
            start_index_stj = (page_number_stj - 1) * ITEMS_PER_PAGE
            end_index_stj = start_index_stj + ITEMS_PER_PAGE
            df_pagina_stj = df_resultado_stj.iloc[start_index_stj:end_index_stj]
            st.divider()

            # --- NOVA LÓGICA DE EXIBIÇÃO COM GROUPBY PARA O STJ ---
            if not df_pagina_stj.empty:
                grupos_stj = df_pagina_stj.groupby('Ramo do direito', sort=False)
                for ramo, grupo_df in grupos_stj:
                    st.subheader(f"RAMO DO DIREITO: {ramo.upper()}")
                    with st.container(border=True):
                        for _, row in grupo_df.iterrows():
                            exibir_item_stj_agrupado(row)
            
            if total_pages_stj > 1:
                st.number_input('Página', min_value=1, max_value=total_pages_stj, step=1, key='page_stj_bottom', on_change=sync_page_stj_bottom)

        else:
            st.error(f"Arquivo '{ARQUIVO_TEMAS_STJ}' não encontrado.")

# --- MÓDULO 3: SÚMULAS ---
elif pagina_selecionada == "Súmulas":
    st.title("🔗 Links para Pesquisa de Súmulas")
    st.markdown("---")
    st.subheader("Tribunais Superiores")
    st.markdown("#### [⚖️ STF - Supremo Tribunal Federal](https://portal.stf.jus.br/jurisprudencia/aplicacaosumula.asp)", unsafe_allow_html=True)
    st.markdown("#### [⚖️ STJ - Superior Tribunal de Justiça](https://scon.stj.jus.br/SCON/sumstj/)", unsafe_allow_html=True)
    st.markdown("#### [⚖️ TST - Tribunal Superior do Trabalho](https://jurisprudencia.tst.jus.br/)", unsafe_allow_html=True)