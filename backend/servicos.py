"""
Serviços de Domínio do Núcleo SaaS (Fase 1).
Orquestra Identidade/Tenants, RBAC, Limites de Plano (Quotas),
Workspaces por EBT, Versionamento Imutável de Simulações, Links de Investidor
e Auditoria Obrigatória.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from core_financeiro import (
    EntradaSimulacaoSaaS,
    ResultadoSimulacaoSaaS,
    TipoCenario,
    executar_simulacao_saas,
)

from .auditoria import registrar_evento_auditoria
from .models import (
    AssinaturaTenant,
    CenarioEBT,
    ClienteEBT,
    ItemCapexEBT,
    ItemOpexEBT,
    JuridicoEBT,
    LeanCanvasEBT,
    Membership,
    PapelMembro,
    PlanoAssinaturaCodigo,
    PlanoSaaSEBT,
    PremissasEBT,
    ResultadoSimulacaoEBT,
    ShareLinkInvestidor,
    StatusAssinatura,
    Tenant,
    User,
    UsoMedidoTenant,
    VersaoPremissasEBT,
)
from .rbac import PermissaoSaaS, verificar_permissao_rbac


class ErroLimitePlanoSaaS(RuntimeError):
    """Exceção disparada quando o Tenant atinge o limite contratado em seu plano."""


CONFIG_LIMITES_POR_PLANO: Dict[PlanoAssinaturaCodigo, Dict[str, object]] = {
    PlanoAssinaturaCodigo.FREE: {
        "limite_ebts": 1,
        "limite_cenarios_por_ebt": 1,
        "limite_simulacoes_mes": 3,
        "limite_analises_ia_mes": 1,
        "limite_pdfs_mes": 1,
        "permite_monte_carlo": False,
        "permite_white_label": False,
    },
    PlanoAssinaturaCodigo.STARTER: {
        "limite_ebts": 3,
        "limite_cenarios_por_ebt": 3,
        "limite_simulacoes_mes": 9999,
        "limite_analises_ia_mes": 15,
        "limite_pdfs_mes": 20,
        "permite_monte_carlo": False,
        "permite_white_label": False,
    },
    PlanoAssinaturaCodigo.PRO: {
        "limite_ebts": 15,
        "limite_cenarios_por_ebt": 10,
        "limite_simulacoes_mes": 99999,
        "limite_analises_ia_mes": 100,
        "limite_pdfs_mes": 150,
        "permite_monte_carlo": True,
        "permite_white_label": True,
    },
    PlanoAssinaturaCodigo.ENTERPRISE: {
        "limite_ebts": 9999,
        "limite_cenarios_por_ebt": 100,
        "limite_simulacoes_mes": 999999,
        "limite_analises_ia_mes": 2000,
        "limite_pdfs_mes": 5000,
        "permite_monte_carlo": True,
        "permite_white_label": True,
    },
}


def _competencia_atual() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def obter_ou_criar_uso_mensal(db: Session, tenant_id: str) -> UsoMedidoTenant:
    competencia = _competencia_atual()
    uso = (
        db.query(UsoMedidoTenant)
        .filter(
            UsoMedidoTenant.tenant_id == tenant_id,
            UsoMedidoTenant.ano_mes == competencia,
        )
        .first()
    )
    if uso is None:
        uso = UsoMedidoTenant(tenant_id=tenant_id, ano_mes=competencia)
        db.add(uso)
        db.flush()
    return uso


def criar_tenant_consultoria(
    db: Session,
    *,
    nome_consultoria: str,
    slug: str,
    email_dono: str,
    nome_dono: str,
    plano: PlanoAssinaturaCodigo = PlanoAssinaturaCodigo.STARTER,
    cnpj: Optional[str] = None,
) -> Tuple[Tenant, User, Membership]:
    """
    Realiza o onboarding inicial de uma Consultoria (Tenant), criando ou reutilizando
    o usuário dono, configurando a assinatura/limites e registrando o AuditLog inicial.
    """
    tenant = Tenant(nome=nome_consultoria.strip(), slug=slug.strip().lower(), cnpj=cnpj)
    db.add(tenant)
    db.flush()

    user = db.query(User).filter(User.email == email_dono.strip().lower()).first()
    if user is None:
        user = User(
            email=email_dono.strip().lower(),
            nome_completo=nome_dono.strip(),
        )
        db.add(user)
        db.flush()

    membership = Membership(
        tenant_id=tenant.id,
        user_id=user.id,
        papel=PapelMembro.DONO.value,
        ativo=True,
    )
    db.add(membership)

    cfg = CONFIG_LIMITES_POR_PLANO[plano]
    assinatura = AssinaturaTenant(
        tenant_id=tenant.id,
        plano_codigo=plano.value,
        status=StatusAssinatura.ATIVA.value,
        limite_ebts=int(cfg["limite_ebts"]),
        limite_cenarios_por_ebt=int(cfg["limite_cenarios_por_ebt"]),
        limite_analises_ia_mes=int(cfg["limite_analises_ia_mes"]),
        limite_pdfs_mes=int(cfg["limite_pdfs_mes"]),
        permite_monte_carlo=bool(cfg["permite_monte_carlo"]),
        permite_white_label=bool(cfg["permite_white_label"]),
    )
    db.add(assinatura)
    db.flush()

    obter_ou_criar_uso_mensal(db, tenant.id)

    registrar_evento_auditoria(
        db,
        tenant_id=tenant.id,
        user_id=user.id,
        acao="tenant.onboarding",
        entidade_tipo="Tenant",
        entidade_id=tenant.id,
        resumo=f"Consultoria '{tenant.nome}' criada no plano '{plano.value}'.",
        dados_novos={"slug": tenant.slug, "plano": plano.value},
    )

    return tenant, user, membership


def criar_workspace_ebt(
    db: Session,
    *,
    membership: Membership,
    nome_startup: str,
    setor_vertical: str = "SaaS B2B",
    estagio: str = "Pre-Seed",
) -> ClienteEBT:
    """
    Cria um novo workspace de empresa assessorada (EBT) dentro do Tenant,
    verificando permissão RBAC e limite de EBTs do plano contratado.
    """
    verificar_permissao_rbac(membership, PermissaoSaaS.EBT_CRIAR)

    tenant_id = membership.tenant_id
    assinatura = (
        db.query(AssinaturaTenant)
        .filter(AssinaturaTenant.tenant_id == tenant_id)
        .first()
    )
    total_ebts_ativas = (
        db.query(ClienteEBT)
        .filter(ClienteEBT.tenant_id == tenant_id, ClienteEBT.ativo.is_(True))
        .count()
    )

    if assinatura and total_ebts_ativas >= assinatura.limite_ebts:
        raise ErroLimitePlanoSaaS(
            f"Limite do plano '{assinatura.plano_codigo}' atingido: máximo de "
            f"{assinatura.limite_ebts} EBTs ativas por consultoria."
        )

    ebt = ClienteEBT(
        tenant_id=tenant_id,
        nome_startup=nome_startup.strip(),
        setor_vertical=setor_vertical,
        estagio=estagio,
    )
    db.add(ebt)
    db.flush()

    # Inicializa entidades 1:1 e cenário Base padrão
    db.add(LeanCanvasEBT(tenant_id=tenant_id, ebt_id=ebt.id))
    db.add(PremissasEBT(tenant_id=tenant_id, ebt_id=ebt.id))
    db.add(JuridicoEBT(tenant_id=tenant_id, ebt_id=ebt.id))
    db.add(
        CenarioEBT(
            tenant_id=tenant_id,
            ebt_id=ebt.id,
            nome="Cenário Base",
            tipo_cenario=TipoCenario.BASE.value,
        )
    )
    db.flush()

    registrar_evento_auditoria(
        db,
        tenant_id=tenant_id,
        user_id=membership.user_id,
        acao="ebt.criar",
        entidade_tipo="ClienteEBT",
        entidade_id=ebt.id,
        resumo=f"Workspace EBT '{ebt.nome_startup}' criado.",
        dados_novos={
            "nome_startup": ebt.nome_startup,
            "setor_vertical": ebt.setor_vertical,
            "estagio": ebt.estagio,
        },
    )
    return ebt


def listar_workspaces_ebt_visiveis(
    db: Session, *, membership: Membership
) -> List[ClienteEBT]:
    """
    Lista os workspaces EBT visíveis para o membro segundo seu papel RBAC:
    - Dono/Admin/Consultor/Analista: todas as EBTs do seu Tenant.
    - Fundador/Investidor: exclusivamente a sua `ebt_restrita_id`.
    """
    verificar_permissao_rbac(membership, PermissaoSaaS.EBT_VISUALIZAR)
    query = db.query(ClienteEBT).filter(
        ClienteEBT.tenant_id == membership.tenant_id,
        ClienteEBT.ativo.is_(True),
    )
    if membership.papel in (PapelMembro.FUNDADOR.value, PapelMembro.INVESTIDOR.value):
        query = query.filter(ClienteEBT.id == membership.ebt_restrita_id)
    return query.order_by(ClienteEBT.criado_em.asc()).all()


def atualizar_premissas_ebt(
    db: Session,
    *,
    membership: Membership,
    ebt_id: str,
    horizonte_meses: Optional[int] = None,
    tma_anual_pct: Optional[float] = None,
    cac_estimado: Optional[float] = None,
    churn_mensal_pct: Optional[float] = None,
    conversao_freemium_pct: Optional[float] = None,
    crescimento_mensal_pct: Optional[float] = None,
    usuarios_freemium_base: Optional[int] = None,
) -> PremissasEBT:
    """Atualiza premissas de uma EBT com verificação RBAC de escopo e trilha de auditoria."""
    verificar_permissao_rbac(
        membership, PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO, ebt_alvo_id=ebt_id
    )

    premissas = (
        db.query(PremissasEBT)
        .filter(
            PremissasEBT.tenant_id == membership.tenant_id,
            PremissasEBT.ebt_id == ebt_id,
        )
        .first()
    )
    if premissas is None:
        raise LookupError(f"Premissas não encontradas para EBT '{ebt_id}'.")

    antes = {
        "horizonte_meses": premissas.horizonte_meses,
        "tma_anual_pct": premissas.tma_anual_pct,
        "cac_estimado": premissas.cac_estimado,
        "churn_mensal_pct": premissas.churn_mensal_pct,
        "conversao_freemium_pct": premissas.conversao_freemium_pct,
        "crescimento_mensal_pct": premissas.crescimento_mensal_pct,
        "usuarios_freemium_base": premissas.usuarios_freemium_base,
    }

    if horizonte_meses is not None:
        premissas.horizonte_meses = horizonte_meses
    if tma_anual_pct is not None:
        premissas.tma_anual_pct = tma_anual_pct
    if cac_estimado is not None:
        premissas.cac_estimado = cac_estimado
    if churn_mensal_pct is not None:
        premissas.churn_mensal_pct = churn_mensal_pct
    if conversao_freemium_pct is not None:
        premissas.conversao_freemium_pct = conversao_freemium_pct
    if crescimento_mensal_pct is not None:
        premissas.crescimento_mensal_pct = crescimento_mensal_pct
    if usuarios_freemium_base is not None:
        premissas.usuarios_freemium_base = usuarios_freemium_base

    depois = {
        "horizonte_meses": premissas.horizonte_meses,
        "tma_anual_pct": premissas.tma_anual_pct,
        "cac_estimado": premissas.cac_estimado,
        "churn_mensal_pct": premissas.churn_mensal_pct,
        "conversao_freemium_pct": premissas.conversao_freemium_pct,
        "crescimento_mensal_pct": premissas.crescimento_mensal_pct,
        "usuarios_freemium_base": premissas.usuarios_freemium_base,
    }
    db.flush()

    registrar_evento_auditoria(
        db,
        tenant_id=membership.tenant_id,
        user_id=membership.user_id,
        acao="premissas.atualizar",
        entidade_tipo="PremissasEBT",
        entidade_id=premissas.id,
        resumo=f"Premissas financeiras da EBT '{ebt_id}' atualizadas.",
        dados_anteriores=antes,
        dados_novos=depois,
    )
    return premissas


def executar_e_versionar_simulacao_ebt(
    db: Session,
    *,
    membership: Membership,
    ebt_id: str,
    cenario: TipoCenario = TipoCenario.BASE,
) -> Tuple[VersaoPremissasEBT, ResultadoSimulacaoEBT, ResultadoSimulacaoSaaS]:
    """
    Executa o motor financeiro puro para uma EBT, grava um snapshot imutável das
    entradas (`VersaoPremissasEBT`), persiste o resultado auditável (`ResultadoSimulacaoEBT`),
    contabiliza o uso medido do Tenant e gera registro em `AuditLog`.
    """
    verificar_permissao_rbac(
        membership, PermissaoSaaS.SIMULACAO_EXECUTAR, ebt_alvo_id=ebt_id
    )

    ebt = (
        db.query(ClienteEBT)
        .filter(
            ClienteEBT.tenant_id == membership.tenant_id,
            ClienteEBT.id == ebt_id,
        )
        .first()
    )
    if ebt is None:
        raise LookupError(f"Workspace EBT '{ebt_id}' não encontrado no Tenant.")

    assinatura = (
        db.query(AssinaturaTenant)
        .filter(AssinaturaTenant.tenant_id == membership.tenant_id)
        .first()
    )
    uso = obter_ou_criar_uso_mensal(db, membership.tenant_id)
    if assinatura is not None:
        try:
            codigo_enum = PlanoAssinaturaCodigo(assinatura.plano_codigo)
            cfg_plano = CONFIG_LIMITES_POR_PLANO.get(codigo_enum, {})
        except ValueError:
            cfg_plano = {}
        limite_sim = int(cfg_plano.get("limite_simulacoes_mes", 9999))
        if uso.simulacoes_executadas >= limite_sim:
            raise ErroLimitePlanoSaaS(
                f"Limite mensal de Simulações atingido no plano '{assinatura.plano_codigo}' "
                f"({uso.simulacoes_executadas}/{limite_sim} simulações no mês {uso.ano_mes}). "
                f"Faça upgrade para o plano Starter ou Pro para simulações ilimitadas."
            )
        if (
            assinatura.plano_codigo == PlanoAssinaturaCodigo.FREE.value
            and cenario != TipoCenario.BASE
        ):
            raise ErroLimitePlanoSaaS(
                "O plano 'free' permite versionar apenas o Cenário Base. "
                "Faça upgrade para desbloquear múltiplos cenarios."
            )

    entrada_pydantic = EntradaSimulacaoSaaS.from_orm_projeto(ebt)
    resultado_pydantic = executar_simulacao_saas(entrada_pydantic, cenario=cenario)

    ultima_versao = (
        db.query(VersaoPremissasEBT)
        .filter(
            VersaoPremissasEBT.tenant_id == membership.tenant_id,
            VersaoPremissasEBT.ebt_id == ebt.id,
        )
        .count()
    )
    novo_numero_versao = ultima_versao + 1

    versao_premissas = VersaoPremissasEBT(
        tenant_id=membership.tenant_id,
        ebt_id=ebt.id,
        numero_versao=novo_numero_versao,
        hash_entrada_sha256=resultado_pydantic.hash_entrada,
        payload_entrada_json=entrada_pydantic.model_dump_json(),
        criado_por_user_id=membership.user_id,
    )
    db.add(versao_premissas)
    db.flush()

    registro_resultado = ResultadoSimulacaoEBT(
        tenant_id=membership.tenant_id,
        ebt_id=ebt.id,
        versao_premissas_id=versao_premissas.id,
        versao_motor=resultado_pydantic.versao_motor,
        cenario_tipo=cenario.value,
        mrr_bruto_base=resultado_pydantic.dre_base.mrr_bruto_total,
        vpl=resultado_pydantic.viabilidade.valor_presente_liquido_vpl,
        tir_anual_pct=resultado_pydantic.viabilidade.taxa_interna_retorno_anual_pct,
        validade_tir=resultado_pydantic.viabilidade.validade_da_tir,
        ltv_cac=resultado_pydantic.unit_economics.indice_ltv_cac,
        possui_alertas_criticos=resultado_pydantic.possui_alertas_criticos,
        payload_resultado_json=resultado_pydantic.model_dump_json(),
    )
    db.add(registro_resultado)

    uso = obter_ou_criar_uso_mensal(db, membership.tenant_id)
    uso.simulacoes_executadas += 1
    db.flush()

    registrar_evento_auditoria(
        db,
        tenant_id=membership.tenant_id,
        user_id=membership.user_id,
        acao="simulacao.executar",
        entidade_tipo="ResultadoSimulacaoEBT",
        entidade_id=registro_resultado.id,
        resumo=(
            f"Simulação v{novo_numero_versao} ({cenario.value}) executada para '{ebt.nome_startup}' "
            f"[motor={resultado_pydantic.versao_motor}, hash={resultado_pydantic.hash_entrada[:12]}]."
        ),
        dados_novos={
            "versao_premissas": novo_numero_versao,
            "hash_entrada": resultado_pydantic.hash_entrada,
            "vpl": registro_resultado.vpl,
            "alertas_criticos": registro_resultado.possui_alertas_criticos,
        },
    )

    return versao_premissas, registro_resultado, resultado_pydantic


def criar_link_compartilhamento_investidor(
    db: Session,
    *,
    membership: Membership,
    ebt_id: str,
    dias_validade: int = 7,
) -> Tuple[str, ShareLinkInvestidor]:
    """
    Gera um token de acesso somente-leitura com expiração para investidor/banca.
    Persiste apenas o hash SHA-256 do token no banco (segurança contra vazamento).
    """
    verificar_permissao_rbac(
        membership, PermissaoSaaS.SHARE_LINK_CRIAR, ebt_alvo_id=ebt_id
    )

    token_claro = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token_claro.encode("utf-8")).hexdigest()
    expira_em = datetime.now(timezone.utc) + timedelta(days=max(1, dias_validade))

    share_link = ShareLinkInvestidor(
        tenant_id=membership.tenant_id,
        ebt_id=ebt_id,
        token_hash=token_hash,
        expira_em=expira_em,
        revogado=False,
    )
    db.add(share_link)
    db.flush()

    registrar_evento_auditoria(
        db,
        tenant_id=membership.tenant_id,
        user_id=membership.user_id,
        acao="share_link.criar",
        entidade_tipo="ShareLinkInvestidor",
        entidade_id=share_link.id,
        resumo=f"Link temporário de investidor criado para EBT '{ebt_id}' (expira em {dias_validade}d).",
    )
    return token_claro, share_link


def validar_token_investidor(
    db: Session, *, token_claro: str, agora: Optional[datetime] = None
) -> ShareLinkInvestidor:
    """
    Valida um token de compartilhamento de investidor (verifica existência,
    revogação e data de expiração) e contabiliza o acesso.
    """
    instante = agora or datetime.now(timezone.utc)
    token_hash = hashlib.sha256(token_claro.encode("utf-8")).hexdigest()

    link = (
        db.query(ShareLinkInvestidor)
        .filter(ShareLinkInvestidor.token_hash == token_hash)
        .first()
    )
    if link is None or link.revogado:
        raise PermissionError("Link de investidor inválido ou revogado.")

    expiracao = link.expira_em
    if expiracao.tzinfo is None:
        expiracao = expiracao.replace(tzinfo=timezone.utc)

    if instante >= expiracao:
        raise PermissionError("Link de investidor expirado.")

    link.acessos_realizados += 1
    db.flush()
    return link


def alterar_plano_assinatura_tenant(
    db: Session,
    *,
    membership: Membership,
    novo_plano: PlanoAssinaturaCodigo,
) -> AssinaturaTenant:
    """
    Atualiza o plano de assinatura do Tenant (ex.: FREE -> STARTER -> PRO -> ENTERPRISE),
    reconfigurando automaticamente todos os limites e feature flags.
    Requer permissão RBAC `TENANT_GERENCIAR_COBRANCA` (exclusiva do Dono).
    """
    verificar_permissao_rbac(membership, PermissaoSaaS.TENANT_GERENCIAR_COBRANCA)

    assinatura = (
        db.query(AssinaturaTenant)
        .filter(AssinaturaTenant.tenant_id == membership.tenant_id)
        .first()
    )
    if assinatura is None:
        raise LookupError("Assinatura não encontrada para o Tenant atual.")

    plano_anterior = assinatura.plano_codigo
    cfg = CONFIG_LIMITES_POR_PLANO[novo_plano]

    assinatura.plano_codigo = novo_plano.value
    assinatura.limite_ebts = int(cfg["limite_ebts"])
    assinatura.limite_cenarios_por_ebt = int(cfg["limite_cenarios_por_ebt"])
    assinatura.limite_analises_ia_mes = int(cfg["limite_analises_ia_mes"])
    assinatura.limite_pdfs_mes = int(cfg["limite_pdfs_mes"])
    assinatura.permite_monte_carlo = bool(cfg["permite_monte_carlo"])
    assinatura.permite_white_label = bool(cfg["permite_white_label"])
    db.flush()

    registrar_evento_auditoria(
        db,
        tenant_id=membership.tenant_id,
        user_id=membership.user_id,
        acao="assinatura.alterar_plano",
        entidade_tipo="AssinaturaTenant",
        entidade_id=assinatura.id,
        resumo=f"Plano do Tenant alterado de '{plano_anterior}' para '{novo_plano.value}'.",
        dados_anteriores={"plano": plano_anterior},
        dados_novos={"plano": novo_plano.value, **cfg},
    )
    return assinatura
