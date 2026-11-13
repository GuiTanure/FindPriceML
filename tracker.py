# tracker.py
from __future__ import annotations

import time
from pathlib import Path

from blocked_sellers import DEFAULT_BLOCKED_SELLERS_PATH, load_blocked_seller_ids
from models import Product
from ml_api import CatalogProductItemsNotFound, MercadoLivreError
from scrapper import BotBlockedError, ChromeScraper
from seller_evaluator import SellerEvaluation, evaluate_seller


class Tracker:
    def __init__(self, api, search_limit: int = 20, max_search_pages: int = 10, output=print, scraper=None, email_sender=None, seller_evaluator=evaluate_seller, blocked_sellers_path: Path | str = DEFAULT_BLOCKED_SELLERS_PATH) -> None:
        self.api = api
        self.search_limit = min(int(search_limit), 20)
        self.max_search_pages = max_search_pages
        self.output = output
        self.scraper = scraper
        self.item_delay = 4
        self.catalog_delay = 5
        self.email_sender = email_sender
        self.seller_evaluator = seller_evaluator
        self.blocked_seller_ids = load_blocked_seller_ids(blocked_sellers_path)
        self._seller_evaluations: dict[str, SellerEvaluation] = {}

    def _catalog_ids(self, product: Product) -> list[str]:
        if product.catalog_product_ids:
            return product.catalog_product_ids
        raise MercadoLivreError(
            f"O produto '{product.query}' nÃ£o possui catalog_product_id. "
            "Remova e cadastre-o novamente para selecionar o catÃ¡logo correto."
        )

    def _collect_items(self, catalog_id: str) -> list[dict]:
        items = []
        offset = 0
        limit = 100
        while True:
            response = self.api.get_catalog_product_items(catalog_id, offset=offset, limit=limit)
            page_items = response.get("results", [])
            items.extend(page_items)
            paging = response.get("paging", {}) or {}
            total = paging.get("total")
            if not page_items or total is None or offset + len(page_items) >= int(total):
                break
            offset += len(page_items)
        return items

    def run_product(self, product: Product) -> dict[str, int]:
        self.output(f"\n=== Produto: {product.query} | alvo: R$ {product.target_price:.2f} ===")
        catalog_ids = self._catalog_ids(product)
        self.output(f"Produtos de catÃ¡logo encontrados: {len(catalog_ids)}")

        unique_items = {}
        for index, catalog_id in enumerate(catalog_ids):
            if index and self.catalog_delay:
                time.sleep(self.catalog_delay)
            try:
                items = self._collect_items(catalog_id)
            except CatalogProductItemsNotFound:
                self.output(f"Nenhum item retornado para {catalog_id}.")
                continue
            except MercadoLivreError as exc:
                self.output(f"Erro ao consultar itens de {catalog_id}: {exc}")
                continue

            for item in items:
                item_id = item.get("item_id")
                if item_id and item_id not in unique_items:
                    enriched = dict(item)
                    enriched["catalog_product_id"] = catalog_id
                    enriched["link"] = (
                        f"https://www.mercadolivre.com.br/p/{catalog_id}"
                        f"?pdp_filters=item_id:{item_id}"
                    )
                    unique_items[item_id] = enriched

        if not unique_items:
            self.output("AnÃºncios encontrados: 0")
            self.output("Oportunidades atÃ© o preÃ§o-alvo: 0")
            return {"found": 0, "candidates": 0}

        if self.scraper is not None:
            return self._evaluate_items(product, unique_items, self.scraper)

        with ChromeScraper() as browser_scraper:
            return self._evaluate_items(product, unique_items, browser_scraper.scrape_price)

    def _evaluate_items(self, product: Product, unique_items: dict, scraper) -> dict[str, int]:
        matches = []
        for index, item in enumerate(unique_items.values()):
            item_id = item.get("item_id")
            catalog_id = item.get("catalog_product_id")
            seller_id = item.get("seller_id")
            seller_key = str(seller_id).strip() if seller_id is not None else ""
            if seller_key in self.blocked_seller_ids:
                self.output(f"Vendedor bloqueado para {catalog_id} - {item_id}: {seller_key}")
                continue
            if index and self.item_delay:
                time.sleep(self.item_delay)
            try:
                scraped = scraper(catalog_id, item_id)
                final_price = float(scraped["price"])
            except BotBlockedError:
                raise
            except Exception as exc:
                self.output(f"Erro ao consultar {item_id}: {exc}")
                continue

            if final_price <= product.target_price:
                opportunity = dict(item)
                opportunity.update(scraped)
                opportunity["catalog_product_id"] = catalog_id
                opportunity["item_id"] = item_id
                opportunity["link"] = item["link"]
                opportunity["price"] = final_price
                seller_id = opportunity.get("seller_id")
                seller_key = str(seller_id).strip() if seller_id is not None else ""
                if seller_key not in self._seller_evaluations:
                    self._seller_evaluations[seller_key] = self.seller_evaluator(self.api, seller_id)
                seller_evaluation = self._seller_evaluations[seller_key]
                if not seller_evaluation.approved:
                    self.output(f"Vendedor reprovado para {catalog_id} - {item_id}: {seller_evaluation.reason}")
                    continue
                opportunity["seller_evaluation"] = seller_evaluation
                matches.append(opportunity)

        matches.sort(key=lambda item: item["price"])
        self.output(f"AnÃºncios encontrados: {len(unique_items)}")
        self.output(f"Oportunidades atÃ© o preÃ§o-alvo: {len(matches)}")
        for item in matches:
            self.output(f"Nome: {item.get('title')}")
            self.output(f"PreÃ§o final: R$ {item['price']:.2f}")
            self.output(f"PreÃ§o original: R$ {item.get('original_price')}")
            self.output(f"Desconto: {item.get('discount')}%")
            self.output(
                " | ".join(
                    [
                        f"ITEM_ID: {item.get('item_id')}",
                        f"Seller: {item.get('seller_id')}",
                        f"Condition: {item.get('condition')}",
                        f"Listing: {item.get('listing_type_id')}",
                        f"Catalog: {item.get('catalog_product_id')}",
                    ]
                )
            )
            self.output(f"Link: {item['link']}")

        if matches and self.email_sender:
            try:
                self.email_sender(self._email_body(product, matches))
                self.output("E-mail com as oportunidades enviado.")
            except Exception as exc:
                self.output(f"Erro ao enviar e-mail: {exc}")
        return {"found": len(unique_items), "candidates": len(matches)}

    @staticmethod
    def _email_body(product: Product, matches: list[dict]) -> str:
        lines = [
            "OPORTUNIDADES ENCONTRADAS",
            "",
            f"Produto pesquisado: {product.query}",
            f"PreÃ§o-alvo: R$ {product.target_price:.2f}",
            f"Quantidade: {len(matches)}",
            "",
        ]
        for index, item in enumerate(matches, 1):
            lines.extend(
                [
                    f"--- Oportunidade {index} ---",
                    f"Nome: {item.get('title') or '(sem nome)' }",
                    f"PreÃ§o final: R$ {item.get('price'):.2f}",
                    f"PreÃ§o original: {item.get('original_price')}",
                    f"Desconto: {item.get('discount')}%",
                    f"ITEM_ID: {item.get('item_id')}",
                    f"Seller: {item.get('seller_id')}",
                    f"Condition: {item.get('condition')}",
                    f"Listing: {item.get('listing_type_id')}",
                    f"Catalog: {item.get('catalog_product_id')}",
                    f"Reputação: {item['seller_evaluation'].level_id}",
                    f"MercadoLíder: {item['seller_evaluation'].power_seller_status or 'não informado'}",
                    f"Motivo da aprovação: {item['seller_evaluation'].reason}",
                    f"Link: {item.get('link')}",
                    "",
                ]
            )
        return "\n".join(lines)

    def run_catalog_product(self, catalog_product_id: str, limit: int = 100) -> list[dict]:
        self.output(f"\n=== Produto de catÃ¡logo: {catalog_product_id} ===")
        try:
            response = self.api.get_catalog_product_items(catalog_product_id, limit=limit)
        except CatalogProductItemsNotFound as exc:
            self.output(str(exc))
            return []
        except MercadoLivreError as exc:
            self.output(f"Erro ao consultar itens de {catalog_product_id}: {exc}")
            return []

        results = response.get("results", [])
        self.output(f"AnÃºncios vinculados encontrados: {len(results)}")
        for item in results:
            self.output(
                " | ".join(
                    [
                        f"ITEM_ID: {item.get('item_id')}",
                        f"PreÃ§o: {item.get('price')} {item.get('currency_id', '')}".strip(),
                        f"Seller: {item.get('seller_id')}",
                        f"Listing: {item.get('listing_type_id')}",
                    ]
                )
            )
        return results
