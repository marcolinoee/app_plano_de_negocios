# =============================================================================
# MASTER MANAGEMENT - VENTURE CAPITAL EDITION
# Copyright (c) 2026 - Prof. [Seu Nome] - [Nome da Instituição]
#
# AVISO LEGAL: Este código-fonte é propriedade intelectual do autor.
# É estritamente proibido o uso comercial, reprodução não autorizada,
# ou venda. Licenciado exclusivamente para fins didáticos e académicos
# na disciplina de Empreendedorismo/TIC.
# =============================================================================

import gc
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

# ── Modelos do Banco de Dados e Núcleo Multi-Tenant SaaS ──────────────────────
from banco_dados import (
    engine as _engine_local,
    session as _legacy_session,
    ProjetoDB,
)
from backend import (
    AnaliseIAEBT,
    AssinaturaTenant,
    ClienteEBT,
    ErroIsolamentoTenant,
    ErroLimitePlanoSaaS,
    ErroPermissaoRBAC,
    ItemCapexEBT,
    ItemOpexEBT,
    JobAssincronoSaaS,
    JuridicoEBT,
    LeanCanvasEBT,
    Membership,
    PapelMembro,
    PermissaoSaaS,
    PlanoAssinaturaCodigo,
    PlanoSaaSEBT,
    PremissasEBT,
    ProvedorAuditoriaDeterministicoIA,
    ProvedorGeminiIA,
    RelatorioDossieEBT,
    ResultadoSimulacaoEBT,
    StorageDossieLocal,
    Tenant,
    User,
    VersaoPremissasEBT,
    alterar_plano_assinatura_tenant,
    atualizar_premissas_ebt,
    construir_prompt_vc_governado,
    criar_engine_saas,
    criar_link_compartilhamento_investidor,
    criar_tenant_consultoria,
    criar_workspace_ebt,
    executar_e_versionar_simulacao_ebt,
    gerar_ddl_rls_postgresql,
    inicializar_banco_saas,
    listar_jobs_tenant,
    listar_trilha_auditoria,
    listar_workspaces_ebt_visiveis,
    obter_ou_criar_uso_mensal,
    registrar_emissao_dossie_pdf,
    registrar_evento_auditoria,
    revisar_e_aprovar_parecer_ia,
    sanitizar_pii_texto,
    solicitar_parecer_ia_governado,
    validar_token_investidor,
    verificar_permissao_rbac,
)
from core_financeiro import (
    EntradaSimulacaoSaaS,
    SeveridadeAlerta,
    TipoCenario,
    executar_simulacao_saas,
    simular_cenarios_padrao,
    simular_monte_carlo,
)

@st.cache_resource
def _obter_session_factory_saas_v3():
    try:
        _legacy_session.rollback()
        _legacy_session.close()
    except Exception:
        pass
    gc.collect()
    _engine_local.dispose()
    db_url_env = os.getenv("DATABASE_URL")
    if db_url_env:
        engine_alvo = criar_engine_saas(db_url_env)
        return inicializar_banco_saas(engine_alvo, classe_projeto_legado=None)
    return inicializar_banco_saas(_engine_local, classe_projeto_legado=ProjetoDB)

if "_db_session_ativa" in st.session_state:
    try:
        st.session_state["_db_session_ativa"].rollback()
        st.session_state["_db_session_ativa"].close()
    except Exception:
        pass
