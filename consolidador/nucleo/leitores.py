"""Leitura dos arquivos de entrada.

Formatos aceitos: .xlsx/.xlsm, .ods, .csv/.txt/.tsv, .dbf, .html/.htm, .json,
.xml simples. Tudo com a biblioteca padrao do Python: nenhuma instalacao
extra e necessaria na maquina do usuario.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import os
import re
import struct
import zipfile
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from . import texto as tx
from .tabela import Tabela

EXTENSOES_SUPORTADAS = (
    ".xlsx", ".xlsm", ".xltx", ".xls", ".ods", ".csv", ".txt", ".tsv",
    ".dbf", ".html", ".htm", ".json", ".xml", ".zip",
)

CODIFICACOES = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


class ErroLeitura(Exception):
    """Falha ao interpretar um arquivo de entrada."""


def ler_arquivo(caminho: str) -> List[Tabela]:
    """Devolve todas as tabelas encontradas no arquivo informado."""
    formato = identificar_formato(caminho)
    leitura = {
        "xlsx": ler_xlsx,
        "ods": ler_ods,
        "csv": lambda c: [ler_csv(c)],
        "dbf": lambda c: [ler_dbf(c)],
        "html": ler_html,
        "json": lambda c: [ler_json(c)],
        "xml": lambda c: [ler_xml(c)],
        "spreadsheetml": ler_spreadsheetml,
        "zip": ler_zip,
    }
    if formato == "ole2":
        raise ErroLeitura(
            "Este arquivo esta no formato binario do Excel 97-2003. "
            "Abra no Excel e salve como .xlsx ou .csv."
        )
    if formato not in leitura:
        raise ErroLeitura(f"Formato de arquivo nao reconhecido: {formato}")
    return [t for t in leitura[formato](caminho) if not t.vazia()]


def identificar_formato(caminho: str) -> str:
    """Descobre o formato pelo conteudo, e nao pela extensao.

    Sistemas de governo costumam exportar relatorios em HTML com o nome
    terminado em .xls; confiar na extensao faria a leitura falhar sem motivo.
    """
    try:
        with open(caminho, "rb") as arquivo:
            inicio = arquivo.read(8192)
    except OSError as erro:
        raise ErroLeitura(f"Nao foi possivel abrir o arquivo: {erro}") from erro
    if not inicio.strip():
        raise ErroLeitura("Arquivo vazio.")

    extensao = os.path.splitext(caminho)[1].lower()
    if inicio[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(caminho) as pacote:
                nomes = set(pacote.namelist())
        except zipfile.BadZipFile as erro:
            raise ErroLeitura(f"Arquivo compactado invalido: {erro}") from erro
        if "xl/workbook.xml" in nomes:
            return "xlsx"
        if "content.xml" in nomes:
            return "ods"
        return "zip"
    if inicio[:4] == b"\xd0\xcf\x11\xe0":
        return "ole2"
    if extensao == ".dbf" or (inicio[:1] in (b"\x02", b"\x03", b"\x04", b"\x05", b"\x30", b"\x31",
                                             b"\x83", b"\x8b", b"\xf5") and extensao != ".txt"
                              and _parece_dbf(inicio)):
        return "dbf"

    amostra = inicio.decode("latin-1", errors="replace").lstrip().lower()
    if "urn:schemas-microsoft-com:office:spreadsheet" in amostra:
        return "spreadsheetml"
    if amostra.startswith("<?xml") or amostra.startswith("<!doctype") or amostra.startswith("<"):
        if "<table" in amostra or "<html" in amostra or "<frameset" in amostra or "<frame " in amostra:
            return "html"
        return "xml"
    if "<table" in amostra or "<tr" in amostra or "<html" in amostra:
        return "html"
    if amostra.startswith("{") or amostra.startswith("["):
        return "json"
    return "csv"


def _parece_dbf(inicio: bytes) -> bool:
    if len(inicio) < 32:
        return False
    mes, dia = inicio[2], inicio[3]
    tamanho_registro = int.from_bytes(inicio[10:12], "little")
    return 1 <= mes <= 12 and 1 <= dia <= 31 and 0 < tamanho_registro < 65536


# --------------------------------------------------------------------------
# Texto delimitado (CSV / TXT / TSV)
# --------------------------------------------------------------------------


def _ler_texto(caminho: str) -> str:
    with open(caminho, "rb") as arquivo:
        bruto = arquivo.read()
    for codificacao in CODIFICACOES:
        try:
            return bruto.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return bruto.decode("latin-1", errors="replace")


def _descobrir_delimitador(amostra: str) -> str:
    try:
        return csv.Sniffer().sniff(amostra, delimiters=";,\t|").delimiter
    except csv.Error:
        pass
    linhas = [l for l in amostra.splitlines() if l.strip()][:20]
    melhor, melhor_nota = ";", -1.0
    for candidato in (";", ",", "\t", "|"):
        contagens = [l.count(candidato) for l in linhas]
        if not contagens or max(contagens) == 0:
            continue
        media = sum(contagens) / len(contagens)
        variacao = sum(abs(c - media) for c in contagens) / len(contagens)
        nota = media - variacao * 2
        if nota > melhor_nota:
            melhor, melhor_nota = candidato, nota
    return melhor


def ler_csv(caminho: str) -> Tabela:
    conteudo = _ler_texto(caminho)
    if not conteudo.strip():
        return Tabela(origem=caminho)
    delimitador = _descobrir_delimitador(conteudo[:8000])
    leitor = csv.reader(io.StringIO(conteudo), delimiter=delimitador)
    matriz = [linha for linha in leitor]
    return Tabela.de_matriz(matriz, origem=caminho, aba=os.path.basename(caminho))


# --------------------------------------------------------------------------
# XLSX (Office Open XML)
# --------------------------------------------------------------------------

_NS_PLANILHA = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_NS_REL_DOC = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_FORMATOS_DATA_PADRAO = set(range(14, 23)) | set(range(45, 48)) | {27, 30, 36, 50, 57}


def _referencia_para_indice(referencia: str) -> int:
    letras = re.match(r"([A-Z]+)", referencia or "")
    if not letras:
        return 0
    indice = 0
    for letra in letras.group(1):
        indice = indice * 26 + (ord(letra) - 64)
    return indice - 1


def _estilos_de_data(zip_arquivo: zipfile.ZipFile) -> set:
    """Descobre quais indices de estilo representam datas."""
    try:
        raiz = ET.fromstring(zip_arquivo.read("xl/styles.xml"))
    except KeyError:
        return set()
    formatos_data = set(_FORMATOS_DATA_PADRAO)
    for formato in raiz.iter(f"{_NS_PLANILHA}numFmt"):
        codigo = (formato.get("formatCode") or "").lower()
        codigo_sem_texto = re.sub(r'"[^"]*"', "", codigo)
        if re.search(r"[dmyh]", codigo_sem_texto) and "0" not in codigo_sem_texto.replace("0.0", ""):
            formatos_data.add(int(formato.get("numFmtId")))
    estilos = set()
    cell_xfs = raiz.find(f"{_NS_PLANILHA}cellXfs")
    if cell_xfs is None:
        return estilos
    for indice, xf in enumerate(cell_xfs.findall(f"{_NS_PLANILHA}xf")):
        if int(xf.get("numFmtId", 0)) in formatos_data:
            estilos.add(indice)
    return estilos


def _textos_compartilhados(zip_arquivo: zipfile.ZipFile) -> List[str]:
    try:
        dados = zip_arquivo.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    raiz = ET.fromstring(dados)
    textos = []
    for item in raiz.findall(f"{_NS_PLANILHA}si"):
        partes = [no.text or "" for no in item.iter(f"{_NS_PLANILHA}t")]
        textos.append("".join(partes))
    return textos


def _abas_do_xlsx(zip_arquivo: zipfile.ZipFile) -> List[Tuple[str, str]]:
    raiz = ET.fromstring(zip_arquivo.read("xl/workbook.xml"))
    relacoes: Dict[str, str] = {}
    try:
        raiz_rel = ET.fromstring(zip_arquivo.read("xl/_rels/workbook.xml.rels"))
        for relacao in raiz_rel:
            alvo = relacao.get("Target", "")
            alvo = alvo[1:] if alvo.startswith("/") else "xl/" + alvo.lstrip("./")
            relacoes[relacao.get("Id")] = alvo.replace("xl/xl/", "xl/")
    except KeyError:
        pass
    abas = []
    for indice, aba in enumerate(raiz.iter(f"{_NS_PLANILHA}sheet"), start=1):
        if (aba.get("state") or "visible") != "visible":
            continue
        identificador = aba.get(f"{_NS_REL_DOC}id")
        caminho = relacoes.get(identificador, f"xl/worksheets/sheet{indice}.xml")
        abas.append((aba.get("name", f"Planilha{indice}"), caminho))
    return abas


def ler_xlsx(caminho: str) -> List[Tabela]:
    tabelas = []
    with zipfile.ZipFile(caminho) as zip_arquivo:
        textos = _textos_compartilhados(zip_arquivo)
        estilos_data = _estilos_de_data(zip_arquivo)
        nomes = set(zip_arquivo.namelist())
        for nome_aba, caminho_aba in _abas_do_xlsx(zip_arquivo):
            if caminho_aba not in nomes:
                continue
            matriz = _ler_aba_xlsx(zip_arquivo.read(caminho_aba), textos, estilos_data)
            tabela = Tabela.de_matriz(matriz, origem=caminho, aba=nome_aba)
            if not tabela.vazia():
                tabelas.append(tabela)
    return tabelas


def _ler_aba_xlsx(dados: bytes, textos: List[str], estilos_data: set) -> List[List[Any]]:
    raiz = ET.fromstring(dados)
    matriz: List[List[Any]] = []
    for linha in raiz.iter(f"{_NS_PLANILHA}row"):
        celulas: List[Any] = []
        for celula in linha.findall(f"{_NS_PLANILHA}c"):
            indice = _referencia_para_indice(celula.get("r", ""))
            while len(celulas) < indice:
                celulas.append("")
            celulas.append(_valor_celula_xlsx(celula, textos, estilos_data))
        matriz.append(celulas)
    return matriz


def _valor_celula_xlsx(celula, textos: List[str], estilos_data: set) -> Any:
    tipo = celula.get("t", "n")
    if tipo == "inlineStr":
        return "".join(no.text or "" for no in celula.iter(f"{_NS_PLANILHA}t"))
    no_valor = celula.find(f"{_NS_PLANILHA}v")
    if no_valor is None or no_valor.text is None:
        return ""
    bruto = no_valor.text
    if tipo == "s":
        indice = int(bruto)
        return textos[indice] if 0 <= indice < len(textos) else ""
    if tipo == "b":
        return "SIM" if bruto in ("1", "true") else "NAO"
    if tipo == "e":
        return bruto
    if tipo in ("str", "d"):
        return bruto
    estilo = int(celula.get("s", 0) or 0)
    if estilo in estilos_data:
        try:
            data = _dt.date(1899, 12, 30) + _dt.timedelta(days=float(bruto))
            return data.strftime("%d/%m/%Y")
        except (ValueError, OverflowError):
            return bruto
    try:
        numero = float(bruto)
    except ValueError:
        return bruto
    return int(numero) if numero.is_integer() else numero


# --------------------------------------------------------------------------
# ODS (LibreOffice Calc)
# --------------------------------------------------------------------------

_NS_TABELA_ODS = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
_NS_TEXTO_ODS = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
_NS_OFFICE_ODS = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"


def ler_ods(caminho: str) -> List[Tabela]:
    with zipfile.ZipFile(caminho) as zip_arquivo:
        raiz = ET.fromstring(zip_arquivo.read("content.xml"))
    tabelas = []
    for tabela_xml in raiz.iter(f"{_NS_TABELA_ODS}table"):
        nome = tabela_xml.get(f"{_NS_TABELA_ODS}name", "Planilha")
        matriz: List[List[Any]] = []
        for linha_xml in tabela_xml.findall(f"{_NS_TABELA_ODS}table-row"):
            repeticoes_linha = int(linha_xml.get(f"{_NS_TABELA_ODS}number-rows-repeated", 1))
            celulas: List[Any] = []
            for celula_xml in linha_xml.findall(f"{_NS_TABELA_ODS}table-cell"):
                repeticoes = int(celula_xml.get(f"{_NS_TABELA_ODS}number-columns-repeated", 1))
                valor = celula_xml.get(f"{_NS_OFFICE_ODS}date-value") or \
                    celula_xml.get(f"{_NS_OFFICE_ODS}value") or \
                    " ".join(no.text or "" for no in celula_xml.iter(f"{_NS_TEXTO_ODS}p"))
                celulas.extend([tx.limpar(valor)] * min(repeticoes, 200))
            if repeticoes_linha > 50 and not any(celulas):
                continue
            matriz.extend([celulas] * min(repeticoes_linha, 200))
        tabela = Tabela.de_matriz(matriz, origem=caminho, aba=nome)
        if not tabela.vazia():
            tabelas.append(tabela)
    return tabelas


# --------------------------------------------------------------------------
# DBF (dBase III/IV, FoxPro)
# --------------------------------------------------------------------------


def ler_dbf(caminho: str) -> Tabela:
    with open(caminho, "rb") as arquivo:
        cabecalho = arquivo.read(32)
        if len(cabecalho) < 32:
            raise ErroLeitura("Arquivo DBF truncado.")
        _versao, _a, _m, _d, qtd_registros, inicio_dados, tamanho_registro = struct.unpack(
            "<BBBBLHH", cabecalho[:12]
        )
        campos = []
        while True:
            descritor = arquivo.read(32)
            if not descritor or descritor[0:1] in (b"\r", b"\x00", b""):
                break
            nome = descritor[:11].split(b"\x00")[0].decode("latin-1").strip()
            tipo = descritor[11:12].decode("latin-1")
            tamanho = descritor[16]
            decimais = descritor[17]
            campos.append((nome, tipo, tamanho, decimais))
        arquivo.seek(inicio_dados)
        linhas = []
        for _ in range(qtd_registros):
            registro = arquivo.read(tamanho_registro)
            if not registro or len(registro) < tamanho_registro:
                break
            if registro[0:1] == b"*":  # registro marcado como excluido
                continue
            posicao = 1
            valores = {}
            for nome, tipo, tamanho, decimais in campos:
                bruto = registro[posicao:posicao + tamanho]
                posicao += tamanho
                valores[nome] = _valor_campo_dbf(bruto, tipo, decimais)
            linhas.append(valores)
    colunas = [c[0] for c in campos]
    return Tabela(colunas, linhas, origem=caminho, aba=os.path.basename(caminho))


def _valor_campo_dbf(bruto: bytes, tipo: str, decimais: int) -> Any:
    texto = bruto.decode("latin-1", errors="replace").strip()
    if tipo == "D":  # data AAAAMMDD
        if len(texto) == 8 and texto.isdigit():
            try:
                return _dt.date(int(texto[:4]), int(texto[4:6]), int(texto[6:])).strftime("%d/%m/%Y")
            except ValueError:
                return texto
        return ""
    if tipo in ("N", "F", "B"):
        if not texto:
            return ""
        try:
            return float(texto) if decimais else int(float(texto))
        except ValueError:
            return texto
    if tipo == "L":
        return {"T": "SIM", "Y": "SIM", "F": "NAO", "N": "NAO"}.get(texto.upper(), "")
    if tipo in ("M", "G", "P"):  # campos memo: conteudo fica em arquivo .dbt/.fpt
        return f"[memo {texto}]" if texto and texto != "0" * len(texto) else ""
    return tx.limpar(texto)


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------


class _ExtratorTabelasHTML(HTMLParser):
    """Extrai tabelas de um HTML, tratando colspan e rowspan."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tabelas: List[List[List[str]]] = []
        self._pilha: List[List[List[str]]] = []
        self._linha: List[str] = []
        self._celula: List[str] = []
        self._em_celula = False
        self._pendente_colspan = 1
        self._pendentes_rowspan: Dict[int, Tuple[int, str]] = {}
        self._ignorar = 0

    def handle_starttag(self, tag, attrs):
        atributos = dict(attrs)
        if tag == "table":
            self._pilha.append([])
            self._pendentes_rowspan = {}
        elif tag == "tr" and self._pilha:
            self._linha = []
        elif tag in ("td", "th") and self._pilha:
            self._em_celula = True
            self._celula = []
            try:
                self._pendente_colspan = max(1, min(int(atributos.get("colspan", 1)), 50))
            except ValueError:
                self._pendente_colspan = 1
            try:
                self._rowspan_atual = max(1, min(int(atributos.get("rowspan", 1)), 500))
            except ValueError:
                self._rowspan_atual = 1
        elif tag in ("script", "style"):
            self._ignorar += 1
        elif tag in ("br", "p", "div", "li") and self._em_celula:
            # A quebra de linha separa rotulos dentro da mesma celula
            # ("DISPENSADOR: X<br>MEDICO: Y") e precisa sobreviver a leitura.
            self._celula.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._ignorar:
            self._ignorar -= 1
        elif tag in ("td", "th") and self._em_celula:
            texto = "\n".join(
                parte for parte in
                (tx.limpar(p) for p in "".join(self._celula).split("\n")) if parte
            )
            posicao = len(self._linha)
            while posicao in self._pendentes_rowspan:
                restante, valor = self._pendentes_rowspan[posicao]
                self._linha.append(valor)
                posicao = len(self._linha)
            self._linha.extend([texto] * self._pendente_colspan)
            if getattr(self, "_rowspan_atual", 1) > 1:
                self._pendentes_rowspan[posicao] = (self._rowspan_atual - 1, texto)
            self._em_celula = False
        elif tag == "tr" and self._pilha:
            for posicao in sorted(self._pendentes_rowspan):
                if posicao >= len(self._linha):
                    self._linha.append(self._pendentes_rowspan[posicao][1])
            self._pendentes_rowspan = {
                p: (r - 1, v) for p, (r, v) in self._pendentes_rowspan.items() if r - 1 > 0
            }
            if self._linha:
                self._pilha[-1].append(self._linha)
            self._linha = []
        elif tag == "table" and self._pilha:
            tabela = self._pilha.pop()
            if tabela:
                if self._pilha:
                    self._pilha[-1].extend(tabela)  # tabela aninhada vira parte da externa
                else:
                    self.tabelas.append(tabela)

    def handle_data(self, dados):
        if self._em_celula and not self._ignorar:
            self._celula.append(dados)


