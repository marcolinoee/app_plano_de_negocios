# =============================================================================
# MASTER MANAGEMENT - VENTURE CAPITAL EDITION
# Copyright (c) 2026 - Prof. [Seu Nome] - [Nome da Instituição]
#
# AVISO LEGAL: Este código-fonte é propriedade intelectual do autor.
# É estritamente proibido o uso comercial, reprodução não autorizada,
# ou venda. Licenciado exclusivamente para fins didáticos e académicos
# na disciplina de Empreendedorismo/TIC.
# =============================================================================

import sys
import io
import os
import time
import urllib.request

import streamlit as st
import plotly.graph_objects as go
import numpy_financial as npf
import pandas as pd
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# ── Google Gemini (Mentor VC) ─────────────────────────────────────────────────
try:
    from google import genai as _genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# ── Modelos do Banco de Dados ─────────────────────────────────────────────────
from banco_dados import (
    session, 
    ProjetoDB, 
    LeanCanvasDB, 
    PremissasStartupDB,
    InvestimentoDB, 
    CustoFixoDB, 
    PlanoSaaSDB, 
    JuridicoDB
)

# =============================================================================
# FUNÇÕES UTILITÁRIAS E DE SEGURANÇA
# =============================================================================
def safe_str(valor):
    """
    Garante que valores nulos ou vazios oriundos da base de dados 
    não quebrem a compilação do PDF ou a interface gráfica.
    """
    if valor:
        return str(valor)
    else:
        return "Não informado."

def fig_to_bytes(fig):
    """
    Converte gráficos Plotly em bytes PNG usando o motor Kaleido.
    Possui tratamento de erro robusto para não travar o gerador de PDF no Windows.
    O parâmetro scale=2 garante alta resolução para impressão no Dossiê.
    """
    try:
        bytes_imagem = fig.to_image(
            format="png", 
            width=1000, 
            height=500, 
            scale=2
        )
        return bytes_imagem
    except Exception as e:
        st.error(f"Erro ao converter gráfico para imagem PNG: {e}")
        return None

def safe_image(url: str, **kwargs):
    """
    Tenta carregar uma imagem da web. Se o computador do utilizador 
    estiver offline, omite a imagem silenciosamente.
    """
    try:
        urllib.request.urlopen(url, timeout=2)
        st.image(url, **kwargs)
    except Exception:
        pass

# =============================================================================
# RESOLUÇÃO DE CAMINHOS ABSOLUTOS (COMPATIBILIDADE PYINSTALLER .EXE)
# =============================================================================
_BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
_LOGO_PATH = os.path.join(_BASE_DIR, "logo.png")
_FONTE_PATH = os.path.join(_BASE_DIR, "assets", "DejaVuSans.ttf")

