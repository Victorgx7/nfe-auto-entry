import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from threading import Event
from unittest.mock import Mock, patch

from src.browser.automation import (
    codigo_origem_corresponde_opcao,
    decimalizar_valor_campo,
    formatar_custo_xml,
    importar_produtos_no_sistema,
    normalizar_codigo_ncm,
    preencher_campos_iniciais_produto,
    unidade_padrao_corresponde_opcao,
)
from src.nfe.parser import ler_produtos_xml


class ProductImportFieldTests(unittest.TestCase):
    def test_matches_default_unit_option(self):
        self.assertTrue(
            unidade_padrao_corresponde_opcao("UNID - UNIDADE")
        )
        self.assertFalse(
            unidade_padrao_corresponde_opcao("UN - UNIDADE")
        )
        self.assertFalse(
            unidade_padrao_corresponde_opcao("PC - PEÇA")
        )

    def test_matches_icms_origin_by_xml_code(self):
        self.assertTrue(
            codigo_origem_corresponde_opcao(
                "0 - Nacional, exceto as indicadas nos códigos 3, 4, 5 e 8",
                "0",
            )
        )
        self.assertFalse(
            codigo_origem_corresponde_opcao(
                "1 - Estrangeira - Importação direta",
                "0",
            )
        )

    def test_normalizes_ncm_formatting(self):
        self.assertEqual(normalizar_codigo_ncm("12345678"), "12345678")
        self.assertEqual(normalizar_codigo_ncm("1234.56.78"), "12345678")
        self.assertEqual(normalizar_codigo_ncm(""), "")

    def test_formats_xml_cost_for_gdoor(self):
        self.assertEqual(formatar_custo_xml("12.50"), "12,50")
        self.assertEqual(formatar_custo_xml("100"), "100,00")
        self.assertEqual(formatar_custo_xml("1,25"), "1,25")
        self.assertEqual(
            formatar_custo_xml("136.5598803700"),
            "136,56",
        )

    def test_reads_formatted_cost_values(self):
        self.assertEqual(decimalizar_valor_campo("12,50"), Decimal("12.50"))
        self.assertEqual(
            decimalizar_valor_campo("R$ 1.234,50"),
            Decimal("1234.50"),
        )
        self.assertIsNone(decimalizar_valor_campo(""))

    def test_saves_after_manual_correction_continues(self):
        page = Mock()
        product = {"codigo": "100", "nome": "Produto teste"}
        aguardou_correcao = Mock(return_value=True)
        erro_preenchimento = RuntimeError("campo inválido")

        with (
            patch(
                "src.browser.automation.carregar_configuracao",
                return_value={"products_url": "https://gdoor.test/produtos"},
            ),
            patch(
                "src.browser.automation.preencher_dados_produto",
                side_effect=erro_preenchimento,
            ),
            patch("src.browser.automation.salvar_produto") as salvar,
        ):
            preencher_campos_iniciais_produto(
                page,
                product,
                aguardar_correcao_manual=aguardou_correcao,
            )

        aguardou_correcao.assert_called_once_with(product, erro_preenchimento)
        salvar.assert_called_once_with(page, product)

    def test_does_not_save_when_manual_correction_is_cancelled(self):
        page = Mock()
        product = {"codigo": "100", "nome": "Produto teste"}

        with (
            patch(
                "src.browser.automation.carregar_configuracao",
                return_value={"products_url": "https://gdoor.test/produtos"},
            ),
            patch(
                "src.browser.automation.preencher_dados_produto",
                side_effect=RuntimeError("campo inválido"),
            ),
            patch("src.browser.automation.salvar_produto") as salvar,
        ):
            with self.assertRaisesRegex(
                InterruptedError,
                "interrompido durante a correção manual",
            ):
                preencher_campos_iniciais_produto(
                    page,
                    product,
                    aguardar_correcao_manual=lambda *_args: False,
                )

        salvar.assert_not_called()

    def test_reads_gtin_fallback_and_icms_origin(self):
        xml = """\
<NFe>
  <infNFe>
    <det>
      <prod>
        <cProd>123</cProd>
        <xProd>Produto teste</xProd>
        <cEAN>SEM GTIN</cEAN>
        <cEANTrib>7891234567890</cEANTrib>
        <NCM>12345678</NCM>
        <uCom>UN</uCom>
        <vUnCom>12.50</vUnCom>
        <CFOP>5102</CFOP>
      </prod>
      <imposto>
        <ICMS>
          <ICMS00>
            <orig>0</orig>
            <CST>00</CST>
          </ICMS00>
        </ICMS>
      </imposto>
    </det>
  </infNFe>
</NFe>
"""
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "produto.xml"
            caminho.write_text(xml, encoding="utf-8")
            produto = ler_produtos_xml(caminho)[0]

        self.assertEqual(produto["ean"], "7891234567890")
        self.assertEqual(produto["impostos"]["ICMS"]["orig"], "0")

    def test_reports_product_registration_progress(self):
        products = [
            {"codigo": "100", "nome": "Produto teste"},
        ]
        progress = []

        with (
            patch(
                "src.browser.automation.carregar_configuracao",
                return_value={},
            ),
            patch(
                "src.browser.automation.ler_produtos_xml",
                return_value=products,
            ),
            patch("src.browser.automation.preencher_campos_iniciais_produto"),
        ):
            result = importar_produtos_no_sistema(
                Path("nota.xml"),
                page=object(),
                progress_callback=lambda *evento: progress.append(evento),
            )

        self.assertEqual(result, products)
        self.assertEqual(
            progress,
            [
                (0, 1, None, "preparando"),
                (1, 1, products[0], "processando"),
                (1, 1, products[0], "enviado"),
            ],
        )

    def test_reports_product_registration_failure(self):
        product = {"codigo": "100", "nome": "Produto teste"}
        progress = []

        with (
            patch(
                "src.browser.automation.carregar_configuracao",
                return_value={},
            ),
            patch(
                "src.browser.automation.ler_produtos_xml",
                return_value=[product],
            ),
            patch(
                "src.browser.automation.preencher_campos_iniciais_produto",
                side_effect=RuntimeError("falha no cadastro"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "falha no cadastro"):
                importar_produtos_no_sistema(
                    Path("nota.xml"),
                    page=object(),
                    progress_callback=lambda *evento: progress.append(evento),
                )

        self.assertEqual(progress[-1], (1, 1, product, "erro"))

    def test_stops_registration_between_products(self):
        products = [
            {"codigo": "100", "nome": "Produto 1"},
            {"codigo": "200", "nome": "Produto 2"},
        ]
        progress = []
        stop_event = Event()

        def capture_progress(*evento):
            progress.append(evento)
            if evento[-1] == "enviado":
                stop_event.set()

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
                "src.browser.automation.preencher_campos_iniciais_produto",
            ) as preencher,
        ):
            result = importar_produtos_no_sistema(
                Path("nota.xml"),
                page=object(),
                progress_callback=capture_progress,
                stop_event=stop_event,
            )

        self.assertEqual(result, products[:1])
        preencher.assert_called_once()
        self.assertEqual(progress[-1], (1, 2, None, "interrompido"))


if __name__ == "__main__":
    unittest.main()
