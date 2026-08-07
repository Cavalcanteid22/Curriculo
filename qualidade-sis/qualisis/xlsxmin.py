"""Gravador mínimo de planilhas .xlsx — sem dependências externas.

Escrito para rodar em qualquer máquina com Python instalado, sem precisar de
``pandas``, ``openpyxl`` ou permissão de administrador para instalar pacotes —
condição comum nos computadores da rede da Secretaria.

Grava direto para dentro do arquivo .zip (formato do .xlsx), linha a linha, de
modo que planilhas com centenas de milhares de linhas não consomem memória.

Suporta o necessário para o produto do setor: várias abas, preenchimento
colorido por célula, cabeçalho fixo, filtro automático e largura de colunas.
"""

from __future__ import annotations

import re
import zipfile
from datetime import date, datetime

LIMITE_LINHAS_EXCEL = 1_048_575  # menos a linha de cabeçalho
RE_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

CORES_BASE = {
    "cabecalho": "2F4858",
    "cinza_claro": "F0EFEC",
    "verde_ok": "D8F0D8",
    "borda": "E1E0D9",
}


def escapar(texto):
    txt = RE_CONTROLE.sub("", str(texto))
    return (txt.replace("&", "&amp;").replace("<", "&lt;")
               .replace(">", "&gt;").replace('"', "&quot;"))


class Formula:
    """Fórmula do Excel. Use nomes de função em inglês (SUM, AVERAGE, IF):
    o Excel em português exibe SOMA, MÉDIA, SE automaticamente."""

    __slots__ = ("texto",)

    def __init__(self, texto):
        self.texto = str(texto).lstrip("=")


def letra_coluna(indice):
    """1 -> A, 27 -> AA."""
    letras = ""
    while indice > 0:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def _nome_aba(nome, usados):
    limpo = re.sub(r"[\\/*?:\[\]]", "-", str(nome))[:31] or "Planilha"
    base, n = limpo, 1
    while limpo.lower() in usados:
        n += 1
        sufixo = f"_{n}"
        limpo = base[: 31 - len(sufixo)] + sufixo
    usados.add(limpo.lower())
    return limpo


