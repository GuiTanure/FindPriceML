import json
import unittest
from unittest.mock import Mock, patch

from scrapper import BotBlockedError, ChromeScraper, ScraperError, build_public_url, parse_nordic_context


class ScraperTests(unittest.TestCase):
    def context_data(self, value=347.18, original=408.45):
        context = {
            "title": "Produto | Mercado Livre",
            "appProps": {
                "pageProps": {
                    "initialState": {
                        "components": {
                            "header": {"title": "Casio G-Shock"},
                            "price": {
                                "price": {
                                    "value": value,
                                    "original_value": original,
                                }
                            },
                        }
                    }
                }
            },
        }
        return "_n.ctx.r=" + json.dumps(context) + ";_n.ctx.r.assets.manifest=new Map([]);"

    def test_builds_public_url(self):
        self.assertEqual(
            build_public_url("MLB26740275", "MLB5260239711"),
            "https://www.mercadolivre.com.br/p/MLB26740275?pdp_filters=item_id:MLB5260239711",
        )

    def test_parses_final_price_context(self):
        result = parse_nordic_context(
            self.context_data(),
            "MLB26740275",
            "MLB5260239711",
            "https://example",
        )
        self.assertEqual(result["price"], 347.18)
        self.assertEqual(result["original_price"], 408.45)
        self.assertEqual(result["title"], "Casio G-Shock")

    def test_invalid_context_raises(self):
        with self.assertRaises(ScraperError):
            parse_nordic_context("_n.ctx.r={invalid", "MLB1", "MLB2", "https://example")

    def test_missing_price_is_recoverable_scraper_error(self):
        context = {
            "appProps": {
                "pageProps": {
                    "initialState": {
                        "components": {"price": {}}
                    }
                }
            }
        }

        with self.assertRaises(ScraperError) as error:
            parse_nordic_context(
                "_n.ctx.r=" + json.dumps(context),
                "MLB1",
                "MLB2",
                "https://example",
            )

        self.assertNotIsInstance(error.exception, BotBlockedError)

    @patch("scrapper.time.monotonic", side_effect=[0, 31])
    def test_raises_bot_blocked_after_nordic_timeout(self, _monotonic):
        page = Mock()
        page.locator.return_value.count.return_value = 0
        scraper = ChromeScraper()
        scraper.page = page

        with self.assertRaises(BotBlockedError):
            scraper.scrape_price("MLB1", "MLB2")


if __name__ == "__main__":
    unittest.main()
