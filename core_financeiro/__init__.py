"""
Pacote puro do Motor Financeiro Master Management (Fase 0 SaaS).
Sem dependências de Streamlit ou SQLAlchemy.
"""

from .calculadora import (
    executar_simulacao_saas,
    simular_cenarios_padrao,
    simular_monte_carlo,
)
from .sanidade import contar_mudancas_sinal, validar_sanidade_simulacao
from .schemas import (
    VERSAO_MOTOR,
    AlertaSanidade,
    DREBaseMensal,
    EntradaSimulacaoSaaS,
    ItemCapexInput,
    ItemOpexInput,
    MetricasUnitEconomics,
    MetricasViabilidade,
    PlanoSaaSInput,
    PremissasInput,
    ResultadoComparacaoCenarios,
    ResultadoMonteCarlo,
    ResultadoSimulacaoSaaS,
    SerieTemporalSimulacao,
    SeveridadeAlerta,
    TipoCenario,
)

__all__ = [
    "VERSAO_MOTOR",
    "AlertaSanidade",
    "DREBaseMensal",
    "EntradaSimulacaoSaaS",
    "ItemCapexInput",
    "ItemOpexInput",
    "MetricasUnitEconomics",
    "MetricasViabilidade",
    "PlanoSaaSInput",
    "PremissasInput",
    "ResultadoComparacaoCenarios",
    "ResultadoMonteCarlo",
    "ResultadoSimulacaoSaaS",
    "SerieTemporalSimulacao",
    "SeveridadeAlerta",
    "TipoCenario",
    "contar_mudancas_sinal",
    "executar_simulacao_saas",
    "simular_cenarios_padrao",
    "simular_monte_carlo",
    "validar_sanidade_simulacao",
]
