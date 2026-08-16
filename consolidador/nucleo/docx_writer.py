"""Gravacao de documentos .docx usando apenas a biblioteca padrao.

Suporta titulo, subtitulos hierarquicos, paragrafos formatados, listas com
marcador e numeradas, tabelas com cabecalho sombreado e cores por celula,
sumario automatico, rodape com numero de pagina e quebra de pagina.
"""

from __future__ import annotations

import datetime as _dt
import re
import zipfile
from typing import Any, Dict, List, Optional, Sequence

_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _escapar(texto: Any) -> str:
    texto = "" if texto is None else str(texto)
    texto = _CONTROLE.sub("", texto)
    return (
        texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class Documento:
    """Monta um documento Word simples, em ordem de escrita."""

    def __init__(self, titulo: str = "Relatorio", autor: str = "Consolidador de Sistemas") -> None:
        self.titulo = titulo
        self.autor = autor
        self._corpo: List[str] = []

    # -- textos ------------------------------------------------------------

    def titulo_principal(self, texto: str, subtitulo: str = "") -> None:
        self._corpo.append(
            f'<w:p><w:pPr><w:pStyle w:val="TituloPrincipal"/></w:pPr>'
            f'<w:r><w:t xml:space="preserve">{_escapar(texto)}</w:t></w:r></w:p>'
        )
        if subtitulo:
            self._corpo.append(
                f'<w:p><w:pPr><w:pStyle w:val="Subtitulo"/></w:pPr>'
                f'<w:r><w:t xml:space="preserve">{_escapar(subtitulo)}</w:t></w:r></w:p>'
            )

    def secao(self, texto: str, nivel: int = 1) -> None:
        nivel = max(1, min(nivel, 3))
        self._corpo.append(
            f'<w:p><w:pPr><w:pStyle w:val="Heading{nivel}"/></w:pPr>'
            f'<w:r><w:t xml:space="preserve">{_escapar(texto)}</w:t></w:r></w:p>'
        )

    def paragrafo(
        self,
        texto: str = "",
        negrito: bool = False,
        italico: bool = False,
        tamanho: Optional[float] = None,
        cor: Optional[str] = None,
        alinhamento: str = "both",
        recuo: int = 0,
        fundo: Optional[str] = None,
    ) -> None:
        propriedades = [f'<w:jc w:val="{alinhamento}"/>']
        if recuo:
            propriedades.append(f'<w:ind w:left="{recuo}"/>')
        if fundo:
            propriedades.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{fundo.lstrip("#")}"/>')
        self._corpo.append(
            f'<w:p><w:pPr>{"".join(propriedades)}</w:pPr>'
            f'{self._trecho(texto, negrito, italico, tamanho, cor)}</w:p>'
        )

    def paragrafo_misto(self, partes: Sequence[Dict[str, Any]], alinhamento: str = "both") -> None:
        """Paragrafo com trechos de formatacao diferente: [{'texto':..,'negrito':True}]."""
        trechos = "".join(
            self._trecho(
                p.get("texto", ""), p.get("negrito", False), p.get("italico", False),
                p.get("tamanho"), p.get("cor"),
            )
            for p in partes
        )
        self._corpo.append(f'<w:p><w:pPr><w:jc w:val="{alinhamento}"/></w:pPr>{trechos}</w:p>')

    def lista(self, itens: Sequence[str], numerada: bool = False) -> None:
        num_id = 2 if numerada else 1
        for item in itens:
            self._corpo.append(
                f'<w:p><w:pPr><w:pStyle w:val="ListaTexto"/>'
                f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num_id}"/></w:numPr></w:pPr>'
                f'{self._trecho(item)}</w:p>'
            )

    def citacao(self, texto: str) -> None:
        self._corpo.append(
            f'<w:p><w:pPr><w:pStyle w:val="Citacao"/></w:pPr>{self._trecho(texto, italico=True)}</w:p>'
        )

    # -- estruturas --------------------------------------------------------

    def tabela(
        self,
        cabecalho: Sequence[str],
        linhas: Sequence[Sequence[Any]],
        larguras: Optional[Sequence[int]] = None,
        cores_linha: Optional[Sequence[Optional[str]]] = None,
        cores_celula: Optional[Dict[int, Dict[int, str]]] = None,
        legenda: str = "",
        alinhamentos: Optional[Sequence[str]] = None,
    ) -> None:
        colunas = len(cabecalho)
        larguras = list(larguras or [round(9000 / max(colunas, 1))] * colunas)
        partes = [
            '<w:tbl><w:tblPr><w:tblStyle w:val="TabelaDados"/>'
            '<w:tblW w:w="5000" w:type="pct"/>'
            '<w:tblBorders>'
            '<w:top w:val="single" w:sz="4" w:color="BFBFBF"/>'
            '<w:left w:val="single" w:sz="4" w:color="BFBFBF"/>'
            '<w:bottom w:val="single" w:sz="4" w:color="BFBFBF"/>'
            '<w:right w:val="single" w:sz="4" w:color="BFBFBF"/>'
            '<w:insideH w:val="single" w:sz="4" w:color="D9D9D9"/>'
            '<w:insideV w:val="single" w:sz="4" w:color="D9D9D9"/>'
            '</w:tblBorders>'
            '<w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
            '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar>'
            '</w:tblPr><w:tblGrid>'
            + "".join(f'<w:gridCol w:w="{largura}"/>' for largura in larguras)
            + "</w:tblGrid>"
        ]
        partes.append('<w:tr><w:trPr><w:tblHeader/></w:trPr>')
        for indice, texto in enumerate(cabecalho):
            partes.append(self._celula(texto, negrito=True, fundo="1F4E79", cor="FFFFFF",
                                       largura=larguras[indice], alinhamento="center"))
        partes.append("</w:tr>")

        for numero, linha in enumerate(linhas):
            fundo_linha = cores_linha[numero] if cores_linha and numero < len(cores_linha) else None
            if fundo_linha is None and numero % 2 == 1:
                fundo_linha = "F4F6F8"
            partes.append("<w:tr>")
            for indice in range(colunas):
                valor = linha[indice] if indice < len(linha) else ""
                fundo = (cores_celula or {}).get(numero, {}).get(indice, fundo_linha)
                alinhamento = alinhamentos[indice] if alinhamentos and indice < len(alinhamentos) else "left"
                partes.append(self._celula(valor, fundo=fundo, largura=larguras[indice],
                                           alinhamento=alinhamento))
            partes.append("</w:tr>")
        partes.append("</w:tbl>")
        self._corpo.append("".join(partes))
        if legenda:
            self._corpo.append(
                f'<w:p><w:pPr><w:pStyle w:val="Legenda"/></w:pPr>{self._trecho(legenda, italico=True)}</w:p>'
            )
        else:
            self._corpo.append('<w:p><w:pPr><w:spacing w:after="0"/></w:pPr></w:p>')

    def sumario(self, titulo: str = "Sumario") -> None:
        self.secao(titulo, 1)
        self._corpo.append(
            '<w:p><w:pPr><w:pStyle w:val="Corpo"/></w:pPr>'
            '<w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>'
            '<w:r><w:instrText xml:space="preserve"> TOC \\o "1-3" \\h \\z \\u </w:instrText></w:r>'
            '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
            '<w:r><w:rPr><w:i/><w:color w:val="7F7F7F"/></w:rPr>'
            '<w:t xml:space="preserve">Clique com o botao direito e escolha '
            '"Atualizar campo" para montar o sumario.</w:t></w:r>'
            '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
        )

    def quebra_pagina(self) -> None:
        self._corpo.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    def linha_horizontal(self) -> None:
        self._corpo.append(
            '<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" '
            'w:color="1F4E79"/></w:pBdr></w:pPr></w:p>'
        )

    # -- gravacao ----------------------------------------------------------

    def salvar(self, caminho: str) -> str:
        with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as pacote:
            pacote.writestr("[Content_Types].xml", _CONTENT_TYPES)
            pacote.writestr("_rels/.rels", _RELS_RAIZ)
            pacote.writestr("docProps/core.xml", self._core())
            pacote.writestr("docProps/app.xml", _APP)
            pacote.writestr("word/document.xml", self._document())
            pacote.writestr("word/_rels/document.xml.rels", _RELS_DOC)
            pacote.writestr("word/styles.xml", _STYLES)
            pacote.writestr("word/numbering.xml", _NUMBERING)
            pacote.writestr("word/footer1.xml", _FOOTER)
        return caminho

    # -- apoio -------------------------------------------------------------

    def _trecho(
        self,
        texto: str,
        negrito: bool = False,
        italico: bool = False,
        tamanho: Optional[float] = None,
        cor: Optional[str] = None,
    ) -> str:
        propriedades = ""
        if negrito:
            propriedades += "<w:b/>"
        if italico:
            propriedades += "<w:i/>"
        if cor:
            propriedades += f'<w:color w:val="{cor.lstrip("#")}"/>'
        if tamanho:
            propriedades += f'<w:sz w:val="{int(tamanho * 2)}"/><w:szCs w:val="{int(tamanho * 2)}"/>'
        propriedades = f"<w:rPr>{propriedades}</w:rPr>" if propriedades else ""
        linhas = str(texto).split("\n")
        conteudo = f'<w:t xml:space="preserve">{_escapar(linhas[0])}</w:t>'
        for extra in linhas[1:]:
            conteudo += f'<w:br/><w:t xml:space="preserve">{_escapar(extra)}</w:t>'
        return f"<w:r>{propriedades}{conteudo}</w:r>"

    def _celula(
        self,
        texto: Any,
        negrito: bool = False,
        fundo: Optional[str] = None,
        cor: Optional[str] = None,
        largura: int = 2000,
        alinhamento: str = "left",
    ) -> str:
        sombreado = (
            f'<w:shd w:val="clear" w:color="auto" w:fill="{fundo.lstrip("#")}"/>' if fundo else ""
        )
        return (
            f'<w:tc><w:tcPr><w:tcW w:w="{largura}" w:type="dxa"/>{sombreado}'
            '<w:vAlign w:val="center"/></w:tcPr>'
            f'<w:p><w:pPr><w:pStyle w:val="TextoTabela"/><w:jc w:val="{alinhamento}"/></w:pPr>'
            f'{self._trecho("" if texto is None else str(texto), negrito=negrito, cor=cor)}</w:p></w:tc>'
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

    def _document(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<w:body>{"".join(self._corpo)}'
            '<w:sectPr><w:footerReference w:type="default" r:id="rIdFooter1"/>'
            '<w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1418" '
            'w:header="709" w:footer="709" w:gutter="0"/>'
            '</w:sectPr></w:body></w:document>'
        )


# --------------------------------------------------------------------------
# Partes fixas do pacote
# --------------------------------------------------------------------------

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '<Override PartName="/word/numbering.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
    '<Override PartName="/word/footer1.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
    '<Override PartName="/docProps/core.xml" '
    'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
    '<Override PartName="/docProps/app.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
    '</Types>'
)