class Aba:
    def __init__(self, livro, nome, larguras=None, congelar_linhas=1,
                 congelar_colunas=0, autofiltro=True):
        self.livro = livro
        self.nome = nome
        self.larguras = larguras or []
        self.congelar_linhas = congelar_linhas
        self.congelar_colunas = congelar_colunas
        self.autofiltro = autofiltro
        self.n_linhas = 0
        self.n_colunas = 0
        self._fh = None
        self._condicionais = []
        self._validacoes = []

    def formatacao_condicional(self, intervalo, formula, cor, negrito=False):
        """Pinta ``intervalo`` (ex.: 'A2:Z5000') quando ``formula`` for verdadeira.

        A fórmula é relativa à primeira célula do intervalo — use ``$`` para
        travar a coluna, como em ``$C2>0``.
        """
        dxf = self.livro.registrar_dxf(cor, negrito=negrito)
        self._condicionais.append((intervalo, formula.lstrip("="), dxf))

    def lista_suspensa(self, intervalo, valores):
        """Cria validação de dados (lista suspensa) no intervalo indicado."""
        self._validacoes.append((intervalo, ",".join(str(v) for v in valores)))

    # -- ciclo de vida ---------------------------------------------------- #
    def __enter__(self):
        self._abrir()
        return self

    def __exit__(self, *exc):
        self.fechar()
        return False

    def _abrir(self):
        self.livro._contador_abas += 1
        self.indice = self.livro._contador_abas
        self.arquivo = f"xl/worksheets/sheet{self.indice}.xml"
        self._fh = self.livro.zip.open(self.arquivo, "w")
        self._escrever(
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        )
        cong = ""
        if self.congelar_linhas or self.congelar_colunas:
            topo = f"{letra_coluna(self.congelar_colunas + 1)}{self.congelar_linhas + 1}"
            painel = "bottomRight" if self.congelar_colunas else "bottomLeft"
            cong = (f'<pane xSplit="{self.congelar_colunas}" ySplit="{self.congelar_linhas}" '
                    f'topLeftCell="{topo}" activePane="{painel}" state="frozen"/>')
        self._escrever(f'<sheetViews><sheetView workbookViewId="0">{cong}</sheetView></sheetViews>')
        self._escrever('<sheetFormatPr defaultRowHeight="15"/>')
        if self.larguras:
            cols = "".join(
                f'<col min="{i}" max="{i}" width="{max(6, min(int(l), 80))}" customWidth="1"/>'
                for i, l in enumerate(self.larguras, start=1) if l
            )
            self._escrever(f"<cols>{cols}</cols>")
        self._escrever("<sheetData>")

    def _escrever(self, texto):
        self._fh.write(texto.encode("utf-8"))

    # -- escrita ---------------------------------------------------------- #
    def linha(self, valores, estilos=None, estilo_geral=None):
        """Escreve uma linha. ``estilos`` é uma lista paralela a ``valores``."""
        if self.n_linhas >= LIMITE_LINHAS_EXCEL:
            return False
        self.n_linhas += 1
        r = self.n_linhas
        partes = [f'<row r="{r}">']
        for i, valor in enumerate(valores, start=1):
            estilo = None
            if estilos is not None and i - 1 < len(estilos):
                estilo = estilos[i - 1]
            estilo = estilo or estilo_geral
            s = self.livro.id_estilo(estilo) if estilo else 0
            ref = f"{letra_coluna(i)}{r}"
            attr_s = f' s="{s}"' if s else ""
            if valor is None or valor == "":
                if s:
                    partes.append(f'<c r="{ref}"{attr_s}/>')
                continue
            if isinstance(valor, bool):
                valor = "SIM" if valor else "NÃO"
            if isinstance(valor, Formula):
                partes.append(f'<c r="{ref}"{attr_s}><f>{escapar(valor.texto)}</f></c>')
            elif isinstance(valor, (int, float)) and not isinstance(valor, bool):
                partes.append(f'<c r="{ref}"{attr_s}><v>{valor}</v></c>')
            elif isinstance(valor, (date, datetime)):
                partes.append(f'<c r="{ref}"{attr_s} t="inlineStr"><is><t>'
                              f'{valor.strftime("%d/%m/%Y")}</t></is></c>')
            else:
                partes.append(f'<c r="{ref}"{attr_s} t="inlineStr">'
                              f'<is><t xml:space="preserve">{escapar(valor)}</t></is></c>')
        partes.append("</row>")
        self._escrever("".join(partes))
        self.n_colunas = max(self.n_colunas, len(valores))
        return True

    def linha_vazia(self, n=1):
        for _ in range(n):
            self.linha([""])

    def fechar(self):
        if self._fh is None:
            return
        self._escrever("</sheetData>")
        if self.autofiltro and self.n_linhas > 1 and self.n_colunas:
            ref = f"A1:{letra_coluna(self.n_colunas)}{self.n_linhas}"
            self._escrever(f'<autoFilter ref="{ref}"/>')
        for prioridade, (intervalo, formula, dxf) in enumerate(self._condicionais, start=1):
            self._escrever(
                f'<conditionalFormatting sqref="{intervalo}">'
                f'<cfRule type="expression" dxfId="{dxf}" priority="{prioridade}">'
                f'<formula>{escapar(formula)}</formula></cfRule></conditionalFormatting>'
            )
        if self._validacoes:
            regras = "".join(
                f'<dataValidation type="list" allowBlank="1" showInputMessage="1" '
                f'showErrorMessage="1" sqref="{intervalo}">'
                f'<formula1>"{escapar(valores)}"</formula1></dataValidation>'
                for intervalo, valores in self._validacoes
            )
            self._escrever(f'<dataValidations count="{len(self._validacoes)}">{regras}'
                           f'</dataValidations>')
        self._escrever("</worksheet>")
        self._fh.close()
        self._fh = None
        self.livro.abas.append(self)