def ler_html(caminho: str, _visitados: Optional[set] = None) -> List[Tabela]:
    conteudo = _ler_texto(caminho)
    extrator = _ExtratorTabelasHTML()
    extrator.feed(conteudo)
    extrator.close()
    tabelas = []
    for indice, matriz in enumerate(extrator.tabelas, start=1):
        if len(matriz) < 2:
            continue
        tabela = Tabela.de_matriz(matriz, origem=caminho, aba=f"tabela_{indice}")
        if not tabela.vazia():
            tabelas.append(tabela)
    if not tabelas:
        tabelas = _ler_quadros_html(caminho, conteudo, _visitados or {os.path.abspath(caminho)})
    if not tabelas:
        raise ErroLeitura("Nenhuma tabela HTML com dados foi encontrada no arquivo.")
    # Relatorios costumam quebrar a mesma tabela em varios blocos por pagina:
    # se as colunas coincidem, unifica.
    return _unir_tabelas_equivalentes(tabelas)


_RE_QUADRO = re.compile(r"""(?i)<frame[^>]+src\s*=\s*["']([^"']+)["']""")


def _ler_quadros_html(caminho: str, conteudo: str, visitados: set) -> List[Tabela]:
    """Le as paginas apontadas por um HTML de quadros (frameset).

    O Excel, ao salvar como pagina da web, gera um arquivo indice com os dados
    em uma pasta ao lado ('RELATORIO (3)_arquivos/sheet001.htm').
    """
    pasta = os.path.dirname(os.path.abspath(caminho))
    tabelas: List[Tabela] = []
    faltando: List[str] = []
    for referencia in _RE_QUADRO.findall(conteudo):
        alvo = unquote(referencia.split("#")[0].replace("\\", "/")).strip()
        if not alvo or alvo.lower().startswith(("http://", "https://", "javascript:")):
            continue
        if os.path.splitext(alvo)[1].lower() not in (".htm", ".html", ""):
            continue
        completo = os.path.normpath(os.path.join(pasta, *alvo.split("/")))
        if os.path.abspath(completo) in visitados:
            continue
        visitados.add(os.path.abspath(completo))
        if not os.path.isfile(completo):
            if "tabstrip" not in alvo.lower() and "filelist" not in alvo.lower():
                faltando.append(alvo)
            continue
        try:
            for tabela in ler_html(completo, visitados):
                tabela.origem = caminho
                tabela.aba = os.path.splitext(os.path.basename(completo))[0]
                tabelas.append(tabela)
        except ErroLeitura:
            continue
    if not tabelas and faltando:
        pasta_dados = faltando[0].split("/")[0]
        raise ErroLeitura(
            "Este arquivo nao contem dados: ele e so o indice de uma planilha que foi aberta no "
            "Excel e salva como 'Pagina da Web'. Os dados ficam na pasta "
            f"'{pasta_dados}', que precisa estar no mesmo local. Como resolver, do mais simples "
            "para o mais trabalhoso: (1) use o arquivo como veio do sistema, sem reabrir e salvar "
            "pelo Excel; (2) abra no Excel e salve com 'Salvar como' -> 'Pasta de Trabalho do "
            f"Excel (*.xlsx)'; (3) compacte o arquivo junto com a pasta '{pasta_dados}' em um .zip "
            "e use o .zip como entrada."
        )
    return tabelas


