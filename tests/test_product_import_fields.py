import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from src.browser.automation import (
    decimalizar_valor_campo,
    formatar_custo_xml,
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

    def test_formats_xml_cost_for_gdoor(self):
        self.assertEqual(formatar_custo_xml("12.50"), "12,50")
        self.assertEqual(formatar_custo_xml("100"), "100")
        self.assertEqual(formatar_custo_xml("1,25"), "1,25")

    def test_reads_formatted_cost_values(self):
        self.assertEqual(decimalizar_valor_campo("12,50"), Decimal("12.50"))
        self.assertEqual(
            decimalizar_valor_campo("R$ 1.234,50"),
            Decimal("1234.50"),
        )
        self.assertIsNone(decimalizar_valor_campo(""))

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


if __name__ == "__main__":
    unittest.main()
