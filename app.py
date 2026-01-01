import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import math
import urllib.parse
import streamlit.components.v1 as components
import time
import re

# --- 1. CONFIGURAÇÕES GERAIS ---
ITEMS_PER_PAGE = 25
st.set_page_config(page_title="Hub Jurídico", page_icon="⚖️", layout="wide")

# ==============================================================================
# ⚓ 1. ÂNCORA INVISÍVEL NO TOPO (O "ALVO" DA TECLA HOME)
# ==============================================================================
st.markdown('<div id="topo_da_pagina"></div>', unsafe_allow_html=True)

# --- 2. LÓGICA DE SALTO PARA O TOPO (SIMULAÇÃO DA TECLA HOME) ---
if 'trigger_scroll_top' not in st.session_state:
    st.session_state.trigger_scroll_top = False

if st.session_state.trigger_scroll_top:
    js = f"""
    <script>
        setTimeout(function() {{
            var topDiv = window.parent.document.getElementById("topo_da_pagina");
            if (topDiv) {{
                topDiv.scrollIntoView({{block: "start", behavior: "auto"}});
            }}
            window.parent.scrollTo(0, 0);
        }}, 100); 
    </script>
    <div id="scroll_trigger_{int(time.time())}"></div>
    """
    components.html(js, height=0)
    st.session_state.trigger_scroll_top = False

# --- FUNÇÃO DE BUSCA INTELIGENTE ---
def filtrar_dados(df, termo_busca):
    """
    Realiza busca inteligente:
    - Com aspas ("termo exato"): Busca a frase exata.
    - Sem aspas (termo livre): Busca palavras em qualquer ordem (AND).
    """
    if not termo_busca:
        return df
    
    termo_busca = termo_busca.lower().strip()
    
    # Verifica se começa e termina com aspas
    if termo_busca.startswith('"') and termo_busca.endswith('"'):
        # Busca exata (remove aspas e busca a frase literal)
        frase = termo_busca[1:-1]
        return df[df['busca'].str.contains(frase, regex=False, na=False)]
    else:
        # Busca por palavras-chave (todas as palavras devem estar presentes)
        palavras = termo_busca.split()
        mask = pd.Series([True] * len(df))
        for p in palavras:
            mask = mask & df['busca'].str.contains(p, regex=False, na=False)
        return df[mask]

# --- CONFIGURAÇÃO DE ADMINISTRAÇÃO ---
SENHA_ADMIN = "060147mae"

# Lista completa de Ramos (Sincronizada com os arquivos da pasta Temas STF)
LISTA_RAMOS_COMPLETA = sorted([
    "Direito Administrativo",
    "Direito Ambiental",
    "Direito Civil",
    "Direito do Consumidor",
    "Direito do Trabalho",
    "Direito Eleitoral",
    "Direito Internacional",
    "Direito Penal",
    "Direito Penal Militar",
    "Direito Previdenciário",
    "Direito Processual Civil e do Trabalho",
    "Direito Processual Penal",
    "Direito Tributário",
    "Direito à Educação",
    "Registros Públicos",
    "Não Classificado",
    "Outros"
])

# --- 3. INICIALIZAÇÃO DO ESTADO DA SESSÃO ---
if 'df_filtrado' not in st.session_state: st.session_state.df_filtrado = pd.DataFrame()
if 'titulo_resultados' not in st.session_state: st.session_state.titulo_resultados = "Use os filtros acima e clique em buscar."
if 'filtros_ativos' not in st.session_state: st.session_state.filtros_ativos = ("Nenhum", "Todos")

# Paginação
if 'page_informativos_top' not in st.session_state: st.session_state.page_informativos_top = 1
if 'page_informativos_bottom' not in st.session_state: st.session_state.page_informativos_bottom = 1
if 'page_stf_top' not in st.session_state: st.session_state.page_stf_top = 1
if 'page_stf_bottom' not in st.session_state: st.session_state.page_stf_bottom = 1
if 'page_stj_top' not in st.session_state: st.session_state.page_stj_top = 1
if 'page_stj_bottom' not in st.session_state: st.session_state.page_stj_bottom = 1

if 'data_needs_refresh' not in st.session_state: st.session_state.data_needs_refresh = False

