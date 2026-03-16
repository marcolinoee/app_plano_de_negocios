import os
import streamlit
import PyInstaller.__main__

# 1. Localiza os arquivos estáticos do Streamlit
st_path = os.path.dirname(streamlit.__file__)
st_static_path = os.path.join(st_path, "static")

# 2. Parâmetros de construção com "Hidden Imports"
params = [
    'lancador.py',
    '--noconfirm',
    '--onedir',
    '--windowed',
    '--name=Master_Management_5',
    # Adicionando os arquivos estáticos do Streamlit
    f'--add-data={st_static_path}{os.pathsep}streamlit/static',
    '--add-data=app.py;.',
    '--add-data=banco_dados.py;.',
    '--add-data=logo.png;.',
    # Forçando a inclusão dos módulos que o PyInstaller "perde"
    '--hidden-import=google.generativeai',
    '--hidden-import=google.ai.generativelanguage',
    '--hidden-import=google.protobuf',
    '--hidden-import=numpy_financial',
    # Coleta total das pastas das bibliotecas
    '--collect-all=streamlit',
    '--collect-all=google.generativeai',
    '--collect-all=google.ai.generativelanguage',
    '--collect-all=plotly',
    '--copy-metadata=streamlit',
    '--copy-metadata=google-generativeai',
]

# 3. Execução
print("💠 Iniciando a construção Master Management 5.0...")
PyInstaller.__main__.run(params)
print("\n✅ Construção finalizada! Se o erro persistir, verifique o Passo 2 abaixo.")