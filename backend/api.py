"""
Camada de API REST Versionada (/v1) — Master Management SaaS (Fase 4).
Expõe:
- Autenticação OAuth2 (Google, GitHub e Sandbox RBAC) + JWT (RFC 7519)
- Links de Convite OAuth vinculados aos 6 perfis RBAC (`dono`, `admin`, `consultor`, `analista`, `fundador`, `investidor`)
- CRUD Multi-Tenant de Workspaces EBT com Row-Level Security (RLS)
- Motor Financeiro (Simulação, Cenários, Monte Carlo e Free Tier)
- Comitê VC de IA Governada (Sanitização PII LGPD, Cache SHA-256 e Homologação)
- Emissão de Dossiês PDF Assinados e Painel de Governança SaaS
"""

from __future__ import annotations

import base64
import os
from typing import Any, Dict, Generator, List, Optional, Tuple

try:
    from fastapi import Depends, FastAPI, Header, HTTPException, Response
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:
    Depends = Any  # type: ignore
    FastAPI = Any  # type: ignore
    Header = Any  # type: ignore
    HTTPException = Exception  # type: ignore
    Response = Any  # type: ignore
    CORSMiddleware = Any  # type: ignore

from pydantic import BaseModel, Field

from core_financeiro import (
    VERSAO_MOTOR,
    EntradaSimulacaoSaaS,
    ResultadoComparacaoCenarios,
    ResultadoMonteCarlo,
    ResultadoSimulacaoSaaS,
    TipoCenario,
    executar_simulacao_saas,
    simular_cenarios_padrao,
    simular_monte_carlo,
)

from .auditoria import listar_trilha_auditoria, registrar_evento_auditoria
from .auth_oauth import (
    ErroAutenticacaoOAuth,
    atualizar_meu_perfil_usuario,
    autenticar_com_email_e_senha,
    autenticar_via_oauth_ou_convite,
    construir_resposta_sessao_autenticada,
    construir_url_autorizacao_oauth,
    criar_convite_rbac_oauth,
    criar_usuario_pelo_admin,
    decodificar_jwt_sessao_saas,
    excluir_usuario_pelo_admin,
    garantir_superadmin_inicial,
    gerenciar_assinante_oauth_pelo_admin,
    listar_provedores_oauth_configurados,
    listar_usuarios_oauth_registrados,
    obter_uso_usuario_pelo_admin,
    registrar_novo_usuario_credenciais,
    trocar_codigo_oauth_por_perfil,
)
from .bootstrap_local import inicializar_banco_saas
from .database import criar_engine_saas, gerar_ddl_rls_postgresql
from .filas_e_storage import (
    gerar_pdf_executivo_ebt_bytes,
    listar_jobs_tenant,
    registrar_emissao_dossie_pdf,
)
from .ia_governanca import (
    CASCATA_MODELOS_GEMINI,
    ErroIA,
    ProvedorAuditoriaDeterministicoIA,
    ProvedorGeminiIA,
    construir_prompt_vc_governado,
    obter_geracao_modelo,
    revisar_e_aprovar_parecer_ia,
    solicitar_parecer_ia_governado,
)
from .models import (
    AnaliseIAEBT,
    AssinaturaTenant,
    ClienteEBT,
    Convite,
    ItemCapexEBT,
    ItemOpexEBT,
    JuridicoEBT,
    LeanCanvasEBT,
    Membership,
    PapelMembro,
    PlanoAssinaturaCodigo,
    PlanoSaaSEBT,
    PremissasEBT,
    RelatorioDossieEBT,
    ResultadoSimulacaoEBT,
    Tenant,
    User,
    VersaoPremissasEBT,
)
from .rbac import ErroPermissaoRBAC, PermissaoSaaS, verificar_permissao_rbac
from .servicos import (
    ErroLimitePlanoSaaS,
    alterar_plano_assinatura_tenant,
    atualizar_premissas_ebt,
    criar_link_compartilhamento_investidor,
    criar_tenant_consultoria,
    criar_workspace_ebt,
    executar_e_versionar_simulacao_ebt,
    listar_workspaces_ebt_visiveis,
    obter_ou_criar_uso_mensal,
    validar_token_investidor,
)


# =============================================================================
# SCHEMAS DE CONTRATO REST (/v1)
# =============================================================================


class OnboardingTenantRequest(BaseModel):
    nome_consultoria: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=100)
    email_dono: str = Field(min_length=5, max_length=255)
    nome_dono: str = Field(min_length=2, max_length=200)
    plano: PlanoAssinaturaCodigo = Field(default=PlanoAssinaturaCodigo.STARTER)
    cnpj: Optional[str] = None


class OnboardingTenantResponse(BaseModel):
    tenant_id: str
    slug: str
    owner_user_id: str
    membership_id: str
    plano: str


class AlterarPlanoRequest(BaseModel):
    plano: PlanoAssinaturaCodigo


class CriarWorkspaceEBTRequest(BaseModel):
    nome_startup: str = Field(min_length=2, max_length=200)
    setor_vertical: str = Field(default="SaaS B2B")
    estagio: str = Field(default="Pre-Seed")


class WorkspaceEBTResponse(BaseModel):
    id: str
    tenant_id: str
    nome_startup: str
    setor_vertical: str
    estagio: str


class OAuthCallbackRequest(BaseModel):
    provedor: str = Field(default="google")
    code: Optional[str] = None
    redirect_uri: str = Field(default="http://localhost:3000/oauth/callback")
    invite_token: Optional[str] = None
    email_fallback: Optional[str] = None
    nome_fallback: Optional[str] = None


class SandboxRBACLoginRequest(BaseModel):
    papel: Optional[PapelMembro] = None
    provedor: str = Field(default="google")
    tenant_id: Optional[str] = None
    invite_token: Optional[str] = None
    email: Optional[str] = None
    nome: Optional[str] = None


class LoginCredenciaisRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    senha: str = Field(min_length=1, max_length=255)


class RegistrarUsuarioRequest(BaseModel):
    nome_completo: str = Field(min_length=2, max_length=200)
    email: str = Field(min_length=3, max_length=255)
    senha: str = Field(min_length=6, max_length=255)
    telefone_whatsapp: Optional[str] = ""
    cargo_organizacao: Optional[str] = ""


class AtualizarMeuPerfilRequest(BaseModel):
    nome_completo: Optional[str] = None
    email: Optional[str] = None
    telefone_whatsapp: Optional[str] = None
    cargo_organizacao: Optional[str] = None
    avatar_url: Optional[str] = None
    senha_atual: Optional[str] = None
    nova_senha: Optional[str] = None


class CriarUsuarioAdminRequest(BaseModel):
    nome_completo: str = Field(min_length=2, max_length=200)
    email: str = Field(min_length=3, max_length=255)
    senha: str = Field(min_length=6, max_length=255)
    papel: PapelMembro = Field(default=PapelMembro.ASSINANTE_FREE)
    plano: PlanoAssinaturaCodigo = Field(default=PlanoAssinaturaCodigo.FREE)
    cargo_organizacao: Optional[str] = ""
    telefone_whatsapp: Optional[str] = ""


class GerenciarAssinanteOAuthRequest(BaseModel):
    novo_papel: Optional[PapelMembro] = None
    novo_plano: Optional[PlanoAssinaturaCodigo] = None
    ebt_restrita_id: Optional[str] = None
    ativo: Optional[bool] = None
    nome_completo: Optional[str] = None
    email: Optional[str] = None
    cargo_organizacao: Optional[str] = None
    telefone_whatsapp: Optional[str] = None


class RenomearEBTRequest(BaseModel):
    nome_startup: str = Field(min_length=2, max_length=200)


class SwitchMembershipRequest(BaseModel):
    membership_id: Optional[str] = None
    tenant_id: Optional[str] = None
    papel: Optional[PapelMembro] = None