gc.collect()
_SESSION_FACTORY_SAAS = _obter_session_factory_saas_v3()
session = _SESSION_FACTORY_SAAS()
st.session_state["_db_session_ativa"] = session

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
# SIDEBAR — GERENCIADOR MULTI-TENANT (CONSULTORIA, RBAC & WORKSPACES EBT)
# =============================================================================
with st.sidebar:
    safe_image(
        "https://images.unsplash.com/photo-1555066931-4365d14bab8c?q=80&w=1000&auto=format&fit=crop", 
        width="stretch"
    )
    st.title("🏢 Núcleo Multi-Tenant SaaS")

    # 1. Seleção da Consultoria (Tenant)
    session.info["bypass_rls"] = True
    todos_tenants = session.query(Tenant).filter(Tenant.ativo.is_(True)).order_by(Tenant.criado_em.asc()).all()

    if "tenant_atual_id" not in st.session_state or st.session_state["tenant_atual_id"] not in [t.id for t in todos_tenants]:
        st.session_state["tenant_atual_id"] = todos_tenants[0].id

    opcoes_tenants = {t.id: f"{t.nome} ({t.slug})" for t in todos_tenants}
    tenant_selecionado_id = st.selectbox(
        "Consultoria (Tenant):",
        options=list(opcoes_tenants.keys()),
        format_func=lambda tid: opcoes_tenants[tid],
        index=list(opcoes_tenants.keys()).index(st.session_state["tenant_atual_id"]),
    )
    if tenant_selecionado_id != st.session_state["tenant_atual_id"]:
        st.session_state["tenant_atual_id"] = tenant_selecionado_id
        st.session_state.pop("membership_atual_id", None)
        st.session_state.pop("projeto_atual_id", None)
        st.session_state["parecer_ia"] = ""
        st.rerun()

    tenant_ativo = session.get(Tenant, st.session_state["tenant_atual_id"])
    assinatura_ativa = (
        session.query(AssinaturaTenant)
        .filter(AssinaturaTenant.tenant_id == tenant_ativo.id)
        .first()
    )

    # 2. Seleção de Perfil de Acesso (RBAC)
    memberships_do_tenant = (
        session.query(Membership)
        .filter(Membership.tenant_id == tenant_ativo.id, Membership.ativo.is_(True))
        .all()
    )
    if "membership_atual_id" not in st.session_state or st.session_state["membership_atual_id"] not in [m.id for m in memberships_do_tenant]:
        st.session_state["membership_atual_id"] = memberships_do_tenant[0].id

    opcoes_memberships = {}
    for m in memberships_do_tenant:
        usr = session.get(User, m.user_id)
        nome_usr = usr.nome_completo if usr else m.user_id[:8]
        opcoes_memberships[m.id] = f"[{m.papel.upper()}] {nome_usr}"

    membership_selecionada_id = st.selectbox(
        "🔐 Papel RBAC Ativo:",
        options=list(opcoes_memberships.keys()),
        format_func=lambda mid: opcoes_memberships[mid],
        index=list(opcoes_memberships.keys()).index(st.session_state["membership_atual_id"]),
    )
    if membership_selecionada_id != st.session_state["membership_atual_id"]:
        st.session_state["membership_atual_id"] = membership_selecionada_id
        st.rerun()

    membership_ativa = session.get(Membership, st.session_state["membership_atual_id"])

    # Ativa o isolamento RLS por Tenant na sessão a partir deste ponto
    session.info["bypass_rls"] = False
    session.info["tenant_id"] = tenant_ativo.id
    session.info["user_id"] = membership_ativa.user_id

    if assinatura_ativa:
        total_ebts_tenant = session.query(ClienteEBT).filter(ClienteEBT.ativo.is_(True)).count()
        st.caption(
            f"📦 Plano **{assinatura_ativa.plano_codigo.upper()}** · "
            f"EBTs: **{total_ebts_tenant}/{assinatura_ativa.limite_ebts}** · "
            f"Papel: **`{membership_ativa.papel}`**"
        )

    with st.expander("➕ Nova Consultoria (Onboarding Tenant)"):
        with st.form("form_novo_tenant", clear_on_submit=True):
            nome_nova_cons = st.text_input("Nome da Consultoria")
            slug_nova_cons = st.text_input("Identificador (slug, ex: nordeste-vc)")
            email_dono_cons = st.text_input("E-mail do Dono", value="diretor@consultoria.com")
            plano_nova_cons = st.selectbox(
                "Plano SaaS",
                options=[
                    PlanoAssinaturaCodigo.FREE,
                    PlanoAssinaturaCodigo.STARTER,
                    PlanoAssinaturaCodigo.PRO,
                    PlanoAssinaturaCodigo.ENTERPRISE,
                ],
                format_func=lambda p: "FREE (Gratuito)" if p == PlanoAssinaturaCodigo.FREE else p.value.upper(),
                index=0,
            )
            btn_criar_tenant = st.form_submit_button("Criar Consultoria")
            if btn_criar_tenant and nome_nova_cons and slug_nova_cons:
                try:
                    session.info["bypass_rls"] = True
                    novo_t, _, novo_m = criar_tenant_consultoria(
                        session,
                        nome_consultoria=nome_nova_cons,
                        slug=slug_nova_cons,
                        email_dono=email_dono_cons,
                        nome_dono=f"Dono {nome_nova_cons}",
                        plano=plano_nova_cons,
                    )
                    criar_workspace_ebt(
                        session,
                        membership=novo_m,
                        nome_startup=f"Primeira EBT - {nome_nova_cons}",
                    )
                    session.commit()
                    st.session_state["tenant_atual_id"] = novo_t.id
                    st.session_state["membership_atual_id"] = novo_m.id
                    st.session_state.pop("projeto_atual_id", None)
                    st.success("Consultoria criada com sucesso!")
                    st.rerun()
                except Exception as exc_tenant:
                    session.rollback()
                    st.error(f"Erro ao criar consultoria: {exc_tenant}")

    st.markdown("---")
    st.subheader("📂 Workspaces EBT")

    # 3. Leitura das EBTs visíveis conforme escopo RBAC
    todos_projetos = listar_workspaces_ebt_visiveis(session, membership=membership_ativa)
    if not todos_projetos:
        todos_projetos = session.query(ClienteEBT).all()

    if "projeto_atual_id" not in st.session_state:
        st.session_state["projeto_atual_id"] = todos_projetos[0].id

    ids_existentes = [p.id for p in todos_projetos]
    if st.session_state["projeto_atual_id"] not in ids_existentes:
        st.session_state["projeto_atual_id"] = ids_existentes[0]

    opcoes_projetos = {p.id: p.nome_startup for p in todos_projetos}
    projeto_selecionado_id = st.selectbox(
        "Startup (Workspace EBT):", 
        options=list(opcoes_projetos.keys()), 
        format_func=lambda x: opcoes_projetos[x], 
        index=list(opcoes_projetos.keys()).index(st.session_state["projeto_atual_id"])
    )
    
    if projeto_selecionado_id != st.session_state["projeto_atual_id"]:
        st.session_state["projeto_atual_id"] = projeto_selecionado_id
        st.session_state["parecer_ia"] = ""
        st.rerun()

    st.markdown("---")

    # 4. Criar Novo Workspace EBT (com validação RBAC e Limite de Plano)
    with st.form("form_novo_proj", clear_on_submit=True):
        novo_nome_startup = st.text_input("Nome da Nova Operação (EBT)")
        botao_nova_startup = st.form_submit_button("➕ Criar Startup")
        
        if botao_nova_startup and novo_nome_startup:
            try:
                nova_startup = criar_workspace_ebt(
                    session,
                    membership=membership_ativa,
                    nome_startup=novo_nome_startup,
                )
                session.commit()
                st.session_state["projeto_atual_id"] = nova_startup.id
                st.session_state["parecer_ia"] = ""
                st.success("Workspace EBT criado e auditado com sucesso!")
                st.rerun()
            except (ErroPermissaoRBAC, ErroLimitePlanoSaaS) as erro_negocio:
                session.rollback()
                st.error(f"🔒 Bloqueado: {erro_negocio}")

    # 5. Renomear e Excluir (Update / Delete)
    with st.expander("✏️ Renomear / 🗑️ Excluir"):
        with st.form("form_renomear"):
            nome_editado = st.text_input(
                "Novo Nome", 
                value=opcoes_projetos[st.session_state["projeto_atual_id"]]
            )
            botao_renomear = st.form_submit_button("Salvar Alteração")
            
            if botao_renomear and nome_editado:
                try:
                    verificar_permissao_rbac(
                        membership_ativa,
                        PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO,
                        ebt_alvo_id=st.session_state["projeto_atual_id"],
                    )
                    projeto_para_editar = session.get(ClienteEBT, st.session_state["projeto_atual_id"])
                    nome_antigo = projeto_para_editar.nome_startup
                    projeto_para_editar.nome_startup = nome_editado
                    registrar_evento_auditoria(
                        session,
                        tenant_id=tenant_ativo.id,
                        user_id=membership_ativa.user_id,
                        acao="ebt.renomear",
                        entidade_tipo="ClienteEBT",
                        entidade_id=projeto_para_editar.id,
                        resumo=f"EBT renomeada de '{nome_antigo}' para '{nome_editado}'.",
                        dados_anteriores={"nome_startup": nome_antigo},
                        dados_novos={"nome_startup": nome_editado},
                    )
                    session.commit()
                    st.rerun()
                except ErroPermissaoRBAC as erro_rbac:
                    session.rollback()
                    st.error(f"🔒 {erro_rbac}")
                
        st.warning("Aviso: A exclusão é permanente e destrói o valuation do banco de dados.")
        botao_excluir = st.button("Excluir Startup", type="primary")
        
        if botao_excluir:
            try:
                verificar_permissao_rbac(
                    membership_ativa,
                    PermissaoSaaS.EBT_EXCLUIR,
                    ebt_alvo_id=st.session_state["projeto_atual_id"],
                )
                if len(todos_projetos) > 1:
                    projeto_para_deletar = session.get(ClienteEBT, st.session_state["projeto_atual_id"])
                    registrar_evento_auditoria(
                        session,
                        tenant_id=tenant_ativo.id,
                        user_id=membership_ativa.user_id,
                        acao="ebt.excluir",
                        entidade_tipo="ClienteEBT",
                        entidade_id=projeto_para_deletar.id,
                        resumo=f"Workspace EBT '{projeto_para_deletar.nome_startup}' excluído.",
                    )
                    session.delete(projeto_para_deletar)
                    session.commit()
                    restantes = listar_workspaces_ebt_visiveis(session, membership=membership_ativa)
                    st.session_state["projeto_atual_id"] = restantes[0].id
                    st.session_state["parecer_ia"] = ""
                    st.rerun()
                else:
                    st.error("Erro Crítico: Não é possível excluir a última startup visível.")
            except ErroPermissaoRBAC as erro_rbac:
                session.rollback()
                st.error(f"🔒 {erro_rbac}")

    st.markdown("---")
    st.subheader("🔌 Sistema Local")
    if st.button("Desligar Servidor Interno", type="primary"):
        st.success("Servidor encerrado. A memória RAM foi libertada.")
        time.sleep(2)
        os._exit(0)

# =============================================================================
# INICIALIZAÇÃO DE INTEGRIDADE RELACIONAL 
# (Garante que as tabelas de 1:1 existam para o Workspace EBT)
# =============================================================================
projeto = session.get(ClienteEBT, st.session_state["projeto_atual_id"])

