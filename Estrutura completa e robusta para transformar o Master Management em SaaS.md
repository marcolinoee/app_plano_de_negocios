# Estrutura completa e robusta para transformar o Master Management em SaaS

Proposta em camadas, da mais importante à menos. A ideia central é um **monólito modular** (e não microsserviços), com o motor financeiro isolado como pacote puro.

## 1. Modelo de negócio e de tenancy

- **Tenant = a consultoria** (cliente pagante). Dentro dela existem **workspaces por EBT** (empresa assessorada).
- **Papéis (RBAC):** dono da consultoria, admin, consultor, analista, fundador/cliente (edita só o seu workspace), investidor/banca (somente leitura, via link com expiração).
- **Planos:** limites por tenant (nº de EBTs, cenários, análises de IA por mês, PDFs, armazenamento). Cobrança via Stripe ou Asaas/Pagar.me (Pix e boleto importam no Brasil).

## 2. Modelo de domínio

- **Plataforma:** `Tenant`, `User`, `Membership` (usuário × tenant × papel), `Convite`, `Assinatura`, `UsoMedido`.
- **Consultoria:** `Cliente/EBT`, `Engajamento`, `Entregável`, `Tarefa`, `Reunião/Ata`, `Cronograma`, `Documento`, `Comentário`.
- **Diagnóstico (o que já existe):** `LeanCanvas`, `Premissas`, `Capex`, `Opex`, `PlanoSaaS`, `Jurídico`.
- **Cenários e versões:** `Cenario` (base/otimista/pessimista), `VersaoPremissas` imutável, `ResultadoSimulacao` guardando entradas e saídas, para auditoria e comparação.
- **IA e relatórios:** `AnaliseIA` (prompt, modelo, custo, resultado), `Relatorio/Dossie` (PDF gerado, versão, hash).
- **Auditoria:** `AuditLog` (quem alterou o quê e quando), obrigatório para consultoria.

## 3. Arquitetura técnica

- **Backend:** FastAPI com módulos por domínio (`identidade`, `consultoria`, `diagnostico`, `financeiro`, `ia`, `relatorios`, `cobranca`). Sessão SQLAlchemy **por requisição** e Alembic para migrações.
- **Banco:** PostgreSQL com `tenant_id` em todas as tabelas e **Row-Level Security**. É mais simples de operar que schema por cliente e seguro quando bem testado.
- **Assíncrono:** Redis + fila (Celery, RQ ou Arq) para PDF, IA e simulações pesadas, com status de job exibido na UI.
- **Arquivos:** S3 compatível (ou Cloudflare R2) para PDFs e anexos, com URL assinada.
- **Autenticação:** provedor pronto (Auth0, Clerk, Supabase Auth ou Keycloak) em vez de implementar do zero; OAuth2/JWT, MFA e SSO para consultorias maiores.
- **Frontend:** Next.js + Tailwind **só se** houver meta de produto comercial; para validar rápido, FastAPI + HTMX ou o próprio Streamlit atrás de autenticação. Gráficos com Plotly.js ou Recharts.
- **API:** REST versionada (`/v1`), OpenAPI gerado, paginação e idempotência nos endpoints de criação.

## 4. Motor financeiro (o coração do produto)

- Pacote Python **puro**, sem Streamlit nem banco, com entrada e saída em Pydantic.
- **Testes** com casos conhecidos (planilha de referência) e testes de propriedade.
- **Validações de sanidade** antes de qualquer IA: TIR fora de faixa plausível, payback menor que o ciclo de caixa, margem acima de limites setoriais, churn zerado, múltiplas raízes na TIR, fluxo sem mudança de sinal. O resultado vira `alertas[]`, exibidos na tela e enviados à IA.
- Cálculo **determinístico e versionado** (`versao_motor`), para reproduzir um resultado antigo.
- Análise de sensibilidade e Monte Carlo como funcionalidades de plano superior.

## 5. IA com governança

- Camada de abstração de provedor (Gemini hoje, trocável depois).
- Prompt versionado, saída estruturada (JSON) e **somente dados agregados**: minimizar o envio de dados pessoais ou sensíveis.
- Limite e custo por tenant, cache de análises iguais, registro de cada chamada.
- Rótulo claro de "parecer gerado por IA" e revisão humana do consultor antes de entrar no dossiê.

## 6. Segurança, LGPD e compliance

- Criptografia em trânsito e em repouso; segredos em cofre (nunca no código ou no `.env` versionado).
- Papel de operador (a plataforma) versus controlador (a consultoria): contrato e DPA.
- Exportação e exclusão de dados por tenant, retenção definida, backups testados.
- Rate limiting, proteção contra OWASP Top 10, varredura de dependências, logs sem dados sensíveis.

## 7. DevOps e operação

- **Docker** + docker-compose local; deploy em Render, Fly.io, Railway ou AWS/GCP conforme a escala.
- **CI/CD** (GitHub Actions): lint, testes do motor, testes de isolamento entre tenants, migração automática e deploy.
- Ambientes dev, staging e produção.
- Observabilidade: Sentry para erros, logs estruturados, métricas (Prometheus/Grafana ou serviço gerenciado), alertas e healthchecks.
- Backup diário do Postgres com teste periódico de restauração.

## 8. Produto e crescimento

- Onboarding guiado (criar consultoria → convidar equipe → criar primeira EBT).
- Modelos de diagnóstico por setor, white-label (logo e cores da consultoria nos PDFs), portal do cliente e notificações por e-mail.
- Analytics de produto (ativação, retenção) e central de ajuda.

## 9. Jurídico

- Trocar o `LICENSE.txt` acadêmico por licença compatível com uso comercial (ou código proprietário), e definir a titularidade caso haja vínculo institucional (UFPE, UNIT). Termos de Uso e Política de Privacidade antes do primeiro cliente externo.

## 10. Roadmap sugerido

| Fase | Entrega | Resultado |
| --- | --- | --- |
| 0 | Extrair o motor financeiro, testes, validações de sanidade | Base confiável |
| 1 | Modelo de domínio, autenticação, tenants, RBAC, RLS, auditoria | Núcleo SaaS |
| 2 | Migrar os 11 módulos para API + frontend, cenários e versões | Paridade com o app atual |
| 3 | Filas, PDF e IA assíncronos, limites por plano | Funcionalidades pesadas |
| 4 | Cobrança, onboarding, white-label, LGPD formalizada | Pronto para clientes pagantes |
| 5 | Observabilidade, escala, portal do cliente, integrações | Operação madura |

**Recomendação prática:** não tente construir tudo de uma vez. As fases 0 e 1 definem se o projeto é viável; faça-as antes de investir em interface. Para um primeiro piloto com 2 ou 3 consultorias, a fase 2 com Streamlit ou HTMX já basta.

## Próximos passos possíveis

- Detalhar o modelo de dados multi-tenant (tabelas e políticas RLS).
- Propor a estrutura de pastas do backend FastAPI.
