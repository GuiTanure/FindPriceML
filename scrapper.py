from __future__ import annotations

import argparse
import json
import time
from typing import Any

from connection import connect


class ScraperError(RuntimeError):
    """A public Mercado Livre page could not provide a valid price context."""


class BotBlockedError(ScraperError):
    """Mercado Livre apresentou uma verificação que impede a automação."""


def build_public_url(catalog_id: str, item_id: str) -> str:
    return f"https://www.mercadolivre.com.br/p/{catalog_id}?pdp_filters=item_id:{item_id}"


def parse_nordic_context(data: str, catalog_id: str, item_id: str, url: str) -> dict[str, Any]:
    if not data.strip():
        raise ScraperError("__NORDIC_RENDERING_CTX__ está vazio.")
    prefix = "_n.ctx.r="
    if not data.startswith(prefix):
        raise ScraperError("O contexto Nordic não começa com o prefixo esperado.")
    try:
        context, _ = json.JSONDecoder().raw_decode(data[len(prefix):])
    except json.JSONDecodeError as exc:
        raise ScraperError(f"JSON inválido em __NORDIC_RENDERING_CTX__: {exc}") from exc

    try:
        price_data = context["appProps"]["pageProps"]["initialState"]["components"]["price"]["price"]
        price = float(price_data["value"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ScraperError("Preço não disponível no contexto Nordic.") from exc

    original_value = price_data.get("original_value")
    try:
        original_price = float(original_value) if original_value is not None else None
    except (TypeError, ValueError):
        original_price = None
    discount = round((original_price - price) / original_price * 100, 1) if original_price and original_price > price else None

    components = context["appProps"]["pageProps"]["initialState"]["components"]
    title = components.get("header", {}).get("title") or components.get("share", {}).get("title") or context.get("title")
    return {
        "price": price,
        "original_price": original_price,
        "discount": discount,
        "title": title,
        "catalog_id": catalog_id,
        "item_id": item_id,
        "url": url,
    }


class ChromeScraper:
    """One reusable connection to the dedicated Chrome CDP session."""

    def __init__(self) -> None:
        self.pw = None
        self.browser = None
        self.page = None

    def __enter__(self) -> "ChromeScraper":
        self.pw, self.browser, _context, self.page = connect()
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        if self.browser:
            self.browser.close()
        if self.pw:
            self.pw.stop()

    def scrape_price(self, catalog_id: str, item_id: str) -> dict[str, Any]:
        url = build_public_url(catalog_id, item_id)
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            deadline = time.monotonic() + 30
            self.page.wait_for_timeout(5000)
            nordic = self.page.locator("#__NORDIC_RENDERING_CTX__")
            warned = False
            while nordic.count() == 0:
                if not warned:
                    print(
                        "Mercado Livre solicitou login/verificação. "
                        "Conclua a etapa no Chrome; aguardando por no máximo 30 segundos..."
                    )
                    warned = True
                self.page.wait_for_timeout(1000)
                if time.monotonic() >= deadline:
                    raise BotBlockedError(
                        "Mercado Livre solicitou login/verificação e o contexto Nordic "
                        "não ficou disponível em 30 segundos."
                    )
            return parse_nordic_context(nordic.inner_text(), catalog_id, item_id, url)
        except ScraperError:
            raise
        except Exception as exc:
            raise ScraperError(f"Falha ao consultar a página pública: {exc}") from exc


def scrape_price(catalog_id: str, item_id: str) -> dict[str, Any]:
    """Compatibility helper for one-off calls; Tracker reuses ChromeScraper."""
    with ChromeScraper() as scraper:
        return scraper.scrape_price(catalog_id, item_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Consulta o preço público de um anúncio do Mercado Livre.")
    parser.add_argument("catalog_id", help="catalog_product_id, por exemplo MLB26740275")
    parser.add_argument("item_id", help="item_id, por exemplo MLB6200992578")
    args = parser.parse_args()
    result = scrape_price(args.catalog_id, args.item_id)
    print()
    print("Produto:", result.get("title"))
    print("Preço atual: R$", result["price"])
    print("Preço original: R$", result.get("original_price"))
    print("Link:", result["url"])


if __name__ == "__main__":
    main()
