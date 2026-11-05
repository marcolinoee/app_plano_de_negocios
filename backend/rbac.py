"""
Controle de Acesso Baseado em Papéis (RBAC) e Escopo por Workspace (EBT).
Garante que:
- Dono e Admin gerenciam a consultoria (Tenant) e todas as EBTs.
- Consultor cria/edita EBTs, aprova pareceres de IA e gera dossiês PDF.
- Analista edita diagnósticos e executa simulações financeiras.
- Fundador/Cliente edita exclusivamente o seu próprio workspace (ebt_restrita_id).
- Investidor/Banca possui acesso estritamente somente leitura.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Optional, Set

from .models import Membership, PapelMembro


class ErroPermissaoRBAC(PermissionError):
    """Exceção disparada quando o papel ou escopo do usuário não permite a operação."""


class PermissaoSaaS(str, Enum):
    TENANT_GERENCIAR_COBRANCA = "tenant:gerenciar_cobranca"
    TENANT_CONVIDAR_MEMBROS = "tenant:convidar_membros"
    EBT_CRIAR = "ebt:criar"
    EBT_EXCLUIR = "ebt:excluir"
    EBT_VISUALIZAR = "ebt:visualizar"
    EBT_EDITAR_DIAGNOSTICO = "ebt:editar_diagnostico"
    SIMULACAO_EXECUTAR = "simulacao:executar"
    IA_SOLICITAR_PARECER = "ia:solicitar_parecer"
    IA_APROVAR_PARECER = "ia:aprovar_parecer"
    DOSSIE_EXPORTAR_PDF = "dossie:exportar_pdf"
    SHARE_LINK_CRIAR = "share_link:criar"
    AUDITORIA_VISUALIZAR = "auditoria:visualizar"


MATRIZ_PERMISSOES_RBAC: Dict[PapelMembro, Set[PermissaoSaaS]] = {
    PapelMembro.DONO: set(PermissaoSaaS),
    PapelMembro.ADMIN: set(PermissaoSaaS),
    PapelMembro.GESTOR: {
        PermissaoSaaS.TENANT_CONVIDAR_MEMBROS,
        PermissaoSaaS.EBT_CRIAR,
        PermissaoSaaS.EBT_EXCLUIR,
        PermissaoSaaS.EBT_VISUALIZAR,
        PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO,
        PermissaoSaaS.SIMULACAO_EXECUTAR,
        PermissaoSaaS.IA_SOLICITAR_PARECER,
        PermissaoSaaS.IA_APROVAR_PARECER,
        PermissaoSaaS.DOSSIE_EXPORTAR_PDF,
        PermissaoSaaS.SHARE_LINK_CRIAR,
        PermissaoSaaS.AUDITORIA_VISUALIZAR,
    },
    PapelMembro.CONSULTOR: {
        PermissaoSaaS.EBT_CRIAR,
        PermissaoSaaS.EBT_VISUALIZAR,
        PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO,
        PermissaoSaaS.SIMULACAO_EXECUTAR,
        PermissaoSaaS.IA_SOLICITAR_PARECER,
        PermissaoSaaS.IA_APROVAR_PARECER,
        PermissaoSaaS.DOSSIE_EXPORTAR_PDF,
        PermissaoSaaS.SHARE_LINK_CRIAR,
    },
    PapelMembro.ASSINANTE_PRO: {
        PermissaoSaaS.EBT_CRIAR,
        PermissaoSaaS.EBT_VISUALIZAR,
        PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO,
        PermissaoSaaS.SIMULACAO_EXECUTAR,
        PermissaoSaaS.IA_SOLICITAR_PARECER,
        PermissaoSaaS.IA_APROVAR_PARECER,
        PermissaoSaaS.DOSSIE_EXPORTAR_PDF,
        PermissaoSaaS.SHARE_LINK_CRIAR,
    },
    PapelMembro.ASSINANTE_FREE: {
        PermissaoSaaS.EBT_CRIAR,
        PermissaoSaaS.EBT_VISUALIZAR,
        PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO,
        PermissaoSaaS.SIMULACAO_EXECUTAR,
        PermissaoSaaS.IA_SOLICITAR_PARECER,
        PermissaoSaaS.DOSSIE_EXPORTAR_PDF,
    },
    PapelMembro.ANALISTA: {
        PermissaoSaaS.EBT_VISUALIZAR,
        PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO,
        PermissaoSaaS.SIMULACAO_EXECUTAR,
        PermissaoSaaS.IA_SOLICITAR_PARECER,
    },
    PapelMembro.FUNDADOR: {
        PermissaoSaaS.EBT_VISUALIZAR,
        PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO,
        PermissaoSaaS.SIMULACAO_EXECUTAR,
    },
    PapelMembro.INVESTIDOR: {
        PermissaoSaaS.EBT_VISUALIZAR,
    },
}


def verificar_permissao_rbac(
    membership: Optional[Membership],
    permissao: PermissaoSaaS,
    ebt_alvo_id: Optional[str] = None,
) -> None:
    """
    Valida se o vínculo (`Membership`) está ativo, possui a permissão exigida
    e, no caso de papéis restritos a workspace (`fundador` ou `investidor`),
    se o `ebt_alvo_id` corresponde exatamente ao `ebt_restrita_id`.
    """
    if membership is None or not membership.ativo:
        raise ErroPermissaoRBAC("Usuário não possui vínculo ativo neste Tenant.")

    try:
        papel_enum = PapelMembro(membership.papel)
    except ValueError as exc:
        raise ErroPermissaoRBAC(f"Papel inválido configurado no vínculo: {membership.papel}") from exc

    permissoes_do_papel = MATRIZ_PERMISSOES_RBAC.get(papel_enum, set())
    if permissao not in permissoes_do_papel:
        raise ErroPermissaoRBAC(
            f"O papel '{papel_enum.value}' não possui a permissão '{permissao.value}'."
        )

    # Restrição de escopo de workspace para Fundador e Investidor
    if papel_enum in (PapelMembro.FUNDADOR, PapelMembro.INVESTIDOR):
        if not membership.ebt_restrita_id:
            raise ErroPermissaoRBAC(
                f"O papel '{papel_enum.value}' exige um workspace EBT vinculado (ebt_restrita_id)."
            )
        if ebt_alvo_id is not None and membership.ebt_restrita_id != ebt_alvo_id:
            raise ErroPermissaoRBAC(
                f"Acesso negado: o usuário com papel '{papel_enum.value}' está restrito "
                f"exclusivamente ao workspace EBT '{membership.ebt_restrita_id}'."
            )
