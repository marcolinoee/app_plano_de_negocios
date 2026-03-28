import sys
import streamlit as st
import plotly.graph_objects as go
from google import genai
import numpy_financial as npf
import pandas as pd
import os
import io
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from banco_dados import session, ProjetoDB, CanvasDB, PremissasFinanceirasDB, InvestimentoDB, CustoFixoDB, ProdutoDB

# ==========================================
# UTILITÁRIOS
# ==========================================
def safe_image(url: str, **kwargs):
    """Exibe imagem remota com fallback silencioso para uso offline."""
    try:
        import urllib.request
        urllib.request.urlopen(url, timeout=2)
        st.image(url, **kwargs)
    except Exception:
        pass  # Offline: omite a imagem sem quebrar a interface

def fig_to_bytes(fig):
    """Converte gráficos Plotly em bytes PNG usando o motor Kaleido."""
    try:
        return fig.to_image(format="png", width=1000, height=550, scale=2)
    except Exception as e:
        st.error(f"Erro ao converter gráfico: {e}")
        return None

# Path base do executável (funciona tanto em .py quanto em .exe)
_BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
_LOGO_PATH = os.path.join(_BASE_DIR, "logo.png")
_FONTE_PATH = os.path.join(_BASE_DIR, "assets", "DejaVuSans.ttf")

