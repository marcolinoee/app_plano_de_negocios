"""
Fila de Jobs Assíncronos e Storage de Dossiês PDF com URL Assinada e Hash SHA-256
(Fase 3 - Seções 4.2, 5 e 6 do Plano SaaS).
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from .auditoria import registrar_evento_auditoria
from .models import (
    AnaliseIAEBT,
    AssinaturaTenant,
    ClienteEBT,
    JobAssincronoSaaS,
    Membership,
    RelatorioDossieEBT,
    ResultadoSimulacaoEBT,
    StatusJobAssincrono,
)
from .rbac import PermissaoSaaS, verificar_permissao_rbac
from .servicos import (
    ErroLimitePlanoSaaS,
    executar_e_versionar_simulacao_ebt,
    obter_ou_criar_uso_mensal,
)


class StorageDossieLocal:
    """
    Provedor de Object Storage (compatível com semântica S3 / Cloudflare R2 / GCS)
    com armazenamento segregado por `tenant_id/ebt_id` e geração de URLs assinadas
    com expiração via HMAC-SHA256.
    """

    def __init__(
        self,
        diretorio_base: Optional[str] = None,
        segredo_assinatura: Optional[str] = None,
    ) -> None:
        raiz_padrao = Path(__file__).resolve().parent.parent / "storage_dossies"
        self.diretorio_base = Path(diretorio_base) if diretorio_base else raiz_padrao
        self.segredo_assinatura = (
            segredo_assinatura
            or os.getenv("MM_STORAGE_HMAC_SECRET", "mm-saas-storage-secret-key-2026")
        ).encode("utf-8")

    def salvar_pdf(
        self,
        *,
        tenant_id: str,
        ebt_id: str,
        pdf_bytes: bytes,
    ) -> Tuple[str, str]:
        """
        Persiste os bytes do PDF no bucket/diretório isolado do Tenant e retorna
        `(storage_key, sha256_pdf)`.
        """
        sha256_pdf = hashlib.sha256(pdf_bytes).hexdigest()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        nome_arquivo = f"dossie_{timestamp}_{sha256_pdf[:12]}.pdf"
        storage_key = f"tenants/{tenant_id}/ebts/{ebt_id}/dossies/{nome_arquivo}"

        caminho_completo = self.diretorio_base / storage_key
        caminho_completo.parent.mkdir(parents=True, exist_ok=True)
        caminho_completo.write_bytes(pdf_bytes)

        return storage_key, sha256_pdf

    def gerar_url_assinada(
        self,
        storage_key: str,
        *,
        expira_em_segundos: int = 3600,
        endpoint_base: str = "https://storage.mastermanagement.saas/v1/download",
    ) -> str:
        """
        Gera uma URL pré-assinada com expiração (estilo S3 Presigned URL)
        autenticada via HMAC-SHA256.
        """
        expira_ts = int(
            (
                datetime.now(timezone.utc)
                + timedelta(seconds=max(60, expira_em_segundos))
            ).timestamp()
        )
        mensagem = f"{storage_key}:{expira_ts}".encode("utf-8")
        assinatura = hmac.new(
            self.segredo_assinatura, mensagem, hashlib.sha256
        ).hexdigest()
        query = urlencode(
            {
                "key": storage_key,
                "expires": expira_ts,
                "signature": assinatura,
            }
        )
        return f"{endpoint_base}?{query}"


def registrar_emissao_dossie_pdf(
    db: Session,
    *,
    membership: Membership,
    ebt_id: str,
    pdf_bytes: bytes,
    storage: Optional[StorageDossieLocal] = None,
    exigir_parecer_aprovado: bool = False,
) -> Tuple[RelatorioDossieEBT, JobAssincronoSaaS, str]:
    """
    Registra e audita a geração de um Dossiê Executivo PDF:
    1. Valida RBAC (`PermissaoSaaS.DOSSIE_EXPORTAR_PDF`).
    2. Verifica quota mensal de PDFs (`limite_pdfs_mes` do plano contratado).
    3. Se `exigir_parecer_aprovado=True`, exige que a última análise de IA da EBT
       esteja homologada por um consultor (`aprovado_pelo_consultor=True`).
    4. Garante que haja um snapshot imutável `ResultadoSimulacaoEBT` vinculado.
    5. Salva o binário no Storage com hash SHA-256, cria `RelatorioDossieEBT` e
       `JobAssincronoSaaS`, incrementa `uso.pdfs_gerados` e grava `AuditLog`.
    Retorna `(relatorio_dossie, job_assincrono, url_assinada)`.
    """
    verificar_permissao_rbac(
        membership, PermissaoSaaS.DOSSIE_EXPORTAR_PDF, ebt_alvo_id=ebt_id
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

    assinatura = (
        db.query(AssinaturaTenant)
        .filter(AssinaturaTenant.tenant_id == membership.tenant_id)
        .first()
    )
    uso = obter_ou_criar_uso_mensal(db, membership.tenant_id)
    if assinatura is not None and uso.pdfs_gerados >= assinatura.limite_pdfs_mes:
        raise ErroLimitePlanoSaaS(
            f"Quota mensal de Dossiês PDF atingida no plano '{assinatura.plano_codigo}' "
            f"({uso.pdfs_gerados}/{assinatura.limite_pdfs_mes} no mês {uso.ano_mes})."
        )

    if exigir_parecer_aprovado:
        ultima_analise = (
            db.query(AnaliseIAEBT)
            .filter(
                AnaliseIAEBT.tenant_id == membership.tenant_id,
                AnaliseIAEBT.ebt_id == ebt.id,
            )
            .order_by(AnaliseIAEBT.criado_em.desc())
            .first()
        )
        if ultima_analise is None or not ultima_analise.aprovado_pelo_consultor:
            raise PermissionError(
                "A emissão oficial homologada exige que o Parecer de IA tenha sido "
                "revisado e aprovado por um Consultor responsável."
            )

    # Garante snapshot imutável da simulação para rastreabilidade do PDF
    ultimo_resultado = (
        db.query(ResultadoSimulacaoEBT)
        .filter(
            ResultadoSimulacaoEBT.tenant_id == membership.tenant_id,
            ResultadoSimulacaoEBT.ebt_id == ebt.id,
        )
        .order_by(ResultadoSimulacaoEBT.criado_em.desc())
        .first()
    )
    if ultimo_resultado is None:
        _, ultimo_resultado, _ = executar_e_versionar_simulacao_ebt(
            db, membership=membership, ebt_id=ebt.id
        )

    job = JobAssincronoSaaS(
        tenant_id=membership.tenant_id,
        ebt_id=ebt.id,
        tipo_job="pdf.dossie",
        status=StatusJobAssincrono.PROCESSANDO.value,
        progresso_pct=50,
        criado_por_user_id=membership.user_id,
    )
    db.add(job)
    db.flush()

    provedor_storage = storage or StorageDossieLocal()
    storage_key, sha256_pdf = provedor_storage.salvar_pdf(
        tenant_id=membership.tenant_id,
        ebt_id=ebt.id,
        pdf_bytes=pdf_bytes,
    )
    url_assinada = provedor_storage.gerar_url_assinada(storage_key)

    relatorio = RelatorioDossieEBT(
        tenant_id=membership.tenant_id,
        ebt_id=ebt.id,
        resultado_simulacao_id=ultimo_resultado.id,
        storage_key=storage_key,
        sha256_pdf=sha256_pdf,
        criado_por_user_id=membership.user_id,
    )
    db.add(relatorio)
    db.flush()

    job.status = StatusJobAssincrono.CONCLUIDO.value
    job.progresso_pct = 100
    job.referencia_resultado_id = relatorio.id
    job.concluido_em = datetime.now(timezone.utc)

    uso.pdfs_gerados += 1
    db.flush()

    registrar_evento_auditoria(
        db,
        tenant_id=membership.tenant_id,
        user_id=membership.user_id,
        acao="dossie.exportar_pdf",
        entidade_tipo="RelatorioDossieEBT",
        entidade_id=relatorio.id,
        resumo=(
            f"Dossiê Executivo PDF emitido para '{ebt.nome_startup}' "
            f"[sha256={sha256_pdf[:12]}, sim_id={ultimo_resultado.id[:8]}]."
        ),
        dados_novos={
            "storage_key": storage_key,
            "sha256_pdf": sha256_pdf,
            "resultado_simulacao_id": ultimo_resultado.id,
        },
    )

    return relatorio, job, url_assinada


def listar_jobs_tenant(
    db: Session,
    *,
    tenant_id: str,
    ebt_id: Optional[str] = None,
    limite: int = 25,
) -> List[JobAssincronoSaaS]:
    """Lista os jobs assíncronos recentes do Tenant (opcionalmente filtrados por EBT)."""
    query = db.query(JobAssincronoSaaS).filter(
        JobAssincronoSaaS.tenant_id == tenant_id
    )
    if ebt_id:
        query = query.filter(JobAssincronoSaaS.ebt_id == ebt_id)
    return query.order_by(JobAssincronoSaaS.criado_em.desc()).limit(limite).all()


def _limpar_latin1(texto: Optional[str]) -> str:
    if not texto:
        return ""
    substituicoes = {
        "—": "-",
        "–": "-",
        "•": "-",
        "·": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "≥": ">=",
        "≤": "<=",
        "→": "->",
    }
    limpo = str(texto)
    for k, v in substituicoes.items():
        limpo = limpo.replace(k, v)
    return limpo.encode("latin-1", "ignore").decode("latin-1")


def gerar_pdf_executivo_ebt_bytes(
    *,
    ebt: ClienteEBT,
    resultado_simulacao: object,
    tenant_nome: str,
    permite_white_label: bool = False,
    parecer_md: Optional[str] = None,
) -> bytes:
    """
    Constrói o binário A4 do Dossiê Executivo de Investimento (Term Sheet & Due Diligence)
    para exportação via API `/v1` e arquivamento assinado.
    """
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Página 1 — Folha de Rosto White-Label
    pdf.add_page()
    pdf.set_font("helvetica", "B", 10)
    selo = (
        f"DOSSIE INSTITUCIONAL WHITE-LABEL - {_limpar_latin1(tenant_nome.upper())}"
        if permite_white_label
        else f"PREPARADO POR: {_limpar_latin1(tenant_nome.upper())} (MASTER MANAGEMENT SAAS)"
    )
    pdf.cell(pdf.epw, 8, selo, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(25)
    pdf.set_font("helvetica", "B", 22)
    pdf.cell(
        pdf.epw,
        14,
        "MEMORANDO EXECUTIVO DE INVESTIMENTO",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="C",
    )
    pdf.set_font("helvetica", "B", 18)
    pdf.cell(
        pdf.epw,
        12,
        _limpar_latin1(ebt.nome_startup.upper()),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="C",
    )
    pdf.ln(10)

    dre = getattr(resultado_simulacao, "dre_base", None)
    ue = getattr(resultado_simulacao, "unit_economics", None)
    viab = getattr(resultado_simulacao, "viabilidade", None)

    pdf.set_font("helvetica", "", 12)
    if dre and ue and viab:
        linhas_capa = [
            f"Vertical: {_limpar_latin1(ebt.setor_vertical)} | Estagio: {_limpar_latin1(ebt.estagio)}",
            f"MRR Consolidado Inicial: R$ {dre.mrr_bruto_total:,.2f} | ARR: R$ {dre.arr_anualizado:,.2f}",
            f"Ticket Medio Pago (ARPU): R$ {ue.ticket_medio_arpu:,.2f} | LTV/CAC: {ue.indice_ltv_cac:.2f}x",
            f"VPL Projetado: R$ {viab.valor_presente_liquido_vpl:,.2f} | CAPEX: R$ {viab.capex_total:,.2f}",
            f"Breakeven / Payback: {_limpar_latin1(viab.mes_de_breakeven_payback_texto)}",
        ]
        for linha in linhas_capa:
            pdf.cell(
                pdf.epw, 9, linha, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C"
            )

    # Página 2 — Lean Canvas & Parecer do Comitê VC
    pdf.add_page()
    pdf.set_font("helvetica", "B", 15)
    pdf.cell(
        pdf.epw,
        10,
        "I. Tese Estrategica e Lean Canvas",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(3)

    lc = ebt.lean_canvas
    if lc:
        blocos = [
            ("Problema de Mercado", lc.problema),
            ("Arquitetura da Solucao e MVP", lc.solucao_mvp),
            ("Proposta Unica de Valor", lc.proposta_valor),
            ("Vantagem Injusta (Moat)", lc.vantagem_injusta),
            ("Canais e Go-To-Market", lc.canais),
        ]
        for titulo, conteudo in blocos:
            pdf.set_font("helvetica", "B", 11)
            pdf.cell(
                pdf.epw, 7, _limpar_latin1(titulo), new_x=XPos.LMARGIN, new_y=YPos.NEXT
            )
            pdf.set_font("helvetica", "", 10)
            pdf.multi_cell(pdf.epw, 6, _limpar_latin1(conteudo or "Nao informado."))
            pdf.ln(2)

    if parecer_md:
        pdf.add_page()
        pdf.set_font("helvetica", "B", 15)
        pdf.cell(
            pdf.epw,
            10,
            "II. Parecer do Comite de Investimento (Governanca IA)",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.ln(3)
        pdf.set_font("helvetica", "", 10)
        texto_limpo = _limpar_latin1(parecer_md.replace("**", "").replace("### ", ""))
        pdf.multi_cell(pdf.epw, 6, texto_limpo)

    return bytes(pdf.output())
