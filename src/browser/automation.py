import json
import os
import time
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from queue import Queue
from threading import Event, Thread
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from src.nfe.parser import ler_produtos_xml

load_dotenv()


def carregar_configuracao():
    configuracao = {
        "base_url": os.getenv(
            "GDOOR_BASE_URL",
            "https://app.gdoorweb.com.br/movimentos/compras/1735",
        ),
        "email": os.getenv("GDOOR_EMAIL"),
        "password": os.getenv("GDOOR_PASSWORD"),
        "products_url": os.getenv(
            "GDOOR_PRODUCTS_URL",
            "https://app.gdoorweb.com.br/cadastros/produtos/lista",
        ),
    }
    if not configuracao["email"] or not configuracao["password"]:
        raise RuntimeError(
            "Configure GDOOR_EMAIL e GDOOR_PASSWORD no arquivo .env."
        )
    return configuracao


def fazer_login(page, email, password):
    page.locator('input[name="email"]').wait_for(state="visible")
    page.click('input[name="email"]')
    page.type('input[name="email"]', email, delay=80)
    page.click('button[type="submit"]')
    page.locator('input[name="password"]').wait_for(state="visible")
    page.click('input[name="password"]')
    page.type('input[name="password"]', password, delay=80)
    page.get_by_role("button", name="Entrar").click()
    page.wait_for_load_state("networkidle")


class GDoorSession:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.playwright = None
        self.browser = None
        self.page = None
        self._solicitacoes = Queue()
        self._pronto = Event()
        self._erro = None
        self._thread = None

    def abrir(self):
        self._thread = Thread(
            target=self._executar_sessao,
            daemon=True
        )
        self._thread.start()
        if not self._pronto.wait(timeout=30):
            raise RuntimeError("Tempo excedido ao abrir o Gdoor.")
        if self._erro:
            raise RuntimeError(self._erro)
        return self.page

    def _executar_sessao(self):
        configuracao = carregar_configuracao()
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=False)
            self.page = self.browser.new_page()
            self.page.goto(
                configuracao["products_url"],
                wait_until="domcontentloaded",
            )
            fazer_login(
                self.page,
                self.email,
                self.password,
            )
        except Exception as exc:
            self._erro = str(exc)
            self._pronto.set()
            return

        self._pronto.set()

        while True:
            funcao, argumentos, palavras_chave, resposta = (
                self._solicitacoes.get()
            )
            if funcao is None:
                break
            try:
                palavras_chave["page"] = self.page
                resultado = funcao(
                    *argumentos,
                    **palavras_chave
                )
                resposta.put(("ok", resultado))
            except Exception as exc:
                resposta.put(("erro", str(exc)))

        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def executar(self, funcao, *argumentos, **palavras_chave):
        resposta = Queue()
        self._solicitacoes.put(
            (funcao, argumentos, palavras_chave, resposta)
        )
        status, valor = resposta.get()
        if status == "erro":
            raise RuntimeError(valor)
        return valor

    def fechar(self):
        self._solicitacoes.put((None, (), {}, Queue()))


def abrir_consulta_produtos(page=None):
    configuracao = carregar_configuracao()
    page.goto(
        configuracao["products_url"],
        wait_until="domcontentloaded",
    )
    page.wait_for_load_state("networkidle")
    return True


