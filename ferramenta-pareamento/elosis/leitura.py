# -*- coding: utf-8 -*-
"""
Leitura de bases de dados em CSV, DBF, Excel (XLSX/XLSM/XLS) e PDF (ELO-SIS).

Todas as colunas são lidas como texto. Bases de vigilância trazem códigos com
zeros à esquerda (CEP, CNES, código de município, CID) que a conversão
automática para número destrói silenciosamente — e trazem, também, valores
inválidos cuja preservação é condição para a etapa de qualificação.

Arquivos grandes são lidos em blocos, com relatório de progresso, de modo que
bases anuais completas do SIM, SINAN e SINASC sejam processadas em estações
de trabalho comuns.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd

from .dbf import ErroDBF, LeitorDBF

csv.field_size_limit(min(sys.maxsize, 2_147_483_647))

FORMATOS_SUPORTADOS = {
    ".csv": "CSV", ".txt": "CSV delimitado", ".tsv": "CSV delimitado por tabulação",
    ".dbf": "DBF (dBase/FoxPro)", ".xlsx": "Excel", ".xlsm": "Excel com macros",
    ".xls": "Excel 97-2003", ".pdf": "PDF",
}

_CODIFICACOES = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
_DELIMITADORES = (";", ",", "\t", "|")


class ErroLeitura(Exception):
    """Falha na leitura de uma base de dados."""


# --------------------------------------------------------------------------- #
# Detecção de codificação e delimitador
# --------------------------------------------------------------------------- #

def detectar_codificacao(caminho: Path, amostra_bytes: int = 256_000) -> str:
    with open(caminho, "rb") as arquivo:
        amostra = arquivo.read(amostra_bytes)
    if amostra.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for codificacao in _CODIFICACOES:
        try:
            amostra.decode(codificacao)
            return codificacao
        except UnicodeDecodeError:
            continue
    return "latin-1"


def detectar_delimitador(caminho: Path, codificacao: str) -> str:
    with open(caminho, "r", encoding=codificacao, errors="replace") as arquivo:
        cabecalho = arquivo.readline()
        segunda = arquivo.readline()
    amostra = cabecalho + segunda
    if not amostra.strip():
        return ";"
    try:
        return csv.Sniffer().sniff(amostra, delimiters="".join(_DELIMITADORES)).delimiter
    except csv.Error:
        contagens = {d: cabecalho.count(d) for d in _DELIMITADORES}
        melhor = max(contagens, key=contagens.get)
        return melhor if contagens[melhor] > 0 else ";"


# --------------------------------------------------------------------------- #
# Leitores por formato
# --------------------------------------------------------------------------- #

def _normalizar_colunas(colunas: Iterable) -> list[str]:
    vistas: dict[str, int] = {}
    saida = []
    for i, coluna in enumerate(colunas):
        nome = str(coluna).strip().replace("\n", " ").replace("\r", " ")
        nome = re.sub(r"\s+", " ", nome)
        if not nome or nome.lower().startswith("unnamed"):
            nome = f"COLUNA_{i + 1}"
        nome = nome.upper()
        if nome in vistas:
            vistas[nome] += 1
            nome = f"{nome}_{vistas[nome]}"
        else:
            vistas[nome] = 0
        saida.append(nome)
    return saida


def ler_csv(caminho: Path, limite: int | None = None,
            progresso: Callable[[int], None] | None = None,
            tamanho_bloco: int = 200_000) -> pd.DataFrame:
    codificacao = detectar_codificacao(caminho)
    delimitador = detectar_delimitador(caminho, codificacao)
    blocos, lidos = [], 0
    leitor = pd.read_csv(
        caminho, sep=delimitador, dtype=str, encoding=codificacao,
        keep_default_na=False, na_values=[], chunksize=tamanho_bloco,
        engine="python", on_bad_lines="warn", quoting=csv.QUOTE_MINIMAL,
    )
    for bloco in leitor:
        if limite is not None and lidos >= limite:
            break
        if limite is not None and lidos + len(bloco) > limite:
            bloco = bloco.iloc[: limite - lidos]
        blocos.append(bloco)
        lidos += len(bloco)
        if progresso:
            progresso(lidos)
    if not blocos:
        return pd.DataFrame()
    quadro = pd.concat(blocos, ignore_index=True)
    quadro.columns = _normalizar_colunas(quadro.columns)
    return quadro.fillna("")


def ler_dbf(caminho: Path, limite: int | None = None,
            progresso: Callable[[int], None] | None = None,
            tamanho_bloco: int = 100_000) -> pd.DataFrame:
    blocos, acumulado, lidos = [], [], 0
    with LeitorDBF(caminho) as leitor:
        for registro in leitor:
            acumulado.append(registro)
            lidos += 1
            if len(acumulado) >= tamanho_bloco:
                blocos.append(pd.DataFrame(acumulado, dtype=str))
                acumulado = []
                if progresso:
                    progresso(lidos)
            if limite is not None and lidos >= limite:
                break
    if acumulado:
        blocos.append(pd.DataFrame(acumulado, dtype=str))
    if progresso:
        progresso(lidos)
    if not blocos:
        return pd.DataFrame()
    quadro = pd.concat(blocos, ignore_index=True)
    quadro.columns = _normalizar_colunas(quadro.columns)
    return quadro.fillna("")


def ler_excel(caminho: Path, limite: int | None = None,
              aba: str | int | None = None,
              progresso: Callable[[int], None] | None = None) -> pd.DataFrame:
    motor = "openpyxl" if caminho.suffix.lower() in (".xlsx", ".xlsm") else None
    try:
        quadro = pd.read_excel(caminho, sheet_name=aba if aba is not None else 0,
                               dtype=str, engine=motor, nrows=limite)
    except ImportError as erro:
        raise ErroLeitura(
            f"Não foi possível abrir {caminho.name}: falta a biblioteca de leitura "
            f"do formato ({erro}). Para arquivos .xls antigos, salve como .xlsx "
            "ou instale o pacote 'xlrd'."
        ) from erro
    except Exception as erro:
        raise ErroLeitura(f"Falha ao ler {caminho.name}: {erro}") from erro
    if isinstance(quadro, dict):
        quadro = next(iter(quadro.values()))
    quadro.columns = _normalizar_colunas(quadro.columns)
    if progresso:
        progresso(len(quadro))
    return quadro.fillna("").astype(str)


def ler_pdf(caminho: Path, limite: int | None = None,
            progresso: Callable[[int], None] | None = None) -> pd.DataFrame:
    """Extrai tabelas de PDF.

    O PDF é formato de apresentação, não de intercâmbio de dados: a extração é
    sempre aproximada. A ferramenta a executa porque relatórios de sistemas
    legados às vezes só estão disponíveis nesse formato, mas sinaliza no
    relatório final que a base exige conferência reforçada.
    """
    tabelas: list[list[list[str]]] = []
    erro_biblioteca = None

    try:
        import pdfplumber  # type: ignore
        with pdfplumber.open(caminho) as pdf:
            for numero, pagina in enumerate(pdf.pages, start=1):
                for tabela in pagina.extract_tables() or []:
                    tabelas.append([[("" if c is None else str(c)) for c in linha]
                                    for linha in tabela])
                if progresso and numero % 10 == 0:
                    progresso(numero)
                if limite and sum(len(t) for t in tabelas) > limite + 1:
                    break
    except BaseException as erro:
        # Deliberadamente amplo. Bibliotecas opcionais de leitura de PDF
        # dependem de extensões compiladas que, em instalações institucionais,
        # podem estar ausentes ou quebradas — e falham de modos que não se
        # reduzem a ImportError. Nenhuma dessas falhas deve impedir a leitura
        # pela via alternativa, nem interromper a análise das demais bases.
        if isinstance(erro, (KeyboardInterrupt, SystemExit)):
            raise
        erro_biblioteca = erro
        tabelas = []

    if not tabelas:
        texto = _extrair_texto_pdf(caminho)
        if texto:
            tabelas = [_tabela_por_espacamento(texto)]

    if not tabelas or not any(tabelas):
        detalhe = (f" A extração assistida por biblioteca não pôde ser usada "
                   f"({type(erro_biblioteca).__name__}); restou apenas a "
                   f"leitura do texto corrido." if erro_biblioteca else "")
        raise ErroLeitura(
            f"Não foi possível extrair dados tabulares de {caminho.name}.{detalhe} "
            "Recomenda-se exportar a base em CSV, DBF ou Excel na origem."
        )

    # Consolida tabelas que compartilham o mesmo cabeçalho (tabela partida em páginas).
    cabecalho = tabelas[0][0]
    linhas: list[list[str]] = []
    for tabela in tabelas:
        inicio = 1 if tabela and tabela[0] == cabecalho else 0
        for linha in tabela[inicio:]:
            if any(str(c).strip() for c in linha):
                linhas.append(list(linha) + [""] * (len(cabecalho) - len(linha)))
    if limite:
        linhas = linhas[:limite]
    quadro = pd.DataFrame(linhas, columns=_normalizar_colunas(cabecalho))
    return quadro.fillna("").astype(str)


def _extrair_texto_pdf(caminho: Path) -> str:
    for modulo, classe in (("pypdf", "PdfReader"), ("PyPDF2", "PdfReader"),
                           ("pdfminer.high_level", "extract_text")):
        try:
            biblioteca = __import__(modulo, fromlist=[classe])
            alvo = getattr(biblioteca, classe)
            if classe == "extract_text":
                return alvo(str(caminho)) or ""
            leitor = alvo(str(caminho))
            return "\n".join((p.extract_text() or "") for p in leitor.pages)
        except BaseException as erro:
            if isinstance(erro, (KeyboardInterrupt, SystemExit)):
                raise
            continue
    return ""


def _tabela_por_espacamento(texto: str) -> list[list[str]]:
    linhas = [l for l in texto.splitlines() if l.strip()]
    return [re.split(r"\s{2,}|\t", l.strip()) for l in linhas]


# --------------------------------------------------------------------------- #
# Interface única
# --------------------------------------------------------------------------- #

def contar_registros(caminho: Path | str) -> int:
    """Conta registros sem carregar a base — útil para estimar o trabalho."""
    caminho = Path(caminho)
    sufixo = caminho.suffix.lower()
    try:
        if sufixo == ".dbf":
            with LeitorDBF(caminho) as leitor:
                return len(leitor)
        if sufixo in (".csv", ".txt", ".tsv"):
            codificacao = detectar_codificacao(caminho)
            with open(caminho, "r", encoding=codificacao, errors="replace") as arquivo:
                return max(0, sum(1 for _ in arquivo) - 1)
    except (OSError, ErroDBF):
        return -1
    return -1


def ler_base(caminho: Path | str, limite: int | None = None,
             aba: str | int | None = None,
             progresso: Callable[[int], None] | None = None) -> pd.DataFrame:
    """Lê qualquer formato suportado devolvendo um quadro de dados textual."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise ErroLeitura(f"Arquivo não encontrado: {caminho}")
    if caminho.stat().st_size == 0:
        raise ErroLeitura(f"Arquivo vazio: {caminho.name}")

    sufixo = caminho.suffix.lower()
    try:
        if sufixo in (".csv", ".txt", ".tsv"):
            quadro = ler_csv(caminho, limite, progresso)
        elif sufixo == ".dbf":
            quadro = ler_dbf(caminho, limite, progresso)
        elif sufixo in (".xlsx", ".xlsm", ".xls"):
            quadro = ler_excel(caminho, limite, aba, progresso)
        elif sufixo == ".pdf":
            quadro = ler_pdf(caminho, limite, progresso)
        else:
            raise ErroLeitura(
                f"Formato não suportado: {sufixo or '(sem extensão)'}. "
                f"Formatos aceitos: {', '.join(sorted(FORMATOS_SUPORTADOS))}."
            )
    except ErroDBF as erro:
        raise ErroLeitura(f"Falha ao ler o DBF {caminho.name}: {erro}") from erro

    if quadro.empty:
        raise ErroLeitura(f"Nenhum registro encontrado em {caminho.name}.")

    # Uniformiza: tudo texto, sem espaços de borda e sem marcadores nulos.
    for coluna in quadro.columns:
        quadro[coluna] = (quadro[coluna].astype(str)
                          .str.strip()
                          .replace({"nan": "", "None": "", "NaT": "", "<NA>": ""}))
    return quadro


def listar_abas_excel(caminho: Path | str) -> list[str]:
    try:
        return pd.ExcelFile(caminho).sheet_names
    except Exception:
        return []
