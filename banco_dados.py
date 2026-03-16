from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

class ProjetoDB(Base):
    __tablename__ = 'projetos'
    id = Column(Integer, primary_key=True)
    nome_empresa = Column(String)
    
    canvas = relationship("CanvasDB", back_populates="projeto", uselist=False, cascade="all, delete-orphan")
    premissas = relationship("PremissasFinanceirasDB", back_populates="projeto", uselist=False, cascade="all, delete-orphan")
    investimentos = relationship("InvestimentoDB", back_populates="projeto", cascade="all, delete-orphan")
    custos_fixos = relationship("CustoFixoDB", back_populates="projeto", cascade="all, delete-orphan")
    produtos = relationship("ProdutoDB", back_populates="projeto", cascade="all, delete-orphan")

class CanvasDB(Base):
    __tablename__ = 'canvas'
    id = Column(Integer, primary_key=True)
    projeto_id = Column(Integer, ForeignKey('projetos.id'))
    
    parceiros, processos, recursos = Column(Text, default=""), Column(Text, default=""), Column(Text, default="")
    proposta_valor, atendimento, canais = Column(Text, default=""), Column(Text, default=""), Column(Text, default="")
    segmentos, estrutura_custos, fontes_receita = Column(Text, default=""), Column(Text, default=""), Column(Text, default="")
    
    projeto = relationship("ProjetoDB", back_populates="canvas")

class PremissasFinanceirasDB(Base):
    __tablename__ = 'premissas_financeiras'
    id = Column(Integer, primary_key=True)
    projeto_id = Column(Integer, ForeignKey('projetos.id'))
    
    horizonte_anos = Column(Integer, default=5)
    tma_anual_pct = Column(Float, default=15.0)
    crescimento_vendas_ano_pct = Column(Float, default=10.0)
    inflacao_custos_ano_pct = Column(Float, default=5.0)
    
    # Sazonalidade (Base 100%)
    saz_m1 = Column(Float, default=100.0)
    saz_m2 = Column(Float, default=100.0)
    saz_m3 = Column(Float, default=100.0)
    saz_m4 = Column(Float, default=100.0)
    saz_m5 = Column(Float, default=100.0)
    saz_m6 = Column(Float, default=100.0)
    saz_m7 = Column(Float, default=100.0)
    saz_m8 = Column(Float, default=100.0)
    saz_m9 = Column(Float, default=100.0)
    saz_m10 = Column(Float, default=100.0)
    saz_m11 = Column(Float, default=100.0)
    saz_m12 = Column(Float, default=100.0)
    
    projeto = relationship("ProjetoDB", back_populates="premissas")

class InvestimentoDB(Base):
    __tablename__ = 'investimentos'
    id = Column(Integer, primary_key=True)
    projeto_id = Column(Integer, ForeignKey('projetos.id'))
    categoria, descricao = Column(String), Column(String)
    valor = Column(Float, default=0.0)
    projeto = relationship("ProjetoDB", back_populates="investimentos")

class CustoFixoDB(Base):
    __tablename__ = 'custos_fixos'
    id = Column(Integer, primary_key=True)
    projeto_id = Column(Integer, ForeignKey('projetos.id'))
    categoria, descricao = Column(String), Column(String)
    valor_mensal = Column(Float, default=0.0)
    projeto = relationship("ProjetoDB", back_populates="custos_fixos")

class ProdutoDB(Base):
    __tablename__ = 'produtos'
    id = Column(Integer, primary_key=True)
    projeto_id = Column(Integer, ForeignKey('projetos.id'))
    nome_produto = Column(String)
    estimativa_vendas_mes = Column(Integer, default=0)
    custo_insumos, impostos_pct, taxas_pct, comissoes_pct = Column(Float, default=0.0), Column(Float, default=0.0), Column(Float, default=0.0), Column(Float, default=0.0)
    margem_lucro_pct, preco_venda_sugerido = Column(Float, default=0.0), Column(Float, default=0.0)
    projeto = relationship("ProjetoDB", back_populates="produtos")

engine = create_engine('sqlite:///meu_plano.db', echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()