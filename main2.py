import os
import shutil
import time
from decimal import Decimal
from pathlib import Path
from xml.parsers.expat import ExpatError

import xmltodict
from dotenv import load_dotenv
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout, sync_playwright

load_dotenv()

# Configurações externas: nunca armazene credenciais ou URLs privadas no código.
BASE_URL = os.getenv("GDOOR_BASE_URL", "").rstrip("/")
LOGIN_EMAIL = os.getenv("GDOOR_EMAIL", "")
LOGIN_PASSWORD = os.getenv("GDOOR_PASSWORD", "")


def validar_configuracao():
    ausentes = [
        nome for nome, valor in {
            "GDOOR_BASE_URL": BASE_URL,
            "GDOOR_EMAIL": LOGIN_EMAIL,
            "GDOOR_PASSWORD": LOGIN_PASSWORD,
        }.items() if not valor
    ]
    if ausentes:
        raise RuntimeError(
            "Configure as variáveis no arquivo .env: " + ", ".join(ausentes)
        )


## --- PASSO 1: LER O XML ---
def ler_xml_nfe(caminho_arquivo):
    with open(caminho_arquivo, "rb") as f:
        doc = xmltodict.parse(f)

    if "nfeProc" in doc:
        nfe = doc["nfeProc"]["NFe"]
    elif "NFe" in doc:
        nfe = doc["NFe"]
    else:
        raise ValueError("Formato de XML não reconhecido: nó NFe não encontrado")

    inf_nfe = nfe["infNFe"]
    itens_raw = inf_nfe["det"]
    if isinstance(itens_raw, dict):
        itens_raw = [itens_raw]

    produtos = []
    for item in itens_raw:
        prod = item["prod"]
        produtos.append({
            "codigo": prod["cProd"],
            "nome": prod["xProd"],
            "quantidade": prod["qCom"],
            "valor_unitario": prod["vUnCom"],
            "codigo_fiscal": prod["CFOP"]
        })

    return {
        "numero_nota": inf_nfe["ide"]["nNF"],
        "cnpj_emitente": inf_nfe["emit"]["CNPJ"],
        "valor_total": inf_nfe["total"]["ICMSTot"]["vNF"],
        "produtos": produtos,
        "codigo_fiscal": [produto["codigo_fiscal"] for produto in produtos]
    }


# --- PASSO 2: DIGITAR NO SISTEMA WEB ---
def lancar_no_sistema(dados_nota):
    validar_configuracao()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        id_nota = input("Informe o ID da nota: ").strip()
        if not id_nota.isdigit():
            raise ValueError("O ID da nota deve conter apenas números.")

        page.goto(
            f"{BASE_URL}/movimentos/nf-e/saidas/{id_nota}/editar",
            wait_until="domcontentloaded"
        )

        page.locator('input[name="email"]').wait_for(state="visible")
        page.fill('input[name="email"]', LOGIN_EMAIL)
        page.click('button[type="submit"]')
        page.locator('input[name="password"]').wait_for(state="visible")
        page.fill('input[name="password"]', LOGIN_PASSWORD)
        page.get_by_role("button", name="Entrar").click()

        page.wait_for_load_state("networkidle")

        for prod in dados_nota["produtos"]:
            page.locator(
                'button[mattooltip="Adicionar produto (Insert)"]'
            ).click()
            produto_input = page.get_by_role("combobox", name="Produto")
            produto_input.fill(prod["codigo"])
            opcao_produto = page.get_by_role("option").filter(
                has_text=prod["codigo"]
            ).first

            try:
                opcao_produto.wait_for(state="visible", timeout=3000)
            except PlaywrightTimeout:
                produto_input.press("Control+A")
                produto_input.fill(prod["nome"])
                opcao_produto = page.get_by_role("option").filter(
                    has_text=prod["nome"]
                ).first
                try:
                    opcao_produto.wait_for(state="visible", timeout=5000)
                except PlaywrightTimeout as exc:
                    print(
                        "Produto não encontrado automaticamente. "
                        f"Código: {prod['codigo']} | Nome: {prod['nome']}"
                    )
                    input(
                        "Selecione o produto manualmente no navegador e "
                        "pressione Enter para continuar..."
                    )
                    if not produto_input.input_value().strip():
                        raise RuntimeError(
                            "O produto não foi selecionado manualmente."
                        ) from exc

            if opcao_produto.is_visible():
                opcao_produto.click()
            page.wait_for_timeout(1000)

            quantidade = page.locator('input[data-placeholder="Quantidade"]')
            quantidade_decimal = Decimal(str(prod["quantidade"]))
            if quantidade_decimal == quantidade_decimal.to_integral_value():
                quantidade_texto = str(int(quantidade_decimal))
            else:
                quantidade_texto = (
                    format(quantidade_decimal, "f")
                    .rstrip("0")
                    .rstrip(".")
                    .replace(".", ",")
                )
            quantidade.click()
            quantidade.press("Control+A")
            quantidade.type(quantidade_texto, delay=50)
            quantidade.blur()
            page.wait_for_timeout(500)
            if not quantidade.input_value():
                raise RuntimeError(
                    f"A quantidade não foi aplicada para: {prod['nome']}"
                )

            tributos = page.get_by_role("button", name="Tributos", exact=True)
            tributos.wait_for(state="visible")
            tributos.click()

            cfop = page.locator('input[data-placeholder="CFOP"]')
            cfop.wait_for(state="visible")
            cfop.fill(prod["codigo_fiscal"])
            cfop.blur()

            page.get_by_role("button", name="Confirmar", exact=True).click()
            time.sleep(0.8)

        print("Preenchimento concluído. Confira os dados antes de salvar.")
        time.sleep(300)
        browser.close()


# --- EXECUTAR ---
if __name__ == "__main__":
    pasta_xml = Path(__file__).resolve().parent / "notasXMLs"
    arquivos_xml = sorted(pasta_xml.glob("*.xml"))

    if not arquivos_xml:
        raise FileNotFoundError(
            f"Nenhum XML encontrado na pasta: {pasta_xml}"
        )

    for arquivo_xml in arquivos_xml:
        print(f"Lendo XML: {arquivo_xml.name}")
        dados = ler_xml_nfe(arquivo_xml)
        lancar_no_sistema(dados)
