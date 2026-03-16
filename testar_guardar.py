from banco_dados import session, ProjetoDB, InvestimentoDB, DespesaDB

print("A iniciar o processo de gravação...\n")

# ==========================================
# 1. GUARDAR DADOS NO BANCO
# ==========================================
# Criamos a "pasta" do projeto
novo_projeto = ProjetoDB(nome_empresa="Distribuidora de Bebidas Teste")

# Adicionamos os Investimentos dentro da pasta do projeto
novo_projeto.investimentos.append(InvestimentoDB(nome="Empilhadeira", valor=100000.00))
novo_projeto.investimentos.append(InvestimentoDB(nome="Veículo para entrega", valor=80000.00))

# Adicionamos as Despesas Fixas
novo_projeto.despesas.append(DespesaDB(nome="Aluguel", valor_mensal=15000.00))
novo_projeto.despesas.append(DespesaDB(nome="Folha de Pagamento", valor_mensal=45000.00))

# A MÁGICA ACONTECE AQUI: Mandamos o banco de dados guardar tudo!
session.add(novo_projeto)
session.commit() # O "commit" é o equivalente a clicar no botão "Guardar"

print("✅ Projeto e todos os seus custos foram guardados no SQLite com sucesso!\n")


# ==========================================
# 2. LER DADOS DO BANCO (Para provar que funcionou)
# ==========================================
print("--- A LER DO FICHEIRO MEU_PLANO.DB ---")

# Pedimos ao banco o primeiro projeto que ele encontrar
projeto_recuperado = session.query(ProjetoDB).first()

print(f"Empresa encontrada: {projeto_recuperado.nome_empresa}")

print("\nInvestimentos recuperados:")
for inv in projeto_recuperado.investimentos:
    print(f" - {inv.nome}: R$ {inv.valor:.2f}")

print("\nDespesas Fixas recuperadas:")
for desp in projeto_recuperado.despesas:
    print(f" - {desp.nome}: R$ {desp.valor_mensal:.2f}")
    
print("-" * 50)