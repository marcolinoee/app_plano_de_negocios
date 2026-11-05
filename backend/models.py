"""
Modelos de Domínio Multi-Tenant (Fase 1 SaaS — Master Management).
Implementa todas as camadas especificadas na arquitetura:
1. Plataforma: Tenant, User, Membership (RBAC), Convite, AssinaturaTenant, UsoMedidoTenant
2. Consultoria & Diagnóstico: ClienteEBT (Workspace), LeanCanvasEBT, PremissasEBT,
   ItemCapexEBT, ItemOpexEBT, PlanoSaaSEBT, JuridicoEBT, ShareLinkInvestidor
3. Cenários e Versões Imutáveis: CenarioEBT, VersaoPremissasEBT, ResultadoSimulacaoEBT
4. IA e Relatórios: AnaliseIAEBT, RelatorioDossieEBT
5. Auditoria: AuditLog
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


BaseSaaS = declarative_base()


# =============================================================================
# ENUMS DE DOMÍNIO E RBAC
# =============================================================================


class PapelMembro(str, Enum):
    DONO = "dono"                         # Dono da consultoria (acesso total + billing)
    ADMIN = "admin"                       # Administrador geral (SUPERADMIN / ADMIN)
    GESTOR = "gestor"                     # Gestor de portfólio / operações
    CONSULTOR = "consultor"               # Cria/edita EBTs, aprova pareceres de IA e emite dossiês
    ANALISTA = "analista"                 # Edita diagnósticos e roda simulações
    ASSINANTE_FREE = "assinante_free"     # Assinante no plano Free Tier
    ASSINANTE_PRO = "assinante_pro"       # Assinante no plano Pro
    FUNDADOR = "fundador"                 # Cliente/Fundador: edita apenas o seu próprio workspace (EBT)
    INVESTIDOR = "investidor"             # Banca/Investidor: acesso estritamente somente leitura


class PlanoAssinaturaCodigo(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class StatusAssinatura(str, Enum):
    TRIAL = "trial"
    ATIVA = "ativa"
    INADIMPLENTE = "inadimplente"
    CANCELADA = "cancelada"


# Tabelas que possuem isolamento obrigatório por tenant_id e recebem políticas RLS no PostgreSQL
TABELAS_COM_RLS: List[str] = [
    "memberships",
    "convites",
    "assinaturas_tenant",
    "uso_medido_tenant",
    "clientes_ebt",
    "lean_canvas_ebt",
    "premissas_ebt",
    "itens_capex_ebt",
    "itens_opex_ebt",
    "planos_saas_ebt",
    "juridico_ebt",
    "cenarios_ebt",
    "versoes_premissas_ebt",
    "resultados_simulacao_ebt",
    "analises_ia_ebt",
    "relatorios_dossie_ebt",
    "share_links_investidor",
    "jobs_assincronos_saas",
    "audit_logs",
]


# =============================================================================
# 1. CAMADA DE PLATAFORMA E IDENTIDADE
# =============================================================================


class Tenant(BaseSaaS):
    """Representa a Consultoria (cliente pagante da plataforma SaaS)."""

    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    nome = Column(String(200), nullable=False)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    cnpj = Column(String(20), nullable=True)
    cor_primaria_hex = Column(String(7), default="#2563EB", nullable=False)  # White-label
    logo_url = Column(String(500), nullable=True)                            # White-label
    ativo = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    memberships = relationship(
        "Membership", back_populates="tenant", cascade="all, delete-orphan"
    )
    assinatura = relationship(
        "AssinaturaTenant",
        back_populates="tenant",
        uselist=False,
        cascade="all, delete-orphan",
    )
    clientes_ebt = relationship(
        "ClienteEBT", back_populates="tenant", cascade="all, delete-orphan"
    )


class User(BaseSaaS):
    """Usuário autenticado na plataforma (pode pertencer a uma ou mais consultorias)."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    email = Column(String(255), nullable=False, unique=True, index=True)
    nome_completo = Column(String(200), nullable=False)
    senha_hash = Column(String(255), nullable=True)
    telefone_whatsapp = Column(String(50), nullable=True, default="")
    cargo_organizacao = Column(String(150), nullable=True, default="")
    avatar_url = Column(Text, nullable=True, default="")
    provedor_auth_sub = Column(String(255), nullable=True, unique=True)  # Ex: Auth0 / Clerk / Supabase sub
    mfa_habilitado = Column(Boolean, default=False, nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    memberships = relationship(
        "Membership", back_populates="user", cascade="all, delete-orphan"
    )


class Membership(BaseSaaS):
    """Vínculo Usuário × Tenant × Papel (RBAC), com restrição opcional por workspace EBT."""

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_membership_tenant_user"),
        Index("ix_memberships_tenant_id", "tenant_id"),
    )

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    papel = Column(String(30), nullable=False, default=PapelMembro.ANALISTA.value)
    # Quando papel == 'fundador' ou 'investidor', restringe o acesso a uma única EBT
    ebt_restrita_id = Column(
        String(36), ForeignKey("clientes_ebt.id", ondelete="SET NULL"), nullable=True
    )
    ativo = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    tenant = relationship("Tenant", back_populates="memberships")
    user = relationship("User", back_populates="memberships")


