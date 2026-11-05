"""
Schemas Pydantic puros para entrada e saída do Motor Financeiro SaaS.
Sem dependências de interface (Streamlit) ou banco de dados (SQLAlchemy).
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

VERSAO_MOTOR = "2.0.0-saas"


class SeveridadeAlerta(str, Enum):
    INFO = "info"
    AVISO = "aviso"
    CRITICO = "critico"


class TipoCenario(str, Enum):
    BASE = "base"
    OTIMISTA = "otimista"
    PESSIMISTA = "pessimista"


class ItemCapexInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    categoria: str = Field(default="Geral", min_length=1)
    descricao: str = Field(default="", max_length=500)
    valor: float = Field(default=0.0, ge=0.0)


class ItemOpexInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    categoria: str = Field(default="Geral", min_length=1)
    descricao: str = Field(default="", max_length=500)
    valor_mensal: float = Field(default=0.0, ge=0.0)


class PlanoSaaSInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    nome_plano: str = Field(min_length=1)
    ticket_mensal: float = Field(default=0.0, ge=0.0)
    usuarios_ativos_base: int = Field(default=0, ge=0)
    taxas_pagamento_pct: float = Field(default=5.0, ge=0.0, le=100.0)
    impostos_pct: float = Field(default=6.0, ge=0.0, le=100.0)
    custo_servidor_por_usuario: float = Field(default=0.0, ge=0.0)

    @property
    def deducao_total_pct(self) -> float:
        return self.taxas_pagamento_pct + self.impostos_pct

    @property
    def mrr_bruto_plano(self) -> float:
        return self.ticket_mensal * self.usuarios_ativos_base

    @property
    def margem_bruta_plano(self) -> float:
        desconto_decimal = self.deducao_total_pct / 100.0
        receita_liquida = self.mrr_bruto_plano * (1.0 - desconto_decimal)
        cogs_plano = self.custo_servidor_por_usuario * self.usuarios_ativos_base
        return receita_liquida - cogs_plano


class PremissasInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    horizonte_meses: int = Field(default=36, ge=1, le=240)
    tma_anual_pct: float = Field(default=25.0, ge=-50.0, le=500.0)
    cac_estimado: float = Field(default=0.0, ge=0.0)
    churn_mensal_pct: float = Field(default=5.0, ge=0.0, le=100.0)
    conversao_freemium_pct: float = Field(default=2.0, ge=0.0, le=100.0)
    crescimento_mensal_pct: float = Field(default=5.0, ge=-90.0, le=500.0)
    usuarios_freemium_base: int = Field(default=0, ge=0)
    ciclo_caixa_meses: float = Field(
        default=1.0,
        ge=0.0,
        description="Ciclo médio de recebimento/caixa em meses para validação de payback",
    )


class EntradaSimulacaoSaaS(BaseModel):
    model_config = ConfigDict(frozen=True)

    nome_startup: str = Field(default="Startup TIC")
    premissas: PremissasInput = Field(default_factory=PremissasInput)
    investimentos: List[ItemCapexInput] = Field(default_factory=list)
    custos_fixos: List[ItemOpexInput] = Field(default_factory=list)
    planos_saas: List[PlanoSaaSInput] = Field(default_factory=list)
    custo_estimado_legal_mensal: float = Field(default=0.0, ge=0.0)

    @field_validator("nome_startup")
    @classmethod
    def limpar_nome(cls, v: str) -> str:
        texto = (v or "").strip()
        return texto if texto else "Startup TIC"

    def calcular_hash_entrada(self) -> str:
        """Gera hash SHA-256 determinístico das entradas para auditoria e cache."""
        payload = self.model_dump(mode="json")
        serializado = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serializado.encode("utf-8")).hexdigest()

    @classmethod
    def from_orm_projeto(cls, projeto_db: object) -> "EntradaSimulacaoSaaS":
        """
        Adaptador desacoplado que converte um objeto ORM (ProjetoDB) em
        EntradaSimulacaoSaaS sem importar SQLAlchemy no motor.
        """
        premissas_db = getattr(projeto_db, "premissas", None)
        juridico_db = getattr(projeto_db, "juridico", None)

        premissas = (
            PremissasInput(
                horizonte_meses=getattr(premissas_db, "horizonte_meses", 36) or 36,
                tma_anual_pct=float(getattr(premissas_db, "tma_anual_pct", 25.0) or 0.0),
                cac_estimado=float(getattr(premissas_db, "cac_estimado", 0.0) or 0.0),
                churn_mensal_pct=float(getattr(premissas_db, "churn_mensal_pct", 5.0) or 0.0),
                conversao_freemium_pct=float(
                    getattr(premissas_db, "conversao_freemium_pct", 2.0) or 0.0
                ),
                crescimento_mensal_pct=float(
                    getattr(premissas_db, "crescimento_mensal_pct", 5.0) or 0.0
                ),
                usuarios_freemium_base=int(
                    getattr(premissas_db, "usuarios_freemium_base", 0) or 0
                ),
            )
            if premissas_db is not None
            else PremissasInput()
        )

        investimentos = [
            ItemCapexInput(
                categoria=getattr(item, "categoria", None) or "Geral",
                descricao=getattr(item, "descricao", None) or "",
                valor=max(0.0, float(getattr(item, "valor", 0.0) or 0.0)),
            )
            for item in (getattr(projeto_db, "investimentos", None) or [])
        ]

        custos_fixos = [
            ItemOpexInput(
                categoria=getattr(item, "categoria", None) or "Geral",
                descricao=getattr(item, "descricao", None) or "",
                valor_mensal=max(0.0, float(getattr(item, "valor_mensal", 0.0) or 0.0)),
            )
            for item in (getattr(projeto_db, "custos_fixos", None) or [])
        ]

        planos_saas = [
            PlanoSaaSInput(
                nome_plano=getattr(plano, "nome_plano", None) or "Plano Padrão",
                ticket_mensal=max(0.0, float(getattr(plano, "ticket_mensal", 0.0) or 0.0)),
                usuarios_ativos_base=max(
                    0, int(getattr(plano, "usuarios_ativos_base", 0) or 0)
                ),
                taxas_pagamento_pct=min(
                    100.0,
                    max(0.0, float(getattr(plano, "taxas_pagamento_pct", 5.0) or 0.0)),
                ),
                impostos_pct=min(
                    100.0, max(0.0, float(getattr(plano, "impostos_pct", 6.0) or 0.0))
                ),
                custo_servidor_por_usuario=max(
                    0.0, float(getattr(plano, "custo_servidor_por_usuario", 0.0) or 0.0)
                ),
            )
            for plano in (getattr(projeto_db, "planos_saas", None) or [])
        ]

        custo_legal = (
            max(0.0, float(getattr(juridico_db, "custo_estimado_legal", 0.0) or 0.0))
            if juridico_db is not None
            else 0.0
        )

        return cls(
            nome_startup=getattr(projeto_db, "nome_startup", None) or "Startup TIC",
            premissas=premissas,
            investimentos=investimentos,
            custos_fixos=custos_fixos,
            planos_saas=planos_saas,
            custo_estimado_legal_mensal=custo_legal,
        )


class AlertaSanidade(BaseModel):
    model_config = ConfigDict(frozen=True)

    codigo: str
    severidade: SeveridadeAlerta
    titulo: str
    mensagem: str
    recomendacao: str
    metricas_afetadas: List[str] = Field(default_factory=list)


class DREBaseMensal(BaseModel):
    model_config = ConfigDict(frozen=True)

    mrr_bruto_direto: float
    mrr_bruto_total: float
    arr_anualizado: float
    despesas_deducoes_fiscais_gateway: float
    mrr_liquido: float
    despesas_nuvem_cogs: float
    margem_bruta_software: float
    margem_bruta_pct: float
    opex_fixo_mensal: float
    burn_rate_total_mensal: float
    ebitda_mensal: float


class MetricasUnitEconomics(BaseModel):
    model_config = ConfigDict(frozen=True)

    usuarios_pagos_diretos: int
    conversos_pagantes_freemium: int
    usuarios_pagantes_totais_base: int
    usuarios_free_tier_planos: int = 0
    custo_nuvem_free_tier_mensal: float = 0.0
    ticket_medio_arpu: float
    media_deducao_impostos_pct: float
    media_custo_nuvem_rs: float
    cac_estimado: float
    ltv_vitalicio_cliente: float
    indice_ltv_cac: float
    meses_payback_cac: Optional[float]


class MetricasViabilidade(BaseModel):
    model_config = ConfigDict(frozen=True)

    capex_total: float
    tma_desconto_mensal_Decimal: float
    valor_presente_liquido_vpl: float
    taxa_interna_retorno_mensal_pct: Optional[float]
    taxa_interna_retorno_anual_pct: float
    validade_da_tir: bool
    mudancas_sinal_fluxo: int
    multiplas_raizes_tir: bool
    mes_breakeven_payback_int: Optional[int]
    mes_de_breakeven_payback_texto: str
    meses_runway_sobrevivencia: Optional[float]


class SerieTemporalSimulacao(BaseModel):
    model_config = ConfigDict(frozen=True)

    rotulos_meses: List[str]
    fluxo_de_caixa_mensal: List[float]
    caixa_acumulado: List[float]
    usuarios_pagantes: List[float]
    mrr_mensal: List[float]
    usuarios_freemium: List[float]


class ResultadoSimulacaoSaaS(BaseModel):
    model_config = ConfigDict(frozen=True)

    versao_motor: str = Field(default=VERSAO_MOTOR)
    hash_entrada: str
    cenario: TipoCenario = Field(default=TipoCenario.BASE)
    dre_base: DREBaseMensal
    unit_economics: MetricasUnitEconomics
    viabilidade: MetricasViabilidade
    series_temporais: SerieTemporalSimulacao
    alertas: List[AlertaSanidade] = Field(default_factory=list)

    @property
    def possui_alertas_criticos(self) -> bool:
        return any(a.severidade == SeveridadeAlerta.CRITICO for a in self.alertas)

    def formatar_alertas_para_ia(self) -> str:
        """
        Gera bloco estruturado de alertas de sanidade para ser injetado no prompt da IA,
        evitando que o modelo de linguagem ignore distorções matemáticas.
        """
        if not self.alertas:
            return "Nenhum alerta de sanidade detectado; premissas dentro das faixas plausíveis."

        linhas = []
        for alerta in self.alertas:
            tag = alerta.severidade.value.upper()
            linhas.append(
                f"- [{tag}] {alerta.codigo} ({alerta.titulo}): {alerta.mensagem} "
                f"Recomendação: {alerta.recomendacao}"
            )
        return "\n".join(linhas)


class ResultadoComparacaoCenarios(BaseModel):
    model_config = ConfigDict(frozen=True)

    versao_motor: str = Field(default=VERSAO_MOTOR)
    cenarios: Dict[TipoCenario, ResultadoSimulacaoSaaS]


class ResultadoMonteCarlo(BaseModel):
    model_config = ConfigDict(frozen=True)

    versao_motor: str = Field(default=VERSAO_MOTOR)
    iteracoes: int
    semente: int
    probabilidade_vpl_positivo_pct: float
    vpl_p10: float
    vpl_p50_mediana: float
    vpl_p90: float
    vpl_media: float
    payback_mediano_meses: Optional[float]
