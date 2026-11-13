import subprocess
import re
import os
import requests
from pathlib import Path
from dotenv import load_dotenv


URL_LOCAL = "http://127.0.0.1:8000"
ENV_FILE = Path(".env")
_processo_tunnel = None


def tunnel_esta_rodando():
    try:
        resposta = requests.get("http://127.0.0.1:20241/metrics", timeout=2)
        return resposta.status_code == 200
    except requests.RequestException:
        return False


def atualizar_redirect_uri(url):
    redirect_uri = f"{url}/callback"

    linhas = ENV_FILE.read_text(encoding="utf-8").splitlines()

    atualizado = False

    for i, linha in enumerate(linhas):
        if linha.startswith("ML_REDIRECT_URI="):
            linhas[i] = f"ML_REDIRECT_URI={redirect_uri}"
            atualizado = True
            break

    if not atualizado:
        linhas.append(f"ML_REDIRECT_URI={redirect_uri}")

    ENV_FILE.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    # ConfigStore usa load_dotenv sem sobrescrever o ambiente. Atualizar aqui
    # tambem garante que uma nova URL seja usada nesta mesma execucao.
    os.environ["ML_REDIRECT_URI"] = redirect_uri

    return redirect_uri


def preparar_tunnel():
    """Garante um tunnel ativo e configura o Redirect URI usado pelo OAuth."""
    global _processo_tunnel

    if tunnel_esta_rodando():
        load_dotenv(dotenv_path=ENV_FILE)
        redirect_uri = os.getenv("ML_REDIRECT_URI", "").strip()
        if redirect_uri:
            print(f"Cloudflare Tunnel ja esta rodando: {redirect_uri}")
            return None, redirect_uri, False
        raise RuntimeError(
            "O Cloudflare Tunnel ja esta rodando, mas ML_REDIRECT_URI nao foi encontrado no .env."
        )

    print("Iniciando Cloudflare Tunnel...")
    _processo_tunnel, url = iniciar_tunnel()
    redirect_uri = atualizar_redirect_uri(url)
    print(f"Tunnel configurado. Callback OAuth: {redirect_uri}")
    return _processo_tunnel, redirect_uri, True


def iniciar_tunnel():
    processo = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", URL_LOCAL],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    while True:
        linha = processo.stdout.readline()

        if not linha:
            break

        match = re.search(
            r"https://[a-z0-9-]+\.trycloudflare\.com",
            linha
        )

        if match:
            return processo, match.group(0)

    raise RuntimeError(
        "Não foi possível obter a URL do Cloudflare Tunnel."
    )


if __name__ == "__main__":
    if tunnel_esta_rodando():
        print("Cloudflare Tunnel já está rodando.")
    else:
        print("Iniciando Cloudflare Tunnel...")

        processo, url = iniciar_tunnel()
        redirect_uri = atualizar_redirect_uri(url)

        print()
        print("========================================")
        print(" CLOUDFLARE TUNNEL INICIADO")
        print("========================================")
        print(f"URL: {url}")
        print(f"Callback: {redirect_uri}")
        print("========================================")
        print()
        print("O .env foi atualizado automaticamente.")
        print("Atualize o Redirect URI no Mercado Livre.")
        print()
        print("O túnel permanecerá ativo enquanto este")
        print("programa estiver aberto.")

        processo.wait()
