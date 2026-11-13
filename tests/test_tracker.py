import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

from ml_api import CatalogProductItemsNotFound
from models import Product
from scrapper import BotBlockedError, ScraperError
from seller_evaluator import SellerEvaluation
from tracker import Tracker


class TrackerTests(unittest.TestCase):
    @staticmethod
    def approved_seller(_api, seller_id):
        return SellerEvaluation(True, str(seller_id), "5_green", "gold", "Vendedor aprovado pela reputação.", 25)

    def product(self, target=320, catalog="MLB22598384"):
        catalog_ids = [catalog] if catalog else []
        return Product("produto", "Casio GA-2100-4ACR", target, True, "2026-09-28T00:00:00", catalog_ids)

    def test_saved_catalog_id_is_used_without_catalog_search(self):
        api = Mock()
        api.get_catalog_product_items.return_value = {
            "results": [{"item_id": "MLB100", "price": 408.45, "seller_id": 7}]
        }
        scraper = Mock(return_value={"price": 347.18, "original_price": 408.45, "discount": 15.0, "title": "Casio G-Shock"})
        output = []
        result = Tracker(api, output=output.append, scraper=scraper, seller_evaluator=self.approved_seller).run_product(self.product(350))
        api.search_catalog_products.assert_not_called()
        api.get_catalog_product_items.assert_called_once_with("MLB22598384", offset=0, limit=100)
        scraper.assert_called_once_with("MLB22598384", "MLB100")
        self.assertEqual(result, {"found": 1, "candidates": 1})

    def test_catalog_product_without_items_is_ignored(self):
        api = Mock()
        api.get_catalog_product_items.side_effect = CatalogProductItemsNotFound("No winners found")
        scraper = Mock()
        result = Tracker(api, output=lambda _: None, scraper=scraper).run_product(self.product())
        scraper.assert_not_called()
        self.assertEqual(result, {"found": 0, "candidates": 0})

    def test_items_are_paginated_and_deduplicated(self):
        api = Mock()
        api.get_catalog_product_items.side_effect = [
            {"paging": {"total": 3}, "results": [
                {"item_id": "MLB100", "price": 408.45, "seller_id": 1},
                {"item_id": "MLB200", "price": 250, "seller_id": 2},
            ]},
            {"paging": {"total": 3}, "results": [
                {"item_id": "MLB100", "price": 408.45, "seller_id": 9},
                {"item_id": "MLB300", "price": 500, "seller_id": 3},
            ]},
        ]
        scraper = Mock(side_effect=lambda _catalog, item_id: {"price": {"MLB100": 300.0, "MLB200": 321.0, "MLB300": 280.0}[item_id]})
        result = Tracker(api, output=lambda _: None, scraper=scraper, seller_evaluator=self.approved_seller).run_product(self.product(300))
        self.assertEqual(result, {"found": 3, "candidates": 2})
        self.assertEqual(api.get_catalog_product_items.call_args_list[1].kwargs, {"offset": 2, "limit": 100})
        self.assertEqual([call.args[1] for call in scraper.call_args_list], ["MLB100", "MLB200", "MLB300"])

    def test_scraper_error_does_not_stop_other_items(self):
        api = Mock()
        api.get_catalog_product_items.return_value = {"results": [{"item_id": "MLB100"}, {"item_id": "MLB200"}]}
        scraper = Mock(side_effect=[RuntimeError("page unavailable"), {"price": 200.0}])
        result = Tracker(api, output=lambda _: None, scraper=scraper, seller_evaluator=self.approved_seller).run_product(self.product())
        self.assertEqual(result, {"found": 2, "candidates": 1})

    def test_missing_price_scraper_error_does_not_stop_other_items(self):
        api = Mock()
        api.get_catalog_product_items.return_value = {"results": [{"item_id": "MLB100"}, {"item_id": "MLB200"}]}
        scraper = Mock(side_effect=[ScraperError("Preço não disponível"), {"price": 200.0}])

        result = Tracker(api, output=lambda _: None, scraper=scraper, seller_evaluator=self.approved_seller).run_product(self.product())

        self.assertEqual(result, {"found": 2, "candidates": 1})

    def test_blocked_seller_is_skipped_before_scraper_and_evaluation(self):
        api = Mock()
        api.get_catalog_product_items.return_value = {
            "results": [{"item_id": "MLB100", "seller_id": 999}, {"item_id": "MLB200", "seller_id": 7}]
        }
        scraper = Mock(return_value={"price": 200.0})
        seller_evaluator = Mock(side_effect=self.approved_seller)

        with tempfile.TemporaryDirectory() as directory:
            blocked_path = Path(directory) / "blocked_sellers.json"
            blocked_path.write_text(json.dumps({"seller_ids": ["999"]}), encoding="utf-8")
            result = Tracker(
                api,
                output=lambda _: None,
                scraper=scraper,
                seller_evaluator=seller_evaluator,
                blocked_sellers_path=blocked_path,
            ).run_product(self.product())

        self.assertEqual(result, {"found": 2, "candidates": 1})
        scraper.assert_called_once_with("MLB22598384", "MLB200")
        seller_evaluator.assert_called_once_with(api, 7)

    def test_bot_blocked_error_is_propagated(self):
        api = Mock()
        api.get_catalog_product_items.return_value = {"results": [{"item_id": "MLB100"}]}
        scraper = Mock(side_effect=BotBlockedError("verificação do Mercado Livre"))

        with self.assertRaises(BotBlockedError):
            Tracker(api, output=lambda _: None, scraper=scraper, seller_evaluator=self.approved_seller).run_product(self.product())

    def test_email_receives_all_opportunity_data(self):
        api = Mock()
        api.get_catalog_product_items.return_value = {
            "results": [{"item_id": "MLB100", "seller_id": 7, "condition": "new", "listing_type_id": "gold_special"}]
        }
        scraper = Mock(return_value={"price": 276.0, "original_price": 299.9, "discount": 8.0, "title": "Casio G-Shock"})
        email_sender = Mock()
        Tracker(api, output=lambda _: None, scraper=scraper, email_sender=email_sender, seller_evaluator=self.approved_seller).run_product(self.product())
        email_sender.assert_called_once()
        body = email_sender.call_args.args[0]
        self.assertIn("Casio G-Shock", body)
        self.assertIn("R$ 276.00", body)
        self.assertIn("MLB100", body)
        self.assertIn("https://www.mercadolivre.com.br/p/MLB22598384?pdp_filters=item_id:MLB100", body)


if __name__ == "__main__":
    unittest.main()
