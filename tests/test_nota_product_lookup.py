import unittest
from unittest.mock import Mock, call

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from src.browser.automation import buscar_produto_por_codigo_ou_gtin


class NotaProductLookupTests(unittest.TestCase):
    def test_searches_by_gtin_and_confirms_with_enter(self):
        campo = Mock()
        page = Mock()
        page.locator.return_value = campo
        produto = {"codigo": "100", "ean": "7891234567890"}

        encontrado = buscar_produto_por_codigo_ou_gtin(page, produto)

        self.assertTrue(encontrado)
        page.locator.assert_called_once_with(
            'input[data-placeholder="Código/GTIN"]'
        )
        campo.wait_for.assert_called_once_with(
            state="visible",
            timeout=2000,
        )
        campo.fill.assert_called_once_with("7891234567890")
        campo.press.assert_called_once_with("Enter")

    def test_searches_by_product_code_when_gtin_is_missing(self):
        campo = Mock()
        page = Mock()
        page.locator.return_value = campo

        self.assertTrue(
            buscar_produto_por_codigo_ou_gtin(
                page,
                {"codigo": "100", "ean": "SEM GTIN"},
            )
        )
        campo.fill.assert_called_once_with("100")
        campo.press.assert_called_once_with("Enter")

    def test_does_not_search_when_code_and_gtin_are_missing(self):
        page = Mock()

        self.assertFalse(
            buscar_produto_por_codigo_ou_gtin(page, {"ean": "SEM GTIN"})
        )
        page.locator.assert_not_called()

    def test_falls_back_when_gtin_field_is_not_visible(self):
        campo = Mock()
        campo.wait_for.side_effect = PlaywrightTimeout("not visible")
        page = Mock()
        page.locator.return_value = campo

        self.assertFalse(
            buscar_produto_por_codigo_ou_gtin(
                page,
                {"ean": "7891234567890"},
            )
        )
        campo.fill.assert_not_called()
        campo.press.assert_not_called()


if __name__ == "__main__":
    unittest.main()
