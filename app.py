import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import math
import urllib.parse

# --- 1. CONFIGURAÇÕES E CONSTANTES ---
ITEMS_PER_PAGE = 25
st.set_page_config(page_title="Hub Jurídico", page_icon="⚖️", layout="wide")

# Defina sua senha de administrador aqui (ou use st.secrets)
SENHA_ADMIN = "admin123" 

# Lista completa para o Dropdown de Edição (garante que todas opções apareçam)
LISTA_RAMOS_COMPLETA = sorted([
    "Direito Administrativo", "Direito Ambiental", "Direito Civil", 
    "Direito Constitucional", "Direito do Consumidor", "Direito do Trabalho", 
    "Direito Eleitoral", "Direito Empresarial", "Direito Financeiro", 
    "Direito Internacional", "Direito Notarial e Registral", "Direito Penal", 
    "Direito Previdenciário", "Direito Processual Civil", 
    "Direito Processual Penal", "Direito Tributário", "ECA", "Outros"
])

# --- 2. ESTADO DA SESSÃO ---
if 'df_filtrado' not in st.session_state: st.session_state.df_filtrado = pd.DataFrame()
if 'page_informativos_top' not in st.session_state: st.session_state.page_informativos_top = 1
if 'page_stf_top' not in st.session_state: st.session_state.page_stf_top = 1
if 'page_stj_top' not in st.session_state: st.session_state.page_stj_top = 1
if 'data_needs_refresh' not in st.session_state: st.session_state.data_needs_refresh = False

# --- 3. CONEXÃO COM BANCO DE DADOS ---
@st.cache_resource
def init_connection():
    try:
        # Tenta pegar do secrets, se falhar tenta string direta (para testes locais)
        return create_engine(st.secrets["DB_CONNECTION_STRING"])
    except Exception as e:
        st.error(f"Erro ao conectar ao banco: {e}")
        return None

engine = init_connection()

# --- 4. FUNÇÕES DE SUPORTE ---

def sync_page_widgets(source_key, target_key):
    if source_key in st.session_state and target_key in st.session_state:
        st.session_state[target_key] = st.session_state[source_key]

def atualizar_ramo_stf(tema_id, novo_ramo):
    """Atualiza o ramo no banco de dados (Apenas Admin)"""
    if engine is None: return False
    try:
        with engine.begin() as conn:
            # Aspas em "Ramo do Direito" e "Tema" são cruciais no PostgreSQL
            stmt = text('UPDATE temas_stf SET "Ramo do Direito" = :ramo WHERE "Tema" = :tema')
            conn.execute(stmt, {"ramo": novo_ramo, "tema": tema_id})
        
        st.cache_data.clear() # Limpa cache para ver a mudança
        st.session_state.data_needs_refresh = True
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar banco: {e}")
        return False

# --- 5. CARREGAMENTO DE DADOS ---

@st.cache_data(ttl=600)
def carregar_dados_informativos():
    if engine is None: return None
    try:
        df = pd.read_sql_query("SELECT * FROM informativos", engine)
        df['num_inf'] = df['arquivo_fonte'].str.extract(r'(\d+)').fillna(0).astype(int)
        cols = ['disciplina', 'assunto', 'tese', 'orgao']
        for c in cols: 
            if c not in df.columns: df[c] = ''
        df['busca'] = df[cols].fillna('').astype(str).apply(' '.join, axis=1).str.lower()
        return df
    except: return None

@st.cache_data(ttl=600)
def carregar_dados_stf():
    if engine is None: return None
    try:
        df = pd.read_sql_query('SELECT * FROM temas_stf', engine)
        df.columns = [col.replace('"', '') for col in df.columns]
        
        # Garante coluna de Ramo
        if 'Ramo do Direito' not in df.columns: 
            df['Ramo do Direito'] = 'Não Classificado'
        else:
            df['Ramo do Direito'] = df['Ramo do Direito'].fillna('Não Classificado')

        cols_busca = ["Tema", "Tese", "Leading Case", "Título", "Ramo do Direito"]
        for c in cols_busca:
            if c not in df.columns: df[c] = ''
            
        df['busca'] = df[cols_busca].fillna('').astype(str).apply(' '.join, axis=1).str.lower()
        return df
    except Exception as e: 
        st.error(f"Erro STF: {e}")
        return None

@st.cache_data(ttl=600)
def carregar_dados_stj():
    if engine is None: return None
    try:
        df = pd.read_sql_query('SELECT * FROM temas_stj', engine)
        df.columns = [col.replace('"', '') for col in df.columns]
        
        cols_busca = ["Tema", "Tese Firmada", "Processo", "Ramo do direito"]
        for c in cols_busca:
            if c not in df.columns: df[c] = ''
            
        df['busca'] = df[cols_busca].fillna('').astype(str).apply(' '.join, axis=1).str.lower()
        return df
    except: return None

# --- 6. EXIBIÇÃO DE ITENS ---

