import json
import tempfile
import unittest
from pathlib import Path

from config import ConfigStore, ConfigurationError, parse_price


class ConfigTests(unittest.TestCase):
    def test_parse_brazilian_prices(self):
        self.assertEqual(parse_price("R$ 320,00"), 320.0)
        self.assertEqual(parse_price("1.234,56"), 1234.56)

    def test_add_and_persist_products(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            store = ConfigStore(path)
            store.add_product("Casio GA-2100", 320, ["MLB22598384", "MLB24066039"])
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["products"]), 1)
            self.assertEqual(data["products"][0]["target_price"], 320.0)
            self.assertEqual(data["products"][0]["catalog_product_ids"], ["MLB22598384", "MLB24066039"])

    def test_rejects_empty_query_and_invalid_price(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            with self.assertRaises(ConfigurationError):
                store.add_product("", 10)
            with self.assertRaises(ConfigurationError):
                store.add_product("Produto", 0)
