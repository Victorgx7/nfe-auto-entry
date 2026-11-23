import xmltodict


def ler_xml_nfe(caminho_arquivo):
    with open(caminho_arquivo, "rb") as arquivo:
        documento = xmltodict.parse(arquivo)

    inf_nfe = extrair_infnfe(documento)
    itens_raw = inf_nfe["det"]
    if isinstance(itens_raw, dict):
        itens_raw = [itens_raw]

    produtos = []
    for item in itens_raw:
        prod = item["prod"]
        produtos.append(
            {
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
                "inf_adicional_produto": obter_texto(item, "infAdProd"),
            }
        )

    return {
        "numero_nota": inf_nfe["ide"]["nNF"],
        "cnpj_emitente": inf_nfe["emit"].get(
            "CNPJ", inf_nfe["emit"].get("CPF", "")
        ),
        "valor_total": inf_nfe["total"]["ICMSTot"]["vNF"],
        "produtos": produtos,
        "codigo_fiscal": [
            produto["codigo_fiscal"] for produto in produtos
        ],
    }


def ler_produtos_xml(caminho_arquivo):
    with open(caminho_arquivo, "rb") as arquivo:
        documento = xmltodict.parse(arquivo)

    inf_nfe = extrair_infnfe(documento)
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
        produtos.append(
            {
                "codigo": codigo,
                "nome": obter_texto(prod, "xProd"),
                "ean": obter_texto(prod, "cEAN"),
                "ncm": obter_texto(prod, "NCM"),
                "unidade": obter_texto(prod, "uCom"),
                "valor_unitario": obter_texto(prod, "vUnCom"),
                "di": extrair_di(prod),
                "impostos": extrair_impostos(item.get("imposto", {})),
                "inf_adicional_produto": obter_texto(item, "infAdProd"),
            }
        )

    return produtos


def extrair_infnfe(documento):
    if "nfeProc" in documento:
        nfe = documento["nfeProc"]["NFe"]
    elif "NFe" in documento:
        nfe = documento["NFe"]
    else:
        raise ValueError(
            "Formato de XML nao reconhecido: no NFe nao encontrado"
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
            adicoes.append(
                {
                    "nAdicao": obter_texto(adi, "nAdicao"),
                    "nSeqAdic": obter_texto(adi, "nSeqAdic"),
                    "cFabricante": obter_texto(
                        adi,
                        "cFabricante",
                        obter_texto(adi, "cFrabrincante"),
                    ),
                }
            )

        declaracoes.append(
            {
                "nDI": obter_texto(di, "nDI"),
                "dDI": obter_texto(di, "dDI"),
                "xLocDesemb": obter_texto(di, "xLocDesemb"),
                "UFDesemb": obter_texto(di, "UFDesemb"),
                "tpViaTransp": obter_texto(di, "tpViaTransp"),
                "tpIntermediario": obter_texto(
                    di,
                    "tpIntermediario",
                    obter_texto(di, "tpIntermedio"),
                ),
                "CNPJ": obter_texto(di, "CNPJ"),
                "UFTerceiro": obter_texto(di, "UFTerceiro"),
                "cExportador": obter_texto(di, "cExportador"),
                "adi": adicoes,
            }
        )
    return declaracoes


def extrair_nodo_principal(dicionario, chave):
    nodo = dicionario.get(chave)
    if not isinstance(nodo, dict):
        return {}
    return next(
        (valor for valor in nodo.values() if isinstance(valor, dict)),
        {},
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
            "pICMS": obter_texto(icms, "pICMS"),
        },
        "IPI": {
            "CST": obter_texto(ipi, "CST"),
            "vBC": obter_texto(ipi, "vBC"),
            "pIPI": obter_texto(ipi, "pIPI"),
        },
        "II": {
            "vBC": obter_texto(ii if isinstance(ii, dict) else {}, "vBC"),
            "vDespAdu": obter_texto(
                ii if isinstance(ii, dict) else {}, "vDespAdu"
            ),
            "vII": obter_texto(ii if isinstance(ii, dict) else {}, "vII"),
            "vIOF": obter_texto(ii if isinstance(ii, dict) else {}, "vIOF"),
        },
        "PIS": {
            "CST": obter_texto(pis, "CST"),
            "vBC": obter_texto(pis, "vBC"),
            "pPIS": obter_texto(pis, "pPIS"),
        },
        "COFINS": {
            "CST": obter_texto(cofins, "CST"),
            "vBC": obter_texto(cofins, "vBC"),
            "pCOFINS": obter_texto(cofins, "pCOFINS"),
        },
        "IBSCBS": {
            "CST": obter_texto(ibscbs, "CST"),
            "cClassTrib": obter_texto(ibscbs, "cClassTrib"),
            "gIBSCBS": {
                "vBC": obter_texto(g_ibscbs, "vBC"),
                "gIBSUF": {
                    "pIBSUF": obter_texto(
                        g_ibsu_f if isinstance(g_ibsu_f, dict) else {},
                        "pIBSUF",
                    ),
                    "vIBSUF": obter_texto(
                        g_ibsu_f if isinstance(g_ibsu_f, dict) else {},
                        "vIBSUF",
                    ),
                },
                "gIBSMun": {
                    "pIBSMun": obter_texto(
                        g_ibs_mun if isinstance(g_ibs_mun, dict) else {},
                        "pIBSMun",
                    ),
                    "vIBSMun": obter_texto(
                        g_ibs_mun if isinstance(g_ibs_mun, dict) else {},
                        "vIBSMun",
                    ),
                },
                "vIBS": obter_texto(g_ibscbs, "vIBS"),
                "gCBS": {
                    "pCBS": obter_texto(
                        g_cbs if isinstance(g_cbs, dict) else {}, "pCBS"
                    ),
                    "vCBS": obter_texto(
                        g_cbs if isinstance(g_cbs, dict) else {}, "vCBS"
                    ),
                },
            },
        },
    }