# =============================================================================
# CONFIGURAÇÃO DE PÁGINA E INJEÇÃO DE CSS
# =============================================================================
st.set_page_config(
    page_title="Master Management — Venture Capital Edition",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* Estilo Base da Aplicação */
    .stApp { 
        background-color: #F8FAFC; 
    }
    
    #MainMenu {
        visibility: hidden;
    } 
    
    footer {
        visibility: hidden;
    }
    
    /* Configuração Avançada de Abas (Tabs) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px; 
        background: #FFFFFF; 
        padding: 10px 10px 0px 10px; 
        border-radius: 10px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 48px; 
        background: #F1F5F9; 
        border-radius: 8px 8px 0px 0px;
        padding: 8px 14px; 
        color: #0F172A; 
        font-weight: 700;
        border-bottom: 3px solid transparent;
        transition: all 0.2s ease-in-out;
    }
    
    .stTabs [aria-selected="true"] {
        background: #2563EB !important; 
        color: #FFFFFF !important;
        border-bottom: 3px solid #1D4ED8 !important;
    }
    
    /* Estilização de Formulários e Inputs */
    .stTextInput input, 
    .stNumberInput input, 
    .stTextArea textarea, 
    .stSelectbox div[data-baseweb="select"] {
        border-radius: 8px; 
        border: 1px solid #CBD5E1; 
        background: #FFFFFF; 
        padding: 10px;
    }
    
    .stTextInput input:focus, 
    .stNumberInput input:focus, 
    .stTextArea textarea:focus {
        border-color: #2563EB; 
        box-shadow: 0 0 0 2px rgba(37,99,235,0.2);
    }
    
    /* Botões Padrão */
    .stButton>button {
        background: #2563EB; 
        color: #FFFFFF; 
        border-radius: 8px; 
        border: none;
        padding: 10px 24px; 
        font-weight: 700; 
        transition: all 0.3s; 
        width: 100%;
    }
    
    .stButton>button:hover { 
        background: #1E40AF; 
        transform: translateY(-2px); 
        color: #FFFFFF; 
    }
    
    /* Cartões e Expanders */
    [data-testid="stForm"], 
    [data-testid="stExpander"] {
        background: #FFFFFF; 
        border-radius: 12px; 
        border: 1px solid #E2E8F0;
        border-left: 4px solid #2563EB; 
        padding: 15px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    }
    
    /* Tipografia e Métricas */
    [data-testid="stMetricValue"] { 
        color: #2563EB; 
        font-weight: 900; 
    }
    
    h1, h2, h3 { 
        color: #0F172A !important; 
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# PERSISTÊNCIA DE ESTADO DA IA
# =============================================================================
# Impede que a resposta do Mentor VC desapareça ao trocar de aba
if "parecer_ia" not in st.session_state:
    st.session_state["parecer_ia"] = ""

# =============================================================================
# SIDEBAR — GERENCIADOR DE PORTFÓLIO (CRUD)
# =============================================================================
with st.sidebar:
    safe_image(
        "https://images.unsplash.com/photo-1555066931-4365d14bab8c?q=80&w=1000&auto=format&fit=crop", 
        width="stretch"
    )
    st.title("📂 Startups em Análise")

    # 1. Leitura Inicial (Read)
    todos_projetos = session.query(ProjetoDB).all()
    if not todos_projetos:
        novo_projeto = ProjetoDB(nome_startup="Nova Startup TIC")
        session.add(novo_projeto)
        session.commit()
        todos_projetos = [novo_projeto]

    # 2. Definição Segura do Projeto Ativo
    if "projeto_atual_id" not in st.session_state:
        st.session_state["projeto_atual_id"] = todos_projetos[0].id

    ids_existentes = [p.id for p in todos_projetos]
    if st.session_state["projeto_atual_id"] not in ids_existentes:
        st.session_state["projeto_atual_id"] = ids_existentes[0]

    # 3. Caixa de Seleção de Projetos
    opcoes_projetos = {p.id: p.nome_startup for p in todos_projetos}
    projeto_selecionado_id = st.selectbox(
        "Startup Ativa:", 
        options=list(opcoes_projetos.keys()), 
        format_func=lambda x: opcoes_projetos[x], 
        index=list(opcoes_projetos.keys()).index(st.session_state["projeto_atual_id"])
    )
    
    # 4. Gatilho de Troca de Projeto
    if projeto_selecionado_id != st.session_state["projeto_atual_id"]:
        st.session_state["projeto_atual_id"] = projeto_selecionado_id
        st.session_state["parecer_ia"] = ""  # Limpa o feedback da IA antiga
        st.rerun()

    st.markdown("---")

    # 5. Criar Novo Projeto (Create)
    with st.form("form_novo_proj", clear_on_submit=True):
        novo_nome_startup = st.text_input("Nome da Nova Operação")
        botao_nova_startup = st.form_submit_button("➕ Criar Startup")
        
        if botao_nova_startup and novo_nome_startup:
            nova_startup = ProjetoDB(nome_startup=novo_nome_startup)
            session.add(nova_startup)
            session.commit()
            st.session_state["projeto_atual_id"] = nova_startup.id
            st.session_state["parecer_ia"] = ""
            st.success("Startup criada com sucesso!")
            st.rerun()

    # 6. Renomear e Excluir (Update / Delete)
    with st.expander("✏️ Renomear / 🗑️ Excluir"):
        with st.form("form_renomear"):
            nome_editado = st.text_input(
                "Novo Nome", 
                value=opcoes_projetos[st.session_state["projeto_atual_id"]]
            )
            botao_renomear = st.form_submit_button("Salvar Alteração")
            
            if botao_renomear and nome_editado:
                projeto_para_editar = session.get(ProjetoDB, st.session_state["projeto_atual_id"])
                projeto_para_editar.nome_startup = nome_editado
                session.commit()
                st.rerun()
                
        st.warning("Aviso: A exclusão é permanente e destrói o valuation do banco de dados.")
        botao_excluir = st.button("Excluir Startup", type="primary")
        
        if botao_excluir:
            if len(todos_projetos) > 1:
                projeto_para_deletar = session.get(ProjetoDB, st.session_state["projeto_atual_id"])
                session.delete(projeto_para_deletar)
                session.commit()
                st.session_state["projeto_atual_id"] = session.query(ProjetoDB).all()[0].id
                st.session_state["parecer_ia"] = ""
                st.rerun()
            else:
                st.error("Erro Crítico: Não é possível excluir a última startup da base de dados.")

    st.markdown("---")
    st.subheader("🔌 Sistema Local")
    if st.button("Desligar Servidor Interno", type="primary"):
        st.success("Servidor encerrado. A memória RAM foi libertada.")
        time.sleep(2)
        os._exit(0)

# =============================================================================
# INICIALIZAÇÃO DE INTEGRIDADE RELACIONAL 
# (Garante que as tabelas de 1:1 existam)
# =============================================================================
projeto = session.get(ProjetoDB, st.session_state["projeto_atual_id"])

def garantir_relacionamento(atributo, classe_modelo):
    """Verifica e cria os registos filhos caso não existam para o projeto."""
    if not getattr(projeto, atributo):
        novo_registo = classe_modelo(projeto_id=projeto.id)
        session.add(novo_registo)
        session.commit()
        session.refresh(projeto)

garantir_relacionamento("lean_canvas", LeanCanvasDB)
garantir_relacionamento("premissas", PremissasStartupDB)
garantir_relacionamento("juridico", JuridicoDB)

# =============================================================================
# CABEÇALHO DO APLICATIVO
# =============================================================================
col_logo, col_titulo = st.columns([1, 6])

with col_logo:
    if os.path.exists(_LOGO_PATH):
        st.image(_LOGO_PATH, width="stretch")
    else:
        st.markdown("## 🚀 VC")

with col_titulo:
    st.title(f"Startup: {projeto.nome_startup}")
    st.caption("Master Management v8.5 — Venture Capital & Due Diligence Edition")
    
st.markdown("---")

# =============================================================================
# ⚙️ MOTOR MATEMÁTICO E FINANCEIRO (SAAS & UNIT ECONOMICS)
# Processado antes das abas para garantir que os dados globais estejam
# acessíveis em todas as visualizações e relatórios.
# =============================================================================
premissas_atuais = projeto.premissas

# 1. Agrupamento de Custos Base (Capex e Opex Fixo)
capex_total_apurado = sum(investimento.valor for investimento in projeto.investimentos)
opex_fixo_mensal = sum(custo.valor_mensal for custo in projeto.custos_fixos) + projeto.juridico.custo_estimado_legal

# 2. Funil Freemium e Utilizadores Base
usuarios_pagos_diretos = sum(plano.usuarios_ativos_base for plano in projeto.planos_saas)
taxa_conversao_freemium_decimal = premissas_atuais.conversao_freemium_pct / 100.0

# Quantidade de utilizadores que convertem da base gratuita para a base paga
conversos_pagantes_freemium = int(premissas_atuais.usuarios_freemium_base * taxa_conversao_freemium_decimal)

# Total absoluto de utilizadores pagantes no momento zero
usuarios_pagantes_totais_base = usuarios_pagos_diretos + conversos_pagantes_freemium

# 3. Cálculo de Faturamento MRR e Ticket Médio
mrr_bruto_direto_apurado = sum(
    plano.ticket_mensal * plano.usuarios_ativos_base 
    for plano in projeto.planos_saas
)

if usuarios_pagos_diretos > 0:
    ticket_medio_arpu = mrr_bruto_direto_apurado / usuarios_pagos_diretos
else:
    ticket_medio_arpu = 0.0

# O MRR total absorve o faturamento dos convertidos do Freemium
mrr_bruto_total_consolidado = mrr_bruto_direto_apurado + (conversos_pagantes_freemium * ticket_medio_arpu)

# 4. Cálculo de Deduções Variáveis (Médias Ponderadas por Plano)
if usuarios_pagos_diretos > 0:
    media_deducao_impostos_pct = sum(
        (plano.taxas_pagamento_pct + plano.impostos_pct) / 100 * (plano.usuarios_ativos_base / usuarios_pagos_diretos) 
        for plano in projeto.planos_saas
    )
    
    media_custo_nuvem_rs = sum(
        plano.custo_servidor_por_usuario * (plano.usuarios_ativos_base / usuarios_pagos_diretos) 
        for plano in projeto.planos_saas
    )
else:
    media_deducao_impostos_pct = 0.0
    media_custo_nuvem_rs = 0.0

# Despesas Financeiras do Mês Zero
despesas_deducoes_base = mrr_bruto_total_consolidado * media_deducao_impostos_pct
despesas_nuvem_cogs_base = usuarios_pagantes_totais_base * media_custo_nuvem_rs

# 5. DRE Base e Margens Operacionais
mrr_liquido_apurado_base = mrr_bruto_total_consolidado - despesas_deducoes_base
burn_rate_total_mensal = opex_fixo_mensal + despesas_nuvem_cogs_base

resultado_operacional_ebitda = mrr_liquido_apurado_base - burn_rate_total_mensal

if mrr_bruto_total_consolidado > 0:
    margem_bruta_percentual = ((mrr_liquido_apurado_base - despesas_nuvem_cogs_base) / mrr_bruto_total_consolidado) * 100
else:
    margem_bruta_percentual = 0.0

faturamento_anualizado_arr = mrr_bruto_total_consolidado * 12

# 6. Mapeamento de Unit Economics
taxa_churn_decimal = premissas_atuais.churn_mensal_pct / 100.0

if taxa_churn_decimal > 0:
    ltv_vitalicio_cliente = ticket_medio_arpu / taxa_churn_decimal
else:
    ltv_vitalicio_cliente = 0.0

cac_aquisicao_mercado = premissas_atuais.cac_estimado

if cac_aquisicao_mercado > 0:
    indice_ltv_cac = ltv_vitalicio_cliente / cac_aquisicao_mercado
else:
    indice_ltv_cac = 0.0

# Tempo em meses para a margem de contribuição de um cliente pagar o seu próprio CAC
if cac_aquisicao_mercado > 0 and ticket_medio_arpu > 0 and (1 - media_deducao_impostos_pct) > 0:
    meses_payback_cac = cac_aquisicao_mercado / (ticket_medio_arpu * (1 - media_deducao_impostos_pct))
else:
    meses_payback_cac = None

# 7. Motor de Simulação Dinâmica (Loop de Crescimento)
meses_de_horizonte_projecao = premissas_atuais.horizonte_meses
tma_desconto_mensal = (1 + premissas_atuais.tma_anual_pct / 100) ** (1 / 12) - 1
taxa_crescimento_organico_mensal = premissas_atuais.crescimento_mensal_pct / 100.0

# Inicialização das listas da linha de tempo
lista_fluxo_de_caixa = [-capex_total_apurado]
lista_rotulos_meses = ["Mês 0"]

timeline_usuarios_pagantes = [usuarios_pagantes_totais_base]
timeline_mrr_crescente = [mrr_bruto_total_consolidado]
timeline_usuarios_freemium = [float(premissas_atuais.usuarios_freemium_base)]

# Variáveis mutáveis do Loop
usuarios_ativos_no_loop = float(usuarios_pagantes_totais_base)
usuarios_freemium_no_loop = float(premissas_atuais.usuarios_freemium_base)

for mes_corrente in range(1, meses_de_horizonte_projecao + 1):
    
    # 7.1. Crescimento da Base Freemium (Topo de Funil)
    usuarios_freemium_no_loop = usuarios_freemium_no_loop * (1 + taxa_crescimento_organico_mensal)
    
    # 7.2. Conversão de Gratuitos para Pagos
    novos_clientes_advindos_do_free = usuarios_freemium_no_loop * taxa_conversao_freemium_decimal
    
    # 7.3. Perdas por Cancelamento (Churn) da Base Paga
    evasao_de_clientes_pagos = usuarios_ativos_no_loop * taxa_churn_decimal
    
    # 7.4. Crescimento Orgânico da Base Paga
    novos_clientes_organicos_pagos = usuarios_ativos_no_loop * taxa_crescimento_organico_mensal
    
    # 7.5. Saldo Final de Utilizadores do Mês
    usuarios_ativos_no_loop = (usuarios_ativos_no_loop 
                               + novos_clientes_organicos_pagos 
                               + novos_clientes_advindos_do_free 
                               - evasao_de_clientes_pagos)

    # 7.6. Faturação do Mês
    mrr_apurado_no_mes = usuarios_ativos_no_loop * ticket_medio_arpu
    
    # 7.7. Custos do Mês
    deducoes_fiscais_no_mes = mrr_apurado_no_mes * media_deducao_impostos_pct
    cogs_nuvem_no_mes = usuarios_ativos_no_loop * media_custo_nuvem_rs
    
    # 7.8. Resultado Líquido
    resultado_liquido_mensal = (mrr_apurado_no_mes - deducoes_fiscais_no_mes) - cogs_nuvem_no_mes - opex_fixo_mensal

    # 7.9. Armazenamento na Matriz
    lista_fluxo_de_caixa.append(resultado_liquido_mensal)
    lista_rotulos_meses.append(f"Mês {mes_corrente}")
    
    timeline_usuarios_pagantes.append(usuarios_ativos_no_loop)
    timeline_mrr_crescente.append(mrr_apurado_no_mes)
    timeline_usuarios_freemium.append(usuarios_freemium_no_loop)

# Criação da Série Acumulada do Caixa (Balanço)
serie_caixa_acumulado = pd.Series(lista_fluxo_de_caixa).cumsum()

# 8. Análise de Viabilidade Financeira a Longo Prazo
valor_presente_liquido_vpl = npf.npv(tma_desconto_mensal, lista_fluxo_de_caixa)

taxa_interna_retorno_anual = 0.0
validade_da_tir = False

try:
    if capex_total_apurado > 0:
        tir_mensal_bruta = npf.irr(lista_fluxo_de_caixa)
        if tir_mensal_bruta is not None and not pd.isna(tir_mensal_bruta):
            taxa_interna_retorno_anual = ((1 + tir_mensal_bruta) ** 12 - 1) * 100
            validade_da_tir = True
except Exception:
    pass

mes_de_breakeven_payback = "O Projeto Não Atinge Breakeven"
for numero_mes, valor_em_caixa in enumerate(serie_caixa_acumulado):
    if valor_em_caixa >= 0 and numero_mes > 0:
        mes_de_breakeven_payback = f"{numero_mes} meses para o Payback"
        break

meses_runway_sobrevivencia = None
if resultado_operacional_ebitda < 0 and capex_total_apurado > 0:
    meses_runway_sobrevivencia = capex_total_apurado / abs(resultado_operacional_ebitda)


# =============================================================================
# 📊 CONSTRUÇÃO DOS GRÁFICOS (BYPASS DE DICIONÁRIO OBRIGATÓRIO PARA PYINSTALLER)
#
# Regra Crítica: A injeção do dicionário `layout` diretamente no construtor 
# `go.Figure()` é obrigatória. O uso do método `.update_layout()` causaria o 
# erro "AttributeError: 'Figure' object has no attribute 'parent'" no .exe Windows.
# =============================================================================

# Gráfico 1: Fluxo de Caixa Mensal e Vale da Morte
figura_cashflow_projetado = go.Figure(
    data=[
        {
            'type': 'bar', 
            'name': "Resultado Mensal Líquido", 
            'x': lista_rotulos_meses, 
            'y': lista_fluxo_de_caixa,
            'marker': {
                'color': ["#DC2626" if fluxo < 0 else "#16A34A" for fluxo in lista_fluxo_de_caixa]
            }
        },
        {
            'type': 'scatter', 
            'name': "Caixa Consolidado (Balanço)", 
            'x': lista_rotulos_meses, 
            'y': serie_caixa_acumulado.tolist(),
            'mode': "lines", 
            'line': {'color': "#0F172A", 'width': 3}
        }
    ],
    layout={
        'barmode': "group", 
        'height': 450, 
        'title': "Projeção de Cashflow — Atravessia do Vale da Morte",
        'legend': {'orientation': "h", 'yanchor': "bottom", 'y': 1.02}
    }
)

# Gráfico 2: Composição de Custos e Burn Rate (Gráfico Circular / Pizza)
# CORREÇÃO APLICADA AQUI: Utilização da variável correta despesas_nuvem_cogs_base
figura_pizza_custos = go.Figure(
    data=[
        {
            'type': 'pie',
            'labels': ["Serviços Cloud (COGS)", "Opex e Despesas Fixas", "Impostos e Gateways"],
            'values': [despesas_nuvem_cogs_base, opex_fixo_mensal, despesas_deducoes_base],
            'hole': 0.55,
            'marker': {'colors': ["#2563EB", "#0F172A", "#94A3B8"]},
            'textinfo': "percent+label"
        }
    ],
    layout={
        'height': 320, 
        'showlegend': False, 
        'margin': {'t': 10, 'b': 10, 'l': 10, 'r': 10}
    }
)

# Gráfico 3: Crescimento Expansivo de MRR e Aquisição de Utilizadores
figura_mrr_tracao = go.Figure(
    data=[
        {
            'type': 'scatter', 
            'name': "Evolução do MRR (R$)", 
            'x': lista_rotulos_meses[1:], 
            'y': timeline_mrr_crescente[1:],
            'mode': "lines", 
            'line': {'color': "#2563EB", 'width': 3}, 
            'yaxis': "y1"
        },
        {
            'type': 'scatter', 
            'name': "Expansão da Base Paga", 
            'x': lista_rotulos_meses[1:], 
            'y': timeline_usuarios_pagantes[1:],
            'mode': "lines", 
            'line': {'color': "#16A34A", 'width': 2, 'dash': "dot"}, 
            'yaxis': "y2"
        }
    ],
    layout={
        'height': 320,
        'yaxis': {
            'title': "Faturação MRR (R$)", 
            'title_font': {'color': "#2563EB"} # Correção Aplicada: title_font em vez de titlefont
        },
        'yaxis2': {
            'title': "Volume de Clientes Pagantes", 
            'overlaying': "y", 
            'side': "right", 
            'title_font': {'color': "#16A34A"}
        },
        'legend': {'orientation': "h", 'yanchor': "bottom", 'y': 1.02},
        'margin': {'t': 10, 'b': 10, 'l': 10, 'r': 10}
    }
)

# Gráfico 4: Visualização do Funil de Conversão (Freemium)
figura_funil_freemium = go.Figure(
    data=[
        {
            'type': 'bar',
            'x': ["Entrada: Base Freemium", "Saída: Conversões Efetivadas"],
            'y': [premissas_atuais.usuarios_freemium_base, conversos_pagantes_freemium],
            'marker': {'color': ["#94A3B8", "#2563EB"]},
            'text': [premissas_atuais.usuarios_freemium_base, conversos_pagantes_freemium],
            'textposition': "outside"
        }
    ],
    layout={
        'height': 280, 
        'title': "Desempenho do Funil Freemium", 
        'margin': {'t': 40, 'b': 10, 'l': 10, 'r': 10}
    }
)


# =============================================================================
# ARQUITETURA DE INFORMAÇÃO — 11 ABAS PROFISSIONAIS DE FUNDOS VC
# =============================================================================
(
    aba_canvas_negocios, 
    aba_premissas_mercado, 
    aba_capex_infra, 
    aba_opex_burn, 
    aba_saas_pricing, 
    aba_legal_riscos, 
    aba_resumo_onepager, 
    aba_viabilidade_vpl, 
    aba_dashboard_unit, 
    aba_mentor_vc, 
    aba_pdf_export
) = st.tabs([
    "🧩 Lean Canvas", 
    "📈 Premissas", 
    "🛠️ Capex", 
    "🔄 Opex",
    "💳 SaaS Pricing", 
    "⚖️ Riscos Legais", 
    "📄 Resumo One-Pager", 
    "📊 Viabilidade", 
    "📉 Dashboards",
    "🤖 Comitê VC (IA)", 
    "🖨️ Data Room (PDF)"
])

# =============================================================================
# ABA 1: LEAN CANVAS E MODELO DE NEGÓCIOS
# =============================================================================
with aba_canvas_negocios:
    safe_image(
        "https://images.unsplash.com/photo-1552664730-d307ca884978?q=80&w=1000&auto=format&fit=crop", 
        width="stretch"
    )
    st.header("🧩 Lean Canvas — Validação da Dor e da Solução")
    st.info("A matriz do Lean Canvas é o primeiro filtro de um investidor. Defina de forma clara a sua Proposta Única de Valor (VPU) e qual o seu 'Fosso Competitivo' (Vantagem Injusta).")

    with st.form("formulario_matriz_canvas"):
        col_c1, col_c2, col_c3, col_c4, col_c5 = st.columns(5)
        
        with col_c1:
            input_problema = st.text_area(
                "1. Problema Mapeado no Mercado", 
                value=projeto.lean_canvas.problema, 
                height=160
            )
            input_estrutura_custos = st.text_area(
                "8. Estrutura Macro de Custos", 
                value=projeto.lean_canvas.estrutura_custos, 
                height=160
            )
            
        with col_c2:
            input_solucao = st.text_area(
                "2. Arquitetura da Solução", 
                value=projeto.lean_canvas.solucao_mvp, 
                height=160
            )
            input_metricas = st.text_area(
                "3. Métricas‑Chave (Growth KPIs)", 
                value=projeto.lean_canvas.metricas_chave, 
                height=160
            )
            
        with col_c3:
            input_proposta_valor = st.text_area(
                "4. Proposta Única de Valor (VPU)",
                value=projeto.lean_canvas.proposta_valor, 
                height=340
            )
            
        with col_c4:
            input_vantagem = st.text_area(
                "5. Vantagem Injusta / Fosso (Moat)",
                value=projeto.lean_canvas.vantagem_injusta, 
                height=160
            )
            input_canais = st.text_area(
                "6. Canais de Aquisição de Clientes",    
                value=projeto.lean_canvas.canais, 
                height=160
            )
            
        with col_c5:
            input_segmentos = st.text_area(
                "7. ICP e Segmentos de Clientes",  
                value=projeto.lean_canvas.segmentos, 
                height=160
            )
            input_receitas = st.text_area(
                "9. Mecanismos e Fontes de Receita",      
                value=projeto.lean_canvas.fontes_receita, 
                height=160
            )

        st.markdown("---")
        st.subheader("🔬 Evidências de Validação Tecnológica (O MVP)")
        input_mvp_descricao = st.text_area(
            "Descreva com profundidade as características técnicas do MVP desenvolvido. Como foi feita a Prova de Conceito? A tecnologia suporta o ganho de escala?", 
            value=projeto.lean_canvas.mvp_descricao, 
            height=100
        )

        st.markdown("---")
        st.subheader("🌍 Matriz de Impacto e Governança (Agenda ESG / ODS)")
        input_ods_onu = st.text_area(
            "Fundos de Investimento modernos requerem o alinhamento com a agenda 2030 da ONU. Qual é o ODS que a sua startup impacta de forma direta?", 
            value=projeto.lean_canvas.ods_onu, 
            height=80
        )

        botao_salvar_canvas = st.form_submit_button("💾 Registar Arquitetura do Modelo de Negócios")
        
        if botao_salvar_canvas:
            canvas_ativo = projeto.lean_canvas
            canvas_ativo.problema = input_problema
            canvas_ativo.solucao_mvp = input_solucao
            canvas_ativo.mvp_descricao = input_mvp_descricao
            canvas_ativo.metricas_chave = input_metricas
            canvas_ativo.proposta_valor = input_proposta_valor
            canvas_ativo.vantagem_injusta = input_vantagem
            canvas_ativo.canais = input_canais
            canvas_ativo.segmentos = input_segmentos
            canvas_ativo.estrutura_custos = input_estrutura_custos
            canvas_ativo.fontes_receita = input_receitas
            canvas_ativo.ods_onu = input_ods_onu
            session.commit()
            st.success("✅ As diretrizes estratégicas da startup foram atualizadas com sucesso no repositório.")

# =============================================================================
# ABA 2: PREMISSAS MACROECONÓMICAS E DE TRAÇÃO
# =============================================================================
with aba_premissas_mercado:
    safe_image(
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f?q=80&w=1000&auto=format&fit=crop", 
        width="stretch"
    )
    st.header("📈 Definição de Premissas do Fundo e Motor de Growth")
    st.info("As variáveis definidas nesta área irão ditar a expansão logarítmica da startup, incluindo o limite do Valuation e a relação de eficiência da aquisição de mercado (CAC vs LTV).")

    with st.form("formulario_premissas_financeiras"):
        linha1_c1, linha1_c2, linha1_c3 = st.columns(3)
        input_horizonte = linha1_c1.number_input(
            "Horizonte de Avaliação de Risco (Meses)", 
            min_value=12, 
            max_value=120, 
            value=premissas_atuais.horizonte_meses
        )
        input_tma = linha1_c2.number_input(
            "Taxa Mínima de Atratividade (TMA Exigida pelo Fundo % a.a.)", 
            value=premissas_atuais.tma_anual_pct
        )
        input_cac_projetado = linha1_c3.number_input(
            "Custo Nominal Global de Aquisição de Clientes - CAC (R$)", 
            min_value=0.0, 
            value=premissas_atuais.cac_estimado
        )

        linha2_c1, linha2_c2, linha2_c3 = st.columns(3)
        input_churn_mensal = linha2_c1.number_input(
            "Taxa Previsional de Evasão de Clientes - Churn (% Mensal)", 
            value=premissas_atuais.churn_mensal_pct
        )
        input_taxa_conversao = linha2_c2.number_input(
            "Funil: Taxa de Conversão de Freemium para Plano Pago (%)", 
            value=premissas_atuais.conversao_freemium_pct
        )
        input_crescimento_organico = linha2_c3.number_input(
            "Taxa de Expansão e Crescimento Orgânico Mensal da Base (MoM %)", 
            value=premissas_atuais.crescimento_mensal_pct
        )

        st.markdown("---")
        st.subheader("Motor de Lançamento (Go-To-Market)")
        input_base_freemium = st.number_input(
            "Volume de Leads / Utilizadores Gratuitos Adquiridos no Momento Zero", 
            min_value=0, 
            value=premissas_atuais.usuarios_freemium_base
        )

        botao_atualizar_premissas = st.form_submit_button("⚡ Injetar Parâmetros no Motor de Valuation")
        
        if botao_atualizar_premissas:
            premissas_atuais.horizonte_meses = input_horizonte
            premissas_atuais.tma_anual_pct = input_tma
            premissas_atuais.cac_estimado = input_cac_projetado
            premissas_atuais.churn_mensal_pct = input_churn_mensal
            premissas_atuais.conversao_freemium_pct = input_taxa_conversao
            premissas_atuais.crescimento_mensal_pct = input_crescimento_organico
            premissas_atuais.usuarios_freemium_base = input_base_freemium
            session.commit()
            st.success("✅ O Motor Económico foi atualizado e as projeções foram recalculadas.")
            st.rerun()

# =============================================================================
# ABA 3: NECESSIDADE DE CAPITAL E CAPEX
# =============================================================================
with aba_capex_infra:
    safe_image(
        "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?q=80&w=1000&auto=format&fit=crop", 
        width="stretch"
    )
    st.header("🛠️ Alocação Estratégica do Capital Inicial (Capex)")

    with st.form("formulario_adicao_capex", clear_on_submit=True):
        col_inv1, col_inv2, col_inv3 = st.columns([1.5, 2.5, 1])
        
        categoria_investimento = col_inv1.selectbox(
            "Ramo de Alocação de Recursos", 
            [
                "Engenharia e Desenvolvimento do MVP", 
                "Setup de Licenças e Patentes", 
                "Compra de Infraestrutura / Servidores", 
                "Orçamento Base de Marketing (GTM)", 
                "Assessoria Legal de Estruturação", 
                "Outros"
            ]
        )
        descricao_investimento = col_inv2.text_input("Finalidade e Descrição Específica")
        valor_investimento = col_inv3.number_input("Valor Necessário (R$)", min_value=0.0, step=1000.0)
        
        botao_inserir_investimento = st.form_submit_button("➕ Adicionar à Rodada de Captação")
        
        if botao_inserir_investimento and descricao_investimento:
            novo_capex = InvestimentoDB(
                categoria=categoria_investimento, 
                descricao=descricao_investimento, 
                valor=valor_investimento, 
                projeto_id=projeto.id
            )
            session.add(novo_capex)
            session.commit()
            st.rerun()

    for item_capex in projeto.investimentos:
        coluna_texto, coluna_botao = st.columns([11, 1])
        coluna_texto.info(
            f"**{item_capex.categoria}** — {item_capex.descricao}   |   "
            f"Orçamento Alocado: R$ {item_capex.valor:,.2f}"
        )
        if coluna_botao.button("🗑️", key=f"excluir_capex_{item_capex.id}"):
            session.delete(item_capex)
            session.commit()
            st.rerun()

    if projeto.investimentos:
        st.metric("Total Requisitado para a Rodada de Financiamento (Seed / Pre-Seed)", f"R$ {capex_total_apurado:,.2f}")

# =============================================================================
# ABA 4: DESPESAS OPERACIONAIS E OPEX
# =============================================================================
with aba_opex_burn:
    safe_image(
        "https://images.unsplash.com/photo-1497366216548-37526070297c?q=80&w=1000&auto=format&fit=crop", 
        width="stretch"
    )
    st.header("🔄 Estrutura Mensal de Queima de Caixa (Opex)")

    with st.form("formulario_adicao_opex", clear_on_submit=True):
        col_op1, col_op2, col_op3 = st.columns([1.5, 2.5, 1])
        
        categoria_despesa = col_op1.selectbox(
            "Centro de Custos", 
            [
                "Custos com Pessoal Técnico (Headcount Tech)", 
                "Licenciamento de APIs / SaaS de Terceiros", 
                "Retirada de Sócios (Pró-labore)", 
                "Orçamento de Tráfego Pago / Performance", 
                "Instalações e Facilities", 
                "Outros"
            ]
        )
        descricao_despesa = col_op2.text_input("Rubrica Administrativa")
        valor_despesa = col_op3.number_input("Pagamento Mensal (R$/Mês)", min_value=0.0, step=500.0)
        
        botao_inserir_opex = st.form_submit_button("➕ Acrescentar Custo na DRE")
        
        if botao_inserir_opex and descricao_despesa:
            novo_opex = CustoFixoDB(
                categoria=categoria_despesa, 
                descricao=descricao_despesa, 
                valor_mensal=valor_despesa, 
                projeto_id=projeto.id
            )
            session.add(novo_opex)
            session.commit()
            st.rerun()

    for item_opex in projeto.custos_fixos:
        col_txt_op, col_btn_op = st.columns([11, 1])
        col_txt_op.error(
            f"**{item_opex.categoria}** — {item_opex.descricao}   |   "
            f"Saída Mensal Constante: R$ {item_opex.valor_mensal:,.2f}/mês"
        )
        if col_btn_op.button("🗑️", key=f"excluir_opex_{item_opex.id}"):
            session.delete(item_opex)
            session.commit()
            st.rerun()

    if projeto.custos_fixos:
        st.metric("Piso do Burn Rate de Manutenção", f"R$ {opex_fixo_mensal:,.2f} ao mês")

# =============================================================================
# ABA 5: PRICING E FATURAMENTO SAAS
# =============================================================================
with aba_saas_pricing:
    safe_image(
        "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?q=80&w=1000&auto=format&fit=crop", 
        width="stretch"
    )
    st.header("💳 Engenharia de Preços e Tiers de Assinatura")

    with st.form("formulario_cadastro_planos", clear_on_submit=True):
        nome_do_tier = st.text_input("Nomenclatura do Plano de Vendas (Ex: Plano Starter, Enterprise B2B)")
        
        col_pr1, col_pr2, col_pr3, col_pr4, col_pr5 = st.columns(5)
        ticket_plano = col_pr1.number_input("Receita Fixa (R$/Mês)", min_value=0.0)
        volume_clientes_plano = col_pr2.number_input("Número de Licenças Vendidas", min_value=0)
        taxa_cartao_plano = col_pr3.number_input("Taxa de Cartão/Gateway (%)", value=5.0)
        carga_fiscal_plano = col_pr4.number_input("Retenção de Impostos (%)", value=6.0)
        custo_nuvem_plano = col_pr5.number_input("Custo de Nuvem/AWS por User (R$)", min_value=0.0)

        botao_inserir_plano = st.form_submit_button("➕ Homologar Nova Linha de Receita")
        
        if botao_inserir_plano and nome_do_tier:
            novo_plano_saas = PlanoSaaSDB(
                nome_plano=nome_do_tier, 
                ticket_mensal=ticket_plano, 
                usuarios_ativos_base=volume_clientes_plano,
                taxas_pagamento_pct=taxa_cartao_plano, 
                impostos_pct=carga_fiscal_plano, 
                custo_servidor_por_usuario=custo_nuvem_plano,
                projeto_id=projeto.id
            )
            session.add(novo_plano_saas)
            session.commit()
            st.rerun()

    for assinatura in projeto.planos_saas:
        col_txt_saas, col_btn_saas = st.columns([11, 1])
        
        mrr_deste_plano = assinatura.ticket_mensal * assinatura.usuarios_ativos_base
        desconto_total = (assinatura.taxas_pagamento_pct + assinatura.impostos_pct) / 100
        margem_deste_plano = (mrr_deste_plano * (1 - desconto_total)) - (assinatura.custo_servidor_por_usuario * assinatura.usuarios_ativos_base)
        
        col_txt_saas.success(
            f"💳 **{assinatura.nome_plano}** — Preço (ARPU): R$ {assinatura.ticket_mensal:.2f} · "
            f"Contas Ativas: {assinatura.usuarios_ativos_base} · "
            f"Receita Produzida: R$ {mrr_deste_plano:,.2f} · "
            f"Lucro Bruto do Tier: R$ {margem_deste_plano:,.2f}"
        )
        if col_btn_saas.button("🗑️", key=f"excluir_plano_{assinatura.id}"):
            session.delete(assinatura)
            session.commit()
            st.rerun()

# =============================================================================
# ABA 6: AUDITORIA LEGAL E DUE DILIGENCE
# =============================================================================
with aba_legal_riscos:
    safe_image(
        "https://images.unsplash.com/photo-1589829085413-56de8ae18c73?q=80&w=1000&auto=format&fit=crop", 
        width="stretch"
    )
    st.header("⚖️ Due Diligence: Propriedade Intelectual e Proteção de Dados")
    st.info("Na avaliação final de um VC, falhas na custódia do código (INPI) e na definição do *Cap Table* (Vesting) são considerados Deal Breakers fatais.")

    with st.form("formulario_auditoria_legal"):
        col_jur1, col_jur2 = st.columns(2)
        
        status_inpi_software = col_jur1.selectbox(
            "Proteção Jurídica do Código e Algoritmos (INPI)", 
            [
                "Não Iniciado (Risco Iminente)", 
                "Processo de Código Fonte Depositado", 
                "Certificado Oficial de Software Emitido"
            ], 
            index=[
                "Não Iniciado", 
                "Código Depositado", 
                "Certificado Emitido"
            ].index(projeto.juridico.registro_inpi) if projeto.juridico.registro_inpi in ["Não Iniciado", "Código Depositado", "Certificado Emitido"] else 0
        )
        
        status_marca_comercial = col_jur2.selectbox(
            "Registo e Blindagem da Marca do Produto", 
            [
                "Não Iniciado (Vulnerabilidade de Uso)", 
                "Busca de Anterioridade Efectuada", 
                "Processo protocolado no INPI", 
                "Direito de Marca Concedido"
            ], 
            index=[
                "Não Iniciado", 
                "Busca Realizada", 
                "Processo em Andamento", 
                "Marca Concedida"
            ].index(projeto.juridico.marca_status) if projeto.juridico.marca_status in ["Não Iniciado", "Busca Realizada", "Processo em Andamento", "Marca Concedida"] else 0
        )

        col_jur3, col_jur4 = st.columns(2)
        
        validacao_lgpd = col_jur3.checkbox(
            "✅ O Sistema respeita as diretrizes de Privacidade por Design e a LGPD (Termos de Uso claros e ativos)", 
            value=projeto.juridico.adequacao_lgpd
        )
        
        validacao_vesting = col_jur4.checkbox(
            "✅ A Governança da Equipa Fundadora está segura mediante um Contrato de Vesting formal (Cliff estabelecido)", 
            value=projeto.juridico.contrato_vesting
        )

        honorarios_legais = st.number_input(
            "Honorários de Retenção e Assessoria DPO (Custo Mensal Corrente em R$)", 
            value=projeto.juridico.custo_estimado_legal
        )

        botao_atualizar_legal = st.form_submit_button("💾 Selar Auditoria no Data Room")
        
        if botao_atualizar_legal:
            dados_legais = projeto.juridico
            
            # Adaptação dos valores se estiverem mapeados de forma diferente no selectbox
            mapeamento_inpi = {
                "Não Iniciado (Risco Iminente)": "Não Iniciado",
                "Processo de Código Fonte Depositado": "Código Depositado",
                "Certificado Oficial de Software Emitido": "Certificado Emitido"
            }
            mapeamento_marca = {
                "Não Iniciado (Vulnerabilidade de Uso)": "Não Iniciado",
                "Busca de Anterioridade Efectuada": "Busca Realizada",
                "Processo protocolado no INPI": "Processo em Andamento",
                "Direito de Marca Concedido": "Marca Concedida"
            }
            
            dados_legais.registro_inpi = mapeamento_inpi.get(status_inpi_software, "Não Iniciado")
            dados_legais.marca_status = mapeamento_marca.get(status_marca_comercial, "Não Iniciado")
            dados_legais.adequacao_lgpd = validacao_lgpd
            dados_legais.contrato_vesting = validacao_vesting
            dados_legais.custo_estimado_legal = honorarios_legais
            
            session.commit()
            st.success("✅ As fragilidades de governança foram avaliadas e registadas.")
            st.rerun()

    st.markdown("---")
    st.subheader("Indicador Sintético de Imunidade e Compliance")
    
    testes_de_imunidade = {
        "O Código-Fonte Tecnológico está Patenteado e Salvo": projeto.juridico.registro_inpi != "Não Iniciado",
        "A Identidade do Produto não está vulnerável a Plágios": projeto.juridico.marca_status != "Não Iniciado",
        "A Base de Clientes está blindada segundo o RGPD/LGPD": projeto.juridico.adequacao_lgpd,
        "A Tabela de Sócios (Cap Table) está blindada com Vesting": projeto.juridico.contrato_vesting,
    }
    
    pontuacao_seguranca = sum(testes_de_imunidade.values())
    
    for criterio, resultado_ok in testes_de_imunidade.items(): 
        st.markdown(f"{'✅' if resultado_ok else '❌'} **{criterio}**")
        
    st.progress(
        pontuacao_seguranca / 4, 
        text=f"Maturidade Jurídica para o Fundo VC: {pontuacao_seguranca} de 4 requisitos superados com distinção"
    )

# =============================================================================
# ABA 7: ONE PAGER (RESUMO EXECUTIVO)
# =============================================================================
with aba_resumo_onepager:
    safe_image(
        "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?q=80&w=1000&auto=format&fit=crop", 
        width="stretch"
    )
    st.header("📄 Sumário Executivo — O *One-Pager* do Investidor")

    with st.expander("🧩 A Tese Central: Dor, Produto e Diferencial (Moat)", expanded=True):
        st.markdown(f"**O Core da Solução (A Proposta Única de Valor):**\n\n{safe_str(projeto.lean_canvas.proposta_valor)}")
        st.markdown(f"**A Barreira Contra a Concorrência (Vantagem Injusta):**\n\n{safe_str(projeto.lean_canvas.vantagem_injusta)}")
        st.markdown(f"**Repercussão Social Global (Normativas ODS):**\n\n{safe_str(projeto.lean_canvas.ods_onu)}")

    with st.expander("🔬 Operações de Validação: O MVP"):
        st.markdown(f"**Características Formais da Arquitetura:**\n\n{safe_str(projeto.lean_canvas.solucao_mvp)}")
        st.markdown(f"**Os Resultados Produzidos pela Prova de Conceito (Tração Tátil):**\n\n{safe_str(projeto.lean_canvas.mvp_descricao)}")

    with st.expander("💸 Síntese da Economia de Escala (SaaS)"):
        bloco_resumo_c1, bloco_resumo_c2, bloco_resumo_c3, bloco_resumo_c4 = st.columns(4)
        bloco_resumo_c1.metric("Capacidade Recorrente (MRR)", f"R$ {mrr_bruto_total_consolidado:,.2f}")
        bloco_resumo_c2.metric("Annual Recurring Revenue (ARR)", f"R$ {faturamento_anualizado_arr:,.2f}")
        bloco_resumo_c3.metric("Velocidade do Burn Rate", f"R$ {burn_rate_total_mensal:,.2f}/mês")
        bloco_resumo_c4.metric("Índice Multiplicador LTV/CAC", f"{indice_ltv_cac:.2f}x")

    with st.expander("⚖️ O Mapa de Riscos Passivos"):
        st.markdown(f"- **Conformidade do Código e Patentes (INPI):** {projeto.juridico.registro_inpi}  \n- **Consistência do Branding e Marca:** {projeto.juridico.marca_status}")
        st.markdown(f"- **Vulnerabilidade em Cibersegurança e Dados:** {'✅ Protocolo Validado' if projeto.juridico.adequacao_lgpd else '❌ Severamente Exposto'}  \n- **Segurança Estrutural do Acordo Acionista:** {'✅ Documento em Vigor' if projeto.juridico.contrato_vesting else '❌ A Sociedade Encontra-se Vulnerável'}")

# =============================================================================
# ABA 8: VALUATION E VIABILIDADE FINANCEIRA
# =============================================================================
with aba_viabilidade_vpl:
    safe_image(
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=1000&auto=format&fit=crop", 
        width="stretch"
    )
    st.header("📊 Inteligência Financeira: Valuation Baseado no *Cashflow*")

    col_val_1, col_val_2, col_val_3, col_val_4 = st.columns(4)
    
    col_val_1.metric(
        "Esforço Total em Capex (O Tamanho da Rodada)", 
        f"R$ {capex_total_apurado:,.2f}"
    )
    col_val_2.metric(
        "Geração Global de Riqueza Acumulada (O Valor Presente Líquido - VPL)", 
        f"R$ {valor_presente_liquido_vpl:,.2f}", 
        delta="Startup Validada com Geração de Valor" if valor_presente_liquido_vpl > 0 else "Operação Inviável que Destrói o Capital Alocado"
    )
    col_val_3.metric(
        "Retorno Base Projetado (Taxa Interna de Retorno - TIR)", 
        f"{taxa_interna_retorno_anual:,.2f}%" if validade_da_tir else "A Variável não pode ser Equacionada (Verifique Limitações de Caixa)", 
        delta=f"Custo Oportunidade do Dinheiro do Fundo: {premissas_atuais.tma_anual_pct}%"
    )
    col_val_4.metric(
        "Ponto de Retorno Efetivo do Fundo (Tempo de Payback)", 
        mes_de_breakeven_payback
    )

    st.plotly_chart(figura_cashflow_projetado, use_container_width=True)

    st.subheader("Auditabilidade Contabilística — Demonstrativo Linear de Caixa")
    tabela_demonstrativo_financeiro = pd.DataFrame({
        "Linha de Tempo Operacional": lista_rotulos_meses,
        "Curva de Faturação Recebida (MRR)": [f"R$ {rendimento:,.2f}" for rendimento in timeline_mrr_crescente],
        "Consolidação de Clientes Efetivos": [f"{int(quantidade_de_clientes):,}" for quantidade_de_clientes in timeline_usuarios_pagantes],
        "Reserva Contabilística (Caixa Líquido Residual)": [f"R$ {saldo_bancario:,.2f}" for saldo_bancario in serie_caixa_acumulado],
    })
    st.dataframe(tabela_demonstrativo_financeiro, use_container_width=True, height=280)

# =============================================================================
# ABA 9: DASHBOARD DE CUSTOS E UNIT ECONOMICS
# =============================================================================
with aba_dashboard_unit:
    safe_image(
        "https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=1000&auto=format&fit=crop", 
        width="stretch"
    )
    st.header("📉 Monitorização Cirúrgica de Unit Economics (SaaS)")

    if not projeto.planos_saas:
        st.warning("⚠️ Atenção à Análise: O ecossistema de métricas encontra-se inativo pois a estratégia e as camadas de *Pricing* ainda não foram homologadas na respetiva área (SaaS).")
    else:
        linha_kpi1_c1, linha_kpi1_c2, linha_kpi1_c3, linha_kpi1_c4 = st.columns(4)
        linha_kpi1_c1.metric("Massa Faturada Vigente (MRR)", f"R$ {mrr_bruto_total_consolidado:,.2f}", delta=f"Carga Sancionada por {int(usuarios_pagantes_totais_base)} Entidades Clientes")
        linha_kpi1_c2.metric("Estimativa de ARR Linear", f"R$ {faturamento_anualizado_arr:,.2f}")
        linha_kpi1_c3.metric("Sobrevivência da Margem Bruta de Operação", f"{margem_bruta_percentual:.1f}%")
        linha_kpi1_c4.metric("ARPU Efetivo (Retorno Financeiro Ponderado por Utilizador)", f"R$ {ticket_medio_arpu:,.2f}")

        linha_kpi2_c1, linha_kpi2_c2, linha_kpi2_c3, linha_kpi2_c4 = st.columns(4)
        status_caixa_texto = "Matriz Económica Superavitária ✓" if resultado_operacional_ebitda >= 0 else "Fluxos Críticos / Risco de Sangria 🔥"
        linha_kpi2_c1.metric("Geração Fria Operacional (EBITDA Adaptado)", f"R$ {resultado_operacional_ebitda:,.2f}", delta=status_caixa_texto, delta_color="normal" if resultado_operacional_ebitda >= 0 else "inverse")
        linha_kpi2_c2.metric("O Efeito Global do Burn Rate Efetivo", f"R$ {burn_rate_total_mensal:,.2f}/mês")
        
        if meses_runway_sobrevivencia: 
            linha_kpi2_c3.metric("Capacidade Funcional de Sobrevida (Runway)", f"{meses_runway_sobrevivencia:.1f} meses restantes", delta="Risco Severo de Queda do Projeto", delta_color="inverse")
        else: 
            linha_kpi2_c3.metric("Capacidade Funcional de Sobrevida (Runway)", "Infinitude e Escala de Segurança Total", delta="Superação Efetiva do Vale da Morte")
            
        texto_avaliacao_ltv = "🟢 Tracionamento Brilhante (Alto Padrão de Performance)" if indice_ltv_cac >= 3 else ("🟡 Marginalmente Eficiente (Exige Atenção a Curto Prazo)" if indice_ltv_cac >= 1 else "🔴 Ineficiência Financeira Brutal (Marketing Custa Mais do que Produz)")
        linha_kpi2_c4.metric("Potência Algorítmica de Retenção e Escala (LTV / CAC)", f"{indice_ltv_cac:.2f}x", delta=texto_avaliacao_ltv)

        st.markdown("---")

        linha_kpi3_c1, linha_kpi3_c2, linha_kpi3_c3, linha_kpi3_c4 = st.columns(4)
        linha_kpi3_c1.metric("Valor Gasto Integral na Captação de um Indivíduo (CAC)", f"R$ {cac_aquisicao_mercado:,.2f}")
        linha_kpi3_c2.metric("Rentabilidade Extraída Vitaliciamente (LTV)", f"R$ {ltv_vitalicio_cliente:,.2f}")
        linha_kpi3_c3.metric("Fugas e Abandono Estimado na Base (Churn)", f"{premissas_atuais.churn_mensal_pct:.1f}% ao Mês")
        
        if meses_payback_cac:
            linha_kpi3_c4.metric("Lapsos Mensais para Retorno de CAC (Payback Marketing)", f"{meses_payback_cac:.1f} Períodos Faturados")
        else:
            linha_kpi3_c4.metric("Ciclos Necessários para Recuperar o CAC", "Incalculável (Verifique as Constantes Inseridas)")

        st.markdown("---")

        bloco_graficos_l, bloco_graficos_r = st.columns(2)
        with bloco_graficos_l:
            st.markdown("**Segmentação Matemática das Hemorragias Contínuas (Rate de Queima)**")
            st.plotly_chart(figura_pizza_custos, use_container_width=True)
            
        with bloco_graficos_r:
            st.markdown("**Crescimento do Momentum (Curvas de Ascensão de Base versus Receita)**")
            st.plotly_chart(figura_mrr_tracao, use_container_width=True)

        st.markdown("---")
        st.subheader("📃 Demonstrativo Direto de Resultados (DRE de Sobrevida Software)")

        linhas_comprovativas_da_dre = [
            ("(+) Aceleração Integral Faturada (MRR Global)", mrr_bruto_total_consolidado, False),
            ("(-) Custo Imediato na Transação e Peso Fiscal", -despesas_deducoes_base, True),
            ("(=) Sobra Transitória (Líquido Transacionado)", mrr_liquido_apurado_base, False),
            ("(-) Faturas Recorrentes Pela Computação em Nuvem (COGS)", -despesas_nuvem_cogs_base, True),
            ("(=) Margem Pura Associada ao Sistema de Software", mrr_liquido_apurado_base - despesas_nuvem_cogs_base, False),
            ("(-) Encargos Relativos a Funcionários, Legalidades e Posição (Opex)", -opex_fixo_mensal, True),
            ("(=) Fundo Final Operacional Resultante (Bottom Line Total)", resultado_operacional_ebitda, False),
        ]
        
        for denominacao_linha, montante_calculado, representacao_negativa in linhas_comprovativas_da_dre:
            linha_totalizadora = denominacao_linha.startswith("(=)")
            cor_do_fundo_painel = "#F1F5F9" if linha_totalizadora else "transparent"
            espessura_da_letra = "700" if linha_totalizadora else "400"
            coloracao_dos_numeros = ("#DC2626" if representacao_negativa else ("#16A34A" if linha_totalizadora and montante_calculado >= 0 else "#0F172A"))
            
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;padding:10px 14px;'
                f'background:{cor_do_fundo_painel};border-radius:8px;font-weight:{espessura_da_letra};margin-bottom:6px;'
                f'border: 1px solid #E2E8F0;">'
                f'<span>{denominacao_linha}</span>'
                f'<span style="color:{coloracao_dos_numeros}">R$ {montante_calculado:,.2f}</span></div>',
                unsafe_allow_html=True
            )