def lancar_no_sistema(
    dados_nota,
    id_nota=None,
    page=None,
    aguardar_selecao_manual=None,
    importar_ibscbs=False,
):
    configuracao = carregar_configuracao()

    if not id_nota:
        raise ValueError("Informe o ID da nota.")

    if page is not None:
        page.goto(
            f"{configuracao['base_url']}/movimentos/nf-e/saidas/"
            f"{id_nota}/editar",
            wait_until="domcontentloaded",
        )

        for produto in dados_nota["produtos"]:
            page.locator(
                'button[mattooltip="Adicionar produto (Insert)"]'
            ).click()
            produto_input = page.get_by_role("combobox", name="Produto")
            produto_input.fill(produto["codigo"])
            opcao_produto = page.get_by_role("option").filter(
                has_text=produto["codigo"]
            ).first

            selecao_automatica = True
            try:
                opcao_produto.wait_for(state="visible", timeout=3000)
            except PlaywrightTimeout:
                produto_input.press("Control+A")
                produto_input.fill(produto["nome"])
                opcao_produto = page.get_by_role("option").filter(
                    has_text=produto["nome"]
                ).first
                try:
                    opcao_produto.wait_for(state="visible", timeout=5000)
                except PlaywrightTimeout:
                    if aguardar_selecao_manual is None:
                        raise RuntimeError(
                            "Produto nao encontrado automaticamente. "
                            f"Codigo: {produto['codigo']} | "
                            f"Nome: {produto['nome']}"
                        )
                    selecao_automatica = False
                    aguardar_selecao_manual(produto)

            if selecao_automatica and opcao_produto.is_visible():
                opcao_produto.click()
            page.wait_for_timeout(1000)

            quantidade = page.locator(
                'input[data-placeholder="Quantidade"]'
            )
            quantidade_decimal = Decimal(str(produto["quantidade"]))
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
                    "A quantidade nao foi aplicada para o produto: "
                    f"{produto['nome']}"
                )

            tributos = page.get_by_role(
                "button", name="Tributos", exact=True
            )
            tributos.wait_for(state="visible")
            tributos.click()

            cfop = page.locator('input[data-placeholder="CFOP"]')
            cfop.wait_for(state="visible")
            cfop.fill(produto["codigo_fiscal"])
            cfop.blur()
            if importar_ibscbs:
                preencher_ibscbs(page, produto)

            page.get_by_role(
                "button", name="Confirmar", exact=True
            ).click()
            time.sleep(0.8)

        print(
            "Preenchimento concluido! Confira os dados na tela "
            "antes de salvar."
        )
        return

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        nova_pagina = browser.new_page()
        nova_pagina.goto(
            f"{configuracao['base_url']}/movimentos/nf-e/saidas/"
            f"{id_nota}/editar",
            wait_until="domcontentloaded",
        )
        fazer_login(
            nova_pagina,
            configuracao["email"],
            configuracao["password"]
        )
        lancar_no_sistema(
            dados_nota,
            id_nota,
            nova_pagina,
            importar_ibscbs=importar_ibscbs,
        )
        browser.close()


def preencher_ibscbs(page, produto):
    abrir_secao_ibscbs(page)

    impostos_ibscbs = produto.get("impostos", {}).get("IBSCBS", {})
    dados_grupo = impostos_ibscbs.get("gIBSCBS", {})
    ibs_uf = dados_grupo.get("gIBSUF", {})
    ibs_municipio = dados_grupo.get("gIBSMun", {})
    dados = {
        "CST": impostos_ibscbs.get("CST", ""),
        "Código de Classificação Tributária": impostos_ibscbs.get(
            "cClassTrib", ""
        ),
        "Alíquota UF": ibs_uf.get("pIBSUF", ""),
        "Alíquota Município": ibs_municipio.get("pIBSMun", ""),
    }
    ausentes = [nome for nome, valor in dados.items() if not valor]
    if ausentes:
        raise RuntimeError(
            "Dados IBS/CBS ausentes no XML para "
            f"{produto['nome']}: {', '.join(ausentes)}."
        )

    selecionar_opcao_tributo(page, "CST", dados["CST"], usar_ultimo=True)
    selecionar_opcao_tributo(
        page,
        "Código de Classificação Tributária",
        dados["Código de Classificação Tributária"],
    )

    grupos_aliquotas = (
        (
            "IBS UF",
            'input[name="ibsCbs.ibs_uf_rate"]',
            dados["Alíquota UF"],
        ),
        (
            "IBS Município",
            'input[name="ibsCbs.ibs_city_rate"]',
            dados["Alíquota Município"],
        ),
    )
    for nome_grupo, seletor, valor in grupos_aliquotas:
        preencher_aliquota_ibscbs(
            page,
            nome_grupo,
            seletor,
            valor,
            produto["nome"],
        )


