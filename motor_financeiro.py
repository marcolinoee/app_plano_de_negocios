from dataclasses import dataclass, field
from typing import List

# --- ENTIDADES BÁSICAS ---

@dataclass
class ItemInvestimento:
    nome: str
    valor: float

@dataclass
class DespesaFixa:
    nome: str
    valor_mensal: float

@dataclass
class Insumo:
    nome: str
    custo_unitario: float
    quantidade_necessaria: float

    @property
    def custo_total(self) -> float:
        return self.custo_unitario * self.quantidade_necessaria

@dataclass
class Produto:
    nome: str
    insumos: List[Insumo] = field(default_factory=list)
    margem_lucro_desejada: float = 0.0  
    impostos_taxas: float = 0.0         
    comissoes: float = 0.0              

    @property
    def custo_variavel_unitario(self) -> float:
        return sum(insumo.custo_total for insumo in self.insumos)

    @property
    def preco_venda_sugerido(self) -> float:
        custo_total_venda = self.impostos_taxas + self.comissoes + self.margem_lucro_desejada
        markup_divisor = 1 - custo_total_venda
        if markup_divisor <= 0:
            return 0.0 # Evita erro matemático se as taxas passarem de 100%
        return self.custo_variavel_unitario / markup_divisor

@dataclass
class VendaProjetada:
    produto: Produto
    quantidade_mensal: int

    @property
    def receita_bruta_mensal(self) -> float:
        return self.produto.preco_venda_sugerido * self.quantidade_mensal

    @property
    def custo_variavel_total_mensal(self) -> float:
        return self.produto.custo_variavel_unitario * self.quantidade_mensal

# --- O MOTOR DE CÁLCULO ---

@dataclass
class ProjetoNegocio:
    nome_empresa: str
    investimentos: List[ItemInvestimento] = field(default_factory=list)
    despesas_fixas: List[DespesaFixa] = field(default_factory=list)
    vendas_projetadas: List[VendaProjetada] = field(default_factory=list)

    def total_investimento(self) -> float:
        return sum(item.valor for item in self.investimentos)

    def total_custo_fixo_mensal(self) -> float:
        return sum(despesa.valor_mensal for despesa in self.despesas_fixas)

    def gerar_dre_mensal(self) -> dict:
        """Calcula a Demonstração de Resultados do Exercício (DRE)"""
        receita_bruta = sum(v.receita_bruta_mensal for v in self.vendas_projetadas)
        custo_variavel_total = sum(v.custo_variavel_total_mensal for v in self.vendas_projetadas)
        
        # Calculando impostos e comissões sobre as vendas
        impostos_total = sum(v.receita_bruta_mensal * v.produto.impostos_taxas for v in self.vendas_projetadas)
        comissoes_total = sum(v.receita_bruta_mensal * v.produto.comissoes for v in self.vendas_projetadas)
        
        receita_liquida = receita_bruta - impostos_total
        margem_bruta = receita_liquida - custo_variavel_total
        margem_contribuicao = margem_bruta - comissoes_total
        
        custos_fixos = self.total_custo_fixo_mensal()
        lucro_liquido = margem_contribuicao - custos_fixos

        return {
            "1. Receita Bruta": receita_bruta,
            "2. Impostos": impostos_total,
            "3. Receita Líquida": receita_liquida,
            "4. Custos Variáveis (Produtos)": custo_variavel_total,
            "5. Margem Bruta": margem_bruta,
            "6. Comissões": comissoes_total,
            "7. Margem de Contribuição": margem_contribuicao,
            "8. Custos Fixos": custos_fixos,
            "9. Lucro Líquido": lucro_liquido
        }

    def calcular_viabilidade(self) -> dict:
        """Calcula ROI e Payback baseados no lucro mensal"""
        dre = self.gerar_dre_mensal()
        lucro_mensal = dre["9. Lucro Líquido"]
        investimento = self.total_investimento()

        if lucro_mensal <= 0:
            return {"ROI Mensal (%)": 0.0, "Payback (Meses)": "Negócio dando prejuízo"}

        roi = (lucro_mensal / investimento) * 100
        payback = investimento / lucro_mensal

        return {
            "ROI Mensal (%)": round(roi, 2),
            "Payback (Meses)": round(payback, 2)
        }