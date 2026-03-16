import google.generativeai as genai

print("--- DIAGNÓSTICO DE CONEXÃO DA IA ---")
chave = input("Cole sua Chave de API aqui e aperte ENTER: ").strip()

genai.configure(api_key=chave)

print("\nBuscando modelos autorizados para esta chave...")
modelos_texto = []

try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            modelos_texto.append(m.name)
            print(f"✔️ Encontrado: {m.name}")
            
    if not modelos_texto:
        print("Nenhum modelo de geração de texto disponível para esta chave.")
    else:
        # Vamos tentar forçar um teste com o primeiro modelo que tenha "flash" no nome
        modelo_escolhido = modelos_texto[0]
        for m in modelos_texto:
            if "flash" in m:
                modelo_escolhido = m
                break
                
        print(f"\nTestando geração de texto com o motor: {modelo_escolhido} ...")
        
        # O pulo do gato: às vezes a string precisa do prefixo exato que veio da lista
        modelo = genai.GenerativeModel(modelo_escolhido)
        resposta = modelo.generate_content("Responda exatamente com esta frase: Conexão bem sucedida com o motor IA!")
        
        print(f"\n✅ SUCESSO! Resposta da IA: {resposta.text}")
        print(f"👉 A string correta que você deve colocar no app.py é: '{modelo_escolhido}'")

except Exception as e:
    print(f"\n❌ ERRO DETALHADO: {e}")