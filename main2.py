import os
import shutil
import time
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
            "valor_unitario": prod["vUnCom"]
        })

    return {
        "numero_nota": inf_nfe["ide"]["nNF"],
        "cnpj_emitente": inf_nfe["emit"]["CNPJ"],
        "valor_total": inf_nfe["total"]["ICMSTot"]["vNF"],
        "produtos": produtos
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
        page.type('input[name="email"]', "##", delay=80)
        page.click('button[type="submit"]')
        page.locator('input[name="password"]').wait_for(state="visible")
        page.click('input[name="password"]')
        page.type('input[name="password"]', "##", delay=80)
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
            page.fill('#campo-nome-produto', prod["nome"])
            page.fill('#campo-quantidade', prod["quantidade"])
            page.fill('#campo-valor', prod["valor_unitario"])
            page.click('#botao-confirmar-item')
            time.sleep(0.5) # Pequena pausa para o sistema processar

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