def abrir_secao_ibscbs(page):
    campo_cst = page.locator('mat-select[name="ibs_cbs_cst"]')
    if campo_cst.is_visible():
        return

    grupos_controles = (
        page.get_by_role("tab", name="IBS/CBS", exact=True),
        page.get_by_role("button", name="IBS/CBS", exact=True),
        page.get_by_text("IBS/CBS", exact=True),
    )
    selecionou_controle = False
    for grupo in grupos_controles:
        for indice in range(grupo.count()):
            controle = grupo.nth(indice)
            if not controle.is_visible():
                continue
            controle.click()
            selecionou_controle = True
            break
        if selecionou_controle:
            break

    if not selecionou_controle:
        raise RuntimeError(
            "Não foi possível localizar o controle para abrir IBS/CBS."
        )
    try:
        campo_cst.wait_for(state="visible", timeout=5000)
    except PlaywrightTimeout as exc:
        raise RuntimeError(
            "A seção IBS/CBS foi selecionada, mas o campo CST não ficou "
            "visível."
        ) from exc


def preencher_aliquota_ibscbs(page, nome_grupo, seletor, valor, nome_produto):
    botao = page.get_by_role("button", name=nome_grupo, exact=True)
    botao.wait_for(state="visible")
    botao.click()

    campo = page.locator(seletor)
    campo.wait_for(state="visible", timeout=5000)
    if not campo.is_enabled():
        raise RuntimeError(
            f"O campo IBS/CBS '{nome_grupo}' está desabilitado para "
            f"o produto {nome_produto}."
        )
    valor_formatado = format(Decimal(str(valor)), "f").replace(".", ",")
    campo.fill(valor_formatado)
    campo.blur()
    if not campo.input_value():
        raise RuntimeError(
            f"A alíquota de {nome_grupo} não foi preenchida para "
            f"o produto {nome_produto}."
        )


def selecionar_opcao_tributo(page, nome_campo, valor, usar_ultimo=False):
    if nome_campo == "CST":
        campo = page.locator('mat-select[name="ibs_cbs_cst"]')
    else:
        padrao_campo = re.compile(rf"^\s*{re.escape(nome_campo)}\s*$")
        campos = page.locator(".mat-select-placeholder:visible").filter(
            has_text=padrao_campo
        )
        campo = campos.last if usar_ultimo else campos.first
    campo.wait_for(state="visible")
    campo.click()

    padrao_opcao = re.compile(rf"^\s*{re.escape(valor)}(?:\s|$)")
    opcao = page.get_by_role("option").filter(has_text=padrao_opcao).first
    opcao.wait_for(state="visible")
    opcao.click()


def normalizar_texto(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )
    texto = re.sub(r"[^\w]+", " ", texto.lower(), flags=re.UNICODE)
    return " ".join(texto.split())


def texto_da_linha_corresponde(termo_normalizado, texto_normalizado):
    if termo_normalizado in texto_normalizado:
        return True

    palavras_termo = termo_normalizado.split()
    palavras_linha = texto_normalizado.split()
    if len(palavras_termo) < 3:
        return False

    correspondentes = sum(
        1
        for palavra in palavras_termo
        if palavra in palavras_linha
        or any(
            palavra in linha_palavra
            or linha_palavra in palavra
            for linha_palavra in palavras_linha
        )
    )
    return correspondentes / len(palavras_termo) >= 0.8


