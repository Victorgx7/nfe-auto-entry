import os
import sys
import time
import json
from decimal import Decimal
from pathlib import Path

import xmltodict
from dotenv import load_dotenv
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout, sync_playwright

load_dotenv()

GDOOR_BASE_URL = os.getenv("GDOOR_BASE_URL", "https://app.gdoorweb.com.br/movimentos/compras/1735")
GDOOR_EMAIL = os.getenv("GDOOR_EMAIL")
GDOOR_PASSWORD = os.getenv("GDOOR_PASSWORD")
GDOOR_PRODUCTS_URL = os.getenv(
    "GDOOR_PRODUCTS_URL",
    "https://app.gdoorweb.com.br/cadastros/produtos/lista",
)

if not GDOOR_EMAIL or not GDOOR_PASSWORD:
    raise RuntimeError(
        "Configure GDOOR_EMAIL e GDOOR_PASSWORD no arquivo .env."
    )

if getattr(sys, "frozen", False):
    pasta_playwright = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    os.environ.setdefault(
        "PLAYWRIGHT_BROWSERS_PATH",
        os.path.join(pasta_playwright, "ms-playwright"),
    )

## --- PASSO 1: LER O XML ---
def ler_xml_nfe(caminho_arquivo):
    with open(caminho_arquivo, "rb") as f:
        doc = xmltodict.parse(f)

    inf_nfe = extrair_infnfe(doc)

    itens_raw = inf_nfe["det"]
    if isinstance(itens_raw, dict):
        itens_raw = [itens_raw]

    produtos = []
    for item in itens_raw:
        prod = item["prod"]
        produtos.append({
            "codigo": prod["cProd"],
            "nome": prod["xProd"],
            "ean": obter_texto(prod, "cEAN"),
            "ncm": obter_texto(prod, "NCM"),
            "unidade": obter_texto(prod, "uCom"),
            "quantidade": obter_texto(prod, "qCom"),
            "valor_unitario": obter_texto(prod, "vUnCom"),
            "codigo_fiscal": obter_texto(prod, "CFOP"),
            "di": extrair_di(prod),
            "impostos": extrair_impostos(item.get("imposto", {})),
            "inf_adicional_produto": obter_texto(item, "infAdProd")
        })

    return {
        "numero_nota": inf_nfe["ide"]["nNF"],
        "cnpj_emitente": inf_nfe["emit"].get("CNPJ", inf_nfe["emit"].get("CPF", "")),
        "valor_total": inf_nfe["total"]["ICMSTot"]["vNF"],
        "produtos": produtos,
        "codigo_fiscal": [produto["codigo_fiscal"] for produto in produtos]
    }


def extrair_infnfe(doc):
    # Aceita XML autorizado (nfeProc) e XML sem o protocolo (NFe).
    if "nfeProc" in doc:
        nfe = doc["nfeProc"]["NFe"]
    elif "NFe" in doc:
        nfe = doc["NFe"]
    else:
        raise ValueError(
            "Formato de XML não reconhecido: "
            "nó NFe não encontrado"
        )
    return nfe["infNFe"]


def obter_texto(dicionario, chave, padrao=""):
    valor = dicionario.get(chave, padrao)
    return "" if valor is None else str(valor).strip()


def como_lista(valor):
    if valor is None:
        return []
    return valor if isinstance(valor, list) else [valor]