def garantir_relacionamento(atributo, classe_modelo):
    """Verifica e cria os registos filhos caso não existam para o workspace EBT."""
    if not getattr(projeto, atributo):
        novo_registo = classe_modelo(tenant_id=tenant_ativo.id, ebt_id=projeto.id)
        session.add(novo_registo)
        session.commit()
        session.refresh(projeto)

garantir_relacionamento("lean_canvas", LeanCanvasEBT)
garantir_relacionamento("premissas", PremissasEBT)
garantir_relacionamento("juridico", JuridicoEBT)

pode_editar_diagnostico = True
try:
    verificar_permissao_rbac(
        membership_ativa,
        PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO,
        ebt_alvo_id=projeto.id,
    )
except ErroPermissaoRBAC:
    pode_editar_diagnostico = False

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
    st.caption(
        f"Master Management SaaS — Consultoria: **{tenant_ativo.nome}** · "
        f"Papel RBAC: **`{membership_ativa.papel.upper()}`** "
        f"{'🔒 (Modo Somente Leitura)' if not pode_editar_diagnostico else '✏️ (Edição Habilitada)'}"
    )
    
st.markdown("---")

# =============================================================================
# ⚙️ MOTOR MATEMÁTICO E FINANCEIRO PURO (CORE_FINANCEIRO — FASE 0 SAAS)
# Processado via pacote isolado Pydantic antes das abas para garantir
# determinismo, versionamento e validações de sanidade.
# =============================================================================
premissas_atuais = projeto.premissas

entrada_simulacao = EntradaSimulacaoSaaS.from_orm_projeto(projeto)
resultado_simulacao = executar_simulacao_saas(entrada_simulacao)
comparativo_cenarios = simular_cenarios_padrao(entrada_simulacao)

# Mapeamento das saídas tipadas do motor puro para as variáveis consumidas pelas abas e PDF
capex_total_apurado = resultado_simulacao.viabilidade.capex_total
opex_fixo_mensal = resultado_simulacao.dre_base.opex_fixo_mensal

usuarios_pagos_diretos = resultado_simulacao.unit_economics.usuarios_pagos_diretos
conversos_pagantes_freemium = resultado_simulacao.unit_economics.conversos_pagantes_freemium
usuarios_pagantes_totais_base = resultado_simulacao.unit_economics.usuarios_pagantes_totais_base

mrr_bruto_direto_apurado = resultado_simulacao.dre_base.mrr_bruto_direto
ticket_medio_arpu = resultado_simulacao.unit_economics.ticket_medio_arpu
mrr_bruto_total_consolidado = resultado_simulacao.dre_base.mrr_bruto_total

media_deducao_impostos_pct = resultado_simulacao.unit_economics.media_deducao_impostos_pct
media_custo_nuvem_rs = resultado_simulacao.unit_economics.media_custo_nuvem_rs
despesas_deducoes_base = resultado_simulacao.dre_base.despesas_deducoes_fiscais_gateway
despesas_nuvem_cogs_base = resultado_simulacao.dre_base.despesas_nuvem_cogs

mrr_liquido_apurado_base = resultado_simulacao.dre_base.mrr_liquido
burn_rate_total_mensal = resultado_simulacao.dre_base.burn_rate_total_mensal
resultado_operacional_ebitda = resultado_simulacao.dre_base.ebitda_mensal
margem_bruta_percentual = resultado_simulacao.dre_base.margem_bruta_pct
faturamento_anualizado_arr = resultado_simulacao.dre_base.arr_anualizado

ltv_vitalicio_cliente = resultado_simulacao.unit_economics.ltv_vitalicio_cliente
cac_aquisicao_mercado = resultado_simulacao.unit_economics.cac_estimado
indice_ltv_cac = resultado_simulacao.unit_economics.indice_ltv_cac
meses_payback_cac = resultado_simulacao.unit_economics.meses_payback_cac

lista_fluxo_de_caixa = resultado_simulacao.series_temporais.fluxo_de_caixa_mensal
lista_rotulos_meses = resultado_simulacao.series_temporais.rotulos_meses
timeline_usuarios_pagantes = resultado_simulacao.series_temporais.usuarios_pagantes
timeline_mrr_crescente = resultado_simulacao.series_temporais.mrr_mensal
timeline_usuarios_freemium = resultado_simulacao.series_temporais.usuarios_freemium
serie_caixa_acumulado = pd.Series(resultado_simulacao.series_temporais.caixa_acumulado)

