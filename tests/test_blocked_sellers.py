import json
import tempfile
import unittest
from pathlib import Path

from blocked_sellers import load_blocked_seller_ids
from config import ConfigurationError


class BlockedSellerTests(unittest.TestCase):
    def test_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(load_blocked_seller_ids(Path(directory) / "missing.json"), frozenset())

    def test_normalizes_ids_and_removes_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blocked.json"
            path.write_text(json.dumps({"seller_ids": [123, " 123 ", "456", ""]}), encoding="utf-8")

            self.assertEqual(load_blocked_seller_ids(path), frozenset({"123", "456"}))

    def test_invalid_format_raises_configuration_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blocked.json"
            path.write_text(json.dumps(["123"]), encoding="utf-8")

            with self.assertRaises(ConfigurationError):
                load_blocked_seller_ids(path)


if __name__ == "__main__":
    unittest.main()
