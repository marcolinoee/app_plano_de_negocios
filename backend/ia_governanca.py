"""
Governança de IA, Sanitização de PII, Cache por Hash, Quotas por Tenant
e Homologação Obrigatória pelo Consultor (Fase 3 - Seção 5 do Plano SaaS).
"""

from __future__ import annotations

import hashlib
import json
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from core_financeiro import (
    EntradaSimulacaoSaaS,
    ResultadoSimulacaoSaaS,
    TipoCenario,
    executar_simulacao_saas,
)

from .auditoria import registrar_evento_auditoria
from .models import (
    AnaliseIAEBT,
    AssinaturaTenant,
    ClienteEBT,
    JobAssincronoSaaS,
    Membership,
    ResultadoSimulacaoEBT,
    StatusJobAssincrono,
)
from .rbac import PermissaoSaaS, verificar_permissao_rbac
from .servicos import ErroLimitePlanoSaaS, obter_ou_criar_uso_mensal

VERSAO_PROMPT_VC = "v2.0-saas-governado"

BANNER_GOVERNANCA_IA = (
    "> ⚠️ **AVISO DE GOVERNANÇA E COMPLIANCE (IA ASSISTIVA)**: Este parecer preliminar foi "
    "gerado por modelo de Inteligência Artificial a partir de dados anonimizados (sem PII) "
    "e métricas determinísticas do motor financeiro. **Não substitui assessoria jurídica, "
    "contábil ou de investimentos e requer revisão e homologação explícita do Consultor "
    "responsável antes de compor o Dossiê Oficial.**\n\n"
)

# Expressões regulares para sanitização de PII (LGPD) antes do envio ao LLM
_REGEX_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_REGEX_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_REGEX_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_REGEX_TELEFONE = re.compile(
    r"(?:\+55\s?)?(?:\(?\d{2}\)?\s?)(?:9?\d{4})-?\d{4}\b"
)


def sanitizar_pii_texto(texto: Optional[str]) -> str:
    """
    Remove/mascara dados pessoais e sensíveis (e-mails, CPFs, CNPJs e telefones)
    antes de enviar textos qualitativos a provedores externos de LLM (conformidade LGPD).
    """
    if not texto:
        return ""
    limpo = _REGEX_EMAIL.sub("[EMAIL_OCULTO_LGPD]", texto)
    limpo = _REGEX_CNPJ.sub("[CNPJ_OCULTO_LGPD]", limpo)
    limpo = _REGEX_CPF.sub("[CPF_OCULTO_LGPD]", limpo)
    limpo = _REGEX_TELEFONE.sub("[TELEFONE_OCULTO_LGPD]", limpo)
    return limpo