valor_presente_liquido_vpl = resultado_simulacao.viabilidade.valor_presente_liquido_vpl
taxa_interna_retorno_anual = resultado_simulacao.viabilidade.taxa_interna_retorno_anual_pct
validade_da_tir = resultado_simulacao.viabilidade.validade_da_tir
mes_de_breakeven_payback = resultado_simulacao.viabilidade.mes_de_breakeven_payback_texto
meses_runway_sobrevivencia = resultado_simulacao.viabilidade.meses_runway_sobrevivencia


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
# ARQUITETURA DE INFORMAÇÃO — 12 ABAS PROFISSIONAIS DE FUNDOS VC + GOVERNANÇA SAAS
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
    aba_pdf_export,
    aba_governanca_saas,
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
    "🖨️ Data Room (PDF)",
    "🛡️ Governança SaaS",
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
            try:
                verificar_permissao_rbac(
                    membership_ativa,
                    PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO,
                    ebt_alvo_id=projeto.id,
                )
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
                registrar_evento_auditoria(
                    session,
                    tenant_id=tenant_ativo.id,
                    user_id=membership_ativa.user_id,
                    acao="lean_canvas.atualizar",
                    entidade_tipo="LeanCanvasEBT",
                    entidade_id=canvas_ativo.id,
                    resumo=f"Lean Canvas da EBT '{projeto.nome_startup}' atualizado.",
                )
                session.commit()
                st.success("✅ As diretrizes estratégicas da startup foram atualizadas e auditadas com sucesso.")
            except ErroPermissaoRBAC as erro_rbac:
                session.rollback()
                st.error(f"🔒 {erro_rbac}")

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
            try:
                atualizar_premissas_ebt(
                    session,
                    membership=membership_ativa,
                    ebt_id=projeto.id,
                    horizonte_meses=input_horizonte,
                    tma_anual_pct=input_tma,
                    cac_estimado=input_cac_projetado,
                    churn_mensal_pct=input_churn_mensal,
                    conversao_freemium_pct=input_taxa_conversao,
                    crescimento_mensal_pct=input_crescimento_organico,
                    usuarios_freemium_base=input_base_freemium,
                )
                session.commit()
                st.success("✅ O Motor Económico foi atualizado e auditado com sucesso.")
                st.rerun()
            except ErroPermissaoRBAC as erro_rbac:
                session.rollback()
                st.error(f"🔒 {erro_rbac}")

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
            try:
                verificar_permissao_rbac(
                    membership_ativa,
                    PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO,
                    ebt_alvo_id=projeto.id,
                )
                novo_capex = ItemCapexEBT(
                    tenant_id=tenant_ativo.id,
                    ebt_id=projeto.id,
                    categoria=categoria_investimento, 
                    descricao=descricao_investimento, 
                    valor=valor_investimento, 
                )
                session.add(novo_capex)
                session.flush()
                registrar_evento_auditoria(
                    session,
                    tenant_id=tenant_ativo.id,
                    user_id=membership_ativa.user_id,
                    acao="capex.adicionar",
                    entidade_tipo="ItemCapexEBT",
                    entidade_id=novo_capex.id,
                    resumo=f"Item Capex '{descricao_investimento}' (R$ {valor_investimento:,.2f}) adicionado.",
                )
                session.commit()
                st.rerun()
            except ErroPermissaoRBAC as erro_rbac:
                session.rollback()
                st.error(f"🔒 {erro_rbac}")

    for item_capex in projeto.investimentos:
        coluna_texto, coluna_botao = st.columns([11, 1])
        coluna_texto.info(
            f"**{item_capex.categoria}** — {item_capex.descricao}   |   "
            f"Orçamento Alocado: R$ {item_capex.valor:,.2f}"
        )
        if coluna_botao.button("🗑️", key=f"excluir_capex_{item_capex.id}"):
            try:
                verificar_permissao_rbac(
                    membership_ativa,
                    PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO,
                    ebt_alvo_id=projeto.id,
                )
                registrar_evento_auditoria(
                    session,
                    tenant_id=tenant_ativo.id,
                    user_id=membership_ativa.user_id,
                    acao="capex.excluir",
                    entidade_tipo="ItemCapexEBT",
                    entidade_id=item_capex.id,
                    resumo=f"Item Capex '{item_capex.descricao}' removido.",
                )
                session.delete(item_capex)
                session.commit()
                st.rerun()
            except ErroPermissaoRBAC as erro_rbac:
                session.rollback()
                st.error(f"🔒 {erro_rbac}")

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
            try:
                verificar_permissao_rbac(
                    membership_ativa,
                    PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO,
                    ebt_alvo_id=projeto.id,
                )
                novo_opex = ItemOpexEBT(
                    tenant_id=tenant_ativo.id,
                    ebt_id=projeto.id,
                    categoria=categoria_despesa, 
                    descricao=descricao_despesa, 
                    valor_mensal=valor_despesa, 
                )
                session.add(novo_opex)
                session.flush()
                registrar_evento_auditoria(
                    session,
                    tenant_id=tenant_ativo.id,
                    user_id=membership_ativa.user_id,
                    acao="opex.adicionar",
                    entidade_tipo="ItemOpexEBT",
                    entidade_id=novo_opex.id,
                    resumo=f"Item Opex '{descricao_despesa}' (R$ {valor_despesa:,.2f}/mês) adicionado.",
                )
                session.commit()
                st.rerun()
            except ErroPermissaoRBAC as erro_rbac:
                session.rollback()
                st.error(f"🔒 {erro_rbac}")

    for item_opex in projeto.custos_fixos:
        col_txt_op, col_btn_op = st.columns([11, 1])
        col_txt_op.error(
            f"**{item_opex.categoria}** — {item_opex.descricao}   |   "
            f"Saída Mensal Constante: R$ {item_opex.valor_mensal:,.2f}/mês"
        )
        if col_btn_op.button("🗑️", key=f"excluir_opex_{item_opex.id}"):
            try:
                verificar_permissao_rbac(
                    membership_ativa,
                    PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO,
                    ebt_alvo_id=projeto.id,
                )
                registrar_evento_auditoria(
                    session,
                    tenant_id=tenant_ativo.id,
                    user_id=membership_ativa.user_id,
                    acao="opex.excluir",
                    entidade_tipo="ItemOpexEBT",
                    entidade_id=item_opex.id,
                    resumo=f"Item Opex '{item_opex.descricao}' removido.",
                )
                session.delete(item_opex)
                session.commit()
                st.rerun()
            except ErroPermissaoRBAC as erro_rbac:
                session.rollback()
                st.error(f"🔒 {erro_rbac}")

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
    st.header("💳 Engenharia de Preços e Tiers de Assinatura (Pagos & Free Tier)")
    st.info(
        "💡 **Suporte Nativo a Free Tier (R$ 0,00)**: Para simular um **Plano Gratuito (Free Tier / PLG)**, "
        "informe `Receita Fixa (R$/Mês) = 0,00` e defina o `Custo de Nuvem/AWS por User (R$)`. "
        "O motor contabilizará automaticamente o COGS de nuvem da base gratuita e sua conversão para os planos pagos, "
        "**sem diluir o Ticket Médio (ARPU) dos assinantes pagantes**."
    )

    with st.form("formulario_cadastro_planos", clear_on_submit=True):
        nome_do_tier = st.text_input("Nomenclatura do Plano de Vendas (Ex: Free Tier, Plano Starter, Enterprise B2B)")
        
        col_pr1, col_pr2, col_pr3, col_pr4, col_pr5 = st.columns(5)
        ticket_plano = col_pr1.number_input("Receita Fixa (R$/Mês)", min_value=0.0)
        volume_clientes_plano = col_pr2.number_input("Número de Licenças Ativas", min_value=0)
        taxa_cartao_plano = col_pr3.number_input("Taxa de Cartão/Gateway (%)", value=5.0)
        carga_fiscal_plano = col_pr4.number_input("Retenção de Impostos (%)", value=6.0)
        custo_nuvem_plano = col_pr5.number_input("Custo de Nuvem/AWS por User (R$)", min_value=0.0)

        botao_inserir_plano = st.form_submit_button("➕ Homologar Tier de Preço / Free Tier")
        
        if botao_inserir_plano and nome_do_tier:
            try:
                verificar_permissao_rbac(
                    membership_ativa,
                    PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO,
                    ebt_alvo_id=projeto.id,
                )
                novo_plano_saas = PlanoSaaSEBT(
                    tenant_id=tenant_ativo.id,
                    ebt_id=projeto.id,
                    nome_plano=nome_do_tier, 
                    ticket_mensal=ticket_plano, 
                    usuarios_ativos_base=volume_clientes_plano,
                    taxas_pagamento_pct=taxa_cartao_plano, 
                    impostos_pct=carga_fiscal_plano, 
                    custo_servidor_por_usuario=custo_nuvem_plano,
                )
                session.add(novo_plano_saas)
                session.flush()
                registrar_evento_auditoria(
                    session,
                    tenant_id=tenant_ativo.id,
                    user_id=membership_ativa.user_id,
                    acao="plano_saas.adicionar",
                    entidade_tipo="PlanoSaaSEBT",
                    entidade_id=novo_plano_saas.id,
                    resumo=f"Plano SaaS '{nome_do_tier}' (R$ {ticket_plano:,.2f}) homologado.",
                )
                session.commit()
                st.rerun()
            except ErroPermissaoRBAC as erro_rbac:
                session.rollback()
                st.error(f"🔒 {erro_rbac}")

    for assinatura in projeto.planos_saas:
        col_txt_saas, col_btn_saas = st.columns([11, 1])
        
        mrr_deste_plano = assinatura.ticket_mensal * assinatura.usuarios_ativos_base
        desconto_total = (assinatura.taxas_pagamento_pct + assinatura.impostos_pct) / 100
        custo_nuvem_total_tier = assinatura.custo_servidor_por_usuario * assinatura.usuarios_ativos_base
        margem_deste_plano = (mrr_deste_plano * (1 - desconto_total)) - custo_nuvem_total_tier
        
        if assinatura.ticket_mensal <= 0.0:
            col_txt_saas.info(
                f"🆓 **FREE TIER: {assinatura.nome_plano}** — Preço: R$ 0,00 (Gratuito) · "
                f"Usuários Free: {assinatura.usuarios_ativos_base} · "
                f"COGS de Nuvem do Free Tier: R$ {custo_nuvem_total_tier:,.2f}/mês · "
                f"Não dilui o ARPU Pago"
            )
        else:
            col_txt_saas.success(
                f"💳 **{assinatura.nome_plano}** — Preço (ARPU): R$ {assinatura.ticket_mensal:.2f} · "
                f"Contas Ativas: {assinatura.usuarios_ativos_base} · "
                f"Receita Produzida: R$ {mrr_deste_plano:,.2f} · "
                f"Lucro Bruto do Tier: R$ {margem_deste_plano:,.2f}"
            )
        if col_btn_saas.button("🗑️", key=f"excluir_plano_{assinatura.id}"):
            try:
                verificar_permissao_rbac(
                    membership_ativa,
                    PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO,
                    ebt_alvo_id=projeto.id,
                )
                registrar_evento_auditoria(
                    session,
                    tenant_id=tenant_ativo.id,
                    user_id=membership_ativa.user_id,
                    acao="plano_saas.excluir",
                    entidade_tipo="PlanoSaaSEBT",
                    entidade_id=assinatura.id,
                    resumo=f"Plano SaaS '{assinatura.nome_plano}' removido.",
                )
                session.delete(assinatura)
                session.commit()
                st.rerun()
            except ErroPermissaoRBAC as erro_rbac:
                session.rollback()
                st.error(f"🔒 {erro_rbac}")

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
            try:
                verificar_permissao_rbac(
                    membership_ativa,
                    PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO,
                    ebt_alvo_id=projeto.id,
                )
                dados_legais = projeto.juridico
                
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
                
                registrar_evento_auditoria(
                    session,
                    tenant_id=tenant_ativo.id,
                    user_id=membership_ativa.user_id,
                    acao="juridico.atualizar",
                    entidade_tipo="JuridicoEBT",
                    entidade_id=dados_legais.id,
                    resumo=f"Due diligence jurídica da EBT '{projeto.nome_startup}' selada.",
                    dados_novos={
                        "inpi": dados_legais.registro_inpi,
                        "marca": dados_legais.marca_status,
                        "lgpd": dados_legais.adequacao_lgpd,
                        "vesting": dados_legais.contrato_vesting,
                    },
                )
                session.commit()
                st.success("✅ As fragilidades de governança foram avaliadas, registadas e auditadas.")
                st.rerun()
            except ErroPermissaoRBAC as erro_rbac:
                session.rollback()
                st.error(f"🔒 {erro_rbac}")

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

    # ── Validações de Sanidade do Motor Financeiro (Fase 0 SaaS) ─────────────
    st.subheader(f"🛡️ Auditoria de Sanidade do Motor Financeiro (v{resultado_simulacao.versao_motor})")
    st.caption(f"Hash Determinístico da Simulação (SHA-256): `{resultado_simulacao.hash_entrada[:16]}...`")

    if not resultado_simulacao.alertas:
        st.success("✅ Todas as validações matemáticas e setoriais passaram sem alertas.")
    else:
        for alerta in resultado_simulacao.alertas:
            texto_alerta = (
                f"**[{alerta.codigo}] {alerta.titulo}** — {alerta.mensagem}\n\n"
                f"💡 *Recomendação:* {alerta.recomendacao}"
            )
            if alerta.severidade == SeveridadeAlerta.CRITICO:
                st.error(texto_alerta)
            elif alerta.severidade == SeveridadeAlerta.AVISO:
                st.warning(texto_alerta)
            else:
                st.info(texto_alerta)

    # ── Comparativo de Cenários (Base / Otimista / Pessimista) ───────────────
    with st.expander("🎯 Matriz Comparativa de Cenários (Base vs. Otimista vs. Pessimista)", expanded=False):
        linhas_cenarios = []
        for rotulo_cenario, chave_cenario in [
            ("Pessimista (Stress Test)", TipoCenario.PESSIMISTA),
            ("Base (Plano Atual)", TipoCenario.BASE),
            ("Otimista (Bull Case)", TipoCenario.OTIMISTA),
        ]:
            sim_c = comparativo_cenarios.cenarios[chave_cenario]
            linhas_cenarios.append({
                "Cenário": rotulo_cenario,
                "VPL Projetado": f"R$ {sim_c.viabilidade.valor_presente_liquido_vpl:,.2f}",
                "TIR Anualizada": (
                    f"{sim_c.viabilidade.taxa_interna_retorno_anual_pct:,.2f}%"
                    if sim_c.viabilidade.validade_da_tir
                    else "Indefinida"
                ),
                "Payback": sim_c.viabilidade.mes_de_breakeven_payback_texto,
                "LTV / CAC": f"{sim_c.unit_economics.indice_ltv_cac:.2f}x",
                "Alertas Críticos": "Sim ⚠️" if sim_c.possui_alertas_criticos else "Não ✅",
            })
        st.dataframe(pd.DataFrame(linhas_cenarios), use_container_width=True, hide_index=True)

    # ── Versionamento Imutável e Simulação de Monte Carlo (Fase 1/2 SaaS) ────
    with st.expander("📸 Versionamento Imutável de Simulações & Stress Test de Monte Carlo", expanded=False):
        col_ver_btn, col_mc_btn = st.columns(2)
        if col_ver_btn.button("📌 Congelar e Versionar Simulação Atual (Snapshot Imutável)"):
            try:
                v_snap, res_snap, _ = executar_e_versionar_simulacao_ebt(
                    session,
                    membership=membership_ativa,
                    ebt_id=projeto.id,
                    cenario=TipoCenario.BASE,
                )
                session.commit()
                st.success(
                    f"✅ Versão imutável **v{v_snap.numero_versao}** congelada com hash `{v_snap.hash_entrada_sha256[:16]}...`!"
                )
            except ErroPermissaoRBAC as erro_rbac:
                session.rollback()
                st.error(f"🔒 {erro_rbac}")

        if col_mc_btn.button("🎲 Executar Simulação Estocástica de Monte Carlo (300 Iterações)"):
            if assinatura_ativa and not assinatura_ativa.permite_monte_carlo:
                st.warning(
                    f"🔒 A Simulação de Monte Carlo é exclusiva dos planos **PRO** e **ENTERPRISE** "
                    f"(plano atual: **{assinatura_ativa.plano_codigo.upper()}**)."
                )
            else:
                mc_res = simular_monte_carlo(entrada_simulacao, iteracoes=300, semente=42)
                mc_c1, mc_c2, mc_c3, mc_c4 = st.columns(4)
                mc_c1.metric("Probabilidade de VPL > 0", f"{mc_res.probabilidade_vpl_positivo_pct:.1f}%")
                mc_c2.metric("VPL Pessimista (P10)", f"R$ {mc_res.vpl_p10:,.2f}")
                mc_c3.metric("VPL Mediano (P50)", f"R$ {mc_res.vpl_p50_mediana:,.2f}")
                mc_c4.metric("VPL Otimista (P90)", f"R$ {mc_res.vpl_p90:,.2f}")

        versoes_salvas = (
            session.query(VersaoPremissasEBT)
            .filter(VersaoPremissasEBT.ebt_id == projeto.id)
            .order_by(VersaoPremissasEBT.numero_versao.desc())
            .all()
        )
        if versoes_salvas:
            st.markdown("**Histórico de Versões Imutáveis Auditadas para esta EBT:**")
            linhas_historico = []
            for v in versoes_salvas:
                r_sim = (
                    session.query(ResultadoSimulacaoEBT)
                    .filter(ResultadoSimulacaoEBT.versao_premissas_id == v.id)
                    .first()
                )
                linhas_historico.append({
                    "Versão": f"v{v.numero_versao}",
                    "Hash SHA-256 (Entrada)": f"{v.hash_entrada_sha256[:16]}...",
                    "Motor": r_sim.versao_motor if r_sim else "-",
                    "MRR Base": f"R$ {r_sim.mrr_bruto_base:,.2f}" if r_sim else "-",
                    "VPL": f"R$ {r_sim.vpl:,.2f}" if r_sim else "-",
                    "LTV/CAC": f"{r_sim.ltv_cac:.2f}x" if r_sim else "-",
                    "Data (UTC)": v.criado_em.strftime("%d/%m/%Y %H:%M") if v.criado_em else "-",
                })
            st.dataframe(pd.DataFrame(linhas_historico), use_container_width=True, hide_index=True)

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
# ABA 10: O CÉREBRO ARTIFICIAL (COMITÊ VC GOVERNADO + SANITIZAÇÃO LGPD + CACHE)
# =============================================================================
with aba_mentor_vc:
    safe_image(
        "https://images.unsplash.com/photo-1677442136019-21780ecad995?q=80&w=1000&auto=format&fit=crop", 
        width="stretch"
    )
    st.header("🤖 Comitê de Avaliação VC Assistido e Governado (Fase 3)")
    st.info(
        "Governança de IA em Produção: Todos os textos abertos passam por **sanitização automática de PII (LGPD)** "
        "(mascaramento de CPFs, CNPJs, e-mails e telefones) antes do envio ao provedor. O parecer é indexado por "
        "**hash SHA-256 do contexto**, economizando quotas via cache inteligente, e requer **homologação do Consultor**."
    )

    prompt_preview_sanitizado, hash_contexto_preview = construir_prompt_vc_governado(
        projeto, resultado_simulacao
    )
    with st.expander("🔍 Inspecionar Prompt Anonimizado (Sem PII) e Hash SHA-256 do Contexto"):
        st.caption(f"Hash SHA-256 do Contexto (Financeiro + Qualitativo Sanitizado): `{hash_contexto_preview}`")
        st.code(prompt_preview_sanitizado, language="markdown")

    col_ia_prov, col_ia_cfg = st.columns([2, 1])
    with col_ia_prov:
        modo_provedor_ia = st.radio(
            "Provedor de Inteligência do Comitê VC:",
            options=[
                "🏛️ Copiloto VC Determinístico Interno (Sem Chave Externa / Custo US$ 0)",
                "✨ Google Gemini API (Nuvem Externa com Sanitização LGPD)",
            ],
            horizontal=False,
        )
    with col_ia_cfg:
        forcar_nova_geracao_ia = st.checkbox(
            "Ignorar cache e forçar nova geração",
            value=False,
            help="Quando desmarcado, se o hash SHA-256 do projeto não mudou, reutiliza o parecer sem descontar da quota mensal.",
        )

    chave_api_usuario = ""
    if modo_provedor_ia.startswith("✨"):
        chave_api_usuario = st.text_input(
            "Credenciais Seguras: Chave da API Google Gemini:",
            type="password",
            key="gemini_key_widget",
        )

    if st.button("🚀 Solicitar Parecer Governado ao Comitê VC", type="primary"):
        if modo_provedor_ia.startswith("✨") and not chave_api_usuario.strip():
            st.warning("⚠️ Informe uma chave válida da API Google Gemini ou selecione o Copiloto VC Determinístico Interno.")
        else:
            try:
                with st.spinner("Executando pipeline governado de IA (Sanitização PII -> Verificação de Cache/Quota -> Geração)..."):
                    provedor_selecionado = (
                        ProvedorGeminiIA(api_key=chave_api_usuario.strip(), modelo="gemini-2.5-flash")
                        if modo_provedor_ia.startswith("✨")
                        else ProvedorAuditoriaDeterministicoIA()
                    )
                    analise_gerada, job_ia, veio_do_cache = solicitar_parecer_ia_governado(
                        session,
                        membership=membership_ativa,
                        ebt_id=projeto.id,
                        provedor_ia=provedor_selecionado,
                        forcar_regeneracao=forcar_nova_geracao_ia,
                    )
                    session.commit()
                    st.session_state["parecer_ia"] = (
                        analise_gerada.parecer_revisado_consultor_md
                        or analise_gerada.parecer_gerado_md
                    )
                    if veio_do_cache:
                        st.success(
                            f"⚡ **Cache Hit Inteligente!** O contexto da EBT não sofreu alterações "
                            f"(`hash={analise_gerada.hash_entrada_simulacao[:12]}...`). Parecer recuperado sem consumir sua quota mensal!"
                        )
                    else:
                        st.success(
                            f"✅ Parecer gerado e registrado com sucesso (`Job #{job_ia.id[:8]}`, "
                            f"Provedor: `{analise_gerada.provedor}/{analise_gerada.modelo}`)."
                        )
            except ErroPermissaoRBAC as erro_rbac:
                session.rollback()
                st.error(f"🔒 Bloqueio RBAC: {erro_rbac}")
            except ErroLimitePlanoSaaS as erro_quota:
                session.rollback()
                st.error(f"🛑 Limite do Plano Atingido: {erro_quota}")
            except Exception as erro_ia:
                session.rollback()
                st.error(f"Erro durante o processamento do parecer de IA: {erro_ia}")

    ultima_analise_ebt = (
        session.query(AnaliseIAEBT)
        .filter(
            AnaliseIAEBT.tenant_id == tenant_ativo.id,
            AnaliseIAEBT.ebt_id == projeto.id,
        )
        .order_by(AnaliseIAEBT.criado_em.desc())
        .first()
    )

    if ultima_analise_ebt is not None:
        st.session_state["parecer_ia"] = (
            ultima_analise_ebt.parecer_revisado_consultor_md
            or ultima_analise_ebt.parecer_gerado_md
        )
        st.markdown("---")
        col_st1, col_st2, col_st3 = st.columns(3)
        col_st1.metric(
            "Status de Homologação",
            "✅ Aprovado pelo Consultor" if ultima_analise_ebt.aprovado_pelo_consultor else "⏳ Pendente de Revisão",
        )
        col_st2.metric("Modelo / Versão Prompt", f"{ultima_analise_ebt.modelo} ({ultima_analise_ebt.versao_prompt})")
        col_st3.metric("Hash do Contexto", f"{ultima_analise_ebt.hash_entrada_simulacao[:14]}...")

        st.markdown(st.session_state["parecer_ia"])

        st.markdown("---")
        st.subheader("👨‍💼 Revisão e Homologação Obrigatória pelo Consultor")
        with st.form("form_homologar_parecer_ia"):
            texto_para_homologar = st.text_area(
                "Edite ou complemente o parecer antes de homologá-lo para o Dossiê Oficial:",
                value=st.session_state["parecer_ia"],
                height=240,
            )
            btn_homologar = st.form_submit_button("✅ Homologar Parecer Oficial pelo Consultor")
            if btn_homologar:
                try:
                    analise_aprovada = revisar_e_aprovar_parecer_ia(
                        session,
                        membership=membership_ativa,
                        analise_id=ultima_analise_ebt.id,
                        texto_revisado_md=texto_para_homologar,
                    )
                    session.commit()
                    st.session_state["parecer_ia"] = analise_aprovada.parecer_revisado_consultor_md
                    st.success("✅ Parecer homologado oficialmente pelo Consultor e registrado no AuditLog!")
                    st.rerun()
                except ErroPermissaoRBAC as erro_rbac:
                    session.rollback()
                    st.error(f"🔒 Apenas Dono, Admin ou Consultor podem homologar pareceres: {erro_rbac}")
    elif st.session_state["parecer_ia"]:
        st.markdown("---")
        st.markdown(st.session_state["parecer_ia"])

