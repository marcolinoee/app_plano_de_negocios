export type PapelRBAC =
  | "dono"
  | "admin"
  | "gestor"
  | "consultor"
  | "analista"
  | "assinante_free"
  | "assinante_pro"
  | "fundador"
  | "investidor";

export type PlanoCodigo = "free" | "starter" | "pro" | "enterprise";

export interface PerfilRBACOAuth {
  membership_id: string;
  user_id: string;
  tenant_id: string;
  tenant_nome: string;
  plano_codigo: PlanoCodigo;
  email: string;
  nome: string;
  provedor_oauth: string;
  papel: PapelRBAC;
  ativo?: boolean;
  ebt_restrita_id?: string | null;
}

export interface SessaoAutenticada {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    email: string;
    nome_completo: string;
    telefone_whatsapp?: string;
    cargo_organizacao?: string;
    avatar_url?: string;
    ativo?: boolean;
    provedor_auth?: string | null;
    provedor_auth_sub?: string | null;
  };
  tenant: {
    id: string;
    nome: string;
    slug: string;
    plano_codigo: PlanoCodigo;
    limite_ebts: number;
    limite_analises_ia_mes: number;
    limite_pdfs_mes: number;
    permite_monte_carlo: boolean;
    permite_white_label: boolean;
  };
  membership_ativa: {
    id: string;
    papel: PapelRBAC;
    ativo?: boolean;
    ebt_restrita_id?: string | null;
    permissoes: string[];
  };
  perfis_rbac_tenant: PerfilRBACOAuth[];
}

export interface UsuarioOAuthRegistrado {
  user_id: string;
  membership_id: string;
  email: string;
  nome_completo: string;
  telefone_whatsapp?: string;
  cargo_organizacao?: string;
  avatar_url?: string;
  ativo?: boolean;
  provedor_auth_sub?: string | null;
  provedor: string;
  papel: PapelRBAC;
  ebt_restrita_id?: string | null;
  tenant_id: string;
  tenant_nome: string;
  tenant_slug: string;
  plano_codigo: PlanoCodigo;
  ebts_disponiveis: Array<{ id: string; nome_startup: string }>;
  consumo_uso?: {
    simulacoes_executadas: number;
    analises_ia_realizadas: number;
    pdfs_gerados: number;
    custo_ia_usd: number;
    total_ebts: number;
    limite_ebts: number;
    limite_analises_ia_mes: number;
    limite_pdfs_mes: number;
    ano_mes: string;
  };
  criado_em?: string | null;
}

export interface UsoUsuarioDetalhado {
  user_id: string;
  membership_id: string;
  email: string;
  nome_completo: string;
  papel: PapelRBAC;
  plano_codigo: PlanoCodigo;
  tenant_nome: string;
  ativo: boolean;
  consumo: {
    simulacoes_executadas: number;
    analises_ia_realizadas: number;
    pdfs_gerados: number;
    custo_ia_usd: number;
    ano_mes: string;
  };
  limites: {
    limite_ebts: number;
    limite_analises_ia_mes: number;
    limite_pdfs_mes: number;
    permite_monte_carlo: boolean;
    permite_white_label: boolean;
  };
  ebts: Array<{ id: string; nome_startup: string; ativo: boolean }>;
}

export interface WorkspaceEBTResumo {
  id: string;
  tenant_id: string;
  nome_startup: string;
  setor_vertical: string;
  estagio: string;
}

export interface CenarioSimulado {
  dre_base: {
    mrr_bruto_direto: number;
    mrr_bruto_total: number;
    despesas_deducoes_fiscais_gateway: number;
    mrr_liquido: number;
    despesas_nuvem_cogs: number;
    custo_nuvem_free_tier_mensal?: number;
    opex_fixo_mensal: number;
    burn_rate_total_mensal: number;
    ebitda_mensal: number;
    margem_bruta_pct: number;
    arr_anualizado: number;
  };
  unit_economics: {
    usuarios_pagos_diretos: number;
    usuarios_free_tier_planos?: number;
    conversos_pagantes_freemium: number;
    usuarios_pagantes_totais_base: number;
    ticket_medio_arpu: number;
    ltv_vitalicio_cliente: number;
    cac_estimado: number;
    indice_ltv_cac: number;
    meses_payback_cac?: number | null;
    media_deducao_impostos_pct?: number;
    media_custo_nuvem_rs?: number;
  };
  viabilidade: {
    capex_total: number;
    valor_presente_liquido_vpl: number;
    taxa_interna_retorno_anual_pct?: number | null;
    validade_da_tir: boolean;
    mes_de_breakeven_payback_texto: string;
    meses_runway_sobrevivencia?: number | null;
    capital_necessario_rodada?: number;
  };
  series_temporais: {
    rotulos_meses: string[];
    fluxo_de_caixa_mensal: number[];
    caixa_acumulado: number[];
    usuarios_pagantes: number[];
    usuarios_freemium: number[];
    mrr_mensal: number[];
  };
  alertas: Array<{
    codigo: string;
    severidade: string;
    titulo: string;
    mensagem: string;
    recomendacao: string;
  }>;
  possui_alertas_criticos?: boolean;
  versao_motor?: string;
  hash_entrada?: string;
}

