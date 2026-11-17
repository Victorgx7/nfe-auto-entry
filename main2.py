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

## --- PASSO 1: LER O XML ---
def ler_xml_nfe(caminho_arquivo):
    with open(caminho_arquivo, "rb") as f:
        doc = xmltodict.parse(f)

    # Acessa o nó principal da NF-e
    inf_nfe = doc["nfeProc"]["NFe"]["infNFe"]

    # Garante que 'det' (itens) seja sempre uma lista, mesmo se a nota tiver 1 só item
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
    with sync_playwright() as p:
        # headless=False faz o navegador aparecer na tela para você ver acontecendo
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # 1. Acessar o sistema
        page.goto("https://app.gdoorweb.com.br/movimentos/nf-e/saidas/1769/editar", wait_until="domcontentloaded")

        # 2. Login (Substitua os seletores pelos do seu sistema)
        page.locator('input[name="email"]').wait_for(state="visible")
        page.click('input[name="email"]')
        page.type('input[name="email"]', "suporte@interagiti.com.br", delay=80)
        page.click('button[type="submit"]')
        page.locator('input[name="password"]').wait_for(state="visible")
        page.click('input[name="password"]')
        page.type('input[name="password"]', "123456", delay=80)
        page.get_by_role("button", name="Entrar").click()

        # Espera a página carregar após o login
        page.wait_for_load_state("networkidle")

        # 3. Ir para a tela de entrada de nota(alterar esse url conforme o sistema do cliente)
        # O código abaixo está dando um erro que ele fica fazendo retorno para tela de login.
        #page.goto("https://app.gdoorweb.com.br/movimentos/nf-e/saidas/1769/editar", wait_until="domcontentloaded")

        # 4. Preencher Cabeçalho (delay=50 simula digitação humana)
        #page.type('#campo-numero-nota', dados_nota["numero_nota"], delay=50)
        #page.type('#campo-cnpj', dados_nota["cnpj_emitente"], delay=50)

        # 5. Preencher os Produtos e forncedor em Loop
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
                    raise RuntimeError(
                        "Produto não encontrado pelo código "
                        f"'{prod['codigo']}' nem pelo nome '{prod['nome']}'"
                    ) from exc

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
                    f"A quantidade não foi aplicada para o produto: {prod['nome']}"
                )
            tributos = page.get_by_role("button", name="Tributos", exact=True)
            tributos.wait_for(state="visible")
            tributos.click()

            cfop = page.locator('input[data-placeholder="CFOP"]')
            cfop.wait_for(state="visible")
            cfop.fill(prod["codigo_fiscal"])
            cfop.blur()

            page.get_by_role("button", name="Confirmar", exact=True).click()
            time.sleep(0.8) # Pequena pausa para o sistema processar

        print("Preenchimento concluído! Confira os dados na tela antes de salvar.")

        # Mantém o navegador aberto por 5 minutos para você conferir e clicar em Salvar
        time.sleep(300)
        browser.close()

# --- EXECUTAR ---
pasta_xml = Path(__file__).resolve().parent / "notasXMLs"
arquivos_xml = sorted(pasta_xml.glob("*.xml"))

if not arquivos_xml:
    raise FileNotFoundError(
        f"Nenhum arquivo XML encontrado na pasta: {pasta_xml}"
    )

for arquivo_xml in arquivos_xml:
    print(f"Lendo XML: {arquivo_xml.name}")
    dados = ler_xml_nfe(arquivo_xml)
    lancar_no_sistema(dados)