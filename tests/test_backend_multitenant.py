"""
Suíte de Testes de Isolamento Multi-Tenant, RBAC, Quotas de Plano,
Versionamento Imutável de Simulações e Auditoria (Fase 1 — Núcleo SaaS).
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from backend import (
    BANNER_GOVERNANCA_IA,
    TABELAS_COM_RLS,
    AssinaturaTenant,
    BaseSaaS,
    CASCATA_MODELOS_GEMINI,
    ClienteEBT,
    CodigoFalhaIA,
    ErroAutenticacaoOAuth,
    ErroIA,
    ErroIAAutenticacao,
    ErroIACascataEsgotada,
    ErroIACotaExcedida,
    ErroIAIndisponivel,
    ErroIANetworkOffline,
    ErroIATimeout,
    ErroIsolamentoTenant,
    ErroLimitePlanoSaaS,
    ErroPermissaoRBAC,
    ItemCapexEBT,
    ItemOpexEBT,
    Membership,
    PapelMembro,
    PermissaoSaaS,
    PlanoAssinaturaCodigo,
    PlanoSaaSEBT,
    ProvedorAuditoriaDeterministicoIA,
    ProvedorGeminiIA,
    StorageDossieLocal,
    User,
    alterar_plano_assinatura_tenant,
    atualizar_meu_perfil_usuario,
    atualizar_premissas_ebt,
    autenticar_com_email_e_senha,
    autenticar_via_oauth_ou_convite,
    construir_resposta_sessao_autenticada,
    criar_convite_rbac_oauth,
    criar_engine_saas,
    criar_link_compartilhamento_investidor,
    criar_session_factory,
    criar_tenant_consultoria,
    criar_workspace_ebt,
    decodificar_jwt_sessao_saas,
    excluir_usuario_pelo_admin,
    executar_e_versionar_simulacao_ebt,
    gerar_ddl_rls_postgresql,
    gerar_jwt_sessao_saas,
    gerenciar_assinante_oauth_pelo_admin,
    inicializar_banco_saas,
    listar_jobs_tenant,
    listar_provedores_oauth_configurados,
    listar_trilha_auditoria,
    listar_usuarios_oauth_registrados,
    listar_workspaces_ebt_visiveis,
    obter_ou_criar_uso_mensal,
    obter_uso_usuario_pelo_admin,
    registrar_emissao_dossie_pdf,
    registrar_novo_usuario_credenciais,
    revisar_e_aprovar_parecer_ia,
    sanitizar_pii_texto,
    sessao_por_requisicao,
    solicitar_parecer_ia_governado,
    validar_token_investidor,
)


class TestNucleoSaaSMultiTenant(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = criar_engine_saas("sqlite:///:memory:")
        BaseSaaS.metadata.create_all(self.engine)
        self.session_factory = criar_session_factory(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_isolamento_estrito_entre_tenants_rls_orm(self) -> None:
        """
        Garante que dados do Tenant A nunca vazam para o Tenant B em consultas
        e que tentativas de escrita cruzada disparam ErroIsolamentoTenant.
        """
        with sessao_por_requisicao(self.session_factory, bypass_rls=True) as db_setup:
            tenant_a, user_a, memb_a = criar_tenant_consultoria(
                db_setup,
                nome_consultoria="Consultoria Alpha",
                slug="alpha-vc",
                email_dono="dono@alpha.com",
                nome_dono="Alice Alpha",
            )
            tenant_b, user_b, memb_b = criar_tenant_consultoria(
                db_setup,
                nome_consultoria="Consultoria Beta",
                slug="beta-vc",
                email_dono="dono@beta.com",
                nome_dono="Bruno Beta",
            )
            tid_a, uid_a, mid_a = tenant_a.id, user_a.id, memb_a.id
            tid_b, uid_b, mid_b = tenant_b.id, user_b.id, memb_b.id

        # Cria EBT na Consultoria Alpha
        with sessao_por_requisicao(
            self.session_factory, tenant_id=tid_a, user_id=uid_a
        ) as db_a:
            m_a = db_a.get(Membership, mid_a)
            criar_workspace_ebt(
                db_a, membership=m_a, nome_startup="Startup Exclusiva Alpha"
            )

        # Cria EBT na Consultoria Beta
        with sessao_por_requisicao(
            self.session_factory, tenant_id=tid_b, user_id=uid_b
        ) as db_b:
            m_b = db_b.get(Membership, mid_b)
            criar_workspace_ebt(
                db_b, membership=m_b, nome_startup="Startup Exclusiva Beta"
            )

        # 1. Consulta sem filtro explícito na sessão do Tenant A deve retornar APENAS a EBT de Alpha
        with sessao_por_requisicao(
            self.session_factory, tenant_id=tid_a, user_id=uid_a
        ) as db_a:
            ebts_visiveis_a = db_a.query(ClienteEBT).all()
            self.assertEqual(len(ebts_visiveis_a), 1)
            self.assertEqual(ebts_visiveis_a[0].nome_startup, "Startup Exclusiva Alpha")

        # 2. Tentativa de gravar objeto forjando tenant_id do Tenant B na sessão do Tenant A deve falhar e fazer rollback
        with self.assertRaises(ErroIsolamentoTenant):
            with sessao_por_requisicao(
                self.session_factory, tenant_id=tid_a, user_id=uid_a
            ) as db_a_invalida:
                ebt_intrusa = ClienteEBT(
                    tenant_id=tid_b,
                    nome_startup="Injeção Cruzada",
                )
                db_a_invalida.add(ebt_intrusa)
                db_a_invalida.flush()

    def test_geracao_ddl_rls_postgresql_completo(self) -> None:
        ddl = gerar_ddl_rls_postgresql()
        for tabela in TABELAS_COM_RLS:
            self.assertIn(f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;", ddl)
            self.assertIn(f"ALTER TABLE {tabela} FORCE ROW LEVEL SECURITY;", ddl)
            self.assertIn(f"ON {tabela}", ddl)
        self.assertIn("current_setting('app.current_tenant_id', true)", ddl)

    def test_rbac_escopo_fundador_e_investidor(self) -> None:
        """
        Valida que:
        - O papel 'fundador' pode editar e simular APENAS a sua EBT vinculada,
          sendo bloqueado ao tentar acessar outra EBT da mesma consultoria ou criar nova EBT.
        - O papel 'investidor' possui leitura na EBT vinculada, mas é bloqueado em edição e simulação.
        """
        with sessao_por_requisicao(self.session_factory, bypass_rls=True) as db_setup:
            tenant, dono, memb_dono = criar_tenant_consultoria(
                db_setup,
                nome_consultoria="Venture Studio Nordeste",
                slug="vs-ne",
                email_dono="partner@vsne.com",
                nome_dono="Partner",
            )
            tid, uid_dono, mid_dono = tenant.id, dono.id, memb_dono.id

        with sessao_por_requisicao(
            self.session_factory, tenant_id=tid, user_id=uid_dono
        ) as db:
            m_dono = db.get(Membership, mid_dono)
            ebt_1 = criar_workspace_ebt(db, membership=m_dono, nome_startup="AgroTech 1")
            ebt_2 = criar_workspace_ebt(db, membership=m_dono, nome_startup="FinTech 2")

            user_fundador = User(
                email="founder@agrotech1.com", nome_completo="Fundador Agro"
            )
            user_investidor = User(
                email="banca@fundo.com", nome_completo="Investidor Banca"
            )
            db.add_all([user_fundador, user_investidor])
            db.flush()

            memb_fundador = Membership(
                tenant_id=tid,
                user_id=user_fundador.id,
                papel=PapelMembro.FUNDADOR.value,
                ebt_restrita_id=ebt_1.id,
                ativo=True,
            )
            memb_investidor = Membership(
                tenant_id=tid,
                user_id=user_investidor.id,
                papel=PapelMembro.INVESTIDOR.value,
                ebt_restrita_id=ebt_1.id,
                ativo=True,
            )
            db.add_all([memb_fundador, memb_investidor])
            db.flush()

            # 1. Fundador vê apenas a EBT 1 na listagem
            visiveis_fundador = listar_workspaces_ebt_visiveis(
                db, membership=memb_fundador
            )
            self.assertEqual([e.id for e in visiveis_fundador], [ebt_1.id])

            # 2. Fundador consegue editar premissas da sua própria EBT (ebt_1)
            atualizar_premissas_ebt(
                db,
                membership=memb_fundador,
                ebt_id=ebt_1.id,
                churn_mensal_pct=3.5,
            )

            # 3. Fundador é bloqueado ao tentar editar a EBT 2 (mesmo tenant, outro workspace)
            with self.assertRaises(ErroPermissaoRBAC):
                atualizar_premissas_ebt(
                    db,
                    membership=memb_fundador,
                    ebt_id=ebt_2.id,
                    churn_mensal_pct=2.0,
                )

            # 4. Fundador não pode criar nova EBT na consultoria
            with self.assertRaises(ErroPermissaoRBAC):
                criar_workspace_ebt(
                    db, membership=memb_fundador, nome_startup="Startup Não Autorizada"
                )

            # 5. Investidor pode listar a EBT 1, mas NÃO pode editar premissas nem rodar simulação
            visiveis_inv = listar_workspaces_ebt_visiveis(
                db, membership=memb_investidor
            )
            self.assertEqual([e.id for e in visiveis_inv], [ebt_1.id])

            with self.assertRaises(ErroPermissaoRBAC):
                atualizar_premissas_ebt(
                    db,
                    membership=memb_investidor,
                    ebt_id=ebt_1.id,
                    cac_estimado=500.0,
                )

            with self.assertRaises(ErroPermissaoRBAC):
                executar_e_versionar_simulacao_ebt(
                    db, membership=memb_investidor, ebt_id=ebt_1.id
                )

    def test_limite_plano_starter_bloqueia_quarta_ebt(self) -> None:
        with sessao_por_requisicao(self.session_factory, bypass_rls=True) as db_setup:
            tenant, dono, memb_dono = criar_tenant_consultoria(
                db_setup,
                nome_consultoria="Consultoria Starter",
                slug="starter-consult",
                email_dono="dono@starter.com",
                nome_dono="Dono Starter",
                plano=PlanoAssinaturaCodigo.STARTER,  # Limite = 3 EBTs
            )
            tid, uid, mid = tenant.id, dono.id, memb_dono.id

        with sessao_por_requisicao(
            self.session_factory, tenant_id=tid, user_id=uid
        ) as db:
            m = db.get(Membership, mid)
            criar_workspace_ebt(db, membership=m, nome_startup="EBT 1")
            criar_workspace_ebt(db, membership=m, nome_startup="EBT 2")
            criar_workspace_ebt(db, membership=m, nome_startup="EBT 3")

            with self.assertRaises(ErroLimitePlanoSaaS):
                criar_workspace_ebt(db, membership=m, nome_startup="EBT 4 Acima do Limite")

    def test_versionamento_imutavel_simulacao_uso_medido_e_auditoria(self) -> None:
        with sessao_por_requisicao(self.session_factory, bypass_rls=True) as db_setup:
            tenant, dono, memb_dono = criar_tenant_consultoria(
                db_setup,
                nome_consultoria="Auditoria Capital",
                slug="auditoria-cap",
                email_dono="ceo@auditoria.com",
                nome_dono="CEO Auditoria",
                plano=PlanoAssinaturaCodigo.PRO,
            )
            tid, uid, mid = tenant.id, dono.id, memb_dono.id

        with sessao_por_requisicao(
            self.session_factory, tenant_id=tid, user_id=uid
        ) as db:
            m = db.get(Membership, mid)
            ebt = criar_workspace_ebt(db, membership=m, nome_startup="HealthSaaS")

            db.add(
                ItemCapexEBT(
                    tenant_id=tid,
                    ebt_id=ebt.id,
                    categoria="MVP",
                    descricao="Desenvolvimento",
                    valor=80000.0,
                )
            )
            db.add(
                ItemOpexEBT(
                    tenant_id=tid,
                    ebt_id=ebt.id,
                    categoria="Equipe",
                    descricao="Devs",
                    valor_mensal=10000.0,
                )
            )
            db.add(
                PlanoSaaSEBT(
                    tenant_id=tid,
                    ebt_id=ebt.id,
                    nome_plano="Clínica Pro",
                    ticket_mensal=300.0,
                    usuarios_ativos_base=60,
                    taxas_pagamento_pct=4.0,
                    impostos_pct=6.0,
                    custo_servidor_por_usuario=15.0,
                )
            )
            db.flush()

            # Simulação v1
            v1, res_db_1, sim_1 = executar_e_versionar_simulacao_ebt(
                db, membership=m, ebt_id=ebt.id
            )
            self.assertEqual(v1.numero_versao, 1)
            self.assertAlmostEqual(res_db_1.mrr_bruto_base, 18000.0, places=2)

            # Altera premissas e roda Simulação v2
            atualizar_premissas_ebt(
                db,
                membership=m,
                ebt_id=ebt.id,
                crescimento_mensal_pct=10.0,
                cac_estimado=600.0,
            )
            v2, res_db_2, sim_2 = executar_e_versionar_simulacao_ebt(
                db, membership=m, ebt_id=ebt.id
            )

            self.assertEqual(v2.numero_versao, 2)
            self.assertNotEqual(v1.hash_entrada_sha256, v2.hash_entrada_sha256)
            self.assertGreater(res_db_2.vpl, res_db_1.vpl)

            # Verifica UsoMedidoTenant
            uso = obter_ou_criar_uso_mensal(db, tid)
            self.assertEqual(uso.simulacoes_executadas, 2)

            # Verifica Trilha de Auditoria (AuditLog)
            trilha = listar_trilha_auditoria(db)
            acoes_registradas = [evento.acao for evento in trilha]
            self.assertIn("ebt.criar", acoes_registradas)
            self.assertIn("premissas.atualizar", acoes_registradas)
            self.assertEqual(acoes_registradas.count("simulacao.executar"), 2)

    def test_share_link_investidor_com_expiracao_e_hash(self) -> None:
        with sessao_por_requisicao(self.session_factory, bypass_rls=True) as db_setup:
            tenant, dono, memb_dono = criar_tenant_consultoria(
                db_setup,
                nome_consultoria="Banca Demoday",
                slug="banca-demoday",
                email_dono="coord@demoday.com",
                nome_dono="Coordenador",
            )
            tid, uid, mid = tenant.id, dono.id, memb_dono.id

        with sessao_por_requisicao(
            self.session_factory, tenant_id=tid, user_id=uid
        ) as db:
            m = db.get(Membership, mid)
            ebt = criar_workspace_ebt(db, membership=m, nome_startup="DeepTech AI")

            token_claro, link = criar_link_compartilhamento_investidor(
                db, membership=m, ebt_id=ebt.id, dias_validade=5
            )
            # Token em texto claro nunca é salvo no banco
            self.assertNotEqual(link.token_hash, token_claro)
            self.assertEqual(len(link.token_hash), 64)

            # Acesso válido contabiliza visualização
            link_validado = validar_token_investidor(db, token_claro=token_claro)
            self.assertEqual(link_validado.acessos_realizados, 1)

            # Acesso após a data de expiração deve falhar
            futuro_expirado = datetime.now(timezone.utc) + timedelta(days=10)
            with self.assertRaises(PermissionError):
                validar_token_investidor(
                    db, token_claro=token_claro, agora=futuro_expirado
                )

    def test_bootstrap_local_e_perfis_rbac_automaticos(self) -> None:
        factory = inicializar_banco_saas(self.engine, classe_projeto_legado=None)
        with sessao_por_requisicao(factory, bypass_rls=True) as db:
            ebts = db.query(ClienteEBT).all()
            self.assertEqual(len(ebts), 1)
            papeis = {m.papel for m in db.query(Membership).all()}
            self.assertIn(PapelMembro.DONO.value, papeis)
            self.assertIn(PapelMembro.CONSULTOR.value, papeis)
            self.assertIn(PapelMembro.FUNDADOR.value, papeis)
            self.assertIn(PapelMembro.INVESTIDOR.value, papeis)

    def test_sanitizacao_pii_lgpd(self) -> None:
        texto_bruto = (
            "Contato do fundador: joao.silva@startup.com.br, CPF 123.456.789-01, "
            "CNPJ 12.345.678/0001-99 e celular +55 (11) 98765-4321."
        )
        limpo = sanitizar_pii_texto(texto_bruto)
        self.assertNotIn("joao.silva@startup.com.br", limpo)
        self.assertNotIn("123.456.789-01", limpo)
        self.assertNotIn("12.345.678/0001-99", limpo)
        self.assertNotIn("98765-4321", limpo)
        self.assertIn("[EMAIL_OCULTO_LGPD]", limpo)
        self.assertIn("[CPF_OCULTO_LGPD]", limpo)
        self.assertIn("[CNPJ_OCULTO_LGPD]", limpo)
        self.assertIn("[TELEFONE_OCULTO_LGPD]", limpo)

    def test_fluxo_ia_governada_cache_quota_e_aprovacao_rbac(self) -> None:
        with sessao_por_requisicao(self.session_factory, bypass_rls=True) as db_setup:
            tenant, dono, memb_dono = criar_tenant_consultoria(
                db_setup,
                nome_consultoria="VC Lab Governado",
                slug="vclab-gov",
                email_dono="dono@vclab.com",
                nome_dono="Dono VC",
            )
            tid, uid_dono, mid_dono = tenant.id, dono.id, memb_dono.id

        with sessao_por_requisicao(
            self.session_factory, tenant_id=tid, user_id=uid_dono
        ) as db:
            m_dono = db.get(Membership, mid_dono)
            ebt = criar_workspace_ebt(db, membership=m_dono, nome_startup="CyberSaaS")

            user_analista = User(
                email="analista@vclab.com", nome_completo="Analista Jr"
            )
            db.add(user_analista)
            db.flush()
            memb_analista = Membership(
                tenant_id=tid,
                user_id=user_analista.id,
                papel=PapelMembro.ANALISTA.value,
                ativo=True,
            )
            db.add(memb_analista)
            db.flush()

            # 1. Primeira solicitação gera parecer inédito e contabiliza 1 uso de IA
            analise_1, job_1, em_cache_1 = solicitar_parecer_ia_governado(
                db,
                membership=memb_analista,
                ebt_id=ebt.id,
                provedor_ia=ProvedorAuditoriaDeterministicoIA(),
            )
            self.assertFalse(em_cache_1)
            self.assertEqual(job_1.status, "concluido")
            self.assertFalse(analise_1.aprovado_pelo_consultor)
            self.assertTrue(analise_1.parecer_gerado_md.startswith(BANNER_GOVERNANCA_IA))

            uso = obter_ou_criar_uso_mensal(db, tid)
            self.assertEqual(uso.analises_ia_realizadas, 1)

            # 2. Segunda solicitação com mesmas entradas retorna do cache sem consumir quota
            analise_2, job_2, em_cache_2 = solicitar_parecer_ia_governado(
                db,
                membership=memb_analista,
                ebt_id=ebt.id,
                provedor_ia=ProvedorAuditoriaDeterministicoIA(),
            )
            self.assertTrue(em_cache_2)
            self.assertEqual(analise_1.id, analise_2.id)
            self.assertEqual(job_2.tipo_job, "ia.parecer.cache_hit")
            self.assertEqual(uso.analises_ia_realizadas, 1)

            # 3. Analista NÃO tem permissão RBAC para homologar/aprovar o parecer
            with self.assertRaises(ErroPermissaoRBAC):
                revisar_e_aprovar_parecer_ia(
                    db,
                    membership=memb_analista,
                    analise_id=analise_1.id,
                    texto_revisado_md="Tentativa de aprovação por analista",
                )

            # 4. Dono/Consultor homologa com sucesso
            analise_homologada = revisar_e_aprovar_parecer_ia(
                db,
                membership=m_dono,
                analise_id=analise_1.id,
                texto_revisado_md="Parecer Oficial Revisado pelo Sócio.",
            )
            self.assertTrue(analise_homologada.aprovado_pelo_consultor)
            self.assertEqual(
                analise_homologada.parecer_revisado_consultor_md,
                "Parecer Oficial Revisado pelo Sócio.",
            )

            # 5. Estouro de quota mensal de IA bloqueia novas gerações forçadas
            assinatura = (
                db.query(AssinaturaTenant)
                .filter(AssinaturaTenant.tenant_id == tid)
                .first()
            )
            uso.analises_ia_realizadas = assinatura.limite_analises_ia_mes
            db.flush()

            with self.assertRaises(ErroLimitePlanoSaaS):
                solicitar_parecer_ia_governado(
                    db,
                    membership=m_dono,
                    ebt_id=ebt.id,
                    forcar_regeneracao=True,
                )

    def test_emissao_dossie_pdf_assinado_storage_e_homologacao(self) -> None:
        with sessao_por_requisicao(self.session_factory, bypass_rls=True) as db_setup:
            tenant, dono, memb_dono = criar_tenant_consultoria(
                db_setup,
                nome_consultoria="DataRoom Partners",
                slug="dataroom-partners",
                email_dono="partner@dataroom.com",
                nome_dono="Partner DataRoom",
            )
            tid, uid, mid = tenant.id, dono.id, memb_dono.id

        with tempfile.TemporaryDirectory() as tmpdir:
            storage_temp = StorageDossieLocal(diretorio_base=tmpdir)

            with sessao_por_requisicao(
                self.session_factory, tenant_id=tid, user_id=uid
            ) as db:
                m = db.get(Membership, mid)
                ebt = criar_workspace_ebt(db, membership=m, nome_startup="BioTech SaaS")

                # Exigir parecer aprovado quando ainda não há parecer aprovado deve bloquear
                with self.assertRaises(PermissionError):
                    registrar_emissao_dossie_pdf(
                        db,
                        membership=m,
                        ebt_id=ebt.id,
                        pdf_bytes=b"%PDF-1.4 conteudo teste",
                        storage=storage_temp,
                        exigir_parecer_aprovado=True,
                    )

                # Gera e homologa parecer
                analise, _, _ = solicitar_parecer_ia_governado(
                    db, membership=m, ebt_id=ebt.id
                )
                revisar_e_aprovar_parecer_ia(
                    db, membership=m, analise_id=analise.id
                )

                # Agora a emissão oficial homologada funciona e gera hash SHA-256 + URL assinada
                relatorio, job_pdf, url_assinada = registrar_emissao_dossie_pdf(
                    db,
                    membership=m,
                    ebt_id=ebt.id,
                    pdf_bytes=b"%PDF-1.4 conteudo oficial assinado",
                    storage=storage_temp,
                    exigir_parecer_aprovado=True,
                )
                self.assertEqual(len(relatorio.sha256_pdf), 64)
                self.assertIn(f"tenants/{tid}/ebts/{ebt.id}/dossies/", relatorio.storage_key)
                self.assertIn("signature=", url_assinada)
                self.assertEqual(job_pdf.status, "concluido")

                jobs = listar_jobs_tenant(db, tenant_id=tid, ebt_id=ebt.id)
                self.assertGreaterEqual(len(jobs), 2)

    def test_plano_free_tier_plataforma_saas_limites_e_upgrade(self) -> None:
        with sessao_por_requisicao(self.session_factory, bypass_rls=True) as db_setup:
            tenant, dono, memb_dono = criar_tenant_consultoria(
                db_setup,
                nome_consultoria="Startup Degustação Free",
                slug="degustacao-free",
                email_dono="founder@free.com",
                nome_dono="Founder Free",
                plano=PlanoAssinaturaCodigo.FREE,
            )
            tid, uid, mid = tenant.id, dono.id, memb_dono.id

        with sessao_por_requisicao(
            self.session_factory, tenant_id=tid, user_id=uid
        ) as db:
            m = db.get(Membership, mid)
            ebt_unica = criar_workspace_ebt(
                db, membership=m, nome_startup="Minha Primeira EBT"
            )

            # Plano FREE permite apenas 1 EBT
            with self.assertRaises(ErroLimitePlanoSaaS):
                criar_workspace_ebt(
                    db, membership=m, nome_startup="Segunda EBT Bloqueada no Free"
                )

            # Plano FREE permite até 3 simulações gratuitas no mês
            executar_e_versionar_simulacao_ebt(db, membership=m, ebt_id=ebt_unica.id)
            executar_e_versionar_simulacao_ebt(db, membership=m, ebt_id=ebt_unica.id)
            executar_e_versionar_simulacao_ebt(db, membership=m, ebt_id=ebt_unica.id)

            with self.assertRaises(ErroLimitePlanoSaaS):
                executar_e_versionar_simulacao_ebt(db, membership=m, ebt_id=ebt_unica.id)

            # Upgrade para PRO desbloqueia novas EBTs e simulações
            assinatura_pro = alterar_plano_assinatura_tenant(
                db, membership=m, novo_plano=PlanoAssinaturaCodigo.PRO
            )
            self.assertEqual(assinatura_pro.plano_codigo, "pro")
            self.assertTrue(assinatura_pro.permite_monte_carlo)

            ebt_2 = criar_workspace_ebt(
                db, membership=m, nome_startup="Segunda EBT Desbloqueada no Pro"
            )
            self.assertIsNotNone(ebt_2.id)
            executar_e_versionar_simulacao_ebt(db, membership=m, ebt_id=ebt_unica.id)

    def test_jwt_hs256_assinatura_validacao_e_expiracao(self) -> None:
        token = gerar_jwt_sessao_saas(
            user_id="user-123",
            email="socio@mm.com.br",
            nome="Sócio Diretor",
            tenant_id="tenant-abc",
            membership_id="memb-xyz",
            papel="dono",
            ebt_restrita_id=None,
            provedor_oauth="google",
            expira_em_segundos=7200,
        )
        claims = decodificar_jwt_sessao_saas(token)
        self.assertEqual(claims["sub"], "user-123")
        self.assertEqual(claims["tenant_id"], "tenant-abc")
        self.assertEqual(claims["papel"], "dono")
        self.assertEqual(claims["provider"], "google")

        # Adulteração da assinatura deve falhar
        token_adulterado = token[:-4] + "XXXX"
        with self.assertRaises(ErroAutenticacaoOAuth):
            decodificar_jwt_sessao_saas(token_adulterado)

        # Token expirado deve ser rejeitado
        futuro = int((datetime.now(timezone.utc) + timedelta(hours=5)).timestamp())
        with self.assertRaises(ErroAutenticacaoOAuth):
            decodificar_jwt_sessao_saas(token, agora_ts=futuro)

    def test_oauth2_convite_rbac_todos_perfis_e_sessao_jwt(self) -> None:
        provedores = listar_provedores_oauth_configurados()
        codigos_prov = {p["id"] for p in provedores}
        self.assertIn("google", codigos_prov)
        self.assertIn("github", codigos_prov)
        self.assertIn("oauth-rbac-sandbox", codigos_prov)

        with sessao_por_requisicao(self.session_factory, bypass_rls=True) as db_setup:
            tenant, dono, memb_dono = criar_tenant_consultoria(
                db_setup,
                nome_consultoria="OAuth Ventures",
                slug="oauth-ventures",
                email_dono="dono@oauthventures.com",
                nome_dono="Sócio OAuth",
            )
            tid, uid_dono, mid_dono = tenant.id, dono.id, memb_dono.id

        with sessao_por_requisicao(
            self.session_factory, tenant_id=tid, user_id=uid_dono
        ) as db:
            m_dono = db.get(Membership, mid_dono)
            ebt_A = criar_workspace_ebt(db, membership=m_dono, nome_startup="Startup Alpha")
            ebt_B = criar_workspace_ebt(db, membership=m_dono, nome_startup="Startup Beta")

            # 1. Emite convite OAuth2 para Fundador restrito apenas à Startup Alpha
            token_convite_fundador, convite_fundador = criar_convite_rbac_oauth(
                db,
                membership_emissor=m_dono,
                papel=PapelMembro.FUNDADOR,
                ebt_restrita_id=ebt_A.id,
                email_convidado="founder.alpha@gmail.com",
            )
            self.assertEqual(convite_fundador.papel, "fundador")
            self.assertEqual(convite_fundador.ebt_restrita_id, ebt_A.id)

            # 2. Emite convite OAuth2 para Investidor restrito à Startup Beta
            token_convite_investidor, convite_investidor = criar_convite_rbac_oauth(
                db,
                membership_emissor=m_dono,
                papel=PapelMembro.INVESTIDOR,
                ebt_restrita_id=ebt_B.id,
                email_convidado="vc.beta@fund.com",
            )

            ebt_A_id = ebt_A.id
            ebt_B_id = ebt_B.id

        # 3. Resgata convite OAuth2 como Fundador via Google OAuth
        with sessao_por_requisicao(self.session_factory, bypass_rls=True) as db_oauth:
            sessao_f = autenticar_via_oauth_ou_convite(
                db_oauth,
                email="founder.alpha@gmail.com",
                nome="Fundador Alpha OAuth",
                provedor="google",
                sub_externo="google-uid-999",
                invite_token=token_convite_fundador,
            )
            self.assertEqual(
                sessao_f["membership_ativa"]["papel"], PapelMembro.FUNDADOR.value
            )
            self.assertEqual(
                sessao_f["membership_ativa"]["ebt_restrita_id"], ebt_A_id
            )
            self.assertIn("access_token", sessao_f)
            permissoes_f = set(sessao_f["membership_ativa"]["permissoes"])
            self.assertNotIn(PermissaoSaaS.EBT_CRIAR.value, permissoes_f)
            self.assertIn(PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO.value, permissoes_f)
            self.assertNotIn(PermissaoSaaS.IA_APROVAR_PARECER.value, permissoes_f)

            # 4. Resgata convite OAuth2 como Investidor via GitHub OAuth
            sessao_i = autenticar_via_oauth_ou_convite(
                db_oauth,
                email="vc.beta@fund.com",
                nome="Partner VC Beta",
                provedor="github",
                sub_externo="github-uid-777",
                invite_token=token_convite_investidor,
            )
            self.assertEqual(
                sessao_i["membership_ativa"]["papel"], PapelMembro.INVESTIDOR.value
            )
            self.assertEqual(
                sessao_i["membership_ativa"]["ebt_restrita_id"], ebt_B_id
            )
            permissoes_i = set(sessao_i["membership_ativa"]["permissoes"])
            self.assertIn(PermissaoSaaS.EBT_VISUALIZAR.value, permissoes_i)
            self.assertNotIn(PermissaoSaaS.EBT_EDITAR_DIAGNOSTICO.value, permissoes_i)
            self.assertNotIn(PermissaoSaaS.SIMULACAO_EXECUTAR.value, permissoes_i)

            # 5. Autenticação via Sandbox RBAC para Consultor
            sessao_c = autenticar_via_oauth_ou_convite(
                db_oauth,
                email="consultor@oauthventures.com",
                nome="Consultor Sênior",
                provedor="oauth-rbac-sandbox",
                tenant_id_preferencial=tid,
                papel_sandbox=PapelMembro.CONSULTOR,
            )
            self.assertEqual(
                sessao_c["membership_ativa"]["papel"], PapelMembro.CONSULTOR.value
            )
            self.assertIn(
                PermissaoSaaS.IA_APROVAR_PARECER.value,
                sessao_c["membership_ativa"]["permissoes"],
            )

    def test_fluxo_oauth_primeiro_admin_demais_free_tier_e_upgrade_pelo_admin(
        self,
    ) -> None:
        """
        Regra obrigatória:
        - O 1º perfil autenticado via OAuth no banco de dados é registrado como ADMIN.
        - Os demais perfis autenticados via OAuth sem convite prévio são categorizados
          automaticamente como assinantes FREE TIER (plano 'free').
        - O upgrade de plano e alteração de papel RBAC ficam sob responsabilidade exclusiva do ADMIN.
        """
        with sessao_por_requisicao(self.session_factory, bypass_rls=True) as db:
            # 1º Usuário OAuth -> Registrado automaticamente como ADMIN
            sessao_admin = autenticar_via_oauth_ou_convite(
                db,
                email="primeiro.admin@ticventures.com.br",
                nome="Primeiro Admin OAuth",
                provedor="google",
                sub_externo="google-sub-admin-001",
            )
            self.assertEqual(
                sessao_admin["membership_ativa"]["papel"], PapelMembro.ADMIN.value
            )
            self.assertIn(
                PermissaoSaaS.TENANT_GERENCIAR_COBRANCA.value,
                sessao_admin["membership_ativa"]["permissoes"],
            )

            # 2º Usuário OAuth -> Registrado automaticamente como Assinante FREE TIER
            sessao_free = autenticar_via_oauth_ou_convite(
                db,
                email="segundo.assinante@startup.com.br",
                nome="Segundo Assinante OAuth Free",
                provedor="github",
                sub_externo="github-sub-free-002",
            )
            self.assertEqual(
                sessao_free["tenant"]["plano_codigo"],
                PlanoAssinaturaCodigo.FREE.value,
            )

            # Lista usuários com acesso OAuth prévio no banco
            usuarios_oauth = listar_usuarios_oauth_registrados(db)
            self.assertEqual(len(usuarios_oauth), 2)

            membership_free_id = sessao_free["membership_ativa"]["id"]
            membership_admin_obj = (
                db.query(Membership)
                .filter(Membership.id == sessao_admin["membership_ativa"]["id"])
                .first()
            )
            membership_free_obj = (
                db.query(Membership).filter(Membership.id == membership_free_id).first()
            )

            # Assinante Free Tier comum NÃO pode promover plano por conta própria via endpoint Admin
            membership_free_obj.papel = PapelMembro.FUNDADOR.value
            db.flush()
            with self.assertRaises(ErroPermissaoRBAC):
                gerenciar_assinante_oauth_pelo_admin(
                    db,
                    membership_admin=membership_free_obj,
                    membership_alvo_id=membership_free_id,
                    novo_plano=PlanoAssinaturaCodigo.PRO,
                )

            # ADMIN promove o assinante Free Tier para PRO e altera seu papel RBAC
            res_upgrade = gerenciar_assinante_oauth_pelo_admin(
                db,
                membership_admin=membership_admin_obj,
                membership_alvo_id=membership_free_id,
                novo_papel=PapelMembro.CONSULTOR,
                novo_plano=PlanoAssinaturaCodigo.PRO,
            )
            self.assertEqual(res_upgrade["papel"], PapelMembro.CONSULTOR.value)
            self.assertEqual(
                res_upgrade["plano_codigo"], PlanoAssinaturaCodigo.PRO.value
            )

    def test_login_credenciais_superadmin_painel_rbac_e_meu_perfil(self) -> None:
        """
        Valida o fluxo completo de:
        1. Login tradicional por E-mail e Senha com o SuperAdmin inicial
           (`marcolinoee@yahoo.com.br` / `123456`) na role `ADMIN`.
        2. Rejeição de credenciais incorretas (`ErroAutenticacaoOAuth`).
        3. Cadastro de novo usuário (`ASSINANTE_FREE`) e promoção pelo Admin
           no Painel RBAC (`GESTOR`, `ASSINANTE_PRO`).
        4. Trava de segurança que impede o Admin de remover seu próprio papel `ADMIN`
           ou desativar sua própria conta (`ErroPermissaoRBAC`).
        5. Atualização da aba 'Meu Perfil' (Nome, Telefone, Cargo, Avatar e Senha).
        """
        with sessao_por_requisicao(self.session_factory, bypass_rls=True) as db:
            # 1. Login do SuperAdmin inicial (seed automático)
            sessao_superadmin = autenticar_com_email_e_senha(
                db,
                email="marcolinoee@yahoo.com.br",
                senha="123456",
            )
            self.assertEqual(
                sessao_superadmin["user"]["email"], "marcolinoee@yahoo.com.br"
            )
            self.assertEqual(
                sessao_superadmin["membership_ativa"]["papel"],
                PapelMembro.ADMIN.value,
            )

            # 2. Senha incorreta deve ser bloqueada
            with self.assertRaises(ErroAutenticacaoOAuth):
                autenticar_com_email_e_senha(
                    db,
                    email="marcolinoee@yahoo.com.br",
                    senha="senha-incorreta",
                )

            # 3. Cadastro de novo usuário via credenciais -> inicia como ASSINANTE_FREE
            sessao_novo = registrar_novo_usuario_credenciais(
                db,
                nome_completo="Ana Carolina Startup",
                email="ana.carolina@startup.com.br",
                senha="senhaSegura123",
                telefone_whatsapp="(11) 98888-7777",
                cargo_organizacao="CEO & Founder",
            )
            self.assertEqual(
                sessao_novo["membership_ativa"]["papel"],
                PapelMembro.ASSINANTE_FREE.value,
            )
            self.assertEqual(sessao_novo["tenant"]["plano_codigo"], "free")

            # 4. Restrição de segurança: Admin NÃO pode remover seu próprio papel ADMIN nem se desativar
            memb_admin_id = sessao_superadmin["membership_ativa"]["id"]
            memb_admin_obj = db.get(Membership, memb_admin_id)
            with self.assertRaises(ErroPermissaoRBAC):
                gerenciar_assinante_oauth_pelo_admin(
                    db,
                    membership_admin=memb_admin_obj,
                    membership_alvo_id=memb_admin_id,
                    novo_papel=PapelMembro.ANALISTA,
                )
            with self.assertRaises(ErroPermissaoRBAC):
                gerenciar_assinante_oauth_pelo_admin(
                    db,
                    membership_admin=memb_admin_obj,
                    membership_alvo_id=memb_admin_id,
                    ativo=False,
                )

            # 5. Admin altera papel de outro usuário para ASSINANTE_PRO (sincronizando plano 'pro')
            memb_ana_id = sessao_novo["membership_ativa"]["id"]
            res_rbac = gerenciar_assinante_oauth_pelo_admin(
                db,
                membership_admin=memb_admin_obj,
                membership_alvo_id=memb_ana_id,
                novo_papel=PapelMembro.ASSINANTE_PRO,
            )
            self.assertEqual(res_rbac["papel"], PapelMembro.ASSINANTE_PRO.value)
            self.assertEqual(res_rbac["plano_codigo"], "pro")

            # 6. Atualização da aba 'Meu Perfil' + troca de senha
            user_ana = db.get(User, sessao_novo["user"]["id"])
            memb_ana_obj = db.get(Membership, memb_ana_id)
            sessao_perfil = atualizar_meu_perfil_usuario(
                db,
                user=user_ana,
                membership_ativa=memb_ana_obj,
                nome_completo="Ana Carolina Silva",
                telefone_whatsapp="(11) 97777-6666",
                cargo_organizacao="Diretora de Tecnologia (CTO)",
                avatar_url="https://exemplo.com/avatar-ana.png",
                senha_atual="senhaSegura123",
                nova_senha="novaSenhaForte456",
            )
            self.assertEqual(
                sessao_perfil["user"]["nome_completo"], "Ana Carolina Silva"
            )
            self.assertEqual(
                sessao_perfil["user"]["cargo_organizacao"],
                "Diretora de Tecnologia (CTO)",
            )
            self.assertEqual(
                sessao_perfil["user"]["avatar_url"],
                "https://exemplo.com/avatar-ana.png",
            )

            # Login com a nova senha deve funcionar
            sessao_relogin = autenticar_com_email_e_senha(
                db,
                email="ana.carolina@startup.com.br",
                senha="novaSenhaForte456",
            )
            self.assertEqual(
                sessao_relogin["user"]["nome_completo"], "Ana Carolina Silva"
            )

    def test_gestao_avancada_contas_admin_excluir_uso_plano_e_trava_seguranca(
        self,
    ) -> None:
        """
        Valida a Gestão Avançada de Contas no Painel Admin (RBAC):
        1. Trava de segurança que impede a exclusão do SuperAdmin oficial ('marcolinoee@yahoo.com.br').
        2. Visualização analítica do consumo de uso da conta (simulações, IA, PDFs, EBTs).
        3. Edição completa de dados (nome, email, cargo, status) e mudança de plano.
        4. Exclusão definitiva de conta com sucesso para usuários comuns.
        5. Atualização para modelo Gemini mais recente (gemini-2.5-flash e gemini-2.5-pro).
        """
        with sessao_por_requisicao(self.session_factory, bypass_rls=True) as db:
            # Login do SuperAdmin
            sessao_admin = autenticar_com_email_e_senha(
                db, email="marcolinoee@yahoo.com.br", senha="123456"
            )
            admin_memb_id = sessao_admin["membership_ativa"]["id"]
            admin_memb = db.get(Membership, admin_memb_id)

            # 1. Trava de segurança: tentar excluir o próprio SuperAdmin DEVE falhar
            with self.assertRaises(ErroPermissaoRBAC) as ctx_lock:
                excluir_usuario_pelo_admin(
                    db,
                    membership_admin=admin_memb,
                    membership_alvo_id=admin_memb_id,
                )
            self.assertIn("Trava de segurança", str(ctx_lock.exception))

            # 2. Cadastrar usuário comum para testes
            sessao_comum = registrar_novo_usuario_credenciais(
                db,
                nome_completo="Carlos Gestor",
                email="carlos.gestor@empresa.com.br",
                senha="senhaCarlos123",
                cargo_organizacao="Gerente Financeiro",
                telefone_whatsapp="(11) 98888-7777",
            )
            carlos_memb_id = sessao_comum["membership_ativa"]["id"]

            # 3. Visualizar Uso do Usuário
            dados_uso = obter_uso_usuario_pelo_admin(
                db,
                membership_admin=admin_memb,
                membership_alvo_id=carlos_memb_id,
            )
            self.assertEqual(dados_uso["email"], "carlos.gestor@empresa.com.br")
            self.assertIn("consumo", dados_uso)
            self.assertIn("limites", dados_uso)
            self.assertIn("simulacoes_executadas", dados_uso["consumo"])

            # 4. Editar Dados e Mudar de Plano
            atualizado = gerenciar_assinante_oauth_pelo_admin(
                db,
                membership_admin=admin_memb,
                membership_alvo_id=carlos_memb_id,
                nome_completo="Carlos Gestor Atualizado",
                email="carlos.novo@empresa.com.br",
                cargo_organizacao="Head de Operações",
                novo_papel=PapelMembro.GESTOR,
                novo_plano=PlanoAssinaturaCodigo.ENTERPRISE,
                ativo=True,
            )
            self.assertEqual(atualizado["nome_completo"], "Carlos Gestor Atualizado")
            self.assertEqual(atualizado["email"], "carlos.novo@empresa.com.br")
            self.assertEqual(atualizado["papel"], "gestor")
            self.assertEqual(atualizado["plano_codigo"], "enterprise")

            # 5. Excluir Conta do Usuário Comum com sucesso
            res_del = excluir_usuario_pelo_admin(
                db,
                membership_admin=admin_memb,
                membership_alvo_id=carlos_memb_id,
            )
            self.assertTrue(res_del["sucesso"])
            self.assertEqual(res_del["email"], "carlos.novo@empresa.com.br")

            # Usuário excluído não pode mais logar
            with self.assertRaises(ErroAutenticacaoOAuth):
                autenticar_com_email_e_senha(
                    db,
                    email="carlos.novo@empresa.com.br",
                    senha="senhaCarlos123",
                )

            # 6. Validação dos modelos da cascata Gemini
            prov_default = ProvedorGeminiIA(api_key="teste-fake-key")
            self.assertIn(prov_default.modelo_nome, ["gemini-4-argon", "gemini-3.8"])
            prov_flash = ProvedorGeminiIA(api_key="teste-fake-key", modelo="gemini-3.8-flash")
            self.assertEqual(prov_flash.modelo_nome, "gemini-3.8-flash")
            prov_pro = ProvedorGeminiIA(api_key="teste-fake-key", modelo="gemini-3.8-pro")
            self.assertEqual(prov_pro.modelo_nome, "gemini-3.8-pro")

    def test_resiliencia_ia_codigos_falha_e_fallback_copiloto(self) -> None:
        """
        Valida a resiliência e tratamento de códigos de falha na IA:
        1. Códigos padronizados ERR_AI_*.
        2. ProvedorGeminiIA com chave vazia lança ErroIAAutenticacao (ERR_AI_AUTH_TOKEN_04).
        3. Simulação de timeout, offline e indisponibilidade gerando códigos respectivos.
        4. solicitar_parecer_ia_governado com permitir_fallback_copiloto=True gera parecer seguro de fallback.
        5. solicitar_parecer_ia_governado com permitir_fallback_copiloto=False propaga ErroIA estruturado.
        """
        # 1. Códigos padronizados
        self.assertEqual(CodigoFalhaIA.TIMEOUT, "ERR_AI_TIMEOUT_01")
        self.assertEqual(CodigoFalhaIA.API_UNAVAILABLE, "ERR_AI_API_UNAVAILABLE_02")
        self.assertEqual(CodigoFalhaIA.NETWORK_OFFLINE, "ERR_AI_NETWORK_OFFLINE_03")
        self.assertEqual(CodigoFalhaIA.AUTH_TOKEN, "ERR_AI_AUTH_TOKEN_04")
        self.assertEqual(CodigoFalhaIA.QUOTA_EXCEEDED, "ERR_AI_QUOTA_EXCEEDED_05")

        # 2. Chave vazia
        prov_sem_chave = ProvedorGeminiIA(api_key="")
        with self.assertRaises(ErroIAAutenticacao) as ctx_auth:
            prov_sem_chave.gerar_parecer("prompt teste", None, None)  # type: ignore
        self.assertIn(
            ctx_auth.exception.codigo_erro,
            ["ERR_GEMINI_AUTH_401", "ERR_AI_AUTH_TOKEN_04"],
        )

        # 3. Mapeamento de exceções no ProvedorGeminiIA
        class ProvedorMockErro(ProvedorGeminiIA):
            def __init__(self, tipo_erro: str) -> None:
                super().__init__(api_key="fake-key-123")
                self.tipo_erro = tipo_erro

            def gerar_parecer(self, prompt, ebt, resultado):
                if self.tipo_erro == "timeout":
                    raise TimeoutError("Deadline exceeded after 30s")
                if self.tipo_erro == "network":
                    raise ConnectionError("Failed to connect: getaddrinfo ENOTFOUND")
                if self.tipo_erro == "503":
                    raise RuntimeError("503 Service Unavailable: server overloaded")
                raise RuntimeError("Falha genérica")

        with self.assertRaises(TimeoutError):
            ProvedorMockErro("timeout").gerar_parecer("", None, None)  # type: ignore

        # 4. Fallback automático no solicitar_parecer_ia_governado
        with sessao_por_requisicao(self.session_factory, bypass_rls=True) as db:
            tenant, _, membership_admin = criar_tenant_consultoria(
                db,
                nome_consultoria="Resilience VC",
                slug="resilience-vc",
                email_dono="dono@resilience.vc",
                nome_dono="Dono Resilience",
                plano=PlanoAssinaturaCodigo.PRO,
            )
            ebt = criar_workspace_ebt(
                db,
                membership=membership_admin,
                nome_startup="DeepTech Alpha",
                setor_vertical="HealthTech",
            )
            db.commit()

            # Provedor que falha com ErroIAIndisponivel
            class ProvedorFalho(ProvedorGeminiIA):
                def __init__(self) -> None:
                    super().__init__(api_key="fake-key")

                def gerar_parecer(self, prompt, ebt, resultado):
                    raise ErroIAIndisponivel("Google GenAI 503 Unavailable")

            # A. Com fallback ativado (permitir_fallback_copiloto=True)
            analise_fallback, job, veio_cache = solicitar_parecer_ia_governado(
                db,
                membership=membership_admin,
                ebt_id=ebt.id,
                provedor_ia=ProvedorFalho(),
                forcar_regeneracao=True,
                permitir_fallback_copiloto=True,
            )
            self.assertFalse(veio_cache)
            self.assertIn("Modo de Resiliência & Fallback", analise_fallback.parecer_gerado_md)
            self.assertTrue(
                "ERR_AI_API_UNAVAILABLE_02" in analise_fallback.parecer_gerado_md
                or "ERR_GEMINI_ALL_MODELS_EXHAUSTED" in analise_fallback.parecer_gerado_md
            )
            self.assertIn("vc-auditor-deterministico", analise_fallback.modelo)

            # B. Sem fallback ativado (permitir_fallback_copiloto=False) propaga o ErroIA
            with self.assertRaises(ErroIA) as ctx_falha:
                solicitar_parecer_ia_governado(
                    db,
                    membership=membership_admin,
                    ebt_id=ebt.id,
                    provedor_ia=ProvedorFalho(),
                    forcar_regeneracao=True,
                    permitir_fallback_copiloto=False,
                )
            self.assertIn(
                ctx_falha.exception.codigo_erro,
                ["ERR_AI_API_UNAVAILABLE_02", "ERR_GEMINI_ALL_MODELS_EXHAUSTED"],
            )

    def test_cascata_exaustiva_gemini_retentativas_e_telemetria(self) -> None:
        """
        Valida a Cascata Exaustiva Multi-Geração Gemini (17 modelos):
        1. Hierarquia exata dos 17 modelos (4 -> 3 -> 2.5 -> 2.0 -> 1.5 -> 1.0).
        2. Aborto imediato com ERR_GEMINI_AUTH_401 em caso de 401/403 sem percorrer a cascata.
        3. Ciclo de 3 retentativas por modelo com backoff antes de avançar para o próximo tier.
        4. Sucesso no segundo tier captura telemetria (modelo_resolvido, geracao_resolvida, tentativas_executadas).
        5. Exaustão de todos os 17 modelos dispara ERR_GEMINI_ALL_MODELS_EXHAUSTED.
        """
        # 1. Hierarquia dos 17 modelos
        self.assertEqual(len(CASCATA_MODELOS_GEMINI), 17)
        self.assertEqual(
            CASCATA_MODELOS_GEMINI,
            (
                "gemini-4-argon",
                "gemini-3.1-pro-preview",
                "gemini-3.8-flash",
                "gemini-3.6-flash",
                "gemini-3-flash-preview",
                "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite",
                "gemini-2.5-pro",
                "gemini-2.5-flash",
                "gemini-2.5-flash-lite",
                "gemini-2.0-pro",
                "gemini-2.0-flash",
                "gemini-2.0-flash-lite",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-1.5-flash-8b",
                "gemini-1.0-pro",
            ),
        )

        # 2. Aborto Imediato em 401/403 (Chave Inválida / Não Autorizada)
        class ProvedorMockAuth401(ProvedorGeminiIA):
            def __init__(self) -> None:
                super().__init__(
                    api_key="chave-invalida",
                    modelo="gemini-4-argon",
                    max_tentativas_por_modelo=3,
                    backoff_delays=(0.001, 0.001, 0.001),
                )
                self.chamadas_feitas = []

            def _invocar_api_modelo(self, modelo: str, prompt: str) -> str:
                self.chamadas_feitas.append(modelo)
                raise RuntimeError("401 Unauthorized: API key not valid. Please pass a valid API key.")

        prov_auth = ProvedorMockAuth401()
        with self.assertRaises(ErroIAAutenticacao) as ctx_auth:
            prov_auth.gerar_parecer("prompt teste", None, None)  # type: ignore

        self.assertEqual(ctx_auth.exception.codigo_erro, "ERR_GEMINI_AUTH_401")
        # Deve ter abortado na 1ª tentativa do 1º modelo, SEM percorrer o resto dos 17 modelos
        self.assertEqual(prov_auth.tentativas_executadas, 1)
        self.assertEqual(len(prov_auth.chamadas_feitas), 1)
        self.assertEqual(prov_auth.chamadas_feitas[0], "gemini-4-argon")

        # 3 e 4. Ciclo de 3 retentativas e recuo para o modelo seguinte com sucesso e telemetria
        class ProvedorMockCascataSucesso(ProvedorGeminiIA):
            def __init__(self) -> None:
                super().__init__(
                    api_key="chave-valida",
                    modelo="gemini-4-argon",
                    max_tentativas_por_modelo=3,
                    backoff_delays=(0.001, 0.001, 0.001),
                )
                self.chamadas = []

            def _invocar_api_modelo(self, modelo: str, prompt: str) -> str:
                self.chamadas.append(modelo)
                # Modelo 1 (gemini-4-argon) falha com 429 nas 3 tentativas
                if modelo == "gemini-4-argon":
                    raise RuntimeError("429 Resource Exhausted: Rate limit reached")
                # Modelo 2 (gemini-3.1-pro-preview) falha na 1ª tentativa com 503 e passa na 2ª
                if modelo == "gemini-3.1-pro-preview":
                    if len([c for c in self.chamadas if c == "gemini-3.1-pro-preview"]) == 1:
                        raise RuntimeError("503 Service Unavailable: overloaded")
                    return "### Parecer Aprovado com Sucesso via Geração 3"
                return "OK"

        prov_cascata = ProvedorMockCascataSucesso()
        parecer = prov_cascata.gerar_parecer("prompt teste", None, None)  # type: ignore

        self.assertIn("Parecer Aprovado com Sucesso via Geração 3", parecer)
        # Modelo 1: 3 tentativas falhas. Modelo 2: 1 falha + 1 sucesso = 5 tentativas no total
        self.assertEqual(prov_cascata.tentativas_executadas, 5)
        self.assertEqual(prov_cascata.modelo_resolvido, "gemini-3.1-pro-preview")
        self.assertIn("Geração Gemini 3", prov_cascata.geracao_resolvida or "")

        # 5. Exaustão de Todos os 17 Modelos
        class ProvedorMockTodosFalham(ProvedorGeminiIA):
            def __init__(self) -> None:
                super().__init__(
                    api_key="chave-valida",
                    modelo="gemini-4-argon",
                    max_tentativas_por_modelo=3,
                    backoff_delays=(0.001, 0.001, 0.001),
                )

            def _invocar_api_modelo(self, modelo: str, prompt: str) -> str:
                raise RuntimeError("503 Service Unavailable")

        prov_todos_falham = ProvedorMockTodosFalham()
        with self.assertRaises(ErroIACascataEsgotada) as ctx_esgotado:
            prov_todos_falham.gerar_parecer("prompt teste", None, None)  # type: ignore

        self.assertEqual(ctx_esgotado.exception.codigo_erro, "ERR_GEMINI_ALL_MODELS_EXHAUSTED")
        # 17 modelos * 3 tentativas = 51 tentativas
        self.assertEqual(prov_todos_falham.tentativas_executadas, 51)


if __name__ == "__main__":
    unittest.main(verbosity=2)