export interface WorkspaceEBTCompleto {
  ebt: WorkspaceEBTResumo;
  lean_canvas: {
    problema: string;
    solucao_mvp: string;
    mvp_descricao: string;
    metricas_chave: string;
    proposta_valor: string;
    vantagem_injusta: string;
    canais: string;
    segmentos: string;
    estrutura_custos: string;
    fontes_receita: string;
    ods_onu: string;
  };
  premissas: {
    horizonte_meses: number;
    tma_anual_pct: number;
    cac_estimado: number;
    churn_mensal_pct: number;
    conversao_freemium_pct: number;
    crescimento_mensal_pct: number;
    usuarios_freemium_base: number;
  };
  investimentos: Array<{
    id: string;
    categoria: string;
    descricao: string;
    valor: number;
  }>;
  custos_fixos: Array<{
    id: string;
    categoria: string;
    descricao: string;
    valor_mensal: number;
  }>;
  planos_saas: Array<{
    id: string;
    nome_plano: string;
    ticket_mensal: number;
    usuarios_ativos_base: number;
    taxas_pagamento_pct: number;
    impostos_pct: number;
    custo_servidor_por_usuario: number;
  }>;
  juridico: {
    registro_inpi: string;
    marca_status: string;
    adequacao_lgpd: boolean;
    contrato_vesting: boolean;
    custo_estimado_legal: number;
  };
  simulacao_base: CenarioSimulado;
  comparativo_cenarios: {
    cenarios: {
      pessimista: CenarioSimulado;
      base: CenarioSimulado;
      otimista: CenarioSimulado;
    };
  };
  versoes_simulacao: Array<{
    id: string;
    numero_versao: number;
    hash_entrada_sha256: string;
    versao_motor: string;
    mrr_bruto_base: number;
    vpl: number;
    ltv_cac: number;
    criado_em?: string | null;
  }>;
  ia_governanca: {
    prompt_anonimizado_preview: string;
    hash_contexto_atual: string;
    ultima_analise?: {
      id: string;
      provedor: string;
      modelo: string;
      modelo_resolvido?: string;
      tentativas_executadas?: number;
      geracao_resolvida?: string;
      versao_prompt: string;
      hash_entrada_simulacao: string;
      parecer_gerado_md: string;
      parecer_revisado_consultor_md?: string | null;
      aprovado_pelo_consultor: boolean;
      custo_estimado_usd: number;
    } | null;
  };
}

export type CodigoFalhaIA =
  | "ERR_GEMINI_ALL_MODELS_EXHAUSTED"
  | "ERR_GEMINI_RATE_LIMIT_429"
  | "ERR_GEMINI_TIMEOUT_504"
  | "ERR_GEMINI_AUTH_401"
  | "ERR_NETWORK_DISCONNECTED"
  | "ERR_AI_TIMEOUT_01"
  | "ERR_AI_API_UNAVAILABLE_02"
  | "ERR_AI_NETWORK_OFFLINE_03"
  | "ERR_AI_AUTH_TOKEN_04"
  | "ERR_AI_QUOTA_EXCEEDED_05"
  | "ERR_AI_GENERIC_FALLBACK_06";

export interface ErroFalhaIA {
  codigo_erro: CodigoFalhaIA | string;
  mensagem_amigavel: string;
  detalhe_tecnico?: string;
  suporta_offline?: boolean;
  status_http?: number;
}

export interface SolicitacaoIAPendenteOutbox {
  id: string;
  ebt_id: string;
  ebt_nome: string;
  timestamp: string;
  usar_gemini: boolean;
  modelo_gemini: string;
  gemini_api_key?: string;
  forcar_regeneracao: boolean;
  codigo_erro: string;
  mensagem_erro: string;
  status: "pendente" | "sincronizando" | "falha" | "PENDING_SYNC";
}
