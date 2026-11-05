"""
Motor de Cálculo Financeiro Determinístico (SaaS & Unit Economics).
Totalmente isolado de UI e banco de dados.
"""

from __future__ import annotations

import math
import random
import statistics
from itertools import accumulate
from typing import Dict, List, Optional

import numpy_financial as npf

from .sanidade import contar_mudancas_sinal, validar_sanidade_simulacao
from .schemas import (
    VERSAO_MOTOR,
    DREBaseMensal,
    EntradaSimulacaoSaaS,
    MetricasUnitEconomics,
    MetricasViabilidade,
    PremissasInput,
    ResultadoComparacaoCenarios,
    ResultadoMonteCarlo,
    ResultadoSimulacaoSaaS,
    SerieTemporalSimulacao,
    TipoCenario,
)


def executar_simulacao_saas(
    entrada: EntradaSimulacaoSaaS,
    cenario: TipoCenario = TipoCenario.BASE,
) -> ResultadoSimulacaoSaaS:
    """
    Executa a simulação financeira determinística completa de uma operação SaaS,
    calculando DRE Base, Unit Economics, Fluxo de Caixa Descontado (VPL/TIR/Payback),
    Séries Temporais e Alertas de Sanidade.
    """
    premissas = entrada.premissas

    # 1. Agrupamento de Custos Base (Capex e Opex Fixo)
    capex_total_apurado = float(sum(item.valor for item in entrada.investimentos))
    opex_fixo_mensal = float(
        sum(custo.valor_mensal for custo in entrada.custos_fixos)
        + entrada.custo_estimado_legal_mensal
    )

    # 2. Segregação entre Planos Pagos e Planos Free Tier (R$ 0,00) + Funil Freemium
    planos_pagos = [p for p in entrada.planos_saas if p.ticket_mensal > 0.0]
    planos_free_tier = [p for p in entrada.planos_saas if p.ticket_mensal <= 0.0]

    usuarios_pagos_diretos = int(
        sum(plano.usuarios_ativos_base for plano in planos_pagos)
    )
    usuarios_free_tier_planos = int(
        sum(plano.usuarios_ativos_base for plano in planos_free_tier)
    )
    usuarios_freemium_totais_base = (
        int(premissas.usuarios_freemium_base) + usuarios_free_tier_planos
    )

    taxa_conversao_freemium_decimal = premissas.conversao_freemium_pct / 100.0

    conversos_pagantes_freemium = int(
        usuarios_freemium_totais_base * taxa_conversao_freemium_decimal
    )
    usuarios_pagantes_totais_base = usuarios_pagos_diretos + conversos_pagantes_freemium

    # 3. Cálculo de Faturamento MRR e Ticket Médio (ARPU exclusivo dos Planos Pagos)
    mrr_bruto_direto_apurado = float(
        sum(
            plano.ticket_mensal * plano.usuarios_ativos_base
            for plano in planos_pagos
        )
    )

    if usuarios_pagos_diretos > 0:
        ticket_medio_arpu = mrr_bruto_direto_apurado / usuarios_pagos_diretos
    else:
        ticket_medio_arpu = 0.0

    mrr_bruto_total_consolidado = mrr_bruto_direto_apurado + (
        conversos_pagantes_freemium * ticket_medio_arpu
    )

    # 4. Cálculo de Deduções Variáveis (Médias Ponderadas por Plano Pago + COGS Free Tier)
    if usuarios_pagos_diretos > 0:
        media_deducao_impostos_pct = float(
            sum(
                ((plano.taxas_pagamento_pct + plano.impostos_pct) / 100.0)
                * (plano.usuarios_ativos_base / usuarios_pagos_diretos)
                for plano in planos_pagos
            )
        )
        media_custo_nuvem_rs = float(
            sum(
                plano.custo_servidor_por_usuario
                * (plano.usuarios_ativos_base / usuarios_pagos_diretos)
                for plano in planos_pagos
            )
        )
    else:
        media_deducao_impostos_pct = 0.0
        media_custo_nuvem_rs = 0.0

    custo_nuvem_free_tier_base = float(
        sum(
            plano.custo_servidor_por_usuario * plano.usuarios_ativos_base
            for plano in planos_free_tier
        )
    )
    media_custo_nuvem_free_rs = (
        custo_nuvem_free_tier_base / usuarios_free_tier_planos
        if usuarios_free_tier_planos > 0
        else 0.0
    )
    proporcao_free_com_custo = (
        usuarios_free_tier_planos / usuarios_freemium_totais_base
        if usuarios_freemium_totais_base > 0
        else 0.0
    )

    despesas_deducoes_base = mrr_bruto_total_consolidado * media_deducao_impostos_pct
    despesas_nuvem_cogs_base = (
        usuarios_pagantes_totais_base * media_custo_nuvem_rs
    ) + custo_nuvem_free_tier_base

    # 5. DRE Base e Margens Operacionais
    mrr_liquido_apurado_base = mrr_bruto_total_consolidado - despesas_deducoes_base
    margem_bruta_software = mrr_liquido_apurado_base - despesas_nuvem_cogs_base
    burn_rate_total_mensal = opex_fixo_mensal + despesas_nuvem_cogs_base
    resultado_operacional_ebitda = mrr_liquido_apurado_base - burn_rate_total_mensal

    if mrr_bruto_total_consolidado > 0:
        margem_bruta_percentual = (
            margem_bruta_software / mrr_bruto_total_consolidado
        ) * 100.0
    else:
        margem_bruta_percentual = 0.0

    faturamento_anualizado_arr = mrr_bruto_total_consolidado * 12.0

    # 6. Mapeamento de Unit Economics
    taxa_churn_decimal = premissas.churn_mensal_pct / 100.0

    if taxa_churn_decimal > 0:
        ltv_vitalicio_cliente = ticket_medio_arpu / taxa_churn_decimal
    else:
        ltv_vitalicio_cliente = 0.0

    cac_aquisicao_mercado = float(premissas.cac_estimado)

    if cac_aquisicao_mercado > 0:
        indice_ltv_cac = ltv_vitalicio_cliente / cac_aquisicao_mercado
    else:
        indice_ltv_cac = 0.0

    fator_liquido_unitario = 1.0 - media_deducao_impostos_pct
    if (
        cac_aquisicao_mercado > 0
        and ticket_medio_arpu > 0
        and fator_liquido_unitario > 0
    ):
        meses_payback_cac: Optional[float] = cac_aquisicao_mercado / (
            ticket_medio_arpu * fator_liquido_unitario
        )
    else:
        meses_payback_cac = None

    # 7. Motor de Simulação Dinâmica (Loop de Crescimento)
    meses_de_horizonte_projecao = premissas.horizonte_meses
    tma_desconto_mensal = (1.0 + premissas.tma_anual_pct / 100.0) ** (1.0 / 12.0) - 1.0
    taxa_crescimento_organico_mensal = premissas.crescimento_mensal_pct / 100.0

    lista_fluxo_de_caixa: List[float] = [-capex_total_apurado]
    lista_rotulos_meses: List[str] = ["Mês 0"]

    timeline_usuarios_pagantes: List[float] = [float(usuarios_pagantes_totais_base)]
    timeline_mrr_crescente: List[float] = [float(mrr_bruto_total_consolidado)]
    timeline_usuarios_freemium: List[float] = [float(usuarios_freemium_totais_base)]

    usuarios_ativos_no_loop = float(usuarios_pagantes_totais_base)
    usuarios_freemium_no_loop = float(usuarios_freemium_totais_base)

    for mes_corrente in range(1, meses_de_horizonte_projecao + 1):
        # 7.1. Crescimento da Base Freemium / Free Tier (Topo de Funil)
        usuarios_freemium_no_loop = max(
            0.0,
            usuarios_freemium_no_loop * (1.0 + taxa_crescimento_organico_mensal),
        )

        # 7.2. Conversão de Gratuitos para Pagos (se houver ao menos 1 plano pago ativo)
        novos_clientes_advindos_do_free = (
            usuarios_freemium_no_loop * taxa_conversao_freemium_decimal
            if ticket_medio_arpu > 0.0
            else 0.0
        )

        # 7.3. Perdas por Cancelamento (Churn) da Base Paga
        evasao_de_clientes_pagos = usuarios_ativos_no_loop * taxa_churn_decimal

        # 7.4. Crescimento Orgânico da Base Paga
        novos_clientes_organicos_pagos = (
            usuarios_ativos_no_loop * taxa_crescimento_organico_mensal
        )

        # 7.5. Saldo Final de Utilizadores do Mês
        usuarios_ativos_no_loop = max(
            0.0,
            usuarios_ativos_no_loop
            + novos_clientes_organicos_pagos
            + novos_clientes_advindos_do_free
            - evasao_de_clientes_pagos,
        )

        # 7.6. Faturação do Mês
        mrr_apurado_no_mes = usuarios_ativos_no_loop * ticket_medio_arpu

        # 7.7. Custos do Mês (COGS Pagos + COGS Free Tier)
        deducoes_fiscais_no_mes = mrr_apurado_no_mes * media_deducao_impostos_pct
        cogs_nuvem_free_no_mes = (
            usuarios_freemium_no_loop
            * proporcao_free_com_custo
            * media_custo_nuvem_free_rs
        )
        cogs_nuvem_no_mes = (
            usuarios_ativos_no_loop * media_custo_nuvem_rs
        ) + cogs_nuvem_free_no_mes

        # 7.8. Resultado Líquido
        resultado_liquido_mensal = (
            (mrr_apurado_no_mes - deducoes_fiscais_no_mes)
            - cogs_nuvem_no_mes
            - opex_fixo_mensal
        )

        # 7.9. Armazenamento na Matriz
        lista_fluxo_de_caixa.append(float(resultado_liquido_mensal))
        lista_rotulos_meses.append(f"Mês {mes_corrente}")

        timeline_usuarios_pagantes.append(float(usuarios_ativos_no_loop))
        timeline_mrr_crescente.append(float(mrr_apurado_no_mes))
        timeline_usuarios_freemium.append(float(usuarios_freemium_no_loop))

    caixa_acumulado = list(accumulate(lista_fluxo_de_caixa))

    # 8. Análise de Viabilidade Financeira a Longo Prazo
    valor_presente_liquido_vpl = float(
        npf.npv(tma_desconto_mensal, lista_fluxo_de_caixa)
    )

    mudancas_sinal = contar_mudancas_sinal(lista_fluxo_de_caixa)
    multiplas_raizes_tir = mudancas_sinal >= 2

    taxa_interna_retorno_mensal_pct: Optional[float] = None
    taxa_interna_retorno_anual = 0.0
    validade_da_tir = False

    try:
        if capex_total_apurado > 0 and mudancas_sinal >= 1:
            tir_mensal_bruta = float(npf.irr(lista_fluxo_de_caixa))
            if (
                tir_mensal_bruta is not None
                and not math.isnan(tir_mensal_bruta)
                and not math.isinf(tir_mensal_bruta)
                and tir_mensal_bruta > -1.0
            ):
                taxa_interna_retorno_mensal_pct = tir_mensal_bruta * 100.0
                taxa_interna_retorno_anual = (
                    (1.0 + tir_mensal_bruta) ** 12.0 - 1.0
                ) * 100.0
                validade_da_tir = True
    except Exception:
        validade_da_tir = False

    mes_breakeven_int: Optional[int] = None
    mes_de_breakeven_payback_texto = "O Projeto Não Atinge Breakeven"
    for numero_mes, valor_em_caixa in enumerate(caixa_acumulado):
        if valor_em_caixa >= 0 and numero_mes > 0:
            mes_breakeven_int = numero_mes
            mes_de_breakeven_payback_texto = f"{numero_mes} meses para o Payback"
            break

    meses_runway_sobrevivencia: Optional[float] = None
    if resultado_operacional_ebitda < 0 and capex_total_apurado > 0:
        meses_runway_sobrevivencia = capex_total_apurado / abs(
            resultado_operacional_ebitda
        )

    dre_base = DREBaseMensal(
        mrr_bruto_direto=mrr_bruto_direto_apurado,
        mrr_bruto_total=mrr_bruto_total_consolidado,
        arr_anualizado=faturamento_anualizado_arr,
        despesas_deducoes_fiscais_gateway=despesas_deducoes_base,
        mrr_liquido=mrr_liquido_apurado_base,
        despesas_nuvem_cogs=despesas_nuvem_cogs_base,
        margem_bruta_software=margem_bruta_software,
        margem_bruta_pct=margem_bruta_percentual,
        opex_fixo_mensal=opex_fixo_mensal,
        burn_rate_total_mensal=burn_rate_total_mensal,
        ebitda_mensal=resultado_operacional_ebitda,
    )

    unit_economics = MetricasUnitEconomics(
        usuarios_pagos_diretos=usuarios_pagos_diretos,
        conversos_pagantes_freemium=conversos_pagantes_freemium,
        usuarios_pagantes_totais_base=usuarios_pagantes_totais_base,
        usuarios_free_tier_planos=usuarios_free_tier_planos,
        custo_nuvem_free_tier_mensal=custo_nuvem_free_tier_base,
        ticket_medio_arpu=ticket_medio_arpu,
        media_deducao_impostos_pct=media_deducao_impostos_pct,
        media_custo_nuvem_rs=media_custo_nuvem_rs,
        cac_estimado=cac_aquisicao_mercado,
        ltv_vitalicio_cliente=ltv_vitalicio_cliente,
        indice_ltv_cac=indice_ltv_cac,
        meses_payback_cac=meses_payback_cac,
    )

    viabilidade = MetricasViabilidade(
        capex_total=capex_total_apurado,
        tma_desconto_mensal_Decimal=tma_desconto_mensal,
        valor_presente_liquido_vpl=valor_presente_liquido_vpl,
        taxa_interna_retorno_mensal_pct=taxa_interna_retorno_mensal_pct,
        taxa_interna_retorno_anual_pct=taxa_interna_retorno_anual,
        validade_da_tir=validade_da_tir,
        mudancas_sinal_fluxo=mudancas_sinal,
        multiplas_raizes_tir=multiplas_raizes_tir,
        mes_breakeven_payback_int=mes_breakeven_int,
        mes_de_breakeven_payback_texto=mes_de_breakeven_payback_texto,
        meses_runway_sobrevivencia=meses_runway_sobrevivencia,
    )

    series_temporais = SerieTemporalSimulacao(
        rotulos_meses=lista_rotulos_meses,
        fluxo_de_caixa_mensal=lista_fluxo_de_caixa,
        caixa_acumulado=caixa_acumulado,
        usuarios_pagantes=timeline_usuarios_pagantes,
        mrr_mensal=timeline_mrr_crescente,
        usuarios_freemium=timeline_usuarios_freemium,
    )

    alertas = validar_sanidade_simulacao(
        entrada=entrada,
        dre=dre_base,
        unit=unit_economics,
        viabilidade=viabilidade,
    )

    return ResultadoSimulacaoSaaS(
        versao_motor=VERSAO_MOTOR,
        hash_entrada=entrada.calcular_hash_entrada(),
        cenario=cenario,
        dre_base=dre_base,
        unit_economics=unit_economics,
        viabilidade=viabilidade,
        series_temporais=series_temporais,
        alertas=alertas,
    )