def extrair_di(prod):
    declaracoes = []
    for di in como_lista(prod.get("DI")):
        if not isinstance(di, dict):
            continue

        adicoes = []
        for adi in como_lista(di.get("adi")):
            if not isinstance(adi, dict):
                continue
            adicoes.append({
                "nAdicao": obter_texto(adi, "nAdicao"),
                "nSeqAdic": obter_texto(adi, "nSeqAdic"),
                "cFabricante": obter_texto(
                    adi,
                    "cFabricante",
                    obter_texto(adi, "cFrabrincante")
                )
            })

        declaracoes.append({
            "nDI": obter_texto(di, "nDI"),
            "dDI": obter_texto(di, "dDI"),
            "xLocDesemb": obter_texto(di, "xLocDesemb"),
            "UFDesemb": obter_texto(di, "UFDesemb"),
            "tpViaTransp": obter_texto(di, "tpViaTransp"),
            "tpIntermediario": obter_texto(
                di,
                "tpIntermediario",
                obter_texto(di, "tpIntermedio")
            ),
            "CNPJ": obter_texto(di, "CNPJ"),
            "UFTerceiro": obter_texto(di, "UFTerceiro"),
            "cExportador": obter_texto(di, "cExportador"),
            "adi": adicoes
        })
    return declaracoes


def extrair_nodo_principal(dicionario, chave):
    nodo = dicionario.get(chave)
    if not isinstance(nodo, dict):
        return {}
    return next(
        (
            valor
            for valor in nodo.values()
            if isinstance(valor, dict)
        ),
        {}
    )


def extrair_impostos(imposto):
    if not isinstance(imposto, dict):
        imposto = {}

    icms = extrair_nodo_principal(imposto, "ICMS")
    ipi = extrair_nodo_principal(imposto, "IPI")
    ii = imposto.get("II", {})
    pis = extrair_nodo_principal(imposto, "PIS")
    cofins = extrair_nodo_principal(imposto, "COFINS")
    ibscbs = imposto.get("IBSCBS", {})
    if not isinstance(ibscbs, dict):
        ibscbs = extrair_nodo_principal(imposto, "IBSCBS")
    g_ibscbs = ibscbs.get("gIBSCBS", {})
    if not isinstance(g_ibscbs, dict):
        g_ibscbs = {}
    g_ibsu_f = g_ibscbs.get("gIBSUF", {})
    g_ibs_mun = g_ibscbs.get("gIBSMun", {})
    g_cbs = g_ibscbs.get("gCBS", {})

    return {
        "ICMS": {
            "CST": obter_texto(icms, "CST"),
            "vBC": obter_texto(icms, "vBC"),
            "pICMS": obter_texto(icms, "pICMS")
        },
        "IPI": {
            "CST": obter_texto(ipi, "CST"),
            "vBC": obter_texto(ipi, "vBC"),
            "pIPI": obter_texto(ipi, "pIPI")
        },
        "II": {
            "vBC": obter_texto(ii if isinstance(ii, dict) else {}, "vBC"),
            "vDespAdu": obter_texto(ii if isinstance(ii, dict) else {}, "vDespAdu"),
            "vII": obter_texto(ii if isinstance(ii, dict) else {}, "vII"),
            "vIOF": obter_texto(ii if isinstance(ii, dict) else {}, "vIOF")
        },
        "PIS": {
            "CST": obter_texto(pis, "CST"),
            "vBC": obter_texto(pis, "vBC"),
            "pPIS": obter_texto(pis, "pPIS")
        },
        "COFINS": {
            "CST": obter_texto(cofins, "CST"),
            "vBC": obter_texto(cofins, "vBC"),
            "pCOFINS": obter_texto(cofins, "pCOFINS")
        },
        "IBSCBS": {
            "CST": obter_texto(ibscbs, "CST"),
            "cClassTrib": obter_texto(ibscbs, "cClassTrib"),
            "gIBSCBS": {
                "vBC": obter_texto(g_ibscbs, "vBC"),
                "gIBSUF": {
                    "pIBSUF": obter_texto(g_ibsu_f if isinstance(g_ibsu_f, dict) else {}, "pIBSUF"),
                    "vIBSUF": obter_texto(g_ibsu_f if isinstance(g_ibsu_f, dict) else {}, "vIBSUF")
                },
                "gIBSMun": {
                    "pIBSMun": obter_texto(g_ibs_mun if isinstance(g_ibs_mun, dict) else {}, "pIBSMun"),
                    "vIBSMun": obter_texto(g_ibs_mun if isinstance(g_ibs_mun, dict) else {}, "vIBSMun")
                },
                "vIBS": obter_texto(g_ibscbs, "vIBS"),
                "gCBS": {
                    "pCBS": obter_texto(g_cbs if isinstance(g_cbs, dict) else {}, "pCBS"),
                    "vCBS": obter_texto(g_cbs if isinstance(g_cbs, dict) else {}, "vCBS")
                }
            }
        }
    }