def ler_zip(caminho: str) -> List[Tabela]:
    """Le uma pasta compactada.

    Serve para o caso em que a planilha foi salva como pagina da web e precisa
    viajar junto com a pasta '..._arquivos': basta compactar os dois e enviar.
    """
    import tempfile

    with zipfile.ZipFile(caminho) as pacote:
        nomes = [n for n in pacote.namelist() if not n.endswith("/")]
        suportados = [
            n for n in nomes
            if os.path.splitext(n)[1].lower() in EXTENSOES_SUPORTADAS
        ]
        if not suportados:
            raise ErroLeitura("O arquivo compactado nao contem nenhum arquivo de dados.")
        # Um indice de pagina da web e suas partes: le so o indice, que ja
        # aponta para as partes.
        principais = [n for n in suportados if "_arquivos/" not in n and "_files/" not in n]
        escolhidos = principais or suportados
        with tempfile.TemporaryDirectory(prefix="consolidador_zip_") as pasta:
            pacote.extractall(pasta)
            tabelas: List[Tabela] = []
            erros: List[str] = []
            for nome in escolhidos:
                completo = os.path.join(pasta, *nome.split("/"))
                if not os.path.isfile(completo):
                    continue
                try:
                    for tabela in ler_arquivo(completo):
                        tabela.origem = caminho
                        tabela.aba = f"{os.path.basename(nome)}"
                        tabelas.append(tabela)
                except ErroLeitura as erro:
                    erros.append(f"{os.path.basename(nome)}: {erro}")
    if not tabelas:
        detalhe = " ".join(erros) if erros else ""
        raise ErroLeitura(f"Nenhuma tabela foi encontrada dentro do arquivo compactado. {detalhe}")
    return tabelas