class CriarConviteRBACRequest(BaseModel):
    email_convidado: str = Field(min_length=3, max_length=255)
    papel: PapelMembro = Field(default=PapelMembro.CONSULTOR)
    ebt_restrita_id: Optional[str] = None
    dias_validade: int = Field(default=7, ge=1, le=90)


class LeanCanvasUpdateRequest(BaseModel):
    problema: str = ""
    solucao_mvp: str = ""
    mvp_descricao: str = ""
    metricas_chave: str = ""
    proposta_valor: str = ""
    vantagem_injusta: str = ""
    canais: str = ""
    segmentos: str = ""
    estrutura_custos: str = ""
    fontes_receita: str = ""
    ods_onu: str = ""


class PremissasUpdateRequest(BaseModel):
    horizonte_meses: int = Field(default=36, ge=6, le=120)
    tma_anual_pct: float = Field(default=25.0, ge=0.0, le=200.0)
    cac_estimado: float = Field(default=0.0, ge=0.0)
    churn_mensal_pct: float = Field(default=5.0, ge=0.0, le=100.0)
    conversao_freemium_pct: float = Field(default=2.0, ge=0.0, le=100.0)
    crescimento_mensal_pct: float = Field(default=5.0, ge=0.0, le=200.0)
    usuarios_freemium_base: int = Field(default=0, ge=0)


class ItemCapexCreateRequest(BaseModel):
    categoria: str = Field(min_length=1, max_length=100)
    descricao: str = Field(min_length=1, max_length=300)
    valor: float = Field(ge=0.0)


class ItemOpexCreateRequest(BaseModel):
    categoria: str = Field(min_length=1, max_length=100)
    descricao: str = Field(min_length=1, max_length=300)
    valor_mensal: float = Field(ge=0.0)


class PlanoSaaSCreateRequest(BaseModel):
    nome_plano: str = Field(min_length=1, max_length=120)
    ticket_mensal: float = Field(ge=0.0)
    usuarios_ativos_base: int = Field(ge=0)
    taxas_pagamento_pct: float = Field(default=5.0, ge=0.0, le=100.0)
    impostos_pct: float = Field(default=6.0, ge=0.0, le=100.0)
    custo_servidor_por_usuario: float = Field(default=0.0, ge=0.0)


class JuridicoUpdateRequest(BaseModel):
    registro_inpi: str = "Não Iniciado"
    marca_status: str = "Não Iniciado"
    adequacao_lgpd: bool = False
    contrato_vesting: bool = False
    custo_estimado_legal: float = Field(default=0.0, ge=0.0)


class SolicitarParecerIARequest(BaseModel):
    usar_gemini: bool = False
    gemini_api_key: Optional[str] = None
    modelo_gemini: Optional[str] = "gemini-3.8"
    forcar_regeneracao: bool = False
    permitir_fallback_copiloto: bool = False


class AnaliseIAResponse(BaseModel):
    id: str
    tenant_id: str
    ebt_id: str
    provedor: str
    modelo: str
    modelo_resolvido: Optional[str] = None
    tentativas_executadas: int = 1
    geracao_resolvida: Optional[str] = None
    versao_prompt: str
    hash_entrada_simulacao: str
    parecer_gerado_md: str
    parecer_revisado_consultor_md: Optional[str] = None
    aprovado_pelo_consultor: bool
    custo_estimado_usd: float
    em_cache: bool = False
    fallback_acionado: bool = False


class AprovarParecerIARequest(BaseModel):
    texto_revisado_md: Optional[str] = None


class EmitirDossiePDFRequest(BaseModel):
    exigir_parecer_aprovado: bool = False
    parecer_customizado_md: Optional[str] = None


class RelatorioDossieResponse(BaseModel):
    id: str
    tenant_id: str
    ebt_id: str
    resultado_simulacao_id: str
    storage_key: str
    sha256_pdf: str
    url_assinada: str
    pdf_base64: Optional[str] = None


class JobAssincronoResponse(BaseModel):
    id: str
    tenant_id: str
    ebt_id: Optional[str] = None
    tipo_job: str
    status: str
    progresso_pct: int
    referencia_resultado_id: Optional[str] = None


class ShareLinkCreateRequest(BaseModel):
    dias_validade: int = Field(default=7, ge=1, le=90)


class ShareLinkValidateRequest(BaseModel):
    token: str


class HealthcheckResponse(BaseModel):
    status: str = "ok"
    servico: str = "master-management-saas"
    versao_api: str = "v1"
    versao_motor_financeiro: str = VERSAO_MOTOR


# =============================================================================
# FÁBRICA FASTAPI (/v1)
# =============================================================================