def produto_tem_indicio_de_existencia(page):
    textos_de_existencia = (
        "duplicar este produto",
        "editar este produto",
        "editar cadastro",
        "abrir produto",
    )

    itens_produto = page.locator("mat-list-item")
    for indice in range(itens_produto.count()):
        item = itens_produto.nth(indice)
        if not item.is_visible():
            continue

        atributos = " ".join(
            normalizar_texto(valor)
            for valor in (
                item.get_attribute("mattooltip") or "",
                item.inner_text(),
                item.locator("[mattooltip]").evaluate_all(
                    "(elementos) => elementos.map((elemento) => "
                    "elemento.getAttribute('mattooltip') || '').join(' ')"
                ),
                item.locator("a[href]").evaluate_all(
                    "(elementos) => elementos.map((elemento) => "
                    "elemento.getAttribute('href') || '').join(' ')"
                ),
            )
        )
        if (
            "duplicar este produto" in atributos
            or "editar cadastro" in atributos
            or "?dup=" in atributos
        ):
            return True

    for seletor in (
        "[role='tooltip']",
        "[mattooltip]",
        "[mattooltipclass]",
        "[aria-label]",
    ):
        elementos = page.locator(seletor)
        for indice in range(elementos.count()):
            elemento = elementos.nth(indice)
            if not elemento.is_visible():
                continue
            texto = normalizar_texto(elemento.inner_text())
            if not texto:
                texto = normalizar_texto(
                    elemento.get_attribute("mattooltip")
                    or elemento.get_attribute("aria-label")
                    or ""
                )
            if any(
                sinal in texto
                for sinal in textos_de_existencia
            ):
                return True

    return False


def menu_de_produto_existente(page):
    menu = page.locator(
        "[role='menu'].mat-menu-panel"
        ":visible, [role='menu']:visible"
    )
    if not menu.count():
        return False

    textos = normalizar_texto(menu.inner_text())
    return (
        "ver detalhes" in textos
        and ("apagar" in textos or "duplicar" in textos)
    )


def item_produto_existe(item):
    if not item.is_visible():
        return False

    try:
        texto_item = normalizar_texto(item.inner_text())
        atributos = " ".join(
            normalizar_texto(valor)
            for valor in (
                item.locator("[mattooltip]").evaluate_all(
                    "(elementos) => elementos.map((elemento) => "
                    "elemento.getAttribute('mattooltip') || '').join(' ')"
                ),
                item.locator("a[href]").evaluate_all(
                    "(elementos) => elementos.map((elemento) => "
                    "elemento.getAttribute('href') || '').join(' ')"
                ),
            )
        )
    except Exception:
        return False

    return (
        "duplicar este produto" in atributos
        or "editar cadastro" in atributos
        or "?dup=" in atributos
    )


def confirmar_produto_por_clique(page, linha):
    try:
        linha.hover(timeout=1000)
        page.wait_for_timeout(300)
    except Exception:
        return False

    gatilhos = linha.locator(
        "button[aria-haspopup='true'], "
        "button.mat-menu-trigger, "
        "[mat-menu-trigger-for]"
    )
    if not gatilhos.count():
        gatilhos = linha.locator("button, [role='button']")

    for indice in range(gatilhos.count()):
        gatilho = gatilhos.nth(indice)
        if not gatilho.is_visible():
            continue
        try:
            gatilho.click(timeout=1500)
            page.wait_for_timeout(500)
            if menu_de_produto_existente(page):
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
                return True
        except Exception:
            continue

    return False


def encontrar_campo_busca(page):
    seletores = [
        'input[data-placeholder="Pesquisar"]',
        'input[placeholder*="Pesquisar"]',
        'input[aria-label*="Pesquisar"]',
        'input[placeholder*="Buscar"]',
        'input[aria-label*="Buscar"]',
        'input[placeholder*="Filtrar"]',
        'input[aria-label*="Filtrar"]',
        'input[placeholder*="Nome"]',
        'input[data-placeholder="Codigo"]',
        'input[placeholder*="Codigo"]',
        'input[placeholder*="C\u00f3digo"]',
        'input[aria-label*="Codigo"]',
        'input[aria-label*="C\u00f3digo"]',
        'input[type="search"]',
    ]
    for seletor in seletores:
        campo = page.locator(seletor)
        for indice in range(campo.count()):
            candidato = campo.nth(indice)
            if candidato.is_visible():
                return candidato

    seletores_matriciais = [
        'input[matinput]',
        'input[role="textbox"]',
        'input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"])',
    ]
    for seletor in seletores_matriciais:
        campo = page.locator(seletor)
        for indice in range(campo.count()):
            candidato = campo.nth(indice)
            if candidato.is_visible():
                return candidato

    for candidato in page.locator('input[type="text"], input:not([type])').all():
        if candidato.is_visible():
            return candidato
    return None


