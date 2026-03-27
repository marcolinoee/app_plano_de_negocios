# 💠 Master Management - Plano de Negócios 5.0

> **Ecossistema Inteligente de Viabilidade Estratégica, Financeira e Análise de Risco com IA.**

O **Master Management 5.0** é uma plataforma avançada de simulação de negócios, projetada para unir o rigor técnico da engenharia econômica com a agilidade das metodologias ágeis de gestão. Desenvolvido para atender tanto o ambiente corporativo quanto o acadêmico, o software transforma dados brutos em decisões fundamentadas e relatórios executivos de alta fidelidade.

---

## 🚀 Arquitetura de Informação (Os 10 Pilares)

O sistema guia o usuário através de uma jornada lógica dividida em 10 interfaces funcionais:

1.  **🧩 Canvas:** Modelagem estratégica visual (Parceiros, Proposta de Valor, Segmentos e Canais).
2.  **📈 Premissas:** Configuração de horizontes temporais, TMA, inflação e **Sazonalidade Mensal** de vendas.
3.  **🛠️ Capex:** Gestão detalhada de investimentos iniciais e ativos imobilizados.
4.  **🔄 Opex:** Controle de custos fixos, folha de pagamento e despesas operacionais (RH e Estrutura).
5.  **🏷️ Preços:** Motor de precificação baseado em Ficha Técnica, Markup e Margem de Contribuição.
6.  **📄 Resumo:** Visão executiva consolidada de todos os dados estratégicos e financeiros do projeto.
7.  **📊 Viabilidade:** Motor financeiro mensal com cálculo de **VPL**, **TIR Anualizada** e **Payback**.
8.  **🤖 IA Mentor:** Consultoria sênior via Gemini API para diagnóstico de viabilidade, riscos e recomendações.
9.  **📉 Dashboard:** Métricas de tração digital para startups (**CAC, LTV, MRR, Churn e Runway**).
10. **🖨️ Relatório:** Geração automatizada de **Dossiê em PDF** incluindo gráficos de fluxo de caixa e parecer técnico.

---

## 🛠️ Stack Tecnológica

O projeto utiliza uma stack focada em precisão matemática, performance e portabilidade:

* **Linguagem:** Python 3.12+.
* **Interface:** Streamlit (UI/UX reativa de alta fidelidade).
* **Banco de Dados:** SQLAlchemy com SQLite (Persistência local robusta).
* **Engine Financeira:** Numpy-Financial (Precisão em cálculos de engenharia econômica).
* **Visualização:** Plotly & Kaleido (Gráficos dinâmicos exportáveis para o relatório).
* **Inteligência Artificial:** Google Generative AI (Gemini 2.5 Flash).
* **Documentação:** FPDF2 (Geração de relatórios executivos em PDF).

---

## 📦 Distribuição (Build Institucional)

Para compilar o sistema como um executável Windows (.exe), garantindo a inclusão de todas as dependências de IA e bibliotecas gráficas, utilize o comando abaixo:

## 👤 Desenvolvedor

Anderson Oliveira

Engenheiro Eletricista e Professor de Ensino Superior.

Mestre em Engenharia e Doutorando no PPGES.

Especialista na criação de materiais didáticos estruturados e ferramentas de automação para engenharia.

```bash
pyinstaller --noconfirm --onedir --add-data "app.py;." \
--add-data "banco_dados.py;." \
--add-data "assets/;assets/" \
--copy-metadata streamlit \
--copy-metadata google-generativeai \
--copy-metadata plotly \
--name "Master_Management_5" lancador.py
