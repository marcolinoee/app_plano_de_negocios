"""
Bootstrap e Migração Automática de Dados Legados (SQLite Local -> Núcleo Multi-Tenant SaaS).
Garante que:
1. As tabelas multi-tenant (`BaseSaaS`) existam no banco local.
2. Exista ao menos uma Consultoria (Tenant) padrão com perfis RBAC prontos para uso
   (Dono, Consultor, Fundador e Investidor).
3. Quaisquer startups legadas na tabela `projetos` (`ProjetoDB`) sejam migradas de forma
   transparente e sem perda de dados para `clientes_ebt` (`ClienteEBT`).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .auditoria import registrar_evento_auditoria
from .auth_oauth import (
    SENHA_SUPERADMIN_INICIAL,
    garantir_superadmin_inicial,
    gerar_hash_senha,
)
from .database import criar_session_factory, sessao_por_requisicao
from .models import (
    BaseSaaS,
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
    Tenant,
    User,
)
from .servicos import (
    criar_tenant_consultoria,
    criar_workspace_ebt,
    obter_ou_criar_uso_mensal,
)


def _migrar_colunas_users_se_necessario(engine: Engine) -> None:
    """
    Garante que bancos SQLite/PostgreSQL criados em versões anteriores recebam
    as colunas de autenticação por senha e perfil de usuário sem perda de dados.
    """
    try:
        insp = inspect(engine)
        if not insp.has_table("users"):
            return
        colunas_existentes = {c["name"] for c in insp.get_columns("users")}
        novas_colunas = [
            ("senha_hash", "VARCHAR(255)"),
            ("telefone_whatsapp", "VARCHAR(50) DEFAULT ''"),
            ("cargo_organizacao", "VARCHAR(150) DEFAULT ''"),
            ("avatar_url", "TEXT DEFAULT ''"),
        ]
        with engine.begin() as conn:
            for nome_col, tipo_sql in novas_colunas:
                if nome_col not in colunas_existentes:
                    conn.execute(
                        text(f"ALTER TABLE users ADD COLUMN {nome_col} {tipo_sql}")
                    )
    except Exception:
        pass


def inicializar_banco_saas(
    engine: Engine,
    classe_projeto_legado: Optional[type] = None,
) -> sessionmaker:
    """
    Cria as tabelas do modelo SaaS no `engine` fornecido, executa o bootstrap
    do Tenant padrão e importa projetos legados caso existam.
    """
    BaseSaaS.metadata.create_all(engine, checkfirst=True)
    _migrar_colunas_users_se_necessario(engine)
    factory = criar_session_factory(engine)

    for tentativa in range(3):
        try:
            with sessao_por_requisicao(factory, bypass_rls=True) as db:
                tenant_padrao, memb_dono = _garantir_tenant_padrao(db)
                _migrar_projetos_legados_se_necessario(
                    db,
                    tenant=tenant_padrao,
                    membership_dono=memb_dono,
                    classe_projeto_legado=classe_projeto_legado,
                )
                garantir_superadmin_inicial(db)
                _garantir_membros_demonstracao_rbac(db, tenant=tenant_padrao)
                obter_ou_criar_uso_mensal(db, tenant_padrao.id)
            break
        except Exception:
            if tentativa == 2:
                pass

    return factory


def _garantir_tenant_padrao(db: Session) -> Tuple[Tenant, Membership]:
    tenant = db.query(Tenant).order_by(Tenant.criado_em.asc()).first()
    if tenant is not None:
        memb_dono = (
            db.query(Membership)
            .filter(
                Membership.tenant_id == tenant.id,
                Membership.papel == PapelMembro.DONO.value,
            )
            .first()
        )
        if memb_dono is not None:
            return tenant, memb_dono

    tenant, _, memb_dono = criar_tenant_consultoria(
        db,
        nome_consultoria="Master Management Venture Partners",
        slug="master-vc",
        email_dono="dono@mastervc.com.br",
        nome_dono="Diretor da Consultoria (Dono)",
        plano=PlanoAssinaturaCodigo.PRO,
        cnpj="00.000.000/0001-91",
    )
    return tenant, memb_dono


def _migrar_projetos_legados_se_necessario(
    db: Session,
    *,
    tenant: Tenant,
    membership_dono: Membership,
    classe_projeto_legado: Optional[type],
) -> None:
    total_ebts = (
        db.query(ClienteEBT).filter(ClienteEBT.tenant_id == tenant.id).count()
    )
    if total_ebts > 0:
        return

    projetos_legados: List[object] = []
    if classe_projeto_legado is not None:
        try:
            projetos_legados = db.query(classe_projeto_legado).all()
        except Exception:
            projetos_legados = []

    if not projetos_legados:
        criar_workspace_ebt(
            db,
            membership=membership_dono,
            nome_startup="Nova Startup TIC",
            setor_vertical="SaaS B2B",
            estagio="Pre-Seed",
        )
        return

    for proj in projetos_legados:
        nome = getattr(proj, "nome_startup", None) or "Startup Migrada"
        ebt = ClienteEBT(
            tenant_id=tenant.id,
            nome_startup=nome,
            setor_vertical="SaaS B2B",
            estagio="Pre-Seed",
        )
        db.add(ebt)
        db.flush()

        lc_old = getattr(proj, "lean_canvas", None)
        db.add(
            LeanCanvasEBT(
                tenant_id=tenant.id,
                ebt_id=ebt.id,
                problema=getattr(lc_old, "problema", "") or "",
                solucao_mvp=getattr(lc_old, "solucao_mvp", "") or "",
                mvp_descricao=getattr(lc_old, "mvp_descricao", "") or "",
                metricas_chave=getattr(lc_old, "metricas_chave", "") or "",
                proposta_valor=getattr(lc_old, "proposta_valor", "") or "",
                vantagem_injusta=getattr(lc_old, "vantagem_injusta", "") or "",
                canais=getattr(lc_old, "canais", "") or "",
                segmentos=getattr(lc_old, "segmentos", "") or "",
                estrutura_custos=getattr(lc_old, "estrutura_custos", "") or "",
                fontes_receita=getattr(lc_old, "fontes_receita", "") or "",
                ods_onu=getattr(lc_old, "ods_onu", "") or "",
            )
        )

        pr_old = getattr(proj, "premissas", None)
        db.add(
            PremissasEBT(
                tenant_id=tenant.id,
                ebt_id=ebt.id,
                horizonte_meses=int(getattr(pr_old, "horizonte_meses", 36) or 36),
                tma_anual_pct=float(getattr(pr_old, "tma_anual_pct", 25.0) or 25.0),
                cac_estimado=float(getattr(pr_old, "cac_estimado", 0.0) or 0.0),
                churn_mensal_pct=float(getattr(pr_old, "churn_mensal_pct", 5.0) or 5.0),
                conversao_freemium_pct=float(
                    getattr(pr_old, "conversao_freemium_pct", 2.0) or 2.0
                ),
                crescimento_mensal_pct=float(
                    getattr(pr_old, "crescimento_mensal_pct", 5.0) or 5.0
                ),
                usuarios_freemium_base=int(
                    getattr(pr_old, "usuarios_freemium_base", 0) or 0
                ),
            )
        )

        jur_old = getattr(proj, "juridico", None)
        db.add(
            JuridicoEBT(
                tenant_id=tenant.id,
                ebt_id=ebt.id,
                registro_inpi=getattr(jur_old, "registro_inpi", "Não Iniciado")
                or "Não Iniciado",
                marca_status=getattr(jur_old, "marca_status", "Não Iniciado")
                or "Não Iniciado",
                adequacao_lgpd=bool(getattr(jur_old, "adequacao_lgpd", False)),
                contrato_vesting=bool(getattr(jur_old, "contrato_vesting", False)),
                custo_estimado_legal=float(
                    getattr(jur_old, "custo_estimado_legal", 0.0) or 0.0
                ),
            )
        )

        db.add(
            CenarioEBT(
                tenant_id=tenant.id,
                ebt_id=ebt.id,
                nome="Cenário Base",
                tipo_cenario="base",
            )
        )

        for inv in getattr(proj, "investimentos", None) or []:
            db.add(
                ItemCapexEBT(
                    tenant_id=tenant.id,
                    ebt_id=ebt.id,
                    categoria=getattr(inv, "categoria", "Outros") or "Outros",
                    descricao=getattr(inv, "descricao", "") or "",
                    valor=float(getattr(inv, "valor", 0.0) or 0.0),
                )
            )

        for custo in getattr(proj, "custos_fixos", None) or []:
            db.add(
                ItemOpexEBT(
                    tenant_id=tenant.id,
                    ebt_id=ebt.id,
                    categoria=getattr(custo, "categoria", "Outros") or "Outros",
                    descricao=getattr(custo, "descricao", "") or "",
                    valor_mensal=float(getattr(custo, "valor_mensal", 0.0) or 0.0),
                )
            )

        for pl in getattr(proj, "planos_saas", None) or []:
            db.add(
                PlanoSaaSEBT(
                    tenant_id=tenant.id,
                    ebt_id=ebt.id,
                    nome_plano=getattr(pl, "nome_plano", "Plano") or "Plano",
                    ticket_mensal=float(getattr(pl, "ticket_mensal", 0.0) or 0.0),
                    usuarios_ativos_base=int(
                        getattr(pl, "usuarios_ativos_base", 0) or 0
                    ),
                    taxas_pagamento_pct=float(
                        getattr(pl, "taxas_pagamento_pct", 5.0) or 5.0
                    ),
                    impostos_pct=float(getattr(pl, "impostos_pct", 6.0) or 6.0),
                    custo_servidor_por_usuario=float(
                        getattr(pl, "custo_servidor_por_usuario", 0.0) or 0.0
                    ),
                )
            )

        db.flush()
        registrar_evento_auditoria(
            db,
            tenant_id=tenant.id,
            user_id=membership_dono.user_id,
            acao="ebt.migracao_legado",
            entidade_tipo="ClienteEBT",
            entidade_id=ebt.id,
            resumo=f"Startup legada '{ebt.nome_startup}' migrada automaticamente para o modelo SaaS.",
        )


def _garantir_membros_demonstracao_rbac(db: Session, *, tenant: Tenant) -> None:
    """
    Garante que o Tenant possua vínculos (Memberships) para cada papel RBAC
    (Consultor, Analista, Fundador e Investidor), facilitando a alternância
    e validação de permissões na interface.
    """
    primeira_ebt = (
        db.query(ClienteEBT)
        .filter(ClienteEBT.tenant_id == tenant.id)
        .order_by(ClienteEBT.criado_em.asc())
        .first()
    )
    ebt_id = primeira_ebt.id if primeira_ebt else None

    perfis = [
        (
            f"consultor@{tenant.slug}.com",
            "Consultor Sênior VC",
            PapelMembro.CONSULTOR,
            None,
        ),
        (
            f"analista@{tenant.slug}.com",
            "Analista Financeiro",
            PapelMembro.ANALISTA,
            None,
        ),
        (
            f"fundador@{tenant.slug}.com",
            "Fundador da EBT (Acesso Restrito)",
            PapelMembro.FUNDADOR,
            ebt_id,
        ),
        (
            f"investidor@{tenant.slug}.com",
            "Banca / Investidor (Somente Leitura)",
            PapelMembro.INVESTIDOR,
            ebt_id,
        ),
    ]

    hash_padrao = gerar_hash_senha(SENHA_SUPERADMIN_INICIAL)
    dono_user = db.query(User).filter(User.email == "dono@mastervc.com.br").first()
    if dono_user is not None:
        if not dono_user.senha_hash:
            dono_user.senha_hash = hash_padrao
        if not dono_user.provedor_auth_sub:
            dono_user.provedor_auth_sub = f"credentials:{dono_user.email}"
        if not dono_user.cargo_organizacao:
            dono_user.cargo_organizacao = "Diretor da Consultoria"

    for email, nome, papel, restrita_id in perfis:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(
                email=email,
                nome_completo=nome,
                senha_hash=hash_padrao,
                cargo_organizacao=nome,
                provedor_auth_sub=f"credentials:{email}",
                ativo=True,
            )
            db.add(user)
            db.flush()
        else:
            if not user.senha_hash:
                user.senha_hash = hash_padrao
            if not user.provedor_auth_sub:
                user.provedor_auth_sub = f"credentials:{email}"
            db.flush()

        vinculo = (
            db.query(Membership)
            .filter(
                Membership.tenant_id == tenant.id,
                Membership.user_id == user.id,
            )
            .first()
        )
        if vinculo is None:
            vinculo = Membership(
                tenant_id=tenant.id,
                user_id=user.id,
                papel=papel.value,
                ebt_restrita_id=restrita_id,
                ativo=True,
            )
            db.add(vinculo)
        elif papel in (PapelMembro.FUNDADOR, PapelMembro.INVESTIDOR) and not vinculo.ebt_restrita_id and ebt_id:
            vinculo.ebt_restrita_id = ebt_id

    db.flush()
