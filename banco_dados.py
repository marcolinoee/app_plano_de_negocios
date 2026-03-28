from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Text, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# ==========================================
# 🛡️ GATILHO DE INTEGRIDADE SQLITE
# ==========================================
# Força o SQLite a respeitar a exclusão em cascata (Foreign Keys)
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

Base = declarative_base()

# ==========================================
# TABELAS DO BANCO DE DADOS
# ==========================================
class ProjetoDB(Base):
    __tablename__ = 'projetos'
    id = Column(Integer, primary_key=True)
    nome_empresa = Column(String)
    
    # O cascade="all, delete-orphan" gerencia a exclusão na camada do Python
    canvas = relationship("CanvasDB", back_populates="projeto", uselist=False, cascade="all, delete-orphan")
    premissas = relationship("PremissasFinanceirasDB", back_populates="projeto", uselist=False, cascade="all, delete-orphan")
    investimentos = relationship("InvestimentoDB", back_populates="projeto", cascade="all, delete-orphan")
    custos_fixos = relationship("CustoFixoDB", back_populates="projeto", cascade="all, delete-orphan")
    produtos = relationship("ProdutoDB", back_populates="projeto", cascade="all, delete-orphan")

class CanvasDB(Base):
    __tablename__ = 'canvas'
    # ondelete="CASCADE" garante a exclusão na camada física do Banco de Dados
    id = Column(Integer, primary_key=True)
    projeto_id = Column(Integer, ForeignKey('projetos.id', ondelete="CASCADE"))
    
    parceiros, processos, recursos = Column(Text, default=""), Column(Text, default=""), Column(Text, default="")
    proposta_valor, atendimento, canais = Column(Text, default=""), Column(Text, default=""), Column(Text, default="")
    segmentos, estrutura_custos, fontes_receita = Column(Text, default=""), Column(Text, default=""), Column(Text, default="")
    
    projeto = relationship("ProjetoDB", back_populates="canvas")

class PremissasFinanceirasDB(Base):
    __tablename__ = 'premissas_financeiras'
    id = Column(Integer, primary_key=True)
    projeto_id = Column(Integer, ForeignKey('projetos.id', ondelete="CASCADE"))
    
    horizonte_anos = Column(Integer, default=5)
    tma_anual_pct = Column(Float, default=15.0)
    crescimento_vendas_ano_pct = Column(Float, default=10.0)
    inflacao_custos_ano_pct = Column(Float, default=5.0)
    
    saz_m1, saz_m2, saz_m3 = Column(Float, default=100.0), Column(Float, default=100.0), Column(Float, default=100.0)
    saz_m4, saz_m5, saz_m6 = Column(Float, default=100.0), Column(Float, default=100.0), Column(Float, default=100.0)
    saz_m7, saz_m8, saz_m9 = Column(Float, default=100.0), Column(Float, default=100.0), Column(Float, default=100.0)
    saz_m10, saz_m11, saz_m12 = Column(Float, default=100.0), Column(Float, default=100.0), Column(Float, default=100.0)
    
    projeto = relationship("ProjetoDB", back_populates="premissas")

class InvestimentoDB(Base):
    __tablename__ = 'investimentos'
    id = Column(Integer, primary_key=True)
    projeto_id = Column(Integer, ForeignKey('projetos.id', ondelete="CASCADE"))
    categoria, descricao = Column(String), Column(String)
    valor = Column(Float, default=0.0)
    
    projeto = relationship("ProjetoDB", back_populates="investimentos")

class CustoFixoDB(Base):
    __tablename__ = 'custos_fixos'
    id = Column(Integer, primary_key=True)
    projeto_id = Column(Integer, ForeignKey('projetos.id', ondelete="CASCADE"))
    categoria, descricao = Column(String), Column(String)
    valor_mensal = Column(Float, default=0.0)
    
    projeto = relationship("ProjetoDB", back_populates="custos_fixos")

class ProdutoDB(Base):
    __tablename__ = 'produtos'
    id = Column(Integer, primary_key=True)
    projeto_id = Column(Integer, ForeignKey('projetos.id', ondelete="CASCADE"))
    nome_produto = Column(String)
    estimativa_vendas_mes = Column(Integer, default=0)
    custo_insumos, impostos_pct = Column(Float, default=0.0), Column(Float, default=0.0)
    taxas_pct, comissoes_pct = Column(Float, default=0.0), Column(Float, default=0.0)
    margem_lucro_pct, preco_venda_sugerido = Column(Float, default=0.0), Column(Float, default=0.0)
    
    projeto = relationship("ProjetoDB", back_populates="produtos")

# ==========================================
# INICIALIZAÇÃO DA SESSÃO
# ==========================================
engine = create_engine('sqlite:///meu_plano.db', echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()