# --- 4. FUNÇÃO DE SINCRONIZAÇÃO ---
def sync_page_widgets(source_key, target_key):
    if source_key in st.session_state and target_key in st.session_state:
        st.session_state[target_key] = st.session_state[source_key]
        if "bottom" in source_key:
            st.session_state.trigger_scroll_top = True

# --- 5. CONEXÃO COM O BANCO DE DADOS ---
@st.cache_resource
def init_connection():
    try:
        return create_engine(st.secrets["DB_CONNECTION_STRING"])
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

engine = init_connection()

# --- FUNÇÕES DE UPDATE E LEITURA (ADMIN) ---
def atualizar_ramo_stf(tema_id, novo_ramo):
    if engine is None: return False
    try:
        with engine.begin() as conn:
            try:
                stmt = text('UPDATE temas_stf SET "Ramo do Direito" = :ramo, "data_ultima_alteracao" = NOW() WHERE "Tema" = :tema')
                conn.execute(stmt, {"ramo": novo_ramo, "tema": tema_id})
            except:
                stmt = text('UPDATE temas_stf SET "Ramo do Direito" = :ramo WHERE "Tema" = :tema')
                conn.execute(stmt, {"ramo": novo_ramo, "tema": tema_id})
                
        st.cache_data.clear()
        st.session_state.data_needs_refresh = True
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar banco: {e}")
        return False

def get_ultimo_tema_editado():
    if engine is None: return None
    try:
        with engine.connect() as conn:
            stmt = text('SELECT "Tema" FROM temas_stf WHERE "data_ultima_alteracao" IS NOT NULL ORDER BY "data_ultima_alteracao" DESC LIMIT 1')
            result = conn.execute(stmt).fetchone()
            return result[0] if result else None
    except:
        return None

# --- 6. FUNÇÕES DE CARREGAMENTO DE DADOS (OTIMIZADAS) ---

# OTIMIZAÇÃO: Cache aumentado para 24h (86400s)
@st.cache_data(ttl=86400)
def carregar_dados_informativos():
    if engine is None: return None
    try:
        # OTIMIZAÇÃO: Selecionando apenas colunas usadas
        query = """
        SELECT arquivo_fonte, disciplina, assunto, tese, orgao 
        FROM informativos
        """
        df = pd.read_sql_query(query, engine)
        
        df['num_inf'] = df['arquivo_fonte'].str.extract(r'(\d+)').fillna(0).astype(int)
        
        colunas_busca = ['disciplina', 'assunto', 'tese', 'orgao']
        for col in colunas_busca:
            if col not in df.columns: df[col] = ''
        
        df['busca'] = df[colunas_busca].fillna('').astype(str).agg(' '.join, axis=1).str.lower()
        return df
    except Exception as e:
        st.error(f"Não foi possível carregar os dados dos informativos: {e}")
        return None

# OTIMIZAÇÃO: Cache aumentado para 24h
@st.cache_data(ttl=86400)
def carregar_dados_stf():
    if engine is None: return None
    try:
        # OTIMIZAÇÃO: Removida a coluna 'Descrição' e outras não usadas
        query = """
        SELECT "Tema", "Título", "Tese", "Leading Case", "Situação do Tema", "Ramo do Direito", "Data do Julgamento"
        FROM temas_stf
        """
        df = pd.read_sql_query(query, engine)
        
        df.columns = [col.replace('"', '') for col in df.columns]
        df['Tema'] = pd.to_numeric(df['Tema'], errors='coerce').fillna(0).astype(int)
        
        if 'Ramo do Direito' not in df.columns: 
            df['Ramo do Direito'] = 'Não Classificado'
        else:
            df['Ramo do Direito'] = df['Ramo do Direito'].fillna('Não Classificado')

        colunas_stf_busca = ["Tema", "Tese", "Leading Case", "Título", "Situação do Tema", "Ramo do Direito"]
        # Filtra apenas colunas que realmente vieram no select
        existentes = [c for c in colunas_stf_busca if c in df.columns]
        
        df['Tese'] = df['Tese'].fillna('')
        df['busca'] = df[existentes].fillna('').astype(str).agg(' '.join, axis=1).str.lower()
        return df
    except Exception as e:
        st.error(f"Não foi possível carregar os dados do STF: {e}")
        return None

