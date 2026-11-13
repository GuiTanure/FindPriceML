import unittest
from unittest.mock import Mock, patch

from main import executar_busca
from models import Product
from scrapper import BotBlockedError


class MainAlertTests(unittest.TestCase):
    def store(self):
        store = Mock()
        store.products.return_value = [Product("id", "Casio DW-5600", 200, True, "2026-10-17T00:00:00", ["MLB1"])]
        return store

    @patch("main.send_email")
    @patch("main._alert_window_is_open", return_value=True)
    @patch("main.build_tracker")
    def test_sends_alert_only_for_bot_blocked_error(self, build_tracker, _window, send_email):
        build_tracker.return_value.run_product.side_effect = BotBlockedError("CAPTCHA")

        with self.assertRaises(BotBlockedError):
            executar_busca(self.store())

        send_email.assert_called_once()
        self.assertEqual(send_email.call_args.kwargs["subject"], "ROBÔ PAROU")
        self.assertIn("Casio DW-5600", send_email.call_args.args[0])
        self.assertIn("CAPTCHA", send_email.call_args.args[0])

    @patch("main.send_email")
    @patch("main._alert_window_is_open", return_value=False)
    @patch("main.build_tracker")
    def test_does_not_send_alert_outside_window(self, build_tracker, _window, send_email):
        build_tracker.return_value.run_product.side_effect = BotBlockedError("CAPTCHA")

        with self.assertRaises(BotBlockedError):
            executar_busca(self.store())

        send_email.assert_not_called()

    @patch("main.send_email")
    @patch("main.build_tracker")
    def test_does_not_send_alert_for_generic_error(self, build_tracker, send_email):
        build_tracker.return_value.run_product.side_effect = RuntimeError("falha temporária")

        with self.assertRaises(RuntimeError):
            executar_busca(self.store())

        send_email.assert_not_called()


if __name__ == "__main__":
    unittest.main()
