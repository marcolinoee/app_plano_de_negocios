# 💠 Master Management - Plano de Negócios 5.0

> **Ecossistema Inteligente de Viabilidade Estratégica, Financeira e Análise de Risco com IA.**

O **Master Management 5.0** é uma plataforma avançada de simulação de negócios, projetada para unir o rigor técnico da engenharia econômica com a agilidade das metodologias ágeis de gestão. Desenvolvido para atender tanto o ambiente corporativo quanto o acadêmico, o software transforma dados brutos em decisões fundamentadas e relatórios executivos de alta fidelidade.

---

## 🚀 Arquitetura de Informação (Os 10 Pilares)

O sistema guia o usuário através de uma jornada lógica dividida em 10 interfaces funcionais completas:

1.  **🧩 Canvas:** Modelagem estratégica visual com persistência de dados (Parceiros, Proposta de Valor, Segmentos, Recursos e Canais).
2.  **📈 Premissas:** Configuração de horizontes temporais (anos), TMA, inflação projetada, crescimento e **Sazonalidade Mensal (12 meses)** de vendas.
3.  **🛠️ Capex:** Gestão detalhada de investimentos iniciais, ativos imobilizados e infraestrutura.
4.  **🔄 Opex:** Controle de custos fixos, folha de pagamento, pró-labore e despesas operacionais.
5.  **🏷️ Preços:** Motor de precificação reversa baseado em custo de insumos, impostos, taxas, comissões e margem de lucro alvo.
6.  **📄 Resumo:** Visão executiva consolidada de todos os eixos estratégicos e premissas financeiras do projeto.
7.  **📊 Viabilidade:** Motor financeiro que projeta o fluxo de caixa mês a mês, calculando **VPL**, **TIR Anualizada** e **Payback**, com gráficos de evolução do caixa acumulado.
8.  **🤖 Mentor IA:** Consultoria sênior via API do Google Gemini (`google-genai`) para diagnóstico automático de viabilidade, mapeamento de riscos e recomendações estratégicas.
9.  **📉 Dashboard Analítico:** * DRE Simplificada e automatizada.
    * Indicadores vitais: Receita Líquida, Margem de Contribuição, Ponto de Equilíbrio (PE), Índice de Lucratividade e ROI Mensal.
    * Gráficos interativos (Plotly): Composição de Custos, Receita vs Margem por Produto e Curva de Sazonalidade.
    * Métricas de Tração Digital (Startups/SaaS): CAC, LTV, MRR, Churn, LTV/CAC e Runway.
10. **🖨️ Relatório Executivo:** Geração automatizada de um **Dossiê em PDF** profissional, incluindo a renderização nativa de gráficos em alta resolução e pareceres da IA.

---

## 🛠️ Stack Tecnológica

O projeto utiliza uma stack focada em precisão matemática, performance e portabilidade robusta para desktop:

* **Linguagem:** Python 3.10+
* **Interface:** Streamlit (UI/UX reativa de alta fidelidade com CSS customizado)
* **Banco de Dados:** SQLAlchemy com SQLite (Persistência local, sem necessidade de nuvem)
* **Engine Financeira:** Numpy-Financial (Precisão acadêmica em cálculos de engenharia econômica)
* **Visualização:** Plotly
* **Motor de Exportação Gráfica:** Kaleido (1.2.0) operado via `choreographer` (Garante a renderização silenciosa de gráficos Plotly no Windows).
* **Inteligência Artificial:** Google GenAI SDK (`google-genai` usando o modelo Gemini 2.5 Flash)
* **Documentação PDF:** FPDF2 com suporte a fontes UTF-8 (`DejaVuSans`)

---

## 💻 Guia de Desenvolvimento e Setup

### ⚠️ Regra Crítica de Diretórios (Windows)
Para evitar falhas na compilação do executável ou na leitura do motor gráfico `choreographer`, **o caminho da pasta do projeto não deve conter caracteres especiais, acentos, cedilhas ou espaços**.
* ❌ Errado: `D:\Projetos_programação\app_plano de negócios\`
* ✅ Correto: `D:\Projetos_programacao\app_plano_de_negocios\`

---

## 📦 Distribuição (Build Institucional)

Para compilar o sistema como um executável Windows (.exe), garantindo a inclusão de todas as dependências de IA e bibliotecas gráficas, utilize o comando abaixo:

1. **Instale as dependências:**

Bash
pip install -r requirements.txt
pip install choreographer

2. **Instale o motor de navegador invisível do Kaleido:**

Bash
choreo_get_chrome

3. **Inicie o sistema:**

Bash
streamlit run app.py

---

## **📦 Distribuição (Build Institucional)**
Para compilar o sistema como um executável autossuficiente (.exe) para alunos e clientes, utilizamos o PyInstaller. O processo embute o Python, as bibliotecas, o banco de dados e o motor de IA em uma única pasta.

**Certifique-se de que o ambiente virtual está ativado e execute o script de build customizado:**

Bash
python build_exe.py

O aplicativo finalizado será gerado no diretório dist/Master_Management_5/.

---

## 🎓 Guia Rápido para Alunos (Como Executar)

Se você é aluno ou usuário final, siga estas instruções ao receber o software:
Baixe o arquivo .zip fornecido pelo professor.

**PASSO OBRIGATÓRIO:** Extraia os arquivos. Clique com o botão direito no .zip e selecione "Extrair Tudo...". Não abra o sistema de dentro do arquivo compactado.

Abra a nova pasta extraída e dê um duplo clique em Master_Management_5.exe.

**Aviso do Antivírus:** Como é um software acadêmico, o Windows SmartScreen pode alertar sobre "Software Desconhecido". Clique em "Mais informações" e, em seguida, em "Executar assim mesmo".

Uma janela de terminal preta abrirá para carregar o servidor local. Em poucos segundos, o sistema abrirá automaticamente no seu navegador.

---

## 👤 Desenvolvedor
Anderson Oliveira

Engenheiro Eletricista e Professor de Ensino Superior.

Mestre em Engenharia e Doutorando no PPGES.

Especialista na criação de materiais didáticos estruturados e ferramentas de automação para engenharia.