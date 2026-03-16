import streamlit as st
import plotly.graph_objects as go
import google.generativeai as genai
import numpy_financial as npf
import pandas as pd
import os
from banco_dados import session, ProjetoDB, CanvasDB, PremissasFinanceirasDB, InvestimentoDB, CustoFixoDB, ProdutoDB

session.expire_all()
st.set_page_config(page_title="Master Management - Plano 5.0", page_icon="💠", layout="wide")

# ==========================================
# IDENTIDADE VISUAL MASTER MANAGEMENT (CSS)
# ==========================================
# Cores da marca: Preto (#111111), Vermelho/Coral (#FA5A5A), Branco (#FFFFFF)
st.markdown("""
    <style>
    /* Fundo da aplicação */
    .stApp { background-color: #FAFAFA; }
    
    /* Ocultar elementos nativos */
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    
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
# INICIALIZAÇÃO
# ==========================================
projeto = session.query(ProjetoDB).first()
if not projeto:
    projeto = ProjetoDB(nome_empresa="Nova Empresa")
    session.add(projeto); session.commit()
if not projeto.canvas:
    session.add(CanvasDB(projeto_id=projeto.id)); session.commit(); session.refresh(projeto)
if not hasattr(projeto, 'premissas') or not projeto.premissas:
    session.add(PremissasFinanceirasDB(projeto_id=projeto.id)); session.commit(); session.refresh(projeto)

# Cabeçalho com o Logotipo
col_logo, col_titulo = st.columns([1, 3])
with col_logo:
    # Tenta carregar o logo se o ficheiro existir
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.markdown("### 💠 MASTER MGT")
with col_titulo:
    st.title(f"Plano de Negócios: {projeto.nome_empresa}")
st.markdown("---")

# ==========================================
# ARQUITETURA DE INFORMAÇÃO: ABAS
# ==========================================
aba1, aba2, aba3, aba4, aba5, aba6, aba7, aba8 = st.tabs([
    "🧩 Canvas", "📈 Premissas", "🛠️ Capex", "🔄 Opex", 
    "🏷️ Preços", "📄 Resumo", "📊 Viabilidade", "🤖 IA"
])

# ==========================================
# ABA 1: CANVAS
# ==========================================
with aba1:
    st.image("https://images.unsplash.com/photo-1552664730-d307ca884978?q=80&w=1000&auto=format&fit=crop", use_container_width=True)
    st.header("Business Model Canvas")
    with st.form("form_canvas"):
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            parceiros = st.text_area("1. Parceiros", value=projeto.canvas.parceiros, height=150)
            estrutura_custos = st.text_area("8. Estrutura de Custos", value=projeto.canvas.estrutura_custos, height=150)
        with c2:
            processos = st.text_area("2. Processos", value=projeto.canvas.processos, height=150)
            recursos = st.text_area("3. Recursos", value=projeto.canvas.recursos, height=150)
        with c3:
            proposta = st.text_area("4. Proposta de Valor", value=projeto.canvas.proposta_valor, height=330)
        with c4:
            atendimento = st.text_area("5. Relacionamento", value=projeto.canvas.atendimento, height=150)
            canais = st.text_area("6. Canais", value=projeto.canvas.canais, height=150)
        with c5:
            segmentos = st.text_area("7. Segmentos", value=projeto.canvas.segmentos, height=150)
            receitas = st.text_area("9. Fontes de Receita", value=projeto.canvas.fontes_receita, height=150)
        if st.form_submit_button("Guardar Estratégia"):
            projeto.canvas.parceiros, projeto.canvas.processos, projeto.canvas.recursos = parceiros, processos, recursos
            projeto.canvas.proposta_valor, projeto.canvas.atendimento, projeto.canvas.canais = proposta, atendimento, canais
            projeto.canvas.segmentos, projeto.canvas.estrutura_custos, projeto.canvas.fontes_receita = segmentos, estrutura_custos, receitas
            session.commit(); st.success("Canvas atualizado!")

# ==========================================
# ABA 2: PREMISSAS E SAZONALIDADE
# ==========================================
with aba2:
    st.image("https://images.unsplash.com/photo-1460925895917-afdab827c52f?q=80&w=1000&auto=format&fit=crop", use_container_width=True)
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
    st.image("https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?q=80&w=1000&auto=format&fit=crop", use_container_width=True)
    st.header("Plano de Investimentos (Capex)")
    with st.form("form_capex", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 1])
        cat_inv = c1.selectbox("Categoria", ["Equipamentos", "Máquinas", "Instalações", "Outros"])
        desc_inv = c2.text_input("Descrição")
        val_inv = c3.number_input("Valor (R$)", min_value=0.0, step=100.0)
        if st.form_submit_button("Adicionar Investimento") and desc_inv:
            session.add(InvestimentoDB(categoria=cat_inv, descricao=desc_inv, valor=val_inv, projeto_id=projeto.id))
            session.commit(); st.rerun()
    for inv in projeto.investimentos: st.info(f"**{inv.categoria}**: {inv.descricao} - R$ {inv.valor:,.2f}")

with aba4:
    st.image("https://images.unsplash.com/photo-1497366216548-37526070297c?q=80&w=1000&auto=format&fit=crop", use_container_width=True)
    st.header("Custos Fixos e RH (Opex)")
    with st.form("form_opex", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 1])
        cat_custo = c1.selectbox("Categoria", ["Colaboradores", "Pró-labore", "Serviços", "Estrutura"])
        desc_custo = c2.text_input("Descrição")
        val_custo = c3.number_input("Valor Mensal (R$)", min_value=0.0, step=100.0)
        if st.form_submit_button("Adicionar Custo") and desc_custo:
            session.add(CustoFixoDB(categoria=cat_custo, descricao=desc_custo, valor_mensal=val_custo, projeto_id=projeto.id))
            session.commit(); st.rerun()
    for custo in projeto.custos_fixos: st.error(f"**{custo.categoria}**: {custo.descricao} - R$ {custo.valor_mensal:,.2f} / mês")

# ==========================================
# ABA 5: PRECIFICAÇÃO
# ==========================================
with aba5:
    st.image("https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?q=80&w=1000&auto=format&fit=crop", use_container_width=True)
    st.header("Ficha Técnica e Precificação")
    with st.form("form_preco", clear_on_submit=True):
        nome_prod = st.text_input("Produto/Serviço")
        c1, c2 = st.columns(2)
        vendas_mes = c1.number_input("Vendas Base (Mês)", min_value=0)
        custo_insumo = c2.number_input("Custo de Insumo (R$)", min_value=0.0)
        c3, c4, c5, c6 = st.columns(4)
        imp_pct = c3.number_input("Impostos (%)")
        tax_pct = c4.number_input("Taxas (%)")
        com_pct = c5.number_input("Comissões (%)")
        lucro_pct = c6.number_input("Margem Lucro (%)")
        
        if st.form_submit_button("Calcular e Salvar") and nome_prod:
            soma_pct = (imp_pct + tax_pct + com_pct + lucro_pct) / 100.0
            if soma_pct >= 1: st.error("A soma não pode ser >= 100%!")
            else:
                preco = custo_insumo / (1 - soma_pct)
                session.add(ProdutoDB(nome_produto=nome_prod, estimativa_vendas_mes=vendas_mes, custo_insumos=custo_insumo, impostos_pct=imp_pct, taxas_pct=tax_pct, comissoes_pct=com_pct, margem_lucro_pct=lucro_pct, preco_venda_sugerido=preco, projeto_id=projeto.id))
                session.commit(); st.success(f"Preço: R$ {preco:.2f}"); st.rerun()

    for p in projeto.produtos: st.success(f"📦 **{p.nome_produto}** | Preço: R$ {p.preco_venda_sugerido:.2f}")

# ==========================================
# ABA 6: RESUMO EXECUTIVO
# ==========================================
with aba6:
    st.image("https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?q=80&w=1000&auto=format&fit=crop", use_container_width=True)
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
    st.image("https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=1000&auto=format&fit=crop", use_container_width=True)
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
    try:
        tir_aa = ((1 + npf.irr(fluxo_caixa))**12 - 1) * 100 if capex_total > 0 else 0
    except: tir_aa = 0

    fluxo_acumulado = pd.Series(fluxo_caixa).cumsum()
    payback_meses = "Não recupera"
    for i, valor in enumerate(fluxo_acumulado):
        if valor >= 0 and i > 0:
            payback_meses = f"{i} meses"
            break

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Capex", f"R$ {capex_total:,.2f}")
    c2.metric("VPL", f"R$ {vpl:,.2f}", delta="Viável" if vpl > 0 else "Inviável")
    c3.metric("TIR a.a.", f"{tir_aa:,.2f}%" if tir_aa else "N/A", delta=f"TMA: {projeto.premissas.tma_anual_pct}%")
    c4.metric("Payback", payback_meses)

    fig = go.Figure(data=[go.Bar(name='Fluxo Mensal', x=meses_labels, y=fluxo_caixa, marker_color=['#111111' if val < 0 else '#FA5A5A' for val in fluxo_caixa])])
    fig.add_trace(go.Scatter(name='Caixa Acumulado', x=meses_labels, y=fluxo_acumulado, mode='lines', line=dict(color='#888888', width=2)))
    fig.update_layout(barmode='group', height=500)
    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# ABA 8: MENTOR IA
# ==========================================
with aba8:
    st.image("https://images.unsplash.com/photo-1677442136019-21780ecad995?q=80&w=1000&auto=format&fit=crop", use_container_width=True)
    st.header("🧠 Parecer Final do Comitê (IA)")
    api_key_final = st.text_input("Sua Chave API Gemini:", type="password")
    if api_key_final and st.button("Gerar Dossiê de Captação"):
        prompt_ia = f"Avalie: Empresa {projeto.nome_empresa}. Capex: {capex_total}, VPL: {vpl}, TIR: {tir_aa}%, Payback: {payback_meses}. Dê parecer financeiro."
        try:
            genai.configure(api_key=api_key_final)
            st.markdown(genai.GenerativeModel('models/gemini-2.5-flash').generate_content(prompt_ia).text)
        except Exception as e: st.error(f"Erro: {e}")