def ler_spreadsheetml(caminho: str) -> List[Tabela]:
    """Le o formato 'Planilha XML 2003' do Excel (SpreadsheetML)."""
    ns = "{urn:schemas-microsoft-com:office:spreadsheet}"
    raiz = ET.fromstring(_ler_texto(caminho))
    tabelas = []
    for indice, planilha in enumerate(raiz.iter(f"{ns}Worksheet"), start=1):
        nome = planilha.get(f"{ns}Name", f"Planilha{indice}")
        matriz: List[List[Any]] = []
        for linha_xml in planilha.iter(f"{ns}Row"):
            celulas: List[Any] = []
            for celula_xml in linha_xml.findall(f"{ns}Cell"):
                indice_celula = celula_xml.get(f"{ns}Index")
                if indice_celula:
                    while len(celulas) < int(indice_celula) - 1:
                        celulas.append("")
                dado = celula_xml.find(f"{ns}Data")
                valor = "".join(dado.itertext()) if dado is not None else ""
                repeticoes = int(celula_xml.get(f"{ns}MergeAcross", 0)) + 1
                celulas.extend([tx.limpar(valor)] * repeticoes)
            matriz.append(celulas)
        tabela = Tabela.de_matriz(matriz, origem=caminho, aba=nome)
        if not tabela.vazia():
            tabelas.append(tabela)
    if not tabelas:
        raise ErroLeitura("Nenhuma planilha com dados foi encontrada no arquivo XML do Excel.")
    return tabelas