def consultar_produto_na_lista(page, termo):
    if not termo:
        print("[CONSULTA] Termo vazio.")
        return False

    campo_busca = encontrar_campo_busca(page)
    if campo_busca is None:
        print(
            "Campo de busca nao identificado automaticamente. "
            "A consulta deste produto precisa ser feita manualmente."
        )
        return False

    termo_normalizado = normalizar_texto(termo)
    if not termo_normalizado:
        print(f"[CONSULTA] Termo invalido apos normalizacao: {termo!r}")
        return False

    print(
        f"[CONSULTA] Iniciando termo={termo!r} "
        f"normalizado={termo_normalizado!r}"
    )

    campo_busca.click()
    campo_busca.press("Control+A")
    campo_busca.fill(str(termo))
    campo_busca.dispatch_event("input")
    campo_busca.dispatch_event("change")
    
    botao_pesquisa = None
    for nome in ("Pesquisar", "Buscar", "Filtrar"):
        try:
            candidato = page.get_by_role(
                "button",
                name=nome,
                exact=False,
            )
            if candidato.count() and candidato.first.is_visible():
                botao_pesquisa = candidato.first
                break
        except Exception:
            continue
    
    if botao_pesquisa is not None:
        botao_pesquisa.click()
        print("[CONSULTA] Clique no botao de pesquisa.")
    else:
        campo_busca.press("Enter")
        campo_busca.blur()
        print("[CONSULTA] Pesquisa acionada pelo Enter.")
    
    for _ in range(16):
        page.wait_for_timeout(500)

        for seletor in (
            "mat-list-item",
            "tbody tr",
            "mat-row",
            "[role='row']",
        ):
            linhas = page.locator(seletor)
            print(
                f"[CONSULTA] Seletor={seletor} "
                f"linhas_visiveis={linhas.count()}"
            )
            for indice in range(linhas.count()):
                linha = linhas.nth(indice)
                if not linha.is_visible():
                    continue

                texto = normalizar_texto(linha.inner_text())
                print(
                    f"[CONSULTA] Linha {indice}: "
                    f"{texto[:180]!r}"
                )
                if (
                    seletor == "mat-list-item"
                    and texto_da_linha_corresponde(
                        termo_normalizado,
                        texto,
                    )
                    and item_produto_existe(linha)
                ):
                    print(
                        "[CONSULTA] TRUE: mat-list-item correspondente "
                        "com marcador duplicar/editar/dup."
                    )
                    return True

                if texto_da_linha_corresponde(termo_normalizado, texto):
                    print(
                        "[CONSULTA] Texto corresponde, tentando confirmar "
                        "pela abertura do menu desta linha."
                    )
                    return confirmar_produto_por_clique(page, linha)

    print(f"[CONSULTA] FALSE: nenhuma linha positiva para {termo!r}.")
    return False