def simular_cenarios_padrao(
    entrada: EntradaSimulacaoSaaS,
) -> ResultadoComparacaoCenarios:
    """
    Gera comparativo determinístico nos 3 cenários clássicos de Venture Capital:
    - BASE: Premissas originais
    - OTIMISTA: Crescimento +30%, Conversão Freemium +25%, Churn -25%
    - PESSIMISTA: Crescimento -35%, Conversão Freemium -30%, Churn +35%
    """
    p = entrada.premissas

    premissas_otimista = PremissasInput(
        horizonte_meses=p.horizonte_meses,
        tma_anual_pct=p.tma_anual_pct,
        cac_estimado=p.cac_estimado * 0.90,
        churn_mensal_pct=max(0.1 if p.churn_mensal_pct > 0 else 0.0, p.churn_mensal_pct * 0.75),
        conversao_freemium_pct=min(100.0, p.conversao_freemium_pct * 1.25),
        crescimento_mensal_pct=p.crescimento_mensal_pct * 1.30,
        usuarios_freemium_base=p.usuarios_freemium_base,
        ciclo_caixa_meses=p.ciclo_caixa_meses,
    )

    premissas_pessimista = PremissasInput(
        horizonte_meses=p.horizonte_meses,
        tma_anual_pct=p.tma_anual_pct,
        cac_estimado=p.cac_estimado * 1.20,
        churn_mensal_pct=min(100.0, p.churn_mensal_pct * 1.35),
        conversao_freemium_pct=max(0.0, p.conversao_freemium_pct * 0.70),
        crescimento_mensal_pct=p.crescimento_mensal_pct * 0.65,
        usuarios_freemium_base=p.usuarios_freemium_base,
        ciclo_caixa_meses=p.ciclo_caixa_meses,
    )

    entrada_otimista = entrada.model_copy(update={"premissas": premissas_otimista})
    entrada_pessimista = entrada.model_copy(update={"premissas": premissas_pessimista})

    cenarios: Dict[TipoCenario, ResultadoSimulacaoSaaS] = {
        TipoCenario.BASE: executar_simulacao_saas(entrada, cenario=TipoCenario.BASE),
        TipoCenario.OTIMISTA: executar_simulacao_saas(
            entrada_otimista, cenario=TipoCenario.OTIMISTA
        ),
        TipoCenario.PESSIMISTA: executar_simulacao_saas(
            entrada_pessimista, cenario=TipoCenario.PESSIMISTA
        ),
    }

    return ResultadoComparacaoCenarios(versao_motor=VERSAO_MOTOR, cenarios=cenarios)


