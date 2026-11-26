import tempfile
import unittest
from pathlib import Path

from xml.parsers.expat import ExpatError

from src.nfe.xml_storage import (
    copiar_xml_para_notas,
    remover_xml_para_consulta,
)


def xml_nfe(numero_nota):
    return f"""\
<NFe>
  <infNFe>
    <ide><nNF>{numero_nota}</nNF></ide>
    <emit><CNPJ>12345678000199</CNPJ></emit>
    <det>
      <prod>
        <cProd>123</cProd>
        <xProd>Produto teste</xProd>
        <cEAN>SEM GTIN</cEAN>
        <NCM>12345678</NCM>
        <uCom>UN</uCom>
        <qCom>1</qCom>
        <vUnCom>10.00</vUnCom>
        <CFOP>5102</CFOP>
      </prod>
      <imposto />
    </det>
    <total><ICMSTot><vNF>10.00</vNF></ICMSTot></total>
  </infNFe>
</NFe>
"""


class XmlStorageTests(unittest.TestCase):
    def test_copies_valid_xml_and_does_not_duplicate_same_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "origem" / "nota.xml"
            source.parent.mkdir()
            source.write_text(xml_nfe("1"), encoding="utf-8")
            notes_dir = root / "notasXMLs"

            destination, copied = copiar_xml_para_notas(source, notes_dir)
            repeated_destination, repeated_copy = copiar_xml_para_notas(
                source,
                notes_dir,
            )

            self.assertTrue(copied)
            self.assertFalse(repeated_copy)
            self.assertEqual(destination, repeated_destination)
            self.assertEqual(destination.read_text(encoding="utf-8"), xml_nfe("1"))
            self.assertTrue(source.exists())

    def test_different_xml_with_same_name_gets_a_suffix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_source = root / "first" / "nota.xml"
            second_source = root / "second" / "nota.xml"
            first_source.parent.mkdir()
            second_source.parent.mkdir()
            first_source.write_text(xml_nfe("1"), encoding="utf-8")
            second_source.write_text(xml_nfe("2"), encoding="utf-8")
            notes_dir = root / "notasXMLs"

            first_destination, _ = copiar_xml_para_notas(
                first_source,
                notes_dir,
            )
            second_destination, copied = copiar_xml_para_notas(
                second_source,
                notes_dir,
            )

            self.assertTrue(copied)
            self.assertEqual(first_destination.name, "nota.xml")
            self.assertEqual(second_destination.name, "nota_1.xml")
            self.assertEqual(first_destination.read_text(encoding="utf-8"), xml_nfe("1"))
            self.assertEqual(second_destination.read_text(encoding="utf-8"), xml_nfe("2"))

    def test_rejects_malformed_xml_without_creating_notes_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "invalid.xml"
            source.write_text("<NFe>", encoding="utf-8")
            notes_dir = root / "notasXMLs"

            with self.assertRaises(ExpatError):
                copiar_xml_para_notas(source, notes_dir)

            self.assertFalse(notes_dir.exists())

    def test_removes_staged_xml_without_deleting_original(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "origem" / "nota.xml"
            source.parent.mkdir()
            source.write_text(xml_nfe("1"), encoding="utf-8")
            notes_dir = root / "notasXMLs"
            destination, _ = copiar_xml_para_notas(source, notes_dir)

            remover_xml_para_consulta(destination, notes_dir)

            self.assertTrue(source.exists())
            self.assertFalse(destination.exists())

    def test_rejects_removing_xml_outside_notes_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outside_xml = root / "nota.xml"
            outside_xml.write_text(xml_nfe("1"), encoding="utf-8")
            notes_dir = root / "notasXMLs"

            with self.assertRaises(ValueError):
                remover_xml_para_consulta(outside_xml, notes_dir)

            self.assertTrue(outside_xml.exists())


if __name__ == "__main__":
    unittest.main()
