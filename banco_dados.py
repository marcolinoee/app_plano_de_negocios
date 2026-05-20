import os
import platform
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Text, Boolean, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# ==========================================
# 🛡️ INTEGRIDADE SQLITE (FK ON)
# ==========================================
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

Base = declarative_base()

# ==========================================
# TABELAS DO BANCO DE DADOS — V8.0 (TIC EDITION)
# ==========================================

class ProjetoDB(Base):
    __tablename__ = 'projetos'
    id            = Column(Integer, primary_key=True)
    nome_startup  = Column(String)

    lean_canvas   = relationship("LeanCanvasDB",      back_populates="projeto", uselist=False, cascade="all, delete-orphan")
    premissas     = relationship("PremissasStartupDB", back_populates="projeto", uselist=False, cascade="all, delete-orphan")
    investimentos = relationship("InvestimentoDB",     back_populates="projeto", cascade="all, delete-orphan")
    custos_fixos  = relationship("CustoFixoDB",        back_populates="projeto", cascade="all, delete-orphan")
    planos_saas   = relationship("PlanoSaaSDB",        back_populates="projeto", cascade="all, delete-orphan")
    juridico      = relationship("JuridicoDB",         back_populates="projeto", uselist=False, cascade="all, delete-orphan")
    quests        = relationship("QuestDB",            back_populates="projeto", cascade="all, delete-orphan")
    sprints       = relationship("RoadmapSprintDB",    back_populates="projeto", cascade="all, delete-orphan")


class LeanCanvasDB(Base):
    __tablename__ = 'lean_canvas'
    id                = Column(Integer, primary_key=True)
    projeto_id        = Column(Integer, ForeignKey('projetos.id', ondelete="CASCADE"))

    # Bloco estratégico principal
    problema          = Column(Text, default="")
    solucao_mvp       = Column(Text, default="")
    mvp_descricao     = Column(Text, default="")   # Prova de Conceito detalhada (Quest #6)
    metricas_chave    = Column(Text, default="")
    proposta_valor    = Column(Text, default="")
    vantagem_injusta  = Column(Text, default="")
    canais            = Column(Text, default="")
    segmentos         = Column(Text, default="")
    estrutura_custos  = Column(Text, default="")
    fontes_receita    = Column(Text, default="")
    ods_onu           = Column(Text, default="")   # Alinhamento ODS / Impacto Social

    projeto = relationship("ProjetoDB", back_populates="lean_canvas")


class PremissasStartupDB(Base):
    __tablename__ = 'premissas_startup'
    id                      = Column(Integer, primary_key=True)
    projeto_id              = Column(Integer, ForeignKey('projetos.id', ondelete="CASCADE"))

    horizonte_meses         = Column(Integer, default=36)   # Runway planejado
    tma_anual_pct           = Column(Float,   default=25.0) # TMA — risco alto = TMA alta
    cac_estimado            = Column(Float,   default=0.0)  # Custo de Aquisição de Cliente
    churn_mensal_pct        = Column(Float,   default=5.0)  # Taxa de Cancelamento Mensal
    conversao_freemium_pct  = Column(Float,   default=2.0)  # Freemium → Pago
    crescimento_mensal_pct  = Column(Float,   default=5.0)  # Crescimento de base mensal (MoM)
    usuarios_freemium_base  = Column(Integer, default=0)    # Usuários gratuitos na base

    projeto = relationship("ProjetoDB", back_populates="premissas")


class InvestimentoDB(Base):
    __tablename__ = 'investimentos'
    id         = Column(Integer, primary_key=True)
    projeto_id = Column(Integer, ForeignKey('projetos.id', ondelete="CASCADE"))
    categoria  = Column(String)
    descricao  = Column(String)
    valor      = Column(Float, default=0.0)

    projeto = relationship("ProjetoDB", back_populates="investimentos")


class CustoFixoDB(Base):
    __tablename__ = 'custos_fixos'
    id           = Column(Integer, primary_key=True)
    projeto_id   = Column(Integer, ForeignKey('projetos.id', ondelete="CASCADE"))
    categoria    = Column(String)
    descricao    = Column(String)
    valor_mensal = Column(Float, default=0.0)

    projeto = relationship("ProjetoDB", back_populates="custos_fixos")


class PlanoSaaSDB(Base):
    __tablename__ = 'planos_saas'
    id                      = Column(Integer, primary_key=True)
    projeto_id              = Column(Integer, ForeignKey('projetos.id', ondelete="CASCADE"))
    nome_plano              = Column(String)
    ticket_mensal           = Column(Float,   default=0.0)
    usuarios_ativos_base    = Column(Integer, default=0)
    taxas_pagamento_pct     = Column(Float,   default=5.0)  # Gateway / processadora
    impostos_pct            = Column(Float,   default=6.0)  # Simples Nacional / ISS
    custo_servidor_por_usuario = Column(Float, default=0.0) # COGS por usuário (nuvem/API)

    projeto = relationship("ProjetoDB", back_populates="planos_saas")


class JuridicoDB(Base):
    __tablename__ = 'juridico'
    id                   = Column(Integer, primary_key=True)
    projeto_id           = Column(Integer, ForeignKey('projetos.id', ondelete="CASCADE"))

    registro_inpi        = Column(String,  default="Não Iniciado")
    marca_status         = Column(String,  default="Não Iniciado")
    adequacao_lgpd       = Column(Boolean, default=False)
    contrato_vesting     = Column(Boolean, default=False)
    custo_estimado_legal = Column(Float,   default=0.0)

    projeto = relationship("ProjetoDB", back_populates="juridico")


class QuestDB(Base):
    """
    Rastreamento das 9 Quests do Plano de Ensino (40% da nota).
    Uma linha por Quest por Projeto.
    """
    __tablename__   = 'quests'
    id              = Column(Integer, primary_key=True)
    projeto_id      = Column(Integer, ForeignKey('projetos.id', ondelete="CASCADE"))
    numero_quest    = Column(Integer)                     # 1 – 9
    status          = Column(String, default="Pendente")  # Pendente | Em Progresso | Entregue
    nota            = Column(Float,  default=0.0)         # 0.0 – 10.0
    entrega_resumo  = Column(Text,   default="")          # Resumo da entrega
    observacoes     = Column(Text,   default="")          # Feedback do professor

    projeto = relationship("ProjetoDB", back_populates="quests")


class RoadmapSprintDB(Base):
    """
    Sprints de desenvolvimento rumo ao Demoday (12/06).
    """
    __tablename__  = 'roadmap_sprints'
    id             = Column(Integer, primary_key=True)
    projeto_id     = Column(Integer, ForeignKey('projetos.id', ondelete="CASCADE"))
    nome_sprint    = Column(String, default="")
    objetivo       = Column(Text,   default="")
    status         = Column(String, default="Backlog")  # Backlog | Em Andamento | Concluído
    semana_inicio  = Column(Integer, default=1)
    semana_fim     = Column(Integer, default=2)

    projeto = relationship("ProjetoDB", back_populates="sprints")


# ==========================================
# 📂 CAMINHO MULTIPLATAFORMA (Windows / macOS / Linux)
# ==========================================
def _get_app_data_path() -> str:
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif system == "Darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "MasterManagement8")


app_data_path = _get_app_data_path()
os.makedirs(app_data_path, exist_ok=True)
db_path = os.path.join(app_data_path, "startup_plan.db")

engine  = create_engine(f"sqlite:///{db_path}", echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()