# OTIMIZAÇÃO: Cache aumentado para 24h
@st.cache_data(ttl=86400)
def carregar_dados_stj():
    if engine is None: return None
    try:
        # OTIMIZAÇÃO: Redução drástica de colunas (de 40 para 7)
        query = """
        SELECT "Tema", "Tese Firmada", "Processo", "Ramo do direito", "Situação do Tema", "Questão submetida a julgamento", "Trânsito em Julgado"
        FROM temas_stj
        """
        df = pd.read_sql_query(query, engine)
        
        df.columns = [col.replace('"', '') for col in df.columns]
        df['Tema'] = pd.to_numeric(df['Tema'], errors='coerce').fillna(0).astype(int)

        colunas_stj_busca = ["Tema", "Tese Firmada", "Processo", "Ramo do direito", "Situação do Tema", "Questão submetida a julgamento"]
        existentes = [c for c in colunas_stj_busca if c in df.columns]
            
        if 'Tese Firmada' not in df.columns: df['Tese Firmada'] = ''
        df['Tese Firmada'] = df['Tese Firmada'].fillna('')
        
        df['busca'] = df[existentes].fillna('').astype(str).agg(' '.join, axis=1).str.lower()
        return df
    except Exception as e:
        st.error(f"Não foi possível carregar os dados do STJ: {e}")
        return None

def exibir_item_informativo_agrupado(row):
    try:
        assunto_str = str(row.get('assunto', 'N/A')) if pd.notna(row.get('assunto')) else ""
        tese_str = str(row.get('tese', 'N/A')) if pd.notna(row.get('tese')) else ""
        arquivo_original = row.get('arquivo_fonte', 'N/A')
        arquivo_pdf = arquivo_original.replace('.docx', '.pdf')
        orgao = row.get('orgao', 'N/A')
        termo_busca_base = arquivo_original.replace('.docx', '')
        termo_de_busca = f"{termo_busca_base} dizer o direito"
        query_codificada = urllib.parse.quote_plus(termo_de_busca)
        google_search_url = f"https://www.google.com/search?q={query_codificada}"
        link_html = f'<a href="{google_search_url}" target="_blank">{arquivo_pdf}</a>'
        st.markdown(f"**ASSUNTO:** {assunto_str.upper()}")
        st.markdown(f"**TESE:** {tese_str} em {link_html} **({orgao})**", unsafe_allow_html=True)
        st.markdown("---")
    except Exception as e:
        st.error(f"Erro ao exibir item: {e}")

# --- 7. INTERFACE PRINCIPAL ---
st.sidebar.title("Menu de Navegação")
pagina_selecionada = st.sidebar.radio("Escolha a ferramenta:", ["Navegador de Informativos", "Pesquisa de Temas (STF/STJ)", "Súmulas"])

st.sidebar.markdown("---")
st.sidebar.markdown("🔒 **Área Administrativa**")
senha_input = st.sidebar.text_input("Senha Admin", type="password")
is_admin = senha_input == SENHA_ADMIN
if is_admin:
    st.sidebar.success("Modo Edição Ativado ✅")


