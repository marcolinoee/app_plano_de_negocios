import React, { useEffect, useState } from "react";
import {
  api,
  carregarOutboxIA,
  limparOutboxIA,
  limparToken,
  obterTokenSalvo,
  removerDoOutboxIA,
  salvarNoOutboxIA,
  salvarToken,
} from "./api";
import {
  GraficoCashflowValeDaMorte,
  GraficoMRRTracao,
  GraficoRoscaBurnRate,
} from "./Charts";
import {
  CodigoFalhaIA,
  ErroFalhaIA,
  PapelRBAC,
  PlanoCodigo,
  SessaoAutenticada,
  SolicitacaoIAPendenteOutbox,
  UsoUsuarioDetalhado,
  UsuarioOAuthRegistrado,
  WorkspaceEBTCompleto,
  WorkspaceEBTResumo,
} from "./types";

const ABAS_STREAMLIT = [
  { id: "canvas", label: "🧩 Lean Canvas", adminOnly: false },
  { id: "premissas", label: "📈 Premissas", adminOnly: false },
  { id: "capex", label: "🛠️ Capex", adminOnly: false },
  { id: "opex", label: "🔄 Opex", adminOnly: false },
  { id: "pricing", label: "💳 SaaS Pricing", adminOnly: false },
  { id: "legal", label: "⚖️ Riscos Legais", adminOnly: false },
  { id: "onepager", label: "📄 Resumo One-Pager", adminOnly: false },
  { id: "viabilidade", label: "📊 Viabilidade", adminOnly: false },
  { id: "dashboards", label: "📉 Dashboards", adminOnly: false },
  { id: "comite_ia", label: "🤖 Comitê VC (IA)", adminOnly: false },
  { id: "dataroom_pdf", label: "🖨️ Data Room (PDF)", adminOnly: false },
  { id: "governanca", label: "🏛️ Governança SaaS", adminOnly: false },
  { id: "painel_rbac", label: "🛡️ Painel Admin (RBAC)", adminOnly: true },
  { id: "meu_perfil", label: "👤 Meu Perfil", adminOnly: false },
] as const;

type AbaId = (typeof ABAS_STREAMLIT)[number]["id"];

const PAPEIS_RBAC_OPCOES: Array<{ value: PapelRBAC; label: string }> = [
  { value: "admin", label: "ADMIN (Super Admin / Acesso Total)" },
  { value: "gestor", label: "GESTOR (Gestão de Portfólio & Equipe)" },
  { value: "analista", label: "ANALISTA (Diagnóstico & Simulações)" },
  { value: "assinante_free", label: "ASSINANTE_FREE (Plano Free Tier)" },
  { value: "assinante_pro", label: "ASSINANTE_PRO (Plano Pro Completo)" },
  { value: "consultor", label: "CONSULTOR (Consultor VC & Homologação IA)" },
  { value: "fundador", label: "FUNDADOR (Acesso Restrito à Própria Startup)" },
  { value: "investidor", label: "INVESTIDOR (Data Room Somente Leitura)" },
  { value: "dono", label: "DONO (Proprietário do Tenant)" },
];

const AVATARES_SUGERIDOS = [
  "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=200&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=200&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=200&auto=format&fit=crop&q=80",
];

function LogoMasterManagement({ className = "w-10 h-10" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      {/* Outer Executive Ring */}
      <circle cx="24" cy="24" r="22" stroke="#3F3F46" strokeWidth="1.5" />
      {/* Concentric Accents (Master Management) */}
      <circle cx="24" cy="24" r="16.5" stroke="#E30000" strokeWidth="2.2" strokeDasharray="5 2.5" />
      <circle cx="24" cy="24" r="11" stroke="#FFFFFF" strokeWidth="1.8" />
      <circle cx="24" cy="24" r="5.5" stroke="#E30000" strokeWidth="2" />
      {/* Central Core */}
      <circle cx="24" cy="24" r="2.5" fill="#E30000" />
    </svg>
  );
}

function WatermarkLinhasGeometricas({ className = "w-64 h-64" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <circle cx="100" cy="100" r="95" stroke="#E30000" strokeWidth="1" strokeOpacity="0.15" />
      <circle cx="100" cy="100" r="75" stroke="#FFFFFF" strokeWidth="1" strokeOpacity="0.08" strokeDasharray="4 6" />
      <circle cx="100" cy="100" r="55" stroke="#E30000" strokeWidth="1.5" strokeOpacity="0.2" />
      <circle cx="100" cy="100" r="35" stroke="#FFFFFF" strokeWidth="1" strokeOpacity="0.08" />
      <circle cx="100" cy="100" r="15" stroke="#E30000" strokeWidth="2" strokeOpacity="0.3" strokeDasharray="3 3" />
      <line x1="0" y1="100" x2="200" y2="100" stroke="#FFFFFF" strokeWidth="0.5" strokeOpacity="0.06" />
      <line x1="100" y1="0" x2="100" y2="200" stroke="#FFFFFF" strokeWidth="0.5" strokeOpacity="0.06" />
    </svg>
  );
}

function validarFormatoEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

function obterIniciais(nome: string | undefined | null): string {
  if (!nome || !nome.trim()) return "MM";
  const partes = nome.trim().split(/\s+/);
  if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase();
  return (partes[0][0] + partes[partes.length - 1][0]).toUpperCase();
}

function fmtBRL(v: number | undefined | null): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(v || 0);
}

function safeStr(v: string | undefined | null): string {
  return v && v.trim() ? v : "Não informado.";
}