# =============================================================================
# ABA 11: MOTOR EXPORTADOR DA DATA ROOM (DOCUMENTAÇÃO PDF GOVERNADA E ASSINADA)
# =============================================================================
with aba_pdf_export:
    safe_image(
        "https://images.unsplash.com/photo-1618044733300-9472054094ee?q=80&w=1000&auto=format&fit=crop", 
        width="stretch"
    )
    st.header("🖨️ A Data Room Segura: Exportação Dossiê do Demoday")
    st.info(
        "Emissão governada do Dossiê Executivo A4 com **cálculo de hash de integridade SHA-256**, "
        "**armazenamento isolado por Tenant**, **URL assinada com expiração (HMAC)** e suporte **White-Label**."
    )

    analise_recente_pdf = (
        session.query(AnaliseIAEBT)
        .filter(
            AnaliseIAEBT.tenant_id == tenant_ativo.id,
            AnaliseIAEBT.ebt_id == projeto.id,
        )
        .order_by(AnaliseIAEBT.criado_em.desc())
        .first()
    )
    if analise_recente_pdf and analise_recente_pdf.aprovado_pelo_consultor:
        st.success("✅ O Parecer de IA desta EBT já se encontra revisado e homologado por um Consultor.")
    else:
        st.warning(
            "⚠️ O Parecer de IA desta EBT ainda não foi homologado por um Consultor na aba '🤖 Comitê VC (IA)'."
        )

    exigir_homologacao_pdf = st.checkbox(
        "🔒 Exigir Parecer de IA homologado pelo Consultor para permitir a emissão (Política Institucional)",
        value=False,
    )

    caixa_interativa_de_revisao_do_comite = st.text_area(
        "Edição da Carta Parecer Oficial (Os registos abaixo transitam da memória permanente originada na análise IA):",
        value=st.session_state["parecer_ia"], 
        height=250,
    )

    if st.button("🚀 Extrair, Assinar (SHA-256) e Materializar Prospecto PDF", type="primary"):
        try:
            with st.spinner("Gerando Dossiê A4, gravando no Storage isolado do Tenant e assinando URL..."):
                
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
                # COMPOSIÇÃO DE FOLHA DE ROSTO (PÁGINA 1 - WHITE LABEL DO TENANT)
                # ==================================
                motor_escritor_de_pdf.add_page()
                motor_escritor_de_pdf.set_font(familia_tipografica, "B", 11)
                selo_consultoria = (
                    f"DOSSIE INSTITUCIONAL WHITE-LABEL — {tenant_ativo.nome.upper()}"
                    if (assinatura_ativa and assinatura_ativa.permite_white_label)
                    else f"PREPARADO POR: {tenant_ativo.nome.upper()} (MASTER MANAGEMENT SAAS)"
                )
                motor_escritor_de_pdf.cell(
                    motor_escritor_de_pdf.epw,
                    8,
                    selo_consultoria,
                    new_x=XPos.LMARGIN,
                    new_y=YPos.NEXT,
                    align="C",
                )
                motor_escritor_de_pdf.ln(35)
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
                # LAUDO OFICIAL DO COMITÊ VC (PÁGINA FINAL)
                # ==================================
                if caixa_interativa_de_revisao_do_comite:
                    motor_escritor_de_pdf.add_page()
                    FormatarTituloGrossoH1("V. Parecer Oficial do Comitê de Investimento e Due Diligence")
                    motor_escritor_de_pdf.set_font(familia_tipografica, "", 12)
                    
                    texto_ia_purificado = caixa_interativa_de_revisao_do_comite.replace("•", "-").replace("·", "-").replace("**", "")
                    motor_escritor_de_pdf.multi_cell(motor_escritor_de_pdf.epw, 7, safe_str(texto_ia_purificado))

                # Compilação Final Exata + Registro Governado no Storage e Banco SaaS
                saida_pdf_bytes_absolutos_reais = bytes(motor_escritor_de_pdf.output())
                relatorio_emitido, job_pdf, url_assinada_pdf = registrar_emissao_dossie_pdf(
                    session,
                    membership=membership_ativa,
                    ebt_id=projeto.id,
                    pdf_bytes=saida_pdf_bytes_absolutos_reais,
                    exigir_parecer_aprovado=exigir_homologacao_pdf,
                )
                session.commit()

                st.success(
                    f"✅ Dossiê Executivo gerado, assinado e arquivado com sucesso! "
                    f"(`Job #{job_pdf.id[:8]}`, SHA-256: `{relatorio_emitido.sha256_pdf[:16]}...`)"
                )
                st.caption(f"**Storage Key (Isolado por Tenant):** `{relatorio_emitido.storage_key}`")
                st.caption("**URL Pré-Assinada com Expiração (HMAC-SHA256):**")
                st.code(url_assinada_pdf, language="text")
                st.download_button(
                    "📥 Baixar Dossiê Executivo Assinado (.pdf)", 
                    data=saida_pdf_bytes_absolutos_reais, 
                    file_name=f"TermSheet_Prospecto_Duro_De_{projeto.nome_startup.replace(' ', '_')}.pdf", 
                    mime="application/pdf"
                )
        except (ErroPermissaoRBAC, PermissionError) as erro_perm_pdf:
            session.rollback()
            st.error(f"🔒 Bloqueio de Governança / RBAC: {erro_perm_pdf}")
        except ErroLimitePlanoSaaS as erro_quota_pdf:
            session.rollback()
            st.error(f"🛑 Limite Mensal de PDFs Atingido: {erro_quota_pdf}")
        except Exception as falha_bruta_profunda_de_geracao_sistema_inviabilizador:
            session.rollback()
            st.error(f"Erro na geração do Dossiê PDF: {falha_bruta_profunda_de_geracao_sistema_inviabilizador}")

