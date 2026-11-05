"""
Infraestrutura de Banco de Dados Multi-Tenant (Sessão por Requisição + RLS).
Implementa Defesa em Profundidade (Defense-in-Depth):
1. No PostgreSQL: configura `SET LOCAL app.current_tenant_id` na transação e provê
   o gerador DDL completo de Row-Level Security (ENABLE + FORCE RLS).
2. No SQLAlchemy ORM (PostgreSQL e SQLite): intercepta queries (`do_orm_execute`) e
   escritas (`before_flush`) na sessão quando `tenant_id` está ativo no contexto,
   bloqueando vazamento ou escrita cruzada entre tenants mesmo em bancos locais de teste.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, List, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker, with_loader_criteria
from sqlalchemy.pool import StaticPool

from .models import TABELAS_COM_RLS, BaseSaaS


class ErroIsolamentoTenant(PermissionError):
    """Exceção disparada quando uma operação viola o isolamento entre tenants."""


def criar_engine_saas(database_url: str, echo: bool = False) -> Engine:
    """Cria engine SQLAlchemy configurada para PostgreSQL ou SQLite (testes/dev)."""
    connect_args = {}
    kwargs_extra = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30
        if ":memory:" in database_url or database_url == "sqlite://":
            kwargs_extra["poolclass"] = StaticPool

    engine = create_engine(database_url, echo=echo, connect_args=connect_args, **kwargs_extra)

    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _ativar_fk_sqlite(dbapi_connection, connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    return engine


def criar_session_factory(engine: Engine) -> sessionmaker:
    """Retorna fábrica de sessões (uma sessão independente por requisição HTTP/job)."""
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    _registrar_hooks_isolamento_orm(factory)
    return factory


def _criar_criterio_tenant(cls, tenant_id: str):
    return with_loader_criteria(
        cls,
        lambda entidade: entidade.tenant_id == tenant_id,
        include_aliases=True,
    )


def _registrar_hooks_isolamento_orm(factory: sessionmaker) -> None:
    """
    Registra interceptadores na fábrica de sessões para impor filtro automático
    por `tenant_id` em leituras (SELECT) e validação estrita em escritas (INSERT/UPDATE).
    """

    @event.listens_for(factory, "do_orm_execute")
    def _filtrar_por_tenant_automaticamente(execute_state) -> None:
        tenant_id = execute_state.session.info.get("tenant_id")
        ignorar_rls = execute_state.session.info.get("bypass_rls", False)

        if not tenant_id or ignorar_rls:
            return

        if (
            execute_state.is_select
            and not execute_state.is_column_load
            and not execute_state.is_relationship_load
        ):
            opcoes = [
                _criar_criterio_tenant(mapper.class_, tenant_id)
                for mapper in BaseSaaS.registry.mappers
                if hasattr(mapper.class_, "tenant_id")
            ]
            if opcoes:
                execute_state.statement = execute_state.statement.options(*opcoes)

    @event.listens_for(factory, "before_flush")
    def _validar_escrita_tenant(session: Session, flush_context, instances) -> None:
        tenant_id_sessao = session.info.get("tenant_id")
        ignorar_rls = session.info.get("bypass_rls", False)

        if not tenant_id_sessao or ignorar_rls:
            return

        for obj in list(session.new) + list(session.dirty):
            if hasattr(obj, "tenant_id"):
                valor_atual = getattr(obj, "tenant_id", None)
                if valor_atual is None:
                    setattr(obj, "tenant_id", tenant_id_sessao)
                elif valor_atual != tenant_id_sessao:
                    raise ErroIsolamentoTenant(
                        f"Violação de RLS/Tenant: tentativa de gravar {obj.__class__.__name__} "
                        f"com tenant_id='{valor_atual}' em sessão do tenant '{tenant_id_sessao}'."
                    )


@contextmanager
def sessao_por_requisicao(
    session_factory: sessionmaker,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    bypass_rls: bool = False,
) -> Generator[Session, None, None]:
    """
    Gerenciador de contexto para ciclo de vida de sessão por requisição:
    1. Abre sessão isolada.
    2. Define `tenant_id` e `user_id` no contexto da sessão e no PostgreSQL (`SET LOCAL`).
    3. Faz commit ao final se não houver exceções, ou rollback automático em caso de erro.
    4. Fecha a sessão garantindo liberação da conexão no pool.
    """
    db: Session = session_factory()
    try:
        db.info["tenant_id"] = tenant_id
        db.info["user_id"] = user_id
        db.info["bypass_rls"] = bypass_rls

        if tenant_id and not bypass_rls and db.bind is not None:
            dialeto = db.bind.dialect.name
            if dialeto == "postgresql":
                db.execute(
                    text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                    {"tid": str(tenant_id)},
                )

        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def gerar_ddl_rls_postgresql(tabelas: Optional[List[str]] = None) -> str:
    """
    Gera o script SQL completo de Row-Level Security (RLS) para PostgreSQL.
    Aplica `ENABLE ROW LEVEL SECURITY` e `FORCE ROW LEVEL SECURITY` em todas
    as tabelas multi-tenant, garantindo que nenhuma linha seja lida ou escrita
    fora do `app.current_tenant_id`.
    """
    alvos = tabelas or TABELAS_COM_RLS
    comandos: List[str] = [
        "-- =============================================================================",
        "-- POLÍTICAS DE ROW-LEVEL SECURITY (RLS) — MASTER MANAGEMENT SAAS (POSTGRESQL)",
        "-- =============================================================================",
        "",
    ]

    for tabela in alvos:
        nome_policy = f"rls_isolamento_tenant_{tabela}"
        comandos.extend(
            [
                f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;",
                f"ALTER TABLE {tabela} FORCE ROW LEVEL SECURITY;",
                f"DROP POLICY IF EXISTS {nome_policy} ON {tabela};",
                (
                    f"CREATE POLICY {nome_policy} ON {tabela}\n"
                    f"    USING (tenant_id = current_setting('app.current_tenant_id', true))\n"
                    f"    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));"
                ),
                "",
            ]
        )

    return "\n".join(comandos)