class Convite(BaseSaaS):
    """Convite enviado por um Dono/Admin para adicionar membros ao Tenant."""

    __tablename__ = "convites"
    __table_args__ = (Index("ix_convites_tenant_id", "tenant_id"),)

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    email_convidado = Column(String(255), nullable=False)
    papel = Column(String(30), nullable=False, default=PapelMembro.CONSULTOR.value)
    ebt_restrita_id = Column(
        String(36), ForeignKey("clientes_ebt.id", ondelete="SET NULL"), nullable=True
    )
    token_hash = Column(String(64), nullable=False, unique=True)
    expira_em = Column(DateTime(timezone=True), nullable=False)
    aceito_em = Column(DateTime(timezone=True), nullable=True)
    criado_em = Column(DateTime(timezone=True), default=_utc_now, nullable=False)


class AssinaturaTenant(BaseSaaS):
    """Plano contratado e limites operacionais (quotas) do Tenant."""

    __tablename__ = "assinaturas_tenant"
    __table_args__ = (Index("ix_assinaturas_tenant_id", "tenant_id", unique=True),)

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    plano_codigo = Column(
        String(30), nullable=False, default=PlanoAssinaturaCodigo.STARTER.value
    )
    status = Column(
        String(30), nullable=False, default=StatusAssinatura.TRIAL.value
    )
    provedor_cobranca = Column(String(30), default="asaas")  # stripe | asaas | pagarme
    assinatura_externa_id = Column(String(120), nullable=True)

    # Limites contratados no plano
    limite_ebts = Column(Integer, default=5, nullable=False)
    limite_cenarios_por_ebt = Column(Integer, default=3, nullable=False)
    limite_analises_ia_mes = Column(Integer, default=20, nullable=False)
    limite_pdfs_mes = Column(Integer, default=30, nullable=False)
    permite_monte_carlo = Column(Boolean, default=False, nullable=False)
    permite_white_label = Column(Boolean, default=False, nullable=False)

    criado_em = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    tenant = relationship("Tenant", back_populates="assinatura")


class UsoMedidoTenant(BaseSaaS):
    """Controle mensal de consumo de recursos (IA, PDFs, simulações) por Tenant."""

    __tablename__ = "uso_medido_tenant"
    __table_args__ = (
        UniqueConstraint("tenant_id", "ano_mes", name="uq_uso_tenant_competencia"),
        Index("ix_uso_medido_tenant_id", "tenant_id"),
    )

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    ano_mes = Column(String(7), nullable=False)  # Formato YYYY-MM
    analises_ia_realizadas = Column(Integer, default=0, nullable=False)
    pdfs_gerados = Column(Integer, default=0, nullable=False)
    simulacoes_executadas = Column(Integer, default=0, nullable=False)
    custo_ia_acumulado_usd = Column(Float, default=0.0, nullable=False)


# =============================================================================
# 2. CAMADA DE CONSULTORIA E DIAGNÓSTICO POR WORKSPACE (EBT)
# =============================================================================