# =============================================================================
# ABA 10: O CÉREBRO ARTIFICIAL (MENTORIA VC GEMINI)
# =============================================================================
with aba_mentor_vc:
    safe_image(
        "https://images.unsplash.com/photo-1677442136019-21780ecad995?q=80&w=1000&auto=format&fit=crop", 
        width="stretch"
    )
    st.header("🤖 Fundo Inteligente: Comité de Avaliação Virtual Assistido")
    st.info(
        "O Modelo Gemini foi configurado para adotar a identidade de um Membro Sênior de um Conselho de Fundo Privado (Venture Capital). "
        "A análise procurará desconstruir ativamente as hipóteses, encontrando as brechas tecnológicas e as ilusões nos Unit Economics. Submeta-se ao questionário duro do mercado."
    )

    if not GEMINI_AVAILABLE:
        st.error("⚠️ Foi observada a ausência de infraestrutura conectiva. Exige que a biblioteca `google-genai` esteja plenamente operacional.")
    else:
        chave_api_usuario = st.text_input("Credenciais Seguras: Coloque a Palavra-passe da API Gemini:", type="password", key="gemini_key_widget")

        if st.button("🚀 Submeter Todo o Prospecto de Operações aos Avaliadores", type="primary"):
            if not st.session_state.get("gemini_key_widget"):
                st.warning("⚠️ Bloqueio Preventivo: Uma chave de autenticação Google válida é vital para desbloquear o algoritmo de raciocínio profundo.")
            else:
                with st.spinner("A transmitir a carga documental para a inteligência na rede. A proceder à intersecção dos Unit Economics com o grau de risco jurídico apresentado..."):
                    
                    prompt_para_o_mentor = f"""Assuma o papel de um Venture Capitalist Sênior ou Investidor Anjo analisando uma startup de tecnologia (SaaS/App) para uma possível rodada de captação (Seed/Series A) no Demoday.
A sua tarefa é fazer a Due Diligence do Pitch Deck da startup descrita abaixo com o rigor técnico e financeiro de um fundo de investimento real.

<projeto_startup>
Nome da Operação: {projeto.nome_startup}
Dores de Mercado (Problema): {safe_str(projeto.lean_canvas.problema)}
Arquitetura Tecnológica e MVP: {safe_str(projeto.lean_canvas.solucao_mvp)}
Relatório da Tração (Prova de Conceito): {safe_str(projeto.lean_canvas.mvp_descricao)}
Proposta Única de Valor Global: {safe_str(projeto.lean_canvas.proposta_valor)}
O Fosso Competitivo (Moat/Vantagem): {safe_str(projeto.lean_canvas.vantagem_injusta)}
ESG e Compliance Social ODS: {safe_str(projeto.lean_canvas.ods_onu)}
</projeto_startup>

<unit_economics>
Receita Recorrente Consolidada (MRR): R$ {mrr_bruto_total_consolidado:,.2f}
Teto de Receita Atual (ARR): R$ {faturamento_anualizado_arr:,.2f}
Queima de Caixa Consolidada (Burn Rate): R$ {burn_rate_total_mensal:,.2f}/mês
EBITDA Mensal: R$ {resultado_operacional_ebitda:,.2f}
Proporção Mágica de Escala (LTV/CAC): {indice_ltv_cac:.2f}x (Benchmark de corte: 3x para Série A)
Tempo Restante de Caixa Livre (Runway): {f"{meses_runway_sobrevivencia:.1f} meses até a falência" if meses_runway_sobrevivencia else "Empresa operando no azul (Lucratividade alcançada)"}
Evasão de Base (Churn Mensal): {premissas_atuais.churn_mensal_pct:.1f}%
Custo Nominal de Aquisição (CAC): R$ {cac_aquisicao_mercado:,.2f}
Margem Bruta (Ex-Infra): {margem_bruta_percentual:.1f}%
</unit_economics>

<passivos_e_compliance>
Patente Tecnológica (INPI): {projeto.juridico.registro_inpi}
Privacidade por Design (LGPD): {"Auditoria Conforme" if projeto.juridico.adequacao_lgpd else "Auditoria Reprovada"}
Acordo Societário (Vesting): {"Formalizado e Resguardado" if projeto.juridico.contrato_vesting else "Irregular"}
</passivos_e_compliance>

A sua devolução de feedback deve ser perfeitamente formatada em Markdown, utilizando os seguintes blocos obrigatórios de resposta:
## 1. Tese de Investimento Global
(Você aprovaria o aporte de capital neste negócio? A dor mapeada é profunda e o mercado é grande o suficiente para uma saída (exit) lucrativa?)

## 2. Radiografia dos Unit Economics e Valuation
(Faça uma auditoria crítica dos números. O MRR justifica o valuation esperado? O Burn Rate é sustentável em relação ao Runway? Faça um apontamento incisivo sobre a relação de LTV e CAC.)

## 3. Viabilidade Técnica e Escala
(A arquitetura do MVP permite ganho de escala (scale-up) sem gargalos operacionais massivos? A Vantagem Injusta protege a empresa de copycats?)

## 4. Due Diligence de Compliance e Riscos
(Examine as ameaças de proteção de dados e LGPD, os processos de registro no INPI e o acordo de Vesting. Há passivos que afugentariam um fundo de VC?)

## 5. Veredito do Comitê de Investimento e Próximos Passos
(Dê o veredito final: "Aprovado para Term Sheet", "Requer Ajustes (Watchlist)" ou "Recusado Formalmente". Liste 3 ações corretivas operacionais imediatas e implacáveis para os founders melhorarem a tração antes da próxima rodada institucional.)
"""
                    try:
                        conector_algoritmo = _genai.Client(api_key=st.session_state.gemini_key_widget)
                        saida_do_modelo = conector_algoritmo.models.generate_content(
                            model="gemini-2.5-flash", 
                            contents=prompt_para_o_mentor
                        )
                        st.session_state["parecer_ia"] = saida_do_modelo.text
                        st.success("✅ A Carta Documental de Fundamentos do Fundo Privado encontra-se processada na totalidade e cristalizada no servidor. Visite a Aba Final de Exportação para o selo final num dossiê.")
                    except Exception as erro_da_chamada_remota:
                        st.error(f"Erro Perturbador na Linha de Redes e Nós Computacionais (Protocolo Google): {erro_da_chamada_remota}")

    if st.session_state["parecer_ia"]:
        st.markdown("---")
        st.markdown(st.session_state["parecer_ia"])