# === PÁGINA 1: INFORMATIVOS ===
if pagina_selecionada == "Navegador de Informativos":
    st.title("📚 Navegador de Índices Jurídicos")
    df_indice = carregar_dados_informativos()
    
    if df_indice is None:
        st.error("Não foi possível carregar os dados dos informativos.")
    else:
        st.header("Selecione os Filtros")
        
        # --- INICIALIZAÇÃO DE VARIÁVEIS DE FILTRO ---
        orgao_selecionado_cat = "Todos"
        disciplina_selecionada_cat = "Todos"
        assunto_selecionado_cat = "Todos"
        termo_busca_informativos = ""
        
        st.subheader("Filtrar por um Informativo Específico")
        col_org_inf, col_inf_select = st.columns(2)
        with col_org_inf:
            orgao_para_filtro_arquivo = st.radio("Escolha o Órgão:", options=["STF", "STJ"], horizontal=True, key="orgao_inf")
        with col_inf_select:
            informativos_disponiveis = ["Nenhum"]
            if not df_indice.empty:
                df_orgao_especifico = df_indice[df_indice['orgao'] == orgao_para_filtro_arquivo]
                df_sorted = df_orgao_especifico.sort_values(by='num_inf', ascending=False)
                lista_ordenada = df_sorted['arquivo_fonte'].str.replace('.docx', '.pdf').unique().tolist()
                informativos_disponiveis += lista_ordenada
            informativo_selecionado = st.selectbox("Escolha o Informativo:", options=informativos_disponiveis, key="inf_select")
        
        disciplina_selecionada_dentro_inf = "Todas"
        assunto_selecionado_dentro_inf = "Todos"
        
        if informativo_selecionado != "Nenhum":
            st.markdown("##### Filtrar conteúdo dentro do informativo selecionado:")
            df_arquivo_selecionado = df_indice[df_indice['arquivo_fonte'] == informativo_selecionado.replace('.pdf', '.docx')]
            col_disc_inf, col_ass_inf = st.columns(2)
            with col_disc_inf:
                disciplinas_no_arquivo = ["Todas"] + sorted(df_arquivo_selecionado['disciplina'].dropna().unique())
                disciplina_selecionada_dentro_inf = st.selectbox("Disciplina:", options=disciplinas_no_arquivo, key="disc_dentro_inf")
            with col_ass_inf:
                assuntos_no_arquivo = ["Todos"]
                if disciplina_selecionada_dentro_inf != "Todas":
                    assuntos_no_arquivo += sorted(df_arquivo_selecionado[df_arquivo_selecionado['disciplina'] == disciplina_selecionada_dentro_inf]['assunto'].dropna().unique())
                assunto_selecionado_dentro_inf = st.selectbox("Assunto:", options=assuntos_no_arquivo, key="ass_dentro_inf")
        else:
            st.markdown("---")
            st.subheader("Ou Navegue por Categoria")
            col1, col2, col3 = st.columns(3)
            with col1:
                orgaos = ["Todos"] + sorted(df_indice['orgao'].dropna().unique())
                orgao_selecionado_cat = st.selectbox("Órgão:", options=orgaos, key="orgao_cat")
            with col2:
                df_filtrado1 = df_indice[df_indice['orgao'] == orgao_selecionado_cat] if orgao_selecionado_cat != "Todos" else df_indice
                disciplinas = ["Todas"] + sorted(df_filtrado1['disciplina'].dropna().unique())
                disciplina_selecionada_cat = st.selectbox("Disciplina:", options=disciplinas, key="disc_cat")
            with col3:
                df_filtrado2 = df_filtrado1[df_filtrado1['disciplina'] == disciplina_selecionada_cat] if disciplina_selecionada_cat != "Todos" else df_filtrado1
                assuntos = ["Todos"] + sorted(df_filtrado2['assunto'].dropna().unique())
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
            else:
                df_final = df_indice.copy()
                if orgao_selecionado_cat != "Todos": df_final = df_final[df_final['orgao'] == orgao_selecionado_cat]
                if disciplina_selecionada_cat != "Todas": df_final = df_final[df_final['disciplina'] == disciplina_selecionada_cat]
                if assunto_selecionado_cat != "Todos": df_final = df_final[df_final['assunto'] == assunto_selecionado_cat]
                
                # --- BUSCA INTELIGENTE AQUI ---
                if termo_busca_informativos:
                    df_final = filtrar_dados(df_final, termo_busca_informativos)
            
            st.session_state.df_filtrado = df_final
            st.session_state.page_informativos_top = 1
            st.session_state.page_informativos_bottom = 1
            st.session_state.titulo_resultados = "Resultados da Busca:" if informativo_selecionado == "Nenhum" else f"Conteúdo do Informativo: {informativo_selecionado}"
            st.session_state.filtros_ativos = (informativo_selecionado, orgao_selecionado_cat)
        
        st.subheader(st.session_state.titulo_resultados)
        
        if not st.session_state.df_filtrado.empty:
            df_final = st.session_state.df_filtrado
            
            # --- ORDENAÇÃO ---
            sort_options = ["Padrão (Disciplina, Assunto)"]
            info_sel, orgao_sel = st.session_state.get('filtros_ativos', ("Nenhum", "Todos"))
            if info_sel == "Nenhum":
                if orgao_sel == "Todos": sort_options.append("Órgão (A-Z)")
                sort_options.append("Informativo (Crescente)")
                sort_options.append("Informativo (Decrescente)")
            sort_by = st.selectbox("Ordenar por:", options=sort_options)
            
            if sort_by == "Padrão (Disciplina, Assunto)": df_final = df_final.sort_values(by=['disciplina', 'assunto'])
            elif "Informativo" in sort_by: df_final = df_final.sort_values(by=['disciplina', 'num_inf'], ascending=[True, (sort_by == "Informativo (Crescente)")])
            elif sort_by == "Órgão (A-Z)": df_final = df_final.sort_values(by=['disciplina', 'orgao', 'assunto'])

            # Paginação e exibição
            total_items = len(df_final)
            total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1
            
            st.number_input('Página', min_value=1, max_value=total_pages, step=1, key='page_informativos_top', on_change=sync_page_widgets, args=('page_informativos_top', 'page_informativos_bottom'))
            st.write(f"Mostrando página {st.session_state.page_informativos_top} de {total_pages} ({total_items} resultados).")
            
            start_index = (st.session_state.page_informativos_top - 1) * ITEMS_PER_PAGE
            end_index = start_index + ITEMS_PER_PAGE
            df_pagina = df_final.iloc[start_index:end_index]
            st.divider()
            
            if not df_pagina.empty:
                for disciplina, grupo_df in df_pagina.groupby('disciplina', sort=False):
                    st.subheader(f"DISCIPLINA: {disciplina.upper()}")
                    with st.container(border=True):
                        for _, row in grupo_df.iterrows():
                            exibir_item_informativo_agrupado(row)
            if total_pages > 1:
                st.session_state.page_informativos_bottom = st.session_state.page_informativos_top
                st.number_input('Página', min_value=1, max_value=total_pages, step=1, key='page_informativos_bottom', label_visibility="collapsed", on_change=sync_page_widgets, args=('page_informativos_bottom', 'page_informativos_top'))