_RELS_RAIZ = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/>'
    '<Relationship Id="rId2" '
    'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
    'Target="docProps/core.xml"/>'
    '<Relationship Id="rId3" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" '
    'Target="docProps/app.xml"/>'
    '</Relationships>'
)

_RELS_DOC = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rIdStyles" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
    'Target="styles.xml"/>'
    '<Relationship Id="rIdNumbering" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" '
    'Target="numbering.xml"/>'
    '<Relationship Id="rIdFooter1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" '
    'Target="footer1.xml"/>'
    '</Relationships>'
)

_APP = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
    'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
    '<Application>Consolidador de Sistemas</Application></Properties>'
)

_FOOTER = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:p><w:pPr><w:jc w:val="center"/><w:rPr><w:sz w:val="16"/><w:color w:val="7F7F7F"/></w:rPr></w:pPr>'
    '<w:r><w:rPr><w:sz w:val="16"/><w:color w:val="7F7F7F"/></w:rPr>'
    '<w:t xml:space="preserve">Pagina </w:t></w:r>'
    '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
    '<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
    '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
    '<w:r><w:rPr><w:sz w:val="16"/></w:rPr><w:t>1</w:t></w:r>'
    '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
    '</w:p></w:ftr>'
)


def _estilo_paragrafo(
    identificador: str,
    nome: str,
    tamanho: int,
    negrito: bool = False,
    cor: str = "1F2937",
    antes: int = 0,
    depois: int = 120,
    nivel: Optional[int] = None,
    italico: bool = False,
    alinhamento: str = "",
    borda_inferior: bool = False,
) -> str:
    propriedades_paragrafo = f'<w:spacing w:before="{antes}" w:after="{depois}" w:line="264" w:lineRule="auto"/>'
    if nivel is not None:
        propriedades_paragrafo += f'<w:outlineLvl w:val="{nivel}"/>'
    if alinhamento:
        propriedades_paragrafo += f'<w:jc w:val="{alinhamento}"/>'
    if borda_inferior:
        propriedades_paragrafo += (
            '<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="2" w:color="1F4E79"/></w:pBdr>'
        )
    corridas = f'<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>'
    if negrito:
        corridas += "<w:b/>"
    if italico:
        corridas += "<w:i/>"
    corridas += f'<w:color w:val="{cor}"/><w:sz w:val="{tamanho * 2}"/><w:szCs w:val="{tamanho * 2}"/>'
    return (
        f'<w:style w:type="paragraph" w:styleId="{identificador}">'
        f'<w:name w:val="{nome}"/><w:basedOn w:val="Normal"/><w:qFormat/>'
        f'<w:pPr>{propriedades_paragrafo}</w:pPr><w:rPr>{corridas}</w:rPr></w:style>'
    )


