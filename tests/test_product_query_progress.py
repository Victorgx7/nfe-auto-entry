import unittest
from pathlib import Path
from unittest.mock import call, patch

from src.browser.automation import consultar_produtos_no_sistema


class ProductQueryProgressTests(unittest.TestCase):
    def test_reports_total_consulted_and_missing_products(self):
        products = [
            {"codigo": "100", "nome": "Produto existente"},
            {"codigo": "200", "nome": "Produto ausente"},
        ]
        progress = []
        page = object()

        with (
            patch(
                "src.browser.automation.carregar_configuracao",
                return_value={},
            ),
            patch(
                "src.browser.automation.ler_produtos_xml",
                return_value=products,
            ),
            patch(
                "src.browser.automation.consultar_produto_na_lista",
                side_effect=[True, False, False],
            ) as consulta,
        ):
            resultados = consultar_produtos_no_sistema(
                [Path("nota.xml")],
                page=page,
                progress_callback=lambda consultados, total, faltantes: (
                    progress.append((consultados, total, faltantes))
                ),
            )

        self.assertEqual(
            progress,
            [(0, 2, 0), (1, 2, 0), (2, 2, 1)],
        )
        self.assertEqual(
            [resultado["existe"] for resultado in resultados],
            [True, False],
        )
        self.assertEqual(
            consulta.call_args_list,
            [
                call(page, "Produto existente"),
                call(page, "Produto ausente"),
                call(page, "200", timeout_segundos=2),
            ],
        )


if __name__ == "__main__":
    unittest.main()
