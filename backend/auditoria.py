"""
Serviço de Auditoria Obrigatória (AuditLog).
Registra quem alterou o quê, quando e em qual Tenant, garantindo rastreabilidade
para consultorias e conformidade com a LGPD.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .models import AuditLog


def registrar_evento_auditoria(
    db: Session,
    *,
    tenant_id: str,
    user_id: Optional[str],
    acao: str,
    entidade_tipo: str,
    entidade_id: str,
    resumo: str,
    dados_anteriores: Optional[Dict[str, Any]] = None,
    dados_novos: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """Cria e adiciona um registro imutável de auditoria na sessão atual."""
    evento = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        acao=acao,
        entidade_tipo=entidade_tipo,
        entidade_id=entidade_id,
        resumo=resumo,
        dados_anteriores_json=(
            json.dumps(dados_anteriores, ensure_ascii=False, sort_keys=True)
            if dados_anteriores is not None
            else None
        ),
        dados_novos_json=(
            json.dumps(dados_novos, ensure_ascii=False, sort_keys=True)
            if dados_novos is not None
            else None
        ),
    )
    db.add(evento)
    db.flush()
    return evento


def listar_trilha_auditoria(
    db: Session,
    *,
    entidade_id: Optional[str] = None,
    limite: int = 100,
) -> List[AuditLog]:
    """Retorna os logs de auditoria do Tenant atual ordenados do mais recente ao mais antigo."""
    query = db.query(AuditLog)
    if entidade_id:
        query = query.filter(AuditLog.entidade_id == entidade_id)
    return query.order_by(AuditLog.criado_em.desc()).limit(limite).all()
