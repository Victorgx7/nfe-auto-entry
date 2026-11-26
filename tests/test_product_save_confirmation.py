import unittest
from unittest.mock import Mock

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from src.browser.automation import aguardar_confirmacao_salvamento


class ProductSaveConfirmationTests(unittest.TestCase):
    def test_waits_for_success_message_in_overlay(self):
        confirmacao = Mock()
        overlay = Mock()
        overlay.get_by_text.return_value = confirmacao
        page = Mock()
        page.locator.return_value = overlay
        produto = {"codigo": "100", "nome": "Produto teste"}

        aguardar_confirmacao_salvamento(page, produto)

        page.locator.assert_called_once_with(".cdk-overlay-container")
        confirmacao.wait_for.assert_called_once_with(
            state="visible",
            timeout=10000,
        )

    def test_raises_when_save_is_not_confirmed(self):
        confirmacao = Mock()
        confirmacao.wait_for.side_effect = PlaywrightTimeout("not visible")
        overlay = Mock()
        overlay.get_by_text.return_value = confirmacao
        page = Mock()
        page.locator.return_value = overlay

        with self.assertRaisesRegex(
            RuntimeError,
            "não confirmou o salvamento do produto 100 - Produto teste",
        ):
            aguardar_confirmacao_salvamento(
                page,
                {"codigo": "100", "nome": "Produto teste"},
            )


if __name__ == "__main__":
    unittest.main()
