# oauth.py
"""Local OAuth Authorization Code + PKCE flow for Mercado Livre."""

from __future__ import annotations

import base64
import hashlib
import http.server
import secrets
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass

import requests


class OAuthError(RuntimeError):
    """Raised when the local OAuth flow cannot be completed."""


@dataclass
class OAuthCallback:
    code: str | None = None
    state: str | None = None
    error: str | None = None
    error_description: str | None = None


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    callback = OAuthCallback()
    received = threading.Event()

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_error(404)
            return
        values = urllib.parse.parse_qs(parsed.query)
        type(self).callback = OAuthCallback(
            code=values.get("code", [None])[0],
            state=values.get("state", [None])[0],
            error=values.get("error", [None])[0],
            error_description=values.get("error_description", [None])[0],
        )
        type(self).received.set()
        body = (
            "<html><body><h1>Autorizacao recebida</h1>"
            "<p>Voce pode fechar esta janela e voltar ao programa.</p></body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        # Never log the callback URL: it may contain the authorization code.
        return


class MercadoLivreOAuth:
    AUTHORIZATION_URL = "https://auth.mercadolivre.com.br/authorization"
    TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, session=None, timeout: float = 15.0):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.session = session or requests.Session()
        self.timeout = timeout

    @staticmethod
    def _pkce_pair() -> tuple[str, str]:
        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return verifier, challenge

    def authorization_url(self, state: str, code_challenge: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.AUTHORIZATION_URL}?{urllib.parse.urlencode(params)}"

    def authorize_local(self, timeout_seconds: int = 300) -> dict:
        parsed_redirect = urllib.parse.urlparse(self.redirect_uri)
        if parsed_redirect.path not in ("", "/callback"):
            raise OAuthError("ML_REDIRECT_URI deve apontar para o endpoint /callback.")
        if parsed_redirect.scheme != "https" or not parsed_redirect.netloc:
            raise OAuthError("ML_REDIRECT_URI deve ser uma URL HTTPS válida.")

        state = secrets.token_urlsafe(32)
        code_verifier, code_challenge = self._pkce_pair()
        handler = _CallbackHandler
        handler.callback = OAuthCallback()
        handler.received = threading.Event()
        try:
            server = http.server.HTTPServer(("127.0.0.1", 8000), handler)
        except OSError as exc:
            raise OAuthError("Não foi possível iniciar o callback local em 127.0.0.1:8000.") from exc

        url = self.authorization_url(state, code_challenge)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            webbrowser.open(url)
            if not handler.received.wait(timeout_seconds):
                raise OAuthError("Tempo limite aguardando o callback OAuth.")
            callback = handler.callback
        finally:
            server.shutdown()
            server_thread.join(timeout=2)
            server.server_close()

        if callback.state != state:
            raise OAuthError("State OAuth inválido; autorização rejeitada.")
        if callback.error:
            description = callback.error_description or callback.error
            raise OAuthError(f"Mercado Livre recusou a autorização: {description}.")
        if not callback.code:
            raise OAuthError("Callback OAuth não retornou authorization code.")
        return self.exchange_code(callback.code, code_verifier)

    def exchange_code(self, code: str, code_verifier: str) -> dict:
        return self._token_request(
            {
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri,
                "code_verifier": code_verifier,
            }
        )

    def _token_request(self, data: dict) -> dict:
        try:
            response = self.session.post(
                self.TOKEN_URL,
                data=data,
                headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise OAuthError(f"Erro de rede no endpoint OAuth: {exc}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise OAuthError("O endpoint OAuth retornou JSON inválido.") from exc
        if response.status_code != 200:
            raise OAuthError(f"Falha no endpoint OAuth (HTTP {response.status_code}).")
        if not payload.get("access_token") or not payload.get("refresh_token"):
            raise OAuthError("Resposta OAuth sem os tokens esperados.")
        payload["obtained_at"] = int(time.time())
        return payload
