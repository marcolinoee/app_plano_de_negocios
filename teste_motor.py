from motor_financeiro import ItemInvestimento, DespesaFixa, Insumo, Produto, VendaProjetada, ProjetoNegocio

# 1. Criando o Projeto
meu_projeto = ProjetoNegocio(nome_empresa="Distribuidora de Bebidas Teste")

# 2. Inserindo Investimentos (Capex)
# Nota: Aqui a classe ItemInvestimento usa 'valor' mesmo.
meu_projeto.investimentos.append(ItemInvestimento(nome="Empilhadeira", valor=100000.00))
meu_projeto.investimentos.append(ItemInvestimento(nome="Veículo para entrega", valor=80000.00))

# 3. Inserindo Gastos Fixos (Opex)
# CORREÇÃO AQUI: mudamos de 'valor' para 'valor_mensal'
meu_projeto.despesas_fixas.append(DespesaFixa(nome="Aluguel e Estrutura", valor_mensal=15000.00))
meu_projeto.despesas_fixas.append(DespesaFixa(nome="Folha de Pagamento", valor_mensal=45000.00))

# 4. Criando um Produto (Vinho) usando a Ficha Técnica
vinho_tinto = Produto(
    nome="Vinho Tinto Seco (Cx c/12)",
    margem_lucro_desejada=0.28, # 28% de lucro
    impostos_taxas=0.135,       # 13.5% de impostos
    comissoes=0.03              # 3% de comissão
)
# Adicionando o custo de compra do fornecedor na ficha técnica
vinho_tinto.insumos.append(Insumo(nome="Caixa de Vinho Fornecedor", custo_unitario=360.00, quantidade_necessaria=1))

# 5. Lançando a Projeção de Vendas
# Vamos simular a venda de 200 caixas por mês
meu_projeto.vendas_projetadas.append(VendaProjetada(produto=vinho_tinto, quantidade_mensal=200))


# ==========================================
# EXECUTANDO O CÁLCULO E EXIBINDO NA TELA
# ==========================================

print(f"\n--- ANÁLISE DE VIABILIDADE: {meu_projeto.nome_empresa.upper()} ---")
print(f"Investimento Total Necessário: R$ {meu_projeto.total_investimento():.2f}")
print(f"Preço de Venda Sugerido (1 cx Vinho): R$ {vinho_tinto.preco_venda_sugerido:.2f}\n")

print("--- DRE MENSAL PROJETADA ---")
dre = meu_projeto.gerar_dre_mensal()
for linha, valor in dre.items():
    print(f"{linha}: R$ {valor:.2f}")

print("\n--- INDICADORES DE RETORNO ---")
indicadores = meu_projeto.calcular_viabilidade()
for ind, valor in indicadores.items():
    print(f"{ind}: {valor}")
print("-" * 50)