# === PÁGINA 2: STF/STJ ===
elif pagina_selecionada == "Pesquisa de Temas (STF/STJ)":
    st.title("🔎 Pesquisa de Temas de Repercussão Geral e Repetitivos")
    tab_stf, tab_stj = st.tabs(["**STF - Repercussão Geral**", "**STJ - Temas Repetitivos**"])

    # --- ABA STF ---
    with tab_stf:
        if st.session_state.data_needs_refresh:
            st.toast("Dados atualizados com sucesso!", icon="✅")
            st.session_state.data_needs_refresh = False
            
        df_stf = carregar_dados_stf()
        
        if df_stf is not None:
            st.header("Pesquisar Temas do STF")
            
            c1, c2, c3 = st.columns([1.5, 1, 2])
            with c1:
                ramos_disponiveis_stf = ["Todos"] + sorted(df_stf['Ramo do Direito'].astype(str).unique())
                ramo_selecionado_stf = st.selectbox("Filtrar por Ramo do Direito:", options=ramos_disponiveis_stf, key="ramo_stf_filter")
            with c2:
                opcao_tese_stf = st.radio("Exibir:", ["Com tese", "Sem teses", "Todos"], index=0, key="filtro_tese_stf")
            with c3:
                termo_busca_stf = st.text_input("Buscar por (Ctrl+F):", key="busca_stf")

            df_resultado_stf = df_stf.copy()
            if ramo_selecionado_stf != "Todos":
                df_resultado_stf = df_resultado_stf[df_resultado_stf['Ramo do Direito'] == ramo_selecionado_stf]
            
            if opcao_tese_stf == "Com tese":
                df_resultado_stf = df_resultado_stf[df_resultado_stf['Tese'].str.strip() != '']
            elif opcao_tese_stf == "Sem teses":
                df_resultado_stf = df_resultado_stf[df_resultado_stf['Tese'].str.strip() == '']
            
            # --- BUSCA INTELIGENTE AQUI ---
            if termo_busca_stf:
                df_resultado_stf = filtrar_dados(df_resultado_stf, termo_busca_stf)
                if 'page_stf_top' in st.session_state:
                      st.session_state.page_stf_top = 1
                      st.session_state.page_stf_bottom = 1
            
            df_resultado_stf = df_resultado_stf.sort_values(by='Tema', ascending=False)

            total_items_stf = len(df_resultado_stf)
            total_pages_stf = math.ceil(total_items_stf / ITEMS_PER_PAGE) if total_items_stf > 0 else 1

            st.number_input('Página', min_value=1, max_value=total_pages_stf, step=1, key='page_stf_top', on_change=sync_page_widgets, args=('page_stf_top', 'page_stf_bottom'))
            
            # --- MOSTRA ÚLTIMA ALTERAÇÃO MANUAL ---
            ultimo_editado = get_ultimo_tema_editado()
            texto_ultimo = f" | 📝 **Último tema alterado manualmente: Tema {ultimo_editado}**" if ultimo_editado else ""
            st.write(f"Mostrando página {st.session_state.page_stf_top} de {total_pages_stf} ({total_items_stf} temas encontrados){texto_ultimo}")
            # --------------------------------------
            
            start_index_stf = (st.session_state.page_stf_top - 1) * ITEMS_PER_PAGE
            end_index_stf = start_index_stf + ITEMS_PER_PAGE
            df_pagina_stf = df_resultado_stf.iloc[start_index_stf:end_index_stf]
            st.divider()
            
            if not df_pagina_stf.empty:
                for _, row in df_pagina_stf.iterrows():
                    ramo_atual = row.get('Ramo do Direito', 'Não Classificado')
                    st.markdown(f"#### Tema {row.get('Tema', 'N/A')} :blue-background[{ramo_atual}]")
                    st.markdown(f"**Título:** {row.get('Título', 'N/A')}")
                    st.markdown(f"**Tese:** {row.get('Tese', 'Pendente')}")
                    
                    with st.expander("Ver detalhes / Editar Classificação"):
                        st.markdown(f"**Situação:** {row.get('Situação do Tema', '-')}")
                        st.markdown(f"**Leading Case:** {row.get('Leading Case', '-')}")
                        st.markdown(f"**Julgamento:** {row.get('Data do Julgamento', '-')}")
                        
                        if is_admin:
                            st.divider()
                            st.write("🛠️ **Admin: Alterar Classificação**")
                            with st.form(key=f"form_stf_{row['Tema']}"):
                                c_edit1, c_edit2 = st.columns([3, 1])
                                idx_inicial = 0
                                if ramo_atual in LISTA_RAMOS_COMPLETA:
                                    idx_inicial = LISTA_RAMOS_COMPLETA.index(ramo_atual)
                                
                                novo_ramo_sel = c_edit1.selectbox("Nova classificação:", 
                                                                  options=LISTA_RAMOS_COMPLETA, 
                                                                  index=idx_inicial)
                                c_edit2.write("") 
                                c_edit2.write("")
                                if c_edit2.form_submit_button("Salvar"):
                                    if novo_ramo_sel != ramo_atual:
                                        atualizar_ramo_stf(row['Tema'], novo_ramo_sel)
                                        st.rerun()
                                    else:
                                        st.info("Sem alterações.")
                        elif not is_admin:
                            st.caption("🔒 Faça login como admin na barra lateral para editar.")
                                    
                    st.divider()

            if total_pages_stf > 1:
                st.session_state.page_stf_bottom = st.session_state.page_stf_top 
                st.number_input('Página', min_value=1, max_value=total_pages_stf, step=1, key='page_stf_bottom', label_visibility="collapsed", on_change=sync_page_widgets, args=('page_stf_bottom', 'page_stf_top'))
        else:
            st.error("Não foi possível carregar os dados do STF.")

    # --- ABA STJ ---
    with tab_stj:
        df_stj = carregar_dados_stj()
        if df_stj is not None:
            st.header("Pesquisar Temas do STJ")
            
            c1, c2, c3 = st.columns([1.5, 1, 2])
            with c1:
                ramos_disponiveis = ["Todos"] + sorted(df_stj['Ramo do direito'].dropna().unique())
                ramo_selecionado = st.selectbox("Filtrar por Ramo do Direito:", options=ramos_disponiveis, key="ramo_stj")
            with c2:
                opcao_tese_stj = st.radio("Exibir:", ["Com tese", "Sem teses", "Todos"], index=0, key="filtro_tese_stj")
            with c3:
                termo_busca_stj = st.text_input("Buscar por (Ctrl+F):", key="busca_stj")
            
            df_resultado_stj = df_stj.copy()
            if ramo_selecionado != st.session_state.get("ramo_selecionado_anterior", "Todos"):
                st.session_state.page_stj_top = 1
                st.session_state.page_stj_bottom = 1
            st.session_state.ramo_selecionado_anterior = ramo_selecionado

            if ramo_selecionado != "Todos":
                df_resultado_stj = df_resultado_stj[df_resultado_stj['Ramo do direito'] == ramo_selecionado]

            if opcao_tese_stj == "Com tese":
                df_resultado_stj = df_resultado_stj[df_resultado_stj['Tese Firmada'].str.strip() != '']
            elif opcao_tese_stj == "Sem teses":
                df_resultado_stj = df_resultado_stj[df_resultado_stj['Tese Firmada'].str.strip() == '']

            # --- BUSCA INTELIGENTE AQUI ---
            if termo_busca_stj:
                df_resultado_stj = filtrar_dados(df_resultado_stj, termo_busca_stj)
                st.session_state.page_stj_top = 1
                st.session_state.page_stj_bottom = 1
            
            df_resultado_stj = df_resultado_stj.sort_values(by='Tema', ascending=False)
            
            total_items_stj = len(df_resultado_stj)
            total_pages_stj = math.ceil(total_items_stj / ITEMS_PER_PAGE) if total_items_stj > 0 else 1

            st.number_input('Página', min_value=1, max_value=total_pages_stj, step=1, key='page_stj_top', on_change=sync_page_widgets, args=('page_stj_top', 'page_stj_bottom'))
            st.write(f"Mostrando página {st.session_state.page_stj_top} de {total_pages_stj} ({total_items_stj} temas encontrados).")
            
            start_index_stj = (st.session_state.page_stj_top - 1) * ITEMS_PER_PAGE
            end_index_stj = start_index_stj + ITEMS_PER_PAGE
            df_pagina_stj = df_resultado_stj.iloc[start_index_stj:end_index_stj]
            st.divider()

            if not df_pagina_stj.empty:
                for _, row in df_pagina_stj.iterrows():
                    ramo = row.get('Ramo do direito', 'N/A')
                    st.markdown(f"#### Tema {row['Tema']} :blue-background[{ramo}]")
                    st.markdown(f"**Questão submetida a julgamento:** {row.get('Questão submetida a julgamento', '-')}")
                    st.markdown(f"**Tese Firmada:** {row.get('Tese Firmada', '-')}")
                    
                    with st.expander("Ver Detalhes"):
                        st.write(f"**Processo:** {row.get('Processo')}")
                        st.write(f"**Situação:** {row.get('Situação do Tema')}")
                        st.write(f"**Trânsito em Julgado:** {row.get('Trânsito em Julgado', '-')}")
                    st.divider()
            
            if total_pages_stj > 1:
                st.session_state.page_stj_bottom = st.session_state.page_stj_top
                st.number_input('Página', min_value=1, max_value=total_pages_stj, step=1, key='page_stj_bottom', label_visibility="collapsed", on_change=sync_page_widgets, args=('page_stj_bottom', 'page_stj_top'))

        else:
            st.error("Não foi possível carregar os dados do STJ.")

elif pagina_selecionada == "Súmulas":
    st.title("🔗 Links para Pesquisa de Súmulas")
    st.markdown("---")
    st.subheader("Tribunais Superiores")
    st.markdown("#### [⚖️ STF - Supremo Tribunal Federal](https://portal.stf.jus.br/jurisprudencia/aplicacaosumula.asp)", unsafe_allow_html=True)
    st.markdown("#### [⚖️ STJ - Superior Tribunal de Justiça](https://scon.stj.jus.br/SCON/sumstj/)", unsafe_allow_html=True)
    st.markdown("#### [⚖️ TST - Tribunal Superior do Trabalho](https://jurisprudencia.tst.jus.br/)", unsafe_allow_html=True)