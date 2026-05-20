import os
import streamlit
import PyInstaller.__main__

# 1. Localiza os arquivos estáticos do Streamlit
st_path = os.path.dirname(streamlit.__file__)
st_static_path = os.path.join(st_path, "static")

# 2. Parâmetros de construção
# FIX: os.pathsep para compatibilidade Windows/Mac/Linux
params = [
    'lancador.py',
    '--noconfirm',
    '--onedir',
    '--windowed',
    '--name=Master_Management_TICs',         # ⬅️ ATUALIZADO: Novo nome do executável e da pasta dist
    
    # Arquivos estáticos do Streamlit
    f'--add-data={st_static_path}{os.pathsep}streamlit/static',
    
    # Arquivos da aplicação
    f'--add-data=app.py{os.pathsep}.',
    f'--add-data=banco_dados.py{os.pathsep}.',
    
    # Assets (fonte UTF-8 para PDF)
    f'--add-data=assets{os.pathsep}assets',
    
    # --- ATUALIZAÇÃO DE DEPENDÊNCIAS ---
    # Hidden imports necessários
    '--hidden-import=google.genai',
    '--hidden-import=google.auth',
    '--hidden-import=numpy_financial',
    '--hidden-import=pandas',                # ⬅️ ADICIONADO: Garantia para renderização das DREs
    '--hidden-import=fpdf',
    '--hidden-import=kaleido',
    '--hidden-import=choreographer',
    
    # Coleta total das bibliotecas
    '--collect-all=streamlit',
    '--collect-all=google.genai',
    '--collect-all=google.auth',
    '--collect-all=plotly',
    '--collect-all=kaleido',
    '--collect-all=choreographer',
    
    # Metadados para evitar erros de "Version not found"
    '--copy-metadata=streamlit',
    '--copy-metadata=google-genai',
    '--copy-metadata=kaleido',
]

# Logo opcional — só inclui se o arquivo existir
if os.path.exists('logo.png'):
    params.append(f'--add-data=logo.png{os.pathsep}.')
else:
    print("⚠️  logo.png não encontrado — será omitido do executável.")

# Remove entradas vazias por segurança
params = [p for p in params if p]

# 3. Execução
print("🚀 Iniciando a construção: Master Management - TICs...")
PyInstaller.__main__.run(params)
print("\n✅ Construção finalizada com sucesso!")
print("   Execute o software em: dist/Master_Management_TICs/Master_Management_TICs.exe")