def construir_prompt_vc_governado(
    ebt: ClienteEBT,
    resultado_simulacao: ResultadoSimulacaoSaaS,
) -> Tuple[str, str]:
    """
    Constrói o prompt versionado para o Comitê de Venture Capital aplicando
    sanitização de PII nos campos abertos e calcula o hash SHA-256 determinístico
    do contexto completo (numérico + qualitativo sanitizado + versão do prompt).
    """
    lc = ebt.lean_canvas
    jur = ebt.juridico

    problema_limpo = sanitizar_pii_texto(lc.problema if lc else "")
    solucao_limpa = sanitizar_pii_texto(lc.solucao_mvp if lc else "")
    proposta_limpa = sanitizar_pii_texto(lc.proposta_valor if lc else "")
    vantagem_limpa = sanitizar_pii_texto(lc.vantagem_injusta if lc else "")
    segmentos_limpos = sanitizar_pii_texto(lc.segmentos if lc else "")
    ip_limpo = sanitizar_pii_texto(jur.registro_inpi if jur else "")
    cap_table_limpo = (
        f"Vesting: {'Formalizado' if (jur and jur.contrato_vesting) else 'Pendente'} | "
        f"LGPD: {'Conforme' if (jur and jur.adequacao_lgpd) else 'Pendente'}"
    )

    payload_contexto = {
        "versao_prompt": VERSAO_PROMPT_VC,
        "hash_entrada_financeira": resultado_simulacao.hash_entrada,
        "setor_vertical": ebt.setor_vertical,
        "estagio": ebt.estagio,
        "problema": problema_limpo,
        "solucao": solucao_limpa,
        "proposta_valor": proposta_limpa,
        "vantagem_injusta": vantagem_limpa,
        "segmentos_clientes": segmentos_limpos,
        "ip": ip_limpo,
        "cap_table": cap_table_limpo,
    }
    serializado = json.dumps(payload_contexto, sort_keys=True, ensure_ascii=False)
    hash_contexto_ia = hashlib.sha256(serializado.encode("utf-8")).hexdigest()

    dre = resultado_simulacao.dre_base
    ue = resultado_simulacao.unit_economics
    viab = resultado_simulacao.viabilidade
    alertas_txt = (
        "\n".join(
            f"- [{a.severidade.value.upper()}] {a.codigo}: {a.mensagem}"
            for a in resultado_simulacao.alertas
        )
        if resultado_simulacao.alertas
        else "- Nenhum alerta de sanidade disparado."
    )

    prompt = f"""
Você é um Managing Partner de um Fundo de Venture Capital Tier-1 avaliando uma Empresa de Base Tecnológica (EBT) em um Comitê de Investimento.
Observação de Segurança: Todos os identificadores pessoais (PII) e razão social foram anonimizados por compliance LGPD.

[1. PERFIL E TESE ESTRATÉGICA (ANONIMIZADA)]
- Vertical / Setor: {ebt.setor_vertical} | Estágio: {ebt.estagio}
- Problema: {problema_limpo}
- Solução & Arquitetura: {solucao_limpa}
- Proposta Única de Valor: {proposta_limpa}
- Vantagem Injusta (Moat): {vantagem_limpa}
- ICP / Segmentos: {segmentos_limpos}

[2. UNIT ECONOMICS E DRE MENSAL BASE (MOTOR v{resultado_simulacao.versao_motor})]
- MRR Bruto Inicial: R$ {dre.mrr_bruto_total:,.2f} | ARR Inicial: R$ {dre.arr_anualizado:,.2f}
- Margem de Contribuição Bruta (após COGS de Nuvem/APIs): {dre.margem_bruta_pct:.1f}%
- Burn Rate Operacional / EBITDA Mensal Base: R$ {dre.ebitda_mensal:,.2f}
- Ticket Médio Ponderado (ARPU): R$ {ue.ticket_medio_arpu:,.2f}
- LTV: R$ {ue.ltv_vitalicio_cliente:,.2f} | CAC: R$ {ue.cac_estimado:,.2f} | Relação LTV/CAC: {ue.indice_ltv_cac:.2f}x
- CAC Payback: {f"{ue.meses_payback_cac:.1f} meses" if ue.meses_payback_cac is not None else "N/A"}

[3. VALUATION E VIABILIDADE]
- CAPEX Total Inicial: R$ {viab.capex_total:,.2f}
- VPL (Descontado pela TMA): R$ {viab.valor_presente_liquido_vpl:,.2f}
- TIR Anualizada: {f"{viab.taxa_interna_retorno_anual_pct:.1f}%" if viab.validade_da_tir else "N/A (sem inversão única de sinal)"}
- Breakeven / Payback: {viab.mes_de_breakeven_payback_texto}
- Runway de Sobrevivência: {f"{viab.meses_runway_sobrevivencia:.1f} meses" if viab.meses_runway_sobrevivencia is not None else "Operação superavitária"}

[4. ALERTAS DO VALIDADOR DETERMINÍSTICO DE SANIDADE PRÉ-IA]
{alertas_txt}

[5. GOVERNANÇA E PROPRIEDADE INTELECTUAL]
- Propriedade Intelectual (INPI): {ip_limpo}
- Cap Table & Vesting: {cap_table_limpo}

Elabore um Parecer Executivo de Due Diligence em Markdown contendo:
1. **Veredito Preliminar do Comitê** (Aprovar Due Diligence / Aprovar com Condicionantes / Reprovar)
2. **Análise Crítica de Unit Economics e Eficiência de Capital** (avalie LTV/CAC, Margem Bruta, Burn e Alertas de Sanidade)
3. **Avaliação de Defensibilidade Tecnológica, Risco Regulatório e Cap Table**
4. **3 Recomendações Táticas Obrigatórias para os Próximos 90 Dias**
""".strip()

    return prompt, hash_contexto_ia


class ProvedorIA(ABC):
    """Interface abstrata para provedores de IA governados do SaaS."""

    provedor_nome: str = "abstrato"
    modelo_nome: str = "abstrato"
    custo_estimado_por_chamada_usd: float = 0.0

    @abstractmethod
    def gerar_parecer(
        self,
        prompt: str,
        ebt: ClienteEBT,
        resultado_simulacao: ResultadoSimulacaoSaaS,
    ) -> str:
        """Gera o parecer técnico em Markdown."""


