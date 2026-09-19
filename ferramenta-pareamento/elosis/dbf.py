# -*- coding: utf-8 -*-
"""
Leitor de arquivos DBF (dBase III/IV, FoxPro, Visual FoxPro) em Python puro.

Os sistemas SIM, SINAN e SINASC exportam suas bases em DBF. O leitor foi
escrito sem dependências externas e opera por fluxo (streaming), lendo um
registro por vez: arquivos de centenas de megabytes são processados sem que
a base inteira precise residir em memória.
"""

from __future__ import annotations

import struct
from datetime import date
from pathlib import Path
from typing import Iterator

# Mapa dos identificadores de página de código gravados no byte 29 do
# cabeçalho. As exportações do DATASUS usam, em geral, cp850 ou cp1252.
_PAGINAS_DE_CODIGO = {
    0x01: "cp437", 0x02: "cp850", 0x03: "cp1252", 0x04: "mac_roman",
    0x64: "cp852", 0x65: "cp866", 0x66: "cp865", 0x67: "cp861",
    0x6A: "cp737", 0x6B: "cp857", 0x78: "cp950", 0x79: "cp949",
    0x7A: "cp936", 0x7B: "cp932", 0x7C: "cp874", 0x7D: "cp1255",
    0x7E: "cp1256", 0x96: "mac_cyrillic", 0x97: "mac_latin2",
    0x98: "mac_greek", 0xC8: "cp1250", 0xC9: "cp1251", 0xCA: "cp1254",
    0xCB: "cp1253", 0xCC: "cp1257",
}

_ORDEM_TENTATIVAS = ("cp850", "cp1252", "latin-1", "utf-8")


class ErroDBF(Exception):
    """Falha na leitura de arquivo DBF."""


class Campo:
    __slots__ = ("nome", "tipo", "tamanho", "decimais", "deslocamento")

    def __init__(self, nome: str, tipo: str, tamanho: int, decimais: int,
                 deslocamento: int):
        self.nome = nome
        self.tipo = tipo
        self.tamanho = tamanho
        self.decimais = decimais
        self.deslocamento = deslocamento

    def __repr__(self) -> str:  # pragma: no cover - auxílio a diagnóstico
        return f"Campo({self.nome}, {self.tipo}{self.tamanho}.{self.decimais})"