def criar_app_fastapi(database_url: Optional[str] = None) -> Any:
    """
    Cria e retorna a aplicação FastAPI configurada com rotas `/v1`,
    CORS, autenticação OAuth2/JWT e sessão SQLAlchemy isolada por Tenant (RLS).
    """
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException, Response
        from fastapi.middleware.cors import CORSMiddleware
    except ImportError as exc:
        raise RuntimeError(
            "O pacote 'fastapi' não está instalado no ambiente atual. "
            "Instale `fastapi` e `uvicorn` para subir o servidor HTTP."
        ) from exc

    url_banco = database_url or os.getenv(
        "DATABASE_URL", "sqlite:///plano_negocios_vc_v5.db"
    )
    engine = criar_engine_saas(url_banco)
    session_factory = inicializar_banco_saas(engine, classe_projeto_legado=None)

    app = FastAPI(
        title="Master Management SaaS API",
        version="2.0.0",
        description=(
            "API Multi-Tenant de Viabilidade Estratégica, Financeira e Venture Capital "
            "com OAuth2, 6 Perfis RBAC e Isolamento Row-Level Security."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def obter_db() -> Generator[Any, None, None]:
        db = session_factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def obter_contexto_autenticado(
        authorization: Optional[str] = Header(default=None),
        db: Any = Depends(obter_db),
    ) -> Tuple[User, Membership, Dict[str, Any]]:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(
                status_code=401,
                detail="Cabeçalho Authorization: Bearer <token> obrigatório.",
            )
        token_jwt = authorization.split(" ", 1)[1].strip()
        try:
            claims = decodificar_jwt_sessao_saas(token_jwt)
        except ErroAutenticacaoOAuth as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        db.info["bypass_rls"] = True
        user = db.get(User, claims["sub"])
        membership = db.get(Membership, claims["membership_id"])
        if user is None or membership is None or not membership.ativo:
            raise HTTPException(
                status_code=401,
                detail="Sessão ou vínculo RBAC inválido/inativo.",
            )

        # Ativa o isolamento RLS para todas as queries subsequentes da requisição
        db.info["bypass_rls"] = False
        db.info["tenant_id"] = membership.tenant_id
        db.info["user_id"] = user.id
        return user, membership, claims

    def _mapear_excecao_negocio(exc: Exception) -> HTTPException:
        if isinstance(exc, ErroIA):
            return HTTPException(
                status_code=exc.status_http,
                detail={
                    "codigo_erro": exc.codigo_erro,
                    "mensagem_amigavel": exc.mensagem_amigavel,
                    "detalhe_tecnico": exc.detalhe_tecnico,
                    "suporta_offline": True,
                },
            )
        if isinstance(exc, (ErroPermissaoRBAC, PermissionError)):
            return HTTPException(status_code=403, detail=str(exc))
        if isinstance(exc, ErroLimitePlanoSaaS):
            return HTTPException(status_code=402, detail=str(exc))
        if isinstance(exc, LookupError):
            return HTTPException(status_code=404, detail=str(exc))
        return HTTPException(status_code=400, detail=str(exc))

    # ── 1. Operação & Motor Puro ──────────────────────────────────────────────

    @app.get("/health", response_model=HealthcheckResponse, include_in_schema=False)
    @app.get("/v1/health", response_model=HealthcheckResponse, tags=["Operação"])
    def healthcheck() -> HealthcheckResponse:
        return HealthcheckResponse()

    @app.post(
        "/v1/financeiro/simular",
        response_model=ResultadoSimulacaoSaaS,
        tags=["Motor Financeiro"],
    )
    def endpoint_simular(
        entrada: EntradaSimulacaoSaaS,
        cenario: TipoCenario = TipoCenario.BASE,
    ) -> ResultadoSimulacaoSaaS:
        return executar_simulacao_saas(entrada, cenario=cenario)

    @app.post(
        "/v1/financeiro/cenarios",
        response_model=ResultadoComparacaoCenarios,
        tags=["Motor Financeiro"],
    )
    def endpoint_cenarios(
        entrada: EntradaSimulacaoSaaS,
    ) -> ResultadoComparacaoCenarios:
        return simular_cenarios_padrao(entrada)

    @app.post(
        "/v1/financeiro/monte-carlo",
        response_model=ResultadoMonteCarlo,
        tags=["Motor Financeiro"],
    )
    def endpoint_monte_carlo(
        entrada: EntradaSimulacaoSaaS,
        iteracoes: int = 300,
        semente: int = 42,
    ) -> ResultadoMonteCarlo:
        return simular_monte_carlo(entrada, iteracoes=iteracoes, semente=semente)

    # ── 2. OAuth2, JWT e Vínculo com Perfis RBAC ──────────────────────────────

    @app.get("/v1/auth/providers", tags=["Autenticação OAuth2 & RBAC"])
    def endpoint_listar_provedores(
        redirect_base_url: str = "http://localhost:3000",
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        db.info["bypass_rls"] = True
        tenants = db.query(Tenant).order_by(Tenant.criado_em.asc()).all()
        usuarios_oauth = listar_usuarios_oauth_registrados(db)
        existe_admin_oauth = any(
            u["papel"] in (PapelMembro.ADMIN.value, PapelMembro.DONO.value)
            for u in usuarios_oauth
        )
        return {
            "provedores": listar_provedores_oauth_configurados(redirect_base_url),
            "papeis_rbac": [p.value for p in PapelMembro],
            "existe_admin_oauth": existe_admin_oauth,
            "usuarios_oauth_registrados": usuarios_oauth,
            "tenants_disponiveis": [
                {"id": t.id, "nome": t.nome, "slug": t.slug} for t in tenants
            ],
        }

    @app.get("/v1/auth/oauth/authorize", tags=["Autenticação OAuth2 & RBAC"])
    def endpoint_url_autorizacao_oauth(
        provedor: str = "google",
        redirect_uri: str = "http://localhost:3000/oauth/callback",
        invite_token: Optional[str] = None,
    ) -> Dict[str, str]:
        url = construir_url_autorizacao_oauth(
            provedor, redirect_uri=redirect_uri, invite_token=invite_token
        )
        return {"authorize_url": url}

    @app.post("/v1/auth/oauth/callback", tags=["Autenticação OAuth2 & RBAC"])
    def endpoint_oauth_callback(
        req: OAuthCallbackRequest,
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        try:
            if req.code and req.provedor in ("google", "github"):
                perfil = trocar_codigo_oauth_por_perfil(
                    req.provedor, code=req.code, redirect_uri=req.redirect_uri
                )
            else:
                email = req.email_fallback or "oauth.user@mastermanagement.com.br"
                nome = req.nome_fallback or "Usuário OAuth"
                perfil = {
                    "email": email,
                    "nome": nome,
                    "sub": f"oauth-{email}",
                    "provedor": req.provedor,
                }

            return autenticar_via_oauth_ou_convite(
                db,
                email=perfil["email"],
                nome=perfil["nome"],
                provedor=perfil["provedor"],
                sub_externo=perfil["sub"],
                invite_token=req.invite_token,
            )
        except Exception as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @app.post("/v1/auth/login", tags=["Autenticação & RBAC"])
    def endpoint_login_credenciais(
        req: LoginCredenciaisRequest,
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        """
        Autenticação tradicional protegida por E-mail e Senha (PBKDF2-HMAC-SHA256).
        Garante o seed do SuperAdmin inicial (`marcolinoee@yahoo.com.br` / `123456`).
        """
        try:
            return autenticar_com_email_e_senha(
                db,
                email=req.email,
                senha=req.senha,
            )
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.post("/v1/auth/register", status_code=201, tags=["Autenticação & RBAC"])
    def endpoint_registrar_usuario(
        req: RegistrarUsuarioRequest,
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        """
        Cadastra um novo usuário com e-mail e senha (hash PBKDF2-HMAC-SHA256)
        como ASSINANTE_FREE no plano Free Tier.
        """
        try:
            return registrar_novo_usuario_credenciais(
                db,
                nome_completo=req.nome_completo,
                email=req.email,
                senha=req.senha,
                telefone_whatsapp=req.telefone_whatsapp or "",
                cargo_organizacao=req.cargo_organizacao or "",
            )
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.put("/v1/auth/profile", tags=["Autenticação & RBAC"])
    def endpoint_atualizar_meu_perfil(
        req: AtualizarMeuPerfilRequest,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        """
        Atualiza os dados da aba 'Meu Perfil' (Nome Completo, E-mail, Telefone/WhatsApp,
        Cargo/Organização, Foto de Perfil/Avatar e Alteração de Senha).
        """
        user, membership, _ = ctx
        try:
            return atualizar_meu_perfil_usuario(
                db,
                user=user,
                membership_ativa=membership,
                nome_completo=req.nome_completo,
                email=req.email,
                telefone_whatsapp=req.telefone_whatsapp,
                cargo_organizacao=req.cargo_organizacao,
                avatar_url=req.avatar_url,
                senha_atual=req.senha_atual,
                nova_senha=req.nova_senha,
            )
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.post("/v1/auth/sandbox-rbac", tags=["Autenticação OAuth2 & RBAC"])
    def endpoint_login_sandbox_rbac(
        req: SandboxRBACLoginRequest,
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        """
        Realiza autenticação OAuth2 registrando o usuário no banco (`User.provedor_auth_sub`):
        - O 1º usuário autenticado via OAuth no banco recebe automaticamente o perfil `admin`.
        - Os demais usuários autenticados via OAuth são categorizados como assinantes `FREE TIER`,
          ficando o upgrade e a atribuição de outros papéis RBAC sob responsabilidade do `admin`.
        """
        try:
            if not req.email or not req.email.strip():
                raise ValueError("O e-mail da conta OAuth é obrigatório para autenticação.")
            email_limpo = req.email.strip().lower()
            nome_padrao = (
                req.nome.strip()
                if (req.nome and req.nome.strip())
                else email_limpo.split("@")[0].replace(".", " ").title()
            )
            provedor_oauth = req.provedor or "google"
            return autenticar_via_oauth_ou_convite(
                db,
                email=email_limpo,
                nome=nome_padrao,
                provedor=provedor_oauth,
                sub_externo=f"oauth-{provedor_oauth}-{email_limpo}",
                invite_token=req.invite_token,
                tenant_id_preferencial=req.tenant_id,
                papel_sandbox=None,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/auth/me", tags=["Autenticação OAuth2 & RBAC"])
    def endpoint_auth_me(
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        user, membership, claims = ctx
        return construir_resposta_sessao_autenticada(
            db,
            user=user,
            membership_ativa=membership,
            provedor_oauth=str(claims.get("provider", "oauth-local")),
        )

    @app.post("/v1/auth/switch-membership", tags=["Autenticação OAuth2 & RBAC"])
    def endpoint_switch_membership(
        req: SwitchMembershipRequest,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        _, membership_atual, claims = ctx
        db.info["bypass_rls"] = True

        nova_membership: Optional[Membership] = None
        if req.membership_id:
            nova_membership = db.get(Membership, req.membership_id)
        elif req.tenant_id or req.papel:
            tid_alvo = req.tenant_id or membership_atual.tenant_id
            papel_alvo = (
                req.papel.value if req.papel else membership_atual.papel
            )
            nova_membership = (
                db.query(Membership)
                .filter(
                    Membership.tenant_id == tid_alvo,
                    Membership.papel == papel_alvo,
                    Membership.ativo.is_(True),
                )
                .first()
            )
            if nova_membership is None:
                nova_membership = (
                    db.query(Membership)
                    .filter(
                        Membership.tenant_id == tid_alvo,
                        Membership.ativo.is_(True),
                    )
                    .first()
                )

        if nova_membership is None:
            raise HTTPException(status_code=404, detail="Perfil RBAC não encontrado.")

        novo_user = db.get(User, nova_membership.user_id)
        if novo_user is None:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        if not novo_user.provedor_auth_sub:
            raise HTTPException(
                status_code=403,
                detail="Operação bloqueada: o perfil RBAC exige autenticação OAuth prévia registrada no banco de dados.",
            )

        eh_admin = membership_atual.papel in (
            PapelMembro.ADMIN.value,
            PapelMembro.DONO.value,
        )
        if not eh_admin and nova_membership.user_id != membership_atual.user_id:
            raise HTTPException(
                status_code=403,
                detail="Apenas o Administrador pode alternar para perfis OAuth de terceiros.",
            )

        return construir_resposta_sessao_autenticada(
            db,
            user=novo_user,
            membership_ativa=nova_membership,
            provedor_oauth=str(claims.get("provider", "oauth-local")),
        )

    @app.get("/v1/admin/assinantes-oauth", tags=["Autenticação OAuth2 & RBAC"])
    @app.get("/v1/admin/usuarios", tags=["Autenticação & RBAC"])
    def endpoint_listar_assinantes_oauth(
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> List[Dict[str, Any]]:
        _, membership, _ = ctx
        if membership.papel not in (PapelMembro.ADMIN.value, PapelMembro.DONO.value):
            raise HTTPException(
                status_code=403,
                detail="Apenas o Administrador (ADMIN) pode listar e gerenciar usuários no Painel RBAC.",
            )
        garantir_superadmin_inicial(db)
        return listar_usuarios_oauth_registrados(db, incluir_todos=True)

    @app.post("/v1/admin/usuarios", status_code=201, tags=["Autenticação & RBAC"])
    def endpoint_criar_usuario_admin(
        req: CriarUsuarioAdminRequest,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        _, membership_admin, _ = ctx
        try:
            return criar_usuario_pelo_admin(
                db,
                membership_admin=membership_admin,
                nome_completo=req.nome_completo,
                email=req.email,
                senha=req.senha,
                papel=req.papel,
                plano=req.plano,
                cargo_organizacao=req.cargo_organizacao or "",
                telefone_whatsapp=req.telefone_whatsapp or "",
            )
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.put(
        "/v1/admin/assinantes-oauth/{membership_id}",
        tags=["Autenticação OAuth2 & RBAC"],
    )
    @app.put(
        "/v1/admin/usuarios/{membership_id}",
        tags=["Autenticação & RBAC"],
    )
    def endpoint_gerenciar_assinante_oauth(
        membership_id: str,
        req: GerenciarAssinanteOAuthRequest,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        _, membership_admin, _ = ctx
        try:
            return gerenciar_assinante_oauth_pelo_admin(
                db,
                membership_admin=membership_admin,
                membership_alvo_id=membership_id,
                novo_papel=req.novo_papel,
                novo_plano=req.novo_plano,
                ebt_restrita_id=req.ebt_restrita_id,
                ativo=req.ativo,
                nome_completo=req.nome_completo,
                email=req.email,
                cargo_organizacao=req.cargo_organizacao,
                telefone_whatsapp=req.telefone_whatsapp,
            )
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.delete(
        "/v1/admin/usuarios/{membership_id}",
        tags=["Autenticação & RBAC"],
    )
    def endpoint_excluir_usuario_admin(
        membership_id: str,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        _, membership_admin, _ = ctx
        try:
            return excluir_usuario_pelo_admin(
                db,
                membership_admin=membership_admin,
                membership_alvo_id=membership_id,
            )
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.get(
        "/v1/admin/usuarios/{membership_id}/uso",
        tags=["Autenticação & RBAC"],
    )
    def endpoint_obter_uso_usuario_admin(
        membership_id: str,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        _, membership_admin, _ = ctx
        try:
            return obter_uso_usuario_pelo_admin(
                db,
                membership_admin=membership_admin,
                membership_alvo_id=membership_id,
            )
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.post("/v1/auth/convites-rbac", tags=["Autenticação OAuth2 & RBAC"])
    def endpoint_criar_convite_rbac(
        req: CriarConviteRBACRequest,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        _, membership, _ = ctx
        try:
            token_claro, convite = criar_convite_rbac_oauth(
                db,
                membership_emissor=membership,
                email_convidado=req.email_convidado,
                papel=req.papel,
                ebt_restrita_id=req.ebt_restrita_id,
                dias_validade=req.dias_validade,
            )
            return {
                "convite_id": convite.id,
                "email_convidado": convite.email_convidado,
                "papel": convite.papel,
                "ebt_restrita_id": convite.ebt_restrita_id,
                "invite_token": token_claro,
                "oauth_invite_url": f"/?invite_token={token_claro}&papel={convite.papel}",
                "expira_em": convite.expira_em.isoformat(),
            }
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    # ── 3. Tenants e Planos de Assinatura (Free / Starter / Pro / Enterprise) ─

    @app.get("/v1/tenants", tags=["Tenants & Planos"])
    def endpoint_listar_tenants(
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> List[Dict[str, Any]]:
        db.info["bypass_rls"] = True
        tenants = db.query(Tenant).order_by(Tenant.criado_em.asc()).all()
        resultado = []
        for t in tenants:
            ass = (
                db.query(AssinaturaTenant)
                .filter(AssinaturaTenant.tenant_id == t.id)
                .first()
            )
            resultado.append(
                {
                    "id": t.id,
                    "nome": t.nome,
                    "slug": t.slug,
                    "plano_codigo": ass.plano_codigo if ass else "starter",
                }
            )
        return resultado

    @app.post(
        "/v1/tenants",
        response_model=OnboardingTenantResponse,
        tags=["Tenants & Planos"],
    )
    def endpoint_criar_tenant(
        req: OnboardingTenantRequest,
        db: Any = Depends(obter_db),
    ) -> OnboardingTenantResponse:
        try:
            db.info["bypass_rls"] = True
            tenant, user, memb = criar_tenant_consultoria(
                db,
                nome_consultoria=req.nome_consultoria,
                slug=req.slug,
                email_dono=req.email_dono,
                nome_dono=req.nome_dono,
                plano=req.plano,
                cnpj=req.cnpj,
            )
            criar_workspace_ebt(
                db,
                membership=memb,
                nome_startup=f"Primeira EBT - {tenant.nome}",
            )
            return OnboardingTenantResponse(
                tenant_id=tenant.id,
                slug=tenant.slug,
                owner_user_id=user.id,
                membership_id=memb.id,
                plano=req.plano.value,
            )
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.patch("/v1/tenants/plano", tags=["Tenants & Planos"])
    def endpoint_alterar_plano(
        req: AlterarPlanoRequest,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        _, membership, _ = ctx
        try:
            ass = alterar_plano_assinatura_tenant(
                db, membership=membership, novo_plano=req.plano
            )
            return {
                "plano_codigo": ass.plano_codigo,
                "limite_ebts": ass.limite_ebts,
                "limite_analises_ia_mes": ass.limite_analises_ia_mes,
                "limite_pdfs_mes": ass.limite_pdfs_mes,
                "permite_monte_carlo": ass.permite_monte_carlo,
                "permite_white_label": ass.permite_white_label,
            }
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    # ── 4. Workspaces EBT e Diagnóstico Completo ──────────────────────────────

    @app.get(
        "/v1/ebts",
        response_model=List[WorkspaceEBTResponse],
        tags=["Workspaces EBT"],
    )
    def endpoint_listar_ebts(
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> List[WorkspaceEBTResponse]:
        _, membership, _ = ctx
        try:
            ebts = listar_workspaces_ebt_visiveis(db, membership=membership)
            return [
                WorkspaceEBTResponse(
                    id=e.id,
                    tenant_id=e.tenant_id,
                    nome_startup=e.nome_startup,
                    setor_vertical=e.setor_vertical,
                    estagio=e.estagio,
                )
                for e in ebts
            ]
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.post(
        "/v1/ebts",
        response_model=WorkspaceEBTResponse,
        tags=["Workspaces EBT"],
    )
    def endpoint_criar_ebt(
        req: CriarWorkspaceEBTRequest,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> WorkspaceEBTResponse:
        _, membership, _ = ctx
        try:
            ebt = criar_workspace_ebt(
                db,
                membership=membership,
                nome_startup=req.nome_startup,
                setor_vertical=req.setor_vertical,
                estagio=req.estagio,
            )
            return WorkspaceEBTResponse(
                id=ebt.id,
                tenant_id=ebt.tenant_id,
                nome_startup=ebt.nome_startup,
                setor_vertical=ebt.setor_vertical,
                estagio=ebt.estagio,
            )
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.patch("/v1/ebts/{ebt_id}", tags=["Workspaces EBT"])
    def endpoint_renomear_ebt(
        ebt_id: str,
        req: RenomearEBTRequest,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> WorkspaceEBTResponse:
        _, membership, _ = ctx
        try:
            verificar_permissao_rbac(
                membership, PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO, ebt_alvo_id=ebt_id
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
                raise LookupError("EBT não encontrada.")
            nome_antigo = ebt.nome_startup
            ebt.nome_startup = req.nome_startup.strip()
            db.flush()
            registrar_evento_auditoria(
                db,
                tenant_id=membership.tenant_id,
                user_id=membership.user_id,
                acao="ebt.renomear",
                entidade_tipo="ClienteEBT",
                entidade_id=ebt.id,
                resumo=f"EBT renomeada de '{nome_antigo}' para '{ebt.nome_startup}'.",
                dados_anteriores={"nome_startup": nome_antigo},
                dados_novos={"nome_startup": ebt.nome_startup},
            )
            return WorkspaceEBTResponse(
                id=ebt.id,
                tenant_id=ebt.tenant_id,
                nome_startup=ebt.nome_startup,
                setor_vertical=ebt.setor_vertical,
                estagio=ebt.estagio,
            )
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.delete("/v1/ebts/{ebt_id}", tags=["Workspaces EBT"])
    def endpoint_excluir_ebt(
        ebt_id: str,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, str]:
        _, membership, _ = ctx
        try:
            verificar_permissao_rbac(
                membership, PermissaoSaaS.EBT_EXCLUIR, ebt_alvo_id=ebt_id
            )
            todas_visiveis = listar_workspaces_ebt_visiveis(db, membership=membership)
            if len(todas_visiveis) <= 1:
                raise ValueError(
                    "Erro Crítico: Não é possível excluir a última startup visível."
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
                raise LookupError("EBT não encontrada.")
            registrar_evento_auditoria(
                db,
                tenant_id=membership.tenant_id,
                user_id=membership.user_id,
                acao="ebt.excluir",
                entidade_tipo="ClienteEBT",
                entidade_id=ebt.id,
                resumo=f"Workspace EBT '{ebt.nome_startup}' excluído.",
            )
            db.delete(ebt)
            db.flush()
            return {"status": "ok"}
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.get("/v1/ebts/{ebt_id}/completo", tags=["Workspaces EBT"])
    def endpoint_obter_ebt_completo(
        ebt_id: str,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        _, membership, _ = ctx
        try:
            verificar_permissao_rbac(
                membership, PermissaoSaaS.EBT_VISUALIZAR, ebt_alvo_id=ebt_id
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
                raise LookupError(f"EBT '{ebt_id}' não encontrada.")

            entrada_sim = EntradaSimulacaoSaaS.from_orm_projeto(ebt)
            simulacao_base = executar_simulacao_saas(
                entrada_sim, cenario=TipoCenario.BASE
            )
            comparativo_cenarios = simular_cenarios_padrao(entrada_sim)
            prompt_anon, hash_contexto = construir_prompt_vc_governado(
                ebt, simulacao_base
            )

            ultima_ia = (
                db.query(AnaliseIAEBT)
                .filter(
                    AnaliseIAEBT.tenant_id == membership.tenant_id,
                    AnaliseIAEBT.ebt_id == ebt.id,
                )
                .order_by(AnaliseIAEBT.criado_em.desc())
                .first()
            )

            versoes_db = (
                db.query(VersaoPremissasEBT)
                .filter(
                    VersaoPremissasEBT.tenant_id == membership.tenant_id,
                    VersaoPremissasEBT.ebt_id == ebt.id,
                )
                .order_by(VersaoPremissasEBT.numero_versao.desc())
                .all()
            )
            historico_versoes = []
            for v in versoes_db:
                r_sim = (
                    db.query(ResultadoSimulacaoEBT)
                    .filter(ResultadoSimulacaoEBT.versao_premissas_id == v.id)
                    .first()
                )
                historico_versoes.append(
                    {
                        "id": v.id,
                        "numero_versao": v.numero_versao,
                        "hash_entrada_sha256": v.hash_entrada_sha256,
                        "versao_motor": r_sim.versao_motor if r_sim else VERSAO_MOTOR,
                        "mrr_bruto_base": r_sim.mrr_bruto_base if r_sim else 0.0,
                        "vpl": r_sim.vpl if r_sim else 0.0,
                        "ltv_cac": r_sim.ltv_cac if r_sim else 0.0,
                        "criado_em": v.criado_em.isoformat() if v.criado_em else None,
                    }
                )

            lc = ebt.lean_canvas
            prem = ebt.premissas
            jur = ebt.juridico

            return {
                "ebt": {
                    "id": ebt.id,
                    "tenant_id": ebt.tenant_id,
                    "nome_startup": ebt.nome_startup,
                    "setor_vertical": ebt.setor_vertical,
                    "estagio": ebt.estagio,
                },
                "lean_canvas": {
                    "problema": lc.problema if lc else "",
                    "solucao_mvp": lc.solucao_mvp if lc else "",
                    "mvp_descricao": lc.mvp_descricao if lc else "",
                    "metricas_chave": lc.metricas_chave if lc else "",
                    "proposta_valor": lc.proposta_valor if lc else "",
                    "vantagem_injusta": lc.vantagem_injusta if lc else "",
                    "canais": lc.canais if lc else "",
                    "segmentos": lc.segmentos if lc else "",
                    "estrutura_custos": lc.estrutura_custos if lc else "",
                    "fontes_receita": lc.fontes_receita if lc else "",
                    "ods_onu": lc.ods_onu if lc else "",
                },
                "premissas": {
                    "horizonte_meses": prem.horizonte_meses if prem else 36,
                    "tma_anual_pct": prem.tma_anual_pct if prem else 25.0,
                    "cac_estimado": prem.cac_estimado if prem else 0.0,
                    "churn_mensal_pct": prem.churn_mensal_pct if prem else 5.0,
                    "conversao_freemium_pct": (
                        prem.conversao_freemium_pct if prem else 2.0
                    ),
                    "crescimento_mensal_pct": (
                        prem.crescimento_mensal_pct if prem else 5.0
                    ),
                    "usuarios_freemium_base": (
                        prem.usuarios_freemium_base if prem else 0
                    ),
                },
                "investimentos": [
                    {
                        "id": i.id,
                        "categoria": i.categoria,
                        "descricao": i.descricao,
                        "valor": i.valor,
                    }
                    for i in ebt.investimentos
                ],
                "custos_fixos": [
                    {
                        "id": c.id,
                        "categoria": c.categoria,
                        "descricao": c.descricao,
                        "valor_mensal": c.valor_mensal,
                    }
                    for c in ebt.custos_fixos
                ],
                "planos_saas": [
                    {
                        "id": p.id,
                        "nome_plano": p.nome_plano,
                        "ticket_mensal": p.ticket_mensal,
                        "usuarios_ativos_base": p.usuarios_ativos_base,
                        "taxas_pagamento_pct": p.taxas_pagamento_pct,
                        "impostos_pct": p.impostos_pct,
                        "custo_servidor_por_usuario": p.custo_servidor_por_usuario,
                    }
                    for p in ebt.planos_saas
                ],
                "juridico": {
                    "registro_inpi": jur.registro_inpi if jur else "Não Iniciado",
                    "marca_status": jur.marca_status if jur else "Não Iniciado",
                    "adequacao_lgpd": bool(jur.adequacao_lgpd if jur else False),
                    "contrato_vesting": bool(jur.contrato_vesting if jur else False),
                    "custo_estimado_legal": (
                        jur.custo_estimado_legal if jur else 0.0
                    ),
                },
                "simulacao_base": simulacao_base.model_dump(),
                "comparativo_cenarios": comparativo_cenarios.model_dump(),
                "versoes_simulacao": historico_versoes,
                "ia_governanca": {
                    "prompt_anonimizado_preview": prompt_anon,
                    "hash_contexto_atual": hash_contexto,
                    "ultima_analise": (
                        {
                            "id": ultima_ia.id,
                            "provedor": ultima_ia.provedor,
                            "modelo": ultima_ia.modelo,
                            "modelo_resolvido": ultima_ia.modelo,
                            "geracao_resolvida": obter_geracao_modelo(ultima_ia.modelo),
                            "versao_prompt": ultima_ia.versao_prompt,
                            "hash_entrada_simulacao": ultima_ia.hash_entrada_simulacao,
                            "parecer_gerado_md": ultima_ia.parecer_gerado_md,
                            "parecer_revisado_consultor_md": (
                                ultima_ia.parecer_revisado_consultor_md
                            ),
                            "aprovado_pelo_consultor": (
                                ultima_ia.aprovado_pelo_consultor
                            ),
                            "custo_estimado_usd": ultima_ia.custo_estimado_usd,
                        }
                        if ultima_ia
                        else None
                    ),
                },
            }
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.put("/v1/ebts/{ebt_id}/lean-canvas", tags=["Workspaces EBT"])
    def endpoint_atualizar_lean_canvas(
        ebt_id: str,
        req: LeanCanvasUpdateRequest,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, str]:
        _, membership, _ = ctx
        try:
            verificar_permissao_rbac(
                membership, PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO, ebt_alvo_id=ebt_id
            )
            lc = (
                db.query(LeanCanvasEBT)
                .filter(
                    LeanCanvasEBT.tenant_id == membership.tenant_id,
                    LeanCanvasEBT.ebt_id == ebt_id,
                )
                .first()
            )
            if lc is None:
                raise LookupError("Lean Canvas não encontrado.")
            for campo, valor in req.model_dump().items():
                setattr(lc, campo, valor)
            db.flush()
            registrar_evento_auditoria(
                db,
                tenant_id=membership.tenant_id,
                user_id=membership.user_id,
                acao="lean_canvas.atualizar",
                entidade_tipo="LeanCanvasEBT",
                entidade_id=lc.id,
                resumo=f"Lean Canvas da EBT '{ebt_id[:8]}' atualizado via API.",
            )
            return {"status": "ok"}
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.put("/v1/ebts/{ebt_id}/premissas", tags=["Workspaces EBT"])
    def endpoint_atualizar_premissas(
        ebt_id: str,
        req: PremissasUpdateRequest,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, str]:
        _, membership, _ = ctx
        try:
            atualizar_premissas_ebt(
                db,
                membership=membership,
                ebt_id=ebt_id,
                **req.model_dump(),
            )
            return {"status": "ok"}
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.post("/v1/ebts/{ebt_id}/capex", tags=["Workspaces EBT"])
    def endpoint_adicionar_capex(
        ebt_id: str,
        req: ItemCapexCreateRequest,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        _, membership, _ = ctx
        try:
            verificar_permissao_rbac(
                membership, PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO, ebt_alvo_id=ebt_id
            )
            item = ItemCapexEBT(
                tenant_id=membership.tenant_id,
                ebt_id=ebt_id,
                categoria=req.categoria,
                descricao=req.descricao,
                valor=req.valor,
            )
            db.add(item)
            db.flush()
            registrar_evento_auditoria(
                db,
                tenant_id=membership.tenant_id,
                user_id=membership.user_id,
                acao="capex.adicionar",
                entidade_tipo="ItemCapexEBT",
                entidade_id=item.id,
                resumo=f"Item Capex '{req.descricao}' (R$ {req.valor:,.2f}) adicionado.",
            )
            return {"id": item.id, "status": "ok"}
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.delete("/v1/ebts/{ebt_id}/capex/{item_id}", tags=["Workspaces EBT"])
    def endpoint_excluir_capex(
        ebt_id: str,
        item_id: str,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, str]:
        _, membership, _ = ctx
        try:
            verificar_permissao_rbac(
                membership, PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO, ebt_alvo_id=ebt_id
            )
            item = (
                db.query(ItemCapexEBT)
                .filter(
                    ItemCapexEBT.tenant_id == membership.tenant_id,
                    ItemCapexEBT.ebt_id == ebt_id,
                    ItemCapexEBT.id == item_id,
                )
                .first()
            )
            if item is None:
                raise LookupError("Item Capex não encontrado.")
            db.delete(item)
            db.flush()
            return {"status": "ok"}
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.post("/v1/ebts/{ebt_id}/opex", tags=["Workspaces EBT"])
    def endpoint_adicionar_opex(
        ebt_id: str,
        req: ItemOpexCreateRequest,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        _, membership, _ = ctx
        try:
            verificar_permissao_rbac(
                membership, PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO, ebt_alvo_id=ebt_id
            )
            item = ItemOpexEBT(
                tenant_id=membership.tenant_id,
                ebt_id=ebt_id,
                categoria=req.categoria,
                descricao=req.descricao,
                valor_mensal=req.valor_mensal,
            )
            db.add(item)
            db.flush()
            registrar_evento_auditoria(
                db,
                tenant_id=membership.tenant_id,
                user_id=membership.user_id,
                acao="opex.adicionar",
                entidade_tipo="ItemOpexEBT",
                entidade_id=item.id,
                resumo=f"Item Opex '{req.descricao}' (R$ {req.valor_mensal:,.2f}/mês) adicionado.",
            )
            return {"id": item.id, "status": "ok"}
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.delete("/v1/ebts/{ebt_id}/opex/{item_id}", tags=["Workspaces EBT"])
    def endpoint_excluir_opex(
        ebt_id: str,
        item_id: str,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, str]:
        _, membership, _ = ctx
        try:
            verificar_permissao_rbac(
                membership, PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO, ebt_alvo_id=ebt_id
            )
            item = (
                db.query(ItemOpexEBT)
                .filter(
                    ItemOpexEBT.tenant_id == membership.tenant_id,
                    ItemOpexEBT.ebt_id == ebt_id,
                    ItemOpexEBT.id == item_id,
                )
                .first()
            )
            if item is None:
                raise LookupError("Item Opex não encontrado.")
            db.delete(item)
            db.flush()
            return {"status": "ok"}
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.post("/v1/ebts/{ebt_id}/planos-saas", tags=["Workspaces EBT"])
    def endpoint_adicionar_plano_saas(
        ebt_id: str,
        req: PlanoSaaSCreateRequest,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        _, membership, _ = ctx
        try:
            verificar_permissao_rbac(
                membership, PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO, ebt_alvo_id=ebt_id
            )
            plano = PlanoSaaSEBT(
                tenant_id=membership.tenant_id,
                ebt_id=ebt_id,
                **req.model_dump(),
            )
            db.add(plano)
            db.flush()
            registrar_evento_auditoria(
                db,
                tenant_id=membership.tenant_id,
                user_id=membership.user_id,
                acao="plano_saas.adicionar",
                entidade_tipo="PlanoSaaSEBT",
                entidade_id=plano.id,
                resumo=f"Plano SaaS '{req.nome_plano}' (R$ {req.ticket_mensal:,.2f}) adicionado.",
            )
            return {"id": plano.id, "status": "ok"}
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.delete("/v1/ebts/{ebt_id}/planos-saas/{plano_id}", tags=["Workspaces EBT"])
    def endpoint_excluir_plano_saas(
        ebt_id: str,
        plano_id: str,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, str]:
        _, membership, _ = ctx
        try:
            verificar_permissao_rbac(
                membership, PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO, ebt_alvo_id=ebt_id
            )
            plano = (
                db.query(PlanoSaaSEBT)
                .filter(
                    PlanoSaaSEBT.tenant_id == membership.tenant_id,
                    PlanoSaaSEBT.ebt_id == ebt_id,
                    PlanoSaaSEBT.id == plano_id,
                )
                .first()
            )
            if plano is None:
                raise LookupError("Plano SaaS não encontrado.")
            db.delete(plano)
            db.flush()
            return {"status": "ok"}
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.put("/v1/ebts/{ebt_id}/juridico", tags=["Workspaces EBT"])
    def endpoint_atualizar_juridico(
        ebt_id: str,
        req: JuridicoUpdateRequest,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, str]:
        _, membership, _ = ctx
        try:
            verificar_permissao_rbac(
                membership, PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO, ebt_alvo_id=ebt_id
            )
            jur = (
                db.query(JuridicoEBT)
                .filter(
                    JuridicoEBT.tenant_id == membership.tenant_id,
                    JuridicoEBT.ebt_id == ebt_id,
                )
                .first()
            )
            if jur is None:
                raise LookupError("Registro jurídico não encontrado.")
            for campo, valor in req.model_dump().items():
                setattr(jur, campo, valor)
            db.flush()
            registrar_evento_auditoria(
                db,
                tenant_id=membership.tenant_id,
                user_id=membership.user_id,
                acao="juridico.atualizar",
                entidade_tipo="JuridicoEBT",
                entidade_id=jur.id,
                resumo=f"Due diligence jurídica da EBT '{ebt_id[:8]}' atualizada.",
            )
            return {"status": "ok"}
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    # ── 5. Simulação Versionada & Monte Carlo da EBT ──────────────────────────

    @app.post("/v1/ebts/{ebt_id}/simular", tags=["Simulação & Monte Carlo"])
    def endpoint_simular_ebt(
        ebt_id: str,
        cenario: TipoCenario = TipoCenario.BASE,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        _, membership, _ = ctx
        try:
            versao, reg_res, res_pydantic = executar_e_versionar_simulacao_ebt(
                db, membership=membership, ebt_id=ebt_id, cenario=cenario
            )
            return {
                "versao_numero": versao.numero_versao,
                "hash_entrada": versao.hash_entrada_sha256,
                "resultado_id": reg_res.id,
                "resultado": res_pydantic.model_dump(),
            }
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.post(
        "/v1/ebts/{ebt_id}/monte-carlo",
        response_model=ResultadoMonteCarlo,
        tags=["Simulação & Monte Carlo"],
    )
    def endpoint_monte_carlo_ebt(
        ebt_id: str,
        iteracoes: int = 300,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> ResultadoMonteCarlo:
        _, membership, _ = ctx
        try:
            verificar_permissao_rbac(
                membership, PermissaoSaaS.SIMULACAO_EXECUTAR, ebt_alvo_id=ebt_id
            )
            ass = (
                db.query(AssinaturaTenant)
                .filter(AssinaturaTenant.tenant_id == membership.tenant_id)
                .first()
            )
            if ass and not ass.permite_monte_carlo:
                raise ErroLimitePlanoSaaS(
                    f"O plano '{ass.plano_codigo}' não inclui Simulação de Monte Carlo. "
                    "Faça upgrade para o plano Pro ou Enterprise."
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
                raise LookupError("EBT não encontrada.")
            entrada = EntradaSimulacaoSaaS.from_orm_projeto(ebt)
            return simular_monte_carlo(entrada, iteracoes=iteracoes, semente=42)
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    # ── 6. Comitê VC (IA Governada) & Data Room PDF ───────────────────────────

    @app.post(
        "/v1/ebts/{ebt_id}/ia/parecer",
        response_model=AnaliseIAResponse,
        tags=["IA Governada & Data Room PDF"],
    )
    def endpoint_solicitar_parecer_ia(
        ebt_id: str,
        req: SolicitarParecerIARequest,
        response: Response,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> AnaliseIAResponse:
        _, membership, _ = ctx
        try:
            modelo_inicial = (
                req.modelo_gemini
                or os.getenv("GEMINI_MODEL", "gemini-4-argon")
            )
            provedor = (
                ProvedorGeminiIA(
                    api_key=req.gemini_api_key,
                    modelo=modelo_inicial,
                )
                if (req.usar_gemini and req.gemini_api_key)
                else ProvedorAuditoriaDeterministicoIA()
            )
            analise, _, veio_do_cache = solicitar_parecer_ia_governado(
                db,
                membership=membership,
                ebt_id=ebt_id,
                provedor_ia=provedor,
                forcar_regeneracao=req.forcar_regeneracao,
                permitir_fallback_copiloto=req.permitir_fallback_copiloto,
            )
            eh_fallback = "fallback" in str(analise.provedor or "").lower()
            modelo_resolvido = (
                getattr(analise, "modelo_resolvido", None)
                or analise.modelo
                or modelo_inicial
            )
            tentativas_executadas = (
                getattr(analise, "tentativas_executadas", 1) or 1
            )
            geracao_resolvida = (
                getattr(analise, "geracao_resolvida", None)
                or obter_geracao_modelo(modelo_resolvido)
            )

            # Headers HTTP obrigatórios para rastreabilidade e telemetria
            response.headers["x-resolved-by-model"] = modelo_resolvido
            response.headers["x-attempts"] = str(tentativas_executadas)

            return AnaliseIAResponse(
                id=analise.id,
                tenant_id=analise.tenant_id,
                ebt_id=analise.ebt_id,
                provedor=analise.provedor,
                modelo=analise.modelo,
                modelo_resolvido=modelo_resolvido,
                tentativas_executadas=tentativas_executadas,
                geracao_resolvida=geracao_resolvida,
                versao_prompt=analise.versao_prompt,
                hash_entrada_simulacao=analise.hash_entrada_simulacao,
                parecer_gerado_md=analise.parecer_gerado_md,
                parecer_revisado_consultor_md=analise.parecer_revisado_consultor_md,
                aprovado_pelo_consultor=analise.aprovado_pelo_consultor,
                custo_estimado_usd=analise.custo_estimado_usd,
                em_cache=veio_do_cache,
                fallback_acionado=eh_fallback,
            )
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.post(
        "/v1/ia/{analise_id}/homologar",
        response_model=AnaliseIAResponse,
        tags=["IA Governada & Data Room PDF"],
    )
    def endpoint_homologar_parecer_ia(
        analise_id: str,
        req: AprovarParecerIARequest,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> AnaliseIAResponse:
        _, membership, _ = ctx
        try:
            analise = revisar_e_aprovar_parecer_ia(
                db,
                membership=membership,
                analise_id=analise_id,
                texto_revisado_md=req.texto_revisado_md,
            )
            return AnaliseIAResponse(
                id=analise.id,
                tenant_id=analise.tenant_id,
                ebt_id=analise.ebt_id,
                provedor=analise.provedor,
                modelo=analise.modelo,
                versao_prompt=analise.versao_prompt,
                hash_entrada_simulacao=analise.hash_entrada_simulacao,
                parecer_gerado_md=analise.parecer_gerado_md,
                parecer_revisado_consultor_md=analise.parecer_revisado_consultor_md,
                aprovado_pelo_consultor=analise.aprovado_pelo_consultor,
                custo_estimado_usd=analise.custo_estimado_usd,
                em_cache=False,
            )
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.post(
        "/v1/ebts/{ebt_id}/dossie-pdf",
        response_model=RelatorioDossieResponse,
        tags=["IA Governada & Data Room PDF"],
    )
    def endpoint_emitir_dossie_pdf(
        ebt_id: str,
        req: EmitirDossiePDFRequest,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> RelatorioDossieResponse:
        _, membership, _ = ctx
        try:
            ebt = (
                db.query(ClienteEBT)
                .filter(
                    ClienteEBT.tenant_id == membership.tenant_id,
                    ClienteEBT.id == ebt_id,
                )
                .first()
            )
            if ebt is None:
                raise LookupError("EBT não encontrada.")

            tenant = db.get(Tenant, membership.tenant_id)
            ass = (
                db.query(AssinaturaTenant)
                .filter(AssinaturaTenant.tenant_id == membership.tenant_id)
                .first()
            )
            ultima_ia = (
                db.query(AnaliseIAEBT)
                .filter(
                    AnaliseIAEBT.tenant_id == membership.tenant_id,
                    AnaliseIAEBT.ebt_id == ebt.id,
                )
                .order_by(AnaliseIAEBT.criado_em.desc())
                .first()
            )
            parecer_final = req.parecer_customizado_md or (
                (
                    ultima_ia.parecer_revisado_consultor_md
                    or ultima_ia.parecer_gerado_md
                )
                if ultima_ia
                else None
            )

            entrada_sim = EntradaSimulacaoSaaS.from_orm_projeto(ebt)
            resultado_sim = executar_simulacao_saas(entrada_sim)

            pdf_bytes = gerar_pdf_executivo_ebt_bytes(
                ebt=ebt,
                resultado_simulacao=resultado_sim,
                tenant_nome=tenant.nome if tenant else "Consultoria",
                permite_white_label=bool(ass.permite_white_label if ass else False),
                parecer_md=parecer_final,
            )

            relatorio, _, url_assinada = registrar_emissao_dossie_pdf(
                db,
                membership=membership,
                ebt_id=ebt.id,
                pdf_bytes=pdf_bytes,
                exigir_parecer_aprovado=req.exigir_parecer_aprovado,
            )

            return RelatorioDossieResponse(
                id=relatorio.id,
                tenant_id=relatorio.tenant_id,
                ebt_id=relatorio.ebt_id,
                resultado_simulacao_id=relatorio.resultado_simulacao_id,
                storage_key=relatorio.storage_key,
                sha256_pdf=relatorio.sha256_pdf,
                url_assinada=url_assinada,
                pdf_base64=base64.b64encode(pdf_bytes).decode("ascii"),
            )
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    # ── 7. Governança SaaS, Share Links, Jobs e Auditoria ─────────────────────

    @app.get("/v1/governanca/painel", tags=["Governança SaaS"])
    def endpoint_painel_governanca(
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        _, membership, _ = ctx
        tid = membership.tenant_id
        ass = (
            db.query(AssinaturaTenant)
            .filter(AssinaturaTenant.tenant_id == tid)
            .first()
        )
        uso = obter_ou_criar_uso_mensal(db, tid)
        total_ebts = (
            db.query(ClienteEBT)
            .filter(ClienteEBT.tenant_id == tid, ClienteEBT.ativo.is_(True))
            .count()
        )
        jobs = listar_jobs_tenant(db, tenant_id=tid, limite=20)
        dossies = (
            db.query(RelatorioDossieEBT)
            .filter(RelatorioDossieEBT.tenant_id == tid)
            .order_by(RelatorioDossieEBT.criado_em.desc())
            .limit(20)
            .all()
        )
        convites = (
            db.query(Convite)
            .filter(Convite.tenant_id == tid)
            .order_by(Convite.criado_em.desc())
            .limit(20)
            .all()
        )
        auditoria = listar_trilha_auditoria(db, limite=40)

        eh_admin = membership.papel in (
            PapelMembro.ADMIN.value,
            PapelMembro.DONO.value,
        )
        if eh_admin:
            garantir_superadmin_inicial(db)
            usuarios_oauth = listar_usuarios_oauth_registrados(db, incluir_todos=True)
        else:
            usuarios_oauth = []
        # Restaura isolamento RLS da sessão após a listagem global do Admin
        db.info["bypass_rls"] = False
        db.info["tenant_id"] = tid

        return {
            "assinatura": {
                "plano_codigo": ass.plano_codigo if ass else "free",
                "status": ass.status if ass else "ativa",
                "limite_ebts": ass.limite_ebts if ass else 1,
                "limite_analises_ia_mes": ass.limite_analises_ia_mes if ass else 1,
                "limite_pdfs_mes": ass.limite_pdfs_mes if ass else 1,
                "permite_monte_carlo": bool(ass.permite_monte_carlo if ass else False),
                "permite_white_label": bool(ass.permite_white_label if ass else False),
            },
            "usuarios_oauth_registrados": usuarios_oauth,
            "uso_mensal": {
                "ano_mes": uso.ano_mes,
                "ebts_ativas": total_ebts,
                "simulacoes_executadas": uso.simulacoes_executadas,
                "analises_ia_realizadas": uso.analises_ia_realizadas,
                "pdfs_gerados": uso.pdfs_gerados,
                "custo_ia_acumulado_usd": uso.custo_ia_acumulado_usd,
            },
            "jobs_assincronos": [
                {
                    "id": j.id,
                    "tipo_job": j.tipo_job,
                    "status": j.status,
                    "progresso_pct": j.progresso_pct,
                    "criado_em": j.criado_em.isoformat() if j.criado_em else None,
                }
                for j in jobs
            ],
            "dossies_emitidos": [
                {
                    "id": d.id,
                    "sha256_pdf": d.sha256_pdf,
                    "storage_key": d.storage_key,
                    "criado_em": d.criado_em.isoformat() if d.criado_em else None,
                }
                for d in dossies
            ],
            "convites_rbac": [
                {
                    "id": c.id,
                    "email_convidado": c.email_convidado,
                    "papel": c.papel,
                    "ebt_restrita_id": c.ebt_restrita_id,
                    "aceito": bool(c.aceito_em is not None),
                    "expira_em": c.expira_em.isoformat() if c.expira_em else None,
                }
                for c in convites
            ],
            "audit_logs": [
                {
                    "id": a.id,
                    "acao": a.acao,
                    "entidade_tipo": a.entidade_tipo,
                    "resumo": a.resumo,
                    "user_id": a.user_id,
                    "criado_em": a.criado_em.isoformat() if a.criado_em else None,
                }
                for a in auditoria
            ],
            "ddl_rls_postgresql": gerar_ddl_rls_postgresql(),
        }

    @app.post("/v1/ebts/{ebt_id}/share-links", tags=["Governança SaaS"])
    def endpoint_criar_share_link(
        ebt_id: str,
        req: ShareLinkCreateRequest,
        ctx: Tuple[User, Membership, Dict[str, Any]] = Depends(
            obter_contexto_autenticado
        ),
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        _, membership, _ = ctx
        try:
            token_claro, link = criar_link_compartilhamento_investidor(
                db,
                membership=membership,
                ebt_id=ebt_id,
                dias_validade=req.dias_validade,
            )
            return {
                "id": link.id,
                "token": token_claro,
                "expira_em": link.expira_em.isoformat(),
            }
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    @app.post("/v1/share-links/validar", tags=["Governança SaaS"])
    def endpoint_validar_share_link(
        req: ShareLinkValidateRequest,
        db: Any = Depends(obter_db),
    ) -> Dict[str, Any]:
        try:
            db.info["bypass_rls"] = True
            link = validar_token_investidor(db, token_claro=req.token)
            return {
                "valido": True,
                "ebt_id": link.ebt_id,
                "tenant_id": link.tenant_id,
                "acessos_realizados": link.acessos_realizados,
                "expira_em": link.expira_em.isoformat(),
            }
        except Exception as exc:
            raise _mapear_excecao_negocio(exc) from exc

    return app


try:
    app = criar_app_fastapi()
except RuntimeError:
    app = None