def consultar_produtos_no_sistema(
    caminhos_arquivos,
    callback=None,
    page=None,
    stop_event=None
):
    configuracao = carregar_configuracao()
    resultados = []

    if page is not None:
        for caminho in map(Path, caminhos_arquivos):
            if stop_event and stop_event.is_set():
                break
            produtos = ler_produtos_xml(caminho)
            for produto in produtos:
                if stop_event and stop_event.is_set():
                    break
                encontrado = consultar_produto_na_lista(
                    page,
                    produto["codigo"]
                )
                criterio = f"Código: {produto['codigo']}"

                if not encontrado:
                    encontrado = consultar_produto_na_lista(
                        page,
                        produto["nome"]
                    )
                    criterio = f"Nome: {produto['nome']}"

                resultado = {
                    "arquivo": caminho.name,
                    "codigo": produto["codigo"],
                    "nome": produto["nome"],
                    "existe": encontrado,
                    "texto": (
                        f"[{caminho.name}] "
                        f"{'EXISTE' if encontrado else 'NÃO EXISTE'} - "
                        f"{criterio}"
                    )
                }
                resultados.append(resultado)
                if callback:
                    callback(resultado)
    else:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            nova_pagina = browser.new_page()
            nova_pagina.goto(
                configuracao["products_url"],
                wait_until="domcontentloaded",
            )
            fazer_login(
                nova_pagina,
                configuracao["email"],
                configuracao["password"],
            )
            for caminho in map(Path, caminhos_arquivos):
                produtos = ler_produtos_xml(caminho)
                for produto in produtos:
                    encontrado = consultar_produto_na_lista(
                        nova_pagina,
                        produto["codigo"]
                    )
                    criterio = f"Código: {produto['codigo']}"

                    if not encontrado:
                        encontrado = consultar_produto_na_lista(
                            nova_pagina,
                            produto["nome"]
                        )
                        criterio = f"Nome: {produto['nome']}"

                    resultado = {
                        "arquivo": caminho.name,
                        "codigo": produto["codigo"],
                        "nome": produto["nome"],
                        "existe": encontrado,
                        "texto": (
                            f"[{caminho.name}] "
                            f"{'EXISTE' if encontrado else 'NÃO EXISTE'} - "
                            f"{criterio}"
                        )
                    }
                    resultados.append(resultado)
                    if callback:
                        callback(resultado)
            browser.close()

    return resultados


def unidade_padrao_corresponde_opcao(texto_opcao):
    partes = re.split(r"[-–]", texto_opcao, maxsplit=1)
    return (
        len(partes) == 2
        and normalizar_texto(partes[0]) == "unid"
        and normalizar_texto(partes[1]).startswith("unidade")
    )


def formatar_custo_xml(valor):
    try:
        custo = Decimal(str(valor).replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"Custo de compra inválido no XML: {valor!r}.") from exc
    if not custo.is_finite():
        raise ValueError(f"Custo de compra inválido no XML: {valor!r}.")
    return format(custo, "f").replace(".", ",")


def decimalizar_valor_campo(valor):
    texto = re.sub(r"[^0-9,.-]", "", str(valor or ""))
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None


def preencher_campo_monetario(page, seletor, valor, descricao, codigo):
    if not valor:
        raise RuntimeError(
            f"O XML não informa {descricao} do produto {codigo}."
        )

    valor_formatado = formatar_custo_xml(valor)
    campo = page.locator(seletor)
    campo.wait_for(state="visible", timeout=10000)
    campo.scroll_into_view_if_needed()
    campo.click()
    campo.press("Control+A")
    campo.type(valor_formatado, delay=60)
    campo.blur()

    valor_aplicado = decimalizar_valor_campo(campo.input_value())
    valor_esperado = Decimal(str(valor).replace(",", "."))
    if valor_aplicado != valor_esperado:
        raise RuntimeError(
            f"O GDOOR não aplicou {descricao} do produto {codigo}: "
            f"XML={valor_formatado}, campo={campo.input_value()!r}."
        )


def selecionar_opcao_dropdown(page, seletor, corresponde, descricao):
    campo = page.locator(seletor)
    campo.wait_for(state="visible")
    campo.click()

    opcoes = page.get_by_role("option")
    correspondentes = []
    for indice in range(opcoes.count()):
        opcao = opcoes.nth(indice)
        if (
            opcao.is_visible()
            and corresponde(opcao.inner_text().strip())
        ):
            correspondentes.append(opcao)

    if len(correspondentes) != 1:
        page.keyboard.press("Escape")
        raise RuntimeError(
            f"Esperava uma opção para {descricao}, "
            f"mas encontrei {len(correspondentes)}."
        )

    correspondentes[0].click()