class LeitorDBF:
    """Percorre um arquivo DBF devolvendo dicionários de texto.

    Todos os valores são devolvidos como texto. A decisão é deliberada: a
    conversão prematura de tipos destrói justamente a evidência de
    inconsistência que a ferramenta precisa detectar — uma data "31/02/2024"
    ou um código fora de domínio deve chegar íntegro à etapa de qualificação.
    """

    def __init__(self, caminho: Path | str, codificacao: str | None = None,
                 incluir_excluidos: bool = False):
        self.caminho = Path(caminho)
        if not self.caminho.exists():
            raise ErroDBF(f"Arquivo não encontrado: {self.caminho}")
        self.incluir_excluidos = incluir_excluidos
        self._arquivo = open(self.caminho, "rb")
        try:
            self._ler_cabecalho()
        except Exception:
            self._arquivo.close()
            raise
        self.codificacao = codificacao or self._detectar_codificacao()
        self._memo = self._abrir_memo()

    # -- cabeçalho -------------------------------------------------------- #

    def _ler_cabecalho(self) -> None:
        cabecalho = self._arquivo.read(32)
        if len(cabecalho) < 32:
            raise ErroDBF("Cabeçalho DBF truncado.")
        (self.versao, ano, mes, dia, self.n_registros,
         self.tamanho_cabecalho, self.tamanho_registro) = struct.unpack(
            "<BBBBIHH", cabecalho[:12])
        self._id_pagina = cabecalho[29]
        try:
            self.data_atualizacao = date(1900 + ano if ano < 80 else 2000 + (ano - 100)
                                         if ano >= 100 else 1900 + ano, mes or 1, dia or 1)
        except ValueError:
            self.data_atualizacao = None

        self.campos: list[Campo] = []
        deslocamento = 1  # byte 0 do registro guarda a marca de exclusão
        while True:
            bruto = self._arquivo.read(32)
            if not bruto or bruto[0] in (0x0D, 0x00):
                break
            if len(bruto) < 32:
                break
            nome = bruto[:11].split(b"\x00")[0].decode("ascii", "replace").strip()
            tipo = chr(bruto[11])
            tamanho = bruto[16]
            decimais = bruto[17]
            if tipo in ("C",) and self.versao in (0x30, 0x31, 0x32, 0xF5, 0xFB):
                # Visual FoxPro grava o tamanho de campos C longos em 2 bytes.
                tamanho = bruto[16] + (bruto[17] << 8) if bruto[17] and tamanho else tamanho
                decimais = 0
            self.campos.append(Campo(nome, tipo, tamanho, decimais, deslocamento))
            deslocamento += tamanho
        if not self.campos:
            raise ErroDBF("Nenhum campo identificado no arquivo DBF.")
        self.nomes = [c.nome for c in self.campos]

    def _detectar_codificacao(self) -> str:
        declarada = _PAGINAS_DE_CODIGO.get(self._id_pagina)
        amostra = self._amostrar_bytes()
        candidatas = ([declarada] if declarada else []) + list(_ORDEM_TENTATIVAS)
        for candidata in candidatas:
            if not candidata:
                continue
            try:
                amostra.decode(candidata)
                return candidata
            except (UnicodeDecodeError, LookupError):
                continue
        return "latin-1"  # nunca falha; preserva os bytes

    def _amostrar_bytes(self, registros: int = 200) -> bytes:
        posicao = self._arquivo.tell()
        self._arquivo.seek(self.tamanho_cabecalho)
        dados = self._arquivo.read(self.tamanho_registro * registros)
        self._arquivo.seek(posicao)
        return dados

    def _abrir_memo(self):
        """Abre o arquivo de memorandos (.FPT/.DBT), se houver campos M."""
        if not any(c.tipo in ("M", "G", "P", "B") and c.tamanho in (4, 10)
                   for c in self.campos):
            return None
        for sufixo in (".fpt", ".FPT", ".dbt", ".DBT"):
            candidato = self.caminho.with_suffix(sufixo)
            if candidato.exists():
                try:
                    return _ArquivoMemo(candidato)
                except Exception:
                    return None
        return None

    # -- leitura ---------------------------------------------------------- #

    def __iter__(self) -> Iterator[dict]:
        self._arquivo.seek(self.tamanho_cabecalho)
        lidos = 0
        while True:
            if self.n_registros and lidos >= self.n_registros:
                break
            bruto = self._arquivo.read(self.tamanho_registro)
            if not bruto or len(bruto) < self.tamanho_registro:
                break
            if bruto[0:1] == b"\x1a":  # marca de fim de arquivo
                break
            lidos += 1
            excluido = bruto[0:1] == b"*"
            if excluido and not self.incluir_excluidos:
                continue
            registro = self._converter(bruto)
            if self.incluir_excluidos:
                registro["_EXCLUIDO_DBF"] = "S" if excluido else "N"
            yield registro

    def _converter(self, bruto: bytes) -> dict:
        registro = {}
        for campo in self.campos:
            fatia = bruto[campo.deslocamento:campo.deslocamento + campo.tamanho]
            registro[campo.nome] = self._converter_campo(campo, fatia)
        return registro

    def _converter_campo(self, campo: Campo, fatia: bytes) -> str:
        tipo = campo.tipo
        if tipo in ("C", "N", "F", "D", "L", "+"):
            texto = fatia.decode(self.codificacao, "replace").strip()
            texto = texto.replace("\x00", "").strip()
            if tipo == "D" and len(texto) == 8 and texto.isdigit():
                return f"{texto[0:4]}-{texto[4:6]}-{texto[6:8]}"
            if tipo == "L":
                return {"T": "S", "Y": "S", "F": "N", "N": "N"}.get(texto.upper(), "")
            return texto
        if tipo == "I":  # inteiro binário de 4 bytes
            if len(fatia) >= 4:
                return str(struct.unpack("<i", fatia[:4])[0])
            return ""
        if tipo in ("B", "O"):  # ponto flutuante de 8 bytes
            if len(fatia) >= 8:
                return str(struct.unpack("<d", fatia[:8])[0])
            return ""
        if tipo == "Y":  # moeda
            if len(fatia) >= 8:
                return str(struct.unpack("<q", fatia[:8])[0] / 10000.0)
            return ""
        if tipo in ("T", "@"):  # data-hora juliana
            if len(fatia) >= 8:
                dias, milissegundos = struct.unpack("<ii", fatia[:8])
                if dias == 0:
                    return ""
                try:
                    from datetime import datetime, timedelta
                    base = datetime(1, 1, 1) + timedelta(days=dias - 1721426)
                    base += timedelta(milliseconds=milissegundos)
                    return base.isoformat(sep=" ", timespec="seconds")
                except (ValueError, OverflowError):
                    return ""
            return ""
        if tipo in ("M", "G", "P"):
            texto = fatia.decode(self.codificacao, "replace").strip().replace("\x00", "")
            if self._memo and texto.isdigit():
                return self._memo.ler(int(texto), self.codificacao)
            return texto
        return fatia.decode(self.codificacao, "replace").strip().replace("\x00", "")

    # -- ciclo de vida ---------------------------------------------------- #

    def fechar(self) -> None:
        try:
            self._arquivo.close()
        except Exception:
            pass
        if self._memo:
            self._memo.fechar()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.fechar()

    def __len__(self) -> int:
        return int(self.n_registros)


