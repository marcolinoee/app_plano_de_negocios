import os
import sys
import time
import socket
import threading
import webbrowser
import streamlit.web.cli as stcli


def porta_disponivel(porta: int) -> bool:
    """Verifica se uma porta TCP está livre."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", porta)) != 0


def escolher_porta(inicio: int = 8501, fim: int = 8510) -> int:
    """Retorna a primeira porta disponível no intervalo 8501-8510."""
    for p in range(inicio, fim):
        if porta_disponivel(p):
            return p
    return inicio  # fallback se todas estiverem ocupadas


def abrir_navegador(porta: int, tentativas: int = 15, intervalo: float = 0.8):
    """Aguarda o servidor subir confirmando via HTTP e abre o browser."""
    import urllib.request
    for _ in range(tentativas):
        time.sleep(intervalo)
        try:
            urllib.request.urlopen(f"http://localhost:{porta}", timeout=1)
            webbrowser.open(f"http://localhost:{porta}")
            return
        except Exception:
            continue
    # Fallback: abre mesmo sem confirmar (máquina muito lenta)
    webbrowser.open(f"http://localhost:{porta}")


if __name__ == "__main__":
    porta = escolher_porta()

    # Abre o navegador em paralelo (daemon=True garante que encerra com o app)
    threading.Thread(target=abrir_navegador, args=(porta,), daemon=True).start()

    # Descobre a localização exata dos arquivos (dentro do .exe ou em dev)
    if getattr(sys, 'frozen', False):
        pasta_base = sys._MEIPASS
    else:
        pasta_base = os.path.dirname(os.path.abspath(__file__))

    caminho_app = os.path.join(pasta_base, 'app.py')

    # Inicia o motor do Streamlit na porta detectada
    sys.argv = [
        "streamlit", "run", caminho_app,
        f"--server.port={porta}",
        "--global.developmentMode=false",
        "--server.headless=true",
    ]
    sys.exit(stcli.main())