class ProvedorGeminiIA(ProvedorIA):
    """Provedor integrado ao Google Gemini (`google-generativeai`)."""

    provedor_nome = "google-gemini"

    def __init__(self, api_key: str, modelo: str = "gemini-2.5-flash") -> None:
        self.api_key = api_key.strip()
        self.modelo_nome = modelo
        self.custo_estimado_por_chamada_usd = 0.0035

    def gerar_parecer(
        self,
        prompt: str,
        ebt: ClienteEBT,
        resultado_simulacao: ResultadoSimulacaoSaaS,
    ) -> str:
        try:
            from google import genai as _genai

            cliente = _genai.Client(api_key=self.api_key)
            resposta = cliente.models.generate_content(
                model=self.modelo_nome,
                contents=prompt,
            )
            return str(resposta.text or "").strip()
        except ImportError:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.modelo_nome)
            resposta = model.generate_content(prompt)
            return str(resposta.text or "").strip()


class ProvedorAuditoriaDeterministicoIA(ProvedorIA):
    """
    Provedor determinístico de Auditoria VC (Copiloto Institucional Interno).
    Gera pareceres estruturados de alta precisão baseados nas métricas do motor
    financeiro e nos alertas de sanidade, sem depender de chave externa e com custo zero.
    """

    provedor_nome = "motor-vc-governado-interno"
    modelo_nome = "vc-auditor-deterministico-v2"
    custo_estimado_por_chamada_usd = 0.0

    def gerar_parecer(
        self,
        prompt: str,
        ebt: ClienteEBT,
        resultado_simulacao: ResultadoSimulacaoSaaS,
    ) -> str:
        dre = resultado_simulacao.dre_base
        ue = resultado_simulacao.unit_economics
        viab = resultado_simulacao.viabilidade
        alertas = resultado_simulacao.alertas

        if resultado_simulacao.possui_alertas_criticos or ue.indice_ltv_cac < 1.5:
            veredito = "🔴 **REPROVAR / REESTRUTURAR PREMISSAS ANTES DO COMITÊ**"
        elif ue.indice_ltv_cac >= 3.0 and viab.valor_presente_liquido_vpl > 0:
            veredito = "🟢 **APROVAR PARA DUE DILIGENCE APROFUNDADA (TERM SHEET)**"
        else:
            veredito = "🟡 **APROVAR COM CONDICIONANTES DE EFICIÊNCIA COMERCIAL**"

        alertas_md = (
            "\n".join(
                f"- **{a.codigo}** (*{a.severidade.value.upper()}*): {a.mensagem} → *Ação recomendada*: {a.recomendacao}"
                for a in alertas
            )
            if alertas
            else "- Nenhuma anomalia matemática ou econômica detectada pelo validador pré-IA."
        )

        tir_str = (
            f"{viab.taxa_interna_retorno_anual_pct:.1f}% a.a."
            if viab.validade_da_tir
            else "Não aplicável (fluxo sem raiz única plausível)"
        )
        payback_cac_str = (
            f"{ue.meses_payback_cac:.1f} meses"
            if ue.meses_payback_cac is not None
            else "N/A"
        )

        return (
            f"### 1. Veredito Preliminar do Comitê\n"
            f"{veredito}\n\n"
            f"### 2. Análise Crítica de Unit Economics e Eficiência de Capital\n"
            f"- **Relação LTV/CAC ({ue.indice_ltv_cac:.2f}x)**: LTV estimado em R$ {ue.ltv_vitalicio_cliente:,.2f} "
            f"frente a um CAC de R$ {ue.cac_estimado:,.2f} (Payback de aquisição em **{payback_cac_str}**).\n"
            f"- **Margem Bruta SaaS ({dre.margem_bruta_pct:.1f}%)**: Receita Recorrente Mensal (MRR) inicial de "
            f"R$ {dre.mrr_bruto_total:,.2f} (ARR de R$ {dre.arr_anualizado:,.2f}).\n"
            f"- **Viabilidade de Longo Prazo**: VPL de **R$ {viab.valor_presente_liquido_vpl:,.2f}**, "
            f"CAPEX Inicial de **R$ {viab.capex_total:,.2f}**, Breakeven em **{viab.mes_de_breakeven_payback_texto}** e TIR de **{tir_str}**.\n\n"
            f"### 3. Diagnóstico de Sanidade Pré-IA e Riscos Mapeados\n"
            f"{alertas_md}\n\n"
            f"### 4. Recomendações Táticas para os Próximos 90 Dias\n"
            f"1. **Otimização de Retenção e Aquisição**: Manter monitoramento de coorte mensal para sustentar LTV/CAC ≥ 3.0x e CAC Payback ≤ 12 meses.\n"
            f"2. **Governança Societária e PI**: Formalizar registro de software/patente no INPI e contrato de *vesting* com *cliff* de 12 meses.\n"
            f"3. **Alocação do Runway**: Vincular cada tranche de desembolso de CAPEX/OPEX a metas auditáveis de MRR líquido."
        )


