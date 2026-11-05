"""
Camada de Autenticação OAuth2 / OIDC, Emissão de JWT e Vínculo Dinâmico com Perfis RBAC
(Fase 4 — Master Management SaaS).

Suporta:
1. OAuth2 Real (Google e GitHub) configurável via variáveis de ambiente.
2. OAuth2 Sandbox / Quick-Link RBAC para autenticação imediata e teste dos 6 papéis
   (`dono`, `admin`, `consultor`, `analista`, `fundador`, `investidor`).
3. Links de Convite OAuth vinculados a um Papel RBAC e (opcionalmente) a uma EBT restrita
   através da entidade `Convite`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from .auditoria import registrar_evento_auditoria
from .models import (
    AssinaturaTenant,
    CenarioEBT,
    ClienteEBT,
    Convite,
    JuridicoEBT,
    LeanCanvasEBT,
    Membership,
    PapelMembro,
    PlanoAssinaturaCodigo,
    PremissasEBT,
    StatusAssinatura,
    Tenant,
    User,
)
from .rbac import (
    MATRIZ_PERMISSOES_RBAC,
    ErroPermissaoRBAC,
    PermissaoSaaS,
    verificar_permissao_rbac,
)
from .servicos import CONFIG_LIMITES_POR_PLANO


class ErroAutenticacaoOAuth(PermissionError):
    """Exceção disparada quando credenciais (e-mail/senha), token JWT ou convite RBAC são inválidos."""


EMAIL_SUPERADMIN_INICIAL = "marcolinoee@yahoo.com.br"
SENHA_SUPERADMIN_INICIAL = "123456"
_ITERACOES_PBKDF2 = 120_000


def gerar_hash_senha(senha_clara: str) -> str:
    """
    Gera um hash criptográfico seguro para a senha usando PBKDF2-HMAC-SHA256
    com salt aleatório de 16 bytes (128 bits).
    Formato armazenado: `pbkdf2_sha256$<iteracoes>$<salt_hex>$<hash_hex>`
    """
    salt = secrets.token_bytes(16)
    derivado = hashlib.pbkdf2_hmac(
        "sha256",
        senha_clara.encode("utf-8"),
        salt,
        _ITERACOES_PBKDF2,
    )
    return f"pbkdf2_sha256${_ITERACOES_PBKDF2}${salt.hex()}${derivado.hex()}"


def verificar_senha_hash(
    senha_clara: str, senha_hash_armazenado: Optional[str]
) -> bool:
    """
    Verifica em tempo constante (`hmac.compare_digest`) se `senha_clara`
    corresponde ao `senha_hash_armazenado`.
    """
    if not senha_clara or not senha_hash_armazenado:
        return False
    partes = senha_hash_armazenado.split("$")
    if len(partes) != 4 or partes[0] != "pbkdf2_sha256":
        return False
    try:
        iteracoes = int(partes[1])
        salt = bytes.fromhex(partes[2])
        hash_esperado = bytes.fromhex(partes[3])
    except Exception:
        return False
    derivado = hashlib.pbkdf2_hmac(
        "sha256",
        senha_clara.encode("utf-8"),
        salt,
        iteracoes,
    )
    return hmac.compare_digest(derivado, hash_esperado)


def _obter_segredo_jwt() -> bytes:
    segredo = os.getenv(
        "MM_JWT_SECRET", "master-management-saas-jwt-secret-key-2026-production"
    )
    return segredo.encode("utf-8")


def _b64url_encode(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def _b64url_decode(texto: str) -> bytes:
    padding = "=" * (-len(texto) % 4)
    return base64.urlsafe_b64decode((texto + padding).encode("ascii"))


def gerar_jwt_sessao_saas(
    *,
    user_id: str,
    email: str,
    nome: str,
    tenant_id: str,
    membership_id: str,
    papel: str,
    ebt_restrita_id: Optional[str] = None,
    provedor_oauth: str = "oauth-local",
    expira_em_segundos: int = 86400,
) -> str:
    """
    Emite um JSON Web Token (JWT RFC 7519) assinado com HMAC-SHA256 (HS256)
    contendo o contexto completo de identidade, Tenant (RLS) e Papel RBAC.
    """
    agora = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "email": email,
        "name": nome,
        "tenant_id": tenant_id,
        "membership_id": membership_id,
        "papel": papel,
        "ebt_restrita_id": ebt_restrita_id,
        "provider": provedor_oauth,
        "iat": agora,
        "exp": agora + max(60, expira_em_segundos),
    }

    segmento_header = _b64url_encode(
        json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    segmento_payload = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    mensagem = f"{segmento_header}.{segmento_payload}".encode("ascii")
    assinatura = hmac.new(_obter_segredo_jwt(), mensagem, hashlib.sha256).digest()
    segmento_assinatura = _b64url_encode(assinatura)
    return f"{segmento_header}.{segmento_payload}.{segmento_assinatura}"


def decodificar_jwt_sessao_saas(
    token: str, *, agora_ts: Optional[int] = None
) -> Dict[str, Any]:
    """
    Valida a assinatura HMAC-SHA256 e a expiração de um JWT do Master Management SaaS.
    """
    if not token or token.count(".") != 2:
        raise ErroAutenticacaoOAuth("Token JWT malformado.")

    seg_header, seg_payload, seg_sig = token.split(".")
    mensagem = f"{seg_header}.{seg_payload}".encode("ascii")
    assinatura_esperada = _b64url_encode(
        hmac.new(_obter_segredo_jwt(), mensagem, hashlib.sha256).digest()
    )

    if not hmac.compare_digest(seg_sig, assinatura_esperada):
        raise ErroAutenticacaoOAuth("Assinatura do token JWT inválida.")

    try:
        payload: Dict[str, Any] = json.loads(_b64url_decode(seg_payload).decode("utf-8"))
    except Exception as exc:
        raise ErroAutenticacaoOAuth("Payload do token JWT inválido.") from exc

    instante = agora_ts if agora_ts is not None else int(time.time())
    if int(payload.get("exp", 0)) <= instante:
        raise ErroAutenticacaoOAuth("Token JWT expirado.")

    return payload


# =============================================================================
# PROVEDORES OAUTH2 (GOOGLE, GITHUB E SANDBOX RBAC)
# =============================================================================


def listar_provedores_oauth_configurados(
    redirect_base_url: str = "http://localhost:3000",
) -> List[Dict[str, Any]]:
    """
    Retorna os provedores OAuth2 disponíveis e seus status de configuração,
    além dos 6 perfis RBAC para vínculo rápido.
    """
    google_client_id = os.getenv("OAUTH_GOOGLE_CLIENT_ID", "")
    github_client_id = os.getenv("OAUTH_GITHUB_CLIENT_ID", "")

    return [
        {
            "id": "google",
            "nome": "Google Workspace / OAuth2",
            "configurado": bool(google_client_id),
            "authorize_url": construir_url_autorizacao_oauth(
                "google", redirect_uri=f"{redirect_base_url}/oauth/callback"
            )
            if google_client_id
            else None,
        },
        {
            "id": "github",
            "nome": "GitHub OAuth2",
            "configurado": bool(github_client_id),
            "authorize_url": construir_url_autorizacao_oauth(
                "github", redirect_uri=f"{redirect_base_url}/oauth/callback"
            )
            if github_client_id
            else None,
        },
        {
            "id": "oauth-rbac-sandbox",
            "nome": "OAuth2 RBAC Identity Sandbox (6 Perfis Prontos)",
            "configurado": True,
            "authorize_url": f"{redirect_base_url}/login",
        },
    ]


def construir_url_autorizacao_oauth(
    provedor: str,
    *,
    redirect_uri: str,
    state: Optional[str] = None,
    invite_token: Optional[str] = None,
) -> str:
    """Constrói a URL de redirecionamento OAuth2 para Google ou GitHub preservando `invite_token` no `state`."""
    estado_obj = {
        "nonce": state or secrets.token_urlsafe(12),
        "provider": provedor,
        "invite_token": invite_token,
    }
    estado_codificado = _b64url_encode(json.dumps(estado_obj).encode("utf-8"))

    if provedor == "google":
        client_id = os.getenv("OAUTH_GOOGLE_CLIENT_ID", "google-client-id-nao-definido")
        params = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": estado_codificado,
                "access_type": "online",
                "prompt": "select_account",
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

    if provedor == "github":
        client_id = os.getenv("OAUTH_GITHUB_CLIENT_ID", "github-client-id-nao-definido")
        params = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": "read:user user:email",
                "state": estado_codificado,
            }
        )
        return f"https://github.com/login/oauth/authorize?{params}"

    raise ValueError(f"Provedor OAuth '{provedor}' não suportado.")


def trocar_codigo_oauth_por_perfil(
    provedor: str,
    *,
    code: str,
    redirect_uri: str,
) -> Dict[str, str]:
    """
    Realiza a troca do `authorization_code` OAuth2 junto ao Google ou GitHub
    pelo perfil verificado do usuário (`email`, `nome`, `sub`).
    """
    if provedor == "google":
        client_id = os.getenv("OAUTH_GOOGLE_CLIENT_ID", "")
        client_secret = os.getenv("OAUTH_GOOGLE_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            raise ErroAutenticacaoOAuth(
                "Variáveis OAUTH_GOOGLE_CLIENT_ID / OAUTH_GOOGLE_CLIENT_SECRET não configuradas."
            )
        dados_token = urllib.parse.urlencode(
            {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
        ).encode("utf-8")
        req_token = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=dados_token,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req_token, timeout=10) as resp:
            token_json = json.loads(resp.read().decode("utf-8"))

        access_token = token_json.get("access_token")
        req_user = urllib.request.Request(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        with urllib.request.urlopen(req_user, timeout=10) as resp_u:
            user_json = json.loads(resp_u.read().decode("utf-8"))

        return {
            "email": str(user_json.get("email", "")).lower().strip(),
            "nome": str(user_json.get("name") or user_json.get("email", "Usuário Google")),
            "sub": str(user_json.get("sub", "")),
            "provedor": "google",
        }

    if provedor == "github":
        client_id = os.getenv("OAUTH_GITHUB_CLIENT_ID", "")
        client_secret = os.getenv("OAUTH_GITHUB_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            raise ErroAutenticacaoOAuth(
                "Variáveis OAUTH_GITHUB_CLIENT_ID / OAUTH_GITHUB_CLIENT_SECRET não configuradas."
            )
        dados_token = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            }
        ).encode("utf-8")
        req_token = urllib.request.Request(
            "https://github.com/login/oauth/access_token",
            data=dados_token,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        with urllib.request.urlopen(req_token, timeout=10) as resp:
            token_json = json.loads(resp.read().decode("utf-8"))

        access_token = token_json.get("access_token")
        req_user = urllib.request.Request(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "MasterManagementSaaS/1.0",
            },
        )
        with urllib.request.urlopen(req_user, timeout=10) as resp_u:
            user_json = json.loads(resp_u.read().decode("utf-8"))

        email = str(user_json.get("email") or "").lower().strip()
        if not email:
            email = f"{user_json.get('login', 'github_user')}@users.noreply.github.com"

        return {
            "email": email,
            "nome": str(user_json.get("name") or user_json.get("login", "Usuário GitHub")),
            "sub": str(user_json.get("id", "")),
            "provedor": "github",
        }

    raise ErroAutenticacaoOAuth(f"Provedor OAuth '{provedor}' inválido.")


# =============================================================================
# LINKS DE CONVITE OAUTH VINCULADOS A PERFIS RBAC (CONVITE -> MEMBERSHIP)
# =============================================================================


def criar_convite_rbac_oauth(
    db: Session,
    *,
    membership_emissor: Membership,
    email_convidado: str,
    papel: PapelMembro,
    ebt_restrita_id: Optional[str] = None,
    dias_validade: int = 7,
) -> Tuple[str, Convite]:
    """
    Gera um Link/Token de Convite OAuth vinculado a um perfil RBAC específico
    (`dono`, `admin`, `consultor`, `analista`, `fundador`, `investidor`).
    Quando o convidado fizer login via OAuth usando este token, sua conta
    receberá automaticamente o `Membership` com o `papel` e `ebt_restrita_id` definidos.
    """
    verificar_permissao_rbac(membership_emissor, PermissaoSaaS.TENANT_CONVIDAR_MEMBROS)

    if papel in (PapelMembro.FUNDADOR, PapelMembro.INVESTIDOR) and not ebt_restrita_id:
        primeira_ebt = (
            db.query(ClienteEBT)
            .filter(
                ClienteEBT.tenant_id == membership_emissor.tenant_id,
                ClienteEBT.ativo.is_(True),
            )
            .first()
        )
        if primeira_ebt:
            ebt_restrita_id = primeira_ebt.id

    token_claro = secrets.token_urlsafe(24)
    token_hash = hashlib.sha256(token_claro.encode("utf-8")).hexdigest()
    expira_em = datetime.now(timezone.utc) + timedelta(days=max(1, dias_validade))

    convite = Convite(
        tenant_id=membership_emissor.tenant_id,
        email_convidado=email_convidado.strip().lower(),
        papel=papel.value,
        ebt_restrita_id=ebt_restrita_id,
        token_hash=token_hash,
        expira_em=expira_em,
        aceito_em=None,
    )
    db.add(convite)
    db.flush()

    registrar_evento_auditoria(
        db,
        tenant_id=membership_emissor.tenant_id,
        user_id=membership_emissor.user_id,
        acao="oauth.convite_rbac_criar",
        entidade_tipo="Convite",
        entidade_id=convite.id,
        resumo=(
            f"Link OAuth RBAC criado para '{convite.email_convidado}' com papel '{convite.papel}' "
            f"(EBT restrita: {ebt_restrita_id or 'Todas do Tenant'})."
        ),
        dados_novos={
            "email_convidado": convite.email_convidado,
            "papel": convite.papel,
            "ebt_restrita_id": ebt_restrita_id,
        },
    )

    return token_claro, convite


def _instanciar_assinatura_tenant(
    tenant_id: str, plano: PlanoAssinaturaCodigo
) -> AssinaturaTenant:
    cfg = CONFIG_LIMITES_POR_PLANO[plano]
    return AssinaturaTenant(
        tenant_id=tenant_id,
        plano_codigo=plano.value,
        status=StatusAssinatura.ATIVA.value,
        limite_ebts=int(cfg["limite_ebts"]),
        limite_cenarios_por_ebt=int(cfg["limite_cenarios_por_ebt"]),
        limite_analises_ia_mes=int(cfg["limite_analises_ia_mes"]),
        limite_pdfs_mes=int(cfg["limite_pdfs_mes"]),
        permite_monte_carlo=bool(cfg["permite_monte_carlo"]),
        permite_white_label=bool(cfg["permite_white_label"]),
    )


def _criar_workspace_inicial_para_tenant(
    db: Session, *, tenant_id: str, nome_startup: str
) -> ClienteEBT:
    ebt = ClienteEBT(
        tenant_id=tenant_id,
        nome_startup=nome_startup,
        setor_vertical="SaaS B2B",
        estagio="Pre-Seed",
    )
    db.add(ebt)
    db.flush()
    db.add(LeanCanvasEBT(tenant_id=tenant_id, ebt_id=ebt.id))
    db.add(PremissasEBT(tenant_id=tenant_id, ebt_id=ebt.id))
    db.add(JuridicoEBT(tenant_id=tenant_id, ebt_id=ebt.id))
    db.add(
        CenarioEBT(
            tenant_id=tenant_id,
            ebt_id=ebt.id,
            nome="Cenário Base",
            tipo_cenario="base",
        )
    )
    db.flush()
    return ebt


def autenticar_via_oauth_ou_convite(
    db: Session,
    *,
    email: str,
    nome: str,
    provedor: str,
    sub_externo: Optional[str] = None,
    invite_token: Optional[str] = None,
    tenant_id_preferencial: Optional[str] = None,
    papel_sandbox: Optional[PapelMembro] = None,
) -> Dict[str, Any]:
    """
    Autentica um usuário via OAuth2 (Google, GitHub ou Provedor OAuth Corporativo).
    Regras obrigatórias de Governança OAuth + RBAC:
    1. Todos os perfis RBAC requerem autenticação OAuth prévia registrada no banco (`User.provedor_auth_sub`).
    2. O PRIMEIRO perfil autenticado via OAuth no banco de dados é registrado automaticamente como `admin`.
    3. Todos os DEMAIS perfis autenticados via OAuth são categorizados automaticamente como assinantes
       `FREE TIER` (`PlanoAssinaturaCodigo.FREE`), ficando o upgrade de plano e elevação de papel RBAC
       sob responsabilidade exclusiva do `admin`.
    """
    db.info["bypass_rls"] = True

    email_limpo = email.strip().lower()
    sub_formatado = f"{provedor}:{sub_externo or email_limpo}"

    # Verifica se já existe algum administrador autenticado via OAuth no banco ANTES deste login
    existe_admin_oauth = (
        db.query(Membership)
        .join(User, User.id == Membership.user_id)
        .filter(
            User.provedor_auth_sub.isnot(None),
            Membership.papel == PapelMembro.ADMIN.value,
            Membership.ativo.is_(True),
        )
        .first()
        is not None
    )

    user = db.query(User).filter(User.email == email_limpo).first()
    if user is None:
        user = User(
            email=email_limpo,
            nome_completo=nome.strip() or email_limpo.split("@")[0],
            provedor_auth_sub=sub_formatado,
            ativo=True,
        )
        db.add(user)
        db.flush()
    else:
        user.provedor_auth_sub = sub_formatado
        if nome.strip():
            user.nome_completo = nome.strip()
        db.flush()

    membership_selecionada: Optional[Membership] = None

    # 1. Se veio um `invite_token` de Link RBAC OAuth emitido pelo Admin, valida e vincula
    if invite_token:
        token_hash = hashlib.sha256(invite_token.strip().encode("utf-8")).hexdigest()
        convite = (
            db.query(Convite)
            .filter(Convite.token_hash == token_hash)
            .first()
        )
        if convite is None:
            raise ErroAutenticacaoOAuth("Token de convite RBAC OAuth não encontrado.")
        if convite.aceito_em is not None:
            raise ErroAutenticacaoOAuth("Este convite RBAC OAuth já foi utilizado.")

        expiracao = convite.expira_em
        if expiracao.tzinfo is None:
            expiracao = expiracao.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= expiracao:
            raise ErroAutenticacaoOAuth("Este convite RBAC OAuth expirou.")

        convite.aceito_em = datetime.now(timezone.utc)
        membership_existente = (
            db.query(Membership)
            .filter(
                Membership.tenant_id == convite.tenant_id,
                Membership.user_id == user.id,
            )
            .first()
        )
        if membership_existente is None:
            membership_existente = Membership(
                tenant_id=convite.tenant_id,
                user_id=user.id,
                papel=convite.papel,
                ebt_restrita_id=convite.ebt_restrita_id,
                ativo=True,
            )
            db.add(membership_existente)
            db.flush()
        else:
            membership_existente.papel = convite.papel
            membership_existente.ebt_restrita_id = convite.ebt_restrita_id
            membership_existente.ativo = True
            db.flush()

        membership_selecionada = membership_existente
        registrar_evento_auditoria(
            db,
            tenant_id=convite.tenant_id,
            user_id=user.id,
            acao="oauth.convite_rbac_aceito",
            entidade_tipo="Membership",
            entidade_id=membership_selecionada.id,
            resumo=(
                f"Usuário '{user.email}' autenticou via OAuth ({provedor}) e assumiu o perfil RBAC "
                f"'{membership_selecionada.papel}'."
            ),
        )

    # 2. Suporte para testes programáticos explícitos (`papel_sandbox`)
    if membership_selecionada is None and papel_sandbox is not None:
        tenant_alvo = (
            db.get(Tenant, tenant_id_preferencial)
            if tenant_id_preferencial
            else db.query(Tenant).order_by(Tenant.criado_em.asc()).first()
        )
        if tenant_alvo is not None:
            membership_selecionada = (
                db.query(Membership)
                .filter(
                    Membership.tenant_id == tenant_alvo.id,
                    Membership.user_id == user.id,
                    Membership.ativo.is_(True),
                )
                .first()
            )
            primeira_ebt = (
                db.query(ClienteEBT)
                .filter(ClienteEBT.tenant_id == tenant_alvo.id)
                .first()
            )
            ebt_id_vinc = (
                primeira_ebt.id
                if papel_sandbox in (PapelMembro.FUNDADOR, PapelMembro.INVESTIDOR)
                and primeira_ebt
                else None
            )
            if membership_selecionada is None:
                membership_selecionada = Membership(
                    tenant_id=tenant_alvo.id,
                    user_id=user.id,
                    papel=papel_sandbox.value,
                    ebt_restrita_id=ebt_id_vinc,
                    ativo=True,
                )
                db.add(membership_selecionada)
                db.flush()
            else:
                membership_selecionada.papel = papel_sandbox.value
                membership_selecionada.ebt_restrita_id = ebt_id_vinc
                db.flush()

    # 3. Fluxo Padrão OAuth:
    #    - Se o usuário já possui Membership ativa (de login OAuth anterior), recupera-a.
    #    - Se for o PRIMEIRO acesso OAuth do banco (sem Admin OAuth ainda), registra como ADMIN.
    #    - Se já houver Admin OAuth, registra o novo usuário como Assinante FREE TIER.
    if membership_selecionada is None:
        query_m = db.query(Membership).filter(
            Membership.user_id == user.id,
            Membership.ativo.is_(True),
        )
        if tenant_id_preferencial:
            m_pref = query_m.filter(
                Membership.tenant_id == tenant_id_preferencial
            ).first()
            if m_pref:
                membership_selecionada = m_pref

        if membership_selecionada is None:
            membership_selecionada = query_m.first()

        if membership_selecionada is None:
            if not existe_admin_oauth:
                # 1º Usuário OAuth no banco -> Registrado obrigatoriamente como ADMIN
                tenant_principal = (
                    db.query(Tenant).order_by(Tenant.criado_em.asc()).first()
                )
                if tenant_principal is None:
                    tenant_principal = Tenant(
                        nome="Master Management Venture Partners",
                        slug="master-vc",
                        ativo=True,
                    )
                    db.add(tenant_principal)
                    db.flush()
                    db.add(
                        _instanciar_assinatura_tenant(
                            tenant_principal.id, PlanoAssinaturaCodigo.PRO
                        )
                    )
                    db.flush()

                ebt_existente = (
                    db.query(ClienteEBT)
                    .filter(ClienteEBT.tenant_id == tenant_principal.id)
                    .first()
                )
                if ebt_existente is None:
                    _criar_workspace_inicial_para_tenant(
                        db,
                        tenant_id=tenant_principal.id,
                        nome_startup="Nova Startup TIC",
                    )

                membership_selecionada = Membership(
                    tenant_id=tenant_principal.id,
                    user_id=user.id,
                    papel=PapelMembro.ADMIN.value,
                    ebt_restrita_id=None,
                    ativo=True,
                )
                db.add(membership_selecionada)
                db.flush()

                registrar_evento_auditoria(
                    db,
                    tenant_id=tenant_principal.id,
                    user_id=user.id,
                    acao="oauth.registro_admin_inicial",
                    entidade_tipo="Membership",
                    entidade_id=membership_selecionada.id,
                    resumo=(
                        f"Primeiro acesso OAuth ('{user.email}' via {provedor}) registrado "
                        f"automaticamente como ADMIN da plataforma."
                    ),
                )
            else:
                # Demais Usuários OAuth -> Categorizados como Assinantes FREE TIER
                slug_base = (
                    email_limpo.split("@")[0]
                    .replace(".", "-")
                    .replace("_", "-")[:20]
                )
                slug_unico = f"free-{slug_base}-{secrets.token_hex(3)}"
                tenant_free = Tenant(
                    nome=f"Workspace Free Tier — {user.nome_completo}",
                    slug=slug_unico,
                    ativo=True,
                )
                db.add(tenant_free)
                db.flush()

                db.add(
                    _instanciar_assinatura_tenant(
                        tenant_free.id, PlanoAssinaturaCodigo.FREE
                    )
                )
                db.flush()

                ebt_free = _criar_workspace_inicial_para_tenant(
                    db,
                    tenant_id=tenant_free.id,
                    nome_startup=f"Startup de {user.nome_completo}",
                )

                membership_selecionada = Membership(
                    tenant_id=tenant_free.id,
                    user_id=user.id,
                    papel=PapelMembro.FUNDADOR.value,
                    ebt_restrita_id=ebt_free.id,
                    ativo=True,
                )
                db.add(membership_selecionada)
                db.flush()

                registrar_evento_auditoria(
                    db,
                    tenant_id=tenant_free.id,
                    user_id=user.id,
                    acao="oauth.registro_assinante_free_tier",
                    entidade_tipo="Membership",
                    entidade_id=membership_selecionada.id,
                    resumo=(
                        f"Novo acesso OAuth ('{user.email}' via {provedor}) categorizado "
                        f"automaticamente como Assinante FREE TIER (upgrade sob responsabilidade do Admin)."
                    ),
                )

    return construir_resposta_sessao_autenticada(
        db,
        user=user,
        membership_ativa=membership_selecionada,
        provedor_oauth=provedor,
    )


def garantir_superadmin_inicial(db: Session) -> Tuple[User, Membership]:
    """
    Seed / Auth Hook obrigatório para o Administrador Inicial (`ADMIN` / `SUPERADMIN`):
    - E-mail: `marcolinoee@yahoo.com.br`
    - Senha inicial: `123456` (armazenada com hash PBKDF2-HMAC-SHA256)
    - Role: `ADMIN` (`PapelMembro.ADMIN`) com acesso irrestrito ao sistema e ao Painel Admin.
    """
    db.info["bypass_rls"] = True

    tenant_principal = db.query(Tenant).order_by(Tenant.criado_em.asc()).first()
    if tenant_principal is None:
        tenant_principal = Tenant(
            nome="Master Management Venture Partners",
            slug="master-vc",
            ativo=True,
        )
        db.add(tenant_principal)
        db.flush()
        db.add(
            _instanciar_assinatura_tenant(
                tenant_principal.id, PlanoAssinaturaCodigo.PRO
            )
        )
        db.flush()

    ebt_existente = (
        db.query(ClienteEBT)
        .filter(ClienteEBT.tenant_id == tenant_principal.id)
        .first()
    )
    if ebt_existente is None:
        _criar_workspace_inicial_para_tenant(
            db,
            tenant_id=tenant_principal.id,
            nome_startup="Nova Startup TIC",
        )

    user_admin = (
        db.query(User)
        .filter(User.email == EMAIL_SUPERADMIN_INICIAL)
        .first()
    )
    if user_admin is None:
        user_admin = User(
            email=EMAIL_SUPERADMIN_INICIAL,
            nome_completo="Marcolino (Super Admin)",
            senha_hash=gerar_hash_senha(SENHA_SUPERADMIN_INICIAL),
            telefone_whatsapp="",
            cargo_organizacao="Diretoria Executiva · Super Admin",
            avatar_url="",
            provedor_auth_sub=f"credentials:{EMAIL_SUPERADMIN_INICIAL}",
            ativo=True,
        )
        db.add(user_admin)
        db.flush()
    else:
        if not user_admin.senha_hash:
            user_admin.senha_hash = gerar_hash_senha(SENHA_SUPERADMIN_INICIAL)
        if not user_admin.provedor_auth_sub:
            user_admin.provedor_auth_sub = f"credentials:{EMAIL_SUPERADMIN_INICIAL}"
        if not user_admin.cargo_organizacao:
            user_admin.cargo_organizacao = "Diretoria Executiva · Super Admin"
        user_admin.ativo = True
        db.flush()

    membership_admin = (
        db.query(Membership)
        .filter(
            Membership.tenant_id == tenant_principal.id,
            Membership.user_id == user_admin.id,
        )
        .first()
    )
    if membership_admin is None:
        membership_admin = Membership(
            tenant_id=tenant_principal.id,
            user_id=user_admin.id,
            papel=PapelMembro.ADMIN.value,
            ebt_restrita_id=None,
            ativo=True,
        )
        db.add(membership_admin)
        db.flush()
    else:
        membership_admin.papel = PapelMembro.ADMIN.value
        membership_admin.ativo = True
        db.flush()

    return user_admin, membership_admin


def autenticar_com_email_e_senha(
    db: Session,
    *,
    email: str,
    senha: str,
) -> Dict[str, Any]:
    """
    Autenticação tradicional protegida por E-mail e Senha (com hash PBKDF2-HMAC-SHA256).
    Garante que o SuperAdmin inicial (`marcolinoee@yahoo.com.br` / `123456`) esteja semeado
    no banco e valida credenciais + status ativo antes de emitir o token JWT da sessão.
    """
    db.info["bypass_rls"] = True
    garantir_superadmin_inicial(db)

    email_limpo = (email or "").strip().lower()
    if not email_limpo or "@" not in email_limpo:
        raise ErroAutenticacaoOAuth("Informe um endereço de e-mail válido.")
    if not senha:
        raise ErroAutenticacaoOAuth("Informe a sua senha para entrar no sistema.")

    user = db.query(User).filter(User.email == email_limpo).first()
    if user is None or not verificar_senha_hash(senha, user.senha_hash):
        raise ErroAutenticacaoOAuth(
            "Credenciais inválidas: e-mail ou senha incorretos."
        )

    if not user.ativo:
        raise ErroAutenticacaoOAuth(
            "Acesso bloqueado: sua conta encontra-se inativa. Contate o Administrador do sistema."
        )

    membership = (
        db.query(Membership)
        .filter(Membership.user_id == user.id, Membership.ativo.is_(True))
        .order_by(Membership.criado_em.asc())
        .first()
    )
    if membership is None:
        raise ErroAutenticacaoOAuth(
            "Acesso bloqueado: seu perfil não possui vínculo ativo no sistema. Contate o Administrador."
        )

    if not user.provedor_auth_sub:
        user.provedor_auth_sub = f"credentials:{user.email}"
        db.flush()

    registrar_evento_auditoria(
        db,
        tenant_id=membership.tenant_id,
        user_id=user.id,
        acao="auth.login_credenciais",
        entidade_tipo="User",
        entidade_id=user.id,
        resumo=f"Login autenticado com sucesso por '{user.email}' (Papel RBAC: {membership.papel}).",
    )

    return construir_resposta_sessao_autenticada(
        db,
        user=user,
        membership_ativa=membership,
        provedor_oauth="credentials",
    )


def registrar_novo_usuario_credenciais(
    db: Session,
    *,
    nome_completo: str,
    email: str,
    senha: str,
    telefone_whatsapp: str = "",
    cargo_organizacao: str = "",
) -> Dict[str, Any]:
    """
    Cadastra um novo usuário com e-mail e senha (hash PBKDF2-HMAC-SHA256),
    categorizando-o inicialmente como `ASSINANTE_FREE` no plano `FREE TIER`.
    """
    db.info["bypass_rls"] = True
    garantir_superadmin_inicial(db)

    email_limpo = (email or "").strip().lower()
    if not email_limpo or "@" not in email_limpo:
        raise ValueError("Informe um endereço de e-mail válido.")
    if not nome_completo or not nome_completo.strip():
        raise ValueError("Informe o seu nome completo.")
    if not senha or len(senha) < 6:
        raise ValueError("A senha deve possuir no mínimo 6 caracteres.")

    existente = db.query(User).filter(User.email == email_limpo).first()
    if existente is not None:
        raise ValueError("Já existe uma conta cadastrada com este endereço de e-mail.")

    slug_base = (
        email_limpo.split("@")[0].replace(".", "-").replace("_", "-")[:20]
    )
    slug_unico = f"free-{slug_base}-{secrets.token_hex(3)}"
    tenant_free = Tenant(
        nome=f"Workspace Free Tier — {nome_completo.strip()}",
        slug=slug_unico,
        ativo=True,
    )
    db.add(tenant_free)
    db.flush()
    db.add(
        _instanciar_assinatura_tenant(tenant_free.id, PlanoAssinaturaCodigo.FREE)
    )
    db.flush()

    ebt_free = _criar_workspace_inicial_para_tenant(
        db,
        tenant_id=tenant_free.id,
        nome_startup=f"Startup de {nome_completo.strip()}",
    )

    novo_user = User(
        email=email_limpo,
        nome_completo=nome_completo.strip(),
        senha_hash=gerar_hash_senha(senha),
        telefone_whatsapp=(telefone_whatsapp or "").strip(),
        cargo_organizacao=(cargo_organizacao or "Assinante Free Tier").strip(),
        avatar_url="",
        provedor_auth_sub=f"credentials:{email_limpo}",
        ativo=True,
    )
    db.add(novo_user)
    db.flush()

    membership = Membership(
        tenant_id=tenant_free.id,
        user_id=novo_user.id,
        papel=PapelMembro.ASSINANTE_FREE.value,
        ebt_restrita_id=None,
        ativo=True,
    )
    db.add(membership)
    db.flush()

    registrar_evento_auditoria(
        db,
        tenant_id=tenant_free.id,
        user_id=novo_user.id,
        acao="auth.cadastro_usuario",
        entidade_tipo="User",
        entidade_id=novo_user.id,
        resumo=(
            f"Novo usuário '{novo_user.email}' cadastrado como ASSINANTE_FREE "
            f"(Workspace inicial: '{ebt_free.nome_startup}')."
        ),
    )

    return construir_resposta_sessao_autenticada(
        db,
        user=novo_user,
        membership_ativa=membership,
        provedor_oauth="credentials",
    )


def criar_usuario_pelo_admin(
    db: Session,
    *,
    membership_admin: Membership,
    nome_completo: str,
    email: str,
    senha: str,
    papel: PapelMembro = PapelMembro.ASSINANTE_FREE,
    plano: PlanoAssinaturaCodigo = PlanoAssinaturaCodigo.FREE,
    cargo_organizacao: str = "",
    telefone_whatsapp: str = "",
) -> Dict[str, Any]:
    """
    Exclusivo para o Administrador (`ADMIN`):
    Cadastra um novo usuário diretamente pelo Painel de Administração RBAC.
    """
    db.info["bypass_rls"] = True
    if membership_admin.papel not in (
        PapelMembro.ADMIN.value,
        PapelMembro.DONO.value,
    ):
        raise ErroPermissaoRBAC(
            "Apenas usuários com a role ADMIN podem criar novos usuários no Painel RBAC."
        )

    email_limpo = (email or "").strip().lower()
    if not email_limpo or "@" not in email_limpo:
        raise ValueError("Informe um endereço de e-mail válido.")
    if not nome_completo or not nome_completo.strip():
        raise ValueError("Informe o nome completo do usuário.")
    if not senha or len(senha) < 6:
        raise ValueError("A senha inicial deve possuir no mínimo 6 caracteres.")

    if db.query(User).filter(User.email == email_limpo).first() is not None:
        raise ValueError("Já existe um usuário cadastrado com este e-mail.")

    if papel == PapelMembro.ASSINANTE_PRO and plano == PlanoAssinaturaCodigo.FREE:
        plano = PlanoAssinaturaCodigo.PRO

    # Se for ASSINANTE_FREE ou ASSINANTE_PRO, cria um workspace próprio ou vincula ao tenant atual
    if papel in (PapelMembro.ASSINANTE_FREE, PapelMembro.ASSINANTE_PRO):
        slug_base = (
            email_limpo.split("@")[0].replace(".", "-").replace("_", "-")[:20]
        )
        tenant_alvo = Tenant(
            nome=f"Workspace — {nome_completo.strip()}",
            slug=f"ws-{slug_base}-{secrets.token_hex(3)}",
            ativo=True,
        )
        db.add(tenant_alvo)
        db.flush()
        db.add(_instanciar_assinatura_tenant(tenant_alvo.id, plano))
        db.flush()
        _criar_workspace_inicial_para_tenant(
            db,
            tenant_id=tenant_alvo.id,
            nome_startup=f"Startup de {nome_completo.strip()}",
        )
        tid_alvo = tenant_alvo.id
        ebt_restrita = None
    else:
        tid_alvo = membership_admin.tenant_id
        primeira_ebt = (
            db.query(ClienteEBT)
            .filter(
                ClienteEBT.tenant_id == tid_alvo,
                ClienteEBT.ativo.is_(True),
            )
            .first()
        )
        ebt_restrita = (
            primeira_ebt.id
            if papel in (PapelMembro.FUNDADOR, PapelMembro.INVESTIDOR)
            and primeira_ebt
            else None
        )

    novo_user = User(
        email=email_limpo,
        nome_completo=nome_completo.strip(),
        senha_hash=gerar_hash_senha(senha),
        telefone_whatsapp=(telefone_whatsapp or "").strip(),
        cargo_organizacao=(cargo_organizacao or "").strip(),
        avatar_url="",
        provedor_auth_sub=f"credentials:{email_limpo}",
        ativo=True,
    )
    db.add(novo_user)
    db.flush()

    m_novo = Membership(
        tenant_id=tid_alvo,
        user_id=novo_user.id,
        papel=papel.value,
        ebt_restrita_id=ebt_restrita,
        ativo=True,
    )
    db.add(m_novo)
    db.flush()

    registrar_evento_auditoria(
        db,
        tenant_id=membership_admin.tenant_id,
        user_id=membership_admin.user_id,
        acao="admin.criar_usuario_rbac",
        entidade_tipo="User",
        entidade_id=novo_user.id,
        resumo=(
            f"Admin criou usuário '{novo_user.email}' com papel '{m_novo.papel}' "
            f"e plano '{plano.value}'."
        ),
    )

    return {
        "membership_id": m_novo.id,
        "user_id": novo_user.id,
        "email": novo_user.email,
        "nome_completo": novo_user.nome_completo,
        "papel": m_novo.papel,
        "ativo": novo_user.ativo and m_novo.ativo,
        "plano_codigo": plano.value,
    }


def atualizar_meu_perfil_usuario(
    db: Session,
    *,
    user: User,
    membership_ativa: Membership,
    nome_completo: Optional[str] = None,
    email: Optional[str] = None,
    telefone_whatsapp: Optional[str] = None,
    cargo_organizacao: Optional[str] = None,
    avatar_url: Optional[str] = None,
    senha_atual: Optional[str] = None,
    nova_senha: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Atualiza os dados cadastrais da aba 'Meu Perfil' (Nome Completo, E-mail,
    Telefone/WhatsApp, Cargo/Organização, Foto de Perfil / Avatar) e opcionalmente
    altera a senha após validar a `senha_atual`.
    """
    db.info["bypass_rls"] = True

    if nome_completo is not None:
        if not nome_completo.strip():
            raise ValueError("O Nome Completo não pode ficar em branco.")
        user.nome_completo = nome_completo.strip()

    if email is not None and email.strip().lower() != user.email:
        novo_email = email.strip().lower()
        if "@" not in novo_email:
            raise ValueError("Informe um endereço de e-mail válido.")
        conflito = (
            db.query(User)
            .filter(User.email == novo_email, User.id != user.id)
            .first()
        )
        if conflito is not None:
            raise ValueError("Este e-mail já está em uso por outro usuário.")
        user.email = novo_email

    if telefone_whatsapp is not None:
        user.telefone_whatsapp = telefone_whatsapp.strip()

    if cargo_organizacao is not None:
        user.cargo_organizacao = cargo_organizacao.strip()

    if avatar_url is not None:
        user.avatar_url = avatar_url.strip()

    if nova_senha is not None and nova_senha.strip() != "":
        if not senha_atual:
            raise ErroAutenticacaoOAuth(
                "Para alterar a senha, informe a sua senha atual."
            )
        if user.senha_hash and not verificar_senha_hash(senha_atual, user.senha_hash):
            raise ErroAutenticacaoOAuth(
                "A senha atual informada está incorreta."
            )
        if len(nova_senha) < 6:
            raise ValueError("A nova senha deve ter pelo menos 6 caracteres.")
        user.senha_hash = gerar_hash_senha(nova_senha)

    db.flush()

    registrar_evento_auditoria(
        db,
        tenant_id=membership_ativa.tenant_id,
        user_id=user.id,
        acao="usuario.atualizar_meu_perfil",
        entidade_tipo="User",
        entidade_id=user.id,
        resumo=f"Usuário '{user.email}' atualizou os dados cadastrais em 'Meu Perfil'.",
    )

    return construir_resposta_sessao_autenticada(
        db,
        user=user,
        membership_ativa=membership_ativa,
        provedor_oauth="credentials",
    )