def exibir_inf(row):
    assunto = str(row.get('assunto', ''))
    tese = str(row.get('tese', ''))
    arquivo = str(row.get('arquivo_fonte', ''))
    link_q = urllib.parse.quote_plus(f"{arquivo.replace('.docx','')} dizer o direito")
    link = f"https://www.google.com/search?q={link_q}"
    
    st.markdown(f"**ASSUNTO:** {assunto.upper()}")
    st.markdown(f"**TESE:** {tese} [Ver PDF]({link}) **({row.get('orgao','')})**")
    st.markdown("---")

def exibir_stj(row):
    st.markdown(f"**TEMA:** {row.get('Tema')}")
    st.markdown(f"**TESE:** {row.get('Tese Firmada')}")
    with st.expander("Ver Detalhes"):
        st.write(f"**Processo:** {row.get('Processo')}")
        st.write(f"**Situação:** {row.get('Situação do Tema')}")
        st.write(f"**Trânsito em Julgado:** {row.get('Trânsito em Julgado', '-')}")
    st.markdown("---")

# --- 7. INTERFACE PRINCIPAL ---

# Barra Lateral (Menu e Login)
st.sidebar.title("Menu")
pagina = st.sidebar.radio("Navegar:", ["Informativos", "Temas STF/STJ", "Súmulas"])

st.sidebar.markdown("---")
st.sidebar.markdown("🔒 **Área Administrativa**")
senha_input = st.sidebar.text_input("Senha Admin", type="password", help="Digite a senha para habilitar edição.")
is_admin = senha_input == SENHA_ADMIN

if is_admin:
    st.sidebar.success("Modo Edição Ativado! ✅")
    st.sidebar.info("Você agora pode alterar a classificação dos temas do STF.")

# --- PÁGINA 1: INFORMATIVOS ---
if pagina == "Informativos":
    st.title("📚 Navegador de Informativos")
    df = carregar_dados_informativos()
    
    if df is not None:
        c1, c2 = st.columns([1, 2])
        orgao_filtro = c1.selectbox("Órgão", ["Todos", "STF", "STJ"])
        busca = c2.text_input("Buscar Informativos:")
        
        df_res = df.copy()
        if orgao_filtro != "Todos": df_res = df_res[df_res['orgao'] == orgao_filtro]
        if busca: df_res = df_res[df_res['busca'].str.contains(busca.lower(), na=False)]
        
        # Ordenação
        df_res = df_res.sort_values(by=['num_inf', 'disciplina'], ascending=[False, True])
        
        # Paginação
        total = len(df_res)
        paginas = max(1, math.ceil(total / ITEMS_PER_PAGE))
        p_atual = st.number_input("Página", 1, paginas, key="p_inf", on_change=sync_page_widgets, args=('p_inf', 'p_inf_bottom'))
        st.caption(f"{total} resultados encontrados.")
        
        inicio = (p_atual - 1) * ITEMS_PER_PAGE
        fatia = df_res.iloc[inicio : inicio + ITEMS_PER_PAGE]
        
        st.divider()
        for _, row in fatia.iterrows():
            exibir_inf(row)
            
        if paginas > 1:
            st.number_input("Página", 1, paginas, key="p_inf_bottom", label_visibility="collapsed", on_change=sync_page_widgets, args=('p_inf_bottom', 'p_inf'))

