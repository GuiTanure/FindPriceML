import unittest
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

from oauth import MercadoLivreOAuth


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            "access_token": "access-value",
            "refresh_token": "refresh-value",
            "expires_in": 21600,
        }


class OAuthTests(unittest.TestCase):
    def test_authorization_url_contains_state_and_pkce(self):
        oauth = MercadoLivreOAuth("client-id", "secret", "https://tunnel.example/callback")
        _, challenge = oauth._pkce_pair()
        url = oauth.authorization_url("state-value", challenge)
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query["client_id"], ["client-id"])
        self.assertEqual(query["redirect_uri"], ["https://tunnel.example/callback"])
        self.assertEqual(query["state"], ["state-value"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["code_challenge"], [challenge])

    def test_exchange_sends_authorization_code_and_verifier(self):
        session = Mock()
        session.post.return_value = FakeResponse()
        oauth = MercadoLivreOAuth("client-id", "secret", "https://tunnel.example/callback", session=session)
        tokens = oauth.exchange_code("authorization-code", "pkce-verifier")
        self.assertEqual(tokens["access_token"], "access-value")
        data = session.post.call_args.kwargs["data"]
        self.assertEqual(data["grant_type"], "authorization_code")
        self.assertEqual(data["code"], "authorization-code")
        self.assertEqual(data["code_verifier"], "pkce-verifier")
        self.assertNotIn("secret", str(tokens))