def construir_resposta_sessao_autenticada(
    db: Session,
    *,
    user: User,
    membership_ativa: Membership,
    provedor_oauth: str = "oauth-local",
) -> Dict[str, Any]:
    """
    Monta o payload padronizado de sessão autenticada com JWT, Tenant, Plano,
    Dados Completos do Perfil e Permissões RBAC.
    """
    db.info["bypass_rls"] = True

    tenant = db.get(Tenant, membership_ativa.tenant_id)
    assinatura = (
        db.query(AssinaturaTenant)
        .filter(AssinaturaTenant.tenant_id == membership_ativa.tenant_id)
        .first()
    )

    eh_admin = membership_ativa.papel in (
        PapelMembro.ADMIN.value,
        PapelMembro.DONO.value,
    )

    if eh_admin:
        todas_memberships = (
            db.query(Membership)
            .join(User, User.id == Membership.user_id)
            .filter(
                Membership.ativo.is_(True),
                User.ativo.is_(True),
            )
            .order_by(Membership.criado_em.asc())
            .all()
        )
    else:
        todas_memberships = (
            db.query(Membership)
            .join(User, User.id == Membership.user_id)
            .filter(
                Membership.user_id == user.id,
                Membership.ativo.is_(True),
                User.ativo.is_(True),
            )
            .order_by(Membership.criado_em.asc())
            .all()
        )

    perfis_disponiveis = []
    for m in todas_memberships:
        u_m = db.get(User, m.user_id)
        if u_m is None:
            continue
        t_m = db.get(Tenant, m.tenant_id)
        ass_m = (
            db.query(AssinaturaTenant)
            .filter(AssinaturaTenant.tenant_id == m.tenant_id)
            .first()
        )
        perfis_disponiveis.append(
            {
                "membership_id": m.id,
                "user_id": m.user_id,
                "tenant_id": m.tenant_id,
                "tenant_nome": t_m.nome if t_m else "Tenant",
                "plano_codigo": ass_m.plano_codigo if ass_m else "free",
                "email": u_m.email,
                "nome": u_m.nome_completo,
                "provedor_oauth": (u_m.provedor_auth_sub or "credentials").split(
                    ":", 1
                )[0],
                "papel": m.papel,
                "ativo": bool(u_m.ativo and m.ativo),
                "ebt_restrita_id": m.ebt_restrita_id,
            }
        )

    papel_enum = PapelMembro(membership_ativa.papel)
    permissoes_ativas = sorted(
        p.value for p in MATRIZ_PERMISSOES_RBAC.get(papel_enum, set())
    )

    access_token = gerar_jwt_sessao_saas(
        user_id=user.id,
        email=user.email,
        nome=user.nome_completo,
        tenant_id=membership_ativa.tenant_id,
        membership_id=membership_ativa.id,
        papel=membership_ativa.papel,
        ebt_restrita_id=membership_ativa.ebt_restrita_id,
        provedor_oauth=provedor_oauth,
    )

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "nome_completo": user.nome_completo,
            "telefone_whatsapp": getattr(user, "telefone_whatsapp", "") or "",
            "cargo_organizacao": getattr(user, "cargo_organizacao", "") or "",
            "avatar_url": getattr(user, "avatar_url", "") or "",
            "ativo": bool(user.ativo),
            "provedor_auth": provedor_oauth,
            "provedor_auth_sub": user.provedor_auth_sub,
        },
        "tenant": {
            "id": tenant.id if tenant else membership_ativa.tenant_id,
            "nome": tenant.nome if tenant else "Consultoria",
            "slug": tenant.slug if tenant else "default",
            "plano_codigo": assinatura.plano_codigo if assinatura else "free",
            "limite_ebts": assinatura.limite_ebts if assinatura else 1,
            "limite_analises_ia_mes": assinatura.limite_analises_ia_mes if assinatura else 1,
            "limite_pdfs_mes": assinatura.limite_pdfs_mes if assinatura else 1,
            "permite_monte_carlo": bool(
                assinatura.permite_monte_carlo if assinatura else False
            ),
            "permite_white_label": bool(
                assinatura.permite_white_label if assinatura else False
            ),
        },
        "membership_ativa": {
            "id": membership_ativa.id,
            "papel": membership_ativa.papel,
            "ativo": bool(membership_ativa.ativo),
            "ebt_restrita_id": membership_ativa.ebt_restrita_id,
            "permissoes": permissoes_ativas,
        },
        "perfis_rbac_tenant": perfis_disponiveis,
    }