def _unir_tabelas_equivalentes(tabelas: List[Tabela]) -> List[Tabela]:
    grupos: List[List[Tabela]] = []
    for tabela in tabelas:
        assinatura = tuple(tx.chave_cabecalho(c) for c in tabela.colunas)
        for grupo in grupos:
            if tuple(tx.chave_cabecalho(c) for c in grupo[0].colunas) == assinatura:
                grupo.append(tabela)
                break
        else:
            grupos.append([tabela])
    resultado = []
    for grupo in grupos:
        if len(grupo) == 1:
            resultado.append(grupo[0])
        else:
            unida = Tabela(
                list(grupo[0].colunas),
                [dict(l) for t in grupo for l in t.linhas],
                origem=grupo[0].origem,
                aba=f"{grupo[0].aba} (+{len(grupo) - 1} blocos)",
            )
            resultado.append(unida)
    return resultado


# --------------------------------------------------------------------------
# JSON e XML
# --------------------------------------------------------------------------


def ler_json(caminho: str) -> Tabela:
    dados = json.loads(_ler_texto(caminho))
    registros = _achar_lista_de_registros(dados)
    if registros is None:
        raise ErroLeitura("O JSON nao contem uma lista de registros reconhecivel.")
    colunas: List[str] = []
    linhas = []
    for item in registros:
        plano = _achatar(item)
        for chave in plano:
            if chave not in colunas:
                colunas.append(chave)
        linhas.append(plano)
    for linha in linhas:
        for coluna in colunas:
            linha.setdefault(coluna, "")
    return Tabela(colunas, linhas, origem=caminho, aba=os.path.basename(caminho))