def solicitar_parecer_ia_governado(
    db: Session,
    *,
    membership: Membership,
    ebt_id: str,
    provedor_ia: Optional[ProvedorIA] = None,
    forcar_regeneracao: bool = False,
) -> Tuple[AnaliseIAEBT, JobAssincronoSaaS, bool]:
    """
    Executa ou recupera do cache um Parecer de IA governado para uma EBT:
    1. Valida RBAC (`IA_SOLICITAR_PARECER`).
    2. Calcula o snapshot da simulação e o hash determinístico do contexto sanitizado (sem PII).
    3. Se já existir `AnaliseIAEBT` para o mesmo `(tenant_id, ebt_id, hash_contexto_ia)`
       e `not forcar_regeneracao`, retorna do cache sem consumir quota nem gerar custo.
    4. Caso contrário, verifica o limite mensal (`limite_analises_ia_mes` do plano),
       registra `JobAssincronoSaaS`, invoca o provedor com texto livre de PII,
       adiciona o aviso obrigatório de governança, contabiliza uso/custo e grava `AuditLog`.
    Retorna `(analise_ia, job_assincrono, veio_do_cache)`.
    """
    verificar_permissao_rbac(
        membership, PermissaoSaaS.IA_SOLICITAR_PARECER, ebt_alvo_id=ebt_id
    )

    ebt = (
        db.query(ClienteEBT)
        .filter(
            ClienteEBT.tenant_id == membership.tenant_id,
            ClienteEBT.id == ebt_id,
        )
        .first()
    )
    if ebt is None:
        raise LookupError(f"Workspace EBT '{ebt_id}' não encontrado no Tenant.")

    entrada_pydantic = EntradaSimulacaoSaaS.from_orm_projeto(ebt)
    resultado_pydantic = executar_simulacao_saas(
        entrada_pydantic, cenario=TipoCenario.BASE
    )
    prompt_sanitizado, hash_contexto_ia = construir_prompt_vc_governado(
        ebt, resultado_pydantic
    )

    # 1. Consulta de Cache Inteligente por Hash de Contexto
    if not forcar_regeneracao:
        analise_cache = (
            db.query(AnaliseIAEBT)
            .filter(
                AnaliseIAEBT.tenant_id == membership.tenant_id,
                AnaliseIAEBT.ebt_id == ebt.id,
                AnaliseIAEBT.hash_entrada_simulacao == hash_contexto_ia,
            )
            .order_by(AnaliseIAEBT.criado_em.desc())
            .first()
        )
        if analise_cache is not None:
            job_cache = JobAssincronoSaaS(
                tenant_id=membership.tenant_id,
                ebt_id=ebt.id,
                tipo_job="ia.parecer.cache_hit",
                status=StatusJobAssincrono.CONCLUIDO.value,
                progresso_pct=100,
                referencia_resultado_id=analise_cache.id,
                criado_por_user_id=membership.user_id,
                concluido_em=datetime.now(timezone.utc),
            )
            db.add(job_cache)
            db.flush()
            return analise_cache, job_cache, True

    # 2. Verificação de Quota Mensal de IA do Plano Contratado
    assinatura = (
        db.query(AssinaturaTenant)
        .filter(AssinaturaTenant.tenant_id == membership.tenant_id)
        .first()
    )
    uso = obter_ou_criar_uso_mensal(db, membership.tenant_id)
    if (
        assinatura is not None
        and uso.analises_ia_realizadas >= assinatura.limite_analises_ia_mes
    ):
        raise ErroLimitePlanoSaaS(
            f"Quota mensal de Análises de IA atingida no plano '{assinatura.plano_codigo}' "
            f"({uso.analises_ia_realizadas}/{assinatura.limite_analises_ia_mes} no mês {uso.ano_mes})."
        )

    provedor = provedor_ia or ProvedorAuditoriaDeterministicoIA()

    # 3. Criação do Job Assíncrono Rastreável
    job = JobAssincronoSaaS(
        tenant_id=membership.tenant_id,
        ebt_id=ebt.id,
        tipo_job="ia.parecer",
        status=StatusJobAssincrono.PROCESSANDO.value,
        progresso_pct=30,
        criado_por_user_id=membership.user_id,
    )
    db.add(job)
    db.flush()

    try:
        corpo_md = provedor.gerar_parecer(
            prompt_sanitizado, ebt, resultado_pydantic
        )
        parecer_completo_md = BANNER_GOVERNANCA_IA + corpo_md.strip()
    except Exception as exc:
        job.status = StatusJobAssincrono.ERRO.value
        job.mensagem_erro = str(exc)[:500]
        job.concluido_em = datetime.now(timezone.utc)
        db.flush()
        raise

    ultimo_resultado_db = (
        db.query(ResultadoSimulacaoEBT)
        .filter(
            ResultadoSimulacaoEBT.tenant_id == membership.tenant_id,
            ResultadoSimulacaoEBT.ebt_id == ebt.id,
        )
        .order_by(ResultadoSimulacaoEBT.criado_em.desc())
        .first()
    )

    analise = AnaliseIAEBT(
        tenant_id=membership.tenant_id,
        ebt_id=ebt.id,
        resultado_simulacao_id=(
            ultimo_resultado_db.id if ultimo_resultado_db else None
        ),
        provedor=provedor.provedor_nome,
        modelo=provedor.modelo_nome,
        versao_prompt=VERSAO_PROMPT_VC,
        hash_entrada_simulacao=hash_contexto_ia,
        parecer_gerado_md=parecer_completo_md,
        parecer_revisado_consultor_md=None,
        aprovado_pelo_consultor=False,
        custo_estimado_usd=provedor.custo_estimado_por_chamada_usd,
    )
    db.add(analise)
    db.flush()

    job.status = StatusJobAssincrono.CONCLUIDO.value
    job.progresso_pct = 100
    job.referencia_resultado_id = analise.id
    job.concluido_em = datetime.now(timezone.utc)

    uso.analises_ia_realizadas += 1
    uso.custo_ia_acumulado_usd = round(
        float(uso.custo_ia_acumulado_usd or 0.0)
        + float(provedor.custo_estimado_por_chamada_usd),
        6,
    )
    db.flush()

    registrar_evento_auditoria(
        db,
        tenant_id=membership.tenant_id,
        user_id=membership.user_id,
        acao="ia.solicitar_parecer",
        entidade_tipo="AnaliseIAEBT",
        entidade_id=analise.id,
        resumo=(
            f"Parecer de IA gerado para '{ebt.nome_startup}' via {provedor.provedor_nome}/{provedor.modelo_nome} "
            f"[hash={hash_contexto_ia[:12]}, pendente de aprovação do consultor]."
        ),
        dados_novos={
            "provedor": provedor.provedor_nome,
            "modelo": provedor.modelo_nome,
            "versao_prompt": VERSAO_PROMPT_VC,
            "hash_entrada_simulacao": hash_contexto_ia,
            "custo_estimado_usd": provedor.custo_estimado_por_chamada_usd,
        },
    )

    return analise, job, False