def ler_produtos_xml(caminho_arquivo):
    with open(caminho_arquivo, "rb") as f:
        doc = xmltodict.parse(f)

    inf_nfe = extrair_infnfe(doc)
    itens_raw = inf_nfe["det"]
    if isinstance(itens_raw, dict):
        itens_raw = [itens_raw]

    produtos = []
    codigos_vistos = set()
    for item in itens_raw:
        prod = item["prod"]
        codigo = obter_texto(prod, "cProd")
        if not codigo or codigo in codigos_vistos:
            continue
        codigos_vistos.add(codigo)
        produtos.append({
            "codigo": codigo,
            "nome": obter_texto(prod, "xProd"),
            "ean": obter_texto(prod, "cEAN"),
            "ncm": obter_texto(prod, "NCM"),
            "unidade": obter_texto(prod, "uCom"),
            "valor_unitario": obter_texto(prod, "vUnCom"),
            "di": extrair_di(prod),
            "impostos": extrair_impostos(item.get("imposto", {})),
            "inf_adicional_produto": obter_texto(item, "infAdProd")
        })

    return produtos

# --- PASSO 2: DIGITAR NO SISTEMA WEB ---
def lancar_no_sistema(dados_nota):
    with sync_playwright() as p:
        # headless=False faz o navegador aparecer na tela para você ver acontecendo
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # 1. Acessar o sistema
        #Incluir input pedindo ID da nota
        idNota = input("Informe o ID da nota: ")
        page.goto(f"{GDOOR_BASE_URL}/movimentos/nf-e/saidas/{idNota}/editar", wait_until="domcontentloaded")

        # 2. Login (Substitua os seletores pelos do seu sistema)
        page.locator('input[name="email"]').wait_for(state="visible")
        page.click('input[name="email"]')
        page.type('input[name="email"]', GDOOR_EMAIL, delay=80)
        page.click('button[type="submit"]')
        page.locator('input[name="password"]').wait_for(state="visible")
        page.click('input[name="password"]')
        page.type('input[name="password"]', GDOOR_PASSWORD, delay=80)
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


def encontrar_campo_busca(page):
    seletores = [
        'input[data-placeholder="Pesquisar"]',
        'input[data-placeholder="Código"]',
        'input[placeholder*="Pesquisar"]',
        'input[placeholder*="Código"]',
        'input[placeholder*="Nome"]',
        'input[type="search"]',
        'input[matinput]',
    ]

    for seletor in seletores:
        campo = page.locator(seletor)
        for indice in range(campo.count()):
            candidato = campo.nth(indice)
            if candidato.is_visible():
                return candidato
    return None


def consultar_produto_na_lista(page, termo):
    if not termo:
        return False

    campo_busca = encontrar_campo_busca(page)
    if campo_busca is None:
        print(
            "Campo de busca não identificado automaticamente. "
            "A consulta deste produto precisa ser feita manualmente."
        )
        return False

    campo_busca.press("Control+A")
    campo_busca.fill(str(termo))
    campo_busca.press("Enter")
    page.wait_for_timeout(1500)

    linha = page.locator("tbody tr").filter(has_text=str(termo)).first
    if linha.is_visible():
        return True

    return False