class _ArquivoMemo:
    """Acesso a blocos de memorando em arquivos .FPT (FoxPro) e .DBT (dBase)."""

    def __init__(self, caminho: Path):
        self.caminho = caminho
        self._arquivo = open(caminho, "rb")
        self.formato = "fpt" if caminho.suffix.lower() == ".fpt" else "dbt"
        cabecalho = self._arquivo.read(512)
        if self.formato == "fpt" and len(cabecalho) >= 8:
            self.tamanho_bloco = struct.unpack(">H", cabecalho[6:8])[0] or 64
        else:
            self.tamanho_bloco = 512

    def ler(self, bloco: int, codificacao: str) -> str:
        if bloco <= 0:
            return ""
        try:
            self._arquivo.seek(bloco * self.tamanho_bloco)
            if self.formato == "fpt":
                cabecalho = self._arquivo.read(8)
                if len(cabecalho) < 8:
                    return ""
                _, tamanho = struct.unpack(">II", cabecalho)
                if tamanho > 50_000_000:
                    return ""
                return self._arquivo.read(tamanho).decode(codificacao, "replace").strip()
            dados = self._arquivo.read(self.tamanho_bloco * 8)
            fim = dados.find(b"\x1a")
            if fim >= 0:
                dados = dados[:fim]
            return dados.decode(codificacao, "replace").strip()
        except (OSError, struct.error):
            return ""

    def fechar(self) -> None:
        try:
            self._arquivo.close()
        except Exception:
            pass


def escrever_dbf(caminho: Path | str, colunas: list[str], linhas: list[dict],
                 tamanhos: dict[str, int] | None = None,
                 codificacao: str = "cp850") -> Path:
    """Grava um DBF dBase III simples — usado na geração de bases de teste."""
    caminho = Path(caminho)
    tamanhos = tamanhos or {}
    larguras = {}
    for coluna in colunas:
        if coluna in tamanhos:
            larguras[coluna] = min(254, max(1, tamanhos[coluna]))
        else:
            maior = max((len(str(linha.get(coluna, "") or "")) for linha in linhas),
                        default=1)
            larguras[coluna] = min(254, max(1, maior))

    tamanho_cabecalho = 32 + 32 * len(colunas) + 1
    tamanho_registro = 1 + sum(larguras[c] for c in colunas)
    hoje = date.today()

    with open(caminho, "wb") as saida:
        saida.write(struct.pack("<BBBBIHH20x", 0x03, hoje.year - 1900, hoje.month,
                                hoje.day, len(linhas), tamanho_cabecalho,
                                tamanho_registro))
        for coluna in colunas:
            nome = coluna[:10].encode("ascii", "replace").ljust(11, b"\x00")
            saida.write(nome + b"C" + b"\x00" * 4
                        + bytes([larguras[coluna]]) + b"\x00" * 15)
        saida.write(b"\x0D")
        for linha in linhas:
            saida.write(b" ")
            for coluna in colunas:
                valor = str(linha.get(coluna, "") or "")
                saida.write(valor.encode(codificacao, "replace")[:larguras[coluna]]
                            .ljust(larguras[coluna], b" "))
        saida.write(b"\x1A")
    return caminho
