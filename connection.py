# connection.py
import socket
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


DEBUG_PORT = 9222
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE_DIR = Path.home() / "AppData" / "Local" / "TanureFindPrice" / "ChromeProfile"


def chrome_running():
    """Verifica se o Chrome de automação já está disponível na porta 9222."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", DEBUG_PORT)) == 0


def start_chrome():
    """Inicia o Chrome dedicado ao scraper."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    subprocess.Popen([
        CHROME_PATH,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={PROFILE_DIR}",
    ])

    for _ in range(30):
        if chrome_running():
            return
        time.sleep(1)

    raise RuntimeError("Chrome não iniciou a porta de depuração.")


def connect():
    """
    Inicia o Chrome se necessário e conecta o Playwright a ele.

    Retorna:
        playwright, browser, context, page
    """
    if not chrome_running():
        print("Iniciando Chrome...")
        start_chrome()
    else:
        print("Chrome já está em execução.")

    pw = sync_playwright().start()

    try:
        browser = pw.chromium.connect_over_cdp(
            f"http://127.0.0.1:{DEBUG_PORT}"
        )
    except Exception:
        pw.stop()
        raise

    if not browser.contexts:
        browser.close()
        pw.stop()
        raise RuntimeError("Nenhum contexto do Chrome encontrado.")

    context = browser.contexts[0]

    if context.pages:
        page = context.pages[0]
    else:
        page = context.new_page()

    print("Chrome conectado.")
    return pw, browser, context, page


if __name__ == "__main__":
    pw, browser, context, page = connect()

    print("CONECTADO")
    print("Páginas abertas:", len(context.pages))

    input("Pressione ENTER para encerrar a conexão...")

    browser.close()
    pw.stop()