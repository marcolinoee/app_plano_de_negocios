"""
Validador de sanidade matemática e setorial (SaaS / Venture Capital).
Executa antes de qualquer chamada à IA ou emissão de relatório, gerando alertas
estruturados e determinísticos.
"""

from __future__ import annotations

from typing import List

from .schemas import (
    AlertaSanidade,
    DREBaseMensal,
    EntradaSimulacaoSaaS,
    MetricasUnitEconomics,
    MetricasViabilidade,
    SeveridadeAlerta,
)

# Limites de referência setorial SaaS B2B/B2C para auditoria de sanidade
LIMITE_TIR_ANUAL_MAX_PLAUSIVEL_PCT = 500.0
LIMITE_TIR_ANUAL_MIN_PLAUSIVEL_PCT = -90.0
LIMITE_MARGEM_BRUTA_MAX_SETORIAL_PCT = 92.0
LIMITE_MARGEM_BRUTA_MIN_SAUDAVEL_PCT = 50.0
LIMITE_CHURN_MENSAL_ALTO_PCT = 15.0
LIMITE_LTV_CAC_MIN_SAUDAVEL = 3.0
LIMITE_LTV_CAC_DESTRUICAO = 1.0
LIMITE_RUNWAY_CRITICO_MESES = 6.0


def contar_mudancas_sinal(fluxo_caixa: List[float], tolerancia: float = 1e-9) -> int:
    """
    Conta quantas vezes a série de fluxo de caixa muda de sinal (ignorando zeros).
    Pela Regra de Sinais de Descartes:
    - 0 mudanças: não existe TIR real.
    - 1 mudança: existe uma única TIR real bem definida.
    - >= 2 mudanças: podem existir múltiplas raízes reais para a TIR.
    """
    sinais: List[int] = []
    for valor in fluxo_caixa:
        if abs(valor) <= tolerancia:
            continue
        sinais.append(1 if valor > 0 else -1)

    if len(sinais) < 2:
        return 0

    mudancas = 0
    for anterior, atual in zip(sinais, sinais[1:]):
        if anterior != atual:
            mudancas += 1
    return mudancas


