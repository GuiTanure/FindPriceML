# ml_api.py
"""Small HTTP client for the Mercado Livre MVP integration."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import requests


class MercadoLivreError(RuntimeError):
    pass


class AuthenticationError(MercadoLivreError):
    pass


class APIError(MercadoLivreError):
    pass


class CatalogProductItemsNotFound(APIError):
    """The catalog product has no current winner listings."""


class NetworkError(MercadoLivreError):
    pass


class MercadoLivreAPI:
    BASE_URL = "https://api.mercadolibre.com"

    def __init__(self, credentials: dict[str, str], token_saver, session=None, timeout: float = 15.0) -> None:
        self.client_id = credentials["client_id"]
        self.client_secret = credentials["client_secret"]
        self.access_token = credentials["access_token"]
        self.refresh_token = credentials.get("refresh_token", "")
        self.expires_in = credentials.get("expires_in")
        self.obtained_at = credentials.get("obtained_at")
        self.token_saver = token_saver
        self.session = session or requests.Session()
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}

    def _decode(self, response: Any) -> dict:
        try:
            data = response.json()
        except ValueError as exc:
            raise APIError("A API retornou JSON inválido.") from exc
        if not isinstance(data, dict):
            raise APIError("A API retornou um formato JSON inesperado.")
        return data

    def refresh_access_token(self) -> None:
        if not self.refresh_token:
            raise AuthenticationError("Access token expirado e refresh token não configurado.")
        try:
            response = self.session.post(
                f"{self.BASE_URL}/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                },
                headers={"Accept": "application/json"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise NetworkError(f"Falha de rede ao renovar autenticação: {exc}") from exc
        if response.status_code != 200:
            raise AuthenticationError(f"Falha ao renovar autenticação (HTTP {response.status_code}).")
        data = self._decode(response)
        new_access = data.get("access_token")
        new_refresh = data.get("refresh_token")
        if not new_access:
            raise AuthenticationError("A resposta de refresh não contém access_token.")
        self.access_token = new_access
        if new_refresh:
            self.refresh_token = new_refresh
        self.expires_in = data.get("expires_in")
        self.obtained_at = int(datetime.now(timezone.utc).timestamp())
        self.token_saver(new_access, new_refresh, self.expires_in, self.obtained_at)

    def _token_needs_refresh(self) -> bool:
        if not self.access_token:
            return True
        if not self.expires_in or not self.obtained_at:
            return False
        now = int(datetime.now(timezone.utc).timestamp())
        return now >= int(self.obtained_at) + int(self.expires_in) - 30

    def _request(self, method: str, path: str, params: dict | None = None, retry_auth: bool = True) -> dict:
        if retry_auth and self._token_needs_refresh() and self.refresh_token:
            self.refresh_access_token()
        for rate_attempt in range(3):
            try:
                response = self.session.request(
                    method,
                    f"{self.BASE_URL}{path}",
                    params=params,
                    headers=self._headers(),
                    timeout=self.timeout,
                )
            except requests.Timeout as exc:
                raise NetworkError("Tempo limite excedido ao consultar o Mercado Livre.") from exc
            except requests.ConnectionError as exc:
                raise NetworkError(f"Não foi possível conectar ao Mercado Livre: {exc}") from exc
            except requests.RequestException as exc:
                raise NetworkError(f"Erro de rede: {exc}") from exc

            if response.status_code == 401 and retry_auth:
                self.refresh_access_token()
                return self._request(method, path, params, retry_auth=False)
            if response.status_code == 429 and rate_attempt < 2:
                time.sleep(0.5 * (2**rate_attempt))
                continue
            if response.status_code in (401, 403):
                raise AuthenticationError(self._error_message(method, path, response))
            if response.status_code >= 400:
                raise APIError(self._error_message(method, path, response))
            return self._decode(response)
        raise APIError("Limite de requisições atingido (HTTP 429) após tentativas.")

    @staticmethod
    def _error_message(method: str, path: str, response: Any) -> str:
        message = "sem mensagem detalhada"
        try:
            payload = response.json()
            if isinstance(payload, dict):
                message = payload.get("message") or payload.get("error") or message
        except ValueError:
            pass
        request_id = getattr(response, "headers", {}).get("x-request-id")
        suffix = f"; request_id={request_id}" if request_id else ""
        return f"{method} {path} retornou HTTP {response.status_code}: {message}{suffix}"

    def search_catalog_products(self, query: str, limit: int = 20) -> dict:
        return self._request(
            "GET",
            "/products/search",
            {
                "status": "active",
                "site_id": "MLB",
                "q": query,
                "limit": max(1, min(int(limit), 20)),
            },
        )

    def get_catalog_product_items(self, catalog_product_id: str, offset: int = 0, limit: int = 100) -> dict:
        """Return marketplace listings attached to a catalog product.

        This resource is used by the public MCP project, but is not part of the
        official public documentation currently used by this application.
        """
        limit = max(1, min(int(limit), 100))
        try:
            return self._request(
                "GET",
                f"/products/{catalog_product_id}/items",
                {"limit": limit, "offset": max(0, int(offset))},
            )
        except APIError as exc:
            if "HTTP 404" in str(exc) and "No winners found" in str(exc):
                raise CatalogProductItemsNotFound(
                    f"Nenhum anúncio vencedor encontrado para {catalog_product_id}."
                ) from exc
            raise
