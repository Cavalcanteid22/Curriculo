"""Leitura robusta e em fluxo (streaming) de bases CSV grandes.

Bases do DATASUS chegam em codificações e separadores variados. Este módulo
detecta encoding e separador, normaliza os nomes das colunas e devolve as
linhas uma a uma — nunca carrega a base inteira na memória, o que permite
processar arquivos de milhões de registros em máquinas comuns da rede da SMS.
"""

from __future__ import annotations

import csv
import gzip
import io
import os
import sys
import unicodedata

csv.field_size_limit(min(sys.maxsize, 2_147_483_647))

ENCODINGS_CANDIDATOS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
SEPARADORES_CANDIDATOS = (";", ",", "\t", "|")


def _abrir_binario(caminho):
    if str(caminho).lower().endswith(".gz"):
        return gzip.open(caminho, "rb")
    return open(caminho, "rb")


def detectar_encoding(caminho, amostra_bytes=1_048_576):
    """Descobre a codificação testando as candidatas mais comuns no Brasil."""
    with _abrir_binario(caminho) as fb:
        amostra = fb.read(amostra_bytes)
    for enc in ENCODINGS_CANDIDATOS:
        try:
            amostra.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        return enc
    return "latin-1"  # latin-1 nunca falha; é a rede de segurança


def detectar_separador(caminho, encoding):
    """Escolhe o separador que produz mais colunas consistentes no cabeçalho."""
    with _abrir_binario(caminho) as fb:
        bruto = fb.read(262_144)
    texto = bruto.decode(encoding, errors="replace")
    linhas = [ln for ln in texto.splitlines() if ln.strip()][:5]
    if not linhas:
        return ";"
    melhor, melhor_qtd = ";", 0
    for sep in SEPARADORES_CANDIDATOS:
        contagens = [ln.count(sep) for ln in linhas]
        if not contagens or contagens[0] == 0:
            continue
        # o bom separador aparece o mesmo número de vezes em todas as linhas
        estavel = len(set(contagens)) == 1
        qtd = contagens[0] + (100 if estavel else 0)
        if qtd > melhor_qtd:
            melhor, melhor_qtd = sep, qtd
    return melhor


def normalizar_coluna(nome):
    """Padroniza nomes de coluna: sem acento, sem espaços, maiúsculo."""
    if nome is None:
        return ""
    txt = str(nome).replace("﻿", "").strip()
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = txt.replace(" ", "_").replace("-", "_").replace(".", "_")
    while "__" in txt:
        txt = txt.replace("__", "_")
    return txt.strip("_").upper()


def tamanho_legivel(n_bytes):
    for unidade in ("B", "KB", "MB", "GB", "TB"):
        if n_bytes < 1024 or unidade == "TB":
            return f"{n_bytes:,.1f} {unidade}".replace(",", "@").replace(".", ",").replace("@", ".")
        n_bytes /= 1024.0
    return f"{n_bytes} B"


class LeitorCSV:
    """Iterador de linhas do CSV como dicionários {COLUNA: valor}.

    Uso::

        with LeitorCSV("base.csv") as leitor:
            print(leitor.colunas)
            for n, linha in leitor:
                ...
    """

    def __init__(self, caminho, encoding=None, separador=None, mapa_colunas=None):
        self.caminho = caminho
        self.tamanho_bytes = os.path.getsize(caminho)
        self.encoding = encoding or detectar_encoding(caminho)
        self.separador = separador or detectar_separador(caminho, self.encoding)
        self.mapa_colunas = mapa_colunas or {}
        self._fb = None
        self._texto = None
        self._leitor = None
        self.colunas = []
        self.colunas_originais = []

    # -- ciclo de vida -------------------------------------------------- #
    def __enter__(self):
        self._fb = _abrir_binario(self.caminho)
        self._texto = io.TextIOWrapper(
            self._fb, encoding=self.encoding, errors="replace", newline=""
        )
        self._leitor = csv.reader(self._texto, delimiter=self.separador, quotechar='"')
        try:
            cabecalho = next(self._leitor)
        except StopIteration:
            cabecalho = []
        self.colunas_originais = cabecalho
        vistas = {}
        colunas = []
        for bruto in cabecalho:
            nome = normalizar_coluna(bruto)
            nome = self.mapa_colunas.get(nome, nome)
            if not nome:
                nome = f"COLUNA_{len(colunas) + 1}"
            if nome in vistas:  # cabeçalho repetido: desambigua
                vistas[nome] += 1
                nome = f"{nome}_{vistas[nome]}"
            else:
                vistas[nome] = 1
            colunas.append(nome)
        self.colunas = colunas
        return self

    def __exit__(self, *exc):
        try:
            if self._texto is not None:
                self._texto.close()
        finally:
            if self._fb is not None:
                self._fb.close()
        return False

    # -- iteração ------------------------------------------------------- #
    def __iter__(self):
        n = 1  # linha 1 é o cabeçalho
        colunas = self.colunas
        n_col = len(colunas)
        for campos in self._leitor:
            n += 1
            if not campos or (len(campos) == 1 and not campos[0].strip()):
                continue  # linha vazia
            if len(campos) < n_col:
                campos = campos + [""] * (n_col - len(campos))
            linha = dict(zip(colunas, campos))
            if len(campos) > n_col:  # colunas extras viram EXTRA_n
                for i, extra in enumerate(campos[n_col:], start=1):
                    linha[f"EXTRA_{i}"] = extra
            yield n, linha

    @property
    def bytes_lidos(self):
        try:
            return self._fb.tell()
        except Exception:  # pragma: no cover - arquivos gz não suportam tell fiel
            return 0


def escrever_csv(caminho, cabecalho, linhas, separador=";", encoding="utf-8-sig"):
    """Grava um CSV compatível com o Excel em português (separador ';')."""
    with open(caminho, "w", newline="", encoding=encoding) as fh:
        w = csv.writer(fh, delimiter=separador, quoting=csv.QUOTE_MINIMAL)
        w.writerow(cabecalho)
        for linha in linhas:
            w.writerow(linha)


def escrever_csv_gz(caminho, cabecalho, linhas, separador=";"):
    """Grava CSV compactado (usado no histórico de execuções)."""
    with gzip.open(caminho, "wt", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=separador, quoting=csv.QUOTE_MINIMAL)
        w.writerow(cabecalho)
        for linha in linhas:
            w.writerow(linha)


def ler_csv_gz(caminho):
    """Lê CSV compactado gravado por :func:`escrever_csv_gz`."""
    with gzip.open(caminho, "rt", newline="", encoding="utf-8") as fh:
        leitor = csv.reader(fh, delimiter=";")
        cabecalho = next(leitor, [])
        for campos in leitor:
            yield dict(zip(cabecalho, campos))