# =============================================================================
# ABA 12: MOTOR EXPORTADOR DA DATA ROOM (DOCUMENTAÇÃO PDF)
# =============================================================================
with aba_pdf_export:
    safe_image(
        "https://images.unsplash.com/photo-1618044733300-9472054094ee?q=80&w=1000&auto=format&fit=crop", 
        width="stretch"
    )
    st.header("🖨️ A Data Room Segura: Exportação Dossiê do Demoday")
    st.info("Plataforma primária de encapsulamento criptográfico do Prospecto Organizacional de Negócios. O Dossiê abarca uma integração das métricas profundas recolhidas ao longo de todas as tabelas em união indissociável ao parecer de risco do comité institucional (IA).")

    caixa_interativa_de_revisao_do_comite = st.text_area(
        "Edição da Carta Parecer Oficial (Os registos abaixo transitam da memória permanente originada na análise IA):",
        value=st.session_state["parecer_ia"], 
        height=250,
    )

    if st.button("🚀 Extrair e Materializar Prospecto Exclusivo (Formatação PDF)", type="primary"):
        try:
            with st.spinner("Processos Cíclicos Iniciados: O construtor gráfico opera neste momento varrimentos das estruturas plotáveis para as injetar perfeitamente limpas num canvas imutável PDF de folha A4. Operações pesadas exigem tolerância ao compasso temporal..."):
                
                familia_tipografica = "helvetica"
                motor_escritor_de_pdf = FPDF()
                motor_escritor_de_pdf.set_auto_page_break(auto=True, margin=15)

                if os.path.exists(_FONTE_PATH):
                    motor_escritor_de_pdf.add_font("DejaVu", "",  _FONTE_PATH)
                    motor_escritor_de_pdf.add_font("DejaVu", "B", _FONTE_PATH)
                    familia_tipografica = "DejaVu"

                # Blocos padronizados de tipografia para o construtor PDF
                def FormatarTituloGrossoH1(texto_escrito):
                    motor_escritor_de_pdf.set_font(familia_tipografica, "B", 18)
                    motor_escritor_de_pdf.cell(motor_escritor_de_pdf.epw, 12, texto_escrito, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                    motor_escritor_de_pdf.line(
                        motor_escritor_de_pdf.l_margin, 
                        motor_escritor_de_pdf.get_y(), 
                        motor_escritor_de_pdf.w - motor_escritor_de_pdf.r_margin, 
                        motor_escritor_de_pdf.get_y()
                    )
                    motor_escritor_de_pdf.ln(5)

                def FormatarSubtitulosElegantesH2(texto_escrito):
                    motor_escritor_de_pdf.set_font(familia_tipografica, "B", 14)
                    motor_escritor_de_pdf.cell(motor_escritor_de_pdf.epw, 9, texto_escrito, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                    motor_escritor_de_pdf.ln(2)

                def EscreverParagrafoNarrativo(texto_escrito):
                    motor_escritor_de_pdf.set_font(familia_tipografica, "", 11)
                    motor_escritor_de_pdf.multi_cell(motor_escritor_de_pdf.epw, 7, safe_str(texto_escrito))
                    motor_escritor_de_pdf.ln(4)

                # ==================================
                # COMPOSIÇÃO DE FOLHA DE ROSTO (PÁGINA 1)
                # ==================================
                motor_escritor_de_pdf.add_page()
                motor_escritor_de_pdf.ln(45)
                motor_escritor_de_pdf.set_font(familia_tipografica, "B", 32)
                motor_escritor_de_pdf.cell(motor_escritor_de_pdf.epw, 20, "MEMORANDO DE INVESTIMENTO DA SOCIEDADE", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
                motor_escritor_de_pdf.set_font(familia_tipografica, "B", 22)
                motor_escritor_de_pdf.cell(motor_escritor_de_pdf.epw, 15, projeto.nome_startup.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
                motor_escritor_de_pdf.ln(15)
                
                motor_escritor_de_pdf.set_font(familia_tipografica, "", 14)
                indicadores_cardeais_da_capa = [
                    f"Índice Formal de Carga ARR Prevista (Aualizado): R$ {faturamento_anualizado_arr:,.2f}",
                    f"Constância Mensal Pura Recolhida Vigente MRR: R$ {mrr_bruto_total_consolidado:,.2f}",
                    f"Relação de Alavancagem Saudável Adquirida Escalar (LTV/CAC): {indice_ltv_cac:.2f}x",
                    f"Estudo Matemático Associado e Direcionado Para Lucratividade Limpa Exigida (Breakeven): {mes_de_breakeven_payback}",
                    f"Valor Acumulado Previsto em Prejuízos Previsíveis a Consumir Capital Necessário Fornecido (Capex Rodada): R$ {capex_total_apurado:,.2f}"
                ]
                
                for sintese_indicadora in indicadores_cardeais_da_capa:
                    motor_escritor_de_pdf.cell(motor_escritor_de_pdf.epw, 10, sintese_indicadora, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

                # ==================================
                # DOCUMENTAÇÃO ESTRUTURADA (PÁGINA 2)
                # ==================================
                motor_escritor_de_pdf.add_page()
                FormatarTituloGrossoH1("I. Análise Exploratória e Condensada dos Verticais de Negócios (A Estrutura Lean Canvas)")
                
                repositorio_da_matriz = [
                    ("Disfunções, Ruídos Inoperáveis e Falhas Identificadas Num Enorme Grupo Económico:", projeto.lean_canvas.problema),
                    ("Arquitetura e Fundamentação Inicial Tecnológica Mapeada Perante Clientes (MVP):", projeto.lean_canvas.solucao_mvp),
                    ("Comprovação Numérica Associativa à Apresentação do Produto Mapeado (A Prova Funcional Limpa):", projeto.lean_canvas.mvp_descricao),
                    ("Argumento Impecável de Resolução Sistémica Associada a Lucros Radicais de Longa Duração (A Missão Principal):", projeto.lean_canvas.proposta_valor),
                    ("Moat / Fosso Exclusivo / Monopólio Relativo e Definitivo em Inserção Num Nicho Concorrencial Cruel:", projeto.lean_canvas.vantagem_injusta),
                    ("Canais Expansivos de Inclusão Maciça (Go-To-Market):", projeto.lean_canvas.canais),
                    ("Bússola Diretiva ESG / ODS:", projeto.lean_canvas.ods_onu)
                ]
                
                for grande_tema, o_grande_conteudo in repositorio_da_matriz:
                    FormatarSubtitulosElegantesH2(grande_tema)
                    EscreverParagrafoNarrativo(o_grande_conteudo)

                # ==================================
                # ALOCAÇÃO LEGISLATIVA DO FUNDO (PÁGINA 3)
                # ==================================
                motor_escritor_de_pdf.add_page()
                FormatarTituloGrossoH1("II. Due Diligence Cautelar Legal, Dispersão do Capex Demandado e Custos Radicais Constantes")
                
                EscreverParagrafoNarrativo(f"Proteção das Propriedades Imateriais e Intelectuais Exclusivas (Norma INPI e Registo Rigoroso de Autoria Pura Operacional Perante Regra Vigente do Software): {projeto.juridico.registro_inpi}\n\n"
                                 f"Exposição Formal de Identidade Comercial face a Cópia Barata Global (A Regra Prática para Manutenção Segura e Rastreável Contínua do Signo da Marca): {projeto.juridico.marca_status}\n\n"
                                 f"Aderência ao Corpo Restritivo Multibilionário Europeu, Regional e Ferozmente Agressivo face à Informação do Cliente Protegida (Compliance Pleno da Legislação Geral de Proteção Segura Exaustiva LGPD e RGPD): {'Processo Exigente Aprovado sem Ressalvas Documentais.' if projeto.juridico.adequacao_lgpd else 'Dossier Pendente; Ação Imediata Mandatória é Claramente Imprescindível para o Avanço.'}\n\n"
                                 f"Cimento Societário Institucional Face ao Eventual Fuga Maciça Súbita, Morte ou Afastamento Ilimitado Indesejável do Talento Superior Criativo Originário (A Existência Contratual Formal de Termos Exclusivos Complexos de Acordo de Quotistas Denominado Vastamente Como Vesting): {'Processo Efetivamente Formalizado nos Termos.' if projeto.juridico.contrato_vesting else 'Alerta Brutal Perigoso Assinalado nos Termos.'}")
                
                motor_escritor_de_pdf.ln(5)
                FormatarSubtitulosElegantesH2("Destinação Rigorosa e Tática de Todo O Recurso de Demanda de Captação Previsto Incial do Caixa Mapeado Fundo Inicial (As Linhas Contratuais Fundamentais do Capex Inicial Seed Pre-Seed):")
                for dado_capex in projeto.investimentos: 
                    EscreverParagrafoNarrativo(f"• Alocação Obrigatória e Restrita Associada a Área de {dado_capex.categoria}: {dado_capex.descricao} — Aporte Integral Total Requisitado: Montante Total em R$ {dado_capex.valor:,.2f}")
                
                motor_escritor_de_pdf.ln(5)
                FormatarSubtitulosElegantesH2("Necessidades Primárias Correntes Sucedidas Associativas Imbricadas À Passagem Meses Que Constituem Uma Base Sólida para Efeito Do Queima Mensal Constante (Despesas Periódicas de Base Pura Opex Operacional Global):")
                for dado_opex in projeto.custos_fixos: 
                    EscreverParagrafoNarrativo(f"• Risco de Orçamento Fixado Contínuo Mês Após Mês Relativamente A Matéria Designada Por {dado_opex.categoria}: Detalhe Transparente Corrente de {dado_opex.descricao} — Pagamento Assumido Exigido Fixo Associado: Perda Contínua Assumida de Valores Correspondentes na Ordem de R$ {dado_opex.valor_mensal:,.2f} a serem pagos fixos e impreteríveis/mês")

                # ==================================
                # IMAGENS REAIS GRÁFICAS PROCESSADAS DA VIABILIDADE (PÁGINA 4 E SEGUINTES)
                # ==================================
                bytes_cashflow_processados = fig_to_bytes(figura_cashflow_projetado)
                if bytes_cashflow_processados:
                    motor_escritor_de_pdf.add_page()
                    FormatarTituloGrossoH1("III. Viabilidade Financeira Acumulada E Visualização Lógica Constatável Exata Perante Toda a Geometria Exaustiva Associada Fria Ao Horizonte Lúgubre Cruel Corrente Denominado Conhecidamente Como O Famoso Vale Da Morte Inicial.")
                    motor_escritor_de_pdf.image(io.BytesIO(bytes_cashflow_processados), x=motor_escritor_de_pdf.l_margin, w=motor_escritor_de_pdf.epw)
                    motor_escritor_de_pdf.ln(10)

                bytes_da_pizza_de_distribuicao = fig_to_bytes(figura_pizza_custos)
                bytes_da_subida_estrondosa_de_clientes_mrr = fig_to_bytes(figura_mrr_tracao)
                
                if bytes_da_pizza_de_distribuicao or bytes_da_subida_estrondosa_de_clientes_mrr:
                    motor_escritor_de_pdf.add_page()
                    FormatarTituloGrossoH1("IV. Dashboard de Demonstrações Frias e Projeções das Trações E Esmagamento Extensivo de Exposição de Expansão Global Perfeita Mapeada Dos Relatórios Profundos Associados À Metodologia e Escala Contínua Extensiva Exata Mapeada (Os Unit Economics Essenciais Frios Assinalados Pela Nuvem Mapeada SaaS Global).")
                    
                    ponto_medio_calculado = motor_escritor_de_pdf.epw / 2 - 5
                    
                    if bytes_da_subida_estrondosa_de_clientes_mrr: 
                        FormatarSubtitulosElegantesH2("Curva Agressiva Exata Ponderada Crescente Relativamente à Base de Assinantes vs Valor Angariado Progressivo Adstrito Resultante das Curvas Mapeadas Expansivas Inesperadas Ascendentes Faturadas do Modelo Adquirido Corrente Lógico (MRR Growth Exato Acumulativo de Expansão):")
                        motor_escritor_de_pdf.image(io.BytesIO(bytes_da_subida_estrondosa_de_clientes_mrr), x=motor_escritor_de_pdf.l_margin, w=motor_escritor_de_pdf.epw)
                        motor_escritor_de_pdf.ln(15)
                        
                    if bytes_da_pizza_de_distribuicao: 
                        FormatarSubtitulosElegantesH2("Efeito Global Constatável e Inequívoco Evidenciado Exatamente Nas Condições Presentes Globais Da Dispersão Efetiva Esvaziada Análisa Relativamente A Geometria Total Assumida Do Constante, Previsível E Famosamente Reconhecido Desastre De Sangria de Fundo Do Sangrento e Temido Valor Do Custo Permanente Crucial Associado Contínuo Mapeado (Burn Rate Geral Mapeado Mensal Permanente Extensivo Distribuído Cruamente Onde O Dinheiro É Perdido):")
                        motor_escritor_de_pdf.image(io.BytesIO(bytes_da_pizza_de_distribuicao), x=motor_escritor_de_pdf.l_margin + ponto_medio_calculado // 2, w=ponto_medio_calculado)

                # ==================================
                # INCLUSÃO FINAL INEXORÁVEL ESCRITA EM PAPEL DO RESULTADO DURO E SECO RECOLHIDO E COMPLETO COM INSERÇÕES ESTATÍSTICAS MATEMÁTICAS PROFUNDAS E EMANADAS DA CRUELDADE FINA ASSINALADA (O LAUDO OFICIAL DO ALGORITMO IA) (PÁGINA FINAL ESCRITA ÚLTIMA DE FUNDAMENTO ÚLTIMO)
                # ==================================
                if caixa_interativa_de_revisao_do_comite:
                    motor_escritor_de_pdf.add_page()
                    FormatarTituloGrossoH1("V. Veredito Assumido Superior Intransigente Oficial Associativo Frio Ao Desfecho Avaliativo do Crivo Absoluto Do Comité Total de Investimento Mapeado Do Sistema Artificial IA Emissão Emitida Perante Regra Mapeada Extensiva Conclusiva Associada De Sentença Final.")
                    motor_escritor_de_pdf.set_font(familia_tipografica, "", 12)
                    
                    # Limpeza de formatações Markdown que podem corromper a FPDF
                    texto_ia_purificado = caixa_interativa_de_revisao_do_comite.replace("•", "-").replace("·", "-").replace("**", "")
                    motor_escritor_de_pdf.multi_cell(motor_escritor_de_pdf.epw, 7, texto_ia_purificado)

                # Compilação Final Exata
                saida_pdf_bytes_absolutos_reais = bytes(motor_escritor_de_pdf.output())
                st.success("✅ A Plataforma exportou com sucesso inexorável pleno e irrevogável o documento tático e puramente criptográfico e profundo final exigente que descreve a alma dura exata inteira do negócio perante a realidade bruta das operações.")
                st.download_button(
                    "📥 Efetuar o Download Categórico e Absoluto Do Prospecto Term Sheet do Dossiê Do Fundo (.pdf Livre de Imposições Formais e Perfeitas Limpo Exato)", 
                    data=saida_pdf_bytes_absolutos_reais, 
                    file_name=f"TermSheet_Prospecto_Duro_De_{projeto.nome_startup.replace(' ', '_')}.pdf", 
                    mime="application/pdf"
                )
        except Exception as falha_bruta_profunda_de_geracao_sistema_inviabilizador:
            st.error(f"Erro Sistémico Crítico Imprevisível Incorreto Falho De Origem Pura Detetado Com Segurança e Transparência Diretamente Reveladora Na Base Crua da Tábua Renderizadora Operacional Local Exata do Construtor de Ficheiros Associada: {falha_bruta_profunda_de_geracao_sistema_inviabilizador}")