def simular_monte_carlo(
    entrada: EntradaSimulacaoSaaS,
    iteracoes: int = 300,
    semente: int = 42,
) -> ResultadoMonteCarlo:
    """
    Executa simulação estocástica de Monte Carlo (com semente determinística para
    reprodutibilidade/auditoria) variando crescimento, churn e conversão.
    """
    if iteracoes < 10:
        raise ValueError("O número mínimo de iterações para Monte Carlo é 10.")

    rng = random.Random(semente)
    p = entrada.premissas

    vpls: List[float] = []
    paybacks: List[int] = []

    for _ in range(iteracoes):
        fator_cresc = max(0.0, rng.gauss(1.0, 0.25))
        fator_churn = max(0.2, rng.gauss(1.0, 0.20))
        fator_conv = max(0.1, rng.gauss(1.0, 0.20))

        premissa_amostra = PremissasInput(
            horizonte_meses=p.horizonte_meses,
            tma_anual_pct=p.tma_anual_pct,
            cac_estimado=p.cac_estimado,
            churn_mensal_pct=min(100.0, p.churn_mensal_pct * fator_churn),
            conversao_freemium_pct=min(100.0, p.conversao_freemium_pct * fator_conv),
            crescimento_mensal_pct=max(-90.0, min(500.0, p.crescimento_mensal_pct * fator_cresc)),
            usuarios_freemium_base=p.usuarios_freemium_base,
            ciclo_caixa_meses=p.ciclo_caixa_meses,
        )
        amostra_entrada = entrada.model_copy(update={"premissas": premissa_amostra})
        res = executar_simulacao_saas(amostra_entrada)
        vpls.append(res.viabilidade.valor_presente_liquido_vpl)
        if res.viabilidade.mes_breakeven_payback_int is not None:
            paybacks.append(res.viabilidade.mes_breakeven_payback_int)

    vpls_ordenados = sorted(vpls)
    n = len(vpls_ordenados)
    idx_p10 = min(n - 1, max(0, int(0.10 * n)))
    idx_p90 = min(n - 1, max(0, int(0.90 * n)))

    prob_positivo = (sum(1 for v in vpls if v > 0) / n) * 100.0
    payback_mediano = float(statistics.median(paybacks)) if paybacks else None

    return ResultadoMonteCarlo(
        versao_motor=VERSAO_MOTOR,
        iteracoes=iteracoes,
        semente=semente,
        probabilidade_vpl_positivo_pct=round(prob_positivo, 2),
        vpl_p10=round(vpls_ordenados[idx_p10], 2),
        vpl_p50_mediana=round(float(statistics.median(vpls_ordenados)), 2),
        vpl_p90=round(vpls_ordenados[idx_p90], 2),
        vpl_media=round(float(statistics.mean(vpls_ordenados)), 2),
        payback_mediano_meses=payback_mediano,
    )