# =============================================================================
# ABA 12: GOVERNANÇA SAAS, QUOTAS, FILA DE JOBS, SHARE LINKS E AUDITORIA
# =============================================================================
with aba_governanca_saas:
    st.header("🛡️ Governança Multi-Tenant, Quotas, Jobs Assíncronos e Auditoria (LGPD)")
    st.info(
        "Painel de controle institucional da Consultoria (Tenant): acompanhe o uso medido e custos de IA do plano, "
        "monitore a fila de Jobs Assíncronos, gere links temporários para investidores e audite todas as alterações."
    )

    # 1. Consumo Medido e Limites do Plano
    uso_atual = obter_ou_criar_uso_mensal(session, tenant_ativo.id)
    session.commit()
    total_ebts_ativas = session.query(ClienteEBT).filter(ClienteEBT.ativo.is_(True)).count()

    col_gov1, col_gov2, col_gov3, col_gov4 = st.columns(4)
    col_gov1.metric(
        "Plano Contratado",
        assinatura_ativa.plano_codigo.upper() if assinatura_ativa else "STARTER",
        delta=f"Status: {assinatura_ativa.status.upper()}" if assinatura_ativa else "TRIAL",
    )
    col_gov2.metric(
        "Workspaces EBT Ativos",
        f"{total_ebts_ativas} / {assinatura_ativa.limite_ebts if assinatura_ativa else 3}",
    )
    col_gov3.metric(
        f"Análises IA ({uso_atual.ano_mes})",
        f"{uso_atual.analises_ia_realizadas} / {assinatura_ativa.limite_analises_ia_mes if assinatura_ativa else 15}",
        delta=f"Custo IA: US$ {uso_atual.custo_ia_acumulado_usd:.4f}",
    )
    col_gov4.metric(
        f"Dossiês PDF / Simulações ({uso_atual.ano_mes})",
        f"{uso_atual.pdfs_gerados} / {assinatura_ativa.limite_pdfs_mes if assinatura_ativa else 20} PDFs",
        delta=f"{uso_atual.simulacoes_executadas} simulações",
    )

    with st.expander("💳 Alterar Plano de Assinatura da Consultoria (Testar Free Tier / Starter / Pro / Enterprise)"):
        opcoes_planos_saas = [
            PlanoAssinaturaCodigo.FREE,
            PlanoAssinaturaCodigo.STARTER,
            PlanoAssinaturaCodigo.PRO,
            PlanoAssinaturaCodigo.ENTERPRISE,
        ]
        idx_plano_atual = next(
            (
                i
                for i, p in enumerate(opcoes_planos_saas)
                if assinatura_ativa and p.value == assinatura_ativa.plano_codigo
            ),
            1,
        )
        with st.form("form_alterar_plano_tenant"):
            novo_plano_selecionado = st.selectbox(
                "Selecione o Plano Contratado para este Tenant:",
                options=opcoes_planos_saas,
                index=idx_plano_atual,
                format_func=lambda p: (
                    "FREE TIER (Gratuito: 1 EBT, 3 Simulações/mês, 1 IA, 1 PDF)"
                    if p == PlanoAssinaturaCodigo.FREE
                    else f"{p.value.upper()}"
                ),
            )
            btn_mudar_plano = st.form_submit_button("🔄 Aplicar Novo Plano ao Tenant")
            if btn_mudar_plano:
                try:
                    alterar_plano_assinatura_tenant(
                        session,
                        membership=membership_ativa,
                        novo_plano=novo_plano_selecionado,
                    )
                    session.commit()
                    st.success(f"✅ Plano do Tenant atualizado para **{novo_plano_selecionado.value.upper()}**!")
                    st.rerun()
                except ErroPermissaoRBAC as erro_rbac:
                    session.rollback()
                    st.error(f"🔒 Apenas o Dono da consultoria pode alterar o plano: {erro_rbac}")

    st.markdown("---")

    # 2. Fila de Jobs Assíncronos e Dossiês Emitidos (Fase 3)
    col_jobs_esq, col_dossies_dir = st.columns(2)
    with col_jobs_esq:
        st.subheader("⚙️ Fila de Jobs Assíncronos (`JobAssincronoSaaS`)")
        jobs_recentes = listar_jobs_tenant(session, tenant_id=tenant_ativo.id, limite=15)
        if not jobs_recentes:
            st.caption("Nenhum job de IA ou PDF processado neste Tenant ainda.")
        else:
            df_jobs = pd.DataFrame([
                {
                    "Job ID": j.id[:8],
                    "Tipo": j.tipo_job,
                    "Status": j.status.upper(),
                    "Progresso": f"{j.progresso_pct}%",
                    "Criado em": j.criado_em.strftime("%d/%m %H:%M:%S") if j.criado_em else "-",
                }
                for j in jobs_recentes
            ])
            st.dataframe(df_jobs, use_container_width=True, hide_index=True, height=210)

    with col_dossies_dir:
        st.subheader("📄 Dossiês PDF Emitidos (`RelatorioDossieEBT`)")
        dossies_recentes = (
            session.query(RelatorioDossieEBT)
            .filter(RelatorioDossieEBT.tenant_id == tenant_ativo.id)
            .order_by(RelatorioDossieEBT.criado_em.desc())
            .limit(15)
            .all()
        )
        if not dossies_recentes:
            st.caption("Nenhum Dossiê PDF emitido neste Tenant ainda.")
        else:
            df_dossies = pd.DataFrame([
                {
                    "Dossiê ID": d.id[:8],
                    "SHA-256": f"{d.sha256_pdf[:12]}...",
                    "Storage Key": d.storage_key.split("/")[-1],
                    "Emitido em": d.criado_em.strftime("%d/%m %H:%M:%S") if d.criado_em else "-",
                }
                for d in dossies_recentes
            ])
            st.dataframe(df_dossies, use_container_width=True, hide_index=True, height=210)

    st.markdown("---")

    # 3. Links de Compartilhamento Somente-Leitura para Investidor / Banca
    st.subheader("🔗 Data Room Externa: Links Temporários para Investidor / Banca")
    col_link_esq, col_link_dir = st.columns(2)

    with col_link_esq:
        with st.form("form_gerar_share_link"):
            dias_exp = st.number_input("Validade do Link (Dias)", min_value=1, max_value=90, value=7)
            btn_gerar_link = st.form_submit_button("🔑 Gerar Token de Acesso Somente-Leitura")
            if btn_gerar_link:
                try:
                    token_gerado, obj_link = criar_link_compartilhamento_investidor(
                        session,
                        membership=membership_ativa,
                        ebt_id=projeto.id,
                        dias_validade=int(dias_exp),
                    )
                    session.commit()
                    st.success("✅ Token temporário gerado (apenas o hash SHA-256 foi salvo no banco):")
                    st.code(token_gerado, language="text")
                except ErroPermissaoRBAC as erro_rbac:
                    session.rollback()
                    st.error(f"🔒 {erro_rbac}")

    with col_link_dir:
        with st.form("form_validar_share_link"):
            token_para_validar = st.text_input("Validar Token Recebido de Investidor:")
            btn_validar_link = st.form_submit_button("🔍 Verificar Validade e Registrar Acesso")
            if btn_validar_link and token_para_validar:
                try:
                    link_ok = validar_token_investidor(session, token_claro=token_para_validar.strip())
                    session.commit()
                    st.success(
                        f"✅ Token válido para a EBT `{link_ok.ebt_id[:8]}...`! "
                        f"Acessos contabilizados: **{link_ok.acessos_realizados}** "
                        f"(Expira em: {link_ok.expira_em.strftime('%d/%m/%Y %H:%M UTC')})."
                    )
                except PermissionError as erro_link:
                    session.rollback()
                    st.error(f"❌ {erro_link}")

    st.markdown("---")

    # 4. Trilha de Auditoria Imutável (AuditLog)
    st.subheader("📜 Trilha de Auditoria Imutável do Tenant (`AuditLog`)")
    eventos_auditoria = listar_trilha_auditoria(session, limite=50)
    if not eventos_auditoria:
        st.info("Nenhum evento de auditoria registrado até o momento.")
    else:
        tabela_audit = pd.DataFrame([
            {
                "Data/Hora (UTC)": ev.criado_em.strftime("%d/%m/%Y %H:%M:%S") if ev.criado_em else "-",
                "Ação": ev.acao,
                "Entidade": ev.entidade_tipo,
                "Resumo Operacional": ev.resumo,
                "Usuário": ev.user_id[:8] if ev.user_id else "sistema",
            }
            for ev in eventos_auditoria
        ])
        st.dataframe(tabela_audit, use_container_width=True, hide_index=True, height=260)

    # 5. Políticas Row-Level Security (PostgreSQL DDL)
    with st.expander("🗄️ Visualizar Script SQL de Row-Level Security (PostgreSQL RLS)"):
        ddl_rls = gerar_ddl_rls_postgresql()
        st.code(ddl_rls, language="sql")

try:
    session.commit()
    session.close()
except Exception:
    session.rollback()
    session.close()