st.set_page_config(page_title="Master Management - Plano 6.0", page_icon="💠", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# IDENTIDADE VISUAL MASTER MANAGEMENT (CSS)
# ==========================================
st.markdown("""
    <style>
    /* Fundo da aplicação */
    .stApp { background-color: #FAFAFA; }
    
    /* Ocultar elementos nativos */
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    
    /* Estilizar as Abas (Tabs) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #FFFFFF;
        padding: 10px 10px 0px 10px;
        border-radius: 10px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #F1F5F9;
        border-radius: 8px 8px 0px 0px;
        padding: 10px 16px;
        color: #111111;
        font-weight: 700;
        border-bottom: 3px solid transparent;
    }
    .stTabs [aria-selected="true"] {
        background-color: #111111 !important;
        color: #FFFFFF !important;
        border-bottom: 3px solid #FA5A5A !important;
    }
    
    /* Inputs e Caixas de Texto */
    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        border-radius: 8px;
        border: 1px solid #E2E8F0;
        background-color: #FFFFFF;
        padding: 10px;
        transition: all 0.3s;
    }
    .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
        border-color: #FA5A5A;
        box-shadow: 0 0 0 2px rgba(250, 90, 90, 0.2);
    }
    
    /* Botões Master Management */
    .stButton>button {
        background-color: #FA5A5A;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 10px 24px;
        font-weight: 700;
        transition: all 0.3s ease;
        width: 100%;
        box-shadow: 0 4px 6px -1px rgba(250, 90, 90, 0.2);
    }
    .stButton>button:hover {
        background-color: #111111;
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2);
        color: white;
    }
    
    /* Cartões e Formulários */
    [data-testid="stForm"], [data-testid="stExpander"] {
        background-color: #FFFFFF;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #111111;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        padding: 15px;
    }
    
    /* Títulos e Textos */
    h1, h2, h3 { color: #111111 !important; }
    
    /* Métricas */
    [data-testid="stMetricValue"] { color: #FA5A5A; font-weight: 900; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# SIDEBAR: GERENCIADOR DE PROJETOS (CRUD)
# ==========================================
with st.sidebar:
    st.image("https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=1000&auto=format&fit=crop", width="stretch")
    st.title("📁 Meus Projetos")
    
    # 1. Busca todos os projetos
    todos_projetos = session.query(ProjetoDB).all()
    
    # 2. Se o banco estiver vazio, cria o projeto fundacional
    if not todos_projetos:
        novo = ProjetoDB(nome_empresa="Nova Empresa")
        session.add(novo)
        session.commit()
        todos_projetos = [novo]
        
    # 3. Gerencia o Estado da Sessão (Qual projeto está aberto?)
    if 'projeto_atual_id' not in st.session_state:
        st.session_state['projeto_atual_id'] = todos_projetos[0].id
        
    # Proteção: Se o ID salvo na sessão foi deletado, volta pro primeiro
    ids_existentes = [p.id for p in todos_projetos]
    if st.session_state['projeto_atual_id'] not in ids_existentes:
        st.session_state['projeto_atual_id'] = ids_existentes[0]

    # 4. Read (Caixa de Seleção de Projetos)
    opcoes_projetos = {p.id: p.nome_empresa for p in todos_projetos}
    projeto_selecionado_id = st.selectbox(
        "Projeto Ativo:",
        options=list(opcoes_projetos.keys()),
        format_func=lambda x: opcoes_projetos[x],
        index=list(opcoes_projetos.keys()).index(st.session_state['projeto_atual_id'])
    )
    
    # Se o usuário trocou no selectbox, atualiza a sessão e recarrega a tela
    if projeto_selecionado_id != st.session_state['projeto_atual_id']:
        st.session_state['projeto_atual_id'] = projeto_selecionado_id
        st.rerun()

    st.markdown("---")
    st.subheader("⚙️ Ações do Gerenciador")

    # 5. Create (Novo Projeto)
    with st.form("form_novo_proj", clear_on_submit=True):
        novo_nome = st.text_input("Nome da Nova Empresa")
        if st.form_submit_button("➕ Criar Novo Projeto") and novo_nome:
            novo_proj = ProjetoDB(nome_empresa=novo_nome)
            session.add(novo_proj)
            session.commit()
            st.session_state['projeto_atual_id'] = novo_proj.id
            st.success("Projeto criado!")
            st.rerun()

    # 6. Update (Renomear)
    with st.expander("✏️ Renomear Projeto Atual"):
        with st.form("form_renomear"):
            novo_nome_atual = st.text_input("Novo Nome", value=opcoes_projetos[st.session_state['projeto_atual_id']])
            if st.form_submit_button("Salvar") and novo_nome_atual:
                proj_editar = session.get(ProjetoDB, st.session_state['projeto_atual_id'])
                proj_editar.nome_empresa = novo_nome_atual
                session.commit()
                st.rerun()

    # 7. Delete (Excluir)
    with st.expander("🗑️ Excluir Projeto Atual"):
        st.warning("⚠️ Atenção: A exclusão é permanente.")
        if st.button("Confirmar Exclusão", type="primary"):
            if len(todos_projetos) > 1:
                proj_deletar = session.get(ProjetoDB, st.session_state['projeto_atual_id'])
                session.delete(proj_deletar)
                session.commit()
                # Atualiza para o primeiro disponível no banco
                restantes = session.query(ProjetoDB).all()
                st.session_state['projeto_atual_id'] = restantes[0].id
                st.rerun()
            else:
                st.error("Você não pode excluir o único projeto restante.")
    # ==========================================
    # 🔌 BOTÃO DE DESLIGAMENTO DO SERVIDOR
    # ==========================================
    st.markdown("---")
    st.subheader("🔌 Sistema")
    st.caption("Ao terminar de usar, encerre o servidor para liberar a memória do computador.")
    
    if st.button("Desligar Master Management", type="primary"):
        st.success("Servidor encerrado com segurança! Você já pode fechar esta aba do navegador.")
        import os
        import time
        time.sleep(2) # Dá tempo de mostrar a mensagem verde antes de matar o processo
        os._exit(0)   # Comando bruto do Sistema Operacional que mata a raiz do servidor

# ==========================================
# INICIALIZAÇÃO DO PROJETO ATIVO
# ==========================================
# Carrega do banco de dados exatamente a instância que está na sessão
projeto = session.get(ProjetoDB, st.session_state['projeto_atual_id'])

# Garante que as dependências vitais 1:1 existam (Gatilhos de segurança)
if not projeto.canvas:
    session.add(CanvasDB(projeto_id=projeto.id)); session.commit(); session.refresh(projeto)
if not hasattr(projeto, 'premissas') or not projeto.premissas:
    session.add(PremissasFinanceirasDB(projeto_id=projeto.id)); session.commit(); session.refresh(projeto)

# Cabeçalho com o Logotipo
col_logo, col_titulo = st.columns([1, 3])
with col_logo:
    if os.path.exists(_LOGO_PATH):
        st.image(_LOGO_PATH, width="stretch")
    else:
        st.markdown("### 💠 MASTER MGT")
with col_titulo:
    st.title(f"Plano de Negócios: {projeto.nome_empresa}")
st.markdown("---")

# ==========================================
# ARQUITETURA DE INFORMAÇÃO: ABAS
# ==========================================
aba1, aba2, aba3, aba4, aba5, aba6, aba7, aba8, aba9, aba10 = st.tabs([
       "🧩 Canvas", "📈 Premissas", "🛠️ Capex", "🔄 Opex",
       "🏷️ Preços", "📄 Resumo", "📊 Viabilidade", "🤖 IA", "📉 Dashboard", 
       "🖨️ Relatório"
   ])
 

# ==========================================
# ABA 1: CANVAS
# ==========================================
with aba1:
    safe_image("https://images.unsplash.com/photo-1552664730-d307ca884978?q=80&w=1000&auto=format&fit=crop", width="stretch")
    st.header("Business Model Canvas")
    with st.form("form_canvas"):
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            parceiros = st.text_area("1. Parceiros", value=projeto.canvas.parceiros, height=150, max_chars=2000)
            estrutura_custos = st.text_area("8. Estrutura de Custos", value=projeto.canvas.estrutura_custos, height=150, max_chars=2000)
        with c2:
            processos = st.text_area("2. Processos", value=projeto.canvas.processos, height=150, max_chars=2000)
            recursos = st.text_area("3. Recursos", value=projeto.canvas.recursos, height=150, max_chars=2000)
        with c3:
            proposta = st.text_area("4. Proposta de Valor", value=projeto.canvas.proposta_valor, height=330, max_chars=2000)
        with c4:
            atendimento = st.text_area("5. Relacionamento", value=projeto.canvas.atendimento, height=150, max_chars=2000)
            canais = st.text_area("6. Canais", value=projeto.canvas.canais, height=150, max_chars=2000)
        with c5:
            segmentos = st.text_area("7. Segmentos", value=projeto.canvas.segmentos, height=150, max_chars=2000)
            receitas = st.text_area("9. Fontes de Receita", value=projeto.canvas.fontes_receita, height=150, max_chars=2000)
        if st.form_submit_button("Guardar Estratégia"):
            projeto.canvas.parceiros, projeto.canvas.processos, projeto.canvas.recursos = parceiros, processos, recursos
            projeto.canvas.proposta_valor, projeto.canvas.atendimento, projeto.canvas.canais = proposta, atendimento, canais
            projeto.canvas.segmentos, projeto.canvas.estrutura_custos, projeto.canvas.fontes_receita = segmentos, estrutura_custos, receitas
            session.commit(); st.success("Canvas atualizado!")

# ==========================================
# ABA 2: PREMISSAS E SAZONALIDADE
# ==========================================
with aba2:
    safe_image("https://images.unsplash.com/photo-1460925895917-afdab827c52f?q=80&w=1000&auto=format&fit=crop", width="stretch")
    st.header("Premissas e Perfil de Sazonalidade")
    with st.form("form_premissas"):
        c1, c2, c3, c4 = st.columns(4)
        hor_anos = c1.number_input("Horizonte (Anos)", min_value=1, max_value=10, value=projeto.premissas.horizonte_anos)
        tma = c2.number_input("TMA (% a.a.)", value=projeto.premissas.tma_anual_pct)
        crescimento = c3.number_input("Crescimento de Vendas (% a.a.)", value=projeto.premissas.crescimento_vendas_ano_pct)
        inflacao = c4.number_input("Inflação de Custos (% a.a.)", value=projeto.premissas.inflacao_custos_ano_pct)
        
        st.markdown("---")
        st.subheader("Sazonalidade das Vendas (%)")
        s1, s2, s3, s4, s5, s6 = st.columns(6)
        m1 = s1.number_input("Mês 1 (%)", value=projeto.premissas.saz_m1)
        m2 = s2.number_input("Mês 2 (%)", value=projeto.premissas.saz_m2)
        m3 = s3.number_input("Mês 3 (%)", value=projeto.premissas.saz_m3)
        m4 = s4.number_input("Mês 4 (%)", value=projeto.premissas.saz_m4)
        m5 = s5.number_input("Mês 5 (%)", value=projeto.premissas.saz_m5)
        m6 = s6.number_input("Mês 6 (%)", value=projeto.premissas.saz_m6)
        
        s7, s8, s9, s10, s11, s12 = st.columns(6)
        m7 = s7.number_input("Mês 7 (%)", value=projeto.premissas.saz_m7)
        m8 = s8.number_input("Mês 8 (%)", value=projeto.premissas.saz_m8)
        m9 = s9.number_input("Mês 9 (%)", value=projeto.premissas.saz_m9)
        m10 = s10.number_input("Mês 10 (%)", value=projeto.premissas.saz_m10)
        m11 = s11.number_input("Mês 11 (%)", value=projeto.premissas.saz_m11)
        m12 = s12.number_input("Mês 12 (%)", value=projeto.premissas.saz_m12)
        
        if st.form_submit_button("Atualizar Motor de Projeção"):
            projeto.premissas.horizonte_anos, projeto.premissas.tma_anual_pct = hor_anos, tma
            projeto.premissas.crescimento_vendas_ano_pct, projeto.premissas.inflacao_custos_ano_pct = crescimento, inflacao
            projeto.premissas.saz_m1, projeto.premissas.saz_m2, projeto.premissas.saz_m3 = m1, m2, m3
            projeto.premissas.saz_m4, projeto.premissas.saz_m5, projeto.premissas.saz_m6 = m4, m5, m6
            projeto.premissas.saz_m7, projeto.premissas.saz_m8, projeto.premissas.saz_m9 = m7, m8, m9
            projeto.premissas.saz_m10, projeto.premissas.saz_m11, projeto.premissas.saz_m12 = m10, m11, m12
            session.commit(); st.success("Atualizado!")

# ==========================================
# ABA 3 e 4: CAPEX e OPEX
# ==========================================
with aba3:
    safe_image("https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?q=80&w=1000&auto=format&fit=crop", width="stretch")
    st.header("Plano de Investimentos (Capex)")
    
    with st.form("form_capex", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 1])
        cat_inv = c1.selectbox("Categoria", ["Equipamentos", "Máquinas", "Instalações", "Outros"], key="cat_capex")
        desc_inv = c2.text_input("Descrição", key="desc_capex")
        val_inv = c3.number_input("Valor (R$)", min_value=0.0, step=100.0, key="val_capex")
        
        if st.form_submit_button("Adicionar Investimento") and desc_inv:
            session.add(InvestimentoDB(categoria=cat_inv, descricao=desc_inv, valor=val_inv, projeto_id=projeto.id))
            session.commit(); st.rerun()
            
    for inv in projeto.investimentos: 
        col_info, col_del = st.columns([11, 1]) 
        with col_info:
            st.info(f"**{inv.categoria}**: {inv.descricao} - R$ {inv.valor:,.2f}")
        with col_del:
            if st.button("🗑️", key=f"del_inv_{inv.id}", help="Excluir item"):
                session.delete(inv)
                session.commit()
                st.rerun()
                
with aba4:
    safe_image("https://images.unsplash.com/photo-1497366216548-37526070297c?q=80&w=1000&auto=format&fit=crop", width="stretch")
    st.header("Custos Fixos e RH (Opex)")
    with st.form("form_opex", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 1])
        cat_custo = c1.selectbox("Categoria", ["Colaboradores", "Pró-labore", "Serviços", "Estrutura"], key="cat_opex")
        desc_custo = c2.text_input("Descrição", key="desc_opex")
        val_custo = c3.number_input("Valor Mensal (R$)", min_value=0.0, step=100.0, key="val_opex")
        
        if st.form_submit_button("Adicionar Custo") and desc_custo:
            session.add(CustoFixoDB(categoria=cat_custo, descricao=desc_custo, valor_mensal=val_custo, projeto_id=projeto.id))
            session.commit(); st.rerun()
            
    for custo in projeto.custos_fixos: 
        col_info, col_del = st.columns([11, 1])
        with col_info:
            st.error(f"**{custo.categoria}**: {custo.descricao} - R$ {custo.valor_mensal:,.2f} / mês")
        with col_del:
            if st.button("🗑️", key=f"del_opex_{custo.id}", help="Excluir custo"):
                session.delete(custo)
                session.commit()
                st.rerun()

# ==========================================
# ABA 5: PRECIFICAÇÃO
# ==========================================
with aba5:
    safe_image("https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?q=80&w=1000&auto=format&fit=crop", width="stretch")
    st.header("Ficha Técnica e Precificação")
    with st.form("form_preco", clear_on_submit=True):
        nome_prod = st.text_input("Produto/Serviço")
        c1, c2 = st.columns(2)
        vendas_mes = c1.number_input("Vendas Base (Mês)", min_value=0)
        custo_insumo = c2.number_input("Custo de Insumo (R$)", min_value=0.0)
        c3, c4, c5, c6 = st.columns(4)
        imp_pct = c3.number_input("Impostos (%)", min_value=0.0, max_value=99.0, step=0.5)
        tax_pct = c4.number_input("Taxas (%)", min_value=0.0, max_value=99.0, step=0.5)
        com_pct = c5.number_input("Comissões (%)", min_value=0.0, max_value=99.0, step=0.5)
        lucro_pct = c6.number_input("Margem Lucro (%)", min_value=0.0, max_value=99.0, step=0.5)
        
        if st.form_submit_button("Calcular e Salvar") and nome_prod:
            soma_pct = (imp_pct + tax_pct + com_pct + lucro_pct) / 100.0
            if soma_pct >= 1: st.error("A soma não pode ser >= 100%!")
            else:
                preco = custo_insumo / (1 - soma_pct)
                session.add(ProdutoDB(nome_produto=nome_prod, estimativa_vendas_mes=vendas_mes, custo_insumos=custo_insumo, impostos_pct=imp_pct, taxas_pct=tax_pct, comissoes_pct=com_pct, margem_lucro_pct=lucro_pct, preco_venda_sugerido=preco, projeto_id=projeto.id))
                session.commit(); st.success(f"Preço: R$ {preco:.2f}"); st.rerun()

    for p in projeto.produtos: 
        col_info, col_del = st.columns([11, 1])
        with col_info:
            st.success(f"📦 **{p.nome_produto}** | Preço: R$ {p.preco_venda_sugerido:.2f}")
        with col_del:
            if st.button("🗑️", key=f"del_prod_{p.id}", help="Excluir produto"):
                session.delete(p)
                session.commit()
                st.rerun()

# ==========================================
# ABA 6: RESUMO EXECUTIVO
# ==========================================
with aba6:
    safe_image("https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?q=80&w=1000&auto=format&fit=crop", width="stretch")
    st.header("📄 Resumo Executivo")
    with st.expander("🧩 Eixo Estratégico", expanded=True):
        st.markdown(f"**Proposta de Valor:** {projeto.canvas.proposta_valor}")
    with st.expander("📈 Premissas Macroeconômicas"):
        st.markdown(f"- Horizonte: {projeto.premissas.horizonte_anos} anos | TMA: {projeto.premissas.tma_anual_pct}% a.a.")
    with st.expander("🛠️ Capex"):
        for inv in projeto.investimentos: st.markdown(f"- {inv.descricao}: R$ {inv.valor:,.2f}")
    with st.expander("🔄 Opex"):
        for custo in projeto.custos_fixos: st.markdown(f"- {custo.descricao}: R$ {custo.valor_mensal:,.2f}")

# ==========================================
# ABA 7: VIABILIDADE MENSAL
# ==========================================
with aba7:
    safe_image("https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=1000&auto=format&fit=crop", width="stretch")
    st.header("Análise de Viabilidade (Mês a Mês)")
    anos = projeto.premissas.horizonte_anos
    meses_totais = anos * 12
    tma_am = (1 + (projeto.premissas.tma_anual_pct / 100.0))**(1/12) - 1
    tx_cresc_am = (1 + (projeto.premissas.crescimento_vendas_ano_pct / 100.0))**(1/12) - 1
    tx_infl_am = (1 + (projeto.premissas.inflacao_custos_ano_pct / 100.0))**(1/12) - 1
    
    saz = [
        projeto.premissas.saz_m1/100, projeto.premissas.saz_m2/100, projeto.premissas.saz_m3/100,
        projeto.premissas.saz_m4/100, projeto.premissas.saz_m5/100, projeto.premissas.saz_m6/100,
        projeto.premissas.saz_m7/100, projeto.premissas.saz_m8/100, projeto.premissas.saz_m9/100,
        projeto.premissas.saz_m10/100, projeto.premissas.saz_m11/100, projeto.premissas.saz_m12/100
    ]
    
    capex_total = sum(i.valor for i in projeto.investimentos)
    receita_base = sum(p.preco_venda_sugerido * p.estimativa_vendas_mes for p in projeto.produtos)
    custo_var_base = sum(p.custo_insumos * p.estimativa_vendas_mes for p in projeto.produtos)
    deducoes_base = sum((p.preco_venda_sugerido * p.estimativa_vendas_mes) * ((p.impostos_pct + p.taxas_pct + p.comissoes_pct) / 100.0) for p in projeto.produtos)
    custo_fixo_base = sum(c.valor_mensal for c in projeto.custos_fixos)
    
    fluxo_caixa, meses_labels = [-capex_total], ["Mês 0"]
    for mes in range(1, meses_totais + 1):
        idx_saz = (mes - 1) % 12
        rec_mes = receita_base * saz[idx_saz] * ((1 + tx_cresc_am)**mes)
        cv_mes = custo_var_base * saz[idx_saz] * ((1 + tx_cresc_am)**mes)
        ded_mes = deducoes_base * saz[idx_saz] * ((1 + tx_cresc_am)**mes)
        cf_mes = custo_fixo_base * ((1 + tx_infl_am)**mes)
        fluxo_caixa.append(rec_mes - cv_mes - ded_mes - cf_mes)
        meses_labels.append(f"M {mes}")

    vpl = npf.npv(tma_am, fluxo_caixa)

    tir_aa = 0.0
    tir_valida = False
    try:
        if capex_total > 0:
            irr_val = npf.irr(fluxo_caixa)
            if irr_val is not None and irr_val == irr_val:  # checa NaN
                tir_aa = ((1 + irr_val)**12 - 1) * 100
                tir_valida = True
    except (ValueError, FloatingPointError):
        tir_aa = 0.0
        tir_valida = False

    fluxo_acumulado = pd.Series(fluxo_caixa).cumsum()
    payback_meses = "Não recupera"
    for i, valor in enumerate(fluxo_acumulado):
        if valor >= 0 and i > 0:
            payback_meses = f"{i} meses"
            break

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Capex", f"R$ {capex_total:,.2f}")
    c2.metric("VPL", f"R$ {vpl:,.2f}", delta="Viável" if vpl > 0 else "Inviável")
    tir_label = f"{tir_aa:,.2f}%" if tir_valida else "N/A"
    tir_delta = f"TMA: {projeto.premissas.tma_anual_pct}%" if tir_valida else "⚠️ Fluxo sem inversão de sinal"
    c3.metric("TIR a.a.", tir_label, delta=tir_delta)
    c4.metric("Payback", payback_meses)

    if not tir_valida and capex_total > 0:
        st.warning("⚠️ A TIR não pôde ser calculada. Verifique se o projeto gera lucro em algum período do horizonte.")

    fig = go.Figure(data=[go.Bar(name='Fluxo Mensal', x=meses_labels, y=fluxo_caixa, marker_color=['#111111' if val < 0 else '#FA5A5A' for val in fluxo_caixa])])
    fig.add_trace(go.Scatter(name='Caixa Acumulado', x=meses_labels, y=fluxo_acumulado, mode='lines', line=dict(color='#888888', width=2)))
    fig.update_layout(barmode='group', height=500)
    st.plotly_chart(fig, width="stretch")

# ==========================================
# ABA 8: MENTOR IA
# ==========================================
with aba8:
    safe_image("https://images.unsplash.com/photo-1677442136019-21780ecad995?q=80&w=1000&auto=format&fit=crop", width="stretch")
    st.header("🧠 Parecer Final do Comitê (IA)")
    api_key_final = st.text_input("Sua Chave API Gemini:", type="password")
    
    if api_key_final and st.button("Gerar Dossiê de Captação"):
        tir_str = f"{tir_aa:.2f}%" if tir_valida else "não calculada (projeto sem retorno positivo no horizonte)"
        prompt_ia = f"""Você é um analista financeiro sênior. Avalie a viabilidade do projeto abaixo e forneça um parecer executivo em português.

<dados_do_projeto>
  Empresa: {projeto.nome_empresa}
  Investimento Inicial (Capex): R$ {capex_total:,.2f}
  Valor Presente Líquido (VPL): R$ {vpl:,.2f}
  TIR Anualizada: {tir_str}
  TMA de Referência: {projeto.premissas.tma_anual_pct}% a.a.
  Payback: {payback_meses}
  Horizonte de análise: {projeto.premissas.horizonte_anos} anos
  Crescimento de vendas projetado: {projeto.premissas.crescimento_vendas_ano_pct}% a.a.
</dados_do_projeto>

Com base nesses dados, forneça:
1. Diagnóstico de viabilidade (viável / inviável / limítrofe)
2. Principais riscos identificados
3. Recomendações estratégicas
4. Comparativo com benchmarks do setor (se aplicável)"""
        try:
            client = genai.Client(api_key=api_key_final)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt_ia
            )
            st.markdown(response.text)
        except Exception as e:
            st.error(f"Erro ao consultar IA: {e}")

# ==========================================
# ABA 9: DASHBOARD DE INDICADORES
# ==========================================
with aba9:
    safe_image("https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=1000&auto=format&fit=crop", width="stretch")
    st.header("📉 Dashboard de Indicadores")
 
    sem_produtos  = len(projeto.produtos) == 0
    sem_capex     = capex_total == 0
    sem_custos    = custo_fixo_base == 0
 
    if sem_produtos:
        st.warning("⚠️ Cadastre ao menos um produto na aba **Preços** para visualizar os indicadores.")
        st.stop()
 
    receita_liq   = receita_base - deducoes_base
    margem_bruta  = receita_liq - custo_var_base
    mc_pct        = (margem_bruta / receita_base * 100) if receita_base > 0 else 0
    lucro_liq     = margem_bruta - custo_fixo_base
    liq_pct       = (lucro_liq / receita_base * 100) if receita_base > 0 else 0
 
    pe_receita    = (custo_fixo_base / (mc_pct / 100)) if mc_pct > 0 else 0
    il            = (vpl / capex_total) if capex_total > 0 else 0
    roi_mensal    = (lucro_liq / capex_total * 100) if capex_total > 0 else 0
    burn_rate     = custo_fixo_base + custo_var_base
    runway_meses  = (capex_total / abs(lucro_liq)) if lucro_liq < 0 and capex_total > 0 else None
 
    meses_pe = "Não recupera"
    for i, v in enumerate(fluxo_acumulado):
        if v >= 0 and i > 0:
            meses_pe = f"{i} meses"
            break
 
    st.subheader("Resumo Executivo")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Receita Bruta/mês",  f"R$ {receita_base:,.2f}")
    col2.metric("Lucro Líquido/mês",  f"R$ {lucro_liq:,.2f}", delta=f"{liq_pct:.1f}% da receita")
    col3.metric("Margem de Contribuição", f"{mc_pct:.1f}%")
    col4.metric("Ponto de Equilíbrio", f"R$ {pe_receita:,.2f}/mês")
 
    st.markdown("---")
    st.subheader("DRE Simplificada (Base Mensal)")
 
    dre_items = [
        ("(+) Receita Bruta",               receita_base,    False),
        ("(-) Deduções (impostos + taxas)",  -deducoes_base,  True),
        ("(=) Receita Líquida",              receita_liq,     False),
        ("(-) Custos Variáveis (insumos)",   -custo_var_base, True),
        ("(=) Margem Bruta",                 margem_bruta,    False),
        ("(-) Custos Fixos",                 -custo_fixo_base, True),
        ("(=) Resultado Líquido",            lucro_liq,       False),
    ]
 
    dre_df = pd.DataFrame(dre_items, columns=["Descrição", "Valor (R$)", "Dedução"])
    dre_df["Valor (R$)"] = dre_df["Valor (R$)"].apply(lambda v: f"R$ {v:,.2f}")
 
    for _, row in dre_df.iterrows():
        is_total = row["Descrição"].startswith("(=)")
        is_neg   = row["Dedução"]
        bg       = "#F1F5F9" if is_total else "transparent"
        fw       = "700" if is_total else "400"
        color    = "#DC2626" if is_neg else ("#16A34A" if is_total and lucro_liq >= 0 else "inherit")
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;padding:6px 10px;'
            f'background:{bg};border-radius:6px;font-weight:{fw};margin-bottom:2px">'
            f'<span>{row["Descrição"]}</span>'
            f'<span style="color:{color}">{row["Valor (R$)"]}</span></div>',
            unsafe_allow_html=True
        )
 
    st.markdown("---")
    st.subheader("Indicadores de Viabilidade")
 
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("VPL",                  f"R$ {vpl:,.2f}",
                  delta="Projeto viável" if vpl > 0 else "Projeto inviável")
        st.metric("Payback",              payback_meses)
 
    with col2:
        tir_str = f"{tir_aa:.2f}%" if tir_valida else "N/A"
        st.metric("TIR Anualizada",       tir_str,
                  delta=f"TMA: {projeto.premissas.tma_anual_pct}%")
        il_delta = "Cria valor" if il > 1 else ("Neutro" if il == 1 else "Destrói valor")
        st.metric("Índice de Lucratividade", f"{il:.2f}x", delta=il_delta)
 
    with col3:
        roi_str = f"{roi_mensal:.2f}% a.m." if capex_total > 0 else "Sem Capex"
        st.metric("ROI Mensal",           roi_str)
        if runway_meses:
            st.metric("Runway estimado",  f"{runway_meses:.0f} meses",
                      delta="Projeto dando prejuízo — use com cautela")
        else:
            st.metric("Resultado mensal", "Positivo ✓")
 
    st.markdown("---")
    st.subheader("Análise Visual")
 
    col_left, col_right = st.columns(2)
 
    with col_left:
        st.markdown("**Composição de Custos Mensais**")
        labels_pizza = ["Custos Variáveis", "Custos Fixos", "Deduções"]
        values_pizza = [custo_var_base, custo_fixo_base, deducoes_base]
        colors_pizza = ["#FA5A5A", "#111111", "#888888"]
 
        fig_pizza = go.Figure(data=[go.Pie(
            labels=labels_pizza,
            values=values_pizza,
            hole=0.55,
            marker=dict(colors=colors_pizza),
            textinfo="percent+label",
            textfont=dict(size=12),
            hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>"
        )])
        fig_pizza.update_layout(
            height=320,
            showlegend=False,
            margin=dict(t=10, b=10, l=10, r=10),
            annotations=[dict(
                text=f"R$ {(custo_var_base+custo_fixo_base+deducoes_base):,.0f}",
                x=0.5, y=0.5, font_size=13, showarrow=False
            )]
        )
        st.plotly_chart(fig_pizza, width="stretch")
 
    with col_right:
        st.markdown("**Receita por Produto/Serviço**")
        nomes_prod   = [p.nome_produto for p in projeto.produtos]
        receitas_prod = [p.preco_venda_sugerido * p.estimativa_vendas_mes for p in projeto.produtos]
        lucros_prod   = [
            (p.preco_venda_sugerido * p.estimativa_vendas_mes)
            - (p.custo_insumos * p.estimativa_vendas_mes)
            - ((p.preco_venda_sugerido * p.estimativa_vendas_mes) * ((p.impostos_pct + p.taxas_pct + p.comissoes_pct) / 100))
            for p in projeto.produtos
        ]
 
        fig_prod = go.Figure()
        fig_prod.add_trace(go.Bar(
            name="Receita Bruta", x=nomes_prod, y=receitas_prod,
            marker_color="#111111",
            hovertemplate="<b>%{x}</b><br>Receita: R$ %{y:,.2f}<extra></extra>"
        ))
        fig_prod.add_trace(go.Bar(
            name="Margem (após CV e deduções)", x=nomes_prod, y=lucros_prod,
            marker_color="#FA5A5A",
            hovertemplate="<b>%{x}</b><br>Margem: R$ %{y:,.2f}<extra></extra>"
        ))
        fig_prod.update_layout(
            height=320,
            barmode="group",
            showlegend=True,
            legend=dict(orientation="h", y=-0.25),
            margin=dict(t=10, b=10, l=10, r=10),
            yaxis=dict(tickprefix="R$ ", tickformat=",.0f")
        )
        st.plotly_chart(fig_prod, width="stretch")
 
    st.markdown("**Perfil de Sazonalidade das Vendas**")
    meses_nomes = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    saz_vals    = [
        projeto.premissas.saz_m1,  projeto.premissas.saz_m2,  projeto.premissas.saz_m3,
        projeto.premissas.saz_m4,  projeto.premissas.saz_m5,  projeto.premissas.saz_m6,
        projeto.premissas.saz_m7,  projeto.premissas.saz_m8,  projeto.premissas.saz_m9,
        projeto.premissas.saz_m10, projeto.premissas.saz_m11, projeto.premissas.saz_m12
    ]
    receita_saz = [receita_base * (s / 100) for s in saz_vals]
 
    fig_saz = go.Figure()
    fig_saz.add_trace(go.Bar(
        x=meses_nomes, y=receita_saz,
        name="Receita projetada",
        marker_color=["#FA5A5A" if s >= 100 else "#CCCCCC" for s in saz_vals],
        hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<br>Índice: %{customdata:.0f}%<extra></extra>",
        customdata=saz_vals
    ))
    fig_saz.add_hline(
        y=receita_base,
        line_dash="dash",
        line_color="#111111",
        annotation_text="Base (100%)",
        annotation_position="top right"
    )
    fig_saz.update_layout(
        height=280,
        showlegend=False,
        margin=dict(t=20, b=10, l=10, r=10),
        yaxis=dict(tickprefix="R$ ", tickformat=",.0f")
    )
    st.plotly_chart(fig_saz, width="stretch")
 
    st.markdown("---")
    st.subheader("Indicadores de Tração Digital (Startups TIC)")
    st.caption("Preencha abaixo para calcular métricas de SaaS/App. Opcional — apenas para projetos digitais.")
 
    with st.expander("Calcular CAC, LTV e MRR"):
        col1, col2, col3 = st.columns(3)
        custo_marketing  = col1.number_input("Custo de Aquisição (R$/mês)", min_value=0.0, step=100.0)
        novos_clientes   = col2.number_input("Novos clientes/mês", min_value=0)
        ticket_medio_mes = col3.number_input("Ticket médio mensal (R$)", min_value=0.0, step=10.0)
 
        col4, col5 = st.columns(2)
        churn_pct        = col4.number_input("Churn mensal (%)", min_value=0.0, max_value=100.0, step=0.5)
        base_clientes    = col5.number_input("Base de clientes atual", min_value=0)
 
        if novos_clientes > 0 or base_clientes > 0:
            cac    = (custo_marketing / novos_clientes) if novos_clientes > 0 else 0
            ltv    = (ticket_medio_mes / (churn_pct / 100)) if churn_pct > 0 else 0
            mrr    = ticket_medio_mes * base_clientes
            ltv_cac = (ltv / cac) if cac > 0 else 0
 
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("CAC",             f"R$ {cac:,.2f}",     delta="Custo por cliente")
            c2.metric("LTV",             f"R$ {ltv:,.2f}",     delta="Valor vitalício")
            c3.metric("MRR",             f"R$ {mrr:,.2f}",     delta="Receita recorrente/mês")
            c4.metric("LTV/CAC",         f"{ltv_cac:.1f}x",
                      delta="Saudável se > 3x" if ltv_cac >= 3 else "Abaixo do ideal (< 3x)")
 
            if ltv_cac > 0:
                if ltv_cac >= 3:
                    st.success(f"✅ LTV/CAC de {ltv_cac:.1f}x indica negócio com boa eficiência de aquisição.")
                elif ltv_cac >= 1:
                    st.warning(f"⚠️ LTV/CAC de {ltv_cac:.1f}x está marginal. Benchmarks saudáveis ficam acima de 3x.")
                else:
                    st.error(f"❌ LTV/CAC abaixo de 1x significa que custa mais adquirir um cliente do que ele gera.")

# ==========================================
# ABA 10: RELATÓRIO EXECUTIVO (PDF)
# ==========================================
with aba10:
    safe_image("https://images.unsplash.com/photo-1618044733300-9472054094ee?q=80&w=1000&auto=format&fit=crop", width="stretch")
    st.header("🖨️ Gerador de Dossiê Executivo V6.0")
    
    parecer_ia_input = st.text_area(
        "Parecer do Mentor IA (Cole aqui o resultado da aba anterior):", 
        height=200,
        help="Este texto será formatado automaticamente no PDF final."
    )

    if st.button("🚀 Gerar Relatório Completo", type="primary"):
        try:
            with st.spinner("Compilando dados e renderizando gráficos de alta resolução... (Isso pode levar alguns segundos)"):
                pdf = FPDF()
                pdf.set_auto_page_break(auto=True, margin=15)
                
                _fn = "DejaVu" if os.path.exists(_FONTE_PATH) else "helvetica"
                if _fn == "DejaVu":
                    pdf.add_font("DejaVu", "", _FONTE_PATH)
                    pdf.add_font("DejaVu", "B", _FONTE_PATH)

                # PÁGINA 1
                pdf.add_page()
                pdf.ln(60)
                pdf.set_font(_fn, "B", 24)
                pdf.cell(pdf.epw, 20, "DOSSIÊ DE VIABILIDADE", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
                pdf.set_font(_fn, "", 18)
                pdf.cell(pdf.epw, 10, projeto.nome_empresa.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
                pdf.ln(10)
                pdf.set_font(_fn, "", 10)
                pdf.cell(pdf.epw, 10, "Documento gerado via Master Management Plano 6.0", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

                # PÁGINA 2
                pdf.add_page()
                pdf.set_font(_fn, "B", 14)
                pdf.cell(pdf.epw, 10, "1. Modelo de Negócios (Estrutura Canvas)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
                pdf.ln(5)
                
                pdf.set_font(_fn, "", 10)
                pdf.set_font(_fn, "B", 11); pdf.cell(pdf.epw, 8, "Proposta de Valor:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_font(_fn, "", 10); pdf.multi_cell(pdf.epw, 6, projeto.canvas.proposta_valor if projeto.canvas else "Não informado")
                
                pdf.ln(4)
                pdf.set_font(_fn, "B", 11); pdf.cell(pdf.epw, 8, "Público-Alvo e Segmentos:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_font(_fn, "", 10); pdf.multi_cell(pdf.epw, 6, projeto.canvas.segmentos if projeto.canvas else "Não informado")

                # PÁGINA 3
                pdf.add_page()
                pdf.set_font(_fn, "B", 14)
                pdf.cell(pdf.epw, 10, "2. Análise de Viabilidade Financeira", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(5)
                
                pdf.set_font(_fn, "B", 10)
                pdf.cell(pdf.epw*0.5, 8, "Indicador", border=1); pdf.cell(pdf.epw*0.5, 8, "Valor", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_font(_fn, "", 10)
                pdf.cell(pdf.epw*0.5, 8, "Investimento Total (Capex)", border=1); pdf.cell(pdf.epw*0.5, 8, f"R$ {capex_total:,.2f}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.cell(pdf.epw*0.5, 8, "VPL (Valor Presente Líquido)", border=1); pdf.cell(pdf.epw*0.5, 8, f"R$ {vpl:,.2f}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.cell(pdf.epw*0.5, 8, "Payback Estimado", border=1); pdf.cell(pdf.epw*0.5, 8, str(payback_meses), border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                
                pdf.ln(10)
                
                try:
                    img_caixa = fig_to_bytes(fig)
                    if img_caixa:
                        pdf.set_font(_fn, "B", 12)
                        pdf.cell(pdf.epw, 8, "Fluxo de Caixa Acumulado", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
                        pdf.image(io.BytesIO(img_caixa), x=pdf.l_margin, w=pdf.epw)
                        pdf.ln(5)
                except Exception as e:
                    st.warning(f"Aviso: Não foi possível renderizar o gráfico de fluxo de caixa no PDF. {e}")

                if len(projeto.produtos) > 0:
                    try:
                        pdf.add_page()
                        pdf.set_font(_fn, "B", 14)
                        pdf.cell(pdf.epw, 10, "3. Análise Visual (Dashboard)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                        pdf.ln(5)

                        img_pizza = fig_to_bytes(fig_pizza)
                        if img_pizza:
                            pdf.set_font(_fn, "B", 12)
                            pdf.cell(pdf.epw, 8, "Composição de Custos Mensais", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
                            pdf.image(io.BytesIO(img_pizza), x=35, w=140) 
                            pdf.ln(10)
                            
                        img_prod = fig_to_bytes(fig_prod)
                        if img_prod:
                            pdf.set_font(_fn, "B", 12)
                            pdf.cell(pdf.epw, 8, "Receita e Margem por Produto", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
                            pdf.image(io.BytesIO(img_prod), x=pdf.l_margin, w=pdf.epw)
                            
                    except Exception as e:
                        st.warning(f"Aviso: Não foi possível renderizar os dashboards no PDF. {e}")

                # PÁGINA FINAL
                pdf.add_page()
                pdf.set_font(_fn, "B", 14)
                num_sessao = "4." if len(projeto.produtos) > 0 else "3."
                pdf.cell(pdf.epw, 10, f"{num_sessao} Parecer Técnico (Mentor IA)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(5)
                pdf.set_font(_fn, "", 10)
                
                texto_final = parecer_ia_input if parecer_ia_input else "Nenhum parecer foi anexado ao relatório."
                texto_limpo = texto_final.replace("•", "-").replace("\u2022", "-").replace("·", "-")
                pdf.multi_cell(pdf.epw, 6, texto_limpo)

                pdf_output = pdf.output()
                pdf_bytes = bytes(pdf_output) if not isinstance(pdf_output, bytes) else pdf_output
                
                st.success("✅ Dossiê compilado com sucesso e gráficos inseridos!")
                st.download_button(
                    label="📥 Baixar Relatório Executivo (PDF)",
                    data=pdf_bytes,
                    file_name=f"Dossie_{projeto.nome_empresa}.pdf",
                    mime="application/pdf"
                )
                
        except Exception as e:
            st.error(f"Erro crítico na geração do relatório: {e}")