import unittest
from unittest.mock import Mock, call, patch

from src.browser.automation import abrir_secao_ibscbs, preencher_ibscbs


class PreencherIBSCBSTests(unittest.TestCase):
    def test_preenche_aliquotas_do_xml_sem_base_de_calculo(self):
        campo_uf = Mock()
        campo_municipio = Mock()
        campo_uf.input_value.return_value = "0,1000"
        campo_municipio.input_value.return_value = "0,2000"
        page = Mock()
        page.locator.side_effect = {
            'input[name="ibsCbs.ibs_uf_rate"]': campo_uf,
            'input[name="ibsCbs.ibs_city_rate"]': campo_municipio,
        }.get
        produto = {
            "nome": "Produto teste",
            "impostos": {
                "IBSCBS": {
                    "CST": "000",
                    "cClassTrib": "000001",
                    "gIBSCBS": {
                        "vBC": "123.45",
                        "gIBSUF": {"pIBSUF": "0.1000"},
                        "gIBSMun": {"pIBSMun": "0.2000"},
                    },
                },
            },
        }

        with (
            patch("src.browser.automation.abrir_secao_ibscbs") as open_section,
            patch(
                "src.browser.automation.selecionar_opcao_tributo"
            ) as select,
        ):
            preencher_ibscbs(page, produto)

        open_section.assert_called_once_with(page)
        self.assertEqual(campo_uf.fill.call_args, call("0,1000"))
        self.assertEqual(campo_municipio.fill.call_args, call("0,2000"))
        self.assertEqual(
            page.locator.call_args_list,
            [
                call('input[name="ibsCbs.ibs_uf_rate"]'),
                call('input[name="ibsCbs.ibs_city_rate"]'),
            ],
        )
        page.get_by_role.assert_any_call(
            "button", name="IBS UF", exact=True
        )
        page.get_by_role.assert_any_call(
            "button", name="IBS Município", exact=True
        )
        select.assert_has_calls(
            [
                call(page, "CST", "000", usar_ultimo=True),
                call(page, "Código de Classificação Tributária", "000001"),
            ]
        )

    def test_abre_a_secao_ibscbs_antes_de_continuar(self):
        campo_cst = Mock()
        campo_cst.is_visible.return_value = False
        controle = Mock()
        controle.is_visible.return_value = True
        grupo = Mock()
        grupo.count.return_value = 1
        grupo.nth.return_value = controle
        page = Mock()
        page.locator.return_value = campo_cst
        page.get_by_role.return_value = grupo

        abrir_secao_ibscbs(page)

        page.locator.assert_called_once_with('mat-select[name="ibs_cbs_cst"]')
        page.get_by_role.assert_any_call(
            "tab", name="IBS/CBS", exact=True
        )
        controle.click.assert_called_once_with()
        campo_cst.wait_for.assert_called_once_with(
            state="visible",
            timeout=5000,
        )

    def test_informa_quais_dados_ibscbs_faltam_no_xml(self):
        produto = {
            "nome": "Produto teste",
            "impostos": {"IBSCBS": {}},
        }

        with self.assertRaisesRegex(
            RuntimeError,
            "CST, Código de Classificação Tributária, Alíquota UF, "
            "Alíquota Município",
        ):
            preencher_ibscbs(Mock(), produto)


if __name__ == "__main__":
    unittest.main()
