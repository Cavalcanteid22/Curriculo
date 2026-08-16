"""Gravacao de arquivos .xlsx usando apenas a biblioteca padrao.

Gera o pacote Office Open XML na mao (zip + XML), com suporte a varias abas,
cores de preenchimento, negrito, bordas, quebra de linha, formatos de numero
e data, largura de coluna, painel congelado, autofiltro e celulas mescladas.
"""

from __future__ import annotations

import datetime as _dt
import re
import zipfile
from typing import Any, Dict, List, Optional, Tuple

_BASE_DATA = _dt.date(1899, 12, 30)
_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# Formatos de numero personalizados (os indices abaixo de 164 sao reservados)
_FORMATOS = {
    "geral": None,
    "texto": "@",
    "inteiro": "#,##0",
    "decimal": "#,##0.00",
    "moeda": 'R$ #,##0.00',
    "percentual": "0.0%",
    "data": "dd/mm/yyyy",
    "data_hora": "dd/mm/yyyy hh:mm",
}


def _escapar(texto: str) -> str:
    texto = _CONTROLE.sub("", texto)
    return (
        texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def coluna_letra(indice: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA."""
    letras = ""
    indice += 1
    while indice:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def referencia(linha: int, coluna: int) -> str:
    return f"{coluna_letra(coluna)}{linha + 1}"


class Estilo:
    """Descricao de formatacao de celula."""

    def __init__(
        self,
        negrito: bool = False,
        italico: bool = False,
        tamanho: float = 10.0,
        cor: str = "FF1F2937",
        fundo: Optional[str] = None,
        borda: bool = False,
        quebra: bool = False,
        alinhamento: str = "",
        vertical: str = "center",
        formato: str = "geral",
        fonte: str = "Calibri",
    ) -> None:
        self.negrito = negrito
        self.italico = italico
        self.tamanho = tamanho
        self.cor = cor if len(cor) == 8 else "FF" + cor.lstrip("#")
        self.fundo = ("FF" + fundo.lstrip("#")) if fundo and len(fundo.lstrip("#")) == 6 else fundo
        self.borda = borda
        self.quebra = quebra
        self.alinhamento = alinhamento
        self.vertical = vertical
        self.formato = formato
        self.fonte = fonte

    def chave(self) -> Tuple:
        return (
            self.negrito, self.italico, self.tamanho, self.cor, self.fundo, self.borda,
            self.quebra, self.alinhamento, self.vertical, self.formato, self.fonte,
        )

    def com(self, **alteracoes) -> "Estilo":
        dados = {
            "negrito": self.negrito, "italico": self.italico, "tamanho": self.tamanho,
            "cor": self.cor, "fundo": self.fundo, "borda": self.borda,
            "quebra": self.quebra, "alinhamento": self.alinhamento,
            "vertical": self.vertical, "formato": self.formato, "fonte": self.fonte,
        }
        dados.update(alteracoes)
        return Estilo(**dados)


class Aba:
    def __init__(self, nome: str) -> None:
        self.nome = _nome_valido(nome)
        self.celulas: Dict[Tuple[int, int], Tuple[Any, Optional[Estilo]]] = {}
        self.larguras: Dict[int, float] = {}
        self.alturas: Dict[int, float] = {}
        self.congelar_em: Optional[Tuple[int, int]] = None
        self.autofiltro: Optional[str] = None
        self.mescladas: List[str] = []
        self.max_linha = -1
        self.max_coluna = -1
        self._proxima_linha = 0

    # -- escrita -----------------------------------------------------------

    def escrever(self, linha: int, coluna: int, valor: Any, estilo: Optional[Estilo] = None) -> None:
        self.celulas[(linha, coluna)] = (valor, estilo)
        self.max_linha = max(self.max_linha, linha)
        self.max_coluna = max(self.max_coluna, coluna)
        self._proxima_linha = max(self._proxima_linha, linha + 1)

    def escrever_linha(
        self,
        valores: List[Any],
        estilo: Optional[Estilo] = None,
        estilos: Optional[List[Optional[Estilo]]] = None,
        linha: Optional[int] = None,
        coluna_inicial: int = 0,
    ) -> int:
        indice = self._proxima_linha if linha is None else linha
        for deslocamento, valor in enumerate(valores):
            estilo_celula = estilos[deslocamento] if estilos and deslocamento < len(estilos) else estilo
            self.escrever(indice, coluna_inicial + deslocamento, valor, estilo_celula)
        self._proxima_linha = max(self._proxima_linha, indice + 1)
        return indice

    def pular_linha(self, quantidade: int = 1) -> None:
        self._proxima_linha += quantidade

    @property
    def proxima_linha(self) -> int:
        return self._proxima_linha

    # -- aparencia ---------------------------------------------------------

    def largura(self, coluna: int, largura: float) -> None:
        self.larguras[coluna] = largura

    def larguras_automaticas(self, minima: float = 9.0, maxima: float = 52.0) -> None:
        medidas: Dict[int, float] = {}
        for (_, coluna), (valor, _estilo) in self.celulas.items():
            texto = _texto_de(valor)
            tamanho = min(len(texto) + 2.5, maxima)
            medidas[coluna] = max(medidas.get(coluna, minima), tamanho)
        for coluna, medida in medidas.items():
            self.larguras.setdefault(coluna, max(minima, medida))

    def congelar(self, linha: int, coluna: int = 0) -> None:
        self.congelar_em = (linha, coluna)

    def aplicar_autofiltro(self, linha_cabecalho: int, coluna_inicial: int, coluna_final: int,
                           linha_final: Optional[int] = None) -> None:
        fim = self.max_linha if linha_final is None else linha_final
        self.autofiltro = (
            f"{referencia(linha_cabecalho, coluna_inicial)}:{referencia(max(fim, linha_cabecalho), coluna_final)}"
        )

    def mesclar(self, linha1: int, coluna1: int, linha2: int, coluna2: int) -> None:
        self.mescladas.append(f"{referencia(linha1, coluna1)}:{referencia(linha2, coluna2)}")


class Planilha:
    def __init__(self) -> None:
        self.abas: List[Aba] = []
        self._textos: Dict[str, int] = {}
        self._estilos: Dict[Tuple, int] = {}
        self._lista_estilos: List[Estilo] = []
        self.titulo = "Consolidacao e analise"
        self.autor = "Consolidador de Sistemas"

    def aba(self, nome: str) -> Aba:
        nova = Aba(nome)
        existentes = {a.nome for a in self.abas}
        if nova.nome in existentes:
            sufixo = 2
            base = nova.nome[:28]
            while f"{base}_{sufixo}" in existentes:
                sufixo += 1
            nova.nome = f"{base}_{sufixo}"
        self.abas.append(nova)
        return nova

    # -- gravacao ----------------------------------------------------------

    def salvar(self, caminho: str) -> str:
        for aba in self.abas:
            for (_pos, (valor, estilo)) in aba.celulas.items():
                if estilo is not None:
                    self._indice_estilo(estilo)
                if isinstance(valor, str) and valor:
                    self._indice_texto(valor)
        with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as pacote:
            pacote.writestr("[Content_Types].xml", self._content_types())
            pacote.writestr("_rels/.rels", _RELS_RAIZ)
            pacote.writestr("docProps/core.xml", self._core())
            pacote.writestr("docProps/app.xml", _APP)
            pacote.writestr("xl/workbook.xml", self._workbook())
            pacote.writestr("xl/_rels/workbook.xml.rels", self._workbook_rels())
            pacote.writestr("xl/styles.xml", self._styles())
            pacote.writestr("xl/sharedStrings.xml", self._shared_strings())
            for indice, aba in enumerate(self.abas, start=1):
                pacote.writestr(f"xl/worksheets/sheet{indice}.xml", self._sheet(aba))
        return caminho

    # -- indices internos --------------------------------------------------

    def _indice_texto(self, texto: str) -> int:
        if texto not in self._textos:
            self._textos[texto] = len(self._textos)
        return self._textos[texto]

    def _indice_estilo(self, estilo: Estilo) -> int:
        chave = estilo.chave()
        if chave not in self._estilos:
            self._estilos[chave] = len(self._lista_estilos) + 1  # 0 = estilo padrao
            self._lista_estilos.append(estilo)
        return self._estilos[chave]

    # -- partes do pacote --------------------------------------------------

    def _content_types(self) -> str:
        abas = "".join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
            f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in range(1, len(self.abas) + 1)
        )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            f'{abas}'
            '<Override PartName="/xl/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '<Override PartName="/xl/sharedStrings.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            '</Types>'
        )

    def _core(self) -> str:
        agora = _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<dc:title>{_escapar(self.titulo)}</dc:title>'
            f'<dc:creator>{_escapar(self.autor)}</dc:creator>'
            f'<cp:lastModifiedBy>{_escapar(self.autor)}</cp:lastModifiedBy>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{agora}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{agora}</dcterms:modified>'
            '</cp:coreProperties>'
        )

    def _workbook(self) -> str:
        abas = "".join(
            f'<sheet name="{_escapar(aba.nome)}" sheetId="{i}" r:id="rId{i}"/>'
            for i, aba in enumerate(self.abas, start=1)
        )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets>{abas}</sheets></workbook>'
        )

    def _workbook_rels(self) -> str:
        relacoes = "".join(
            f'<Relationship Id="rId{i}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(self.abas) + 1)
        )
        proximo = len(self.abas) + 1
        relacoes += (
            f'<Relationship Id="rId{proximo}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
            'Target="styles.xml"/>'
            f'<Relationship Id="rId{proximo + 1}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" '
            'Target="sharedStrings.xml"/>'
        )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{relacoes}</Relationships>'
        )

    def _shared_strings(self) -> str:
        itens = "".join(
            f'<si><t xml:space="preserve">{_escapar(texto)}</t></si>'
            for texto, _ in sorted(self._textos.items(), key=lambda item: item[1])
        )
        total = len(self._textos)
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            f'count="{total}" uniqueCount="{total}">{itens}</sst>'
        )

    def _styles(self) -> str:
        formatos_usados: Dict[str, int] = {}
        proximo_id = 164
        for estilo in self._lista_estilos:
            codigo = _FORMATOS.get(estilo.formato, estilo.formato)
            if codigo and codigo not in formatos_usados:
                formatos_usados[codigo] = proximo_id
                proximo_id += 1
        num_fmts = "".join(
            f'<numFmt numFmtId="{identificador}" formatCode="{_escapar(codigo)}"/>'
            for codigo, identificador in formatos_usados.items()
        )

        fontes = ['<font><sz val="10"/><color rgb="FF1F2937"/><name val="Calibri"/></font>']
        preenchimentos = [
            '<fill><patternFill patternType="none"/></fill>',
            '<fill><patternFill patternType="gray125"/></fill>',
        ]
        bordas = ['<border><left/><right/><top/><bottom/><diagonal/></border>']
        cor_borda = "FFD1D5DB"
        bordas.append(
            f'<border><left style="thin"><color rgb="{cor_borda}"/></left>'
            f'<right style="thin"><color rgb="{cor_borda}"/></right>'
            f'<top style="thin"><color rgb="{cor_borda}"/></top>'
            f'<bottom style="thin"><color rgb="{cor_borda}"/></bottom><diagonal/></border>'
        )
        indices_fonte: Dict[Tuple, int] = {}
        indices_fill: Dict[str, int] = {}
        xfs = ['<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>']

        for estilo in self._lista_estilos:
            chave_fonte = (estilo.negrito, estilo.italico, estilo.tamanho, estilo.cor, estilo.fonte)
            if chave_fonte not in indices_fonte:
                indices_fonte[chave_fonte] = len(fontes)
                fontes.append(
                    "<font>"
                    + ("<b/>" if estilo.negrito else "")
                    + ("<i/>" if estilo.italico else "")
                    + f'<sz val="{estilo.tamanho:g}"/><color rgb="{estilo.cor}"/>'
                    f'<name val="{_escapar(estilo.fonte)}"/></font>'
                )
            if estilo.fundo:
                if estilo.fundo not in indices_fill:
                    indices_fill[estilo.fundo] = len(preenchimentos)
                    preenchimentos.append(
                        f'<fill><patternFill patternType="solid">'
                        f'<fgColor rgb="{estilo.fundo}"/><bgColor indexed="64"/></patternFill></fill>'
                    )
                fill_id = indices_fill[estilo.fundo]
            else:
                fill_id = 0
            codigo = _FORMATOS.get(estilo.formato, estilo.formato)
            num_fmt_id = formatos_usados.get(codigo, 0) if codigo else 0
            border_id = 1 if estilo.borda else 0
            alinhamento = ""
            if estilo.alinhamento or estilo.quebra or estilo.vertical:
                partes = []
                if estilo.alinhamento:
                    partes.append(f'horizontal="{estilo.alinhamento}"')
                if estilo.vertical:
                    partes.append(f'vertical="{estilo.vertical}"')
                if estilo.quebra:
                    partes.append('wrapText="1"')
                alinhamento = f'<alignment {" ".join(partes)}/>'
            xfs.append(
                f'<xf numFmtId="{num_fmt_id}" fontId="{indices_fonte[chave_fonte]}" '
                f'fillId="{fill_id}" borderId="{border_id}" xfId="0" '
                f'applyFont="1" applyFill="1" applyBorder="1" '
                f'applyNumberFormat="{1 if num_fmt_id else 0}" '
                f'applyAlignment="{1 if alinhamento else 0}">{alinhamento}</xf>'
            )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            + (f'<numFmts count="{len(formatos_usados)}">{num_fmts}</numFmts>' if formatos_usados else "")
            + f'<fonts count="{len(fontes)}">{"".join(fontes)}</fonts>'
            + f'<fills count="{len(preenchimentos)}">{"".join(preenchimentos)}</fills>'
            + f'<borders count="{len(bordas)}">{"".join(bordas)}</borders>'
            + '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            + f'<cellXfs count="{len(xfs)}">{"".join(xfs)}</cellXfs>'
            + '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
            + '</styleSheet>'
        )

    def _sheet(self, aba: Aba) -> str:
        partes = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        ]
        if aba.max_linha >= 0:
            partes.append(
                f'<dimension ref="A1:{referencia(aba.max_linha, max(aba.max_coluna, 0))}"/>'
            )
        if aba.congelar_em:
            linha, coluna = aba.congelar_em
            celula = referencia(linha, coluna)
            painel = "bottomRight" if coluna else "bottomLeft"
            partes.append(
                '<sheetViews><sheetView workbookViewId="0" showGridLines="1">'
                f'<pane xSplit="{coluna}" ySplit="{linha}" topLeftCell="{celula}" '
                f'activePane="{painel}" state="frozen"/>'
                f'<selection pane="{painel}" activeCell="{celula}" sqref="{celula}"/>'
                '</sheetView></sheetViews>'
            )
        partes.append('<sheetFormatPr defaultRowHeight="15"/>')
        if aba.larguras:
            colunas = "".join(
                f'<col min="{c + 1}" max="{c + 1}" width="{largura:.1f}" customWidth="1"/>'
                for c, largura in sorted(aba.larguras.items())
            )
            partes.append(f"<cols>{colunas}</cols>")

        partes.append("<sheetData>")
        por_linha: Dict[int, List[Tuple[int, Any, Optional[Estilo]]]] = {}
        for (linha, coluna), (valor, estilo) in aba.celulas.items():
            por_linha.setdefault(linha, []).append((coluna, valor, estilo))
        for linha in sorted(por_linha):
            altura = f' ht="{aba.alturas[linha]:.1f}" customHeight="1"' if linha in aba.alturas else ""
            partes.append(f'<row r="{linha + 1}"{altura}>')
            for coluna, valor, estilo in sorted(por_linha[linha]):
                partes.append(self._celula(linha, coluna, valor, estilo))
            partes.append("</row>")
        partes.append("</sheetData>")

        if aba.autofiltro:
            partes.append(f'<autoFilter ref="{aba.autofiltro}"/>')
        if aba.mescladas:
            mescladas = "".join(f'<mergeCell ref="{ref}"/>' for ref in aba.mescladas)
            partes.append(f'<mergeCells count="{len(aba.mescladas)}">{mescladas}</mergeCells>')
        partes.append('<pageMargins left="0.5" right="0.5" top="0.6" bottom="0.6" header="0.3" footer="0.3"/>')
        partes.append("</worksheet>")
        return "".join(partes)

    def _celula(self, linha: int, coluna: int, valor: Any, estilo: Optional[Estilo]) -> str:
        ref = referencia(linha, coluna)
        indice_estilo = self._estilos.get(estilo.chave()) if estilo else None
        atributo_estilo = f' s="{indice_estilo}"' if indice_estilo else ""
        if valor is None or valor == "":
            return f'<c r="{ref}"{atributo_estilo}/>'
        if isinstance(valor, bool):
            return f'<c r="{ref}"{atributo_estilo} t="b"><v>{1 if valor else 0}</v></c>'
        if isinstance(valor, (_dt.datetime, _dt.date)):
            data = valor.date() if isinstance(valor, _dt.datetime) else valor
            serial = (data - _BASE_DATA).days
            return f'<c r="{ref}"{atributo_estilo}><v>{serial}</v></c>'
        if isinstance(valor, (int, float)):
            return f'<c r="{ref}"{atributo_estilo}><v>{valor!r}</v></c>'
        texto = str(valor)
        return f'<c r="{ref}"{atributo_estilo} t="s"><v>{self._indice_texto(texto)}</v></c>'


def _texto_de(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, (_dt.date, _dt.datetime)):
        return "00/00/0000"
    return str(valor)


_INVALIDOS_NOME = re.compile(r"[\\/*?:\[\]]")


def _nome_valido(nome: str) -> str:
    limpo = _INVALIDOS_NOME.sub("-", nome or "Planilha").strip("'")
    return (limpo[:31] or "Planilha")


_RELS_RAIZ = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="xl/workbook.xml"/>'
    '<Relationship Id="rId2" '
    'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
    'Target="docProps/core.xml"/>'
    '<Relationship Id="rId3" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" '
    'Target="docProps/app.xml"/>'
    '</Relationships>'
)

_APP = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
    'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
    '<Application>Consolidador de Sistemas</Application></Properties>'
)
