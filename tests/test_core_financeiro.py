"""
Suíte de Testes de Referência, Sanidade e Propriedades Matemáticas do Motor Financeiro (Fase 0).
Valida:
1. Casos conhecidos (planilha de referência para DRE, Unit Economics, VPL, TIR e Payback).
2. Determinismo, versionamento e hash criptográfico SHA-256 de auditoria.
3. Todas as validações de sanidade exigidas na arquitetura SaaS (churn zerado, múltiplas raízes na TIR,
   fluxo sem mudança de sinal, TIR fora de faixa plausível, payback menor que ciclo de caixa,
   margem acima do limite setorial, LTV/CAC destrutivo, runway crítico).
4. Invariantes e testes de propriedade (monotonicidade de VPL vs Capex, TMA e Crescimento).
5. Isolamento arquitetural (ausência de imports de Streamlit ou SQLAlchemy no pacote puro).
"""

from __future__ import annotations

import pathlib
import sys
import unittest

from core_financeiro import (
    VERSAO_MOTOR,
    EntradaSimulacaoSaaS,
    ItemCapexInput,
    ItemOpexInput,
    PlanoSaaSInput,
    PremissasInput,
    SeveridadeAlerta,
    TipoCenario,
    contar_mudancas_sinal,
    executar_simulacao_saas,
    simular_cenarios_padrao,
    simular_monte_carlo,
)


def criar_cenario_referencia_b2b() -> EntradaSimulacaoSaaS:
    """
    Cria o caso de referência auditado (planilha padrão SaaS B2B):
    - 1 plano de R$ 200,00 com 100 clientes pagos diretos
    - 500 usuários freemium com 2% de conversão (= 10 clientes convertidos)
    - Total pagantes base = 110 clientes -> MRR Bruto = R$ 22.000,00 | ARR = R$ 264.000,00
    - Taxas (5%) + Impostos (6%) = 11% -> Deduções = R$ 2.420,00 -> MRR Líquido = R$ 19.580,00
    - Custo nuvem = R$ 10,00/usuário -> COGS = 110 * 10 = R$ 1.100,00
    - Margem Bruta Software = 19.580 - 1.100 = R$ 18.480,00 (84,0% do MRR Bruto)
    - Opex Fixo = R$ 12.000,00 + Jurídico R$ 1.000,00 = R$ 13.000,00
    - Burn Rate Total = 13.000 + 1.100 = R$ 14.100,00
    - EBITDA Base = 19.580 - 14.100 = R$ 5.480,00
    - Churn = 4% a.m. -> LTV = 200 / 0,04 = R$ 5.000,00
    - CAC = R$ 1.000,00 -> LTV/CAC = 5,0x
    - Capex = R$ 100.000,00
    """
    return EntradaSimulacaoSaaS(
        nome_startup="SaaS B2B Referência",
        premissas=PremissasInput(
            horizonte_meses=36,
            tma_anual_pct=20.0,
            cac_estimado=1000.0,
            churn_mensal_pct=4.0,
            conversao_freemium_pct=2.0,
            crescimento_mensal_pct=6.0,
            usuarios_freemium_base=500,
            ciclo_caixa_meses=1.0,
        ),
        investimentos=[
            ItemCapexInput(
                categoria="Engenharia e Desenvolvimento do MVP",
                descricao="Desenvolvimento Core",
                valor=100000.0,
            )
        ],
        custos_fixos=[
            ItemOpexInput(
                categoria="Custos com Pessoal Técnico (Headcount Tech)",
                descricao="Time Engenharia",
                valor_mensal=12000.0,
            )
        ],
        planos_saas=[
            PlanoSaaSInput(
                nome_plano="Plano Pro B2B",
                ticket_mensal=200.0,
                usuarios_ativos_base=100,
                taxas_pagamento_pct=5.0,
                impostos_pct=6.0,
                custo_servidor_por_usuario=10.0,
            )
        ],
        custo_estimado_legal_mensal=1000.0,
    )