def importar_produtos_no_sistema(caminho_arquivo):
    produtos = ler_produtos_xml(caminho_arquivo)
    if not produtos:
        print(f"Nenhum produto encontrado em {caminho_arquivo.name}.")
        return

    print(
        f"{len(produtos)} produto(s) encontrado(s) em {caminho_arquivo.name}. "
        "Preencha o cadastro no sistema conforme a tela exibida."
    )

    if not GDOOR_PRODUCTS_URL:
        raise RuntimeError(
            "Configure GDOOR_PRODUCTS_URL no arquivo .env com a URL da tela "
            "de cadastro de produtos."
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(GDOOR_PRODUCTS_URL, wait_until="domcontentloaded")

        page.locator('input[name="email"]').wait_for(state="visible")
        page.click('input[name="email"]')
        page.type('input[name="email"]', GDOOR_EMAIL, delay=80)
        page.click('button[type="submit"]')
        page.locator('input[name="password"]').wait_for(state="visible")
        page.click('input[name="password"]')
        page.type('input[name="password"]', GDOOR_PASSWORD, delay=80)
        page.get_by_role("button", name="Entrar").click()
        page.wait_for_load_state("networkidle")

        for indice, produto in enumerate(produtos, start=1):
            print(
                f"\nProduto {indice}/{len(produtos)}:\n"
                f"  Código: {produto['codigo']}\n"
                f"  Nome: {produto['nome']}\n"
                f"  GTIN: {produto['ean'] or '-'}\n"
                f"  NCM: {produto['ncm'] or '-'}\n"
                f"  Unidade: {produto['unidade'] or '-'}\n"
                f"  Valor unitário: {produto['valor_unitario'] or '-'}\n"
                "  Grupo DI:\n"
                f"{json.dumps(produto['di'], ensure_ascii=False, indent=4)}\n"
                "  Grupo imposto:\n"
                f"{json.dumps(produto['impostos'], ensure_ascii=False, indent=4)}\n"
                f"  infAdProd: {produto['inf_adicional_produto'] or '-'}"
            )

            encontrado_por_codigo = consultar_produto_na_lista(
                page,
                produto["codigo"],
            )

            if encontrado_por_codigo:
                print(
                    f"Produto encontrado pelo código: {produto['codigo']}"
                )
            else:
                encontrado_por_nome = consultar_produto_na_lista(
                    page,
                    produto["nome"],
                )
                if encontrado_por_nome:
                    print(
                        f"Produto encontrado pelo nome: {produto['nome']}"
                    )
                else:
                    print(
                        "Produto não encontrado pelo código nem pelo nome. "
                        "Confira/cadastre manualmente."
                    )

            input(
                "Pressione Enter para consultar o próximo produto..."
            )

        print("Importação de produtos concluída. Confira os cadastros antes de fechar.")
        time.sleep(300)
        browser.close()


def selecionar_arquivos(pasta_xml):
    arquivos_xml = sorted(pasta_xml.glob("*.xml"))
    if not arquivos_xml:
        raise FileNotFoundError(
            f"Nenhum arquivo XML encontrado na pasta: {pasta_xml}"
        )
    return arquivos_xml


def mostrar_menu():
    print("\nO que deseja fazer?")
    print("1 - Importar produtos do XML")
    print("2 - Importar nota fiscal")
    print("3 - Sair")
    return input("Opção: ").strip()


# --- EXECUTAR ---
pasta_base = (
    os.path.dirname(sys.executable)
    if getattr(sys, "frozen", False)
    else os.path.dirname(os.path.abspath(__file__))
)
pasta_xml = Path(pasta_base) / "notasXMLs"

while True:
    opcao = mostrar_menu()
    if opcao == "3":
        break
    if opcao not in {"1", "2"}:
        print("Opção inválida.")
        continue

    arquivos_xml = selecionar_arquivos(pasta_xml)
    for arquivo_xml in arquivos_xml:
        print(f"\nArquivo XML: {arquivo_xml.name}")
        if opcao == "1":
            importar_produtos_no_sistema(arquivo_xml)
        else:
            print("Lendo XML...")
            dados = ler_xml_nfe(arquivo_xml)
            lancar_no_sistema(dados)