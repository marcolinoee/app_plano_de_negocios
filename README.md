# 💠 Master Management - Plano de Negócios 5.0

> **Simulador de Viabilidade Econômico-Financeira e Estratégica**

O **Master Management Plano 5.0** é uma solução robusta desenvolvida para transformar a criação de planos de negócios em uma experiência analítica de alta precisão. Projetado para o ambiente acadêmico e profissional de engenharia e gestão, o software une a modelagem estratégica do Canvas com o rigor da matemática financeira e o poder da Inteligência Artificial.

---

## 🚀 Estrutura do Software

O sistema guia o usuário através de 8 pilares fundamentais:

1.  **🧩 Canvas:** Modelagem estratégica (Parceiros, Valor, Segmentos, etc).
2.  **📈 Premissas:** Definição de horizontes temporais, TMA, Inflação e **Sazonalidade Mensal**.
3.  **🛠️ Capex:** Gestão de investimentos iniciais e ativos imobilizados.
4.  **🔄 Opex:** Controle de custos fixos, folha de pagamento e estrutura.
5.  **🏷️ Precificação:** Cálculo de Markup dinâmico e preço de venda sugerido.
6.  **📄 Resumo:** Visão consolidada de todos os dados do projeto.
7.  **📊 Viabilidade:** Motor financeiro mensal com cálculo de **VPL**, **TIR Anualizada** e **Payback**.
8.  **🤖 IA Mentor:** Consultoria via Gemini API para benchmarking e análise de crédito.

---

## 🛠️ Stack Tecnológica

* **Python 3.12+**
* **Streamlit** (UI/UX Premium)
* **SQLAlchemy** (Banco de Dados SQLite)
* **Numpy-Financial** (Cálculos de VPL/TIR)
* **Plotly** (Gráficos Dinâmicos)
* **Google Generative AI** (Integração LLM)

---

## 📦 Compilação e Distribuição

Para gerar o executável institucional (.exe), utilize o PyInstaller a partir da raiz do projeto:

```bash
pyinstaller --noconfirm --onedir --add-data "app.py;." --add-data "banco_dados.py;." --copy-metadata streamlit --copy-metadata google-generativeai --copy-metadata plotly --name "Master_Management_Plano_5" lancador.py