# --- PÁGINA 2: TEMAS STF/STJ ---
elif pagina == "Temas STF/STJ":
    st.title("🔎 Pesquisa de Temas Repetitivos")
    tab_stf, tab_stj = st.tabs(["**STF - Repercussão Geral**", "**STJ - Repetitivos**"])
    
    # === ABA STF ===
    with tab_stf:
        if st.session_state.data_needs_refresh:
            st.toast("Dados atualizados com sucesso!", icon="✅")
            st.session_state.data_needs_refresh = False
            
        df_stf = carregar_dados_stf()
        
        if df_stf is not None:
            # Filtros STF
            c1, c2 = st.columns([1, 2])
            # Pega ramos existentes no banco + opção 'Todos'
            ramos_no_db = sorted(df_stf['Ramo do Direito'].astype(str).unique())
            ramo_filtro = c1.selectbox("Filtrar por Ramo (STF):", ["Todos"] + ramos_no_db)
            busca_stf = c2.text_input("Buscar Tema STF (Ctrl+F):")
            
            # Aplica Filtros
            res_stf = df_stf.copy()
            if ramo_filtro != "Todos": res_stf = res_stf[res_stf['Ramo do Direito'] == ramo_filtro]
            if busca_stf: res_stf = res_stf[res_stf['busca'].str.contains(busca_stf.lower(), na=False)]
            
            # Ordenação
            res_stf = res_stf.sort_values(by=['Ramo do Direito', 'Tema'], ascending=[True, False])
            
            # Paginação STF
            total_stf = len(res_stf)
            pgs_stf = max(1, math.ceil(total_stf / ITEMS_PER_PAGE))
            p_stf = st.number_input("Página", 1, pgs_stf, key="pstf", on_change=sync_page_widgets, args=('pstf', 'pstf_b'))
            st.write(f"Mostrando página {p_stf} de {pgs_stf} ({total_stf} temas).")
            
            inicio_stf = (p_stf - 1) * ITEMS_PER_PAGE
            fatia_stf = res_stf.iloc[inicio_stf : inicio_stf + ITEMS_PER_PAGE]
            
            st.divider()
            
            # Loop de Exibição STF
            if not fatia_stf.empty:
                for _, row in fatia_stf.iterrows():
                    ramo_atual = row.get('Ramo do Direito', 'Não Classificado')
                    
                    # Título do Card
                    st.markdown(f"#### Tema {row['Tema']} <span style='font-size:0.7em; background:#f0f2f6; padding:2px 6px; border-radius:4px;'>{ramo_atual}</span>", unsafe_allow_html=True)
                    st.markdown(f"**{row.get('Título')}**")
                    
                    with st.expander("Ver Detalhes / Editar Classificação"):
                        st.markdown(f"**Tese:** {row.get('Tese', '-')}")
                        st.markdown(f"**Leading Case:** {row.get('Leading Case', '-')}")
                        st.markdown(f"**Situação:** {row.get('Situação do Tema', '-')}")
                        
                        # ÁREA DE ADMINISTRAÇÃO (Só aparece se logado)
                        if is_admin:
                            st.markdown("---")
                            st.markdown("##### 🛠️ Admin: Alterar Ramo")
                            with st.form(key=f"form_stf_{row['Tema']}"):
                                c_edit1, c_edit2 = st.columns([3, 1])
                                
                                # Define índice inicial do dropdown
                                idx_inicial = 0
                                if ramo_atual in LISTA_RAMOS_COMPLETA:
                                    idx_inicial = LISTA_RAMOS_COMPLETA.index(ramo_atual)
                                
                                novo_ramo_sel = c_edit1.selectbox("Selecione a classificação correta:", 
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
                            st.caption("🔒 Para editar a classificação, insira a senha de admin na barra lateral.")
                            
                    st.divider()
            
            if pgs_stf > 1:
                st.number_input("Página", 1, pgs_stf, key="pstf_b", label_visibility="collapsed", on_change=sync_page_widgets, args=('pstf_b', 'pstf'))

    # === ABA STJ ===
    with tab_stj:
        df_stj = carregar_dados_stj()
        if df_stj is not None:
            c1, c2 = st.columns([1, 2])
            # Dropdown STJ
            lista_ramos_stj = sorted(df_stj['Ramo do direito'].dropna().unique())
            ramo_filtro_stj = c1.selectbox("Filtrar por Ramo (STJ):", ["Todos"] + lista_ramos_stj)
            busca_stj = c2.text_input("Buscar Tema STJ (Ctrl+F):")
            
            res_stj = df_stj.copy()
            if ramo_filtro_stj != "Todos": res_stj = res_stj[res_stj['Ramo do direito'] == ramo_filtro_stj]
            if busca_stj: res_stj = res_stj[res_stj['busca'].str.contains(busca_stj.lower(), na=False)]
            
            res_stj = res_stj.sort_values(by=['Ramo do direito', 'Tema'])
            
            # Paginação STJ
            total_stj = len(res_stj)
            pgs_stj = max(1, math.ceil(total_stj / ITEMS_PER_PAGE))
            p_stj = st.number_input("Página", 1, pgs_stj, key="pstj", on_change=sync_page_widgets, args=('pstj', 'pstj_b'))
            st.write(f"Mostrando página {p_stj} de {pgs_stj} ({total_stj} temas).")
            
            inicio_stj = (p_stj - 1) * ITEMS_PER_PAGE
            fatia_stj = res_stj.iloc[inicio_stj : inicio_stj + ITEMS_PER_PAGE]
            
            st.divider()
            if not fatia_stj.empty:
                for ramo, grupo in fatia_stj.groupby('Ramo do direito', sort=False):
                    st.subheader(f"📂 {ramo}")
                    with st.container(border=True):
                        for _, row in grupo.iterrows():
                            exibir_stj(row)
            
            if pgs_stj > 1:
                st.number_input("Página", 1, pgs_stj, key="pstj_b", label_visibility="collapsed", on_change=sync_page_widgets, args=('pstj_b', 'pstj'))

# --- PÁGINA 3: SÚMULAS ---
elif pagina == "Súmulas":
    st.title("🔗 Links Úteis de Súmulas")
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("#### 🏛️ [STF - Súmulas](https://portal.stf.jus.br/jurisprudencia/aplicacaosumula.asp)")
        st.caption("Supremo Tribunal Federal")
    with c2:
        st.markdown("#### ⚖️ [STJ - Súmulas](https://scon.stj.jus.br/SCON/sumstj/)")
        st.caption("Superior Tribunal de Justiça")
    with c3:
        st.markdown("#### 🔨 [TST - Súmulas](https://jurisprudencia.tst.jus.br/)")
        st.caption("Tribunal Superior do Trabalho")