class LivroExcel:
    """Livro .xlsx gravado em fluxo."""

    def __init__(self, caminho):
        self.caminho = caminho
        self.zip = zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED, allowZip64=True)
        self.abas = []
        self._contador_abas = 0
        self._nomes = set()
        # estilos fixos: 0 padrão | 1 cabeçalho | 2 negrito | 3 título | 4 envolver
        self._estilos = {"padrao": 0, "cabecalho": 1, "negrito": 2, "titulo": 3, "envolver": 4}
        self._fills = ["none", "gray125", CORES_BASE["cabecalho"]]
        self._dxfs = []
        self._dxf_indices = {}
        self._xfs = [
            {"font": 0, "fill": 0},
            {"font": 1, "fill": 2, "wrap": True},
            {"font": 2, "fill": 0},
            {"font": 3, "fill": 0},
            {"font": 0, "fill": 0, "wrap": True},
        ]

    # -- estilos ---------------------------------------------------------- #
    def registrar_dxf(self, hexcor, negrito=False):
        """Registra um formato diferencial (usado pela formatação condicional)."""
        chave = (hexcor.lstrip("#").upper(), bool(negrito))
        if chave in self._dxf_indices:
            return self._dxf_indices[chave]
        self._dxfs.append(chave)
        self._dxf_indices[chave] = len(self._dxfs) - 1
        return self._dxf_indices[chave]

    def registrar_cor(self, hexcor, nome=None, negrito=False):
        """Registra (ou reaproveita) um estilo de preenchimento sólido."""
        chave = nome or f"cor_{hexcor}{'_b' if negrito else ''}"
        if chave in self._estilos:
            return chave
        hexcor = hexcor.lstrip("#").upper()
        if hexcor not in self._fills:
            self._fills.append(hexcor)
        self._xfs.append({"font": 2 if negrito else 0, "fill": self._fills.index(hexcor)})
        self._estilos[chave] = len(self._xfs) - 1
        return chave

    def id_estilo(self, nome):
        if nome is None:
            return 0
        if nome in self._estilos:
            return self._estilos[nome]
        if re.fullmatch(r"#?[0-9A-Fa-f]{6}", str(nome)):  # cor solta
            return self._estilos[self.registrar_cor(nome)]
        return 0

    # -- abas ------------------------------------------------------------- #
    def aba(self, nome, larguras=None, congelar_linhas=1, congelar_colunas=0, autofiltro=True):
        return Aba(self, _nome_aba(nome, self._nomes), larguras=larguras,
                   congelar_linhas=congelar_linhas, congelar_colunas=congelar_colunas,
                   autofiltro=autofiltro)

    # -- fechamento ------------------------------------------------------- #
    def _styles_xml(self):
        fontes = (
            '<font><sz val="10"/><color rgb="FF0B0B0B"/><name val="Calibri"/></font>'
            '<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>'
            '<font><b/><sz val="10"/><color rgb="FF0B0B0B"/><name val="Calibri"/></font>'
            '<font><b/><sz val="14"/><color rgb="FF0B0B0B"/><name val="Calibri"/></font>'
        )
        fills = []
        for f in self._fills:
            if f in ("none", "gray125"):
                fills.append(f'<fill><patternFill patternType="{f}"/></fill>')
            else:
                fills.append(f'<fill><patternFill patternType="solid">'
                             f'<fgColor rgb="FF{f}"/><bgColor indexed="64"/>'
                             f'</patternFill></fill>')
        xfs = []
        for xf in self._xfs:
            alinhamento = ('<alignment vertical="top" wrapText="1"/>' if xf.get("wrap")
                           else '<alignment vertical="top"/>')
            xfs.append(
                f'<xf numFmtId="0" fontId="{xf["font"]}" fillId="{xf["fill"]}" borderId="0" '
                f'xfId="0" applyFont="1" applyFill="1" applyAlignment="1">{alinhamento}</xf>'
            )
        dxfs = ""
        if self._dxfs:
            itens = []
            for cor, negrito in self._dxfs:
                fonte = "<font><b/></font>" if negrito else ""
                itens.append(f'<dxf>{fonte}<fill><patternFill><bgColor rgb="FF{cor}"/>'
                             f'</patternFill></fill></dxf>')
            dxfs = f'<dxfs count="{len(itens)}">{"".join(itens)}</dxfs>'
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<fonts count="4">{fontes}</fonts>'
            f'<fills count="{len(fills)}">{"".join(fills)}</fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            f'<cellXfs count="{len(xfs)}">{"".join(xfs)}</cellXfs>'
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
            f'{dxfs}'
            '</styleSheet>'
        )

    def reordenar(self, nomes):
        """Reordena as abas do livro (as não citadas ficam ao final, na ordem original)."""
        posicao = {n: i for i, n in enumerate(nomes)}
        original = {id(a): i for i, a in enumerate(self.abas)}
        self.abas.sort(key=lambda a: posicao.get(a.nome, len(nomes) + original[id(a)]))

    def fechar(self):
        n = len(self.abas)
        abas_xml = "".join(
            f'<sheet name="{escapar(a.nome)}" sheetId="{i}" r:id="rId{i}"/>'
            for i, a in enumerate(self.abas, start=1)
        )
        self.zip.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets>{abas_xml}</sheets></workbook>'
        )
        rels = "".join(
            f'<Relationship Id="rId{i}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{a.indice}.xml"/>'
            for i, a in enumerate(self.abas, start=1)
        )
        rels += (f'<Relationship Id="rId{n + 1}" '
                 'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
                 'Target="styles.xml"/>')
        self.zip.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{rels}</Relationships>'
        )
        self.zip.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>'
        )
        overrides = "".join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in range(1, n + 1)
        )
        self.zip.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            f'{overrides}'
            '<Override PartName="/xl/styles.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '</Types>'
        )
        self.zip.writestr("xl/styles.xml", self._styles_xml())
        self.zip.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.fechar()
        return False
