import filecmp
import shutil
from pathlib import Path

from src.nfe.parser import ler_xml_nfe


def copiar_xml_para_notas(caminho_origem, pasta_notas):
    origem = Path(caminho_origem)
    if origem.suffix.lower() != ".xml":
        raise ValueError("Selecione um arquivo XML.")

    dados_nfe = ler_xml_nfe(origem)
    if not dados_nfe["produtos"]:
        raise ValueError("O XML não contém produtos.")

    pasta_notas = Path(pasta_notas)
    pasta_notas.mkdir(parents=True, exist_ok=True)

    destino = pasta_notas / origem.name
    indice = 1
    while destino.exists():
        if filecmp.cmp(origem, destino, shallow=False):
            return destino, False
        destino = pasta_notas / f"{origem.stem}_{indice}{origem.suffix}"
        indice += 1

    shutil.copy2(origem, destino)
    return destino, True


def remover_xml_para_consulta(caminho_xml, pasta_notas):
    arquivo = Path(caminho_xml)
    pasta = Path(pasta_notas).resolve()
    if arquivo.suffix.lower() != ".xml" or arquivo.parent.resolve() != pasta:
        raise ValueError("O arquivo não pertence à lista de XMLs da consulta.")
    if not arquivo.is_file():
        raise FileNotFoundError("O XML não está mais disponível para consulta.")

    arquivo.unlink()