export default function App() {
  const [sessao, setSessao] = useState<SessaoAutenticada | null>(null);
  const [carregandoAuth, setCarregandoAuth] = useState<boolean>(true);
  const [erroGlobal, setErroGlobal] = useState<string | null>(null);
  const [msgSucesso, setMsgSucesso] = useState<string | null>(null);

  // Estados de Autenticação Tradicional (E-mail + Senha)
  const [modoAuthTela, setModoAuthTela] = useState<"login" | "cadastro">(
    "login"
  );
  const [emailLogin, setEmailLogin] = useState<string>("");
  const [senhaLogin, setSenhaLogin] = useState<string>("");
  const [mostrarSenhaLogin, setMostrarSenhaLogin] = useState<boolean>(false);
  const [submetendoLogin, setSubmetendoLogin] = useState<boolean>(false);
  const [erroValidacaoLogin, setErroValidacaoLogin] = useState<string | null>(
    null
  );

  // Estados de Cadastro de Nova Conta
  const [formCadastro, setFormCadastro] = useState({
    nome_completo: "",
    email: "",
    senha: "",
    telefone_whatsapp: "",
    cargo_organizacao: "",
  });

  // Estados do Painel Admin de RBAC
  const [usuariosRBAC, setUsuariosRBAC] = useState<UsuarioOAuthRegistrado[]>(
    []
  );
  const [carregandoUsuariosRBAC, setCarregandoUsuariosRBAC] =
    useState<boolean>(false);
  const [filtroBuscaRBAC, setFiltroBuscaRBAC] = useState<string>("");
  const [edicoesRBAC, setEdicoesRBAC] = useState<
    Record<
      string,
      {
        papel: PapelRBAC;
        plano_codigo: PlanoCodigo;
        ativo: boolean;
      }
    >
  >({});
  const [usuarioModalRBAC, setUsuarioModalRBAC] =
    useState<UsuarioOAuthRegistrado | null>(null);
  const [mostrarModalNovoUsuario, setMostrarModalNovoUsuario] =
    useState<boolean>(false);
  const [novoUsuarioAdminForm, setNovoUsuarioAdminForm] = useState({
    nome_completo: "",
    email: "",
    senha: "",
    papel: "assinante_free" as PapelRBAC,
    plano: "free" as PlanoCodigo,
    cargo_organizacao: "",
    telefone_whatsapp: "",
  });

  // Modais de Gestão Avançada de Contas no Painel Admin (RBAC)
  const [usuarioModalEdicao, setUsuarioModalEdicao] =
    useState<UsuarioOAuthRegistrado | null>(null);
  const [formEdicaoUsuario, setFormEdicaoUsuario] = useState({
    nome_completo: "",
    email: "",
    cargo_organizacao: "",
    telefone_whatsapp: "",
    papel: "assinante_free" as PapelRBAC,
    plano_codigo: "free" as PlanoCodigo,
    ativo: true,
  });
  const [salvandoEdicao, setSalvandoEdicao] = useState<boolean>(false);

  const [usuarioModalUso, setUsuarioModalUso] =
    useState<UsuarioOAuthRegistrado | null>(null);
  const [dadosUsoDetalhado, setDadosUsoDetalhado] =
    useState<UsoUsuarioDetalhado | null>(null);
  const [carregandoUsoDetalhado, setCarregandoUsoDetalhado] =
    useState<boolean>(false);

  const [usuarioModalExclusao, setUsuarioModalExclusao] =
    useState<UsuarioOAuthRegistrado | null>(null);
  const [executandoExclusao, setExecutandoExclusao] = useState<boolean>(false);

  const [usuarioModalPlano, setUsuarioModalPlano] =
    useState<UsuarioOAuthRegistrado | null>(null);
  const [novoPlanoSelecionado, setNovoPlanoSelecionado] =
    useState<PlanoCodigo>("pro");
  const [salvandoPlano, setSalvandoPlano] = useState<boolean>(false);

  // Modais de Gestão Avançada de Contas no Painel Admin (RBAC)
  // Estados da Aba "Meu Perfil"
  const [formMeuPerfil, setFormMeuPerfil] = useState({
    nome_completo: "",
    email: "",
    telefone_whatsapp: "",
    cargo_organizacao: "",
    avatar_url: "",
    senha_atual: "",
    nova_senha: "",
    confirmar_nova_senha: "",
  });
  const [mostrarSenhaPerfil, setMostrarSenhaPerfil] = useState<boolean>(false);
  const [salvandoPerfil, setSalvandoPerfil] = useState<boolean>(false);

  // Interface Executiva & Navegação (Top Navbar & Slide-Over Drawer & Modal)
  const [drawerPerfilAberto, setDrawerPerfilAberto] = useState<boolean>(false);
  const [modalNovaStartupAberto, setModalNovaStartupAberto] = useState<boolean>(false);

  // Workspaces EBT e Seleção de Abas
  const [ebts, setEbts] = useState<WorkspaceEBTResumo[]>([]);
  const [ebtAtivaId, setEbtAtivaId] = useState<string>("");
  const [dadosEBT, setDadosEBT] = useState<WorkspaceEBTCompleto | null>(null);
  const [abaAtiva, setAbaAtiva] = useState<AbaId>("canvas");

  // Formulários da Sidebar
  const [novoNomeStartup, setNovoNomeStartup] = useState<string>("");
  const [nomeRenomearStartup, setNomeRenomearStartup] = useState<string>("");
  const [novaConsultoria, setNovaConsultoria] = useState({
    nome_consultoria: "",
    slug: "",
    email_dono: "diretor@consultoria.com",
    plano: "free" as PlanoCodigo,
  });

  // Estados das Abas 1 a 6
  const [formCanvas, setFormCanvas] = useState<
    WorkspaceEBTCompleto["lean_canvas"] | null
  >(null);
  const [formPremissas, setFormPremissas] = useState<
    WorkspaceEBTCompleto["premissas"] | null
  >(null);
  const [formJuridico, setFormJuridico] = useState<
    WorkspaceEBTCompleto["juridico"] | null
  >(null);

  const [novoCapex, setNovoCapex] = useState({
    categoria: "Engenharia e Desenvolvimento do MVP",
    descricao: "",
    valor: 0,
  });
  const [novoOpex, setNovoOpex] = useState({
    categoria: "Custos com Pessoal Técnico (Headcount Tech)",
    descricao: "",
    valor_mensal: 0,
  });
  const [novoPlanoSaaS, setNovoPlanoSaaS] = useState({
    nome_plano: "",
    ticket_mensal: 0,
    usuarios_ativos_base: 0,
    taxas_pagamento_pct: 5.0,
    impostos_pct: 6.0,
    custo_servidor_por_usuario: 0.0,
  });

  // Estados da Aba 8 (Monte Carlo)
  const [resultadoMC, setResultadoMC] = useState<{
    iteracoes: number;
    vpl_medio: number;
    vpl_mediana_p50: number;
    vpl_p10_pessimista: number;
    vpl_p90_otimista: number;
    probabilidade_vpl_positivo_pct: number;
    probabilidade_quebra_caixa_pct: number;
  } | null>(null);

  // Estados da Aba 10 e 11 (IA e PDF)
  const [modoProvedorIA, setModoProvedorIA] = useState<"interno" | "gemini">(
    "interno"
  );
  const [forcarRegeneracaoIA, setForcarRegeneracaoIA] =
    useState<boolean>(false);
  const [chaveGemini, setChaveGemini] = useState<string>("");
  const [modeloGemini, setModeloGemini] =
    useState<string>("gemini-4-argon");
  const [permitirFallbackAutomatico, setPermitirFallbackAutomatico] =
    useState<boolean>(true);
  const [alertaFalhaIA, setAlertaFalhaIA] = useState<ErroFalhaIA | null>(null);

  // Estados de Conectividade e Outbox Offline para IA
  const [redeOnline, setRedeOnline] = useState<boolean>(
    typeof navigator !== "undefined" ? navigator.onLine : true
  );
  const [pendenciasOutbox, setPendenciasOutbox] = useState<
    SolicitacaoIAPendenteOutbox[]
  >(() => carregarOutboxIA());
  const [sincronizandoOutbox, setSincronizandoOutbox] =
    useState<boolean>(false);
  const [mostrarModalOutbox, setMostrarModalOutbox] = useState<boolean>(false);

  const [textoHomologacaoIA, setTextoHomologacaoIA] = useState<string>("");
  const [exigirHomologacaoPDF, setExigirHomologacaoPDF] =
    useState<boolean>(false);
  const [cartaParecerPDF, setCartaParecerPDF] = useState<string>("");
  const [ultimoPDFEmitido, setUltimoPDFEmitido] = useState<{
    id: string;
    storage_key: string;
    sha256_pdf: string;
    url_assinada: string;
    pdf_base64?: string | null;
  } | null>(null);
  const [processandoAcao, setProcessandoAcao] = useState<boolean>(false);

  // Estados da Aba 12 (Governança SaaS & Admin OAuth)
  const [painelGov, setPainelGov] = useState<
    Awaited<ReturnType<typeof api.obterPainelGovernanca>> | null
  >(null);
  const [diasShareLink, setDiasShareLink] = useState<number>(7);
  const [tokenShareGerado, setTokenShareGerado] = useState<string>("");
  const [tokenParaValidar, setTokenParaValidar] = useState<string>("");
  const [resValidacaoShare, setResValidacaoShare] = useState<string>("");
  const [conviteRBACForm, setConviteRBACForm] = useState({
    email_convidado: "",
    papel: "consultor" as PapelRBAC,
    dias_validade: 7,
  });
  const [linkConviteOAuthGerado, setLinkConviteOAuthGerado] =
    useState<string>("");

  function notificarSucesso(msg: string) {
    setErroGlobal(null);
    setMsgSucesso(msg);
    setTimeout(() => setMsgSucesso(null), 5000);
  }

  function notificarErro(err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    setMsgSucesso(null);
    setErroGlobal(msg);
  }

  function sincronizarFormularioPerfil(s: SessaoAutenticada) {
    setFormMeuPerfil({
      nome_completo: s.user.nome_completo || "",
      email: s.user.email || "",
      telefone_whatsapp: s.user.telefone_whatsapp || "",
      cargo_organizacao: s.user.cargo_organizacao || "",
      avatar_url: s.user.avatar_url || "",
      senha_atual: "",
      nova_senha: "",
      confirmar_nova_senha: "",
    });
  }

  async function carregarUsuariosDoPainelRBAC() {
    try {
      setCarregandoUsuariosRBAC(true);
      const lista = await api.listarUsuariosRBAC();
      setUsuariosRBAC(lista);
      const mapaEdicoes: Record<
        string,
        { papel: PapelRBAC; plano_codigo: PlanoCodigo; ativo: boolean }
      > = {};
      for (const u of lista) {
        mapaEdicoes[u.membership_id] = {
          papel: u.papel,
          plano_codigo: u.plano_codigo,
          ativo: u.ativo !== false,
        };
      }
      setEdicoesRBAC(mapaEdicoes);
    } catch (err) {
      notificarErro(err);
    } finally {
      setCarregandoUsuariosRBAC(false);
    }
  }

  function abrirModalEdicao(u: UsuarioOAuthRegistrado) {
    setUsuarioModalEdicao(u);
    setFormEdicaoUsuario({
      nome_completo: u.nome_completo,
      email: u.email,
      cargo_organizacao: u.cargo_organizacao || "",
      telefone_whatsapp: u.telefone_whatsapp || "",
      papel: u.papel,
      plano_codigo: u.plano_codigo,
      ativo: u.ativo !== false,
    });
  }

  async function abrirModalUso(u: UsuarioOAuthRegistrado) {
    setUsuarioModalUso(u);
    setCarregandoUsoDetalhado(true);
    setDadosUsoDetalhado(null);
    try {
      const uso = await api.obterUsoUsuarioPeloAdmin(u.membership_id);
      setDadosUsoDetalhado(uso);
    } catch (err) {
      notificarErro(err);
    } finally {
      setCarregandoUsoDetalhado(false);
    }
  }

  function abrirModalPlano(u: UsuarioOAuthRegistrado) {
    setUsuarioModalPlano(u);
    setNovoPlanoSelecionado(u.plano_codigo);
  }

  function abrirModalExclusao(u: UsuarioOAuthRegistrado) {
    setUsuarioModalExclusao(u);
  }

  async function handleSalvarEdicaoAvancada(e: React.FormEvent) {
    e.preventDefault();
    if (!usuarioModalEdicao) return;
    if (!formEdicaoUsuario.nome_completo.trim()) {
      notificarErro("O nome completo não pode ficar vazio.");
      return;
    }
    if (!validarFormatoEmail(formEdicaoUsuario.email)) {
      notificarErro("Informe um endereço de e-mail válido.");
      return;
    }
    try {
      setSalvandoEdicao(true);
      await api.gerenciarAssinanteOAuthPeloAdmin(
        usuarioModalEdicao.membership_id,
        {
          nome_completo: formEdicaoUsuario.nome_completo.trim(),
          email: formEdicaoUsuario.email.trim().toLowerCase(),
          cargo_organizacao: formEdicaoUsuario.cargo_organizacao.trim(),
          telefone_whatsapp: formEdicaoUsuario.telefone_whatsapp.trim(),
          novo_papel: formEdicaoUsuario.papel,
          novo_plano: formEdicaoUsuario.plano_codigo,
          ativo: formEdicaoUsuario.ativo,
        }
      );
      setUsuarioModalEdicao(null);
      await carregarUsuariosDoPainelRBAC();
      const s = await api.obterSessaoAtual();
      setSessao(s);
      notificarSucesso(
        `Dados de ${formEdicaoUsuario.nome_completo} atualizados com sucesso!`
      );
    } catch (err) {
      notificarErro(err);
    } finally {
      setSalvandoEdicao(false);
    }
  }

  async function handleSalvarMudancaPlano() {
    if (!usuarioModalPlano) return;
    try {
      setSalvandoPlano(true);
      await api.gerenciarAssinanteOAuthPeloAdmin(
        usuarioModalPlano.membership_id,
        {
          novo_plano: novoPlanoSelecionado,
        }
      );
      setUsuarioModalPlano(null);
      await carregarUsuariosDoPainelRBAC();
      const s = await api.obterSessaoAtual();
      setSessao(s);
      notificarSucesso(
        `Plano de ${usuarioModalPlano.nome_completo} alterado para ${novoPlanoSelecionado.toUpperCase()} com sucesso!`
      );
    } catch (err) {
      notificarErro(err);
    } finally {
      setSalvandoPlano(false);
    }
  }

  async function handleConfirmarExclusaoUsuario() {
    if (!usuarioModalExclusao) return;
    try {
      setExecutandoExclusao(true);
      const res = await api.excluirUsuarioPeloAdmin(
        usuarioModalExclusao.membership_id
      );
      setUsuarioModalExclusao(null);
      await carregarUsuariosDoPainelRBAC();
      notificarSucesso(
        res.mensagem ||
          `Conta de ${usuarioModalExclusao.nome_completo} excluída definitivamente com sucesso.`
      );
    } catch (err) {
      notificarErro(err);
    } finally {
      setExecutandoExclusao(false);
    }
  }

  function abrirModalEdicao(u: UsuarioOAuthRegistrado) {
    setUsuarioModalEdicao(u);
    setFormEdicaoUsuario({
      nome_completo: u.nome_completo,
      email: u.email,
      cargo_organizacao: u.cargo_organizacao || "",
      telefone_whatsapp: u.telefone_whatsapp || "",
      papel: u.papel,
      plano_codigo: u.plano_codigo,
      ativo: u.ativo !== false,
    });
  }

  async function abrirModalUso(u: UsuarioOAuthRegistrado) {
    setUsuarioModalUso(u);
    setCarregandoUsoDetalhado(true);
    setDadosUsoDetalhado(null);
    try {
      const uso = await api.obterUsoUsuarioPeloAdmin(u.membership_id);
      setDadosUsoDetalhado(uso);
    } catch (err) {
      notificarErro(err);
    } finally {
      setCarregandoUsoDetalhado(false);
    }
  }

  function abrirModalPlano(u: UsuarioOAuthRegistrado) {
    setUsuarioModalPlano(u);
    setNovoPlanoSelecionado(u.plano_codigo);
  }

  function abrirModalExclusao(u: UsuarioOAuthRegistrado) {
    setUsuarioModalExclusao(u);
  }

  async function handleSalvarEdicaoAvancada(e: React.FormEvent) {
    e.preventDefault();
    if (!usuarioModalEdicao) return;
    if (!formEdicaoUsuario.nome_completo.trim()) {
      notificarErro("O nome completo não pode ficar vazio.");
      return;
    }
    if (!validarFormatoEmail(formEdicaoUsuario.email)) {
      notificarErro("Informe um endereço de e-mail válido.");
      return;
    }
    try {
      setSalvandoEdicao(true);
      await api.gerenciarAssinanteOAuthPeloAdmin(
        usuarioModalEdicao.membership_id,
        {
          nome_completo: formEdicaoUsuario.nome_completo.trim(),
          email: formEdicaoUsuario.email.trim().toLowerCase(),
          cargo_organizacao: formEdicaoUsuario.cargo_organizacao.trim(),
          telefone_whatsapp: formEdicaoUsuario.telefone_whatsapp.trim(),
          novo_papel: formEdicaoUsuario.papel,
          novo_plano: formEdicaoUsuario.plano_codigo,
          ativo: formEdicaoUsuario.ativo,
        }
      );
      setUsuarioModalEdicao(null);
      await carregarUsuariosDoPainelRBAC();
      const s = await api.obterSessaoAtual();
      setSessao(s);
      notificarSucesso(
        `Dados de ${formEdicaoUsuario.nome_completo} atualizados com sucesso!`
      );
    } catch (err) {
      notificarErro(err);
    } finally {
      setSalvandoEdicao(false);
    }
  }

  async function handleSalvarMudancaPlano() {
    if (!usuarioModalPlano) return;
    try {
      setSalvandoPlano(true);
      await api.gerenciarAssinanteOAuthPeloAdmin(
        usuarioModalPlano.membership_id,
        {
          novo_plano: novoPlanoSelecionado,
        }
      );
      setUsuarioModalPlano(null);
      await carregarUsuariosDoPainelRBAC();
      const s = await api.obterSessaoAtual();
      setSessao(s);
      notificarSucesso(
        `Plano de ${usuarioModalPlano.nome_completo} alterado para ${novoPlanoSelecionado.toUpperCase()} com sucesso!`
      );
    } catch (err) {
      notificarErro(err);
    } finally {
      setSalvandoPlano(false);
    }
  }

  async function handleConfirmarExclusaoUsuario() {
    if (!usuarioModalExclusao) return;
    try {
      setExecutandoExclusao(true);
      const res = await api.excluirUsuarioPeloAdmin(
        usuarioModalExclusao.membership_id
      );
      setUsuarioModalExclusao(null);
      await carregarUsuariosDoPainelRBAC();
      notificarSucesso(
        res.mensagem ||
          `Conta de ${usuarioModalExclusao.nome_completo} excluída definitivamente com sucesso.`
      );
    } catch (err) {
      notificarErro(err);
    } finally {
      setExecutandoExclusao(false);
    }
  }

  useEffect(() => {
    function handleOnline() {
      setRedeOnline(true);
      const pendentes = carregarOutboxIA();
      setPendenciasOutbox(pendentes);
      if (pendentes.length > 0) {
        notificarSucesso(
          `📡 Conexão restabelecida! Há ${pendentes.length} solicitação(ões) de IA salva(s) no dispositivo prontas para sincronização.`
        );
      }
    }
    function handleOffline() {
      setRedeOnline(false);
      notificarErro(
        "Atenção: Seu dispositivo está sem conexão à internet. O sistema operará em Modo Offline / Persistência Ativa."
      );
    }
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  async function handleSolicitarParecerIA(
    ebtId: string,
    forcarFallbackCopiloto = false
  ) {
    if (!ebtId) return;

    // Detecção precoce de rede offline do cliente
    if (!redeOnline && modoProvedorIA === "gemini" && !forcarFallbackCopiloto) {
      const ebtNome = dadosEBT?.premissas?.nome_startup || "EBT em Análise";
      const novaPendencia: SolicitacaoIAPendenteOutbox = {
        id: "pend_" + Date.now(),
        ebt_id: ebtId,
        ebt_nome: ebtNome,
        timestamp: new Date().toISOString(),
        usar_gemini: true,
        modelo_gemini: modeloGemini,
        gemini_api_key: chaveGemini || undefined,
        forcar_regeneracao: forcarRegeneracaoIA,
        codigo_erro: "ERR_NETWORK_DISCONNECTED",
        mensagem_erro:
          "Sem ligação à internet detectada (Código: ERR_NETWORK_DISCONNECTED). Seus dados foram guardados localmente.",
        status: "PENDING_SYNC",
      };
      salvarNoOutboxIA(novaPendencia);
      setPendenciasOutbox(carregarOutboxIA());
      setAlertaFalhaIA({
        codigo_erro: "ERR_NETWORK_DISCONNECTED",
        mensagem_amigavel:
          "Sem ligação à internet detectada (Código: ERR_NETWORK_DISCONNECTED). Seus dados foram guardados localmente.",
        detalhe_tecnico:
          "Dispositivo sem conectividade à internet detectado pelo navegador (navigator.onLine === false).",
        suporta_offline: true,
      });
      return;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 45000);

    try {
      setProcessandoAcao(true);
      setAlertaFalhaIA(null);

      const usarGeminiFinal = forcarFallbackCopiloto
        ? false
        : modoProvedorIA === "gemini";

      const res = await api.solicitarParecerIA(
        ebtId,
        {
          usar_gemini: usarGeminiFinal,
          gemini_api_key: chaveGemini || undefined,
          modelo_gemini: usarGeminiFinal ? modeloGemini : undefined,
          forcar_regeneracao: forcarRegeneracaoIA,
          permitir_fallback_copiloto: permitirFallbackAutomatico,
        },
        controller.signal
      );
      clearTimeout(timeoutId);

      await carregarEBTCompleta(ebtId);

      if (res.fallback_acionado) {
        notificarSucesso(
          "🛡️ Parecer gerado com sucesso via Modo de Resiliência (Copiloto VC Interno) devido à instabilidade na API externa!"
        );
      } else if (res.em_cache) {
        notificarSucesso(
          "⚡ Cache Hit Inteligente! Parecer recuperado sem consumir sua quota mensal!"
        );
      } else {
        const mod =
          res.modelo_resolvido ||
          res.modelo ||
          (usarGeminiFinal ? modeloGemini : "Copiloto VC Interno");
        const tent = res.tentativas_executadas || 1;
        const gen = res.geracao_resolvida ? ` • ${res.geracao_resolvida}` : "";
        notificarSucesso(
          `Parecer gerado com sucesso via ${mod}${gen} (${tent} tentativa${tent > 1 ? "s" : ""})!`
        );
      }
    } catch (err: unknown) {
      clearTimeout(timeoutId);
      const erroObj = err as {
        name?: string;
        codigo_erro?: string;
        mensagem_amigavel?: string;
        message?: string;
        detalhe?: string;
        status?: number;
      };

      const codigo =
        erroObj.codigo_erro ||
        (erroObj.name === "AbortError"
          ? "ERR_GEMINI_TIMEOUT_504"
          : !redeOnline
          ? "ERR_NETWORK_DISCONNECTED"
          : erroObj.status === 422
          ? "ERR_VALIDACAO_DADOS"
          : erroObj.status === 400
          ? "ERR_REQUISICAO_INVALIDA"
          : "ERR_GEMINI_ALL_MODELS_EXHAUSTED");

      const msg =
        erroObj.mensagem_amigavel ||
        erroObj.message ||
        `Não foi possível conectar ao serviço de inteligência artificial no momento (Código: ${codigo}).`;

      // Persistência automática no Outbox se for requisição ao Gemini
      if (modoProvedorIA === "gemini" && !forcarFallbackCopiloto) {
        const ebtNome = dadosEBT?.premissas?.nome_startup || "EBT em Análise";
        const novaPendencia: SolicitacaoIAPendenteOutbox = {
          id: "pend_" + Date.now(),
          ebt_id: ebtId,
          ebt_nome: ebtNome,
          timestamp: new Date().toISOString(),
          usar_gemini: true,
          modelo_gemini: modeloGemini,
          gemini_api_key: chaveGemini || undefined,
          forcar_regeneracao: forcarRegeneracaoIA,
          codigo_erro: codigo,
          mensagem_erro: msg,
          status: "PENDING_SYNC",
        };
        salvarNoOutboxIA(novaPendencia);
        setPendenciasOutbox(carregarOutboxIA());
      }

      setAlertaFalhaIA({
        codigo_erro: codigo,
        mensagem_amigavel: msg,
        detalhe_tecnico: erroObj.detalhe || erroObj.message,
        suporta_offline: true,
        status_http: erroObj.status,
      });
    } finally {
      setProcessandoAcao(false);
    }
  }

  async function handleSincronizarPendenciasOutbox() {
    const pendentes = carregarOutboxIA();
    if (pendentes.length === 0) {
      notificarSucesso("Nenhuma pendência na fila de persistência offline.");
      return;
    }
    setSincronizandoOutbox(true);
    let sucessos = 0;
    let falhas = 0;

    for (const item of pendentes) {
      try {
        await api.solicitarParecerIA(item.ebt_id, {
          usar_gemini: item.usar_gemini,
          gemini_api_key: item.gemini_api_key,
          modelo_gemini: item.modelo_gemini,
          forcar_regeneracao: item.forcar_regeneracao,
          permitir_fallback_copiloto: true,
        });
        removerDoOutboxIA(item.id);
        sucessos++;
      } catch {
        falhas++;
      }
    }

    const restantes = carregarOutboxIA();
    setPendenciasOutbox(restantes);
    setSincronizandoOutbox(false);

    if (ebtAtivaId) {
      await carregarEBTCompleta(ebtAtivaId);
    }

    if (falhas === 0) {
      setAlertaFalhaIA(null);
      notificarSucesso(
        `✅ Todas as ${sucessos} pendência(s) de IA foram sincronizadas e processadas com sucesso!`
      );
    } else {
      notificarErro(
        `Sincronização parcial: ${sucessos} processada(s), ${falhas} ainda pendente(s) devido a instabilidade de rede.`
      );
    }
  }

  function handleRemoverPendenciaOutbox(id: string) {
    removerDoOutboxIA(id);
    setPendenciasOutbox(carregarOutboxIA());
    notificarSucesso("Solicitação removida da fila de persistência.");
  }

  function handleLimparOutboxCompleto() {
    limparOutboxIA();
    setPendenciasOutbox([]);
    setAlertaFalhaIA(null);
    setSincronizandoOutbox(false);
    setProcessandoAcao(false);
    notificarSucesso("Fila de persistência limpa e interface destravada com sucesso.");
  }

  useEffect(() => {
    async function inicializar() {
      const tok = obterTokenSalvo();
      if (!tok) {
        setCarregandoAuth(false);
        return;
      }
      try {
        const s = await api.obterSessaoAtual();
        setSessao(s);
        sincronizarFormularioPerfil(s);
        await carregarListaEBTs();
      } catch {
        limparToken();
      } finally {
        setCarregandoAuth(false);
      }
    }
    inicializar();
  }, []);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setDrawerPerfilAberto(false);
        setModalNovaStartupAberto(false);
        setMostrarModalNovoUsuario(false);
        setUsuarioModalRBAC(null);
        setUsuarioModalEdicao(null);
        setUsuarioModalUso(null);
        setUsuarioModalExclusao(null);
        setUsuarioModalPlano(null);
        setMostrarModalOutbox(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  async function carregarListaEBTs(preferidaId?: string) {
    const lista = await api.listarEBTs();
    setEbts(lista);
    if (lista.length > 0) {
      const alvo =
        preferidaId && lista.some((e) => e.id === preferidaId)
          ? preferidaId
          : lista[0].id;
      setEbtAtivaId(alvo);
      await carregarEBTCompleta(alvo);
    }
  }

  async function carregarEBTCompleta(ebtId: string) {
    const completo = await api.obterEBTCompleto(ebtId);
    setDadosEBT(completo);
    setNomeRenomearStartup(completo.ebt.nome_startup);
    setFormCanvas(completo.lean_canvas);
    setFormPremissas(completo.premissas);
    setFormJuridico(completo.juridico);
    setResultadoMC(null);
    const parecerAtivo =
      completo.ia_governanca.ultima_analise?.parecer_revisado_consultor_md ||
      completo.ia_governanca.ultima_analise?.parecer_gerado_md ||
      "";
    setTextoHomologacaoIA(parecerAtivo);
    setCartaParecerPDF(parecerAtivo);
  }

  useEffect(() => {
    if (!sessao) return;
    if (abaAtiva === "governanca") {
      api.obterPainelGovernanca().then(setPainelGov).catch(notificarErro);
    }
    if (
      abaAtiva === "painel_rbac" &&
      (sessao.membership_ativa.papel === "admin" ||
        sessao.membership_ativa.papel === "dono")
    ) {
      carregarUsuariosDoPainelRBAC();
    }
  }, [abaAtiva, sessao]);

  async function handleLoginCredenciais(e: React.FormEvent) {
    e.preventDefault();
    setErroValidacaoLogin(null);
    setErroGlobal(null);

    const emailLimpo = emailLogin.trim().toLowerCase();
    if (!validarFormatoEmail(emailLimpo)) {
      setErroValidacaoLogin(
        "Informe um endereço de e-mail válido (ex.: usuario@dominio.com.br)."
      );
      return;
    }
    if (!senhaLogin) {
      setErroValidacaoLogin("Informe a sua senha para entrar no sistema.");
      return;
    }

    try {
      setSubmetendoLogin(true);
      const novaSessao = await api.loginCredenciais({
        email: emailLimpo,
        senha: senhaLogin,
      });
      salvarToken(novaSessao.access_token);
      setSessao(novaSessao);
      sincronizarFormularioPerfil(novaSessao);
      setSenhaLogin("");
      await carregarListaEBTs();
      notificarSucesso(
        `Bem-vindo(a), ${novaSessao.user.nome_completo}! Acesso autenticado com perfil ${novaSessao.membership_ativa.papel.toUpperCase()}.`
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setErroValidacaoLogin(msg);
    } finally {
      setSubmetendoLogin(false);
    }
  }

  async function handleRegistrarNovaConta(e: React.FormEvent) {
    e.preventDefault();
    setErroValidacaoLogin(null);
    setErroGlobal(null);

    const emailLimpo = formCadastro.email.trim().toLowerCase();
    if (!formCadastro.nome_completo.trim()) {
      setErroValidacaoLogin("Informe o seu Nome Completo.");
      return;
    }
    if (!validarFormatoEmail(emailLimpo)) {
      setErroValidacaoLogin("Informe um endereço de e-mail válido.");
      return;
    }
    if (formCadastro.senha.length < 6) {
      setErroValidacaoLogin("A senha deve possuir pelo menos 6 caracteres.");
      return;
    }

    try {
      setSubmetendoLogin(true);
      const novaSessao = await api.registrarUsuario({
        nome_completo: formCadastro.nome_completo.trim(),
        email: emailLimpo,
        senha: formCadastro.senha,
        telefone_whatsapp: formCadastro.telefone_whatsapp.trim(),
        cargo_organizacao: formCadastro.cargo_organizacao.trim(),
      });
      salvarToken(novaSessao.access_token);
      setSessao(novaSessao);
      sincronizarFormularioPerfil(novaSessao);
      await carregarListaEBTs();
      notificarSucesso(
        `Conta criada com sucesso! Bem-vindo(a), ${novaSessao.user.nome_completo}.`
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setErroValidacaoLogin(msg);
    } finally {
      setSubmetendoLogin(false);
    }
  }

  async function handleSalvarMeuPerfil(e: React.FormEvent) {
    e.preventDefault();
    if (!formMeuPerfil.nome_completo.trim()) {
      notificarErro("O Nome Completo não pode ficar vazio.");
      return;
    }
    if (!validarFormatoEmail(formMeuPerfil.email)) {
      notificarErro("Informe um endereço de e-mail válido.");
      return;
    }
    if (formMeuPerfil.nova_senha) {
      if (!formMeuPerfil.senha_atual) {
        notificarErro(
          "Informe a sua Senha Atual para confirmar a alteração de senha."
        );
        return;
      }
      if (formMeuPerfil.nova_senha.length < 6) {
        notificarErro("A Nova Senha deve possuir pelo menos 6 caracteres.");
        return;
      }
      if (
        formMeuPerfil.confirmar_nova_senha &&
        formMeuPerfil.nova_senha !== formMeuPerfil.confirmar_nova_senha
      ) {
        notificarErro("A confirmação da nova senha não confere.");
        return;
      }
    }

    try {
      setSalvandoPerfil(true);
      const sessaoAtualizada = await api.atualizarMeuPerfil({
        nome_completo: formMeuPerfil.nome_completo.trim(),
        email: formMeuPerfil.email.trim().toLowerCase(),
        telefone_whatsapp: formMeuPerfil.telefone_whatsapp.trim(),
        cargo_organizacao: formMeuPerfil.cargo_organizacao.trim(),
        avatar_url: formMeuPerfil.avatar_url.trim(),
        senha_atual: formMeuPerfil.nova_senha
          ? formMeuPerfil.senha_atual
          : undefined,
        nova_senha: formMeuPerfil.nova_senha
          ? formMeuPerfil.nova_senha
          : undefined,
      });
      salvarToken(sessaoAtualizada.access_token);
      setSessao(sessaoAtualizada);
      sincronizarFormularioPerfil(sessaoAtualizada);
      notificarSucesso(
        "Dados de 'Meu Perfil' atualizados e salvos com sucesso!"
      );
    } catch (err) {
      notificarErro(err);
    } finally {
      setSalvandoPerfil(false);
    }
  }

  function handleUploadAvatarArquivo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      notificarErro("A imagem de avatar deve ter no máximo 2 MB.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        setFormMeuPerfil((prev) => ({
          ...prev,
          avatar_url: reader.result as string,
        }));
      }
    };
    reader.readAsDataURL(file);
  }

  async function handleTrocarMembershipOAuth(membershipId: string) {
    try {
      const novaSessao = await api.alternarMembership({
        membership_id: membershipId,
      });
      salvarToken(novaSessao.access_token);
      setSessao(novaSessao);
      sincronizarFormularioPerfil(novaSessao);
      await carregarListaEBTs();
      if (abaAtiva === "governanca") {
        const g = await api.obterPainelGovernanca();
        setPainelGov(g);
      }
      if (
        abaAtiva === "painel_rbac" &&
        novaSessao.membership_ativa.papel !== "admin" &&
        novaSessao.membership_ativa.papel !== "dono"
      ) {
        setAbaAtiva("canvas");
      }
      notificarSucesso(
        `Contexto alternado para [${novaSessao.membership_ativa.papel.toUpperCase()}] ${novaSessao.user.nome_completo} (Plano ${novaSessao.tenant.plano_codigo.toUpperCase()}).`
      );
    } catch (err) {
      notificarErro(err);
    }
  }

  function handleLogout() {
    limparToken();
    setSessao(null);
    setDadosEBT(null);
    setErroGlobal(null);
    setErroValidacaoLogin(null);
    setAbaAtiva("canvas");
  }

  if (carregandoAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0A0A0A] text-white relative overflow-hidden font-executive">
        <div className="absolute -top-16 -right-16 pointer-events-none">
          <WatermarkLinhasGeometricas className="w-96 h-96 opacity-10" />
        </div>
        <div className="bg-[#121212] border border-[#27272A] p-8 rounded-2xl max-w-md w-full text-center shadow-2xl relative z-10 space-y-4">
          <div className="flex justify-center">
            <LogoMasterManagement className="w-16 h-16 animate-pulse" />
          </div>
          <div>
            <h2 className="text-lg font-black tracking-wider text-white uppercase font-executive">
              MASTER <span className="text-[#E30000]">MANAGEMENT</span>
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Inicializando ambiente seguro de Venture Capital...
            </p>
          </div>
          <div className="w-full bg-[#27272A] rounded-full h-1.5 overflow-hidden">
            <div className="bg-[#E30000] h-1.5 rounded-full animate-pulse w-3/4"></div>
          </div>
        </div>
      </div>
    );
  }

  // ===========================================================================
  // 1. INTERFACE DE AUTENTICAÇÃO PROTEGIDA (MASTER MANAGEMENT DARK EXECUTIVE)
  // Bloqueia acesso a todas as rotas/telas para usuários não autenticados.
  // ===========================================================================
  if (!sessao) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] text-white flex flex-col justify-center items-center p-4 sm:p-6 relative overflow-hidden font-executive">
        {/* Marca d'água geométrica concêntrica nos cantos (WCAG e Master Management branding) */}
        <div className="absolute -top-24 -left-24 pointer-events-none">
          <WatermarkLinhasGeometricas className="w-96 h-96 opacity-20" />
        </div>
        <div className="absolute -bottom-24 -right-24 pointer-events-none">
          <WatermarkLinhasGeometricas className="w-96 h-96 opacity-20" />
        </div>

        <div className="max-w-md w-full relative z-10">
          <div className="bg-[#121212] border border-[#27272A] rounded-2xl p-6 sm:p-8 shadow-2xl space-y-6">
            {/* Header com Logotipo e Tipografia Imponente */}
            <div className="flex items-center gap-4">
              <LogoMasterManagement className="w-12 h-12 flex-shrink-0" />
              <div>
                <h1 className="text-xl font-black tracking-wider text-white uppercase leading-none font-executive">
                  MASTER <span className="text-[#E30000]">MANAGEMENT</span>
                </h1>
                <p className="text-[10px] tracking-widest text-slate-400 font-bold uppercase mt-1">
                  Strategic Consulting & Venture Capital
                </p>
              </div>
            </div>

            {/* Alternador Login / Cadastro com alto contraste */}
            <div className="grid grid-cols-2 gap-1 bg-[#18181B] p-1.5 rounded-xl border border-[#27272A]">
              <button
                type="button"
                onClick={() => {
                  setModoAuthTela("login");
                  setErroValidacaoLogin(null);
                }}
                className={`py-2 text-xs font-bold rounded-lg transition flex items-center justify-center gap-1.5 ${
                  modoAuthTela === "login"
                    ? "bg-[#E30000] text-white shadow-md shadow-red-950/40"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <span>🔐</span> Entrar no Sistema
              </button>
              <button
                type="button"
                onClick={() => {
                  setModoAuthTela("cadastro");
                  setErroValidacaoLogin(null);
                }}
                className={`py-2 text-xs font-bold rounded-lg transition flex items-center justify-center gap-1.5 ${
                  modoAuthTela === "cadastro"
                    ? "bg-[#E30000] text-white shadow-md shadow-red-950/40"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <span>✨</span> Criar Nova Conta
              </button>
            </div>

            {(erroValidacaoLogin || erroGlobal) && (
              <div
                role="alert"
                className="bg-red-950/70 border border-[#E30000] text-red-200 rounded-xl p-3.5 text-xs font-medium flex items-start gap-2"
              >
                <span className="text-base text-[#E30000]">⚠️</span>
                <span>{erroValidacaoLogin || erroGlobal}</span>
              </div>
            )}

            {modoAuthTela === "login" ? (
              <form
                onSubmit={handleLoginCredenciais}
                className="space-y-4"
                noValidate
              >
                <div>
                  <label
                    htmlFor="login-email"
                    className="block text-xs font-bold text-slate-300 mb-1.5"
                  >
                    E-mail Corporativo
                  </label>
                  <input
                    id="login-email"
                    type="email"
                    required
                    autoComplete="email"
                    placeholder="seu.email@empresa.com.br"
                    className="w-full bg-[#1A1A1A] border border-[#3F3F46] rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-[#E30000] focus:ring-1 focus:ring-[#E30000] transition"
                    value={emailLogin}
                    onChange={(e) => {
                      setEmailLogin(e.target.value);
                      if (erroValidacaoLogin) setErroValidacaoLogin(null);
                    }}
                  />
                </div>

                <div>
                  <label
                    htmlFor="login-senha"
                    className="block text-xs font-bold text-slate-300 mb-1.5"
                  >
                    Senha de Acesso
                  </label>
                  <div className="relative">
                    <input
                      id="login-senha"
                      type={mostrarSenhaLogin ? "text" : "password"}
                      required
                      autoComplete="current-password"
                      placeholder="Digite sua senha"
                      className="w-full bg-[#1A1A1A] border border-[#3F3F46] rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-[#E30000] focus:ring-1 focus:ring-[#E30000] transition pr-24"
                      value={senhaLogin}
                      onChange={(e) => {
                        setSenhaLogin(e.target.value);
                        if (erroValidacaoLogin) setErroValidacaoLogin(null);
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => setMostrarSenhaLogin((v) => !v)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-bold text-slate-300 hover:text-white px-2 py-1 rounded bg-[#27272A] hover:bg-[#3F3F46] transition"
                      title={
                        mostrarSenhaLogin ? "Ocultar senha" : "Visualizar senha"
                      }
                    >
                      {mostrarSenhaLogin ? "🙈 Ocultar" : "👁️ Mostrar"}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={submetendoLogin}
                  className="st-btn w-full !py-3 !text-sm flex items-center justify-center gap-2"
                >
                  {submetendoLogin ? (
                    <>
                      <span className="animate-spin inline-block">⏳</span>
                      <span>Validando credenciais...</span>
                    </>
                  ) : (
                    <span>Entrar no Sistema</span>
                  )}
                </button>
              </form>
            ) : (
              <form
                onSubmit={handleRegistrarNovaConta}
                className="space-y-3.5"
                noValidate
              >
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1">
                    Nome Completo *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="Seu nome completo"
                    className="w-full bg-[#1A1A1A] border border-[#3F3F46] rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#E30000] focus:ring-1 focus:ring-[#E30000]"
                    value={formCadastro.nome_completo}
                    onChange={(e) =>
                      setFormCadastro({
                        ...formCadastro,
                        nome_completo: e.target.value,
                      })
                    }
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1">
                    E-mail Corporativo *
                  </label>
                  <input
                    type="email"
                    required
                    placeholder="seu.email@empresa.com.br"
                    className="w-full bg-[#1A1A1A] border border-[#3F3F46] rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#E30000] focus:ring-1 focus:ring-[#E30000]"
                    value={formCadastro.email}
                    onChange={(e) =>
                      setFormCadastro({
                        ...formCadastro,
                        email: e.target.value,
                      })
                    }
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-slate-300 mb-1">
                      Telefone / WhatsApp
                    </label>
                    <input
                      type="text"
                      placeholder="(11) 99999-9999"
                      className="w-full bg-[#1A1A1A] border border-[#3F3F46] rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#E30000] focus:ring-1 focus:ring-[#E30000]"
                      value={formCadastro.telefone_whatsapp}
                      onChange={(e) =>
                        setFormCadastro({
                          ...formCadastro,
                          telefone_whatsapp: e.target.value,
                        })
                      }
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-300 mb-1">
                      Cargo / Organização
                    </label>
                    <input
                      type="text"
                      placeholder="Ex: CEO / Startup TIC"
                      className="w-full bg-[#1A1A1A] border border-[#3F3F46] rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#E30000] focus:ring-1 focus:ring-[#E30000]"
                      value={formCadastro.cargo_organizacao}
                      onChange={(e) =>
                        setFormCadastro({
                          ...formCadastro,
                          cargo_organizacao: e.target.value,
                        })
                      }
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1">
                    Senha (mínimo 6 caracteres) *
                  </label>
                  <div className="relative">
                    <input
                      type={mostrarSenhaLogin ? "text" : "password"}
                      required
                      placeholder="Crie uma senha segura"
                      className="w-full bg-[#1A1A1A] border border-[#3F3F46] rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#E30000] focus:ring-1 focus:ring-[#E30000] pr-20"
                      value={formCadastro.senha}
                      onChange={(e) =>
                        setFormCadastro({
                          ...formCadastro,
                          senha: e.target.value,
                        })
                      }
                    />
                    <button
                      type="button"
                      onClick={() => setMostrarSenhaLogin((v) => !v)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-bold text-slate-300 hover:text-white px-2 py-1 rounded bg-[#27272A]"
                    >
                      {mostrarSenhaLogin ? "🙈" : "👁️"}
                    </button>
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={submetendoLogin}
                  className="st-btn w-full !py-2.5 !text-sm flex items-center justify-center gap-2"
                >
                  {submetendoLogin
                    ? "⏳ Cadastrando conta..."
                    : "Criar Conta e Entrar no Sistema"}
                </button>
              </form>
            )}

            <div className="pt-4 border-t border-[#27272A] flex items-center justify-between text-[11px] text-slate-400">
              <span className="flex items-center gap-1">
                <span>🔒</span> Sessão Criptografada JWT + PBKDF2
              </span>
              <span className="font-semibold text-slate-300">
                Multi-Tenant RBAC
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Variáveis derivadas da simulação (idênticas ao app.py)
  const sim = dadosEBT?.simulacao_base;
  const dre = sim?.dre_base;
  const ue = sim?.unit_economics;
  const viab = sim?.viabilidade;
  const series = sim?.series_temporais;

  const permissoesAtivas = new Set(sessao.membership_ativa.permissoes);
  const podeEditarDiagnostico = permissoesAtivas.has("ebt:editar_diagnostico");
  const ehAdmin =
    sessao.membership_ativa.papel === "admin" ||
    sessao.membership_ativa.papel === "dono";

  const testesImunidade = formJuridico
    ? [
        {
          label: "O Código-Fonte Tecnológico está Patenteado e Salvo",
          ok: formJuridico.registro_inpi !== "Não Iniciado",
        },
        {
          label: "A Identidade do Produto não está vulnerável a Plágios",
          ok: formJuridico.marca_status !== "Não Iniciado",
        },
        {
          label: "A Base de Clientes está blindada segundo o RGPD/LGPD",
          ok: formJuridico.adequacao_lgpd,
        },
        {
          label: "A Tabela de Sócios (Cap Table) está blindada com Vesting",
          ok: formJuridico.contrato_vesting,
        },
      ]
    : [];
  const pontuacaoSeguranca = testesImunidade.filter((t) => t.ok).length;

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-[#0F172A] flex flex-col font-executive">
      {/* =====================================================================
          1. TOP NAVBAR EXECUTIVO (IDENTIDADE VISUAL MASTER MANAGEMENT)
      ===================================================================== */}
      <header className="bg-[#0A0A0A] text-white border-b border-[#27272A] sticky top-0 z-30 shadow-lg">
        {/* Faixa Superior: Marca Oficial + Seletor Rápido de EBT + Perfil Drawer Trigger */}
        <div className="w-full px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          {/* Lado Esquerdo: Identidade Visual e Logotipo Oficial Master Management */}
          <div className="flex items-center gap-3.5 flex-shrink-0">
            <div className="relative flex items-center justify-center">
              <LogoMasterManagement className="w-10 h-10" />
            </div>
            <div className="flex flex-col">
              <span className="text-base sm:text-lg font-black tracking-wider text-white uppercase leading-tight font-executive">
                MASTER <span className="text-[#E30000]">MANAGEMENT</span>
              </span>
              <span className="text-[9px] sm:text-[10px] tracking-[0.22em] text-slate-400 font-bold uppercase leading-none">
                Venture Capital & Advisory
              </span>
            </div>
          </div>

          {/* Centro: Seletor Rápido de Startup (Workspace EBT) */}
          <div className="hidden md:flex items-center gap-2.5 flex-1 max-w-xl mx-4">
            <div className="flex items-center gap-2 bg-[#171717] border border-[#2E2E32] rounded-xl px-3 py-1.5 w-full shadow-inner">
              <span className="text-xs font-bold text-slate-400 flex items-center gap-1 flex-shrink-0">
                <span className="text-sm">🚀</span> Startup:
              </span>
              <select
                aria-label="Selecionar Startup Ativa"
                className="bg-transparent text-xs font-extrabold text-white focus:outline-none flex-1 truncate cursor-pointer"
                value={ebtAtivaId}
                onChange={(e) => {
                  setEbtAtivaId(e.target.value);
                  carregarEBTCompleta(e.target.value);
                }}
              >
                {ebts.map((e) => (
                  <option
                    key={e.id}
                    value={e.id}
                    className="bg-[#171717] text-white font-medium"
                  >
                    {e.nome_startup}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => setModalNovaStartupAberto(true)}
                title="Criar novo Workspace EBT"
                className="text-[11px] font-bold px-2 py-0.5 rounded bg-[#E30000] hover:bg-[#C00000] text-white transition flex items-center gap-1 flex-shrink-0"
              >
                <span>➕</span> Nova
              </button>
            </div>
          </div>

          {/* Lado Direito: Badges de Plano/Papel + Avatar Pill (Dispara o Slide-Over Drawer) */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <div className="hidden xl:flex items-center gap-2">
              <span className="px-2.5 py-1 text-[11px] font-bold rounded-lg bg-[#18181B] text-slate-300 border border-[#27272A] flex items-center gap-1.5">
                <span className="text-xs">🏢</span>
                <span className="truncate max-w-[140px]">
                  {sessao.tenant.nome}
                </span>
              </span>
              <span className="px-2 py-1 text-[10px] font-black tracking-wider rounded-lg bg-emerald-950/80 text-emerald-400 border border-emerald-800 uppercase">
                {sessao.tenant.plano_codigo}
              </span>
            </div>

            <button
              type="button"
              onClick={() => setDrawerPerfilAberto(true)}
              aria-haspopup="dialog"
              aria-expanded={drawerPerfilAberto}
              aria-label="Abrir centro de controle e perfil do usuário"
              className="flex items-center gap-2.5 p-1 sm:px-3 sm:py-1.5 rounded-xl bg-[#171717] hover:bg-[#222226] border border-[#2E2E32] hover:border-slate-600 transition focus:outline-none focus:ring-2 focus:ring-[#E30000]"
            >
              {sessao.user.avatar_url ? (
                <img
                  src={sessao.user.avatar_url}
                  alt={sessao.user.nome_completo}
                  className="w-8 h-8 rounded-full object-cover border-2 border-[#E30000] flex-shrink-0"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-[#E30000] text-white font-black flex items-center justify-center text-xs flex-shrink-0 shadow-sm">
                  {obterIniciais(sessao.user.nome_completo)}
                </div>
              )}
              <div className="hidden sm:flex flex-col text-left">
                <span className="text-xs font-bold text-white truncate max-w-[130px]">
                  {sessao.user.nome_completo}
                </span>
                <span className="text-[10px] text-slate-400 font-semibold uppercase flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#E30000] inline-block"></span>
                  {sessao.membership_ativa.papel}
                </span>
              </div>
              <span className="text-slate-400 text-xs hidden sm:inline ml-0.5">
                ▼
              </span>
            </button>
          </div>
        </div>

        {/* Faixa Inferior: Menu Horizontal Superior de Abas (Com rolagem suave e destaque em Vermelho Master) */}
        <div className="bg-[#121212] border-t border-[#27272A] px-4 sm:px-6">
          <nav
            role="tablist"
            aria-label="Navegação das Abas do Plano de Negócios"
            className="flex items-center gap-1.5 overflow-x-auto tabs-scrollbar py-2 text-xs"
          >
            {ABAS_STREAMLIT.filter((t) => !t.adminOnly || ehAdmin).map((t) => {
              const ativa = abaAtiva === t.id;
              return (
                <button
                  key={t.id}
                  role="tab"
                  aria-selected={ativa}
                  onClick={() => setAbaAtiva(t.id)}
                  className={`flex-shrink-0 px-3.5 py-2 rounded-lg font-bold transition flex items-center gap-1.5 focus:outline-none focus:ring-2 focus:ring-[#E30000] ${
                    ativa
                      ? "bg-[#E30000] text-white shadow-md shadow-red-950/50 border-b-2 border-white"
                      : "text-slate-300 hover:text-white hover:bg-[#27272A]"
                  }`}
                >
                  <span>{t.label}</span>
                </button>
              );
            })}
          </nav>
        </div>
      </header>

      {/* Banner de Modo Offline & Persistência Ativa */}
      {(!redeOnline || pendenciasOutbox.length > 0) && (
        <div
          role="status"
          aria-live="polite"
          className={`border-b px-4 sm:px-6 py-2.5 text-xs flex flex-wrap items-center justify-between gap-3 ${
            !redeOnline
              ? "bg-amber-950/80 border-amber-600/50 text-amber-200"
              : "bg-[#18181B] border-[#3F3F46] text-slate-200"
          }`}
        >
          <div className="flex items-center gap-2.5">
            <span className="flex h-2.5 w-2.5 relative">
              <span
                className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  !redeOnline ? "bg-amber-400" : "bg-[#E30000]"
                }`}
              />
              <span
                className={`relative inline-flex rounded-full h-2.5 w-2.5 ${
                  !redeOnline ? "bg-amber-500" : "bg-[#E30000]"
                }`}
              />
            </span>
            <div className="font-medium">
              <span className="font-extrabold text-white">
                {!redeOnline
                  ? "Operando em Modo Offline"
                  : "Persistência Ativa Local"}
                :
              </span>{" "}
              {pendenciasOutbox.length > 0 ? (
                <span>
                  Há <strong>{pendenciasOutbox.length}</strong> solicitação(ões)
                  de IA salva(s) no dispositivo prontas para envio.
                </span>
              ) : (
                <span>
                  Conexão de rede ausente. Suas solicitações de IA serão salvas
                  localmente e sincronizadas quando restabelecida.
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {pendenciasOutbox.length > 0 && (
              <>
                <button
                  type="button"
                  disabled={sincronizandoOutbox}
                  onClick={handleSincronizarPendenciasOutbox}
                  className="px-3 py-1.5 rounded-lg bg-[#E30000] hover:bg-[#C00000] text-white font-bold text-xs inline-flex items-center gap-1.5 transition shadow-sm focus:outline-none focus:ring-2 focus:ring-[#E30000]"
                  title="Reenviar todas as solicitações salvas localmente para a API"
                  aria-label="Sincronizar e reenviar solicitações de IA pendentes"
                >
                  <span>{sincronizandoOutbox ? "⏳" : "🔄"}</span>
                  <span>
                    {sincronizandoOutbox
                      ? "Sincronizando..."
                      : "Sincronizar / Reenviar Pendências"}
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => setMostrarModalOutbox(true)}
                  className="px-2.5 py-1.5 rounded-lg border border-[#3F3F46] bg-[#27272A] hover:bg-[#3F3F46] text-white text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-slate-400"
                  title="Inspecionar fila de pendências locais"
                >
                  Inspecionar Fila ({pendenciasOutbox.length})
                </button>

                <button
                  type="button"
                  onClick={handleLimparOutboxCompleto}
                  className="px-2.5 py-1.5 rounded-lg border border-red-800 bg-red-950/90 hover:bg-red-900 text-red-200 hover:text-white text-xs font-bold transition focus:outline-none focus:ring-2 focus:ring-red-400 inline-flex items-center gap-1"
                  title="Limpar e destravar a fila de persistência offline"
                >
                  <span>🗑️</span>
                  <span>Limpar Fila</span>
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* =====================================================================
          2. SLIDE-OVER DRAWER (PAINEL DE PERFIL & CONTROLE SAAS)
      ===================================================================== */}
      {drawerPerfilAberto && (
        <div
          className="fixed inset-0 z-50 overflow-hidden font-executive"
          role="dialog"
          aria-modal="true"
        >
          {/* Backdrop Escuro */}
          <div
            className="fixed inset-0 bg-black/75 backdrop-blur-sm transition-opacity"
            onClick={() => setDrawerPerfilAberto(false)}
            aria-hidden="true"
          />

          <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
            <div className="w-screen max-w-md bg-[#121212] border-l border-[#27272A] text-white shadow-2xl flex flex-col justify-between overflow-y-auto">
              {/* Topo do Drawer */}
              <div className="p-6 space-y-6">
                <div className="flex items-center justify-between pb-4 border-b border-[#27272A]">
                  <div className="flex items-center gap-3">
                    <LogoMasterManagement className="w-8 h-8" />
                    <div>
                      <h2 className="text-sm font-black tracking-wider uppercase text-white font-executive">
                        Painel de Controle
                      </h2>
                      <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-widest">
                        Master Management SaaS
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setDrawerPerfilAberto(false)}
                    aria-label="Fechar painel"
                    className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-[#27272A] transition"
                  >
                    ✕
                  </button>
                </div>

                {/* Card do Usuário Autenticado */}
                <div className="bg-[#18181B] border border-[#2E2E32] rounded-xl p-4 space-y-3.5">
                  <div className="flex items-center gap-3">
                    {sessao.user.avatar_url ? (
                      <img
                        src={sessao.user.avatar_url}
                        alt={sessao.user.nome_completo}
                        className="w-12 h-12 rounded-full object-cover border-2 border-[#E30000] flex-shrink-0"
                      />
                    ) : (
                      <div className="w-12 h-12 rounded-full bg-[#E30000] text-white font-black flex items-center justify-center text-sm flex-shrink-0 shadow-md">
                        {obterIniciais(sessao.user.nome_completo)}
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="font-extrabold text-white text-sm truncate">
                        {sessao.user.nome_completo}
                      </div>
                      <div className="text-slate-400 truncate text-xs">
                        {sessao.user.email}
                      </div>
                      {sessao.user.cargo_organizacao && (
                        <div className="text-[11px] text-slate-400 truncate mt-0.5">
                          {sessao.user.cargo_organizacao}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    <span className="px-2 py-0.5 text-[10px] font-black rounded bg-[#E30000] text-white uppercase tracking-wider">
                      Role: {sessao.membership_ativa.papel}
                    </span>
                    <span className="px-2 py-0.5 text-[10px] font-black rounded bg-emerald-950 text-emerald-400 border border-emerald-800 uppercase tracking-wider">
                      Plano: {sessao.tenant.plano_codigo}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => {
                        setAbaAtiva("meu_perfil");
                        setDrawerPerfilAberto(false);
                      }}
                      className="py-2 px-3 font-bold rounded-lg text-xs transition bg-[#27272A] hover:bg-[#3F3F46] text-white flex items-center justify-center gap-1.5"
                    >
                      <span>👤</span> Meu Perfil
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setDrawerPerfilAberto(false);
                        handleLogout();
                      }}
                      className="py-2 px-3 font-bold rounded-lg text-xs transition bg-red-950/60 hover:bg-red-900 border border-red-800 text-red-200 flex items-center justify-center gap-1.5"
                    >
                      <span>🚪</span> Sair
                    </button>
                  </div>

                  {ehAdmin && (
                    <button
                      type="button"
                      onClick={() => {
                        setAbaAtiva("painel_rbac");
                        setDrawerPerfilAberto(false);
                      }}
                      className="w-full py-2 px-3 font-bold rounded-lg text-xs transition bg-[#E30000] hover:bg-[#C00000] text-white flex items-center justify-center gap-2 shadow-sm"
                    >
                      <span>🛡️</span> Abrir Painel Admin (RBAC)
                    </button>
                  )}
                </div>

                {/* Seleção de Papel RBAC */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-bold text-slate-300">
                    🔐 Papel RBAC Ativo (Sessão):
                  </label>
                  <select
                    className="w-full bg-[#1A1A1A] border border-[#3F3F46] rounded-lg px-3 py-2 text-xs font-semibold text-white focus:outline-none focus:border-[#E30000]"
                    value={sessao.membership_ativa.id}
                    onChange={(e) => handleTrocarMembershipOAuth(e.target.value)}
                  >
                    {sessao.perfis_rbac_tenant.map((p) => (
                      <option
                        key={p.membership_id}
                        value={p.membership_id}
                        className="bg-[#1A1A1A]"
                      >
                        [{p.papel.toUpperCase()} · {p.plano_codigo.toUpperCase()}]{" "}
                        {p.nome} ({p.email})
                      </option>
                    ))}
                  </select>
                  <p className="text-[11px] text-slate-400">
                    Consultoria: <strong>{sessao.tenant.nome}</strong> · EBTs:{" "}
                    <strong>
                      {ebts.length}/{sessao.tenant.limite_ebts}
                    </strong>
                  </p>
                </div>

                <hr className="border-[#27272A]" />

                {/* Gestão de Workspaces EBT */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-black tracking-wider uppercase text-slate-300 flex items-center gap-1.5">
                      <span>📂</span> Workspaces EBT (Startups)
                    </h3>
                    <span className="text-[10px] text-slate-400 font-bold">
                      {ebts.length} cadastradas
                    </span>
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-slate-400 mb-1">
                      Startup Ativa:
                    </label>
                    <select
                      className="w-full bg-[#1A1A1A] border border-[#3F3F46] rounded-lg px-3 py-2 text-xs font-bold text-white focus:outline-none focus:border-[#E30000]"
                      value={ebtAtivaId}
                      onChange={(e) => {
                        setEbtAtivaId(e.target.value);
                        carregarEBTCompleta(e.target.value);
                      }}
                    >
                      {ebts.map((e) => (
                        <option
                          key={e.id}
                          value={e.id}
                          className="bg-[#1A1A1A]"
                        >
                          {e.nome_startup}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Criar Novo Workspace EBT */}
                  <form
                    onSubmit={async (e) => {
                      e.preventDefault();
                      if (!novoNomeStartup.trim()) return;
                      try {
                        const criada = await api.criarEBT({
                          nome_startup: novoNomeStartup.trim(),
                        });
                        setNovoNomeStartup("");
                        await carregarListaEBTs(criada.id);
                        notificarSucesso(
                          "Workspace EBT criado e auditado com sucesso!"
                        );
                      } catch (err) {
                        notificarErro(err);
                      }
                    }}
                    className="bg-[#18181B] border border-[#2E2E32] rounded-xl p-3 space-y-2"
                  >
                    <label className="block text-xs font-bold text-slate-300">
                      Nova Operação (EBT)
                    </label>
                    <input
                      className="w-full bg-[#121212] border border-[#3F3F46] rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#E30000]"
                      value={novoNomeStartup}
                      onChange={(e) => setNovoNomeStartup(e.target.value)}
                      placeholder="Ex: DeepTech SaaS"
                    />
                    <button
                      type="submit"
                      className="st-btn w-full !py-1.5 !text-xs"
                    >
                      ➕ Criar Startup
                    </button>
                  </form>

                  {/* Renomear / Excluir */}
                  <details className="bg-[#18181B] border border-[#2E2E32] rounded-xl p-3 text-xs">
                    <summary className="font-bold cursor-pointer text-slate-300 hover:text-white">
                      ✏️ Renomear / 🗑️ Excluir Startup
                    </summary>
                    <div className="space-y-3 mt-3">
                      <form
                        onSubmit={async (e) => {
                          e.preventDefault();
                          if (!ebtAtivaId || !nomeRenomearStartup.trim()) return;
                          try {
                            await api.renomearEBT(
                              ebtAtivaId,
                              nomeRenomearStartup.trim()
                            );
                            await carregarListaEBTs(ebtAtivaId);
                            notificarSucesso("Nome da startup atualizado!");
                          } catch (err) {
                            notificarErro(err);
                          }
                        }}
                        className="space-y-2"
                      >
                        <label className="block text-xs font-semibold text-slate-300">
                          Novo Nome
                        </label>
                        <input
                          className="w-full bg-[#121212] border border-[#3F3F46] rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#E30000]"
                          value={nomeRenomearStartup}
                          onChange={(e) =>
                            setNomeRenomearStartup(e.target.value)
                          }
                        />
                        <button
                          type="submit"
                          className="w-full py-1.5 px-3 bg-[#27272A] hover:bg-[#3F3F46] text-white font-bold rounded-lg text-xs transition"
                        >
                          Salvar Alteração
                        </button>
                      </form>
                      <div className="bg-amber-950/40 border border-amber-800 text-amber-300 p-2 rounded-lg text-[11px]">
                        ⚠️ Aviso: A exclusão é permanente e destrói o valuation
                        do banco de dados.
                      </div>
                      <button
                        type="button"
                        onClick={async () => {
                          if (!ebtAtivaId) return;
                          try {
                            await api.excluirEBT(ebtAtivaId);
                            await carregarListaEBTs();
                            notificarSucesso("Workspace EBT excluído.");
                          } catch (err) {
                            notificarErro(err);
                          }
                        }}
                        className="w-full py-1.5 px-3 bg-red-950 hover:bg-red-900 border border-red-800 text-red-200 font-bold rounded-lg text-xs transition"
                      >
                        Excluir Startup
                      </button>
                    </div>
                  </details>
                </div>

                {/* Nova Consultoria (Apenas Admin) */}
                {ehAdmin && (
                  <details className="bg-[#18181B] border border-[#2E2E32] rounded-xl p-3 text-xs">
                    <summary className="font-bold cursor-pointer text-slate-300 hover:text-white">
                      ➕ Nova Consultoria (Onboarding Tenant)
                    </summary>
                    <form
                      onSubmit={async (e) => {
                        e.preventDefault();
                        try {
                          await api.criarTenant({
                            nome_consultoria: novaConsultoria.nome_consultoria,
                            slug: novaConsultoria.slug,
                            email_dono: novaConsultoria.email_dono,
                            nome_dono: `Dono ${novaConsultoria.nome_consultoria}`,
                            plano: novaConsultoria.plano,
                          });
                          notificarSucesso("Consultoria criada com sucesso!");
                          setNovaConsultoria({
                            nome_consultoria: "",
                            slug: "",
                            email_dono: "diretor@consultoria.com",
                            plano: "free",
                          });
                        } catch (err) {
                          notificarErro(err);
                        }
                      }}
                      className="space-y-2 mt-3"
                    >
                      <input
                        className="w-full bg-[#121212] border border-[#3F3F46] rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#E30000]"
                        placeholder="Nome da Consultoria"
                        value={novaConsultoria.nome_consultoria}
                        onChange={(e) =>
                          setNovaConsultoria({
                            ...novaConsultoria,
                            nome_consultoria: e.target.value,
                          })
                        }
                        required
                      />
                      <input
                        className="w-full bg-[#121212] border border-[#3F3F46] rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#E30000]"
                        placeholder="Identificador (slug, ex: nordeste-vc)"
                        value={novaConsultoria.slug}
                        onChange={(e) =>
                          setNovaConsultoria({
                            ...novaConsultoria,
                            slug: e.target.value,
                          })
                        }
                        required
                      />
                      <select
                        className="w-full bg-[#121212] border border-[#3F3F46] rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#E30000]"
                        value={novaConsultoria.plano}
                        onChange={(e) =>
                          setNovaConsultoria({
                            ...novaConsultoria,
                            plano: e.target.value as PlanoCodigo,
                          })
                        }
                      >
                        <option value="free">FREE (Gratuito)</option>
                        <option value="starter">STARTER</option>
                        <option value="pro">PRO</option>
                        <option value="enterprise">ENTERPRISE</option>
                      </select>
                      <button
                        type="submit"
                        className="st-btn w-full !py-1.5 !text-xs"
                      >
                        Criar Consultoria
                      </button>
                    </form>
                  </details>
                )}
              </div>

              {/* Rodapé do Drawer */}
              <div className="p-4 border-t border-[#27272A] bg-[#0A0A0A] text-[11px] text-slate-400 flex items-center justify-between">
                <span>🔒 Sessão Criptografada JWT</span>
                <span>Multi-Tenant RBAC</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          MODAL RÁPIDO: CRIAR NOVA STARTUP (ACIONADO PELO TOP NAVBAR)
      ===================================================================== */}
      {modalNovaStartupAberto && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
        >
          <div className="bg-[#121212] border border-[#27272A] rounded-2xl max-w-md w-full p-6 text-white space-y-4 shadow-2xl font-executive">
            <div className="flex items-center justify-between pb-3 border-b border-[#27272A]">
              <div className="flex items-center gap-2">
                <span className="text-xl">🚀</span>
                <h3 className="text-sm font-black uppercase text-white">
                  Criar Novo Workspace EBT
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setModalNovaStartupAberto(false)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (!novoNomeStartup.trim()) return;
                try {
                  const criada = await api.criarEBT({
                    nome_startup: novoNomeStartup.trim(),
                  });
                  setNovoNomeStartup("");
                  setModalNovaStartupAberto(false);
                  await carregarListaEBTs(criada.id);
                  notificarSucesso(
                    "Workspace EBT criado e auditado com sucesso!"
                  );
                } catch (err) {
                  notificarErro(err);
                }
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5">
                  Nome da Nova Operação (EBT) *
                </label>
                <input
                  required
                  autoFocus
                  className="w-full bg-[#1A1A1A] border border-[#3F3F46] rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-[#E30000] focus:ring-1 focus:ring-[#E30000]"
                  placeholder="Ex: FinTech NextGen"
                  value={novoNomeStartup}
                  onChange={(e) => setNovoNomeStartup(e.target.value)}
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setModalNovaStartupAberto(false)}
                  className="px-4 py-2 text-xs font-bold rounded-lg bg-[#27272A] hover:bg-[#3F3F46] text-white"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="st-btn px-4 py-2 !text-xs font-bold"
                >
                  Criar Startup
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* =====================================================================
          3. ÁREA PRINCIPAL — CONTEÚDO EXECUTIVO E ABAS OPERACIONAIS
      ===================================================================== */}
      <main className="flex-1 max-w-[1920px] w-full mx-auto p-4 sm:p-6 space-y-6">
        {/* Sub-Cabeçalho Executivo do Workspace */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-[#0A0A0A] border border-[#27272A] text-white flex items-center justify-center text-xl font-black shadow-sm flex-shrink-0">
              <span className="text-[#E30000]">M</span>M
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-xl sm:text-2xl font-black text-[#0F172A] tracking-tight">
                  Startup: {dadosEBT?.ebt.nome_startup || "Carregando..."}
                </h1>
                <span className="px-2.5 py-0.5 text-[11px] font-bold rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                  ID: {ebtAtivaId ? ebtAtivaId.slice(0, 8) : "..."}
                </span>
              </div>
              <p className="text-xs text-slate-600 mt-1 flex items-center gap-2 flex-wrap">
                <span>
                  Consultoria: <strong>{sessao.tenant.nome}</strong>
                </span>
                <span>·</span>
                <span>
                  Plano:{" "}
                  <strong className="uppercase">
                    {sessao.tenant.plano_codigo}
                  </strong>
                </span>
                <span>·</span>
                <span>
                  Papel:{" "}
                  <code className="bg-slate-100 px-1.5 py-0.5 rounded font-bold uppercase text-slate-800">
                    {sessao.membership_ativa.papel}
                  </code>
                </span>
                <span>·</span>
                <span
                  className={`font-bold ${
                    podeEditarDiagnostico
                      ? "text-emerald-700"
                      : "text-amber-700"
                  }`}
                >
                  {podeEditarDiagnostico
                    ? "✏️ Edição Habilitada"
                    : "🔒 Modo Somente Leitura"}
                </span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setDrawerPerfilAberto(true)}
              className="px-3.5 py-2 text-xs font-bold rounded-lg border border-slate-300 hover:bg-slate-50 text-slate-700 transition flex items-center gap-1.5"
            >
              <span>⚙️</span> Configurações
            </button>
            <button
              type="button"
              onClick={() => setModalNovaStartupAberto(true)}
              className="st-btn !py-2 !px-3.5 !text-xs font-bold"
            >
              <span>➕</span> Nova Startup
            </button>
          </div>
        </div>

        {/* Notificações Globais de Erro e Sucesso */}
        {erroGlobal && (
          <div
            role="alert"
            className="bg-red-50 border-l-4 border-[#E30000] text-red-950 p-4 rounded-xl text-sm flex justify-between items-center shadow-sm"
          >
            <span className="flex items-center gap-2">
              <span className="text-[#E30000] text-base">⚠️</span>
              <span>{erroGlobal}</span>
            </span>
            <button
              onClick={() => setErroGlobal(null)}
              className="text-xs font-bold text-[#E30000] hover:underline ml-4"
            >
              Fechar
            </button>
          </div>
        )}
        {msgSucesso && (
          <div
            role="status"
            className="bg-emerald-50 border-l-4 border-emerald-600 text-emerald-950 p-4 rounded-xl text-sm flex justify-between items-center shadow-sm"
          >
            <span className="flex items-center gap-2">
              <span className="text-emerald-600 text-base">✅</span>
              <span>{msgSucesso}</span>
            </span>
            <button
              onClick={() => setMsgSucesso(null)}
              className="text-xs font-bold text-emerald-800 hover:underline ml-4"
            >
              Fechar
            </button>
          </div>
        )}

        {/* ===================================================================
            ABA 1: 🧩 LEAN CANVAS
        =================================================================== */}
        {abaAtiva === "canvas" && formCanvas && (
          <section className="space-y-4">
            <img
              src="https://images.unsplash.com/photo-1552664730-d307ca884978?q=80&w=1000&auto=format&fit=crop"
              alt="Lean Canvas"
              className="w-full h-40 object-cover rounded-xl"
            />
            <h2 className="text-xl font-extrabold">
              🧩 Lean Canvas — Validação da Dor e da Solução
            </h2>
            <div className="bg-blue-50 border border-blue-200 text-blue-900 rounded-lg p-3 text-sm">
              A matriz do Lean Canvas é o primeiro filtro de um investidor.
              Defina de forma clara a sua Proposta Única de Valor (VPU) e qual o
              seu &apos;Fosso Competitivo&apos; (Vantagem Injusta).
            </div>

            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (!ebtAtivaId || !formCanvas) return;
                try {
                  await api.atualizarLeanCanvas(ebtAtivaId, formCanvas);
                  await carregarEBTCompleta(ebtAtivaId);
                  notificarSucesso(
                    "As diretrizes estratégicas da startup foram atualizadas e auditadas com sucesso."
                  );
                } catch (err) {
                  notificarErro(err);
                }
              }}
              className="st-card space-y-4"
            >
              <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-bold mb-1">
                      1. Problema Mapeado no Mercado
                    </label>
                    <textarea
                      rows={5}
                      disabled={!podeEditarDiagnostico}
                      className="st-input text-xs"
                      value={formCanvas.problema}
                      onChange={(e) =>
                        setFormCanvas({
                          ...formCanvas,
                          problema: e.target.value,
                        })
                      }
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold mb-1">
                      8. Estrutura Macro de Custos
                    </label>
                    <textarea
                      rows={5}
                      disabled={!podeEditarDiagnostico}
                      className="st-input text-xs"
                      value={formCanvas.estrutura_custos}
                      onChange={(e) =>
                        setFormCanvas({
                          ...formCanvas,
                          estrutura_custos: e.target.value,
                        })
                      }
                    />
                  </div>
                </div>

                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-bold mb-1">
                      2. Arquitetura da Solução
                    </label>
                    <textarea
                      rows={5}
                      disabled={!podeEditarDiagnostico}
                      className="st-input text-xs"
                      value={formCanvas.solucao_mvp}
                      onChange={(e) =>
                        setFormCanvas({
                          ...formCanvas,
                          solucao_mvp: e.target.value,
                        })
                      }
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold mb-1">
                      3. Métricas‑Chave (Growth KPIs)
                    </label>
                    <textarea
                      rows={5}
                      disabled={!podeEditarDiagnostico}
                      className="st-input text-xs"
                      value={formCanvas.metricas_chave}
                      onChange={(e) =>
                        setFormCanvas({
                          ...formCanvas,
                          metricas_chave: e.target.value,
                        })
                      }
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold mb-1">
                    4. Proposta Única de Valor (VPU)
                  </label>
                  <textarea
                    rows={12}
                    disabled={!podeEditarDiagnostico}
                    className="st-input text-xs"
                    value={formCanvas.proposta_valor}
                    onChange={(e) =>
                      setFormCanvas({
                        ...formCanvas,
                        proposta_valor: e.target.value,
                      })
                    }
                  />
                </div>

                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-bold mb-1">
                      5. Vantagem Injusta / Fosso (Moat)
                    </label>
                    <textarea
                      rows={5}
                      disabled={!podeEditarDiagnostico}
                      className="st-input text-xs"
                      value={formCanvas.vantagem_injusta}
                      onChange={(e) =>
                        setFormCanvas({
                          ...formCanvas,
                          vantagem_injusta: e.target.value,
                        })
                      }
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold mb-1">
                      6. Canais de Aquisição de Clientes
                    </label>
                    <textarea
                      rows={5}
                      disabled={!podeEditarDiagnostico}
                      className="st-input text-xs"
                      value={formCanvas.canais}
                      onChange={(e) =>
                        setFormCanvas({
                          ...formCanvas,
                          canais: e.target.value,
                        })
                      }
                    />
                  </div>
                </div>

                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-bold mb-1">
                      7. ICP e Segmentos de Clientes
                    </label>
                    <textarea
                      rows={5}
                      disabled={!podeEditarDiagnostico}
                      className="st-input text-xs"
                      value={formCanvas.segmentos}
                      onChange={(e) =>
                        setFormCanvas({
                          ...formCanvas,
                          segmentos: e.target.value,
                        })
                      }
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold mb-1">
                      9. Mecanismos e Fontes de Receita
                    </label>
                    <textarea
                      rows={5}
                      disabled={!podeEditarDiagnostico}
                      className="st-input text-xs"
                      value={formCanvas.fontes_receita}
                      onChange={(e) =>
                        setFormCanvas({
                          ...formCanvas,
                          fontes_receita: e.target.value,
                        })
                      }
                    />
                  </div>
                </div>
              </div>

              <hr className="border-slate-200" />
              <div>
                <h3 className="text-sm font-bold mb-1">
                  🔬 Evidências de Validação Tecnológica (O MVP)
                </h3>
                <textarea
                  rows={3}
                  disabled={!podeEditarDiagnostico}
                  placeholder="Descreva com profundidade as características técnicas do MVP desenvolvido..."
                  className="st-input text-xs"
                  value={formCanvas.mvp_descricao}
                  onChange={(e) =>
                    setFormCanvas({
                      ...formCanvas,
                      mvp_descricao: e.target.value,
                    })
                  }
                />
              </div>

              <hr className="border-slate-200" />
              <div>
                <h3 className="text-sm font-bold mb-1">
                  🌍 Matriz de Impacto e Governança (Agenda ESG / ODS)
                </h3>
                <textarea
                  rows={2}
                  disabled={!podeEditarDiagnostico}
                  placeholder="Qual é o ODS que a sua startup impacta de forma direta?"
                  className="st-input text-xs"
                  value={formCanvas.ods_onu}
                  onChange={(e) =>
                    setFormCanvas({
                      ...formCanvas,
                      ods_onu: e.target.value,
                    })
                  }
                />
              </div>

              <button
                type="submit"
                disabled={!podeEditarDiagnostico}
                className="st-btn w-full"
              >
                💾 Registar Arquitetura do Modelo de Negócios
              </button>
            </form>
          </section>
        )}

        {/* ===================================================================
            ABA 2: 📈 PREMISSAS
        =================================================================== */}
        {abaAtiva === "premissas" && formPremissas && (
          <section className="space-y-4">
            <img
              src="https://images.unsplash.com/photo-1460925895917-afdab827c52f?q=80&w=1000&auto=format&fit=crop"
              alt="Premissas"
              className="w-full h-40 object-cover rounded-xl"
            />
            <h2 className="text-xl font-extrabold">
              📈 Definição de Premissas do Fundo e Motor de Growth
            </h2>
            <div className="bg-blue-50 border border-blue-200 text-blue-900 rounded-lg p-3 text-sm">
              As variáveis definidas nesta área irão ditar a expansão
              logarítmica da startup, incluindo o limite do Valuation e a
              relação de eficiência da aquisição de mercado (CAC vs LTV).
            </div>

            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (!ebtAtivaId || !formPremissas) return;
                try {
                  await api.atualizarPremissas(ebtAtivaId, formPremissas);
                  await carregarEBTCompleta(ebtAtivaId);
                  notificarSucesso(
                    "O Motor Económico foi atualizado e auditado com sucesso."
                  );
                } catch (err) {
                  notificarErro(err);
                }
              }}
              className="st-card space-y-4"
            >
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Horizonte de Avaliação de Risco (Meses)
                  </label>
                  <input
                    type="number"
                    min={12}
                    max={120}
                    disabled={!podeEditarDiagnostico}
                    className="st-input"
                    value={formPremissas.horizonte_meses}
                    onChange={(e) =>
                      setFormPremissas({
                        ...formPremissas,
                        horizonte_meses: Number(e.target.value),
                      })
                    }
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Taxa Mínima de Atratividade (TMA Exigida pelo Fundo % a.a.)
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    disabled={!podeEditarDiagnostico}
                    className="st-input"
                    value={formPremissas.tma_anual_pct}
                    onChange={(e) =>
                      setFormPremissas({
                        ...formPremissas,
                        tma_anual_pct: Number(e.target.value),
                      })
                    }
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Custo Nominal Global de Aquisição de Clientes - CAC (R$)
                  </label>
                  <input
                    type="number"
                    min={0}
                    step="10"
                    disabled={!podeEditarDiagnostico}
                    className="st-input"
                    value={formPremissas.cac_estimado}
                    onChange={(e) =>
                      setFormPremissas({
                        ...formPremissas,
                        cac_estimado: Number(e.target.value),
                      })
                    }
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold mb-1">
                    Taxa Previsional de Evasão de Clientes - Churn (% Mensal)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    disabled={!podeEditarDiagnostico}
                    className="st-input"
                    value={formPremissas.churn_mensal_pct}
                    onChange={(e) =>
                      setFormPremissas({
                        ...formPremissas,
                        churn_mensal_pct: Number(e.target.value),
                      })
                    }
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Funil: Taxa de Conversão de Freemium para Plano Pago (%)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    disabled={!podeEditarDiagnostico}
                    className="st-input"
                    value={formPremissas.conversao_freemium_pct}
                    onChange={(e) =>
                      setFormPremissas({
                        ...formPremissas,
                        conversao_freemium_pct: Number(e.target.value),
                      })
                    }
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Taxa de Expansão e Crescimento Orgânico Mensal da Base (MoM
                    %)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    disabled={!podeEditarDiagnostico}
                    className="st-input"
                    value={formPremissas.crescimento_mensal_pct}
                    onChange={(e) =>
                      setFormPremissas({
                        ...formPremissas,
                        crescimento_mensal_pct: Number(e.target.value),
                      })
                    }
                  />
                </div>
              </div>

              <hr className="border-slate-200" />
              <div>
                <h3 className="text-sm font-bold mb-2">
                  Motor de Lançamento (Go-To-Market)
                </h3>
                <label className="block text-xs font-bold mb-1">
                  Volume de Leads / Utilizadores Gratuitos Adquiridos no Momento
                  Zero
                </label>
                <input
                  type="number"
                  min={0}
                  disabled={!podeEditarDiagnostico}
                  className="st-input max-w-md"
                  value={formPremissas.usuarios_freemium_base}
                  onChange={(e) =>
                    setFormPremissas({
                      ...formPremissas,
                      usuarios_freemium_base: Number(e.target.value),
                    })
                  }
                />
              </div>

              <button
                type="submit"
                disabled={!podeEditarDiagnostico}
                className="st-btn w-full"
              >
                ⚡ Injetar Parâmetros no Motor de Valuation
              </button>
            </form>
          </section>
        )}

        {/* ===================================================================
            ABA 3: 🛠️ CAPEX
        =================================================================== */}
        {abaAtiva === "capex" && dadosEBT && (
          <section className="space-y-4">
            <img
              src="https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?q=80&w=1000&auto=format&fit=crop"
              alt="Capex"
              className="w-full h-40 object-cover rounded-xl"
            />
            <h2 className="text-xl font-extrabold">
              🛠️ Alocação Estratégica do Capital Inicial (Capex)
            </h2>

            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (!ebtAtivaId || !novoCapex.descricao.trim()) return;
                try {
                  await api.adicionarCapex(ebtAtivaId, novoCapex);
                  setNovoCapex({ ...novoCapex, descricao: "", valor: 0 });
                  await carregarEBTCompleta(ebtAtivaId);
                  notificarSucesso("Item Capex adicionado à rodada!");
                } catch (err) {
                  notificarErro(err);
                }
              }}
              className="st-card space-y-4"
            >
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Ramo de Alocação de Recursos
                  </label>
                  <select
                    className="st-input"
                    disabled={!podeEditarDiagnostico}
                    value={novoCapex.categoria}
                    onChange={(e) =>
                      setNovoCapex({ ...novoCapex, categoria: e.target.value })
                    }
                  >
                    <option>Engenharia e Desenvolvimento do MVP</option>
                    <option>Setup de Licenças e Patentes</option>
                    <option>Compra de Infraestrutura / Servidores</option>
                    <option>Orçamento Base de Marketing (GTM)</option>
                    <option>Assessoria Legal de Estruturação</option>
                    <option>Outros</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Finalidade e Descrição Específica
                  </label>
                  <input
                    className="st-input"
                    disabled={!podeEditarDiagnostico}
                    value={novoCapex.descricao}
                    onChange={(e) =>
                      setNovoCapex({ ...novoCapex, descricao: e.target.value })
                    }
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Valor Necessário (R$)
                  </label>
                  <input
                    type="number"
                    min={0}
                    step="1000"
                    className="st-input"
                    disabled={!podeEditarDiagnostico}
                    value={novoCapex.valor}
                    onChange={(e) =>
                      setNovoCapex({
                        ...novoCapex,
                        valor: Number(e.target.value),
                      })
                    }
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={!podeEditarDiagnostico}
                className="st-btn w-full"
              >
                ➕ Adicionar à Rodada de Captação
              </button>
            </form>

            <div className="space-y-2">
              {dadosEBT.investimentos.map((item) => (
                <div
                  key={item.id}
                  className="bg-blue-50 border border-blue-200 text-blue-950 rounded-lg p-3 flex items-center justify-between text-sm"
                >
                  <span>
                    <strong>{item.categoria}</strong> — {item.descricao} |
                    Orçamento Alocado: <strong>{fmtBRL(item.valor)}</strong>
                  </span>
                  <button
                    type="button"
                    disabled={!podeEditarDiagnostico}
                    onClick={async () => {
                      try {
                        await api.excluirCapex(ebtAtivaId, item.id);
                        await carregarEBTCompleta(ebtAtivaId);
                      } catch (err) {
                        notificarErro(err);
                      }
                    }}
                    className="px-2.5 py-1 bg-white border border-slate-300 rounded hover:bg-red-50"
                  >
                    🗑️
                  </button>
                </div>
              ))}
            </div>

            {dadosEBT.investimentos.length > 0 && (
              <div className="st-card">
                <div className="text-xs font-bold text-slate-500">
                  Total Requisitado para a Rodada de Financiamento (Seed /
                  Pre-Seed)
                </div>
                <div className="text-2xl font-black text-[#E30000] mt-1">
                  {fmtBRL(viab?.capex_total)}
                </div>
              </div>
            )}
          </section>
        )}

        {/* ===================================================================
            ABA 4: 🔄 OPEX
        =================================================================== */}
        {abaAtiva === "opex" && dadosEBT && (
          <section className="space-y-4">
            <img
              src="https://images.unsplash.com/photo-1497366216548-37526070297c?q=80&w=1000&auto=format&fit=crop"
              alt="Opex"
              className="w-full h-40 object-cover rounded-xl"
            />
            <h2 className="text-xl font-extrabold">
              🔄 Estrutura Mensal de Queima de Caixa (Opex)
            </h2>

            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (!ebtAtivaId || !novoOpex.descricao.trim()) return;
                try {
                  await api.adicionarOpex(ebtAtivaId, novoOpex);
                  setNovoOpex({ ...novoOpex, descricao: "", valor_mensal: 0 });
                  await carregarEBTCompleta(ebtAtivaId);
                  notificarSucesso("Item Opex acrescentado na DRE!");
                } catch (err) {
                  notificarErro(err);
                }
              }}
              className="st-card space-y-4"
            >
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Centro de Custos
                  </label>
                  <select
                    className="st-input"
                    disabled={!podeEditarDiagnostico}
                    value={novoOpex.categoria}
                    onChange={(e) =>
                      setNovoOpex({ ...novoOpex, categoria: e.target.value })
                    }
                  >
                    <option>
                      Custos com Pessoal Técnico (Headcount Tech)
                    </option>
                    <option>Licenciamento de APIs / SaaS de Terceiros</option>
                    <option>Retirada de Sócios (Pró-labore)</option>
                    <option>Orçamento de Tráfego Pago / Performance</option>
                    <option>Instalações e Facilities</option>
                    <option>Outros</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Rubrica Administrativa
                  </label>
                  <input
                    className="st-input"
                    disabled={!podeEditarDiagnostico}
                    value={novoOpex.descricao}
                    onChange={(e) =>
                      setNovoOpex({ ...novoOpex, descricao: e.target.value })
                    }
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Pagamento Mensal (R$/Mês)
                  </label>
                  <input
                    type="number"
                    min={0}
                    step="500"
                    className="st-input"
                    disabled={!podeEditarDiagnostico}
                    value={novoOpex.valor_mensal}
                    onChange={(e) =>
                      setNovoOpex({
                        ...novoOpex,
                        valor_mensal: Number(e.target.value),
                      })
                    }
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={!podeEditarDiagnostico}
                className="st-btn w-full"
              >
                ➕ Acrescentar Custo na DRE
              </button>
            </form>

            <div className="space-y-2">
              {dadosEBT.custos_fixos.map((item) => (
                <div
                  key={item.id}
                  className="bg-red-50 border border-red-200 text-red-950 rounded-lg p-3 flex items-center justify-between text-sm"
                >
                  <span>
                    <strong>{item.categoria}</strong> — {item.descricao} | Saída
                    Mensal Constante:{" "}
                    <strong>{fmtBRL(item.valor_mensal)}/mês</strong>
                  </span>
                  <button
                    type="button"
                    disabled={!podeEditarDiagnostico}
                    onClick={async () => {
                      try {
                        await api.excluirOpex(ebtAtivaId, item.id);
                        await carregarEBTCompleta(ebtAtivaId);
                      } catch (err) {
                        notificarErro(err);
                      }
                    }}
                    className="px-2.5 py-1 bg-white border border-slate-300 rounded hover:bg-red-100"
                  >
                    🗑️
                  </button>
                </div>
              ))}
            </div>

            {dadosEBT.custos_fixos.length > 0 && (
              <div className="st-card">
                <div className="text-xs font-bold text-slate-500">
                  Piso do Burn Rate de Manutenção
                </div>
                <div className="text-2xl font-black text-[#E30000] mt-1">
                  {fmtBRL(dre?.opex_fixo_mensal)} ao mês
                </div>
              </div>
            )}
          </section>
        )}

        {/* ===================================================================
            ABA 5: 💳 SAAS PRICING
        =================================================================== */}
        {abaAtiva === "pricing" && dadosEBT && (
          <section className="space-y-4">
            <img
              src="https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?q=80&w=1000&auto=format&fit=crop"
              alt="Pricing"
              className="w-full h-40 object-cover rounded-xl"
            />
            <h2 className="text-xl font-extrabold">
              💳 Engenharia de Preços e Tiers de Assinatura (Pagos & Free Tier)
            </h2>
            <div className="bg-blue-50 border border-blue-200 text-blue-900 rounded-lg p-3 text-sm">
              💡 <strong>Suporte Nativo a Free Tier (R$ 0,00)</strong>: Para
              simular um <strong>Plano Gratuito (Free Tier / PLG)</strong>,
              informe <code>Receita Fixa (R$/Mês) = 0,00</code> e defina o{" "}
              <code>Custo de Nuvem/AWS por User (R$)</code>. O motor
              contabilizará automaticamente o COGS de nuvem da base gratuita e
              sua conversão para os planos pagos,{" "}
              <strong>
                sem diluir o Ticket Médio (ARPU) dos assinantes pagantes
              </strong>
              .
            </div>

            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (!ebtAtivaId || !novoPlanoSaaS.nome_plano.trim()) return;
                try {
                  await api.adicionarPlanoSaaS(ebtAtivaId, novoPlanoSaaS);
                  setNovoPlanoSaaS({
                    nome_plano: "",
                    ticket_mensal: 0,
                    usuarios_ativos_base: 0,
                    taxas_pagamento_pct: 5.0,
                    impostos_pct: 6.0,
                    custo_servidor_por_usuario: 0.0,
                  });
                  await carregarEBTCompleta(ebtAtivaId);
                  notificarSucesso("Tier de Preço homologado com sucesso!");
                } catch (err) {
                  notificarErro(err);
                }
              }}
              className="st-card space-y-4"
            >
              <div>
                <label className="block text-xs font-bold mb-1">
                  Nomenclatura do Plano de Vendas (Ex: Free Tier, Plano Starter,
                  Enterprise B2B)
                </label>
                <input
                  className="st-input"
                  disabled={!podeEditarDiagnostico}
                  value={novoPlanoSaaS.nome_plano}
                  onChange={(e) =>
                    setNovoPlanoSaaS({
                      ...novoPlanoSaaS,
                      nome_plano: e.target.value,
                    })
                  }
                  required
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Receita Fixa (R$/Mês)
                  </label>
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    className="st-input"
                    disabled={!podeEditarDiagnostico}
                    value={novoPlanoSaaS.ticket_mensal}
                    onChange={(e) =>
                      setNovoPlanoSaaS({
                        ...novoPlanoSaaS,
                        ticket_mensal: Number(e.target.value),
                      })
                    }
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Número de Licenças Ativas
                  </label>
                  <input
                    type="number"
                    min={0}
                    className="st-input"
                    disabled={!podeEditarDiagnostico}
                    value={novoPlanoSaaS.usuarios_ativos_base}
                    onChange={(e) =>
                      setNovoPlanoSaaS({
                        ...novoPlanoSaaS,
                        usuarios_ativos_base: Number(e.target.value),
                      })
                    }
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Taxa de Cartão/Gateway (%)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    className="st-input"
                    disabled={!podeEditarDiagnostico}
                    value={novoPlanoSaaS.taxas_pagamento_pct}
                    onChange={(e) =>
                      setNovoPlanoSaaS({
                        ...novoPlanoSaaS,
                        taxas_pagamento_pct: Number(e.target.value),
                      })
                    }
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Retenção de Impostos (%)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    className="st-input"
                    disabled={!podeEditarDiagnostico}
                    value={novoPlanoSaaS.impostos_pct}
                    onChange={(e) =>
                      setNovoPlanoSaaS({
                        ...novoPlanoSaaS,
                        impostos_pct: Number(e.target.value),
                      })
                    }
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Custo de Nuvem/AWS por User (R$)
                  </label>
                  <input
                    type="number"
                    min={0}
                    step="0.1"
                    className="st-input"
                    disabled={!podeEditarDiagnostico}
                    value={novoPlanoSaaS.custo_servidor_por_usuario}
                    onChange={(e) =>
                      setNovoPlanoSaaS({
                        ...novoPlanoSaaS,
                        custo_servidor_por_usuario: Number(e.target.value),
                      })
                    }
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={!podeEditarDiagnostico}
                className="st-btn w-full"
              >
                ➕ Homologar Tier de Preço / Free Tier
              </button>
            </form>

            <div className="space-y-2">
              {dadosEBT.planos_saas.map((assinatura) => {
                const mrr =
                  assinatura.ticket_mensal * assinatura.usuarios_ativos_base;
                const desc =
                  (assinatura.taxas_pagamento_pct + assinatura.impostos_pct) /
                  100;
                const cogs =
                  assinatura.custo_servidor_por_usuario *
                  assinatura.usuarios_ativos_base;
                const margem = mrr * (1 - desc) - cogs;
                const ehFree = assinatura.ticket_mensal <= 0;
                return (
                  <div
                    key={assinatura.id}
                    className={`rounded-lg p-3 flex items-center justify-between text-sm border ${
                      ehFree
                        ? "bg-blue-50 border-blue-200 text-blue-950"
                        : "bg-emerald-50 border-emerald-200 text-emerald-950"
                    }`}
                  >
                    <span>
                      {ehFree ? (
                        <>
                          🆓 <strong>FREE TIER: {assinatura.nome_plano}</strong>{" "}
                          — Preço: R$ 0,00 (Gratuito) · Usuários Free:{" "}
                          {assinatura.usuarios_ativos_base} · COGS de Nuvem do
                          Free Tier: {fmtBRL(cogs)}/mês · Não dilui o ARPU Pago
                        </>
                      ) : (
                        <>
                          💳 <strong>{assinatura.nome_plano}</strong> — Preço
                          (ARPU): {fmtBRL(assinatura.ticket_mensal)} · Contas
                          Ativas: {assinatura.usuarios_ativos_base} · Receita
                          Produzida: {fmtBRL(mrr)} · Lucro Bruto do Tier:{" "}
                          {fmtBRL(margem)}
                        </>
                      )}
                    </span>
                    <button
                      type="button"
                      disabled={!podeEditarDiagnostico}
                      onClick={async () => {
                        try {
                          await api.excluirPlanoSaaS(ebtAtivaId, assinatura.id);
                          await carregarEBTCompleta(ebtAtivaId);
                        } catch (err) {
                          notificarErro(err);
                        }
                      }}
                      className="px-2.5 py-1 bg-white border border-slate-300 rounded hover:bg-red-50"
                    >
                      🗑️
                    </button>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* ===================================================================
            ABA 6: ⚖️ RISCOS LEGAIS
        =================================================================== */}
        {abaAtiva === "legal" && formJuridico && (
          <section className="space-y-4">
            <img
              src="https://images.unsplash.com/photo-1589829085413-56de8ae18c73?q=80&w=1000&auto=format&fit=crop"
              alt="Riscos Legais"
              className="w-full h-40 object-cover rounded-xl"
            />
            <h2 className="text-xl font-extrabold">
              ⚖️ Due Diligence: Propriedade Intelectual e Proteção de Dados
            </h2>
            <div className="bg-blue-50 border border-blue-200 text-blue-900 rounded-lg p-3 text-sm">
              Na avaliação final de um VC, falhas na custódia do código (INPI) e
              na definição do <em>Cap Table</em> (Vesting) são considerados Deal
              Breakers fatais.
            </div>

            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (!ebtAtivaId || !formJuridico) return;
                try {
                  await api.atualizarJuridico(ebtAtivaId, formJuridico);
                  await carregarEBTCompleta(ebtAtivaId);
                  notificarSucesso(
                    "As fragilidades de governança foram avaliadas, registadas e auditadas."
                  );
                } catch (err) {
                  notificarErro(err);
                }
              }}
              className="st-card space-y-4"
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Proteção Jurídica do Código e Algoritmos (INPI)
                  </label>
                  <select
                    className="st-input"
                    disabled={!podeEditarDiagnostico}
                    value={formJuridico.registro_inpi}
                    onChange={(e) =>
                      setFormJuridico({
                        ...formJuridico,
                        registro_inpi: e.target.value,
                      })
                    }
                  >
                    <option value="Não Iniciado">
                      Não Iniciado (Risco Iminente)
                    </option>
                    <option value="Código Depositado">
                      Processo de Código Fonte Depositado
                    </option>
                    <option value="Certificado Emitido">
                      Certificado Oficial de Software Emitido
                    </option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold mb-1">
                    Registo e Blindagem da Marca do Produto
                  </label>
                  <select
                    className="st-input"
                    disabled={!podeEditarDiagnostico}
                    value={formJuridico.marca_status}
                    onChange={(e) =>
                      setFormJuridico({
                        ...formJuridico,
                        marca_status: e.target.value,
                      })
                    }
                  >
                    <option value="Não Iniciado">
                      Não Iniciado (Vulnerabilidade de Uso)
                    </option>
                    <option value="Busca Realizada">
                      Busca de Anterioridade Efectuada
                    </option>
                    <option value="Processo em Andamento">
                      Processo protocolado no INPI
                    </option>
                    <option value="Marca Concedida">
                      Direito de Marca Concedido
                    </option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-semibold">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    disabled={!podeEditarDiagnostico}
                    checked={formJuridico.adequacao_lgpd}
                    onChange={(e) =>
                      setFormJuridico({
                        ...formJuridico,
                        adequacao_lgpd: e.target.checked,
                      })
                    }
                  />
                  ✅ O Sistema respeita as diretrizes de Privacidade por Design
                  e a LGPD (Termos de Uso claros e ativos)
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    disabled={!podeEditarDiagnostico}
                    checked={formJuridico.contrato_vesting}
                    onChange={(e) =>
                      setFormJuridico({
                        ...formJuridico,
                        contrato_vesting: e.target.checked,
                      })
                    }
                  />
                  ✅ A Governança da Equipa Fundadora está segura mediante um
                  Contrato de Vesting formal (Cliff estabelecido)
                </label>
              </div>

              <div>
                <label className="block text-xs font-bold mb-1">
                  Honorários de Retenção e Assessoria DPO (Custo Mensal Corrente
                  em R$)
                </label>
                <input
                  type="number"
                  step="100"
                  disabled={!podeEditarDiagnostico}
                  className="st-input max-w-md"
                  value={formJuridico.custo_estimado_legal}
                  onChange={(e) =>
                    setFormJuridico({
                      ...formJuridico,
                      custo_estimado_legal: Number(e.target.value),
                    })
                  }
                />
              </div>

              <button
                type="submit"
                disabled={!podeEditarDiagnostico}
                className="st-btn w-full"
              >
                💾 Selar Auditoria no Data Room
              </button>
            </form>

            <div className="st-card space-y-2">
              <h3 className="text-sm font-bold">
                Indicador Sintético de Imunidade e Compliance
              </h3>
              {testesImunidade.map((t, idx) => (
                <div key={idx} className="text-xs font-semibold">
                  {t.ok ? "✅" : "❌"} {t.label}
                </div>
              ))}
              <div className="w-full bg-slate-200 h-3 rounded-full overflow-hidden mt-2">
                <div
                  className="bg-[#E30000] h-full transition-all"
                  style={{ width: `${(pontuacaoSeguranca / 4) * 100}%` }}
                />
              </div>
              <div className="text-xs text-slate-600">
                Maturidade Jurídica para o Fundo VC: {pontuacaoSeguranca} de 4
                requisitos superados com distinção
              </div>
            </div>
          </section>
        )}

        {/* ===================================================================
            ABA 7: 📄 RESUMO ONE-PAGER
        =================================================================== */}
        {abaAtiva === "onepager" && dadosEBT && (
          <section className="space-y-4">
            <img
              src="https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?q=80&w=1000&auto=format&fit=crop"
              alt="One Pager"
              className="w-full h-40 object-cover rounded-xl"
            />
            <h2 className="text-xl font-extrabold">
              📄 Sumário Executivo — O <em>One-Pager</em> do Investidor
            </h2>

            <details open className="st-card space-y-2">
              <summary className="font-bold cursor-pointer text-sm">
                🧩 A Tese Central: Dor, Produto e Diferencial (Moat)
              </summary>
              <div className="text-xs space-y-2 pt-2">
                <p>
                  <strong>O Core da Solução (Proposta Única de Valor):</strong>{" "}
                  {safeStr(dadosEBT.lean_canvas.proposta_valor)}
                </p>
                <p>
                  <strong>
                    A Barreira Contra a Concorrência (Vantagem Injusta):
                  </strong>{" "}
                  {safeStr(dadosEBT.lean_canvas.vantagem_injusta)}
                </p>
                <p>
                  <strong>Repercussão Social Global (Normativas ODS):</strong>{" "}
                  {safeStr(dadosEBT.lean_canvas.ods_onu)}
                </p>
              </div>
            </details>

            <details open className="st-card space-y-2">
              <summary className="font-bold cursor-pointer text-sm">
                🔬 Operações de Validação: O MVP
              </summary>
              <div className="text-xs space-y-2 pt-2">
                <p>
                  <strong>Características Formais da Arquitetura:</strong>{" "}
                  {safeStr(dadosEBT.lean_canvas.solucao_mvp)}
                </p>
                <p>
                  <strong>
                    Os Resultados Produzidos pela Prova de Conceito:
                  </strong>{" "}
                  {safeStr(dadosEBT.lean_canvas.mvp_descricao)}
                </p>
              </div>
            </details>

            <details open className="st-card">
              <summary className="font-bold cursor-pointer text-sm">
                💸 Síntese da Economia de Escala (SaaS)
              </summary>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-3">
                <div>
                  <div className="text-xs text-slate-500 font-semibold">
                    Capacidade Recorrente (MRR)
                  </div>
                  <div className="text-lg font-black text-[#E30000]">
                    {fmtBRL(dre?.mrr_bruto_total)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-slate-500 font-semibold">
                    Annual Recurring Revenue (ARR)
                  </div>
                  <div className="text-lg font-black text-[#E30000]">
                    {fmtBRL(dre?.arr_anualizado)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-slate-500 font-semibold">
                    Velocidade do Burn Rate
                  </div>
                  <div className="text-lg font-black text-[#E30000]">
                    {fmtBRL(dre?.burn_rate_total_mensal)}/mês
                  </div>
                </div>
                <div>
                  <div className="text-xs text-slate-500 font-semibold">
                    Índice Multiplicador LTV/CAC
                  </div>
                  <div className="text-lg font-black text-[#E30000]">
                    {(ue?.indice_ltv_cac || 0).toFixed(2)}x
                  </div>
                </div>
              </div>
            </details>

            <details open className="st-card space-y-1 text-xs">
              <summary className="font-bold cursor-pointer text-sm">
                ⚖️ O Mapa de Riscos Passivos
              </summary>
              <div className="pt-2 space-y-1">
                <div>
                  •{" "}
                  <strong>Conformidade do Código e Patentes (INPI):</strong>{" "}
                  {dadosEBT.juridico.registro_inpi}
                </div>
                <div>
                  • <strong>Consistência do Branding e Marca:</strong>{" "}
                  {dadosEBT.juridico.marca_status}
                </div>
                <div>
                  • <strong>Vulnerabilidade em Cibersegurança e Dados:</strong>{" "}
                  {dadosEBT.juridico.adequacao_lgpd
                    ? "✅ Protocolo Validado"
                    : "❌ Severamente Exposto"}
                </div>
                <div>
                  •{" "}
                  <strong>
                    Segurança Estrutural do Acordo Acionista (Vesting):
                  </strong>{" "}
                  {dadosEBT.juridico.contrato_vesting
                    ? "✅ Documento em Vigor"
                    : "❌ A Sociedade Encontra-se Vulnerável"}
                </div>
              </div>
            </details>
          </section>
        )}

        {/* ===================================================================
            ABA 8: 📊 VIABILIDADE
        =================================================================== */}
        {abaAtiva === "viabilidade" && dadosEBT && sim && viab && series && (
          <section className="space-y-4">
            <img
              src="https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=1000&auto=format&fit=crop"
              alt="Viabilidade"
              className="w-full h-40 object-cover rounded-xl"
            />
            <h2 className="text-xl font-extrabold">
              📊 Inteligência Financeira: Valuation Baseado no{" "}
              <em>Cashflow</em>
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="st-card">
                <div className="text-xs font-bold text-slate-500">
                  Esforço Total em Capex (O Tamanho da Rodada)
                </div>
                <div className="text-xl font-black text-[#E30000] mt-1">
                  {fmtBRL(viab.capex_total)}
                </div>
              </div>
              <div className="st-card">
                <div className="text-xs font-bold text-slate-500">
                  Geração Global de Riqueza Acumulada (VPL)
                </div>
                <div className="text-xl font-black text-[#E30000] mt-1">
                  {fmtBRL(viab.valor_presente_liquido_vpl)}
                </div>
                <div
                  className={`text-[11px] font-bold mt-1 ${
                    viab.valor_presente_liquido_vpl > 0
                      ? "text-emerald-700"
                      : "text-red-700"
                  }`}
                >
                  {viab.valor_presente_liquido_vpl > 0
                    ? "▲ Startup Validada com Geração de Valor"
                    : "▼ Operação Inviável que Destrói o Capital Alocado"}
                </div>
              </div>
              <div className="st-card">
                <div className="text-xs font-bold text-slate-500">
                  Retorno Base Projetado (TIR)
                </div>
                <div className="text-xl font-black text-[#E30000] mt-1">
                  {viab.validade_da_tir &&
                  viab.taxa_interna_retorno_anual_pct !== null &&
                  viab.taxa_interna_retorno_anual_pct !== undefined
                    ? `${viab.taxa_interna_retorno_anual_pct.toFixed(2)}%`
                    : "Indefinida (Verifique Caixa)"}
                </div>
                <div className="text-[11px] text-slate-500 mt-1">
                  Custo Oportunidade (TMA):{" "}
                  {dadosEBT.premissas.tma_anual_pct.toFixed(1)}%
                </div>
              </div>
              <div className="st-card">
                <div className="text-xs font-bold text-slate-500">
                  Ponto de Retorno Efetivo do Fundo (Payback)
                </div>
                <div className="text-lg font-black text-[#E30000] mt-1">
                  {viab.mes_de_breakeven_payback_texto}
                </div>
              </div>
            </div>

            <GraficoCashflowValeDaMorte
              rotulos={series.rotulos_meses}
              fluxoMensal={series.fluxo_de_caixa_mensal}
              caixaAcumulado={series.caixa_acumulado}
            />

            {/* Alertas de Sanidade */}
            <div className="st-card space-y-2">
              <h3 className="text-sm font-bold">
                🛡️ Auditoria de Sanidade do Motor Financeiro (v
                {sim.versao_motor || "1.0"})
              </h3>
              <p className="text-xs text-slate-500">
                Hash Determinístico da Simulação (SHA-256):{" "}
                <code>{(sim.hash_entrada || "").slice(0, 16)}...</code>
              </p>
              {sim.alertas.length === 0 ? (
                <div className="bg-emerald-50 border border-emerald-200 text-emerald-900 p-2.5 rounded text-xs">
                  ✅ Todas as validações matemáticas e setoriais passaram sem
                  alertas.
                </div>
              ) : (
                sim.alertas.map((a, idx) => (
                  <div
                    key={idx}
                    className={`p-3 rounded-lg text-xs border ${
                      a.severidade === "critico"
                        ? "bg-red-50 border-red-200 text-red-900"
                        : "bg-amber-50 border-amber-200 text-amber-900"
                    }`}
                  >
                    <div>
                      <strong>
                        [{a.codigo}] {a.titulo}
                      </strong>{" "}
                      — {a.mensagem}
                    </div>
                    <div className="mt-1 italic">
                      💡 Recomendação: {a.recomendacao}
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Matriz Comparativa de Cenários */}
            <details open className="st-card">
              <summary className="font-bold cursor-pointer text-sm">
                🎯 Matriz Comparativa de Cenários (Base vs. Otimista vs.
                Pessimista)
              </summary>
              <div className="overflow-x-auto mt-3">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-100 text-slate-700">
                      <th className="p-2">Cenário</th>
                      <th className="p-2">VPL Projetado</th>
                      <th className="p-2">TIR Anualizada</th>
                      <th className="p-2">Payback</th>
                      <th className="p-2">LTV / CAC</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(
                      [
                        ["Pessimista (Stress Test)", "pessimista"],
                        ["Base (Plano Atual)", "base"],
                        ["Otimista (Bull Case)", "otimista"],
                      ] as const
                    ).map(([rotulo, chave]) => {
                      const c = dadosEBT.comparativo_cenarios.cenarios[chave];
                      return (
                        <tr key={chave} className="border-b border-slate-200">
                          <td className="p-2 font-bold">{rotulo}</td>
                          <td className="p-2">
                            {fmtBRL(c.viabilidade.valor_presente_liquido_vpl)}
                          </td>
                          <td className="p-2">
                            {c.viabilidade.validade_da_tir &&
                            c.viabilidade.taxa_interna_retorno_anual_pct !==
                              null &&
                            c.viabilidade.taxa_interna_retorno_anual_pct !==
                              undefined
                              ? `${c.viabilidade.taxa_interna_retorno_anual_pct.toFixed(2)}%`
                              : "Indefinida"}
                          </td>
                          <td className="p-2">
                            {c.viabilidade.mes_de_breakeven_payback_texto}
                          </td>
                          <td className="p-2">
                            {c.unit_economics.indice_ltv_cac.toFixed(2)}x
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </details>

            {/* Versionamento Imutável & Monte Carlo */}
            <details open className="st-card space-y-3">
              <summary className="font-bold cursor-pointer text-sm">
                📸 Versionamento Imutável de Simulações & Stress Test de Monte
                Carlo
              </summary>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      const snap =
                        await api.executarSimulacaoVersionada(ebtAtivaId);
                      await carregarEBTCompleta(ebtAtivaId);
                      notificarSucesso(
                        `Versão imutável v${snap.versao_numero} congelada com hash ${snap.hash_entrada.slice(0, 16)}...!`
                      );
                    } catch (err) {
                      notificarErro(err);
                    }
                  }}
                  className="st-btn text-xs"
                >
                  📌 Congelar e Versionar Simulação Atual (Snapshot Imutável)
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      const mc = await api.executarMonteCarlo(ebtAtivaId);
                      setResultadoMC(mc);
                    } catch (err) {
                      notificarErro(err);
                    }
                  }}
                  className="st-btn text-xs"
                >
                  🎲 Executar Simulação Estocástica de Monte Carlo (300
                  Iterações)
                </button>
              </div>

              {resultadoMC && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3 bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <div>
                    <div className="text-xs text-slate-500">
                      Probabilidade de VPL &gt; 0
                    </div>
                    <div className="text-lg font-black text-[#E30000]">
                      {resultadoMC.probabilidade_vpl_positivo_pct.toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">
                      VPL Pessimista (P10)
                    </div>
                    <div className="text-lg font-black text-[#E30000]">
                      {fmtBRL(resultadoMC.vpl_p10_pessimista)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">
                      VPL Mediano (P50)
                    </div>
                    <div className="text-lg font-black text-[#E30000]">
                      {fmtBRL(resultadoMC.vpl_mediana_p50)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">
                      VPL Otimista (P90)
                    </div>
                    <div className="text-lg font-black text-[#E30000]">
                      {fmtBRL(resultadoMC.vpl_p90_otimista)}
                    </div>
                  </div>
                </div>
              )}

              {dadosEBT.versoes_simulacao &&
                dadosEBT.versoes_simulacao.length > 0 && (
                  <div className="overflow-x-auto">
                    <div className="text-xs font-bold mb-1">
                      Histórico de Versões Imutáveis Auditadas para esta EBT:
                    </div>
                    <table className="w-full text-xs text-left border-collapse">
                      <thead>
                        <tr className="bg-slate-100">
                          <th className="p-2">Versão</th>
                          <th className="p-2">Hash SHA-256</th>
                          <th className="p-2">MRR Base</th>
                          <th className="p-2">VPL</th>
                          <th className="p-2">LTV/CAC</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dadosEBT.versoes_simulacao.map((v) => (
                          <tr key={v.id} className="border-b border-slate-200">
                            <td className="p-2 font-bold">
                              v{v.numero_versao}
                            </td>
                            <td className="p-2 font-mono">
                              {v.hash_entrada_sha256.slice(0, 16)}...
                            </td>
                            <td className="p-2">{fmtBRL(v.mrr_bruto_base)}</td>
                            <td className="p-2">{fmtBRL(v.vpl)}</td>
                            <td className="p-2">{v.ltv_cac.toFixed(2)}x</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
            </details>

            {/* Demonstrativo Linear de Caixa */}
            <div className="st-card">
              <h3 className="text-sm font-bold mb-2">
                Auditabilidade Contabilística — Demonstrativo Linear de Caixa
              </h3>
              <div className="max-h-64 overflow-y-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead className="sticky top-0 bg-slate-100">
                    <tr>
                      <th className="p-2">Linha de Tempo Operacional</th>
                      <th className="p-2">Curva de Faturação Recebida (MRR)</th>
                      <th className="p-2">
                        Consolidação de Clientes Efetivos
                      </th>
                      <th className="p-2">
                        Reserva Contabilística (Caixa Líquido Residual)
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {series.rotulos_meses.map((rot, i) => (
                      <tr key={i} className="border-b border-slate-100">
                        <td className="p-2 font-semibold">{rot}</td>
                        <td className="p-2">{fmtBRL(series.mrr_mensal[i])}</td>
                        <td className="p-2">
                          {Math.round(series.usuarios_pagantes[i])}
                        </td>
                        <td
                          className={`p-2 font-bold ${
                            series.caixa_acumulado[i] < 0
                              ? "text-red-600"
                              : "text-emerald-700"
                          }`}
                        >
                          {fmtBRL(series.caixa_acumulado[i])}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}

        {/* ===================================================================
            ABA 9: 📉 DASHBOARDS (UNIT ECONOMICS & DRE SOFTWARE)
        =================================================================== */}
        {abaAtiva === "dashboards" && dadosEBT && dre && ue && viab && series && (
          <section className="space-y-4">
            <img
              src="https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=1000&auto=format&fit=crop"
              alt="Dashboards"
              className="w-full h-40 object-cover rounded-xl"
            />
            <h2 className="text-xl font-extrabold">
              📉 Monitorização Cirúrgica de Unit Economics (SaaS)
            </h2>

            {dadosEBT.planos_saas.length === 0 ? (
              <div className="bg-amber-50 border border-amber-300 text-amber-900 p-4 rounded-xl text-sm">
                ⚠️ Atenção à Análise: O ecossistema de métricas encontra-se
                inativo pois a estratégia e as camadas de <em>Pricing</em> ainda
                não foram homologadas na respetiva área (SaaS Pricing).
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="st-card">
                    <div className="text-xs font-bold text-slate-500">
                      Massa Faturada Vigente (MRR)
                    </div>
                    <div className="text-xl font-black text-[#E30000] mt-1">
                      {fmtBRL(dre.mrr_bruto_total)}
                    </div>
                    <div className="text-[11px] text-emerald-700 font-semibold mt-1">
                      {Math.round(ue.usuarios_pagantes_totais_base)} Entidades
                      Clientes
                    </div>
                  </div>
                  <div className="st-card">
                    <div className="text-xs font-bold text-slate-500">
                      Estimativa de ARR Linear
                    </div>
                    <div className="text-xl font-black text-[#E30000] mt-1">
                      {fmtBRL(dre.arr_anualizado)}
                    </div>
                  </div>
                  <div className="st-card">
                    <div className="text-xs font-bold text-slate-500">
                      Sobrevivência da Margem Bruta
                    </div>
                    <div className="text-xl font-black text-[#E30000] mt-1">
                      {dre.margem_bruta_pct.toFixed(1)}%
                    </div>
                  </div>
                  <div className="st-card">
                    <div className="text-xs font-bold text-slate-500">
                      ARPU Efetivo (Ponderado Pagantes)
                    </div>
                    <div className="text-xl font-black text-[#E30000] mt-1">
                      {fmtBRL(ue.ticket_medio_arpu)}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="st-card">
                    <div className="text-xs font-bold text-slate-500">
                      Geração Fria Operacional (EBITDA)
                    </div>
                    <div className="text-xl font-black text-[#E30000] mt-1">
                      {fmtBRL(dre.ebitda_mensal)}
                    </div>
                    <div
                      className={`text-[11px] font-bold mt-1 ${
                        dre.ebitda_mensal >= 0
                          ? "text-emerald-700"
                          : "text-red-600"
                      }`}
                    >
                      {dre.ebitda_mensal >= 0
                        ? "Matriz Económica Superavitária ✓"
                        : "Fluxos Críticos / Risco de Sangria 🔥"}
                    </div>
                  </div>
                  <div className="st-card">
                    <div className="text-xs font-bold text-slate-500">
                      O Efeito Global do Burn Rate Efetivo
                    </div>
                    <div className="text-xl font-black text-[#E30000] mt-1">
                      {fmtBRL(dre.burn_rate_total_mensal)}/mês
                    </div>
                  </div>
                  <div className="st-card">
                    <div className="text-xs font-bold text-slate-500">
                      Capacidade Funcional de Sobrevida (Runway)
                    </div>
                    <div className="text-lg font-black text-[#E30000] mt-1">
                      {viab.meses_runway_sobrevivencia
                        ? `${viab.meses_runway_sobrevivencia.toFixed(1)} meses restantes`
                        : "Infinitude e Escala de Segurança Total"}
                    </div>
                  </div>
                  <div className="st-card">
                    <div className="text-xs font-bold text-slate-500">
                      Potência de Retenção e Escala (LTV / CAC)
                    </div>
                    <div className="text-xl font-black text-[#E30000] mt-1">
                      {ue.indice_ltv_cac.toFixed(2)}x
                    </div>
                    <div className="text-[11px] font-semibold mt-1">
                      {ue.indice_ltv_cac >= 3
                        ? "🟢 Tracionamento Brilhante"
                        : ue.indice_ltv_cac >= 1
                          ? "🟡 Marginalmente Eficiente"
                          : "🔴 Ineficiência Financeira"}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="st-card">
                    <div className="text-xs font-bold text-slate-500">
                      Valor Gasto na Captação (CAC)
                    </div>
                    <div className="text-xl font-black text-[#E30000] mt-1">
                      {fmtBRL(ue.cac_estimado)}
                    </div>
                  </div>
                  <div className="st-card">
                    <div className="text-xs font-bold text-slate-500">
                      Rentabilidade Extraída Vitaliciamente (LTV)
                    </div>
                    <div className="text-xl font-black text-[#E30000] mt-1">
                      {fmtBRL(ue.ltv_vitalicio_cliente)}
                    </div>
                  </div>
                  <div className="st-card">
                    <div className="text-xs font-bold text-slate-500">
                      Fugas e Abandono Estimado (Churn)
                    </div>
                    <div className="text-xl font-black text-[#E30000] mt-1">
                      {dadosEBT.premissas.churn_mensal_pct.toFixed(1)}% ao Mês
                    </div>
                  </div>
                  <div className="st-card">
                    <div className="text-xs font-bold text-slate-500">
                      Payback de CAC
                    </div>
                    <div className="text-lg font-black text-[#E30000] mt-1">
                      {ue.meses_payback_cac
                        ? `${ue.meses_payback_cac.toFixed(1)} Períodos Faturados`
                        : "Incalculável"}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <h4 className="text-xs font-bold mb-2">
                      Segmentação Matemática das Hemorragias Contínuas (Rate de
                      Queima)
                    </h4>
                    <GraficoRoscaBurnRate
                      cogsNuvem={dre.despesas_nuvem_cogs}
                      opexFixo={dre.opex_fixo_mensal}
                      impostosGateways={dre.despesas_deducoes_fiscais_gateway}
                    />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold mb-2">
                      Crescimento do Momentum (Curvas de Ascensão de Base versus
                      Receita)
                    </h4>
                    <GraficoMRRTracao
                      rotulos={series.rotulos_meses}
                      mrrMensal={series.mrr_mensal}
                      usuariosPagantes={series.usuarios_pagantes}
                    />
                  </div>
                </div>

                {/* Demonstrativo Direto de Resultados (DRE de Sobrevida Software) */}
                <div className="st-card space-y-2">
                  <h3 className="text-sm font-bold mb-2">
                    📃 Demonstrativo Direto de Resultados (DRE de Sobrevida
                    Software)
                  </h3>
                  {[
                    {
                      label: "(+) Aceleração Integral Faturada (MRR Global)",
                      val: dre.mrr_bruto_total,
                      neg: false,
                      tot: false,
                    },
                    {
                      label:
                        "(-) Custo Imediato na Transação e Peso Fiscal",
                      val: -dre.despesas_deducoes_fiscais_gateway,
                      neg: true,
                      tot: false,
                    },
                    {
                      label:
                        "(=) Sobra Transitória (Líquido Transacionado)",
                      val: dre.mrr_liquido,
                      neg: false,
                      tot: true,
                    },
                    {
                      label:
                        "(-) Faturas Recorrentes Pela Computação em Nuvem (COGS)",
                      val: -dre.despesas_nuvem_cogs,
                      neg: true,
                      tot: false,
                    },
                    {
                      label:
                        "(=) Margem Pura Associada ao Sistema de Software",
                      val: dre.mrr_liquido - dre.despesas_nuvem_cogs,
                      neg: false,
                      tot: true,
                    },
                    {
                      label:
                        "(-) Encargos Relativos a Funcionários, Legalidades e Posição (Opex)",
                      val: -dre.opex_fixo_mensal,
                      neg: true,
                      tot: false,
                    },
                    {
                      label:
                        "(=) Fundo Final Operacional Resultante (Bottom Line Total)",
                      val: dre.ebitda_mensal,
                      neg: dre.ebitda_mensal < 0,
                      tot: true,
                    },
                  ].map((linha, idx) => (
                    <div
                      key={idx}
                      className={`flex justify-between items-center px-3.5 py-2.5 rounded-lg border border-slate-200 text-xs ${
                        linha.tot ? "bg-[#F1F5F9] font-bold" : "bg-white"
                      }`}
                    >
                      <span>{linha.label}</span>
                      <span
                        className={
                          linha.neg
                            ? "text-[#DC2626] font-bold"
                            : linha.tot && linha.val >= 0
                              ? "text-[#16A34A] font-bold"
                              : "text-[#0F172A]"
                        }
                      >
                        {fmtBRL(linha.val)}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </section>
        )}

        {/* ===================================================================
            ABA 10: 🤖 COMITÊ VC (IA GOVERNADA)
        =================================================================== */}
        {abaAtiva === "comite_ia" && dadosEBT && (
          <section className="space-y-4">
            <img
              src="https://images.unsplash.com/photo-1677442136019-21780ecad995?q=80&w=1000&auto=format&fit=crop"
              alt="Comitê VC IA"
              className="w-full h-40 object-cover rounded-xl"
            />
            <h2 className="text-xl font-extrabold">
              🤖 Comitê de Avaliação VC Assistido e Governado (Fase 3)
            </h2>
            <div className="bg-blue-50 border border-blue-200 text-blue-900 rounded-lg p-3 text-sm">
              Governança de IA em Produção: Todos os textos abertos passam por{" "}
              <strong>sanitização automática de PII (LGPD)</strong> antes do
              envio ao provedor. O parecer é indexado por{" "}
              <strong>hash SHA-256 do contexto</strong>, economizando quotas via
              cache inteligente, e requer{" "}
              <strong>homologação do Consultor / Admin</strong>.
            </div>

            <details className="st-card text-xs">
              <summary className="font-bold cursor-pointer">
                🔍 Inspecionar Prompt Anonimizado (Sem PII) e Hash SHA-256 do
                Contexto
              </summary>
              <div className="mt-2 space-y-2">
                <div className="text-slate-500">
                  Hash SHA-256 do Contexto:{" "}
                  <code>{dadosEBT.ia_governanca.hash_contexto_atual}</code>
                </div>
                <pre className="bg-slate-900 text-slate-100 p-3 rounded-lg overflow-x-auto text-[11px] whitespace-pre-wrap">
                  {dadosEBT.ia_governanca.prompt_anonimizado_preview}
                </pre>
              </div>
            </details>

            <div className="st-card space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                <div className="md:col-span-2 space-y-2">
                  <div className="font-bold">
                    Provedor de Inteligência do Comitê VC:
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      checked={modoProvedorIA === "interno"}
                      onChange={() => setModoProvedorIA("interno")}
                    />
                    🏛️ Copiloto VC Determinístico Interno (Sem Chave Externa /
                    Custo US$ 0)
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      checked={modoProvedorIA === "gemini"}
                      onChange={() => setModoProvedorIA("gemini")}
                    />
                    ✨ Google Gemini API (Nuvem Externa com Sanitização LGPD)
                  </label>
                </div>
                <div className="flex items-center">
                  <label className="flex items-center gap-2 text-xs font-semibold cursor-pointer">
                    <input
                      type="checkbox"
                      checked={forcarRegeneracaoIA}
                      onChange={(e) => setForcarRegeneracaoIA(e.target.checked)}
                    />
                    Ignorar cache e forçar nova geração
                  </label>
                </div>
              </div>

              {modoProvedorIA === "gemini" && (
                <div className="space-y-3 bg-zinc-900/50 p-3 rounded-xl border border-zinc-700/60">
                  <div>
                    <label className="block text-xs font-bold text-white mb-1">
                      Versão Inicial na Cascata Gemini (Waterfall 17 Modelos):
                    </label>
                    <select
                      className="st-input font-bold"
                      value={modeloGemini}
                      onChange={(e) => setModeloGemini(e.target.value)}
                    >
                      <optgroup label="Geração Gemini 4 & 3 (Frontier & Agentes Autônomos)">
                        <option value="gemini-4-argon">
                          🚀 gemini-4-argon (Frontier / Máxima Capacidade Analítica)
                        </option>
                        <option value="gemini-3.1-pro-preview">
                          🧠 gemini-3.1-pro-preview (Raciocínio Profundo & Estruturado)
                        </option>
                        <option value="gemini-3.8-flash">
                          ⚡ gemini-3.8-flash (Engenharia & Agentes de Alto Desempenho)
                        </option>
                        <option value="gemini-3.6-flash">
                          ⚡ gemini-3.6-flash (Multimodal Balanceado)
                        </option>
                        <option value="gemini-3-flash-preview">
                          ⚡ gemini-3-flash-preview (Alta Velocidade Frontier)
                        </option>
                        <option value="gemini-3.5-flash-lite">
                          ⚡ gemini-3.5-flash-lite (Otimizado para Alto Débito)
                        </option>
                        <option value="gemini-3.1-flash-lite">
                          ⚡ gemini-3.1-flash-lite (Flash-Lite de Entrada)
                        </option>
                      </optgroup>

                      <optgroup label="Geração Gemini 2.5">
                        <option value="gemini-2.5-pro">
                          🧠 gemini-2.5-pro (Raciocínio Avançado 2.5)
                        </option>
                        <option value="gemini-2.5-flash">
                          ⚡ gemini-2.5-flash (Flash 2.5 de Baixa Latência)
                        </option>
                        <option value="gemini-2.5-flash-lite">
                          ⚡ gemini-2.5-flash-lite (Flash Leve e Eficiente)
                        </option>
                      </optgroup>

                      <optgroup label="Geração Gemini 2.0">
                        <option value="gemini-2.0-pro">
                          🧠 gemini-2.0-pro (Raciocínio Profundo 2.0)
                        </option>
                        <option value="gemini-2.0-flash">
                          ⚡ gemini-2.0-flash (Flash Multimodal 2.0)
                        </option>
                        <option value="gemini-2.0-flash-lite">
                          ⚡ gemini-2.0-flash-lite (Flash-Lite 2.0)
                        </option>
                      </optgroup>

                      <optgroup label="Geração Gemini 1.5">
                        <option value="gemini-1.5-pro">
                          🧠 gemini-1.5-pro (Context Window 2M Tokens)
                        </option>
                        <option value="gemini-1.5-flash">
                          ⚡ gemini-1.5-flash (Flash 1.5 Rápido)
                        </option>
                        <option value="gemini-1.5-flash-8b">
                          ⚡ gemini-1.5-flash-8b (Ultra-Leve 8B)
                        </option>
                      </optgroup>

                      <optgroup label="Geração Gemini 1.0 (Legado)">
                        <option value="gemini-1.0-pro">
                          🏛️ gemini-1.0-pro (Legado Frontier 1.0)
                        </option>
                      </optgroup>
                    </select>
                    <p className="text-[11px] text-slate-400 mt-1">
                      Cascata inteligente: esgota rigorosamente 3 tentativas com backoff exponencial por modelo antes de recuar para o tier seguinte (4 → 3 → 2.5 → 2.0 → 1.5 → 1.0).
                    </p>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-white mb-1">
                      Credenciais Seguras: Chave da API Google Gemini:
                    </label>
                    <input
                      type="password"
                      placeholder="AIzaSy... (opcional se já configurada no backend via GEMINI_API_KEY)"
                      className="st-input"
                      value={chaveGemini}
                      onChange={(e) => setChaveGemini(e.target.value)}
                    />
                  </div>
                </div>
              )}

              <div className="flex items-center pt-1">
                <label className="flex items-center gap-2 text-xs font-semibold cursor-pointer text-slate-300 hover:text-white">
                  <input
                    type="checkbox"
                    checked={permitirFallbackAutomatico}
                    onChange={(e) =>
                      setPermitirFallbackAutomatico(e.target.checked)
                    }
                  />
                  🛡️ Resiliência Ativa: Fallback automático para Copiloto VC
                  Interno se o Gemini estiver indisponível
                </label>
              </div>

              <button
                type="button"
                disabled={processandoAcao}
                onClick={() => handleSolicitarParecerIA(ebtAtivaId, false)}
                className="st-btn w-full flex items-center justify-center gap-2"
              >
                <span>{processandoAcao ? "⏳" : "🚀"}</span>
                <span>
                  {processandoAcao
                    ? "Consultando Comitê de IA..."
                    : "Solicitar Parecer Governado ao Comitê VC"}
                </span>
              </button>
            </div>

            {/* Alerta Estruturado de Falha de IA com Código Padronizado e Ações de Fallback */}
            {alertaFalhaIA && (
              <div
                role="alert"
                aria-live="polite"
                className="bg-[#18181B] border-2 border-[#E30000] rounded-2xl p-4 sm:p-5 text-white space-y-3.5 shadow-xl animate-in fade-in"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-xl bg-red-950/80 border border-[#E30000] flex items-center justify-center text-xl flex-shrink-0">
                      ⚠️
                    </div>
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <h4 className="text-sm font-extrabold text-white">
                          Comunicação com o Provedor de IA Interrompida
                        </h4>
                        <span className="px-2 py-0.5 rounded bg-[#E30000] text-white font-black text-[11px] tracking-wider uppercase">
                          Código: {alertaFalhaIA.codigo_erro}
                        </span>
                        <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 font-mono text-[11px] font-bold">
                          Estado: PENDING_SYNC
                        </span>
                      </div>
                      <p className="text-xs text-slate-200 mt-1 leading-relaxed">
                        {alertaFalhaIA.mensagem_amigavel}
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setAlertaFalhaIA(null)}
                    className="text-slate-400 hover:text-white font-bold text-xs p-1 rounded-lg"
                    aria-label="Dispensar aviso de erro de IA"
                  >
                    ✕
                  </button>
                </div>

                <div className="bg-[#121212] border border-[#27272A] rounded-xl p-3 flex flex-wrap items-center justify-between gap-3 text-xs">
                  <div className="flex items-center gap-2 text-slate-300">
                    <span>💾</span>
                    <span>
                      <strong>Modo de Persistência Ativo (PENDING_SYNC):</strong> Os dados da
                      requisição foram salvos em cache local e aguardam sincronização.
                    </span>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    {/* Botão 1: Reprocessar Análise (Cascata) */}
                    <button
                      type="button"
                      disabled={processandoAcao}
                      onClick={() =>
                        handleSolicitarParecerIA(ebtAtivaId, false)
                      }
                      className="px-3.5 py-1.5 rounded-lg bg-[#E30000] hover:bg-[#C00000] text-white font-black text-xs inline-flex items-center gap-1.5 transition shadow-sm focus:outline-none focus:ring-2 focus:ring-[#E30000]"
                      title="Executar nova varredura em cascata em todas as gerações do Gemini (Gerações 4 a 1.0)"
                    >
                      <span>🔄</span>
                      <span>
                        {processandoAcao ? "Processando Cascata..." : "Reprocessar Análise"}
                      </span>
                    </button>

                    {/* Botão 2: Fallback Imediato Copiloto */}
                    <button
                      type="button"
                      disabled={processandoAcao}
                      onClick={() => handleSolicitarParecerIA(ebtAtivaId, true)}
                      className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs inline-flex items-center gap-1.5 transition shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                      title="Gerar parecer instantâneo utilizando o Copiloto Institucional sem depender de provedor externo"
                    >
                      <span>⚡</span>
                      <span>
                        Gerar Agora via Copiloto VC (Fallback Imediato)
                      </span>
                    </button>

                    {/* Botão 3: Limpar Fila de Persistência / Destravar */}
                    <button
                      type="button"
                      onClick={handleLimparOutboxCompleto}
                      className="px-3.5 py-1.5 rounded-lg border border-red-700/80 bg-red-950/90 hover:bg-red-900 text-red-200 hover:text-white font-bold text-xs inline-flex items-center gap-1.5 transition shadow-sm focus:outline-none focus:ring-2 focus:ring-red-400"
                      title="Limpar todos os itens da fila de persistência do navegador e destravar a interface"
                    >
                      <span>🗑️</span>
                      <span>Limpar Fila de Persistência</span>
                    </button>
                  </div>
                </div>

                {alertaFalhaIA.detalhe_tecnico && (
                  <details className="text-[11px] text-slate-400 pt-1">
                    <summary className="cursor-pointer hover:text-slate-200">
                      Rastreabilidade Técnica / Diagnóstico do Erro
                    </summary>
                    <pre className="mt-1.5 p-2 rounded bg-black/80 border border-[#27272A] text-red-300 whitespace-pre-wrap font-mono">
                      {alertaFalhaIA.detalhe_tecnico}
                    </pre>
                  </details>
                )}
              </div>
            )}

            {dadosEBT.ia_governanca.ultima_analise && (
              <div className="st-card space-y-4">
                {/* Badge de Telemetria de Resolução e Modelo Ativo */}
                <div className="bg-[#121212] border border-[#27272A] rounded-xl p-3 flex flex-wrap items-center justify-between gap-3 text-xs">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-base">🚀</span>
                    <span className="text-slate-400">Modelo Resolvido:</span>
                    <span className="text-white font-mono font-black text-xs px-2 py-0.5 rounded bg-zinc-900 border border-zinc-700">
                      {dadosEBT.ia_governanca.ultima_analise.modelo_resolvido ||
                        dadosEBT.ia_governanca.ultima_analise.modelo}
                    </span>
                    {dadosEBT.ia_governanca.ultima_analise.geracao_resolvida && (
                      <span className="px-2 py-0.5 rounded-full bg-red-950/80 border border-[#E30000] text-red-300 text-[11px] font-bold">
                        {dadosEBT.ia_governanca.ultima_analise.geracao_resolvida}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-slate-300 text-xs">
                    <span>⏱️ Tentativas na cascata:</span>
                    <span className="px-2 py-0.5 rounded bg-zinc-800 text-white font-mono font-bold">
                      {dadosEBT.ia_governanca.ultima_analise.tentativas_executadas || 1} tentativa(s)
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <div className="text-xs text-slate-500">
                      Status de Homologação
                    </div>
                    <div className="text-sm font-black text-[#E30000]">
                      {dadosEBT.ia_governanca.ultima_analise
                        .aprovado_pelo_consultor
                        ? "✅ Aprovado pelo Consultor"
                        : "⏳ Pendente de Revisão"}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">
                      Modelo / Versão Prompt
                    </div>
                    <div className="text-sm font-bold">
                      {dadosEBT.ia_governanca.ultima_analise.modelo} (
                      {dadosEBT.ia_governanca.ultima_analise.versao_prompt})
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">
                      Hash do Contexto
                    </div>
                    <div className="text-sm font-mono">
                      {dadosEBT.ia_governanca.ultima_analise.hash_entrada_simulacao.slice(
                        0,
                        14
                      )}
                      ...
                    </div>
                  </div>
                </div>

                <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-xs whitespace-pre-wrap leading-relaxed">
                  {textoHomologacaoIA}
                </div>

                <hr className="border-slate-200" />
                <h3 className="text-sm font-bold">
                  👨‍💼 Revisão e Homologação Obrigatória pelo Consultor / Admin
                </h3>
                <textarea
                  rows={8}
                  className="st-input text-xs"
                  value={textoHomologacaoIA}
                  onChange={(e) => setTextoHomologacaoIA(e.target.value)}
                />
                <button
                  type="button"
                  onClick={async () => {
                    const idAnalise =
                      dadosEBT.ia_governanca.ultima_analise?.id;
                    if (!idAnalise) return;
                    try {
                      await api.homologarParecerIA(
                        idAnalise,
                        textoHomologacaoIA
                      );
                      await carregarEBTCompleta(ebtAtivaId);
                      notificarSucesso(
                        "Parecer homologado oficialmente e registrado no AuditLog!"
                      );
                    } catch (err) {
                      notificarErro(err);
                    }
                  }}
                  className="st-btn w-full"
                >
                  ✅ Homologar Parecer Oficial pelo Consultor
                </button>
              </div>
            )}
          </section>
        )}

        {/* ===================================================================
            ABA 11: 🖨️ DATA ROOM (PDF)
        =================================================================== */}
        {abaAtiva === "dataroom_pdf" && dadosEBT && (
          <section className="space-y-4">
            <img
              src="https://images.unsplash.com/photo-1618044733300-9472054094ee?q=80&w=1000&auto=format&fit=crop"
              alt="Data Room PDF"
              className="w-full h-40 object-cover rounded-xl"
            />
            <h2 className="text-xl font-extrabold">
              🖨️ A Data Room Segura: Exportação Dossiê do Demoday
            </h2>
            <div className="bg-blue-50 border border-blue-200 text-blue-900 rounded-lg p-3 text-sm">
              Emissão governada do Dossiê Executivo A4 com{" "}
              <strong>cálculo de hash de integridade SHA-256</strong>,{" "}
              <strong>armazenamento isolado por Tenant</strong>,{" "}
              <strong>URL assinada com expiração (HMAC)</strong> e suporte{" "}
              <strong>White-Label</strong>.
            </div>

            {dadosEBT.ia_governanca.ultima_analise?.aprovado_pelo_consultor ? (
              <div className="bg-emerald-50 border border-emerald-200 text-emerald-900 p-3 rounded-lg text-xs">
                ✅ O Parecer de IA desta EBT já se encontra revisado e
                homologado por um Consultor.
              </div>
            ) : (
              <div className="bg-amber-50 border border-amber-200 text-amber-900 p-3 rounded-lg text-xs">
                ⚠️ O Parecer de IA desta EBT ainda não foi homologado por um
                Consultor na aba &apos;🤖 Comitê VC (IA)&apos;.
              </div>
            )}

            <div className="st-card space-y-4">
              <label className="flex items-center gap-2 text-xs font-semibold cursor-pointer">
                <input
                  type="checkbox"
                  checked={exigirHomologacaoPDF}
                  onChange={(e) => setExigirHomologacaoPDF(e.target.checked)}
                />
                🔒 Exigir Parecer de IA homologado pelo Consultor para permitir
                a emissão (Política Institucional)
              </label>

              <div>
                <label className="block text-xs font-bold mb-1">
                  Edição da Carta Parecer Oficial:
                </label>
                <textarea
                  rows={8}
                  className="st-input text-xs"
                  value={cartaParecerPDF}
                  onChange={(e) => setCartaParecerPDF(e.target.value)}
                />
              </div>

              <button
                type="button"
                disabled={processandoAcao}
                onClick={async () => {
                  try {
                    setProcessandoAcao(true);
                    const pdfRes = await api.emitirDossiePDF(ebtAtivaId, {
                      exigir_parecer_aprovado: exigirHomologacaoPDF,
                      parecer_customizado_md: cartaParecerPDF || undefined,
                    });
                    setUltimoPDFEmitido(pdfRes);
                    notificarSucesso(
                      `Dossiê Executivo gerado, assinado e arquivado com sucesso! (SHA-256: ${pdfRes.sha256_pdf.slice(0, 16)}...)`
                    );
                  } catch (err) {
                    notificarErro(err);
                  } finally {
                    setProcessandoAcao(false);
                  }
                }}
                className="st-btn w-full"
              >
                🚀 Extrair, Assinar (SHA-256) e Materializar Prospecto PDF
              </button>

              {ultimoPDFEmitido && (
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 space-y-2 text-xs">
                  <div>
                    <strong>Storage Key (Isolado por Tenant):</strong>{" "}
                    <code>{ultimoPDFEmitido.storage_key}</code>
                  </div>
                  <div>
                    <strong>Hash SHA-256 do PDF:</strong>{" "}
                    <code>{ultimoPDFEmitido.sha256_pdf}</code>
                  </div>
                  <div>
                    <strong>URL Pré-Assinada com Expiração (HMAC-SHA256):</strong>
                    <pre className="bg-slate-900 text-slate-100 p-2 rounded mt-1 overflow-x-auto">
                      {ultimoPDFEmitido.url_assinada}
                    </pre>
                  </div>
                  {ultimoPDFEmitido.pdf_base64 && (
                    <a
                      href={`data:application/pdf;base64,${ultimoPDFEmitido.pdf_base64}`}
                      download={`TermSheet_Prospecto_Duro_De_${dadosEBT.ebt.nome_startup.replace(/\s+/g, "_")}.pdf`}
                      className="inline-block st-btn text-xs mt-2"
                    >
                      📥 Baixar Dossiê Executivo Assinado (.pdf)
                    </a>
                  )}
                </div>
              )}
            </div>
          </section>
        )}

        {/* ===================================================================
            ABA 12: 🛡️ GOVERNANÇA SAAS & ADMINISTRAÇÃO DE CONTAS OAUTH
        =================================================================== */}
        {abaAtiva === "governanca" && painelGov && (
          <section className="space-y-4">
            <h2 className="text-xl font-extrabold">
              🛡️ Governança Multi-Tenant, Quotas, Contas OAuth e Auditoria
              (LGPD)
            </h2>
            <div className="bg-blue-50 border border-blue-200 text-blue-900 rounded-lg p-3 text-sm">
              Painel de controle institucional: acompanhe o uso medido do plano,
              gerencie assinantes autenticados via OAuth (atribuição de perfil
              RBAC e upgrade de plano Free Tier sob responsabilidade exclusiva
              do <strong>Admin</strong>) e audite todas as alterações.
            </div>

            {/* 1. Consumo Medido e Limites do Plano */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="st-card">
                <div className="text-xs font-bold text-slate-500">
                  Plano Contratado
                </div>
                <div className="text-xl font-black text-[#E30000] uppercase mt-1">
                  {painelGov.assinatura.plano_codigo}
                </div>
                <div className="text-[11px] text-emerald-700 font-semibold">
                  Status: {painelGov.assinatura.status.toUpperCase()}
                </div>
              </div>
              <div className="st-card">
                <div className="text-xs font-bold text-slate-500">
                  Workspaces EBT Ativos
                </div>
                <div className="text-xl font-black text-[#E30000] mt-1">
                  {painelGov.uso_mensal.ebts_ativas} /{" "}
                  {painelGov.assinatura.limite_ebts}
                </div>
              </div>
              <div className="st-card">
                <div className="text-xs font-bold text-slate-500">
                  Análises IA ({painelGov.uso_mensal.ano_mes})
                </div>
                <div className="text-xl font-black text-[#E30000] mt-1">
                  {painelGov.uso_mensal.analises_ia_realizadas} /{" "}
                  {painelGov.assinatura.limite_analises_ia_mes}
                </div>
                <div className="text-[11px] text-slate-500">
                  Custo IA: US${" "}
                  {painelGov.uso_mensal.custo_ia_acumulado_usd.toFixed(4)}
                </div>
              </div>
              <div className="st-card">
                <div className="text-xs font-bold text-slate-500">
                  Dossiês PDF / Simulações ({painelGov.uso_mensal.ano_mes})
                </div>
                <div className="text-xl font-black text-[#E30000] mt-1">
                  {painelGov.uso_mensal.pdfs_gerados} /{" "}
                  {painelGov.assinatura.limite_pdfs_mes} PDFs
                </div>
                <div className="text-[11px] text-slate-500">
                  {painelGov.uso_mensal.simulacoes_executadas} simulações
                </div>
              </div>
            </div>

            {/* 2. GESTÃO ADMINISTRATIVA DE ASSINANTES OAUTH (RBAC & UPGRADE DE PLANO) */}
            {ehAdmin ? (
              <div className="st-card space-y-3">
                <h3 className="text-sm font-extrabold text-[#0F172A]">
                  👥 Gestão Administrativa de Contas OAuth Registradas — Upgrade
                  de Plano & Vínculo RBAC (Exclusivo Admin)
                </h3>
                <p className="text-xs text-slate-600">
                  Todos os usuários abaixo autenticaram-se previamente via OAuth
                  no banco de dados. Como <strong>Admin</strong>, você é o
                  responsável por realizar o upgrade de assinantes{" "}
                  <code>FREE TIER</code> para planos pagos (
                  <code>STARTER</code>, <code>PRO</code>,{" "}
                  <code>ENTERPRISE</code>) e atribuir seus papéis RBAC:
                </p>

                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-100 text-slate-700">
                        <th className="p-2">Usuário OAuth</th>
                        <th className="p-2">Provedor</th>
                        <th className="p-2">Workspace / Tenant</th>
                        <th className="p-2">Papel RBAC</th>
                        <th className="p-2">Plano de Assinatura</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(painelGov.usuarios_oauth_registrados || []).map((u) => (
                        <tr
                          key={u.membership_id}
                          className="border-b border-slate-200"
                        >
                          <td className="p-2">
                            <div className="font-bold">{u.nome_completo}</div>
                            <div className="text-slate-500">{u.email}</div>
                          </td>
                          <td className="p-2 uppercase font-semibold text-blue-700">
                            {u.provedor}
                          </td>
                          <td className="p-2">{u.tenant_nome}</td>
                          <td className="p-2">
                            {u.user_id === sessao.user.id ? (
                              <span
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-blue-100 text-blue-900 font-bold text-[11px]"
                                title="Restrição de segurança: você não pode remover seu próprio papel de Administrador."
                              >
                                🔒 {u.papel.toUpperCase()} (Sua Conta)
                              </span>
                            ) : (
                              <select
                                className="st-input !py-1 text-xs"
                                value={u.papel}
                                onChange={async (e) => {
                                  try {
                                    await api.gerenciarAssinanteOAuthPeloAdmin(
                                      u.membership_id,
                                      {
                                        novo_papel: e.target.value as PapelRBAC,
                                      }
                                    );
                                    const g = await api.obterPainelGovernanca();
                                    setPainelGov(g);
                                    const s = await api.obterSessaoAtual();
                                    setSessao(s);
                                    notificarSucesso(
                                      `Papel RBAC de ${u.email} atualizado para ${e.target.value.toUpperCase()}!`
                                    );
                                  } catch (err) {
                                    notificarErro(err);
                                  }
                                }}
                              >
                                {PAPEIS_RBAC_OPCOES.map((op) => (
                                  <option key={op.value} value={op.value}>
                                    {op.label}
                                  </option>
                                ))}
                              </select>
                            )}
                          </td>
                          <td className="p-2">
                            <select
                              className="st-input !py-1 text-xs font-bold"
                              value={u.plano_codigo}
                              onChange={async (e) => {
                                try {
                                  await api.gerenciarAssinanteOAuthPeloAdmin(
                                    u.membership_id,
                                    {
                                      novo_plano: e.target
                                        .value as PlanoCodigo,
                                    }
                                  );
                                  const g = await api.obterPainelGovernanca();
                                  setPainelGov(g);
                                  const s = await api.obterSessaoAtual();
                                  setSessao(s);
                                  notificarSucesso(
                                    `Plano de ${u.email} atualizado pelo Admin para ${e.target.value.toUpperCase()}!`
                                  );
                                } catch (err) {
                                  notificarErro(err);
                                }
                              }}
                            >
                              <option value="free">
                                FREE TIER (Gratuito)
                              </option>
                              <option value="starter">STARTER</option>
                              <option value="pro">PRO</option>
                              <option value="enterprise">ENTERPRISE</option>
                            </select>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Emissão de Links de Convite OAuth RBAC pelo Admin */}
                <hr className="border-slate-200 pt-2" />
                <h4 className="text-xs font-bold">
                  🔗 Emitir Link de Convite OAuth pré-vinculado a um Papel RBAC
                </h4>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    try {
                      const res = await api.criarConviteRBAC({
                        email_convidado: conviteRBACForm.email_convidado,
                        papel: conviteRBACForm.papel,
                        ebt_restrita_id:
                          conviteRBACForm.papel === "fundador" ||
                          conviteRBACForm.papel === "investidor"
                            ? ebtAtivaId
                            : undefined,
                        dias_validade: conviteRBACForm.dias_validade,
                      });
                      setLinkConviteOAuthGerado(
                        `${window.location.origin}${res.oauth_invite_url}`
                      );
                      notificarSucesso("Link de Convite OAuth RBAC gerado!");
                    } catch (err) {
                      notificarErro(err);
                    }
                  }}
                  className="grid grid-cols-1 md:grid-cols-4 gap-3"
                >
                  <input
                    type="email"
                    required
                    placeholder="E-mail do convidado OAuth"
                    className="st-input text-xs"
                    value={conviteRBACForm.email_convidado}
                    onChange={(e) =>
                      setConviteRBACForm({
                        ...conviteRBACForm,
                        email_convidado: e.target.value,
                      })
                    }
                  />
                  <select
                    className="st-input text-xs"
                    value={conviteRBACForm.papel}
                    onChange={(e) =>
                      setConviteRBACForm({
                        ...conviteRBACForm,
                        papel: e.target.value as PapelRBAC,
                      })
                    }
                  >
                    <option value="consultor">CONSULTOR</option>
                    <option value="analista">ANALISTA</option>
                    <option value="fundador">FUNDADOR (EBT Atual)</option>
                    <option value="investidor">
                      INVESTIDOR (Read-Only EBT Atual)
                    </option>
                    <option value="admin">ADMIN</option>
                  </select>
                  <input
                    type="number"
                    min={1}
                    max={90}
                    className="st-input text-xs"
                    value={conviteRBACForm.dias_validade}
                    onChange={(e) =>
                      setConviteRBACForm({
                        ...conviteRBACForm,
                        dias_validade: Number(e.target.value),
                      })
                    }
                  />
                  <button type="submit" className="st-btn text-xs">
                    Gerar Link OAuth RBAC
                  </button>
                </form>
                {linkConviteOAuthGerado && (
                  <pre className="bg-slate-900 text-slate-100 p-2 rounded text-xs overflow-x-auto">
                    {linkConviteOAuthGerado}
                  </pre>
                )}
              </div>
            ) : (
              <div className="bg-amber-50 border border-amber-200 text-amber-900 p-4 rounded-xl text-xs">
                🔒{" "}
                <strong>
                  Conta Categorizada como Assinante{" "}
                  {sessao.tenant.plano_codigo.toUpperCase()}:
                </strong>{" "}
                O upgrade do plano de assinatura (Free Tier → Starter / Pro /
                Enterprise) e a elevação de perfil RBAC estão sob
                responsabilidade exclusiva do{" "}
                <strong>Administrador (`admin`)</strong>.
              </div>
            )}

            {/* 3. Fila de Jobs Assíncronos e Dossiês Emitidos */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="st-card">
                <h3 className="text-sm font-bold mb-2">
                  ⚙️ Fila de Jobs Assíncronos (JobAssincronoSaaS)
                </h3>
                {painelGov.jobs_assincronos.length === 0 ? (
                  <p className="text-xs text-slate-500">
                    Nenhum job de IA ou PDF processado neste Tenant ainda.
                  </p>
                ) : (
                  <table className="w-full text-xs text-left">
                    <thead>
                      <tr className="bg-slate-100">
                        <th className="p-1.5">Job ID</th>
                        <th className="p-1.5">Tipo</th>
                        <th className="p-1.5">Status</th>
                        <th className="p-1.5">Progresso</th>
                      </tr>
                    </thead>
                    <tbody>
                      {painelGov.jobs_assincronos.map((j) => (
                        <tr key={j.id} className="border-b border-slate-100">
                          <td className="p-1.5 font-mono">
                            {j.id.slice(0, 8)}
                          </td>
                          <td className="p-1.5">{j.tipo_job}</td>
                          <td className="p-1.5 uppercase font-bold">
                            {j.status}
                          </td>
                          <td className="p-1.5">{j.progresso_pct}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              <div className="st-card">
                <h3 className="text-sm font-bold mb-2">
                  📄 Dossiês PDF Emitidos (RelatorioDossieEBT)
                </h3>
                {painelGov.dossies_emitidos.length === 0 ? (
                  <p className="text-xs text-slate-500">
                    Nenhum Dossiê PDF emitido neste Tenant ainda.
                  </p>
                ) : (
                  <table className="w-full text-xs text-left">
                    <thead>
                      <tr className="bg-slate-100">
                        <th className="p-1.5">Dossiê ID</th>
                        <th className="p-1.5">SHA-256</th>
                        <th className="p-1.5">Arquivo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {painelGov.dossies_emitidos.map((d) => (
                        <tr key={d.id} className="border-b border-slate-100">
                          <td className="p-1.5 font-mono">
                            {d.id.slice(0, 8)}
                          </td>
                          <td className="p-1.5 font-mono">
                            {d.sha256_pdf.slice(0, 12)}...
                          </td>
                          <td className="p-1.5">
                            {d.storage_key.split("/").pop()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* 4. Links Temporários para Investidor / Banca */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="st-card space-y-2">
                <h3 className="text-sm font-bold">
                  🔑 Gerar Token de Acesso Somente-Leitura (Investidor)
                </h3>
                <input
                  type="number"
                  min={1}
                  max={90}
                  className="st-input text-xs"
                  value={diasShareLink}
                  onChange={(e) => setDiasShareLink(Number(e.target.value))}
                />
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      const res = await api.criarShareLink(
                        ebtAtivaId,
                        diasShareLink
                      );
                      setTokenShareGerado(res.token);
                    } catch (err) {
                      notificarErro(err);
                    }
                  }}
                  className="st-btn w-full text-xs"
                >
                  🔑 Gerar Token de Acesso Somente-Leitura
                </button>
                {tokenShareGerado && (
                  <pre className="bg-slate-900 text-slate-100 p-2 rounded text-xs">
                    {tokenShareGerado}
                  </pre>
                )}
              </div>

              <div className="st-card space-y-2">
                <h3 className="text-sm font-bold">
                  🔍 Validar Token Recebido de Investidor
                </h3>
                <input
                  className="st-input text-xs"
                  placeholder="Cole o token..."
                  value={tokenParaValidar}
                  onChange={(e) => setTokenParaValidar(e.target.value)}
                />
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      const r = await api.validarShareLink(tokenParaValidar);
                      setResValidacaoShare(
                        `✅ Token válido para EBT ${r.ebt_id.slice(0, 8)}... (${r.acessos_realizados} acessos)`
                      );
                    } catch (err) {
                      notificarErro(err);
                    }
                  }}
                  className="st-btn w-full text-xs"
                >
                  🔍 Verificar Validade e Registrar Acesso
                </button>
                {resValidacaoShare && (
                  <div className="text-xs text-emerald-700 font-bold">
                    {resValidacaoShare}
                  </div>
                )}
              </div>
            </div>

            {/* 5. Trilha de Auditoria Imutável (AuditLog) */}
            <div className="st-card">
              <h3 className="text-sm font-bold mb-2">
                📜 Trilha de Auditoria Imutável do Tenant (AuditLog)
              </h3>
              <div className="max-h-60 overflow-y-auto">
                <table className="w-full text-xs text-left">
                  <thead className="sticky top-0 bg-slate-100">
                    <tr>
                      <th className="p-2">Ação</th>
                      <th className="p-2">Entidade</th>
                      <th className="p-2">Resumo Operacional</th>
                      <th className="p-2">Usuário</th>
                    </tr>
                  </thead>
                  <tbody>
                    {painelGov.audit_logs.map((ev) => (
                      <tr key={ev.id} className="border-b border-slate-100">
                        <td className="p-2 font-mono font-bold">{ev.acao}</td>
                        <td className="p-2">{ev.entidade_tipo}</td>
                        <td className="p-2">{ev.resumo}</td>
                        <td className="p-2 font-mono">
                          {(ev.user_id || "sistema").slice(0, 8)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 6. DDL PostgreSQL RLS */}
            <details className="st-card text-xs">
              <summary className="font-bold cursor-pointer">
                🗄️ Visualizar Script SQL de Row-Level Security (PostgreSQL RLS)
              </summary>
              <pre className="bg-slate-900 text-slate-100 p-3 rounded-lg mt-2 overflow-x-auto text-[11px]">
                {painelGov.ddl_rls_postgresql}
              </pre>
            </details>
          </section>
        )}

        {/* ===================================================================
            ABA 13: 🛡️ PAINEL DE ADMINISTRAÇÃO DE RBAC (CONTROLE DE PERFIS)
            Visível e acessível exclusivamente para usuários com role ADMIN.
        =================================================================== */}
        {abaAtiva === "painel_rbac" && (
          <section className="space-y-4">
            {!ehAdmin ? (
              <div className="bg-red-50 border-l-4 border-red-600 text-red-900 p-6 rounded-xl text-sm">
                <h3 className="text-base font-extrabold mb-1">
                  🔒 Acesso Restrito ao Administrador (ADMIN)
                </h3>
                <p>
                  Seu perfil atual (
                  <code className="font-bold uppercase">
                    {sessao.membership_ativa.papel}
                  </code>
                  ) não possui permissão para visualizar ou gerenciar o Painel
                  de Administração de RBAC.
                </p>
              </div>
            ) : (
              <>
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-extrabold text-[#0F172A]">
                      🛡️ Painel de Administração de RBAC — Controle de Perfis &
                      Assinantes
                    </h2>
                    <p className="text-xs text-slate-600 mt-0.5">
                      Gerencie papéis de acesso (<code>ADMIN</code>,{" "}
                      <code>GESTOR</code>, <code>ANALISTA</code>,{" "}
                      <code>ASSINANTE_FREE</code>, <code>ASSINANTE_PRO</code>),
                      planos de assinatura e status das contas cadastradas.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => carregarUsuariosDoPainelRBAC()}
                      className="px-3 py-2 bg-white border border-slate-300 hover:bg-slate-100 rounded-lg text-xs font-bold text-slate-700"
                    >
                      🔄 Atualizar Lista
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        setMostrarModalNovoUsuario((aberto) => !aberto)
                      }
                      className="st-btn !py-2 text-xs"
                    >
                      ➕ Novo Usuário
                    </button>
                  </div>
                </div>

                {/* KPIs do Painel Admin */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="st-card">
                    <div className="text-xs font-bold text-slate-500">
                      Total de Usuários
                    </div>
                    <div className="text-2xl font-black text-[#E30000] mt-1">
                      {usuariosRBAC.length}
                    </div>
                    <div className="text-[11px] text-slate-500">
                      Contas registradas no banco
                    </div>
                  </div>
                  <div className="st-card">
                    <div className="text-xs font-bold text-slate-500">
                      Administradores (ADMIN)
                    </div>
                    <div className="text-2xl font-black text-[#E30000] mt-1">
                      {
                        usuariosRBAC.filter(
                          (u) => u.papel === "admin" || u.papel === "dono"
                        ).length
                      }
                    </div>
                    <div className="text-[11px] text-emerald-700 font-semibold">
                      Acesso total habilitado
                    </div>
                  </div>
                  <div className="st-card">
                    <div className="text-xs font-bold text-slate-500">
                      Gestores / Analistas / Pro
                    </div>
                    <div className="text-2xl font-black text-[#E30000] mt-1">
                      {
                        usuariosRBAC.filter((u) =>
                          [
                            "gestor",
                            "analista",
                            "consultor",
                            "assinante_pro",
                          ].includes(u.papel)
                        ).length
                      }
                    </div>
                    <div className="text-[11px] text-slate-500">
                      Operação e análise avançada
                    </div>
                  </div>
                  <div className="st-card">
                    <div className="text-xs font-bold text-slate-500">
                      Contas Ativas
                    </div>
                    <div className="text-2xl font-black text-emerald-600 mt-1">
                      {usuariosRBAC.filter((u) => u.ativo !== false).length} /{" "}
                      {usuariosRBAC.length}
                    </div>
                    <div className="text-[11px] text-slate-500">
                      Status operacional ativo
                    </div>
                  </div>
                </div>

                {/* Formulário / Modal de Criação de Novo Usuário pelo Admin */}
                {mostrarModalNovoUsuario && (
                  <div className="st-card border-2 border-blue-200 bg-blue-50/30 space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-extrabold text-[#0F172A]">
                        ➕ Cadastrar Novo Usuário no Sistema (Admin)
                      </h3>
                      <button
                        type="button"
                        onClick={() => setMostrarModalNovoUsuario(false)}
                        className="text-xs font-bold text-slate-500 hover:text-slate-800"
                      >
                        ✕ Fechar
                      </button>
                    </div>
                    <form
                      onSubmit={async (e) => {
                        e.preventDefault();
                        try {
                          await api.criarUsuarioPeloAdmin(novoUsuarioAdminForm);
                          setNovoUsuarioAdminForm({
                            nome_completo: "",
                            email: "",
                            senha: "",
                            papel: "assinante_free",
                            plano: "free",
                            cargo_organizacao: "",
                            telefone_whatsapp: "",
                          });
                          setMostrarModalNovoUsuario(false);
                          await carregarUsuariosDoPainelRBAC();
                          const s = await api.obterSessaoAtual();
                          setSessao(s);
                          notificarSucesso(
                            "Novo usuário cadastrado com sucesso no Painel RBAC!"
                          );
                        } catch (err) {
                          notificarErro(err);
                        }
                      }}
                      className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs"
                    >
                      <div>
                        <label className="block font-bold mb-1">
                          Nome Completo *
                        </label>
                        <input
                          type="text"
                          required
                          placeholder="Nome do usuário"
                          className="st-input text-xs"
                          value={novoUsuarioAdminForm.nome_completo}
                          onChange={(e) =>
                            setNovoUsuarioAdminForm({
                              ...novoUsuarioAdminForm,
                              nome_completo: e.target.value,
                            })
                          }
                        />
                      </div>
                      <div>
                        <label className="block font-bold mb-1">E-mail *</label>
                        <input
                          type="email"
                          required
                          placeholder="usuario@empresa.com.br"
                          className="st-input text-xs"
                          value={novoUsuarioAdminForm.email}
                          onChange={(e) =>
                            setNovoUsuarioAdminForm({
                              ...novoUsuarioAdminForm,
                              email: e.target.value,
                            })
                          }
                        />
                      </div>
                      <div>
                        <label className="block font-bold mb-1">
                          Senha Inicial (mín. 6 caracteres) *
                        </label>
                        <input
                          type="password"
                          required
                          placeholder="Senha inicial"
                          className="st-input text-xs"
                          value={novoUsuarioAdminForm.senha}
                          onChange={(e) =>
                            setNovoUsuarioAdminForm({
                              ...novoUsuarioAdminForm,
                              senha: e.target.value,
                            })
                          }
                        />
                      </div>
                      <div>
                        <label className="block font-bold mb-1">
                          Papel / Role RBAC *
                        </label>
                        <select
                          className="st-input text-xs font-semibold"
                          value={novoUsuarioAdminForm.papel}
                          onChange={(e) => {
                            const novoPapel = e.target.value as PapelRBAC;
                            let novoPlano = novoUsuarioAdminForm.plano;
                            if (novoPapel === "assinante_free")
                              novoPlano = "free";
                            if (novoPapel === "assinante_pro")
                              novoPlano = "pro";
                            setNovoUsuarioAdminForm({
                              ...novoUsuarioAdminForm,
                              papel: novoPapel,
                              plano: novoPlano,
                            });
                          }}
                        >
                          {PAPEIS_RBAC_OPCOES.map((op) => (
                            <option key={op.value} value={op.value}>
                              {op.label}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block font-bold mb-1">
                          Plano Associado
                        </label>
                        <select
                          className="st-input text-xs font-semibold"
                          value={novoUsuarioAdminForm.plano}
                          onChange={(e) =>
                            setNovoUsuarioAdminForm({
                              ...novoUsuarioAdminForm,
                              plano: e.target.value as PlanoCodigo,
                            })
                          }
                        >
                          <option value="free">FREE TIER</option>
                          <option value="starter">STARTER</option>
                          <option value="pro">PRO</option>
                          <option value="enterprise">ENTERPRISE</option>
                        </select>
                      </div>
                      <div>
                        <label className="block font-bold mb-1">
                          Cargo / Organização
                        </label>
                        <input
                          type="text"
                          placeholder="Ex: Analista de Investimentos"
                          className="st-input text-xs"
                          value={novoUsuarioAdminForm.cargo_organizacao}
                          onChange={(e) =>
                            setNovoUsuarioAdminForm({
                              ...novoUsuarioAdminForm,
                              cargo_organizacao: e.target.value,
                            })
                          }
                        />
                      </div>
                      <div className="md:col-span-3 flex justify-end gap-2 pt-1">
                        <button type="submit" className="st-btn text-xs !py-2">
                          💾 Criar Usuário e Vincular Perfil RBAC
                        </button>
                      </div>
                    </form>
                  </div>
                )}

                {/* Tabela Principal de Usuários e Gerenciamento de Papéis RBAC */}
                <div className="st-card space-y-3">
                  <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                    <h3 className="text-sm font-extrabold text-[#0F172A]">
                      👥 Usuários Cadastrados e Controle de Papéis (RBAC)
                    </h3>
                    <input
                      type="text"
                      placeholder="🔍 Filtrar por nome, e-mail ou papel..."
                      className="st-input !w-full md:!w-80 text-xs !py-1.5"
                      value={filtroBuscaRBAC}
                      onChange={(e) => setFiltroBuscaRBAC(e.target.value)}
                    />
                  </div>

                  <div className="bg-amber-50 border border-amber-200 text-amber-900 rounded-lg p-2.5 text-xs">
                    🛡️ <strong>Trava de Segurança Ativa:</strong> Para evitar
                    perda acidental de acesso administrativo, o administrador
                    logado (<code>{sessao.user.email}</code>) está impedido de
                    remover seu próprio papel <code>ADMIN</code> ou inativar sua
                    própria conta.
                  </div>

                  {carregandoUsuariosRBAC ? (
                    <div className="p-6 text-center text-xs text-slate-500">
                      ⏳ Carregando lista de usuários cadastrados...
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs text-left border-collapse">
                        <thead>
                          <tr className="bg-slate-100 text-slate-700 border-b border-slate-200">
                            <th className="p-2.5">Nome / Cargo</th>
                            <th className="p-2.5">E-mail / Contato</th>
                            <th className="p-2.5">Papel / Role Atual (RBAC)</th>
                            <th className="p-2.5">Plano</th>
                            <th className="p-2.5">Status</th>
                            <th className="p-2.5 text-right">Ações</th>
                          </tr>
                        </thead>
                        <tbody>
                          {usuariosRBAC
                            .filter((u) => {
                              const q = filtroBuscaRBAC.trim().toLowerCase();
                              if (!q) return true;
                              return (
                                u.nome_completo.toLowerCase().includes(q) ||
                                u.email.toLowerCase().includes(q) ||
                                u.papel.toLowerCase().includes(q)
                              );
                            })
                            .map((u) => {
                              const ehProprioAdmin =
                                u.user_id === sessao.user.id;
                              const edicao = edicoesRBAC[u.membership_id] || {
                                papel: u.papel,
                                plano_codigo: u.plano_codigo,
                                ativo: u.ativo !== false,
                              };
                              const houveMudanca =
                                edicao.papel !== u.papel ||
                                edicao.plano_codigo !== u.plano_codigo ||
                                edicao.ativo !== (u.ativo !== false);

                              return (
                                <tr
                                  key={u.membership_id}
                                  className="border-b border-slate-200 hover:bg-slate-50/80 transition"
                                >
                                  <td className="p-2.5">
                                    <div className="flex items-center gap-2.5">
                                      {u.avatar_url ? (
                                        <img
                                          src={u.avatar_url}
                                          alt={u.nome_completo}
                                          className="w-8 h-8 rounded-full object-cover border border-slate-300"
                                        />
                                      ) : (
                                        <div className="w-8 h-8 rounded-full bg-red-100 text-[#E30000] font-black flex items-center justify-center text-[11px]">
                                          {obterIniciais(u.nome_completo)}
                                        </div>
                                      )}
                                      <div>
                                        <div className="font-bold text-slate-900 flex items-center gap-1.5">
                                          <span>{u.nome_completo}</span>
                                          {ehProprioAdmin && (
                                            <span className="px-1.5 py-0.5 text-[10px] rounded bg-[#E30000] text-white font-bold">
                                              Você
                                            </span>
                                          )}
                                        </div>
                                        <div className="text-[11px] text-slate-500">
                                          {u.cargo_organizacao || u.tenant_nome}
                                        </div>
                                      </div>
                                    </div>
                                  </td>

                                  <td className="p-2.5">
                                    <div className="font-medium text-slate-800">
                                      {u.email}
                                    </div>
                                    {u.telefone_whatsapp && (
                                      <div className="text-[11px] text-slate-500">
                                        📱 {u.telefone_whatsapp}
                                      </div>
                                    )}
                                  </td>

                                  <td className="p-2.5">
                                    {ehProprioAdmin ? (
                                      <div
                                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-zinc-100 border border-zinc-300 text-zinc-900 font-bold text-xs"
                                        title="Impedido de remover seu próprio papel de administrador por segurança."
                                      >
                                        🔒 {u.papel.toUpperCase()} (Protegido)
                                      </div>
                                    ) : (
                                      <select
                                        aria-label={`Alterar papel de ${u.email}`}
                                        className="st-input !py-1.5 text-xs font-bold"
                                        value={edicao.papel}
                                        onChange={(e) => {
                                          const novoPapel = e.target
                                            .value as PapelRBAC;
                                          let novoPlano = edicao.plano_codigo;
                                          if (novoPapel === "assinante_free")
                                            novoPlano = "free";
                                          if (novoPapel === "assinante_pro")
                                            novoPlano = "pro";
                                          setEdicoesRBAC({
                                            ...edicoesRBAC,
                                            [u.membership_id]: {
                                              ...edicao,
                                              papel: novoPapel,
                                              plano_codigo: novoPlano,
                                            },
                                          });
                                        }}
                                      >
                                        {PAPEIS_RBAC_OPCOES.map((op) => (
                                          <option
                                            key={op.value}
                                            value={op.value}
                                          >
                                            {op.label}
                                          </option>
                                        ))}
                                      </select>
                                    )}
                                  </td>

                                  <td className="p-2.5">
                                    <select
                                      aria-label={`Alterar plano de ${u.email}`}
                                      className="st-input !py-1.5 text-xs font-semibold"
                                      value={edicao.plano_codigo}
                                      onChange={(e) =>
                                        setEdicoesRBAC({
                                          ...edicoesRBAC,
                                          [u.membership_id]: {
                                            ...edicao,
                                            plano_codigo: e.target
                                              .value as PlanoCodigo,
                                          },
                                        })
                                      }
                                    >
                                      <option value="free">FREE TIER</option>
                                      <option value="starter">STARTER</option>
                                      <option value="pro">PRO</option>
                                      <option value="enterprise">
                                        ENTERPRISE
                                      </option>
                                    </select>
                                  </td>

                                  <td className="p-2.5">
                                    <button
                                      type="button"
                                      disabled={ehProprioAdmin}
                                      onClick={() =>
                                        setEdicoesRBAC({
                                          ...edicoesRBAC,
                                          [u.membership_id]: {
                                            ...edicao,
                                            ativo: !edicao.ativo,
                                          },
                                        })
                                      }
                                      className={`px-2.5 py-1 rounded-full text-[11px] font-bold transition ${
                                        edicao.ativo
                                          ? "bg-emerald-100 text-emerald-900 border border-emerald-300"
                                          : "bg-red-100 text-red-900 border border-red-300"
                                      } ${
                                        ehProprioAdmin
                                          ? "opacity-75 cursor-not-allowed"
                                          : "hover:opacity-80 cursor-pointer"
                                      }`}
                                      title={
                                        ehProprioAdmin
                                          ? "Você não pode inativar sua própria conta de Administrador."
                                          : "Clique para alternar entre Ativo e Inativo"
                                      }
                                    >
                                      {edicao.ativo ? "● Ativo" : "○ Inativo"}
                                    </button>
                                  </td>

                                  <td className="p-2.5 text-right">
                                    <div className="inline-flex items-center gap-1.5 flex-wrap justify-end">
                                      {/* 1. Mudar Plano */}
                                      <button
                                        type="button"
                                        onClick={() => abrirModalPlano(u)}
                                        className="px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 text-slate-800 font-bold text-xs inline-flex items-center gap-1 transition focus:outline-none focus:ring-2 focus:ring-[#E30000]"
                                        title={`Mudar plano de assinatura de ${u.nome_completo}`}
                                        aria-label={`Mudar plano de ${u.nome_completo}`}
                                      >
                                        <span>💳</span> Plano
                                      </button>

                                      {/* 2. Visualizar Uso */}
                                      <button
                                        type="button"
                                        onClick={() => abrirModalUso(u)}
                                        className="px-2.5 py-1.5 rounded-lg border border-indigo-200 bg-indigo-50/70 hover:bg-indigo-100 text-indigo-900 font-bold text-xs inline-flex items-center gap-1 transition focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        title={`Visualizar consumo de recursos e métricas de ${u.nome_completo}`}
                                        aria-label={`Visualizar uso de recursos de ${u.nome_completo}`}
                                      >
                                        <span>📊</span> Uso
                                      </button>

                                      {/* 3. Editar Dados */}
                                      <button
                                        type="button"
                                        onClick={() => abrirModalEdicao(u)}
                                        className="px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 text-slate-800 font-bold text-xs inline-flex items-center gap-1 transition focus:outline-none focus:ring-2 focus:ring-[#E30000]"
                                        title={`Editar dados cadastrais e permissões de ${u.nome_completo}`}
                                        aria-label={`Editar dados de ${u.nome_completo}`}
                                      >
                                        <span>✏️</span> Editar
                                      </button>

                                      {/* 4. Excluir Conta (com trava para o próprio admin) */}
                                      {ehProprioAdmin ? (
                                        <button
                                          type="button"
                                          disabled
                                          className="px-2 py-1.5 rounded-lg border border-zinc-200 bg-zinc-100 text-zinc-400 font-bold text-xs inline-flex items-center gap-1 cursor-not-allowed opacity-60"
                                          title="Trava de segurança: Você não pode excluir a sua própria conta de Administrador."
                                          aria-label="Exclusão bloqueada para o próprio Administrador"
                                        >
                                          <span>🔒</span> Protegido
                                        </button>
                                      ) : (
                                        <button
                                          type="button"
                                          onClick={() => abrirModalExclusao(u)}
                                          className="px-2.5 py-1.5 rounded-lg border border-red-200 bg-red-50/80 hover:bg-red-100 text-[#E30000] font-bold text-xs inline-flex items-center gap-1 transition focus:outline-none focus:ring-2 focus:ring-[#E30000]"
                                          title={`Excluir definitivamente o registro de ${u.nome_completo}`}
                                          aria-label={`Excluir conta de ${u.nome_completo}`}
                                        >
                                          <span>🗑️</span> Excluir
                                        </button>
                                      )}

                                      {/* Salvamento rápido inline se houve mudança direta na linha */}
                                      {houveMudanca && (
                                        <button
                                          type="button"
                                          onClick={async () => {
                                            try {
                                              await api.gerenciarAssinanteOAuthPeloAdmin(
                                                u.membership_id,
                                                {
                                                  novo_papel: edicao.papel,
                                                  novo_plano: edicao.plano_codigo,
                                                  ativo: edicao.ativo,
                                                }
                                              );
                                              await carregarUsuariosDoPainelRBAC();
                                              const s =
                                                await api.obterSessaoAtual();
                                              setSessao(s);
                                              notificarSucesso(
                                                `Alterações de RBAC para ${u.nome_completo} salvas com sucesso!`
                                              );
                                            } catch (err) {
                                              notificarErro(err);
                                            }
                                          }}
                                          className="px-2.5 py-1.5 rounded-lg font-bold text-xs bg-[#E30000] text-white hover:bg-[#C00000] shadow-sm inline-flex items-center gap-1"
                                          title="Salvar alterações rápidas feitas nesta linha"
                                        >
                                          💾 Salvar
                                        </button>
                                      )}
                                    </div>
                                  </td>
                                </tr>
                              );
                            })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                {/* =============================================================
                    MODAL 1: ✏️ EDITAR DADOS DO USUÁRIO
                ============================================================= */}
                {usuarioModalEdicao && (
                  <div
                    className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto"
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="modal-edicao-titulo"
                  >
                    <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-xl w-full p-6 space-y-4 my-8 animate-in fade-in duration-150">
                      <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                        <div className="flex items-center gap-2">
                          <span className="text-xl">✏️</span>
                          <div>
                            <h3
                              id="modal-edicao-titulo"
                              className="text-base font-extrabold text-[#0F172A]"
                            >
                              Editar Dados do Usuário
                            </h3>
                            <p className="text-xs text-slate-500">
                              {usuarioModalEdicao.nome_completo} • {usuarioModalEdicao.email}
                            </p>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setUsuarioModalEdicao(null)}
                          className="text-slate-400 hover:text-slate-700 font-bold p-1 rounded-lg"
                          aria-label="Fechar modal de edição"
                        >
                          ✕
                        </button>
                      </div>

                      <form onSubmit={handleSalvarEdicaoAvancada} className="space-y-3.5 text-xs">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          <div>
                            <label className="block font-bold text-slate-700 mb-1">
                              Nome Completo *
                            </label>
                            <input
                              type="text"
                              required
                              className="st-input text-xs"
                              value={formEdicaoUsuario.nome_completo}
                              onChange={(e) =>
                                setFormEdicaoUsuario({
                                  ...formEdicaoUsuario,
                                  nome_completo: e.target.value,
                                })
                              }
                            />
                          </div>

                          <div>
                            <label className="block font-bold text-slate-700 mb-1">
                              E-mail Corporativo *
                            </label>
                            <input
                              type="email"
                              required
                              disabled={usuarioModalEdicao.email.toLowerCase() === "marcolinoee@yahoo.com.br"}
                              className={`st-input text-xs ${
                                usuarioModalEdicao.email.toLowerCase() === "marcolinoee@yahoo.com.br"
                                  ? "bg-slate-100 text-slate-500 cursor-not-allowed"
                                  : ""
                              }`}
                              value={formEdicaoUsuario.email}
                              onChange={(e) =>
                                setFormEdicaoUsuario({
                                  ...formEdicaoUsuario,
                                  email: e.target.value,
                                })
                              }
                            />
                            {usuarioModalEdicao.email.toLowerCase() === "marcolinoee@yahoo.com.br" && (
                              <span className="text-[10px] text-amber-700 font-medium">
                                🔒 E-mail raiz do Administrador bloqueado contra alteração.
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          <div>
                            <label className="block font-bold text-slate-700 mb-1">
                              Cargo / Organização
                            </label>
                            <input
                              type="text"
                              placeholder="Ex: Diretor Financeiro / EBT Alpha"
                              className="st-input text-xs"
                              value={formEdicaoUsuario.cargo_organizacao}
                              onChange={(e) =>
                                setFormEdicaoUsuario({
                                  ...formEdicaoUsuario,
                                  cargo_organizacao: e.target.value,
                                })
                              }
                            />
                          </div>

                          <div>
                            <label className="block font-bold text-slate-700 mb-1">
                              Telefone / WhatsApp
                            </label>
                            <input
                              type="tel"
                              placeholder="+55 11 99999-9999"
                              className="st-input text-xs"
                              value={formEdicaoUsuario.telefone_whatsapp}
                              onChange={(e) =>
                                setFormEdicaoUsuario({
                                  ...formEdicaoUsuario,
                                  telefone_whatsapp: e.target.value,
                                })
                              }
                            />
                          </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
                          <div>
                            <label className="block font-bold text-slate-700 mb-1">
                              Papel / Role RBAC
                            </label>
                            <select
                              disabled={usuarioModalEdicao.user_id === sessao.user.id}
                              className={`st-input text-xs font-bold ${
                                usuarioModalEdicao.user_id === sessao.user.id
                                  ? "bg-slate-100 text-slate-500 cursor-not-allowed"
                                  : ""
                              }`}
                              value={formEdicaoUsuario.papel}
                              onChange={(e) => {
                                const novoPapel = e.target.value as PapelRBAC;
                                let novoPlano = formEdicaoUsuario.plano_codigo;
                                if (novoPapel === "assinante_free") novoPlano = "free";
                                if (novoPapel === "assinante_pro") novoPlano = "pro";
                                setFormEdicaoUsuario({
                                  ...formEdicaoUsuario,
                                  papel: novoPapel,
                                  plano_codigo: novoPlano,
                                });
                              }}
                            >
                              {PAPEIS_RBAC_OPCOES.map((op) => (
                                <option key={op.value} value={op.value}>
                                  {op.label}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div>
                            <label className="block font-bold text-slate-700 mb-1">
                              Plano Atual
                            </label>
                            <select
                              className="st-input text-xs font-bold"
                              value={formEdicaoUsuario.plano_codigo}
                              onChange={(e) =>
                                setFormEdicaoUsuario({
                                  ...formEdicaoUsuario,
                                  plano_codigo: e.target.value as PlanoCodigo,
                                })
                              }
                            >
                              <option value="free">FREE TIER</option>
                              <option value="starter">STARTER</option>
                              <option value="pro">PRO</option>
                              <option value="enterprise">ENTERPRISE</option>
                            </select>
                          </div>

                          <div>
                            <label className="block font-bold text-slate-700 mb-1">
                              Status de Ativação
                            </label>
                            <select
                              disabled={usuarioModalEdicao.user_id === sessao.user.id}
                              className={`st-input text-xs font-bold ${
                                usuarioModalEdicao.user_id === sessao.user.id
                                  ? "bg-slate-100 text-slate-500 cursor-not-allowed"
                                  : ""
                              }`}
                              value={formEdicaoUsuario.ativo ? "ativo" : "inativo"}
                              onChange={(e) =>
                                setFormEdicaoUsuario({
                                  ...formEdicaoUsuario,
                                  ativo: e.target.value === "ativo",
                                })
                              }
                            >
                              <option value="ativo">● Ativo</option>
                              <option value="inativo">○ Inativo</option>
                            </select>
                          </div>
                        </div>

                        {usuarioModalEdicao.user_id === sessao.user.id && (
                          <div className="bg-amber-50 border border-amber-200 text-amber-900 p-2.5 rounded-lg text-[11px] flex items-center gap-2">
                            <span>🔒</span>
                            <span>
                              Você está editando a sua própria conta de Administrador. A Role <strong>ADMIN</strong> e o status <strong>Ativo</strong> estão bloqueados para proteger a governança do sistema.
                            </span>
                          </div>
                        )}

                        <div className="flex justify-end gap-2 pt-4 border-t border-slate-200">
                          <button
                            type="button"
                            onClick={() => setUsuarioModalEdicao(null)}
                            className="px-4 py-2 rounded-lg border border-slate-300 text-xs font-bold text-slate-700 hover:bg-slate-100 transition"
                          >
                            Cancelar
                          </button>
                          <button
                            type="submit"
                            disabled={salvandoEdicao}
                            className="st-btn !py-2 text-xs inline-flex items-center gap-1.5"
                          >
                            {salvandoEdicao ? "Salvando..." : "💾 Salvar Alterações"}
                          </button>
                        </div>
                      </form>
                    </div>
                  </div>
                )}

                {/* =============================================================
                    MODAL 2: 📊 VISUALIZAR CONSUMO DE RECURSOS & MÉTRICAS DE USO
                ============================================================= */}
                {usuarioModalUso && (
                  <div
                    className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto"
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="modal-uso-titulo"
                  >
                    <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-2xl w-full p-6 space-y-5 my-8 animate-in fade-in duration-150">
                      <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                        <div className="flex items-center gap-2">
                          <div className="w-9 h-9 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-700 font-black text-base">
                            📊
                          </div>
                          <div>
                            <h3
                              id="modal-uso-titulo"
                              className="text-base font-extrabold text-[#0F172A]"
                            >
                              Consumo de Recursos & Auditoria de Uso
                            </h3>
                            <p className="text-xs text-slate-500">
                              {usuarioModalUso.nome_completo} ({usuarioModalUso.email})
                            </p>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setUsuarioModalUso(null)}
                          className="text-slate-400 hover:text-slate-700 font-bold p-1 rounded-lg"
                          aria-label="Fechar modal de uso"
                        >
                          ✕
                        </button>
                      </div>

                      {carregandoUsoDetalhado ? (
                        <div className="py-12 text-center text-xs text-slate-500 space-y-2">
                          <div className="animate-spin text-2xl">⏳</div>
                          <div>Carregando métricas analíticas e consumo de cotas...</div>
                        </div>
                      ) : dadosUsoDetalhado ? (
                        <div className="space-y-4">
                          {/* Banner de Plano e Tenant */}
                          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-bold text-slate-700">Plano Ativo:</span>
                              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-black bg-[#E30000] text-white uppercase tracking-wider">
                                {dadosUsoDetalhado.plano.toUpperCase()}
                              </span>
                            </div>
                            <div className="text-xs text-slate-600 font-medium">
                              Organização: <strong>{dadosUsoDetalhado.tenant_nome}</strong>
                            </div>
                          </div>

                          {/* 4 Cards de Métricas */}
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {/* Card 1: Simulações de Cenários */}
                            <div className="p-3.5 rounded-xl border border-slate-200 bg-white shadow-sm space-y-1.5">
                              <div className="flex items-center justify-between text-xs text-slate-600">
                                <span className="font-bold flex items-center gap-1.5">
                                  <span>🎲</span> Simulações de Monte Carlo
                                </span>
                                <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                                  Ilimitadas
                                </span>
                              </div>
                              <div className="text-2xl font-black text-slate-900">
                                {dadosUsoDetalhado.consumo.simulacoes_executadas}
                              </div>
                              <p className="text-[10px] text-slate-500">
                                Total de rodadas de estresse financeiro executadas na base.
                              </p>
                            </div>

                            {/* Card 2: Análises de IA */}
                            <div className="p-3.5 rounded-xl border border-slate-200 bg-white shadow-sm space-y-1.5">
                              <div className="flex items-center justify-between text-xs text-slate-600">
                                <span className="font-bold flex items-center gap-1.5">
                                  <span>✨</span> Pareceres IA (Gemini / Copiloto)
                                </span>
                                <span className="text-[11px] font-black text-slate-800">
                                  {dadosUsoDetalhado.consumo.analises_ia_mes} / {dadosUsoDetalhado.limites.limite_analises_ia_mes}
                                </span>
                              </div>
                              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                                <div
                                  className="h-2 rounded-full transition-all bg-[#E30000]"
                                  style={{
                                    width: `${Math.min(
                                      100,
                                      Math.round(
                                        (dadosUsoDetalhado.consumo.analises_ia_mes /
                                          (dadosUsoDetalhado.limites.limite_analises_ia_mes || 1)) *
                                          100
                                      )
                                    )}%`,
                                  }}
                                />
                              </div>
                              <div className="flex justify-between items-center text-[10px] text-slate-500 pt-0.5">
                                <span>Custo Acumulado IA:</span>
                                <span className="font-bold text-slate-800">
                                  US$ {dadosUsoDetalhado.consumo.custo_acumulado_ia_usd.toFixed(4)}
                                </span>
                              </div>
                            </div>

                            {/* Card 3: Relatórios PDF */}
                            <div className="p-3.5 rounded-xl border border-slate-200 bg-white shadow-sm space-y-1.5">
                              <div className="flex items-center justify-between text-xs text-slate-600">
                                <span className="font-bold flex items-center gap-1.5">
                                  <span>📄</span> Dossiês Executivos PDF
                                </span>
                                <span className="text-[11px] font-black text-slate-800">
                                  {dadosUsoDetalhado.consumo.relatorios_pdf_mes} / {dadosUsoDetalhado.limites.limite_relatorios_pdf_mes}
                                </span>
                              </div>
                              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                                <div
                                  className="h-2 rounded-full transition-all bg-indigo-600"
                                  style={{
                                    width: `${Math.min(
                                      100,
                                      Math.round(
                                        (dadosUsoDetalhado.consumo.relatorios_pdf_mes /
                                          (dadosUsoDetalhado.limites.limite_relatorios_pdf_mes || 1)) *
                                          100
                                      )
                                    )}%`,
                                  }}
                                />
                              </div>
                              <p className="text-[10px] text-slate-500">
                                Emissões de relatórios auditáveis neste ciclo de faturamento.
                              </p>
                            </div>

                            {/* Card 4: EBTs Cadastradas */}
                            <div className="p-3.5 rounded-xl border border-slate-200 bg-white shadow-sm space-y-1.5">
                              <div className="flex items-center justify-between text-xs text-slate-600">
                                <span className="font-bold flex items-center gap-1.5">
                                  <span>🏢</span> EBTs Cadastradas & Ativas
                                </span>
                                <span className="text-[11px] font-black text-slate-800">
                                  {dadosUsoDetalhado.consumo.ebts_ativas_count} / {dadosUsoDetalhado.limites.limite_ebts_ativas}
                                </span>
                              </div>
                              <div className="text-2xl font-black text-slate-900">
                                {dadosUsoDetalhado.consumo.ebts_ativas_count}{" "}
                                <span className="text-xs font-normal text-slate-500">
                                  de {dadosUsoDetalhado.consumo.ebts_cadastradas_total} cadastradas
                                </span>
                              </div>
                              <p className="text-[10px] text-slate-500">
                                Capacidade máxima de empresas simultâneas do plano.
                              </p>
                            </div>
                          </div>

                          {/* Lista das EBTs do Usuário */}
                          <div className="border border-slate-200 rounded-xl p-3 bg-slate-50/50 space-y-2">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-bold text-slate-700">
                                Empresas de Base Tecnológica Vinculadas:
                              </span>
                              <span className="text-[11px] font-semibold text-slate-500">
                                {dadosUsoDetalhado.ebts.length} registradas
                              </span>
                            </div>

                            {dadosUsoDetalhado.ebts.length === 0 ? (
                              <p className="text-xs text-slate-500 italic py-2">
                                Nenhuma EBT vinculada a este usuário até o momento.
                              </p>
                            ) : (
                              <div className="max-h-40 overflow-y-auto space-y-1.5 pr-1">
                                {dadosUsoDetalhado.ebts.map((ebt) => (
                                  <div
                                    key={ebt.id}
                                    className="flex items-center justify-between bg-white border border-slate-200 rounded-lg px-3 py-2 text-xs"
                                  >
                                    <div>
                                      <div className="font-bold text-slate-900">{ebt.razao_social}</div>
                                      <div className="text-[10px] text-slate-500">
                                        {ebt.setor} • {ebt.estagio}
                                      </div>
                                    </div>
                                    <span
                                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                        ebt.ativa
                                          ? "bg-emerald-100 text-emerald-800"
                                          : "bg-slate-100 text-slate-600"
                                      }`}
                                    >
                                      {ebt.ativa ? "Ativa" : "Inativa"}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      ) : null}

                      <div className="flex justify-end pt-3 border-t border-slate-200">
                        <button
                          type="button"
                          onClick={() => setUsuarioModalUso(null)}
                          className="px-4 py-2 rounded-lg bg-slate-900 text-white hover:bg-black text-xs font-bold transition"
                        >
                          Fechar
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* =============================================================
                    MODAL 3: 💳 MUDAR PLANO DE ASSINATURA
                ============================================================= */}
                {usuarioModalPlano && (
                  <div
                    className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto"
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="modal-plano-titulo"
                  >
                    <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-lg w-full p-6 space-y-4 my-8 animate-in fade-in duration-150">
                      <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                        <div className="flex items-center gap-2">
                          <span className="text-xl">💳</span>
                          <div>
                            <h3
                              id="modal-plano-titulo"
                              className="text-base font-extrabold text-[#0F172A]"
                            >
                              Alterar Plano do Assinante
                            </h3>
                            <p className="text-xs text-slate-500">
                              {usuarioModalPlano.nome_completo} ({usuarioModalPlano.email})
                            </p>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setUsuarioModalPlano(null)}
                          className="text-slate-400 hover:text-slate-700 font-bold p-1 rounded-lg"
                          aria-label="Fechar modal de plano"
                        >
                          ✕
                        </button>
                      </div>

                      <div className="space-y-3">
                        <p className="text-xs text-slate-600">
                          Selecione o novo tier de assinatura para conceder cotas ampliadas de simulações, pareceres de IA e relatórios executivos:
                        </p>

                        <div className="space-y-2">
                          {[
                            {
                              cod: "free" as PlanoCodigo,
                              nome: "FREE TIER",
                              badge: "Gratuito",
                              desc: "1 EBT Ativa • 5 Análises IA/mês • 3 Relatórios PDF • Modelos Determinísticos & Gemini Flash",
                            },
                            {
                              cod: "starter" as PlanoCodigo,
                              nome: "STARTER",
                              badge: "Essencial",
                              desc: "3 EBTs Ativas • 20 Análises IA/mês • 10 Relatórios PDF • Gemini 2.5 Flash",
                            },
                            {
                              cod: "pro" as PlanoCodigo,
                              nome: "PRO",
                              badge: "Mais Popular",
                              desc: "10 EBTs Ativas • 100 Análises IA/mês • Relatórios Ilimitados • Gemini 2.5 Pro + Flash",
                            },
                            {
                              cod: "enterprise" as PlanoCodigo,
                              nome: "ENTERPRISE",
                              badge: "Corporativo",
                              desc: "EBTs Ilimitadas • IA Dedicada Ilimitada • Suporte Prioritário & Auditoria VC Personalizada",
                            },
                          ].map((p) => {
                            const selecionado = novoPlanoSelecionado === p.cod;
                            const ehAtual = usuarioModalPlano.plano_codigo === p.cod;
                            return (
                              <label
                                key={p.cod}
                                className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition ${
                                  selecionado
                                    ? "border-[#E30000] bg-red-50/50 shadow-sm"
                                    : "border-slate-200 hover:border-slate-300 bg-white"
                                }`}
                              >
                                <input
                                  type="radio"
                                  name="plano_selecionado"
                                  className="mt-1"
                                  checked={selecionado}
                                  onChange={() => setNovoPlanoSelecionado(p.cod)}
                                />
                                <div className="flex-1 text-xs">
                                  <div className="flex items-center gap-2">
                                    <span className="font-extrabold text-slate-900">{p.nome}</span>
                                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700">
                                      {p.badge}
                                    </span>
                                    {ehAtual && (
                                      <span className="px-1.5 py-0.5 rounded text-[9px] font-black bg-blue-100 text-blue-800">
                                        Atual
                                      </span>
                                    )}
                                  </div>
                                  <p className="text-slate-500 mt-0.5 text-[11px] leading-relaxed">
                                    {p.desc}
                                  </p>
                                </div>
                              </label>
                            );
                          })}
                        </div>
                      </div>

                      <div className="flex justify-end gap-2 pt-4 border-t border-slate-200">
                        <button
                          type="button"
                          onClick={() => setUsuarioModalPlano(null)}
                          className="px-4 py-2 rounded-lg border border-slate-300 text-xs font-bold text-slate-700 hover:bg-slate-100 transition"
                        >
                          Cancelar
                        </button>
                        <button
                          type="button"
                          disabled={salvandoPlano || novoPlanoSelecionado === usuarioModalPlano.plano_codigo}
                          onClick={handleSalvarMudancaPlano}
                          className="st-btn !py-2 text-xs"
                        >
                          {salvandoPlano ? "Atualizando..." : "💳 Confirmar Alteração de Plano"}
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* =============================================================
                    MODAL 4: 🗑️ CONFIRMAR EXCLUSÃO DEFINITIVA DE CONTA
                ============================================================= */}
                {usuarioModalExclusao && (
                  <div
                    className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto"
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="modal-exclusao-titulo"
                  >
                    <div className="bg-white rounded-2xl shadow-2xl border border-red-200 max-w-md w-full p-6 space-y-4 my-8 animate-in fade-in duration-150">
                      <div className="flex items-center gap-3 text-red-600">
                        <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center text-xl font-black">
                          ⚠️
                        </div>
                        <div>
                          <h3
                            id="modal-exclusao-titulo"
                            className="text-base font-extrabold text-[#0F172A]"
                          >
                            Excluir Conta Definitivamente?
                          </h3>
                          <p className="text-xs text-red-700 font-semibold">
                            Ação irreversível de segurança
                          </p>
                        </div>
                      </div>

                      <div className="p-3 bg-red-50/70 border border-red-200 rounded-xl space-y-2 text-xs text-slate-700">
                        <p>
                          Você está prestes a desativar e excluir do banco de dados o cadastro de:
                        </p>
                        <div className="bg-white p-2.5 rounded-lg border border-red-200 space-y-1">
                          <div className="font-bold text-slate-900">
                            {usuarioModalExclusao.nome_completo}
                          </div>
                          <div className="text-slate-600">
                            E-mail: <strong>{usuarioModalExclusao.email}</strong>
                          </div>
                          <div className="text-slate-600">
                            Papel: <strong>{usuarioModalExclusao.papel.toUpperCase()}</strong> | Plano: <strong>{usuarioModalExclusao.plano_codigo.toUpperCase()}</strong>
                          </div>
                        </div>
                        <p className="text-[11px] text-red-700 font-medium">
                          Todos os vínculos de sessão, credenciais de login e associações organizacionais deste usuário serão revogados imediatamente.
                        </p>
                      </div>

                      <div className="flex justify-end gap-2 pt-3 border-t border-slate-200">
                        <button
                          type="button"
                          onClick={() => setUsuarioModalExclusao(null)}
                          className="px-4 py-2 rounded-lg border border-slate-300 text-xs font-bold text-slate-700 hover:bg-slate-100 transition"
                        >
                          Cancelar
                        </button>
                        <button
                          type="button"
                          disabled={executandoExclusao}
                          onClick={handleConfirmarExclusaoUsuario}
                          className="px-4 py-2 rounded-lg bg-[#E30000] text-white hover:bg-[#C00000] text-xs font-extrabold shadow-sm transition inline-flex items-center gap-1.5 focus:outline-none focus:ring-2 focus:ring-[#E30000]"
                        >
                          {executandoExclusao ? "Excluindo..." : "🗑️ Sim, Excluir Registro"}
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* =============================================================
                    MODAL DE FILA DE PERSISTÊNCIA OFFLINE / OUTBOX IA
                ============================================================= */}
                {mostrarModalOutbox && (
                  <div
                    className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto font-executive"
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="modal-outbox-titulo"
                  >
                    <div className="bg-[#121212] border border-[#27272A] rounded-2xl max-w-2xl w-full text-white shadow-2xl p-6 space-y-4 my-8 animate-in fade-in">
                      <div className="flex items-center justify-between border-b border-[#27272A] pb-3">
                        <div className="flex items-center gap-2">
                          <div className="w-9 h-9 rounded-xl bg-red-950 border border-[#E30000] flex items-center justify-center text-[#E30000] font-black text-base">
                            📡
                          </div>
                          <div>
                            <h3
                              id="modal-outbox-titulo"
                              className="text-base font-extrabold text-white"
                            >
                              Fila de Persistência Offline — Solicitações de IA
                            </h3>
                            <p className="text-xs text-slate-400">
                              Gerenciamento de solicitações armazenadas localmente em caso de instabilidade na API.
                            </p>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setMostrarModalOutbox(false)}
                          className="text-slate-400 hover:text-white font-bold p-1 rounded-lg"
                          aria-label="Fechar modal de outbox"
                        >
                          ✕
                        </button>
                      </div>

                      {pendenciasOutbox.length === 0 ? (
                        <div className="py-8 text-center text-xs text-slate-400">
                          <p>Nenhuma solicitação pendente no armazenamento local.</p>
                        </div>
                      ) : (
                        <div className="space-y-2.5 max-h-80 overflow-y-auto pr-1">
                          {pendenciasOutbox.map((p) => (
                            <div
                              key={p.id}
                              className="p-3 bg-[#1A1A1A] border border-[#27272A] rounded-xl flex flex-wrap items-center justify-between gap-3 text-xs"
                            >
                              <div className="space-y-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="font-extrabold text-white">
                                    {p.ebt_nome}
                                  </span>
                                  <span className="px-2 py-0.5 rounded bg-red-950 text-red-300 border border-red-800 text-[10px] font-bold uppercase">
                                    {p.codigo_erro}
                                  </span>
                                  <span className="text-[10px] text-slate-400">
                                    {new Date(p.timestamp).toLocaleTimeString(
                                      "pt-BR"
                                    )}
                                  </span>
                                </div>
                                <p className="text-[11px] text-slate-300 leading-tight">
                                  {p.mensagem_erro}
                                </p>
                                <div className="text-[10px] text-slate-400">
                                  Modelo:{" "}
                                  <span className="font-bold text-white">
                                    {p.modelo_gemini}
                                  </span>{" "}
                                  • EBT ID: <code>{p.ebt_id}</code>
                                </div>
                              </div>

                              <div className="flex items-center gap-2">
                                <button
                                  type="button"
                                  onClick={() =>
                                    handleRemoverPendenciaOutbox(p.id)
                                  }
                                  className="px-2.5 py-1.5 rounded-lg border border-[#3F3F46] bg-[#27272A] hover:bg-[#3F3F46] text-slate-300 text-xs font-semibold transition"
                                  title="Remover esta solicitação da fila"
                                >
                                  Descartar
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-[#27272A]">
                        <div>
                          {pendenciasOutbox.length > 0 && (
                            <button
                              type="button"
                              onClick={handleLimparOutboxCompleto}
                              className="text-xs text-red-400 hover:text-red-300 underline font-semibold"
                            >
                              Limpar toda a fila
                            </button>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => setMostrarModalOutbox(false)}
                            className="px-4 py-2 rounded-lg border border-[#3F3F46] text-xs font-bold text-slate-300 hover:bg-[#27272A] transition"
                          >
                            Fechar
                          </button>
                          {pendenciasOutbox.length > 0 && (
                            <button
                              type="button"
                              disabled={sincronizandoOutbox}
                              onClick={handleSincronizarPendenciasOutbox}
                              className="st-btn !py-2 text-xs inline-flex items-center gap-1.5"
                            >
                              <span>{sincronizandoOutbox ? "⏳" : "🔄"}</span>
                              <span>
                                {sincronizandoOutbox
                                  ? "Sincronizando..."
                                  : "Sincronizar Todas"}
                              </span>
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </section>
        )}

        {/* ===================================================================
            ABA 14: 👤 MEU PERFIL (DADOS DO USUÁRIO, AVATAR, RBAC E SENHA)
            Acessível para qualquer usuário autenticado.
        =================================================================== */}
        {abaAtiva === "meu_perfil" && (
          <section className="space-y-4">
            <div>
              <h2 className="text-xl font-extrabold text-[#0F172A]">
                👤 Meu Perfil — Dados da Conta, Credenciais e Assinatura
              </h2>
              <p className="text-xs text-slate-600 mt-0.5">
                Gerencie suas informações pessoais, foto de perfil, contato
                profissional e credenciais de segurança.
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
              {/* Coluna Esquerda: Resumo Visual do Perfil, Papel RBAC e Plano */}
              <div className="st-card flex flex-col items-center text-center space-y-3">
                {formMeuPerfil.avatar_url ? (
                  <img
                    src={formMeuPerfil.avatar_url}
                    alt={formMeuPerfil.nome_completo}
                    className="w-24 h-24 rounded-full object-cover border-4 border-[#E30000] shadow-md"
                  />
                ) : (
                  <div className="w-24 h-24 rounded-full bg-[#E30000] text-white font-black text-2xl flex items-center justify-center shadow-md">
                    {obterIniciais(formMeuPerfil.nome_completo)}
                  </div>
                )}

                <div>
                  <h3 className="text-base font-extrabold text-[#0F172A]">
                    {formMeuPerfil.nome_completo || sessao.user.nome_completo}
                  </h3>
                  <p className="text-xs text-slate-500">
                    {formMeuPerfil.email || sessao.user.email}
                  </p>
                  {(formMeuPerfil.cargo_organizacao ||
                    sessao.user.cargo_organizacao) && (
                    <p className="text-xs font-semibold text-[#E30000] mt-1">
                      {formMeuPerfil.cargo_organizacao ||
                        sessao.user.cargo_organizacao}
                    </p>
                  )}
                </div>

                {/* Exibição Somente Leitura do Papel RBAC e Plano Atual */}
                <div className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-left space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500 font-semibold">
                      Papel RBAC Atual:
                    </span>
                    <span className="px-2.5 py-0.5 rounded-full bg-[#E30000] text-white font-bold uppercase text-[11px]">
                      {sessao.membership_ativa.papel}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500 font-semibold">
                      Plano de Assinatura:
                    </span>
                    <span className="px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-900 font-bold uppercase text-[11px]">
                      {sessao.tenant.plano_codigo}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500 font-semibold">
                      Status da Conta:
                    </span>
                    <span className="px-2.5 py-0.5 rounded-full bg-emerald-50 border border-emerald-300 text-emerald-800 font-bold text-[11px]">
                      ● Ativo
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500 font-semibold">
                      Organização / Tenant:
                    </span>
                    <span className="font-bold text-slate-800 truncate max-w-[150px]">
                      {sessao.tenant.nome}
                    </span>
                  </div>
                </div>

                {/* Seletor Rápido de Avatares ou Upload */}
                <div className="w-full text-left space-y-2 pt-1">
                  <label className="block text-[11px] font-bold text-slate-600">
                    Escolher Avatar Executivo ou Enviar Foto:
                  </label>
                  <div className="flex items-center gap-2">
                    {AVATARES_SUGERIDOS.map((url, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() =>
                          setFormMeuPerfil({
                            ...formMeuPerfil,
                            avatar_url: url,
                          })
                        }
                        className={`rounded-full p-0.5 border-2 transition ${
                          formMeuPerfil.avatar_url === url
                            ? "border-[#E30000] scale-105"
                            : "border-transparent hover:border-slate-300"
                        }`}
                      >
                        <img
                          src={url}
                          alt={`Avatar ${idx + 1}`}
                          className="w-9 h-9 rounded-full object-cover"
                        />
                      </button>
                    ))}
                  </div>
                  <div className="pt-1">
                    <label className="inline-block w-full text-center py-1.5 px-3 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-lg text-xs cursor-pointer transition">
                      📷 Enviar Foto do Computador
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleUploadAvatarArquivo}
                        className="hidden"
                      />
                    </label>
                  </div>
                </div>
              </div>

              {/* Coluna Direita (2 cols): Formulário Completo de Dados e Senha */}
              <form
                onSubmit={handleSalvarMeuPerfil}
                className="st-card lg:col-span-2 space-y-4"
              >
                <h3 className="text-sm font-extrabold text-[#0F172A] border-b border-slate-200 pb-2">
                  📋 Dados Cadastrais do Usuário
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      Nome Completo *
                    </label>
                    <input
                      type="text"
                      required
                      className="st-input text-xs"
                      value={formMeuPerfil.nome_completo}
                      onChange={(e) =>
                        setFormMeuPerfil({
                          ...formMeuPerfil,
                          nome_completo: e.target.value,
                        })
                      }
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      E-mail *
                    </label>
                    <input
                      type="email"
                      required
                      className="st-input text-xs"
                      value={formMeuPerfil.email}
                      onChange={(e) =>
                        setFormMeuPerfil({
                          ...formMeuPerfil,
                          email: e.target.value,
                        })
                      }
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      Telefone / WhatsApp
                    </label>
                    <input
                      type="text"
                      placeholder="(11) 99999-9999"
                      className="st-input text-xs"
                      value={formMeuPerfil.telefone_whatsapp}
                      onChange={(e) =>
                        setFormMeuPerfil({
                          ...formMeuPerfil,
                          telefone_whatsapp: e.target.value,
                        })
                      }
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      Cargo / Organização
                    </label>
                    <input
                      type="text"
                      placeholder="Ex: Diretor Executivo / Venture Capital"
                      className="st-input text-xs"
                      value={formMeuPerfil.cargo_organizacao}
                      onChange={(e) =>
                        setFormMeuPerfil({
                          ...formMeuPerfil,
                          cargo_organizacao: e.target.value,
                        })
                      }
                    />
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-xs font-bold text-slate-700 mb-1">
                      URL da Foto de Perfil / Avatar
                    </label>
                    <input
                      type="text"
                      placeholder="https://exemplo.com/minha-foto.jpg"
                      className="st-input text-xs"
                      value={formMeuPerfil.avatar_url}
                      onChange={(e) =>
                        setFormMeuPerfil({
                          ...formMeuPerfil,
                          avatar_url: e.target.value,
                        })
                      }
                    />
                  </div>
                </div>

                {/* Campos Somente Leitura de Papel RBAC e Plano */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                  <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1">
                      Papel RBAC (Somente Leitura)
                    </label>
                    <input
                      type="text"
                      readOnly
                      disabled
                      className="st-input text-xs bg-slate-100 text-slate-700 font-bold uppercase cursor-not-allowed"
                      value={sessao.membership_ativa.papel}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1">
                      Plano Atual (Somente Leitura)
                    </label>
                    <input
                      type="text"
                      readOnly
                      disabled
                      className="st-input text-xs bg-slate-100 text-slate-700 font-bold uppercase cursor-not-allowed"
                      value={sessao.tenant.plano_codigo}
                    />
                  </div>
                </div>

                {/* Seção de Alteração de Senha */}
                <div className="pt-3 border-t border-slate-200 space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-extrabold text-[#0F172A]">
                      🔑 Alteração de Senha (Opcional)
                    </h4>
                    <button
                      type="button"
                      onClick={() => setMostrarSenhaPerfil((v) => !v)}
                      className="text-xs font-bold text-[#E30000] hover:underline"
                    >
                      {mostrarSenhaPerfil
                        ? "🙈 Ocultar senhas"
                        : "👁️ Visualizar senhas"}
                    </button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">
                        Senha Atual
                      </label>
                      <input
                        type={mostrarSenhaPerfil ? "text" : "password"}
                        autoComplete="current-password"
                        placeholder="Informe a senha atual"
                        className="st-input text-xs"
                        value={formMeuPerfil.senha_atual}
                        onChange={(e) =>
                          setFormMeuPerfil({
                            ...formMeuPerfil,
                            senha_atual: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">
                        Nova Senha
                      </label>
                      <input
                        type={mostrarSenhaPerfil ? "text" : "password"}
                        autoComplete="new-password"
                        placeholder="Mínimo 6 caracteres"
                        className="st-input text-xs"
                        value={formMeuPerfil.nova_senha}
                        onChange={(e) =>
                          setFormMeuPerfil({
                            ...formMeuPerfil,
                            nova_senha: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">
                        Confirmar Nova Senha
                      </label>
                      <input
                        type={mostrarSenhaPerfil ? "text" : "password"}
                        autoComplete="new-password"
                        placeholder="Repita a nova senha"
                        className="st-input text-xs"
                        value={formMeuPerfil.confirmar_nova_senha}
                        onChange={(e) =>
                          setFormMeuPerfil({
                            ...formMeuPerfil,
                            confirmar_nova_senha: e.target.value,
                          })
                        }
                      />
                    </div>
                  </div>
                </div>

                <div className="pt-2 flex justify-end">
                  <button
                    type="submit"
                    disabled={salvandoPerfil}
                    className="st-btn px-6 flex items-center gap-2 disabled:opacity-60"
                  >
                    {salvandoPerfil
                      ? "⏳ Salvando alterações..."
                      : "💾 Salvar Alterações"}
                  </button>
                </div>
              </form>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