def listar_usuarios_oauth_registrados(
    db: Session, *, incluir_todos: bool = False
) -> List[Dict[str, Any]]:
    """
    Lista os usuários cadastrados no banco de dados com seus respectivos
    Tenants, Planos, Status (Ativo/Inativo) e Papéis RBAC para o Painel Admin.
    """
    db.info["bypass_rls"] = True
    query_users = db.query(User)
    if not incluir_todos:
        query_users = query_users.filter(User.provedor_auth_sub.isnot(None))
    usuarios = query_users.order_by(User.criado_em.asc()).all()

    resultado: List[Dict[str, Any]] = []
    for u in usuarios:
        memberships = (
            db.query(Membership).filter(Membership.user_id == u.id).all()
        )
        for m in memberships:
            t = db.get(Tenant, m.tenant_id)
            ass = (
                db.query(AssinaturaTenant)
                .filter(AssinaturaTenant.tenant_id == m.tenant_id)
                .first()
            )
            ebts_tenant = (
                db.query(ClienteEBT)
                .filter(ClienteEBT.tenant_id == m.tenant_id, ClienteEBT.ativo.is_(True))
                .all()
            )
            resultado.append(
                {
                    "user_id": u.id,
                    "membership_id": m.id,
                    "email": u.email,
                    "nome_completo": u.nome_completo,
                    "telefone_whatsapp": getattr(u, "telefone_whatsapp", "") or "",
                    "cargo_organizacao": getattr(u, "cargo_organizacao", "") or "",
                    "avatar_url": getattr(u, "avatar_url", "") or "",
                    "ativo": bool(u.ativo and m.ativo),
                    "provedor_auth_sub": u.provedor_auth_sub,
                    "provedor": (u.provedor_auth_sub or "credentials").split(":", 1)[0],
                    "papel": m.papel,
                    "ebt_restrita_id": m.ebt_restrita_id,
                    "tenant_id": m.tenant_id,
                    "tenant_nome": t.nome if t else "Workspace",
                    "tenant_slug": t.slug if t else "workspace",
                    "plano_codigo": ass.plano_codigo if ass else "free",
                    "ebts_disponiveis": [
                        {"id": e.id, "nome_startup": e.nome_startup}
                        for e in ebts_tenant
                    ],
                    "criado_em": u.criado_em.isoformat() if u.criado_em else None,
                }
            )
    return resultado


