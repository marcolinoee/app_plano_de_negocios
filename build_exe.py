import os
import streamlit
import PyInstaller.__main__

# 1. Localiza os arquivos estáticos do Streamlit
st_path = os.path.dirname(streamlit.__file__)
st_static_path = os.path.join(st_path, "static")

# 2. Parâmetros de construção
# FIX 4.1 — os.pathsep para compatibilidade Windows/Mac/Linux
params = [
    'lancador.py',
    '--noconfirm',
    '--onedir',
    '--windowed',
    '--name=Master_Management_5',
    # Arquivos estáticos do Streamlit
    f'--add-data={st_static_path}{os.pathsep}streamlit/static',
    # Arquivos da aplicação
    f'--add-data=app.py{os.pathsep}.',
    f'--add-data=banco_dados.py{os.pathsep}.',
    # Assets (fonte UTF-8 para PDF)
    f'--add-data=assets{os.pathsep}assets',
    # Hidden imports necessários
    '--hidden-import=google.generativeai',
    '--hidden-import=google.ai.generativelanguage',
    '--hidden-import=google.protobuf',
    '--hidden-import=numpy_financial',
    # Coleta total das bibliotecas
    '--collect-all=streamlit',
    '--collect-all=google.generativeai',
    '--collect-all=google.ai.generativelanguage',
    '--collect-all=plotly',
    '--copy-metadata=streamlit',
    '--copy-metadata=google-generativeai',
]

# Logo opcional — só inclui se o arquivo existir
if os.path.exists('logo.png'):
    params.append(f'--add-data=logo.png{os.pathsep}.')
else:
    print("⚠️  logo.png não encontrado — será omitido do executável.")

# Remove entradas vazias por segurança
params = [p for p in params if p]

# 3. Execução
print("💠 Iniciando a construção Master Management 5.0...")
PyInstaller.__main__.run(params)
print("\n✅ Construção finalizada!")
print("   Execute: dist/Master_Management_5/Master_Management_5")