def _achar_lista_de_registros(dados):
    if isinstance(dados, list) and dados and isinstance(dados[0], dict):
        return dados
    if isinstance(dados, dict):
        for valor in dados.values():
            achado = _achar_lista_de_registros(valor)
            if achado:
                return achado
    return None


def _achatar(objeto, prefixo: str = "") -> Dict[str, Any]:
    plano: Dict[str, Any] = {}
    if isinstance(objeto, dict):
        for chave, valor in objeto.items():
            nome = f"{prefixo}.{chave}" if prefixo else str(chave)
            plano.update(_achatar(valor, nome))
    elif isinstance(objeto, list):
        plano[prefixo] = "; ".join(tx.limpar(v) for v in objeto if not isinstance(v, (dict, list)))
    else:
        plano[prefixo or "valor"] = tx.limpar(objeto)
    return plano


def ler_xml(caminho: str) -> Tabela:
    raiz = ET.parse(caminho).getroot()
    candidatos: Dict[str, List] = {}
    for filho in raiz.iter():
        netos = list(filho)
        if netos and len({n.tag for n in netos}) == 1 and len(netos) > 1:
            candidatos.setdefault(netos[0].tag, []).extend(netos)
    if not candidatos:
        raise ErroLeitura("O XML nao contem uma lista de registros reconhecivel.")
    elementos = max(candidatos.values(), key=len)
    colunas: List[str] = []
    linhas = []
    for elemento in elementos:
        registro: Dict[str, Any] = {}
        for chave, valor in elemento.attrib.items():
            registro[chave] = tx.limpar(valor)
        for filho in elemento:
            registro[re.sub(r"\{.*\}", "", filho.tag)] = tx.limpar(filho.text)
        if not registro:
            continue
        for chave in registro:
            if chave not in colunas:
                colunas.append(chave)
        linhas.append(registro)
    for linha in linhas:
        for coluna in colunas:
            linha.setdefault(coluna, "")
    return Tabela(colunas, linhas, origem=caminho, aba=os.path.basename(caminho))