def preencher_campos_iniciais_produto(page, produto):
    configuracao = carregar_configuracao()
    url_produtos = urlsplit(configuracao["products_url"])
    url_novo_produto = urlunsplit(
        (
            url_produtos.scheme,
            url_produtos.netloc,
            "/cadastros/produtos/novo",
            "",
            "",
        )
    )
    page.goto(url_novo_produto, wait_until="domcontentloaded")

    campo_nome = page.locator('input[name="name"]')
    campo_nome.wait_for(state="visible")
    campo_nome.fill(produto["nome"])

    selecionar_opcao_dropdown(
        page,
        'mat-select[name="measure_unit"]',
        unidade_padrao_corresponde_opcao,
        "unidade padrão UNID - UNIDADE",
    )

    gtin = produto["ean"].strip()
    if gtin and gtin.upper() != "SEM GTIN":
        campo_gtin = page.locator(
            'input[data-placeholder="GTIN, EAN, UPC, etc."]'
        )
        campo_gtin.wait_for(state="visible", timeout=10000)
        campo_gtin.scroll_into_view_if_needed()
        campo_gtin.fill(gtin)
        campo_gtin.blur()
        if campo_gtin.input_value() != gtin:
            raise RuntimeError(
                f"Não foi possível aplicar o GTIN do produto "
                f"{produto['codigo']}."
            )

    preencher_campo_monetario(
        page,
        'input[data-placeholder="Custo de compra"]',
        produto["valor_unitario"],
        "o custo de compra",
        produto["codigo"],
    )
def importar_produtos_no_sistema(caminho_arquivo, page=None, aguardar=False):
    configuracao = carregar_configuracao()
    produtos = ler_produtos_xml(caminho_arquivo)
    if not produtos:
        print(f"Nenhum produto encontrado em {caminho_arquivo.name}.")
        return

    print(
        f"{len(produtos)} produto(s) encontrado(s) em "
        f"{caminho_arquivo.name}. "
        "Preencha o cadastro no sistema conforme a tela exibida."
    )

    if page is not None:
        produto = produtos[0]
        preencher_campos_iniciais_produto(page, produto)
        print(
            "Campos iniciais preenchidos para "
            f"{produto['codigo']} - {produto['nome']}. "
            "O cadastro ainda não foi salvo."
        )
        return produto

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(
            configuracao["products_url"],
            wait_until="domcontentloaded",
        )
        fazer_login(
            page,
            configuracao["email"],
            configuracao["password"],
        )

        for indice, produto in enumerate(produtos, start=1):
            print(
                f"\nProduto {indice}/{len(produtos)}:\n"
                f"  Codigo: {produto['codigo']}\n"
                f"  Nome: {produto['nome']}\n"
                f"  GTIN: {produto['ean'] or '-'}\n"
                f"  NCM: {produto['ncm'] or '-'}\n"
                f"  Unidade: {produto['unidade'] or '-'}\n"
                f"  Valor unitario: {produto['valor_unitario'] or '-'}\n"
                "  Grupo DI:\n"
                f"{json.dumps(produto['di'], ensure_ascii=False, indent=4)}\n"
                "  Grupo imposto:\n"
                f"{json.dumps(produto['impostos'], ensure_ascii=False, indent=4)}\n"
                f"  infAdProd: {produto['inf_adicional_produto'] or '-'}"
            )

            encontrado = consultar_produto_na_lista(
                page, produto["codigo"]
            )
            if encontrado:
                print(
                    f"Produto encontrado pelo codigo: {produto['codigo']}"
                )
            else:
                encontrado = consultar_produto_na_lista(
                    page, produto["nome"]
                )
                if encontrado:
                    print(
                        f"Produto encontrado pelo nome: {produto['nome']}"
                    )
                else:
                    print(
                        "Produto nao encontrado pelo codigo nem pelo nome. "
                        "Confira/cadastre manualmente."
                    )

            input(
                "Pressione Enter para consultar o próximo produto..."
            )

        print(
            "Importação de produtos concluída. "
            "Confira os cadastros antes de fechar."
        )
        time.sleep(300)
        browser.close()
