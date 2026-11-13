import unittest
from unittest.mock import Mock

from ml_api import AuthenticationError, CatalogProductItemsNotFound, MercadoLivreAPI


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload
        self.headers = {}

    def json(self):
        return self.payload


class ApiTests(unittest.TestCase):
    def make_api(self, session):
        return MercadoLivreAPI(
            {"client_id": "id", "client_secret": "secret", "access_token": "token"},
            Mock(),
            session,
        )

    def test_products_search_uses_catalog_parameters(self):
        session = Mock()
        session.request.return_value = FakeResponse(200, {"results": [{"id": "MLB22598384"}]})
        result = self.make_api(session).search_catalog_products("Casio GA-2100-4ACR")
        self.assertEqual(result["results"][0]["id"], "MLB22598384")
        self.assertEqual(session.request.call_args.args[1], "https://api.mercadolibre.com/products/search")
        self.assertEqual(
            session.request.call_args.kwargs["params"],
            {"status": "active", "site_id": "MLB", "q": "Casio GA-2100-4ACR", "limit": 20},
        )

    def test_401_refreshes_and_retries(self):
        session = Mock()
        session.request.side_effect = [FakeResponse(401, {}), FakeResponse(200, {"results": []})]
        session.post.return_value = FakeResponse(200, {"access_token": "new", "refresh_token": "new-refresh"})
        saver = Mock()
        api = MercadoLivreAPI(
            {"client_id": "id", "client_secret": "secret", "access_token": "old", "refresh_token": "refresh"},
            saver,
            session,
        )
        api.search_catalog_products("Casio")
        self.assertEqual(api.access_token, "new")
        self.assertEqual(saver.call_args.args[0:2], ("new", "new-refresh"))

    def test_403_error_is_explicit_and_safe(self):
        session = Mock()
        response = FakeResponse(403, {"message": "forbidden", "error": "forbidden", "status": 403})
        response.headers = {"x-request-id": "request-123"}
        session.request.return_value = response
        with self.assertRaises(AuthenticationError) as error:
            self.make_api(session).search_catalog_products("Casio")
        text = str(error.exception)
        self.assertIn("GET /products/search", text)
        self.assertIn("HTTP 403", text)
        self.assertNotIn("token", text)
        self.assertNotIn("secret", text)

    def test_catalog_product_items_uses_catalog_endpoint(self):
        session = Mock()
        session.request.return_value = FakeResponse(
            200,
            {"paging": {"total": 1}, "results": [{"item_id": "MLB123", "price": 200, "seller_id": 7}]},
        )
        result = self.make_api(session).get_catalog_product_items("MLB22598384")
        self.assertEqual(result["results"][0]["item_id"], "MLB123")
        self.assertEqual(session.request.call_args.args[1], "https://api.mercadolibre.com/products/MLB22598384/items")
        self.assertEqual(session.request.call_args.kwargs["params"], {"limit": 100, "offset": 0})

    def test_catalog_product_without_winners_is_explicit(self):
        session = Mock()
        session.request.return_value = FakeResponse(404, {"message": "No winners found", "status": 404})
        with self.assertRaises(CatalogProductItemsNotFound):
            self.make_api(session).get_catalog_product_items("MLB22598384")


if __name__ == "__main__":
    unittest.main()
