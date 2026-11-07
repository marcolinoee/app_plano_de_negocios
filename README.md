# 💠 Master Management Enterprise SaaS 5.0
> **Plataforma Corporativa Multi-Tenant de Engenharia Econômica, Governança Venture Capital e Inteligência Artificial Assistiva.**

[![Architecture](https://img.shields.io/badge/Architecture-FastAPI%20%7C%20React%2018%20%7C%20PostgreSQL%20RLS-blue)](https://fastapi.tiangolo.com/)
[![AI Engine](https://img.shields.io/badge/AI%20Engine-Gemini%20Waterfall%20(17%20Models)-red)](https://ai.google.dev/)
[![Security](https://img.shields.io/badge/Security-Multi--Tenant%20RLS%20%7C%20RBAC%20%7C%20PBKDF2--SHA256-green)](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
[![WCAG](https://img.shields.io/badge/Compliance-WCAG%202.1%20AA-purple)](https://www.w3.org/WAI/standards-guidelines/wcag/)

---

## 📋 Sumário Executivo

O **Master Management SaaS 5.0** é uma plataforma corporativa projetada para avaliação de viabilidade econômico-financeira de startups e empreendimentos de TIC, modelagem de cenários sob incerteza (Simulação de Monte Carlo), geração automatizada de relatórios executivos com assinatura criptográfica (Data Room PDF) e simulação de comitê de investimentos via Inteligência Artificial governada.

A solução opera sob um modelo **Multi-Tenant isolado por Row-Level Security (RLS)**, garantindo conformidade com a LGPD/GDPR, controle de acesso baseado em papéis (**RBAC de 6 níveis**) e alta disponibilidade com uma **cascata exaustiva de IA de 17 modelos Gemini** com retentativas exponenciais, telemetria de resolução e persistência local resiliente (*Outbox pattern*).

---

## 🏛️ Arquitetura da Solução

```mermaid
flowchart TD
    subgraph Client["Camada de Apresentação (Frontend SPA)"]
        UI["React 18 + TypeScript + Vite"]
        TW["Tailwind CSS (Master Executive Theme)"]
        STORE["Local Storage & Outbox Resiliente"]
        NGINX["Nginx Reverse Proxy (:3000 / :80)"]
    end

    subgraph API_Gateway["Camada de Aplicação (Backend REST API)"]
        FASTAPI["FastAPI 0.115+ (:8000)"]
        AUTH["Auth & RBAC (PBKDF2-SHA256 + JWT HS256 + OAuth2)"]
        AUDIT["Auditoria & Rastreabilidade de Requisições"]
    end

    subgraph Engines["Motores Especializados"]
        CORE_FIN["Motor Financeiro Puro (Zero I/O)\n• DRE & Fluxo de Caixa\n• VPL, TIR, Payback\n• Monte Carlo (1.000 iterações)"]
        AI_GOV["IA Governada & Sanitização LGPD\n• Anonimização de PII\n• Cache SHA-256\n• Cascata de 17 Modelos Gemini\n• Backoff Exponencial + Jitter"]
        PDF_GEN["Motor de Dossiês Executivos (ReportLab)\n• Assinatura Criptográfica SHA-256\n• Selo e QR Code de Validação"]
    end

    subgraph Data["Camada de Dados & Persistência"]
        PG["PostgreSQL 16 (Multi-Tenant com RLS)"]
        STORAGE["Storage de Dossiês Assinados (Volumes Docker)"]
    end

    UI --> NGINX
    NGINX -->|"/v1/*"| FASTAPI
    FASTAPI --> AUTH
    FASTAPI --> AUDIT
    FASTAPI --> CORE_FIN
    FASTAPI --> AI_GOV
    FASTAPI --> PDF_GEN
    FASTAPI -->|Tenant Context (SET LOCAL)| PG
    PDF_GEN --> STORAGE
    STORE -.->|Reenvio / Sync| FASTAPI
```

---

## 🌟 Funcionalidades Implementadas (Features Detalhadas)

### 1. 🧭 Navegação Superior Executiva & Identidade Master Management
- **Barra de Navegação Superior (Top Navbar):** Substituição do menu lateral esquerdo tradicional por uma barra horizontal fluida em abas, com controle de overflow e agrupamento inteligente.
- **Painel Lateral Oculto (Slide-Over Drawer):** Painel de perfil do usuário e dados de sessão/tenant acionado ao clicar no avatar executivo.
- **Paleta Corporativa de Elite:**
  - Fundo Dark Executive: `#0A0A0A` e grafite profundo `#121212` nos cabeçalhos e barras de navegação.
  - Painéis de Leitura Internos: Fundo off-white `#F8FAFC` com tipografia grafite escura `#0F172A`, garantindo contraste superior a **4.5:1** (conforme WCAG 2.1 AA).
  - Destaque Institucional: Vermelho Master Management (`#E30000` / `#D91414`) aplicado em botões de ação primária, indicadores de status e detalhes gráficos concêntricos.

### 2. 🗂️ As 12 Abas Funcionais da Plataforma
1. **🧩 Lean Canvas:** Modelagem estratégica estruturada (Parceiros-chave, Proposta de Valor, Segmentos, Canais, Estrutura de Custos e Fontes de Receita).
2. **📈 Premissas & Sazonalidade:** Horizontes de projeção (1 a 5 anos), Taxa Mínima de Atratividade (TMA), alíquotas tributárias, inflação e curva sazonal de vendas mês a mês (12 meses).
3. **🛠️ CapEx (Investimentos):** Cadastro detalhado de ativos imobilizados, maquinário, infraestrutura e despesas pré-operacionais com depreciação contábil.
4. **🔄 OpEx (Custos Fixos):** Custos operacionais mensais, folha de pagamento, pró-labore com encargos e despesas administrativas.
5. **🏷️ SaaS & Pricing:** Precificação reversa com decomposição de custos variáveis, impostos faturados, comissões de gateway e margem de contribuição alvo.
6. **⚖️ Riscos Legais & Compliance:** Mapeamento de passivos trabalhistas, societários e de propriedade intelectual com pontuação de severidade.
7. **📄 Recurso One-Pager:** Sumário executivo condensado para comitês e bancas de aceleração.
8. **📊 Viabilidade Econômica:** Fluxo de Caixa Descontado (FCD) mensal, VPL (Valor Presente Líquido), TIR Anualizada (Taxa Interna de Retorno), Payback Simples e Descontado, e Simulação Estocástica de Monte Carlo.
9. **📉 Dashboards Executivos:** DRE gerencial projetada, Ponto de Equilíbrio (PE), Margem EBITDA e métricas SaaS de alta tração (CAC, LTV, MRR, Churn, Runway e Magic Number).
10. **🤖 Comitê-VC (IA):** Parecer consultivo gerado por Inteligência Artificial simulando um comitê sênior de Venture Capital, categorizando tese de investimento, riscos e governança.
11. **🖨️ Data Room (PDF):** Geração sob demanda do Dossiê Executivo completo em PDF com carimbo digital SHA-256 e assinatura técnica do consultor.
12. **🛡️ Painel Admin (RBAC):** Gestão corporativa de usuários, planos e tenants com trilha de auditoria completa.

---

### 3. 👥 Gestão Avançada de Contas no Painel Admin (RBAC)
O Painel de Administração conta com ações dedicadas por usuário na tabela de gestão:
- **Excluir Conta:** Exclusão/desativação definitiva com modal de confirmação de segurança em duas etapas.
  - *Trava de Segurança Inviolável:* O Super Administrador logado (`marcolinoee@yahoo.com.br`) possui proteção de nível de código que impede a exclusão acidental da conta matriz.
- **Editar Usuário:** Modal responsivo para alteração de Nome Completo, E-mail, Papel RBAC e Status de Ativação.
- **Visualizar Uso Analítico:** Modal com métricas individuais de consumo:
  - Total de simulações de IA solicitadas.
  - Análises financeiras executadas.
  - Relatórios executivos em PDF emitidos.
  - Status de adesão ao programa EBT.
- **Mudar de Plano:** Seletor com atualização instantânea de licença (`FREE_TIER`, `PRO`, `ENTERPRISE`, `CUSTOM`).
- **6 Níveis de Papéis de Acesso (RBAC):**
  | Papel | Permissões Principais |
  | :--- | :--- |
  | `dono` | Acesso irrestrito a configurações do Tenant, faturamento e gestão de administradores. |
  | `admin` | Gestão de usuários, alteração de premissas, emissão de relatórios e execução de IA. |
  | `consultor` | Modelagem financeira, auditoria de dados e homologação técnica de pareceres. |
  | `analista` | Edição de premissas, execução de cálculos e leitura de relatórios. |
  | `fundador` | Leitura integral, visualização de dashboards e exportação do One-Pager. |
  | `investidor` | Acesso somente-leitura ao Data Room, Dossiê PDF e métricas de viabilidade. |

---

### 4. 🧠 Arquitetura de IA com Cascata Exaustiva Gemini (17 Modelos)

O módulo de integração com a Google GenAI API foi desenhado para missão crítica, operando em cascata (*waterfall*) com **17 modelos decrescentes**, garantindo que a análise seja entregue mesmo sob alta taxa de erro, sobrecarga ou quota esgotada em modelos de ponta.

#### Matriz de Fallback em Cascata
```
[Geração 4 & 3 - Frontier]
  1. gemini-4-argon
  2. gemini-3.1-pro-preview
  3. gemini-3.8-flash
  4. gemini-3.6-flash
  5. gemini-3-flash-preview
  6. gemini-3.5-flash-lite
  7. gemini-3.1-flash-lite
        ↓ (fallback se esgotadas retentativas)
[Geração 2.5]
  8. gemini-2.5-pro
  9. gemini-2.5-flash
  10. gemini-2.5-flash-lite
        ↓
[Geração 2.0]
  11. gemini-2.0-pro
  12. gemini-2.0-flash
  13. gemini-2.0-flash-lite
        ↓
[Geração 1.5]
  14. gemini-1.5-pro
  15. gemini-1.5-flash
  16. gemini-1.5-flash-8b
        ↓
[Geração 1.0 - Contingência Extrema]
  17. gemini-1.0-pro
```

#### Política de Retentativas e Telemetria
- **Mínimo de 3 Retentativas por Endpoint:** Cada modelo do catálogo é acionado com repetições em intervalos crescentes (*Exponential Backoff* com Jitter aleatório: ~1.0s, ~2.0s e ~4.0s).
- **Aborto Imediato em Erro de Credencial (401 / 403):** Se a chave de API for rejeitada, a cascata é interrompida imediatamente para evitar loops fúteis de rede, sinalizando `ERR_AI_AUTH_TOKEN_04`.
- **Cabeçalhos de Telemetria de Resolução:** Toda resposta da API inclui nos cabeçalhos HTTP e no corpo JSON:
  - `x-resolved-by-model`: Nome exato do modelo Gemini que efetivamente atendeu a requisição.
  - `x-attempts`: Número total de tentativas executadas durante o percurso da cascata.
  - `x-resolution-latency-ms`: Latência total da resolução em milissegundos.

---

### 5. 🛡️ Resiliência Offline, Outbox Local & Destravamento de Fila
Caso a conexão de rede caia ou todos os 17 modelos falhem:
- **Modo de Persistência Ativo (`PENDING_SYNC`):** O prompt, parâmetros e contexto da sessão são automaticamente persistidos no `localStorage` do navegador.
- **Códigos de Falha Padronizados:**
  - `ERR_GEMINI_ALL_MODELS_EXHAUSTED`: Todos os 17 modelos e suas respectivas 3 tentativas foram consultados sem sucesso.
  - `ERR_AI_TIMEOUT_01`: Tempo limite de rede excedido.
  - `ERR_AI_API_UNAVAILABLE_02`: Provedor temporariamente indisponível (HTTP 5xx).
  - `ERR_AI_NETWORK_OFFLINE_03`: Falha total de conectividade do cliente.
  - `ERR_AI_AUTH_TOKEN_04`: Chave de API inválida ou expirada.
- **Ações de Recuperação na UI:**
  - Botão **"Reprocessar Análise"**: Tenta nova sincronização com a API.
  - Botão **"Gerar Agora via Copiloto VC (Fallback Imediato)"**: Aciona o motor heurístico local sem latência externa.
  - Botão **"Limpar Fila de Persistência"**: Permite esvaziar e destravar o armazenamento local caso requisições antigas fiquem retidas.

---

### 6. 🔒 Governança de IA, LGPD e Assinatura Digital de PDF
- **Sanitização de PII (LGPD):** Regex avançada remove dados sensíveis (CPFs, e-mails, telefones e valores de cartões) antes do envio do prompt aos LLMs externos.
- **Cache Determinístico SHA-256:** Prompts com parâmetros idênticos são recuperados da base local sem gerar consumo redundante de tokens de API.
- **Homologação Humana Obrigatória:** As recomendações da IA possuem estado inicial `aguardando_revisao` e só são consolidadas no Data Room após chancela de um usuário com perfil `consultor` ou `admin`.
- **Dossiê Executivo em PDF:** Gerado via ReportLab com tipografia estruturada, gráficos de fluxo de caixa e um **hash criptográfico SHA-256** impresso no rodapé para validação de autenticidade documental.

---

## 🚀 Guia Passo a Passo de Implementação e Replicação

Siga este roteiro detalhado para clonar e configurar esta mesma arquitetura em seu ambiente ou em um novo projeto SaaS semelhante.

### 1. Pré-Requisitos do Sistema
- **Git** (2.40+)
- **Docker Engine** (24.0+) e **Docker Compose v2**
- **Node.js** 20 LTS e **npm** (para desenvolvimento frontend local)
- **Python** 3.11 ou 3.12 (para desenvolvimento backend local)

---

### 2. Estrutura Canônica de Diretórios
```
meu_projeto_saas/
├── backend/
│   ├── api.py                 # FastAPI Router, Endpoints /v1 e Telemetria
│   ├── auth_oauth.py          # Autenticação PBKDF2, JWT HS256 e OAuth2 Sandbox
│   ├── auditoria.py           # Logs de conformidade e trilha de auditoria
│   ├── database.py            # Engine SQLAlchemy e sessão RLS (SET LOCAL)
│   ├── filas_e_storage.py     # Geração de PDFs (ReportLab) e assinatura SHA-256
│   ├── ia_governanca.py       # Cascata Gemini de 17 modelos, retentativas e sanitização
│   ├── models.py              # Modelos relacionais SQLAlchemy (Tenant, Usuario, etc.)
│   └── rbac.py                # Decorators e verificadores de privilégios RBAC
├── core_financeiro/
│   ├── __init__.py
│   ├── calculadora.py         # Motor puro: DRE, FCD, VPL, TIR, Payback e Monte Carlo
│   ├── sanidade.py            # Validações matemáticas e coerência contábil
│   └── schemas.py             # Schemas Pydantic tipados (Zero I/O)
├── frontend/
│   ├── index.html
│   ├── nginx.conf             # Proxy reverso SPA + redirecionamento para o backend
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── api.ts             # Cliente HTTP Axios com interceptors de JWT e retry
│       ├── App.tsx            # Interface SPA (12 abas, modais RBAC e telemetria)
│       ├── Charts.tsx         # Gráficos interativos (Chart.js / Tailwind)
│       ├── main.tsx
│       └── types.ts           # Definições de tipos TypeScript
├── tests/
│   ├── test_backend_multitenant.py
│   └── test_core_financeiro.py
├── .env.example
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
└── requirements.txt
```

---

### 3. Configuração de Variáveis de Ambiente (`.env`)
Crie o arquivo `.env` na raiz do projeto com base no modelo:

```bash
# Banco de Dados PostgreSQL (Multi-Tenant com RLS)
POSTGRES_USER=mm_admin
POSTGRES_PASSWORD=mm_secret_2026
POSTGRES_DB=mm_saas_ebt
DATABASE_URL=postgresql+psycopg2://mm_admin:mm_secret_2026@db:5432/mm_saas_ebt

# Segredos Criptográficos
MM_JWT_SECRET=sua-chave-secreta-jwt-super-segura-hmac-sha256
MM_PDF_SIGNING_SECRET=sua-chave-secreta-para-assinatura-de-pdf-sha256

# Google GenAI Studio (Gemini)
GEMINI_API_KEY=sua_chave_de_api_do_google_ai_studio
GEMINI_MODEL=gemini-4-argon

# Provedores OAuth2 (Opcionais; em branco ativa o Sandbox Provider)
OAUTH_GOOGLE_CLIENT_ID=
OAUTH_GOOGLE_CLIENT_SECRET=
OAUTH_GITHUB_CLIENT_ID=
OAUTH_GITHUB_CLIENT_SECRET=
```

---

### 4. Executando com Docker Compose (Subida em 1 Comando)
Execute o comando de compilação e inicialização dos containers:

```bash
docker compose up --build -d
```

O Docker Compose inicializará quatro containers integrados em rede interna isolada:
1. `mm_saas_postgres` (`5432:5432`): Banco de dados relacional com RLS.
2. `mm_saas_backend` (`8000:8000`): API FastAPI com workers assíncronos.
3. `mm_saas_frontend` (`3000:80`): Nginx servindo o bundle SPA compilado.
4. `mm_saas_streamlit_legacy` (`8501:8501`): Módulo legado para simulações desktop.

---

### 5. Acessos e Credenciais Pré-Configuradas

| Serviço | URL de Acesso Local | URL de Rede (LAN) |
| :--- | :--- | :--- |
| **Frontend Principal (React SPA)** | `http://localhost:3000` | `http://<IP_DO_HOST>:3000` |
| **API REST Swagger / OpenAPI** | `http://localhost:8000/docs` | `http://<IP_DO_HOST>:8000/docs` |
| **Streamlit (Legado)** | `http://localhost:8501` | `http://<IP_DO_HOST>:8501` |

#### Credencial de Super Administrador (Bootstrap Automático)
- **E-mail:** `marcolinoee@yahoo.com.br`
- **Senha Padrão:** `Admin@2026Master`
- **Papel:** `dono` (Acesso irrestrito a todos os módulos e ao Painel Admin RBAC)

> [!NOTE]
> Para testar perfis instantaneamente sem configurar chaves OAuth externas, utilize os atalhos de **Login Sandbox (1-Click)** disponíveis na tela de autenticação, que simulam os perfis `dono`, `admin`, `consultor`, `analista`, `fundador` e `investidor`.

---

### 6. Execução da Suíte de Testes Automatizados

Para certificar a integridade do motor financeiro e da API multi-tenant:

```bash
# Executando testes dentro do container backend
docker exec -it mm_saas_backend python -m unittest discover tests

# Ou em ambiente virtual local (venv)
python -m unittest discover tests
```

*Resultado esperado:* **31 testes unitários aprovados (100% OK)** cobrindo:
- Isolamento de tenants via RLS (Row-Level Security).
- Bloqueio de senhas sem complexidade mínima e verificação PBKDF2.
- Cálculos matemáticos de VPL, TIR e Payback Descontado contra benchmarks analíticos.
- Cascata e resiliência de provedores de IA.

---

## 📡 Dicionário de Endpoints da API REST (`/v1`)

### Autenticação & Gestão de Contas
- `POST /v1/auth/login`: Autenticação por e-mail e senha (retorna JWT Token).
- `POST /v1/auth/oauth/{provider}`: Troca de autorização OAuth2 ou login via Sandbox.
- `GET /v1/auth/me`: Retorna os dados cadastrais e permissões do usuário conectado.
- `GET /v1/admin/usuarios`: Lista os usuários cadastrados do Tenant (exige `admin` ou `dono`).
- `PUT /v1/admin/usuarios/{id}`: Atualiza dados, papéis e status do usuário.
- `DELETE /v1/admin/usuarios/{id}`: Exclusão com trava de segurança de SuperAdmin.
- `POST /v1/admin/usuarios/{id}/mudar-plano`: Altera o plano de subscrição do assinante.
- `GET /v1/admin/usuarios/{id}/uso`: Retorna métricas de consumo de IA e emissão de PDFs.

### Cálculos Financeiros & Simulações
- `POST /v1/financeiro/calcular`: Executa a projeção completa (DRE, VPL, TIR e Payback).
- `POST /v1/financeiro/monte-carlo`: Executa simulação estocástica (1.000 iterações com desvio padrão).

### IA Governada & Relatórios
- `POST /v1/ia/analisar`: Executa a cascata de 17 modelos Gemini com retorno de telemetria.
- `GET /v1/ia/historico`: Consulta diagnósticos anteriores homologados.
- `POST /v1/ia/homologar`: Registra a aprovação técnica do consultor sobre o parecer de IA.
- `POST /v1/dossie/gerar-pdf`: Compila o Dossiê Executivo assinado com selo SHA-256.

---

## 🎨 Guia de Cores & Design System (Master Management)

| Elemento | Código HEX | Finalidade de Uso |
| :--- | :--- | :--- |
| **Dark Executive Base** | `#0A0A0A` | Fundo principal da aplicação e barras de navegação superiores. |
| **Dark Card Background** | `#121212` | Módulos estruturais escuros, drawer lateral e rodapés. |
| **Light Content Panel** | `#F8FAFC` | Painéis e cartões internos de trabalho e tabelas analíticas. |
| **Master Red (Destaque)** | `#E30000` | Botões primários (CTAs), badges de alerta e indicadores ativos. |
| **Dark Master Red** | `#990000` | Hover de botões vermelhos e acentos de erro crítico. |
| **Dark Text** | `#0F172A` | Textos em cartões claros com alto contraste legível. |
| **Muted Border** | `#334155` | Linhas divisórias discretas e bordas de inputs. |

---

## 📜 Licença e Propriedade Intelectual

Projeto desenvolvido sob padrões executivos de governança corporativa.
Todos os direitos reservados à **Master Management**.
Proibida a reprodução ou distribuição não autorizada de componentes do motor financeiro e da cascata proprietária de governança.
