import os
import unittest
from unittest.mock import patch

from src.browser.automation import (
    carregar_configuracao,
    verificar_redirecionamento_atualizacao,
)


class AutomationConfigTests(unittest.TestCase):
    def test_base_url_with_login_path_is_reduced_to_origin(self):
        variables = {
            "GDOOR_BASE_URL": "https://app.gdoorweb.com.br/login",
            "GDOOR_EMAIL": "test@example.com",
            "GDOOR_PASSWORD": "test-password",
        }
        with patch.dict(os.environ, variables):
            configuracao = carregar_configuracao()

        self.assertEqual(
            configuracao["base_url"],
            "https://app.gdoorweb.com.br",
        )

    def test_database_update_redirect_is_reported(self):
        page = type(
            "Page",
            (),
            {"url": "https://app.gdoorweb.com.br/atualizacao-banco-de-dados"},
        )()

        with self.assertRaisesRegex(
            RuntimeError,
            "atualização do banco de dados",
        ):
            verificar_redirecionamento_atualizacao(page)


if __name__ == "__main__":
    unittest.main()