_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:docDefaults><w:rPrDefault><w:rPr>'
    '<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>'
    '<w:sz w:val="22"/><w:szCs w:val="22"/><w:lang w:val="pt-BR"/>'
    '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>'
    '<w:spacing w:after="120" w:line="264" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
    '<w:name w:val="Normal"/><w:qFormat/></w:style>'
    + _estilo_paragrafo("TituloPrincipal", "Title", 20, negrito=True, cor="1F4E79",
                        antes=0, depois=60, alinhamento="left")
    + _estilo_paragrafo("Subtitulo", "Subtitle", 11, italico=True, cor="5A6B7B",
                        depois=240, borda_inferior=True)
    + _estilo_paragrafo("Heading1", "heading 1", 15, negrito=True, cor="1F4E79",
                        antes=280, depois=120, nivel=0)
    + _estilo_paragrafo("Heading2", "heading 2", 12, negrito=True, cor="2E75B6",
                        antes=220, depois=100, nivel=1)
    + _estilo_paragrafo("Heading3", "heading 3", 11, negrito=True, cor="404040",
                        antes=180, depois=80, nivel=2)
    + _estilo_paragrafo("Corpo", "Corpo", 11)
    + _estilo_paragrafo("ListaTexto", "Lista", 11, depois=60)
    + _estilo_paragrafo("TextoTabela", "Texto de tabela", 9, depois=0, antes=0)
    + _estilo_paragrafo("Legenda", "caption", 8, italico=True, cor="7F7F7F", depois=200)
    + _estilo_paragrafo("Citacao", "Quote", 10, italico=True, cor="404040", depois=160)
    + '<w:style w:type="table" w:styleId="TabelaDados"><w:name w:val="Tabela de dados"/>'
      '<w:tblPr><w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:bottom w:w="40" w:type="dxa"/>'
      '</w:tblCellMar></w:tblPr></w:style>'
    + '</w:styles>'
)

_NUMBERING = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:abstractNum w:abstractNumId="1"><w:multiLevelType w:val="hybridMultilevel"/>'
    '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="&#8226;"/>'
    '<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="454" w:hanging="284"/></w:pPr>'
    '<w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol" w:hint="default"/></w:rPr></w:lvl>'
    '</w:abstractNum>'
    '<w:abstractNum w:abstractNumId="2"><w:multiLevelType w:val="hybridMultilevel"/>'
    '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/>'
    '<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="454" w:hanging="284"/></w:pPr></w:lvl>'
    '</w:abstractNum>'
    '<w:num w:numId="1"><w:abstractNumId w:val="1"/></w:num>'
    '<w:num w:numId="2"><w:abstractNumId w:val="2"/></w:num>'
    '</w:numbering>'
)
