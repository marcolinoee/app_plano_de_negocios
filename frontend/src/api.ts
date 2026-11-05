import {
  PapelRBAC,
  PlanoCodigo,
  SessaoAutenticada,
  UsuarioOAuthRegistrado,
  WorkspaceEBTCompleto,
  WorkspaceEBTResumo,
} from "./types";

const API_BASE =
  (import.meta as unknown as { env?: { VITE_API_BASE_URL?: string } }).env
    ?.VITE_API_BASE_URL || "/v1";

const TOKEN_STORAGE_KEY = "mm_saas_jwt_token";

export function obterTokenSalvo(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function salvarToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function limparToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

async function requisicao<T>(
  caminho: string,
  opcoes: RequestInit = {}
): Promise<T> {
  const token = obterTokenSalvo();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((opcoes.headers as Record<string, string>) || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const resp = await fetch(`${API_BASE}${caminho}`, {
    ...opcoes,
    headers,
  });

  if (!resp.ok) {
    let detalhe = `Erro HTTP ${resp.status}`;
    try {
      const jsonErro = await resp.json();
      detalhe = jsonErro.detail || JSON.stringify(jsonErro);
    } catch {
      detalhe = await resp.text();
    }
    throw new Error(detalhe);
  }

  return resp.json() as Promise<T>;
}

export const api = {
  loginCredenciais: (dados: { email: string; senha: string }) =>
    requisicao<SessaoAutenticada>("/auth/login", {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  registrarUsuario: (dados: {
    nome_completo: string;
    email: string;
    senha: string;
    telefone_whatsapp?: string;
    cargo_organizacao?: string;
  }) =>
    requisicao<SessaoAutenticada>("/auth/register", {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  atualizarMeuPerfil: (dados: {
    nome_completo?: string;
    email?: string;
    telefone_whatsapp?: string;
    cargo_organizacao?: string;
    avatar_url?: string;
    senha_atual?: string;
    nova_senha?: string;
  }) =>
    requisicao<SessaoAutenticada>("/auth/profile", {
      method: "PUT",
      body: JSON.stringify(dados),
    }),

  listarUsuariosRBAC: () =>
    requisicao<UsuarioOAuthRegistrado[]>("/admin/usuarios"),

  criarUsuarioPeloAdmin: (dados: {
    nome_completo: string;
    email: string;
    senha: string;
    papel: PapelRBAC;
    plano: PlanoCodigo;
    cargo_organizacao?: string;
    telefone_whatsapp?: string;
  }) =>
    requisicao<{
      membership_id: string;
      user_id: string;
      email: string;
      nome_completo: string;
      papel: PapelRBAC;
      ativo: boolean;
      plano_codigo: PlanoCodigo;
    }>("/admin/usuarios", {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  obterProvedoresOAuth: () =>
    requisicao<{
      provedores: Array<{
        id: string;
        nome: string;
        configurado: boolean;
        authorize_url?: string | null;
      }>;
      papeis_rbac: PapelRBAC[];
      existe_admin_oauth: boolean;
      usuarios_oauth_registrados: UsuarioOAuthRegistrado[];
      tenants_disponiveis: Array<{ id: string; nome: string; slug: string }>;
    }>("/auth/providers"),

  autenticarOAuth: (dados: {
    email: string;
    nome: string;
    provedor: string;
    invite_token?: string;
    tenant_id?: string;
  }) =>
    requisicao<SessaoAutenticada>("/auth/sandbox-rbac", {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  obterSessaoAtual: () => requisicao<SessaoAutenticada>("/auth/me"),

  alternarMembership: (dados: {
    membership_id?: string;
    tenant_id?: string;
    papel?: PapelRBAC;
  }) =>
    requisicao<SessaoAutenticada>("/auth/switch-membership", {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  criarConviteRBAC: (dados: {
    email_convidado: string;
    papel: PapelRBAC;
    ebt_restrita_id?: string | null;
    dias_validade?: number;
  }) =>
    requisicao<{
      convite_id: string;
      email_convidado: string;
      papel: PapelRBAC;
      ebt_restrita_id?: string | null;
      invite_token: string;
      oauth_invite_url: string;
      expira_em: string;
    }>("/auth/convites-rbac", {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  gerenciarAssinanteOAuthPeloAdmin: (
    membershipId: string,
    dados: {
      novo_papel?: PapelRBAC;
      novo_plano?: PlanoCodigo;
      ebt_restrita_id?: string | null;
      ativo?: boolean;
      nome_completo?: string;
      cargo_organizacao?: string;
      telefone_whatsapp?: string;
    }
  ) =>
    requisicao<{
      membership_id: string;
      user_id: string;
      email: string;
      nome_completo: string;
      papel: PapelRBAC;
      ativo?: boolean;
      ebt_restrita_id?: string | null;
      tenant_id: string;
      plano_codigo: PlanoCodigo;
    }>(`/admin/assinantes-oauth/${membershipId}`, {
      method: "PUT",
      body: JSON.stringify(dados),
    }),

  listarTenants: () =>
    requisicao<
      Array<{ id: string; nome: string; slug: string; plano_codigo: PlanoCodigo }>
    >("/tenants"),

  criarTenant: (dados: {
    nome_consultoria: string;
    slug: string;
    email_dono: string;
    nome_dono: string;
    plano: PlanoCodigo;
  }) =>
    requisicao<{
      tenant_id: string;
      slug: string;
      owner_user_id: string;
      membership_id: string;
      plano: string;
    }>("/tenants", {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  alterarPlanoTenant: (plano: PlanoCodigo) =>
    requisicao<{
      plano_codigo: PlanoCodigo;
      limite_ebts: number;
      limite_analises_ia_mes: number;
      limite_pdfs_mes: number;
      permite_monte_carlo: boolean;
      permite_white_label: boolean;
    }>("/tenants/plano", {
      method: "PATCH",
      body: JSON.stringify({ plano }),
    }),

  listarEBTs: () => requisicao<WorkspaceEBTResumo[]>("/ebts"),

  criarEBT: (dados: {
    nome_startup: string;
    setor_vertical?: string;
    estagio?: string;
  }) =>
    requisicao<WorkspaceEBTResumo>("/ebts", {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  renomearEBT: (ebtId: string, nome_startup: string) =>
    requisicao<WorkspaceEBTResumo>(`/ebts/${ebtId}`, {
      method: "PATCH",
      body: JSON.stringify({ nome_startup }),
    }),

  excluirEBT: (ebtId: string) =>
    requisicao<{ status: string }>(`/ebts/${ebtId}`, {
      method: "DELETE",
    }),

  obterEBTCompleto: (ebtId: string) =>
    requisicao<WorkspaceEBTCompleto>(`/ebts/${ebtId}/completo`),

  atualizarLeanCanvas: (
    ebtId: string,
    dados: WorkspaceEBTCompleto["lean_canvas"]
  ) =>
    requisicao<{ status: string }>(`/ebts/${ebtId}/lean-canvas`, {
      method: "PUT",
      body: JSON.stringify(dados),
    }),

  atualizarPremissas: (
    ebtId: string,
    dados: WorkspaceEBTCompleto["premissas"]
  ) =>
    requisicao<{ status: string }>(`/ebts/${ebtId}/premissas`, {
      method: "PUT",
      body: JSON.stringify(dados),
    }),

  adicionarCapex: (
    ebtId: string,
    dados: { categoria: string; descricao: string; valor: number }
  ) =>
    requisicao<{ id: string; status: string }>(`/ebts/${ebtId}/capex`, {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  excluirCapex: (ebtId: string, itemId: string) =>
    requisicao<{ status: string }>(`/ebts/${ebtId}/capex/${itemId}`, {
      method: "DELETE",
    }),

  adicionarOpex: (
    ebtId: string,
    dados: { categoria: string; descricao: string; valor_mensal: number }
  ) =>
    requisicao<{ id: string; status: string }>(`/ebts/${ebtId}/opex`, {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  excluirOpex: (ebtId: string, itemId: string) =>
    requisicao<{ status: string }>(`/ebts/${ebtId}/opex/${itemId}`, {
      method: "DELETE",
    }),

  adicionarPlanoSaaS: (
    ebtId: string,
    dados: {
      nome_plano: string;
      ticket_mensal: number;
      usuarios_ativos_base: number;
      taxas_pagamento_pct: number;
      impostos_pct: number;
      custo_servidor_por_usuario: number;
    }
  ) =>
    requisicao<{ id: string; status: string }>(`/ebts/${ebtId}/planos-saas`, {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  excluirPlanoSaaS: (ebtId: string, planoId: string) =>
    requisicao<{ status: string }>(`/ebts/${ebtId}/planos-saas/${planoId}`, {
      method: "DELETE",
    }),

  atualizarJuridico: (
    ebtId: string,
    dados: WorkspaceEBTCompleto["juridico"]
  ) =>
    requisicao<{ status: string }>(`/ebts/${ebtId}/juridico`, {
      method: "PUT",
      body: JSON.stringify(dados),
    }),

  executarSimulacaoVersionada: (ebtId: string) =>
    requisicao<{
      versao_numero: number;
      hash_entrada: string;
      resultado_id: string;
    }>(`/ebts/${ebtId}/simular`, { method: "POST" }),

  executarMonteCarlo: (ebtId: string) =>
    requisicao<{
      iteracoes: number;
      vpl_medio: number;
      vpl_mediana_p50: number;
      vpl_p10_pessimista: number;
      vpl_p90_otimista: number;
      probabilidade_vpl_positivo_pct: number;
      probabilidade_quebra_caixa_pct: number;
    }>(`/ebts/${ebtId}/monte-carlo`, { method: "POST" }),

  solicitarParecerIA: (
    ebtId: string,
    dados: {
      usar_gemini: boolean;
      gemini_api_key?: string;
      forcar_regeneracao: boolean;
    }
  ) =>
    requisicao<{
      id: string;
      parecer_gerado_md: string;
      parecer_revisado_consultor_md?: string | null;
      aprovado_pelo_consultor: boolean;
      em_cache: boolean;
    }>(`/ebts/${ebtId}/ia/parecer`, {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  homologarParecerIA: (analiseId: string, texto_revisado_md: string) =>
    requisicao<{
      id: string;
      aprovado_pelo_consultor: boolean;
      parecer_revisado_consultor_md: string;
    }>(`/ia/${analiseId}/homologar`, {
      method: "POST",
      body: JSON.stringify({ texto_revisado_md }),
    }),

  emitirDossiePDF: (
    ebtId: string,
    dados: {
      exigir_parecer_aprovado: boolean;
      parecer_customizado_md?: string;
    }
  ) =>
    requisicao<{
      id: string;
      storage_key: string;
      sha256_pdf: string;
      url_assinada: string;
      pdf_base64?: string | null;
    }>(`/ebts/${ebtId}/dossie-pdf`, {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  obterPainelGovernanca: () =>
    requisicao<{
      assinatura: {
        plano_codigo: PlanoCodigo;
        status: string;
        limite_ebts: number;
        limite_analises_ia_mes: number;
        limite_pdfs_mes: number;
        permite_monte_carlo: boolean;
        permite_white_label: boolean;
      };
      usuarios_oauth_registrados?: UsuarioOAuthRegistrado[];
      uso_mensal: {
        ano_mes: string;
        ebts_ativas: number;
        simulacoes_executadas: number;
        analises_ia_realizadas: number;
        pdfs_gerados: number;
        custo_ia_acumulado_usd: number;
      };
      jobs_assincronos: Array<{
        id: string;
        tipo_job: string;
        status: string;
        progresso_pct: number;
        criado_em?: string | null;
      }>;
      dossies_emitidos: Array<{
        id: string;
        sha256_pdf: string;
        storage_key: string;
        criado_em?: string | null;
      }>;
      convites_rbac: Array<{
        id: string;
        email_convidado: string;
        papel: PapelRBAC;
        ebt_restrita_id?: string | null;
        aceito: boolean;
        expira_em?: string | null;
      }>;
      audit_logs: Array<{
        id: string;
        acao: string;
        entidade_tipo: string;
        resumo: string;
        user_id?: string | null;
        criado_em?: string | null;
      }>;
      ddl_rls_postgresql: string;
    }>("/governanca/painel"),

  criarShareLink: (ebtId: string, dias_validade: number = 7) =>
    requisicao<{ id: string; token: string; expira_em: string }>(
      `/ebts/${ebtId}/share-links`,
      {
        method: "POST",
        body: JSON.stringify({ dias_validade }),
      }
    ),

  validarShareLink: (token: string) =>
    requisicao<{
      valido: boolean;
      ebt_id: string;
      tenant_id: string;
      acessos_realizados: number;
      expira_em: string;
    }>(`/share-links/validar`, {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
};