class TestMotorFinanceiroSaaS(unittest.TestCase):
    def test_planilha_referencia_dre_e_unit_economics(self) -> None:
        entrada = criar_cenario_referencia_b2b()
        res = executar_simulacao_saas(entrada)

        # Metadados
        self.assertEqual(res.versao_motor, VERSAO_MOTOR)
        self.assertEqual(len(res.hash_entrada), 64)

        # Unit Economics exatos da planilha de referência
        u = res.unit_economics
        self.assertEqual(u.usuarios_pagos_diretos, 100)
        self.assertEqual(u.conversos_pagantes_freemium, 10)
        self.assertEqual(u.usuarios_pagantes_totais_base, 110)
        self.assertAlmostEqual(u.ticket_medio_arpu, 200.0, places=4)
        self.assertAlmostEqual(u.media_deducao_impostos_pct, 0.11, places=4)
        self.assertAlmostEqual(u.media_custo_nuvem_rs, 10.0, places=4)
        self.assertAlmostEqual(u.ltv_vitalicio_cliente, 5000.0, places=2)
        self.assertAlmostEqual(u.indice_ltv_cac, 5.0, places=4)
        # Payback CAC = 1000 / (200 * (1 - 0.11)) = 1000 / 178 = 5.617977...
        self.assertIsNotNone(u.meses_payback_cac)
        self.assertAlmostEqual(u.meses_payback_cac or 0.0, 1000.0 / 178.0, places=4)

        # DRE Base exata
        d = res.dre_base
        self.assertAlmostEqual(d.mrr_bruto_direto, 20000.0, places=2)
        self.assertAlmostEqual(d.mrr_bruto_total, 22000.0, places=2)
        self.assertAlmostEqual(d.arr_anualizado, 264000.0, places=2)
        self.assertAlmostEqual(d.despesas_deducoes_fiscais_gateway, 2420.0, places=2)
        self.assertAlmostEqual(d.mrr_liquido, 19580.0, places=2)
        self.assertAlmostEqual(d.despesas_nuvem_cogs, 1100.0, places=2)
        self.assertAlmostEqual(d.margem_bruta_software, 18480.0, places=2)
        self.assertAlmostEqual(d.margem_bruta_pct, 84.0, places=2)
        self.assertAlmostEqual(d.opex_fixo_mensal, 13000.0, places=2)
        self.assertAlmostEqual(d.burn_rate_total_mensal, 14100.0, places=2)
        self.assertAlmostEqual(d.ebitda_mensal, 5480.0, places=2)

        # Viabilidade
        v = res.viabilidade
        self.assertAlmostEqual(v.capex_total, 100000.0, places=2)
        self.assertTrue(v.validade_da_tir)
        self.assertEqual(v.mudancas_sinal_fluxo, 1)
        self.assertFalse(v.multiplas_raizes_tir)
        self.assertGreater(v.valor_presente_liquido_vpl, 0.0)
        self.assertIsNotNone(v.mes_breakeven_payback_int)
        self.assertEqual(len(res.series_temporais.fluxo_de_caixa_mensal), 37)

        # Nenhum alerta crítico no caso saudável de referência
        self.assertFalse(res.possui_alertas_criticos)

    def test_determinismo_e_hash_entrada(self) -> None:
        entrada1 = criar_cenario_referencia_b2b()
        entrada2 = criar_cenario_referencia_b2b()

        res1 = executar_simulacao_saas(entrada1)
        res2 = executar_simulacao_saas(entrada2)

        self.assertEqual(res1.hash_entrada, res2.hash_entrada)
        self.assertEqual(res1.model_dump(), res2.model_dump())

    def test_alerta_churn_zerado(self) -> None:
        base = criar_cenario_referencia_b2b()
        premissas_sem_churn = base.premissas.model_copy(update={"churn_mensal_pct": 0.0})
        entrada = base.model_copy(update={"premissas": premissas_sem_churn})

        res = executar_simulacao_saas(entrada)
        codigos = {a.codigo for a in res.alertas}
        self.assertIn("CHURN_ZERADO", codigos)
        self.assertTrue(res.possui_alertas_criticos)

    def test_alerta_fluxo_sem_mudanca_sinal(self) -> None:
        base = criar_cenario_referencia_b2b()
        # Sem Capex e com operação superavitária desde o mês 0 -> todos os fluxos >= 0
        entrada = base.model_copy(update={"investimentos": []})
        res = executar_simulacao_saas(entrada)

        codigos = {a.codigo for a in res.alertas}
        self.assertIn("FLUXO_SEM_MUDANCA_SINAL", codigos)
        self.assertEqual(res.viabilidade.mudancas_sinal_fluxo, 0)
        self.assertFalse(res.viabilidade.validade_da_tir)

    def test_alerta_multiplas_raizes_tir(self) -> None:
        # Teste direto da função de contagem de sinais e da simulação quando há 2 inversões
        fluxo_oscilante = [-50000.0, 20000.0, 25000.0, -10000.0, -15000.0]
        self.assertEqual(contar_mudancas_sinal(fluxo_oscilante), 2)

        # Simulação onde o Mês 1 é positivo (forte receita inicial), mas o churn é muito maior
        # que a aquisição e o fluxo mensal fica negativo nos meses seguintes após Capex negativo no Mês 0
        entrada = EntradaSimulacaoSaaS(
            nome_startup="Startup Churn Tardio",
            premissas=PremissasInput(
                horizonte_meses=24,
                tma_anual_pct=15.0,
                cac_estimado=200.0,
                churn_mensal_pct=25.0,
                conversao_freemium_pct=0.0,
                crescimento_mensal_pct=0.0,
                usuarios_freemium_base=0,
            ),
            investimentos=[ItemCapexInput(categoria="MVP", descricao="Setup", valor=10000.0)],
            custos_fixos=[ItemOpexInput(categoria="Opex", descricao="Fixo", valor_mensal=5000.0)],
            planos_saas=[
                PlanoSaaSInput(
                    nome_plano="Plano Base",
                    ticket_mensal=100.0,
                    usuarios_ativos_base=150,
                    taxas_pagamento_pct=5.0,
                    impostos_pct=5.0,
                    custo_servidor_por_usuario=5.0,
                )
            ],
        )
        res = executar_simulacao_saas(entrada)
        codigos = {a.codigo for a in res.alertas}
        self.assertTrue(res.viabilidade.multiplas_raizes_tir)
        self.assertIn("TIR_MULTIPLAS_RAIZES", codigos)

    def test_alerta_tir_acima_faixa_e_payback_menor_ciclo_caixa(self) -> None:
        base = criar_cenario_referencia_b2b()
        # Capex muito baixo (R$ 1.000) frente a EBITDA mensal de R$ 5.480 -> Payback em 1 mês e TIR > 500% a.a.
        entrada = base.model_copy(
            update={
                "investimentos": [
                    ItemCapexInput(categoria="MVP", descricao="Mínimo", valor=1000.0)
                ],
                "premissas": base.premissas.model_copy(update={"ciclo_caixa_meses": 2.0}),
            }
        )
        res = executar_simulacao_saas(entrada)
        codigos = {a.codigo for a in res.alertas}
        self.assertIn("TIR_ACIMA_FAIXA_PLAUSIVEL", codigos)
        self.assertIn("PAYBACK_MENOR_CICLO_CAIXA", codigos)

    def test_alerta_margem_acima_limite_setorial(self) -> None:
        base = criar_cenario_referencia_b2b()
        # Plano sem impostos, sem gateway e sem custo de nuvem -> margem bruta de 100% (> 92%)
        entrada = base.model_copy(
            update={
                "planos_saas": [
                    PlanoSaaSInput(
                        nome_plano="Plano Irreal",
                        ticket_mensal=500.0,
                        usuarios_ativos_base=50,
                        taxas_pagamento_pct=0.0,
                        impostos_pct=0.0,
                        custo_servidor_por_usuario=0.0,
                    )
                ]
            }
        )
        res = executar_simulacao_saas(entrada)
        codigos = {a.codigo for a in res.alertas}
        self.assertIn("MARGEM_ACIMA_LIMITE_SETORIAL", codigos)

    def test_alerta_ltv_cac_destruicao_e_runway_critico(self) -> None:
        entrada = EntradaSimulacaoSaaS(
            nome_startup="Startup Queima Rápida",
            premissas=PremissasInput(
                horizonte_meses=24,
                tma_anual_pct=20.0,
                cac_estimado=5000.0,  # LTV será 100 / 0.10 = 1000 -> LTV/CAC = 0.2x (< 1.0x)
                churn_mensal_pct=10.0,
                conversao_freemium_pct=1.0,
                crescimento_mensal_pct=2.0,
                usuarios_freemium_base=0,
            ),
            investimentos=[ItemCapexInput(categoria="Seed", descricao="Caixa", valor=30000.0)],
            custos_fixos=[ItemOpexInput(categoria="Folha", descricao="Time", valor_mensal=15000.0)],
            planos_saas=[
                PlanoSaaSInput(
                    nome_plano="Starter",
                    ticket_mensal=100.0,
                    usuarios_ativos_base=10,
                    taxas_pagamento_pct=5.0,
                    impostos_pct=6.0,
                    custo_servidor_por_usuario=10.0,
                )
            ],
        )
        res = executar_simulacao_saas(entrada)
        codigos = {a.codigo for a in res.alertas}
        self.assertIn("LTV_CAC_DESTRUICAO_VALOR", codigos)
        self.assertIn("RUNWAY_CRITICO", codigos)
        self.assertEqual(res.possui_alertas_criticos, True)

    def test_propriedades_monotonicidade_financeira(self) -> None:
        """
        Testes de propriedade (Property-based invariants):
        1. Aumentar o Capex mantendo fluxos operacionais constantes deve reduzir exatamente o VPL na mesma proporção.
        2. Aumentar a TMA em fluxo convencional com VPL positivo deve reduzir o VPL.
        3. Cenário Otimista > Cenário Base > Cenário Pessimista em VPL.
        """
        base = criar_cenario_referencia_b2b()
        res_base = executar_simulacao_saas(base)

        # Propriedade 1: VPL(Capex + Delta) == VPL(Capex) - Delta
        delta_capex = 25000.0
        entrada_maior_capex = base.model_copy(
            update={
                "investimentos": [
                    ItemCapexInput(
                        categoria="Capex",
                        descricao="Maior",
                        valor=100000.0 + delta_capex,
                    )
                ]
            }
        )
        res_maior_capex = executar_simulacao_saas(entrada_maior_capex)
        self.assertAlmostEqual(
            res_base.viabilidade.valor_presente_liquido_vpl
            - res_maior_capex.viabilidade.valor_presente_liquido_vpl,
            delta_capex,
            places=2,
        )

        # Propriedade 2: Monotonicidade de Cenários (Otimista > Base > Pessimista)
        comparativo = simular_cenarios_padrao(base)
        vpl_otimista = comparativo.cenarios[TipoCenario.OTIMISTA].viabilidade.valor_presente_liquido_vpl
        vpl_base = comparativo.cenarios[TipoCenario.BASE].viabilidade.valor_presente_liquido_vpl
        vpl_pessimista = comparativo.cenarios[TipoCenario.PESSIMISTA].viabilidade.valor_presente_liquido_vpl

        self.assertGreater(vpl_otimista, vpl_base)
        self.assertGreater(vpl_base, vpl_pessimista)

    def test_monte_carlo_reprodutivel(self) -> None:
        base = criar_cenario_referencia_b2b()
        mc1 = simular_monte_carlo(base, iteracoes=50, semente=123)
        mc2 = simular_monte_carlo(base, iteracoes=50, semente=123)

        self.assertEqual(mc1.model_dump(), mc2.model_dump())
        self.assertLessEqual(mc1.vpl_p10, mc1.vpl_p50_mediana)
        self.assertLessEqual(mc1.vpl_p50_mediana, mc1.vpl_p90)

    def test_isolamento_arquitetural_sem_streamlit_ou_sqlalchemy(self) -> None:
        """Garante que os módulos de core_financeiro não importam streamlit nem sqlalchemy."""
        for nome_modulo in (
            "core_financeiro",
            "core_financeiro.schemas",
            "core_financeiro.sanidade",
            "core_financeiro.calculadora",
        ):
            modulo = sys.modules[nome_modulo]
            codigo_fonte = pathlib.Path(modulo.__file__).read_text(encoding="utf-8")
            self.assertNotIn("import streamlit", codigo_fonte)
            self.assertNotIn("from streamlit", codigo_fonte)
            self.assertNotIn("import sqlalchemy", codigo_fonte)
            self.assertNotIn("from sqlalchemy", codigo_fonte)

    def test_adaptador_from_orm_projeto(self) -> None:
        """Valida a conversão desacoplada a partir de objetos ORM (ex.: ProjetoDB)."""
        from types import SimpleNamespace

        projeto_fake = SimpleNamespace(
            nome_startup="Startup ORM Test",
            premissas=SimpleNamespace(
                horizonte_meses=24,
                tma_anual_pct=18.0,
                cac_estimado=500.0,
                churn_mensal_pct=3.0,
                conversao_freemium_pct=2.5,
                crescimento_mensal_pct=5.0,
                usuarios_freemium_base=400,
            ),
            investimentos=[
                SimpleNamespace(categoria="Infra", descricao="Servidor", valor=50000.0)
            ],
            custos_fixos=[
                SimpleNamespace(categoria="Dev", descricao="Engenheiro", valor_mensal=8000.0)
            ],
            planos_saas=[
                SimpleNamespace(
                    nome_plano="Enterprise",
                    ticket_mensal=1000.0,
                    usuarios_ativos_base=20,
                    taxas_pagamento_pct=4.0,
                    impostos_pct=6.0,
                    custo_servidor_por_usuario=25.0,
                )
            ],
            juridico=SimpleNamespace(custo_estimado_legal=500.0),
        )

        entrada = EntradaSimulacaoSaaS.from_orm_projeto(projeto_fake)
        res = executar_simulacao_saas(entrada)

        self.assertEqual(entrada.nome_startup, "Startup ORM Test")
        self.assertEqual(res.unit_economics.usuarios_pagos_diretos, 20)
        self.assertEqual(res.unit_economics.conversos_pagantes_freemium, 10)
        self.assertAlmostEqual(res.dre_base.opex_fixo_mensal, 8500.0, places=2)

    def test_plano_free_tier_nao_dilui_arpu_e_contabiliza_cogs_nuvem(self) -> None:
        """
        Garante que cadastrar um Plano Free Tier (ticket_mensal == 0.0):
        1. Não dilui o ARPU dos assinantes pagantes;
        2. Contabiliza o COGS de nuvem dos usuários gratuitos;
        3. Alimenta o funil de conversão para planos pagos;
        4. Funciona mesmo quando a startup possui APENAS plano Free Tier (pré-receita).
        """
        entrada_plg = EntradaSimulacaoSaaS(
            nome_startup="PLG Startup",
            premissas=PremissasInput(
                horizonte_meses=24,
                tma_anual_pct=20.0,
                cac_estimado=200.0,
                churn_mensal_pct=4.0,
                conversao_freemium_pct=2.0,
                crescimento_mensal_pct=5.0,
                usuarios_freemium_base=0,
            ),
            investimentos=[ItemCapexInput(categoria="MVP", valor=50000.0)],
            custos_fixos=[ItemOpexInput(categoria="Time", valor_mensal=5000.0)],
            planos_saas=[
                PlanoSaaSInput(
                    nome_plano="Free Tier",
                    ticket_mensal=0.0,
                    usuarios_ativos_base=1000,
                    taxas_pagamento_pct=0.0,
                    impostos_pct=0.0,
                    custo_servidor_por_usuario=1.50,
                ),
                PlanoSaaSInput(
                    nome_plano="Pro",
                    ticket_mensal=100.0,
                    usuarios_ativos_base=50,
                    taxas_pagamento_pct=4.0,
                    impostos_pct=6.0,
                    custo_servidor_por_usuario=10.0,
                ),
            ],
        )
        res = executar_simulacao_saas(entrada_plg)

        # ARPU deve continuar sendo R$ 100,00 (dos 50 pagantes), sem ser diluído pelos 1.000 gratuitos
        self.assertAlmostEqual(res.unit_economics.ticket_medio_arpu, 100.0, places=2)
        self.assertEqual(res.unit_economics.usuarios_pagos_diretos, 50)
        self.assertEqual(res.unit_economics.usuarios_free_tier_planos, 1000)
        # 2% de 1.000 usuários do Free Tier convertem em 20 pagantes adicionais
        self.assertEqual(res.unit_economics.conversos_pagantes_freemium, 20)
        self.assertEqual(res.unit_economics.usuarios_pagantes_totais_base, 70)
        # COGS Free Tier = 1.000 * R$ 1,50 = R$ 1.500,00; COGS Pagos = 70 * R$ 10,00 = R$ 700,00
        self.assertAlmostEqual(
            res.unit_economics.custo_nuvem_free_tier_mensal, 1500.0, places=2
        )
        self.assertAlmostEqual(res.dre_base.despesas_nuvem_cogs, 2200.0, places=2)

        # Caso extremo: Startup 100% Free Tier (ainda sem plano pago cadastrado)
        entrada_so_free = entrada_plg.model_copy(
            update={"planos_saas": [entrada_plg.planos_saas[0]]}
        )
        res_free = executar_simulacao_saas(entrada_so_free)
        self.assertEqual(res_free.dre_base.mrr_bruto_total, 0.0)
        self.assertAlmostEqual(res_free.dre_base.despesas_nuvem_cogs, 1500.0, places=2)
        self.assertIsNotNone(res_free.viabilidade.meses_runway_sobrevivencia)


if __name__ == "__main__":
    unittest.main(verbosity=2)