class ClienteEBT(BaseSaaS):
    """
    Workspace de uma EBT (Empresa de Base Tecnológica / Startup assessorada)
    pertencente a uma Consultoria (Tenant).
    """

    __tablename__ = "clientes_ebt"
    __table_args__ = (Index("ix_clientes_ebt_tenant_id", "tenant_id"),)

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    nome_startup = Column(String(200), nullable=False)
    setor_vertical = Column(String(100), default="SaaS B2B", nullable=False)
    estagio = Column(String(50), default="Pre-Seed", nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    atualizado_em = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    tenant = relationship("Tenant", back_populates="clientes_ebt")
    lean_canvas = relationship(
        "LeanCanvasEBT",
        back_populates="ebt",
        uselist=False,
        cascade="all, delete-orphan",
    )
    premissas = relationship(
        "PremissasEBT",
        back_populates="ebt",
        uselist=False,
        cascade="all, delete-orphan",
    )
    investimentos = relationship(
        "ItemCapexEBT", back_populates="ebt", cascade="all, delete-orphan"
    )
    custos_fixos = relationship(
        "ItemOpexEBT", back_populates="ebt", cascade="all, delete-orphan"
    )
    planos_saas = relationship(
        "PlanoSaaSEBT", back_populates="ebt", cascade="all, delete-orphan"
    )
    juridico = relationship(
        "JuridicoEBT",
        back_populates="ebt",
        uselist=False,
        cascade="all, delete-orphan",
    )
    cenarios = relationship(
        "CenarioEBT", back_populates="ebt", cascade="all, delete-orphan"
    )
    versoes_premissas = relationship(
        "VersaoPremissasEBT", back_populates="ebt", cascade="all, delete-orphan"
    )
    resultados_simulacao = relationship(
        "ResultadoSimulacaoEBT", back_populates="ebt", cascade="all, delete-orphan"
    )


class LeanCanvasEBT(BaseSaaS):
    __tablename__ = "lean_canvas_ebt"
    __table_args__ = (Index("ix_lean_canvas_ebt_tenant_id", "tenant_id"),)

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    ebt_id = Column(
        String(36),
        ForeignKey("clientes_ebt.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    problema = Column(Text, default="")
    solucao_mvp = Column(Text, default="")
    mvp_descricao = Column(Text, default="")
    metricas_chave = Column(Text, default="")
    proposta_valor = Column(Text, default="")
    vantagem_injusta = Column(Text, default="")
    canais = Column(Text, default="")
    segmentos = Column(Text, default="")
    estrutura_custos = Column(Text, default="")
    fontes_receita = Column(Text, default="")
    ods_onu = Column(Text, default="")

    ebt = relationship("ClienteEBT", back_populates="lean_canvas")


class PremissasEBT(BaseSaaS):
    __tablename__ = "premissas_ebt"
    __table_args__ = (Index("ix_premissas_ebt_tenant_id", "tenant_id"),)

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    ebt_id = Column(
        String(36),
        ForeignKey("clientes_ebt.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    horizonte_meses = Column(Integer, default=36, nullable=False)
    tma_anual_pct = Column(Float, default=25.0, nullable=False)
    cac_estimado = Column(Float, default=0.0, nullable=False)
    churn_mensal_pct = Column(Float, default=5.0, nullable=False)
    conversao_freemium_pct = Column(Float, default=2.0, nullable=False)
    crescimento_mensal_pct = Column(Float, default=5.0, nullable=False)
    usuarios_freemium_base = Column(Integer, default=0, nullable=False)
    ciclo_caixa_meses = Column(Float, default=1.0, nullable=False)

    ebt = relationship("ClienteEBT", back_populates="premissas")


class ItemCapexEBT(BaseSaaS):
    __tablename__ = "itens_capex_ebt"
    __table_args__ = (Index("ix_itens_capex_ebt_tenant_id", "tenant_id"),)

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    ebt_id = Column(
        String(36), ForeignKey("clientes_ebt.id", ondelete="CASCADE"), nullable=False
    )
    categoria = Column(String(120), nullable=False)
    descricao = Column(String(500), nullable=False)
    valor = Column(Float, default=0.0, nullable=False)

    ebt = relationship("ClienteEBT", back_populates="investimentos")


class ItemOpexEBT(BaseSaaS):
    __tablename__ = "itens_opex_ebt"
    __table_args__ = (Index("ix_itens_opex_ebt_tenant_id", "tenant_id"),)

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    ebt_id = Column(
        String(36), ForeignKey("clientes_ebt.id", ondelete="CASCADE"), nullable=False
    )
    categoria = Column(String(120), nullable=False)
    descricao = Column(String(500), nullable=False)
    valor_mensal = Column(Float, default=0.0, nullable=False)

    ebt = relationship("ClienteEBT", back_populates="custos_fixos")


class PlanoSaaSEBT(BaseSaaS):
    __tablename__ = "planos_saas_ebt"
    __table_args__ = (Index("ix_planos_saas_ebt_tenant_id", "tenant_id"),)

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    ebt_id = Column(
        String(36), ForeignKey("clientes_ebt.id", ondelete="CASCADE"), nullable=False
    )
    nome_plano = Column(String(120), nullable=False)
    ticket_mensal = Column(Float, default=0.0, nullable=False)
    usuarios_ativos_base = Column(Integer, default=0, nullable=False)
    taxas_pagamento_pct = Column(Float, default=5.0, nullable=False)
    impostos_pct = Column(Float, default=6.0, nullable=False)
    custo_servidor_por_usuario = Column(Float, default=0.0, nullable=False)

    ebt = relationship("ClienteEBT", back_populates="planos_saas")


class JuridicoEBT(BaseSaaS):
    __tablename__ = "juridico_ebt"
    __table_args__ = (Index("ix_juridico_ebt_tenant_id", "tenant_id"),)

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    ebt_id = Column(
        String(36),
        ForeignKey("clientes_ebt.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    registro_inpi = Column(String(60), default="Não Iniciado", nullable=False)
    marca_status = Column(String(60), default="Não Iniciado", nullable=False)
    adequacao_lgpd = Column(Boolean, default=False, nullable=False)
    contrato_vesting = Column(Boolean, default=False, nullable=False)
    custo_estimado_legal = Column(Float, default=0.0, nullable=False)

    ebt = relationship("ClienteEBT", back_populates="juridico")


# =============================================================================
# 3. CENÁRIOS, VERSÕES IMUTÁVEIS E AUDITORIA DE SIMULAÇÃO
# =============================================================================


class CenarioEBT(BaseSaaS):
    """Cenário nomeado (ex.: Base, Otimista, Pessimista, Rodada Seed) por EBT."""

    __tablename__ = "cenarios_ebt"
    __table_args__ = (Index("ix_cenarios_ebt_tenant_id", "tenant_id"),)

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    ebt_id = Column(
        String(36), ForeignKey("clientes_ebt.id", ondelete="CASCADE"), nullable=False
    )
    nome = Column(String(100), nullable=False, default="Base")
    tipo_cenario = Column(String(30), nullable=False, default="base")
    descricao = Column(Text, default="")
    criado_em = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    ebt = relationship("ClienteEBT", back_populates="cenarios")


class VersaoPremissasEBT(BaseSaaS):
    """
    Snapshot imutável das entradas (Premissas + Capex + Opex + Planos SaaS)
    no momento de uma simulação, garantindo reprodutibilidade histórica.
    """

    __tablename__ = "versoes_premissas_ebt"
    __table_args__ = (Index("ix_versoes_premissas_ebt_tenant_id", "tenant_id"),)

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    ebt_id = Column(
        String(36), ForeignKey("clientes_ebt.id", ondelete="CASCADE"), nullable=False
    )
    numero_versao = Column(Integer, nullable=False)
    hash_entrada_sha256 = Column(String(64), nullable=False, index=True)
    payload_entrada_json = Column(Text, nullable=False)  # EntradaSimulacaoSaaS serializada
    criado_por_user_id = Column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    criado_em = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    ebt = relationship("ClienteEBT", back_populates="versoes_premissas")


class ResultadoSimulacaoEBT(BaseSaaS):
    """
    Registro auditável de uma execução do motor financeiro ligada a uma VersaoPremissasEBT.
    """

    __tablename__ = "resultados_simulacao_ebt"
    __table_args__ = (Index("ix_resultados_simulacao_ebt_tenant_id", "tenant_id"),)

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    ebt_id = Column(
        String(36), ForeignKey("clientes_ebt.id", ondelete="CASCADE"), nullable=False
    )
    versao_premissas_id = Column(
        String(36),
        ForeignKey("versoes_premissas_ebt.id", ondelete="CASCADE"),
        nullable=False,
    )
    versao_motor = Column(String(30), nullable=False)
    cenario_tipo = Column(String(30), nullable=False, default="base")

    # Indicadores-chave indexados para busca e comparação rápida entre EBTs do portfólio
    mrr_bruto_base = Column(Float, nullable=False)
    vpl = Column(Float, nullable=False)
    tir_anual_pct = Column(Float, nullable=False)
    validade_tir = Column(Boolean, nullable=False)
    ltv_cac = Column(Float, nullable=False)
    possui_alertas_criticos = Column(Boolean, nullable=False, default=False)

    # Saída completa serializada (ResultadoSimulacaoSaaS JSON)
    payload_resultado_json = Column(Text, nullable=False)
    criado_em = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    ebt = relationship("ClienteEBT", back_populates="resultados_simulacao")


# =============================================================================
# 4. GOVERNANÇA DE IA, RELATÓRIOS E COMPARTILHAMENTO EXTERNO
# =============================================================================


class AnaliseIAEBT(BaseSaaS):
    """Registro governado de chamadas à IA com controle de revisão humana e cache."""

    __tablename__ = "analises_ia_ebt"
    __table_args__ = (Index("ix_analises_ia_ebt_tenant_id", "tenant_id"),)

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    ebt_id = Column(
        String(36), ForeignKey("clientes_ebt.id", ondelete="CASCADE"), nullable=False
    )
    resultado_simulacao_id = Column(
        String(36),
        ForeignKey("resultados_simulacao_ebt.id", ondelete="SET NULL"),
        nullable=True,
    )
    provedor = Column(String(40), nullable=False, default="google-gemini")
    modelo = Column(String(80), nullable=False, default="gemini-2.5-flash")
    versao_prompt = Column(String(30), nullable=False, default="v1.0-vc-comite")
    hash_entrada_simulacao = Column(String(64), nullable=False, index=True)
    parecer_gerado_md = Column(Text, nullable=False)
    parecer_revisado_consultor_md = Column(Text, nullable=True)
    aprovado_pelo_consultor = Column(Boolean, default=False, nullable=False)
    aprovado_por_user_id = Column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    custo_estimado_usd = Column(Float, default=0.0, nullable=False)
    criado_em = Column(DateTime(timezone=True), default=_utc_now, nullable=False)


class RelatorioDossieEBT(BaseSaaS):
    """Dossiê PDF emitido, versionado e assinado com hash SHA-256."""

    __tablename__ = "relatorios_dossie_ebt"
    __table_args__ = (Index("ix_relatorios_dossie_ebt_tenant_id", "tenant_id"),)

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    ebt_id = Column(
        String(36), ForeignKey("clientes_ebt.id", ondelete="CASCADE"), nullable=False
    )
    resultado_simulacao_id = Column(
        String(36),
        ForeignKey("resultados_simulacao_ebt.id", ondelete="RESTRICT"),
        nullable=False,
    )
    storage_key = Column(String(500), nullable=False)  # Caminho no S3 / R2
    sha256_pdf = Column(String(64), nullable=False)
    criado_por_user_id = Column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    criado_em = Column(DateTime(timezone=True), default=_utc_now, nullable=False)


class ShareLinkInvestidor(BaseSaaS):
    """Link temporário somente-leitura para banca avaliadora ou fundo de investimento."""

    __tablename__ = "share_links_investidor"
    __table_args__ = (Index("ix_share_links_tenant_id", "tenant_id"),)

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    ebt_id = Column(
        String(36), ForeignKey("clientes_ebt.id", ondelete="CASCADE"), nullable=False
    )
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expira_em = Column(DateTime(timezone=True), nullable=False)
    revogado = Column(Boolean, default=False, nullable=False)
    acessos_realizados = Column(Integer, default=0, nullable=False)
    criado_em = Column(DateTime(timezone=True), default=_utc_now, nullable=False)


class StatusJobAssincrono(str, Enum):
    PENDENTE = "pendente"
    PROCESSANDO = "processando"
    CONCLUIDO = "concluido"
    ERRO = "erro"


class JobAssincronoSaaS(BaseSaaS):
    """
    Fila e rastreamento de jobs assíncronos (IA, PDF e Simulações Pesadas)
    por Tenant, exibindo status de processamento na UI.
    """

    __tablename__ = "jobs_assincronos_saas"
    __table_args__ = (Index("ix_jobs_assincronos_tenant_id", "tenant_id"),)

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    ebt_id = Column(
        String(36), ForeignKey("clientes_ebt.id", ondelete="CASCADE"), nullable=True
    )
    tipo_job = Column(String(50), nullable=False)  # ia.parecer | pdf.dossie | simulacao.monte_carlo
    status = Column(
        String(30), nullable=False, default=StatusJobAssincrono.PENDENTE.value
    )
    progresso_pct = Column(Integer, default=0, nullable=False)
    referencia_resultado_id = Column(String(36), nullable=True)
    mensagem_erro = Column(Text, nullable=True)
    criado_por_user_id = Column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    criado_em = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    concluido_em = Column(DateTime(timezone=True), nullable=True)


# =============================================================================
# 5. AUDITORIA IMUTÁVEL (OBRIGATÓRIA PARA CONSULTORIA E LGPD)
# =============================================================================


class AuditLog(BaseSaaS):
    """Trilha de auditoria registrando quem alterou o quê, quando e em qual Tenant."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_criado", "tenant_id", "criado_em"),
    )

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    acao = Column(String(80), nullable=False)            # Ex: "ebt.criar", "simulacao.executar"
    entidade_tipo = Column(String(80), nullable=False)   # Ex: "ClienteEBT", "PremissasEBT"
    entidade_id = Column(String(36), nullable=False)
    resumo = Column(String(500), nullable=False)
    dados_anteriores_json = Column(Text, nullable=True)
    dados_novos_json = Column(Text, nullable=True)
    criado_em = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