def gerenciar_assinante_oauth_pelo_admin(
    db: Session,
    *,
    membership_admin: Membership,
    membership_alvo_id: str,
    novo_papel: Optional[PapelMembro] = None,
    novo_plano: Optional[PlanoAssinaturaCodigo] = None,
    ebt_restrita_id: Optional[str] = None,
    ativo: Optional[bool] = None,
    nome_completo: Optional[str] = None,
    cargo_organizacao: Optional[str] = None,
    telefone_whatsapp: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Exclusivo para o Administrador (`admin` / `dono`):
    Gerencia o Papel/Role RBAC (`ADMIN`, `GESTOR`, `ANALISTA`, `ASSINANTE_FREE`,
    `ASSINANTE_PRO`, `CONSULTOR`, `FUNDADOR`, `INVESTIDOR`), Status (`Ativo`/`Inativo`)
    e Plano de Assinatura de qualquer usuário no Painel Admin RBAC.

    Restrição de Segurança Obrigatória:
    Impede que o administrador remova seu próprio papel de administrador ou inative
    a própria conta por engano.
    """
    db.info["bypass_rls"] = True

    if membership_admin.papel not in (
        PapelMembro.ADMIN.value,
        PapelMembro.DONO.value,
    ):
        raise ErroPermissaoRBAC(
            "Apenas o Administrador (ADMIN) possui permissão para gerenciar usuários e perfis RBAC."
        )

    m_alvo = db.get(Membership, membership_alvo_id)
    if m_alvo is None:
        raise LookupError("Vínculo (Membership) do usuário não encontrado.")

    user_alvo = db.get(User, m_alvo.user_id)
    if user_alvo is None:
        raise LookupError("Usuário não encontrado.")

    # Restrição de segurança: impedir que o administrador remova seu próprio papel ADMIN ou se desative
    eh_proprio_admin = (
        m_alvo.id == membership_admin.id
        or m_alvo.user_id == membership_admin.user_id
    )
    if eh_proprio_admin:
        if novo_papel is not None and novo_papel not in (
            PapelMembro.ADMIN,
            PapelMembro.DONO,
        ):
            raise ErroPermissaoRBAC(
                "Restrição de segurança: você não pode remover seu próprio papel de Administrador (ADMIN)."
            )
        if ativo is False:
            raise ErroPermissaoRBAC(
                "Restrição de segurança: você não pode inativar sua própria conta de Administrador."
            )

    plano_anterior = None
    papel_anterior = m_alvo.papel
    status_anterior = bool(user_alvo.ativo and m_alvo.ativo)

    if nome_completo is not None and nome_completo.strip():
        user_alvo.nome_completo = nome_completo.strip()
    if cargo_organizacao is not None:
        user_alvo.cargo_organizacao = cargo_organizacao.strip()
    if telefone_whatsapp is not None:
        user_alvo.telefone_whatsapp = telefone_whatsapp.strip()

    if ativo is not None:
        user_alvo.ativo = bool(ativo)
        m_alvo.ativo = bool(ativo)

    if novo_papel is not None:
        m_alvo.papel = novo_papel.value
        if novo_papel in (PapelMembro.FUNDADOR, PapelMembro.INVESTIDOR):
            if ebt_restrita_id:
                m_alvo.ebt_restrita_id = ebt_restrita_id
            elif not m_alvo.ebt_restrita_id:
                primeira_ebt = (
                    db.query(ClienteEBT)
                    .filter(
                        ClienteEBT.tenant_id == m_alvo.tenant_id,
                        ClienteEBT.ativo.is_(True),
                    )
                    .first()
                )
                if primeira_ebt:
                    m_alvo.ebt_restrita_id = primeira_ebt.id
        else:
            m_alvo.ebt_restrita_id = None

        # Sincroniza plano automaticamente quando o papel selecionado é ASSINANTE_FREE ou ASSINANTE_PRO
        if novo_plano is None:
            if novo_papel == PapelMembro.ASSINANTE_FREE:
                novo_plano = PlanoAssinaturaCodigo.FREE
            elif novo_papel == PapelMembro.ASSINANTE_PRO:
                novo_plano = PlanoAssinaturaCodigo.PRO

    ass = (
        db.query(AssinaturaTenant)
        .filter(AssinaturaTenant.tenant_id == m_alvo.tenant_id)
        .first()
    )
    if novo_plano is not None:
        limites = CONFIG_LIMITES_POR_PLANO[novo_plano]
        if ass is None:
            ass = _instanciar_assinatura_tenant(m_alvo.tenant_id, novo_plano)
            db.add(ass)
        else:
            plano_anterior = ass.plano_codigo
            ass.plano_codigo = novo_plano.value
            ass.limite_ebts = int(limites["limite_ebts"])
            ass.limite_cenarios_por_ebt = int(limites["limite_cenarios_por_ebt"])
            ass.limite_analises_ia_mes = int(limites["limite_analises_ia_mes"])
            ass.limite_pdfs_mes = int(limites["limite_pdfs_mes"])
            ass.permite_monte_carlo = bool(limites["permite_monte_carlo"])
            ass.permite_white_label = bool(limites["permite_white_label"])

    db.flush()

    registrar_evento_auditoria(
        db,
        tenant_id=m_alvo.tenant_id,
        user_id=membership_admin.user_id,
        acao="admin.gerenciar_assinante_oauth",
        entidade_tipo="Membership",
        entidade_id=m_alvo.id,
        resumo=(
            f"Admin atualizou usuário '{user_alvo.email}': "
            f"papel '{papel_anterior}' -> '{m_alvo.papel}', "
            f"status '{status_anterior}' -> '{bool(user_alvo.ativo and m_alvo.ativo)}', "
            f"plano '{plano_anterior or (ass.plano_codigo if ass else 'free')}' -> "
            f"'{ass.plano_codigo if ass else 'free'}'."
        ),
        dados_anteriores={
            "papel": papel_anterior,
            "plano": plano_anterior,
            "ativo": status_anterior,
        },
        dados_novos={
            "papel": m_alvo.papel,
            "plano": ass.plano_codigo if ass else "free",
            "ativo": bool(user_alvo.ativo and m_alvo.ativo),
            "ebt_restrita_id": m_alvo.ebt_restrita_id,
        },
    )

    return {
        "membership_id": m_alvo.id,
        "user_id": user_alvo.id,
        "email": user_alvo.email,
        "nome_completo": user_alvo.nome_completo,
        "papel": m_alvo.papel,
        "ativo": bool(user_alvo.ativo and m_alvo.ativo),
        "ebt_restrita_id": m_alvo.ebt_restrita_id,
        "tenant_id": m_alvo.tenant_id,
        "plano_codigo": ass.plano_codigo if ass else "free",
    }
