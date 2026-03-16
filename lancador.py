import os
import sys
import time
import threading
import webbrowser
import streamlit.web.cli as stcli

def abrir_navegador():
    # Aguarda 3 segundos para o servidor do Streamlit arrancar completamente
    time.sleep(3)
    webbrowser.open("http://localhost:8501")

if __name__ == "__main__":
    # Abre o navegador em paralelo
    threading.Thread(target=abrir_navegador).start()
    
    # Descobre a localização exata de onde o .exe está a correr
    if getattr(sys, 'frozen', False):
        pasta_base = sys._MEIPASS
    else:
        pasta_base = os.path.dirname(os.path.abspath(__file__))
        
    caminho_app = os.path.join(pasta_base, 'app.py')
    
    # Inicia o motor do Streamlit
    sys.argv = ["streamlit", "run", caminho_app, "--global.developmentMode=false"]
    sys.exit(stcli.main())