def validar_sanidade_simulacao(
    entrada: EntradaSimulacaoSaaS,
    dre: DREBaseMensal,
    unit: MetricasUnitEconomics,
    viabilidade: MetricasViabilidade,
) -> List[AlertaSanidade]:
    """
    Avalia as entradas e saídas da simulação financeira contra regras de sanidade
    econômica e de engenharia financeira.
    """
    alertas: List[AlertaSanidade] = []
    premissas = entrada.premissas

    # 1. Validação de Churn Zerado ou Irrealista
    if premissas.churn_mensal_pct <= 0.0:
        alertas.append(
            AlertaSanidade(
                codigo="CHURN_ZERADO",
                severidade=SeveridadeAlerta.CRITICO,
                titulo="Churn mensal zerado (0%)",
                mensagem=(
                    "A taxa de cancelamento mensal (Churn) está configurada em 0%. "
                    "Na prática de SaaS, churn zero implica retenção perpétua, "
                    "distorcendo o LTV (tende ao infinito) e inflando a projeção de receita."
                ),
                recomendacao=(
                    "Informe um churn mensal realista (ex.: 1,5% a 3% para SaaS B2B, "
                    "ou 4% a 8% para SaaS B2C/SMB)."
                ),
                metricas_afetadas=["churn_mensal_pct", "ltv_vitalicio_cliente", "indice_ltv_cac"],
            )
        )
    elif premissas.churn_mensal_pct >= LIMITE_CHURN_MENSAL_ALTO_PCT:
        alertas.append(
            AlertaSanidade(
                codigo="CHURN_EXCESSIVO",
                severidade=SeveridadeAlerta.AVISO,
                titulo="Churn mensal criticamente elevado",
                mensagem=(
                    f"O churn mensal de {premissas.churn_mensal_pct:.1f}% corrói "
                    "a base ativa em menos de um ano, inviabilizando o efeito composto do MRR."
                ),
                recomendacao="Revise a retenção do produto (Product-Market Fit) antes de escalar aquisição.",
                metricas_afetadas=["churn_mensal_pct", "ltv_vitalicio_cliente"],
            )
        )

    # 2. Validação de Fluxo de Caixa sem Mudança de Sinal
    if viabilidade.mudancas_sinal_fluxo == 0:
        alertas.append(
            AlertaSanidade(
                codigo="FLUXO_SEM_MUDANCA_SINAL",
                severidade=SeveridadeAlerta.CRITICO,
                titulo="Fluxo de caixa sem mudança de sinal",
                mensagem=(
                    "A série de fluxo de caixa não apresenta inversão de sinal ao longo do horizonte "
                    f"de {premissas.horizonte_meses} meses (ou não há Capex inicial negativo, ou a "
                    "operação permanece deficitária em todos os períodos). A TIR não possui solução real."
                ),
                recomendacao=(
                    "Verifique se o Capex inicial foi lançado corretamente ou ajuste preços, "
                    "custos e crescimento para atingir o ponto de equilíbrio (breakeven)."
                ),
                metricas_afetadas=["taxa_interna_retorno_anual_pct", "valor_presente_liquido_vpl"],
            )
        )

    # 3. Validação de Múltiplas Raízes na TIR
    if viabilidade.multiplas_raizes_tir:
        alertas.append(
            AlertaSanidade(
                codigo="TIR_MULTIPLAS_RAIZES",
                severidade=SeveridadeAlerta.CRITICO,
                titulo="Múltiplas raízes matemáticas na TIR",
                mensagem=(
                    f"O fluxo de caixa muda de sinal {viabilidade.mudancas_sinal_fluxo} vezes "
                    "(ex.: fluxo negativo inicial, torna-se positivo e volta a ficar negativo "
                    "por churn elevado). Pela Regra de Descartes, a TIR padrão torna-se ambígua."
                ),
                recomendacao=(
                    "Utilize o VPL como critério primário de decisão e avalie a causa da "
                    "inversão tardia de caixa (ex.: churn superando aquisição)."
                ),
                metricas_afetadas=["taxa_interna_retorno_anual_pct", "valor_presente_liquido_vpl"],
            )
        )

    # 4. Validação de TIR fora de faixa plausível
    if viabilidade.validade_da_tir:
        tir_anual = viabilidade.taxa_interna_retorno_anual_pct
        if tir_anual > LIMITE_TIR_ANUAL_MAX_PLAUSIVEL_PCT:
            alertas.append(
                AlertaSanidade(
                    codigo="TIR_ACIMA_FAIXA_PLAUSIVEL",
                    severidade=SeveridadeAlerta.AVISO,
                    titulo="TIR anualizada acima da faixa plausível de mercado",
                    mensagem=(
                        f"A TIR projetada de {tir_anual:,.1f}% a.a. excede o limite de sanidade "
                        f"({LIMITE_TIR_ANUAL_MAX_PLAUSIVEL_PCT:.0f}% a.a.), geralmente causado por "
                        "Capex subdimensionado ou crescimento mensal exponencial sem fricção."
                    ),
                    recomendacao=(
                        "Audite o Capex necessário para sustentar a operação e valide se a taxa "
                        "de crescimento mensal considera a saturação dos canais."
                    ),
                    metricas_afetadas=["taxa_interna_retorno_anual_pct", "capex_total"],
                )
            )
        elif tir_anual < LIMITE_TIR_ANUAL_MIN_PLAUSIVEL_PCT:
            alertas.append(
                AlertaSanidade(
                    codigo="TIR_ABAIXO_FAIXA_PLAUSIVEL",
                    severidade=SeveridadeAlerta.CRITICO,
                    titulo="TIR fortemente negativa (destruição severa de capital)",
                    mensagem=(
                        f"A TIR anualizada de {tir_anual:,.1f}% a.a. indica perda quase integral "
                        "do capital investido dentro do horizonte projetado."
                    ),
                    recomendacao="Reduza o burn rate fixo ou eleve o ARPU/conversão antes de captar recursos.",
                    metricas_afetadas=["taxa_interna_retorno_anual_pct", "valor_presente_liquido_vpl"],
                )
            )

    # 5. Payback menor que o ciclo de caixa
    ciclo_minimo = max(1.0, premissas.ciclo_caixa_meses)
    if (
        viabilidade.mes_breakeven_payback_int is not None
        and viabilidade.capex_total > 0
        and viabilidade.mes_breakeven_payback_int <= ciclo_minimo
    ):
        alertas.append(
            AlertaSanidade(
                codigo="PAYBACK_MENOR_CICLO_CAIXA",
                severidade=SeveridadeAlerta.AVISO,
                titulo="Payback do projeto menor ou igual ao ciclo de caixa",
                mensagem=(
                    f"O Payback estimado ({viabilidade.mes_breakeven_payback_int} mês) ocorre "
                    f"dentro ou antes do ciclo operacional de caixa ({ciclo_minimo:.1f} mês). "
                    "Isso sugere Capex irrisório frente à geração líquida imediata."
                ),
                recomendacao=(
                    "Confirme se o tempo de maturação comercial (ramp-up) e o prazo de "
                    "recebimento do gateway de pagamento foram considerados."
                ),
                metricas_afetadas=["mes_breakeven_payback_int", "capex_total"],
            )
        )

    if (
        unit.meses_payback_cac is not None
        and unit.cac_estimado > 0
        and unit.meses_payback_cac < premissas.ciclo_caixa_meses
    ):
        alertas.append(
            AlertaSanidade(
                codigo="CAC_PAYBACK_MENOR_CICLO_CAIXA",
                severidade=SeveridadeAlerta.AVISO,
                titulo="Payback do CAC menor que o ciclo de caixa",
                mensagem=(
                    f"O CAC Payback ({unit.meses_payback_cac:.2f} meses) é inferior ao ciclo "
                    f"de caixa ({premissas.ciclo_caixa_meses:.1f} meses), indicando CAC "
                    "possivelmente subestimado para o ticket médio informado."
                ),
                recomendacao="Verifique se todos os custos de marketing e vendas (salários de SDR/closers e mídia) estão incluídos no CAC.",
                metricas_afetadas=["meses_payback_cac", "cac_estimado"],
            )
        )

    # 6. Margem Bruta acima de limites setoriais ou negativa
    if dre.mrr_bruto_total > 0:
        if dre.margem_bruta_pct > LIMITE_MARGEM_BRUTA_MAX_SETORIAL_PCT:
            alertas.append(
                AlertaSanidade(
                    codigo="MARGEM_ACIMA_LIMITE_SETORIAL",
                    severidade=SeveridadeAlerta.AVISO,
                    titulo="Margem bruta acima do teto setorial de SaaS",
                    mensagem=(
                        f"A margem bruta de {dre.margem_bruta_pct:.1f}% supera o benchmark máximo "
                        f"típico de software ({LIMITE_MARGEM_BRUTA_MAX_SETORIAL_PCT:.0f}%). "
                        "Impostos (Simples/Lucro Presumido), taxas de gateway ou custos de nuvem/IA "
                        "(COGS) podem estar subestimados."
                    ),
                    recomendacao=(
                        "Verifique se as alíquotas fiscais (mín. ~6% no Brasil), taxas de cobrança "
                        "e custos de infraestrutura/APIs por usuário foram preenchidos nos planos."
                    ),
                    metricas_afetadas=["margem_bruta_pct", "despesas_nuvem_cogs"],
                )
            )
        elif dre.margem_bruta_pct <= 0.0:
            alertas.append(
                AlertaSanidade(
                    codigo="MARGEM_BRUTA_NEGATIVA_OU_NULA",
                    severidade=SeveridadeAlerta.CRITICO,
                    titulo="Margem bruta negativa ou nula (Unit Economics deficitário na origem)",
                    mensagem=(
                        f"A margem bruta é de {dre.margem_bruta_pct:.1f}%. O custo direto de "
                        "servir cada cliente (nuvem + impostos + taxas) supera o preço cobrado."
                    ),
                    recomendacao=(
                        "Aumente o ticket mensal dos planos ou reduza o custo de servidor/API por "
                        "usuário antes de escalar vendas — escalar agravará o prejuízo."
                    ),
                    metricas_afetadas=["margem_bruta_pct", "ticket_medio_arpu"],
                )
            )
        elif dre.margem_bruta_pct < LIMITE_MARGEM_BRUTA_MIN_SAUDAVEL_PCT:
            alertas.append(
                AlertaSanidade(
                    codigo="MARGEM_BRUTA_ABAIXO_BENCHMARK_SAAS",
                    severidade=SeveridadeAlerta.INFO,
                    titulo="Margem bruta abaixo do padrão SaaS (50%–85%)",
                    mensagem=(
                        f"A margem bruta atual ({dre.margem_bruta_pct:.1f}%) está abaixo do "
                        "patamar esperado por fundos de VC para empresas de software puro."
                    ),
                    recomendacao="Otimize custos de infraestrutura (COGS) ou revise o pricing dos tiers.",
                    metricas_afetadas=["margem_bruta_pct"],
                )
            )

    # 7. Deduções variáveis (impostos + gateway) >= 100% em algum plano
    for plano in entrada.planos_saas:
        if plano.deducao_total_pct >= 100.0:
            alertas.append(
                AlertaSanidade(
                    codigo="DEDUCOES_PLANO_INVIAVEIS",
                    severidade=SeveridadeAlerta.CRITICO,
                    titulo=f"Impostos e taxas somam {plano.deducao_total_pct:.1f}% no plano '{plano.nome_plano}'",
                    mensagem=(
                        f"O plano '{plano.nome_plano}' possui soma de impostos ({plano.impostos_pct:.1f}%) "
                        f"e gateway ({plano.taxas_pagamento_pct:.1f}%) igual ou superior a 100% da receita."
                    ),
                    recomendacao="Corrija os percentuais de impostos e taxas de pagamento do plano.",
                    metricas_afetadas=["media_deducao_impostos_pct"],
                )
            )

    # 8. Relação LTV/CAC e coerência de CAC
    if not entrada.planos_saas:
        alertas.append(
            AlertaSanidade(
                codigo="SEM_PLANOS_SAAS",
                severidade=SeveridadeAlerta.CRITICO,
                titulo="Nenhum plano de receita SaaS cadastrado",
                mensagem="Não há planos de assinatura configurados; a simulação não gera receita operacional.",
                recomendacao="Cadastre ao menos um plano SaaS com ticket mensal e base de usuários.",
                metricas_afetadas=["mrr_bruto_total"],
            )
        )
    else:
        if premissas.cac_estimado <= 0.0 and premissas.crescimento_mensal_pct > 0.0:
            alertas.append(
                AlertaSanidade(
                    codigo="CAC_ZERADO_COM_CRESCIMENTO",
                    severidade=SeveridadeAlerta.AVISO,
                    titulo="CAC igual a zero com crescimento mensal positivo",
                    mensagem=(
                        f"O projeto prevê crescimento de {premissas.crescimento_mensal_pct:.1f}% a.m. "
                        "com CAC de R$ 0,00, anulando o cálculo da razão LTV/CAC."
                    ),
                    recomendacao="Informe uma estimativa conservadora de CAC para habilitar a auditoria de eficiência comercial.",
                    metricas_afetadas=["cac_estimado", "indice_ltv_cac"],
                )
            )
        elif (
            premissas.cac_estimado > 0.0
            and premissas.churn_mensal_pct > 0.0
            and unit.ticket_medio_arpu > 0.0
        ):
            if unit.indice_ltv_cac < LIMITE_LTV_CAC_DESTRUICAO:
                alertas.append(
                    AlertaSanidade(
                        codigo="LTV_CAC_DESTRUICAO_VALOR",
                        severidade=SeveridadeAlerta.CRITICO,
                        titulo="Relação LTV/CAC menor que 1,0x (aquisição destrói caixa)",
                        mensagem=(
                            f"O indicador LTV/CAC é de {unit.indice_ltv_cac:.2f}x. Cada cliente "
                            f"custa R$ {unit.cac_estimado:,.2f} para ser adquirido e gera apenas "
                            f"R$ {unit.ltv_vitalicio_cliente:,.2f} ao longo de todo o seu ciclo de vida."
                        ),
                        recomendacao="Reduza o CAC, diminua o churn ou eleve o ticket médio (ARPU) antes de investir em aquisição.",
                        metricas_afetadas=["indice_ltv_cac", "ltv_vitalicio_cliente", "cac_estimado"],
                    )
                )
            elif unit.indice_ltv_cac < LIMITE_LTV_CAC_MIN_SAUDAVEL:
                alertas.append(
                    AlertaSanidade(
                        codigo="LTV_CAC_ABAIXO_BENCHMARK_VC",
                        severidade=SeveridadeAlerta.AVISO,
                        titulo="Relação LTV/CAC abaixo do benchmark de Venture Capital (3,0x)",
                        mensagem=(
                            f"O índice LTV/CAC atual ({unit.indice_ltv_cac:.2f}x) está entre 1,0x e 3,0x, "
                            "indicando eficiência marginal para captação institucional (Seed/Series A)."
                        ),
                        recomendacao="Busque atingir LTV/CAC >= 3,0x por meio de upsell/cross-sell ou redução de churn.",
                        metricas_afetadas=["indice_ltv_cac"],
                    )
                )

    # 9. Runway crítico
    if (
        viabilidade.meses_runway_sobrevivencia is not None
        and viabilidade.meses_runway_sobrevivencia < LIMITE_RUNWAY_CRITICO_MESES
    ):
        alertas.append(
            AlertaSanidade(
                codigo="RUNWAY_CRITICO",
                severidade=SeveridadeAlerta.CRITICO,
                titulo="Runway inferior a 6 meses",
                mensagem=(
                    f"Com o burn rate líquido atual, o capital aportado sustenta apenas "
                    f"{viabilidade.meses_runway_sobrevivencia:.1f} meses de operação."
                ),
                recomendacao=(
                    "Amplie a rodada de captação para garantir entre 12 e 18 meses de runway "
                    "ou reduza as despesas fixas mensais (Opex)."
                ),
                metricas_afetadas=["meses_runway_sobrevivencia", "burn_rate_total_mensal"],
            )
        )

    return alertas