def revisar_e_aprovar_parecer_ia(
    db: Session,
    *,
    membership: Membership,
    analise_id: str,
    texto_revisado_md: Optional[str] = None,
) -> AnaliseIAEBT:
    """
    Homologa e aprova o parecer de IA por um Consultor/Admin/Dono habilitado
    (`PermissaoSaaS.IA_APROVAR_PARECER`), liberando-o como parecer oficial revisado
    para inclusão no Dossiê Executivo PDF.
    """
    analise = (
        db.query(AnaliseIAEBT)
        .filter(
            AnaliseIAEBT.tenant_id == membership.tenant_id,
            AnaliseIAEBT.id == analise_id,
        )
        .first()
    )
    if analise is None:
        raise LookupError(f"Análise de IA '{analise_id}' não encontrada no Tenant.")

    verificar_permissao_rbac(
        membership, PermissaoSaaS.IA_APROVAR_PARECER, ebt_alvo_id=analise.ebt_id
    )

    texto_final = (
        texto_revisado_md.strip()
        if texto_revisado_md and texto_revisado_md.strip()
        else analise.parecer_gerado_md
    )
    analise.parecer_revisado_consultor_md = texto_final
    analise.aprovado_pelo_consultor = True
    analise.aprovado_por_user_id = membership.user_id
    db.flush()

    registrar_evento_auditoria(
        db,
        tenant_id=membership.tenant_id,
        user_id=membership.user_id,
        acao="ia.aprovar_parecer",
        entidade_tipo="AnaliseIAEBT",
        entidade_id=analise.id,
        resumo=f"Parecer de IA '{analise.id[:8]}' revisado e homologado pelo consultor.",
        dados_novos={
            "aprovado_pelo_consultor": True,
            "aprovado_por_user_id": membership.user_id,
        },
    )

    return analise
