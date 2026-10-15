# -*- coding: utf-8 -*-
"""
Relatório analítico-descritivo em formato Word (ELO-SIS).

Produz documento estruturado segundo as normas da ABNT, contendo a
metodologia empregada, a explicação de cada procedimento, as orientações
dirigidas às áreas técnicas, a análise dos resultados com os respectivos
cálculos estatísticos e epidemiológicos, os gráficos de série temporal e de
projeção e as análises comparativas entre as bases.

O documento é redigido para dois públicos simultâneos: a banca examinadora,
que precisa verificar o rigor metodológico, e a equipe da SUIS, que precisa
saber o que fazer na segunda-feira seguinte. Por isso cada seção de resultado
é acompanhada de uma seção de interpretação em linguagem corrente.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from . import graficos as gr
from .pareamento import PAREADO, REVISAO_MANUAL
from .pipeline import ResultadoExecucao
from .qualidade import AMARELO, VERDE, VERMELHO, rotulo_do_tipo

FONTE = "Arial"
COR_TITULO = RGBColor(0x1F, 0x4E, 0x79)
COR_TEXTO = RGBColor(0x00, 0x00, 0x00)
COR_NOTA = RGBColor(0x52, 0x51, 0x4E)


# --------------------------------------------------------------------------- #
# Formatação ABNT
# --------------------------------------------------------------------------- #

def _configurar_documento(documento: Document) -> None:
    """Margens, fonte e espaçamento conforme a ABNT NBR 14724."""
    for secao in documento.sections:
        secao.top_margin = Cm(3)
        secao.left_margin = Cm(3)
        secao.bottom_margin = Cm(2)
        secao.right_margin = Cm(2)

    normal = documento.styles["Normal"]
    normal.font.name = FONTE
    normal.font.size = Pt(12)
    normal.font.color.rgb = COR_TEXTO
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), FONTE)
    paragrafo = normal.paragraph_format
    paragrafo.line_spacing = 1.5
    paragrafo.space_after = Pt(0)
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    paragrafo.first_line_indent = Cm(1.25)


def _titulo(documento: Document, texto: str, nivel: int = 1,
            quebra_antes: bool = False) -> None:
    if quebra_antes:
        documento.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    paragrafo = documento.add_paragraph()
    paragrafo.paragraph_format.first_line_indent = Cm(0)
    paragrafo.paragraph_format.space_before = Pt(18 if nivel == 1 else 12)
    paragrafo.paragraph_format.space_after = Pt(12)
    paragrafo.paragraph_format.line_spacing = 1.5
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.LEFT
    execucao = paragrafo.add_run(texto.upper() if nivel == 1 else texto)
    execucao.bold = True
    execucao.font.size = Pt(12)
    execucao.font.name = FONTE
    execucao.font.color.rgb = COR_TITULO
    paragrafo.style = documento.styles[f"Heading {min(nivel, 4)}"]
    for run in paragrafo.runs:
        run.font.color.rgb = COR_TITULO
        run.font.name = FONTE
        run.font.size = Pt(12)
        run.bold = True


def _paragrafo(documento: Document, texto: str, recuo: bool = True,
               italico: bool = False, tamanho: int = 12) -> None:
    paragrafo = documento.add_paragraph()
    paragrafo.paragraph_format.first_line_indent = Cm(1.25 if recuo else 0)
    paragrafo.paragraph_format.space_after = Pt(6)
    paragrafo.paragraph_format.line_spacing = 1.5
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    execucao = paragrafo.add_run(texto)
    execucao.font.size = Pt(tamanho)
    execucao.font.name = FONTE
    execucao.italic = italico


def _citacao_longa(documento: Document, texto: str, fonte: str = "") -> None:
    """Citação com mais de três linhas: recuo de 4 cm, fonte 10, espaço simples."""
    paragrafo = documento.add_paragraph()
    paragrafo.paragraph_format.left_indent = Cm(4)
    paragrafo.paragraph_format.first_line_indent = Cm(0)
    paragrafo.paragraph_format.line_spacing = 1.0
    paragrafo.paragraph_format.space_before = Pt(6)
    paragrafo.paragraph_format.space_after = Pt(6)
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    execucao = paragrafo.add_run(texto + (f" ({fonte})" if fonte else ""))
    execucao.font.size = Pt(10)
    execucao.font.name = FONTE


def _lista(documento: Document, itens: list[str], numerada: bool = False) -> None:
    for posicao, item in enumerate(itens, start=1):
        paragrafo = documento.add_paragraph()
        paragrafo.paragraph_format.left_indent = Cm(1.25)
        paragrafo.paragraph_format.first_line_indent = Cm(-0.5)
        paragrafo.paragraph_format.space_after = Pt(4)
        paragrafo.paragraph_format.line_spacing = 1.5
        paragrafo.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        marcador = f"{posicao}. " if numerada else "• "
        execucao = paragrafo.add_run(marcador + item)
        execucao.font.size = Pt(12)
        execucao.font.name = FONTE


def _legenda(documento: Document, texto: str, acima: bool = True) -> None:
    """Título de figura/tabela (acima) ou fonte (abaixo), conforme a ABNT."""
    paragrafo = documento.add_paragraph()
    paragrafo.paragraph_format.first_line_indent = Cm(0)
    paragrafo.paragraph_format.space_before = Pt(6 if acima else 2)
    paragrafo.paragraph_format.space_after = Pt(2 if acima else 12)
    paragrafo.paragraph_format.line_spacing = 1.0
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.LEFT if acima else WD_ALIGN_PARAGRAPH.LEFT
    execucao = paragrafo.add_run(texto)
    execucao.font.size = Pt(10)
    execucao.font.name = FONTE
    execucao.bold = acima
    if not acima:
        execucao.font.color.rgb = COR_NOTA


def _figura(documento: Document, caminho: Path, numero: int, titulo: str,
            fonte: str = "Fonte: elaboração própria, gerado pelo ELO-SIS.",
            largura_cm: float = 15.5) -> int:
    if not caminho or not Path(caminho).exists():
        return numero
    _legenda(documento, f"Figura {numero} — {titulo}", acima=True)
    paragrafo = documento.add_paragraph()
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragrafo.paragraph_format.first_line_indent = Cm(0)
    paragrafo.paragraph_format.space_after = Pt(2)
    paragrafo.add_run().add_picture(str(caminho), width=Cm(largura_cm))
    _legenda(documento, fonte, acima=False)
    return numero + 1


def _tabela(documento: Document, numero: int, titulo: str, colunas: list[str],
            linhas: list[list], fonte: str = "Fonte: elaboração própria.",
            tamanho: int = 9, larguras: list[float] | None = None) -> int:
    _legenda(documento, f"Tabela {numero} — {titulo}", acima=True)
    tabela = documento.add_table(rows=1, cols=len(colunas))
    tabela.style = "Table Grid"
    tabela.alignment = WD_TABLE_ALIGNMENT.CENTER

    cabecalho = tabela.rows[0]
    for indice, nome in enumerate(colunas):
        celula = cabecalho.cells[indice]
        celula.text = ""
        paragrafo = celula.paragraphs[0]
        paragrafo.paragraph_format.first_line_indent = Cm(0)
        paragrafo.paragraph_format.space_after = Pt(0)
        paragrafo.paragraph_format.line_spacing = 1.0
        paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        execucao = paragrafo.add_run(str(nome))
        execucao.bold = True
        execucao.font.size = Pt(tamanho)
        execucao.font.name = FONTE
        execucao.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _sombrear(celula, "1F4E79")

    for numero_linha, linha in enumerate(linhas):
        celulas = tabela.add_row().cells
        for indice, valor in enumerate(linha[:len(colunas)]):
            celula = celulas[indice]
            celula.text = ""
            paragrafo = celula.paragraphs[0]
            paragrafo.paragraph_format.first_line_indent = Cm(0)
            paragrafo.paragraph_format.space_after = Pt(0)
            paragrafo.paragraph_format.line_spacing = 1.0
            paragrafo.alignment = (WD_ALIGN_PARAGRAPH.LEFT if indice == 0
                                   else WD_ALIGN_PARAGRAPH.CENTER)
            execucao = paragrafo.add_run("" if valor is None else str(valor))
            execucao.font.size = Pt(tamanho)
            execucao.font.name = FONTE
        if numero_linha % 2 == 1:
            for celula in celulas:
                _sombrear(celula, "F2F2F2")

    if larguras:
        for linha in tabela.rows:
            for indice, largura in enumerate(larguras[:len(colunas)]):
                linha.cells[indice].width = Cm(largura)

    _legenda(documento, fonte, acima=False)
    return numero + 1


def _sombrear(celula, cor_hex: str) -> None:
    elemento = OxmlElement("w:shd")
    elemento.set(qn("w:val"), "clear")
    elemento.set(qn("w:color"), "auto")
    elemento.set(qn("w:fill"), cor_hex)
    celula._tc.get_or_add_tcPr().append(elemento)


def _sumario_automatico(documento: Document) -> None:
    """Insere campo de sumário, atualizável no Word por F9."""
    paragrafo = documento.add_paragraph()
    paragrafo.paragraph_format.first_line_indent = Cm(0)
    execucao = paragrafo.add_run()
    inicio = OxmlElement("w:fldChar")
    inicio.set(qn("w:fldCharType"), "begin")
    instrucao = OxmlElement("w:instrText")
    instrucao.set(qn("xml:space"), "preserve")
    instrucao.text = 'TOC \\o "1-3" \\h \\z \\u'
    separador = OxmlElement("w:fldChar")
    separador.set(qn("w:fldCharType"), "separate")
    texto = OxmlElement("w:t")
    texto.text = ("Sumário: no Word, clique com o botão direito e selecione "
                  "“Atualizar campo” para gerar.")
    fim = OxmlElement("w:fldChar")
    fim.set(qn("w:fldCharType"), "end")
    for elemento in (inicio, instrucao, separador, texto, fim):
        execucao._r.append(elemento)


def _numerar_paginas(documento: Document) -> None:
    rodape = documento.sections[0].footer
    paragrafo = rodape.paragraphs[0]
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    execucao = paragrafo.add_run()
    inicio = OxmlElement("w:fldChar")
    inicio.set(qn("w:fldCharType"), "begin")
    instrucao = OxmlElement("w:instrText")
    instrucao.text = "PAGE"
    fim = OxmlElement("w:fldChar")
    fim.set(qn("w:fldCharType"), "end")
    for elemento in (inicio, instrucao, fim):
        execucao._r.append(elemento)
    execucao.font.size = Pt(10)
    execucao.font.name = FONTE


def _numero(valor, casas: int = 1) -> str:
    """Formata número no padrão brasileiro."""
    if valor is None or valor == "":
        return "—"
    if isinstance(valor, int):
        return f"{valor:,}".replace(",", ".")
    try:
        texto = f"{float(valor):,.{casas}f}"
    except (TypeError, ValueError):
        return str(valor)
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


# --------------------------------------------------------------------------- #
# Seções do relatório
# --------------------------------------------------------------------------- #

def _capa(documento: Document, resultado: ResultadoExecucao) -> None:
    for _ in range(3):
        documento.add_paragraph()

    for texto, tamanho, negrito in (
            ("SECRETARIA MUNICIPAL DA SAÚDE DE SALVADOR", 12, True),
            ("SUBCOORDENADORIA DE INFORMAÇÃO EM SAÚDE — SUIS", 12, True)):
        paragrafo = documento.add_paragraph()
        paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragrafo.paragraph_format.first_line_indent = Cm(0)
        execucao = paragrafo.add_run(texto)
        execucao.bold = negrito
        execucao.font.size = Pt(tamanho)
        execucao.font.name = FONTE

    for _ in range(6):
        documento.add_paragraph()

    paragrafo = documento.add_paragraph()
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragrafo.paragraph_format.first_line_indent = Cm(0)
    execucao = paragrafo.add_run(
        "RELATÓRIO ANALÍTICO-DESCRITIVO DA QUALIFICAÇÃO, HARMONIZAÇÃO E "
        "PAREAMENTO DAS BASES DO SIM, DO SINAN E DO SINASC")
    execucao.bold = True
    execucao.font.size = Pt(14)
    execucao.font.name = FONTE

    documento.add_paragraph()
    paragrafo = documento.add_paragraph()
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragrafo.paragraph_format.first_line_indent = Cm(0)
    execucao = paragrafo.add_run(
        "Produto gerado pela ferramenta ELO-SIS, no âmbito do projeto de "
        "intervenção “O Desafio da Interoperabilidade em Sistemas: proposta "
        "para linkage entre SIM, SINAN e SINASC”")
    execucao.italic = True
    execucao.font.size = Pt(11)
    execucao.font.name = FONTE

    for _ in range(8):
        documento.add_paragraph()

    bases = ", ".join(resultado.bases)
    for texto in (f"Bases analisadas: {bases}",
                  f"Ano de referência: {resultado.configuracao.ano_referencia}",
                  f"Emissão: {resultado.momento.strftime('%d de %B de %Y, às %H:%M')}"):
        paragrafo = documento.add_paragraph()
        paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragrafo.paragraph_format.first_line_indent = Cm(0)
        execucao = paragrafo.add_run(texto)
        execucao.font.size = Pt(11)
        execucao.font.name = FONTE

    for _ in range(5):
        documento.add_paragraph()
    paragrafo = documento.add_paragraph()
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragrafo.paragraph_format.first_line_indent = Cm(0)
    execucao = paragrafo.add_run(f"SALVADOR\n{resultado.momento.year}")
    execucao.bold = True
    execucao.font.size = Pt(12)
    execucao.font.name = FONTE


def _secao_apresentacao(documento: Document, resultado: ResultadoExecucao,
                        contadores: dict) -> None:
    _titulo(documento, "1 Apresentação", 1, quebra_antes=True)

    total_registros = sum(q.total_registros for q in resultado.qualidade.values())
    total_achados = sum(len(q.achados) for q in resultado.qualidade.values())
    total_pares = sum(len([p for p in pa.pares if p.classificacao == PAREADO])
                      for pa in resultado.pareamentos)
    total_revisao = sum(len([p for p in pa.pares if p.classificacao == REVISAO_MANUAL])
                        for pa in resultado.pareamentos)

    _paragrafo(documento,
        "Este relatório apresenta os resultados da qualificação, da "
        "harmonização e do pareamento das bases de dados dos sistemas "
        "nacionais de informação em saúde sob gestão da Subcoordenadoria de "
        "Informação em Saúde (SUIS) da Secretaria Municipal da Saúde de "
        "Salvador. Foi gerado automaticamente pela ferramenta ELO-SIS, "
        "produto técnico do projeto de intervenção que lhe dá origem.")

    _paragrafo(documento,
        f"Foram processadas {len(resultado.bases)} bases, totalizando "
        f"{_numero(total_registros)} registros. A análise identificou "
        f"{_numero(total_achados)} inconsistências, distribuídas nas dimensões "
        f"de completude, acurácia e consistência, e estabeleceu "
        f"{_numero(total_pares)} pares entre registros de bases distintas, "
        f"além de {_numero(total_revisao)} pares encaminhados à verificação "
        f"manual. O tempo total de processamento foi de "
        f"{_numero(resultado.tempo_total, 1)} segundos.")

    _paragrafo(documento,
        "A pertinência do procedimento decorre de uma constatação já "
        "consolidada na literatura. Bogaert et al. (2021), em análise temática "
        "das avaliações dos sistemas de informação em saúde de nove países "
        "europeus, identificam a fragmentação das fontes de dados, com "
        "acessibilidade, uso e reuso limitados, como a primeira e mais "
        "importante das barreiras estruturais recorrentes. Garcia, Miranda e "
        "Sousa (2022) registram que, apesar da disponibilidade e do "
        "aprimoramento de diversos sistemas de informação em saúde nas últimas "
        "décadas, a interoperabilidade entre eles ainda não se realizou nos "
        "setores de vigilância em saúde, e apresentam o relacionamento de "
        "bases como estratégia viável diante da inexistência de identificador "
        "único universal de alta qualidade e de preenchimento obrigatório em "
        "todos os sistemas.")

    _paragrafo(documento,
        "Cabe registrar, desde logo, que o procedimento aqui documentado não "
        "constitui solução de interoperabilidade. Conforme a Organização "
        "Panamericana da Saúde (2016), a interoperabilidade depende do êxito "
        "simultâneo dos níveis técnico, sintático e semântico, envolvendo "
        "decisões de política, padronização e regulação que extrapolam a "
        "competência da gestão setorial municipal. O pareamento opera a "
        "posteriori, sobre dados já produzidos, sem alterar os sistemas nem os "
        "padrões que os regem: daí o seu custo operacional relativamente baixo "
        "e, simultaneamente, o seu caráter de solução parcial, que amplia a "
        "capacidade analítica sem resolver a fragmentação que a torna "
        "necessária.")

    _titulo(documento, "1.1 Como ler este relatório", 2)
    _paragrafo(documento,
        "O documento está organizado de modo que cada seção de resultado seja "
        "seguida de sua interpretação. A seção 2 descreve a metodologia; a "
        "seção 3 apresenta os resultados da qualificação das bases; a seção 4, "
        "os resultados do pareamento; a seção 5, as análises estatísticas e "
        "epidemiológicas, incluindo as projeções; a seção 6 reúne as "
        "orientações dirigidas às áreas técnicas; e a seção 7 explicita as "
        "limitações do procedimento.")
    _paragrafo(documento,
        "Este relatório acompanha a planilha de resultados, que contém o "
        "detalhamento registro a registro. Enquanto o relatório responde ao "
        "que foi encontrado e por quê, a planilha responde a onde está e o que "
        "fazer: nela, cada linha recebe cor — verde para registros sem "
        "inconsistência, amarelo para os que exigem verificação manual e "
        "vermelho para os que apresentam inconsistência real — e colunas com "
        "descrição, justificativa, recomendação de correção e orientação para "
        "a área técnica.")


def _secao_metodologia(documento: Document, resultado: ResultadoExecucao,
                       contadores: dict) -> None:
    configuracao = resultado.configuracao
    _titulo(documento, "2 Metodologia", 1, quebra_antes=True)

    _paragrafo(documento,
        "O procedimento compreende seis etapas encadeadas, executadas "
        "integralmente em ambiente local, sem transmissão de dados para "
        "serviços externos. As etapas são descritas a seguir, com indicação do "
        "referencial que as fundamenta.")

    _titulo(documento, "2.1 Leitura e identificação das bases", 2)
    _paragrafo(documento,
        "As bases são lidas nos formatos DBF, CSV, Excel e PDF. Todos os "
        "campos são carregados como texto, decisão que preserva os zeros à "
        "esquerda de códigos como CEP, CNES e código de município do IBGE — "
        "destruídos pela conversão automática para número — e, sobretudo, "
        "preserva os valores inválidos, cuja detecção é o objeto da etapa "
        "seguinte. A identificação do sistema de origem é feita pela "
        "assinatura de campos, e não pelo nome do arquivo: nomes de arquivo "
        "são atribuídos por pessoas e variam, ao passo que o conjunto de "
        "campos é produzido pelo próprio sistema exportador.")

    _titulo(documento, "2.2 Avaliação da qualidade das bases", 2)
    _paragrafo(documento,
        "A qualificação segue as dimensões identificadas por Ghalavand et al. "
        "(2024) em revisão sistemática que partiu de 760 artigos e submeteu 58 "
        "à apreciação crítica, da qual resultaram catorze dimensões: acurácia, "
        "consistência, segurança, oportunidade, completude, confiabilidade, "
        "acessibilidade, objetividade, relevância, compreensibilidade, "
        "navegabilidade, reputação, eficiência e valor agregado. Conforme "
        "definido no projeto, foram adotadas como prioritárias a acurácia, a "
        "completude e a consistência — rotineiramente avaliadas na SUIS —, "
        "acrescidas da oportunidade, apontada pelos autores entre as três mais "
        "empregadas na literatura.")
    _lista(documento, [
        "Completude — proporção de registros com preenchimento válido, por "
        "variável. A ferramenta distingue três situações habitualmente "
        "confundidas: campo em branco, campo preenchido com código de "
        "ignorado e campo com valor útil. Apenas a terceira constitui "
        "completude efetiva, razão pela qual se reporta a completude útil ao "
        "lado da completude bruta.",
        "Acurácia — proporção de registros com valores compatíveis com o "
        "domínio e com as regras de formação da variável. São verificados os "
        "dígitos verificadores do CPF e do CNS, a estrutura dos códigos da "
        "CID-10, a existência das datas no calendário e a pertinência dos "
        "códigos aos domínios de cada sistema.",
        "Consistência — coerência lógica entre variáveis do mesmo registro: "
        "ordem cronológica dos eventos, plausibilidade biológica dos valores "
        "e compatibilidade entre campos correlatos.",
        "Oportunidade — intervalo, em dias, entre a ocorrência do evento e o "
        "seu registro no sistema, confrontado com o prazo normativo de cada "
        "sistema.",
    ])
    _paragrafo(documento,
        "Cada registro recebe classificação por cor segundo a regra da "
        "gravidade máxima: basta uma inconsistência real para que a linha seja "
        "classificada como vermelha; na ausência destas, uma inconsistência "
        "provável a torna amarela; sem qualquer achado, permanece verde. A "
        "distinção entre o real e o provável não é de grau, mas de natureza: "
        "uma data inexistente no calendário é erro objetivo, ao passo que uma "
        "similaridade elevada entre dois nomes é indício que demanda "
        "confirmação humana.")

    _titulo(documento, "2.3 Detecção de duplicidades", 2)
    _paragrafo(documento,
        "Garcia, Miranda e Sousa (2022) advertem que bases contendo registros "
        "duplicados, ou registros distintos referentes à mesma pessoa, "
        "produzem diferentes possibilidades de análise combinatória nas funções "
        "de junção. A consequência prática é que a duplicidade não tratada "
        "antes do pareamento multiplica pares espúrios. A depuração, por isso, "
        "precede o relacionamento. São distinguidos três fenômenos: a duplicata "
        "técnica, em que o mesmo número de identificação do sistema aparece "
        "mais de uma vez; a duplicata de conteúdo, em que registros de "
        "numeração distinta apresentam identificação nominal idêntica; e a "
        "duplicata provável, em que a similaridade é elevada sem haver "
        "identidade exata — esta última sempre encaminhada à verificação "
        "manual.")

    _titulo(documento, "2.4 Pré-processamento e harmonização", 2)
    _paragrafo(documento,
        "O pré-processamento segue os procedimentos padronizados descritos por "
        "Garcia, Miranda e Sousa (2022): para as variáveis nominais, conversão "
        "de todas as letras para maiúsculas, remoção de acentos, de caracteres "
        "especiais e de espaços duplos e supressão das preposições que ligam "
        "sobrenomes — DA, DE, DO, DAS e DOS; para as variáveis numéricas que "
        "frequentemente apresentam inconsistências de preenchimento, como o "
        "CPF, remoção completa de pontos e traços seguida do preenchimento com "
        "dígitos zero à esquerda até que o campo alcance os onze dígitos "
        "padronizados.")
    _paragrafo(documento,
        "A harmonização, no sentido dado por Schmidt et al. (2020), torna "
        "comparáveis variáveis que os sistemas registram sob nomes e "
        "codificações distintas. O caso mais evidente é o do sexo, codificado "
        "como 1 e 2 no SIM e no SINASC e como M e F no SINAN. Os autores "
        "identificaram seis termos correntes empregados como sinônimos de "
        "harmonização — record linkage, data linkage, data warehousing, data "
        "sharing, data interoperability e health information exchange —, o que "
        "recomenda precisão terminológica: nesta ferramenta, harmonização "
        "designa a etapa que torna as variáveis comparáveis, e pareamento, a "
        "etapa que identifica registros da mesma pessoa.")
    _paragrafo(documento,
        "Todas as variáveis harmonizadas são gravadas em colunas novas, "
        "identificadas pelo prefixo H_, e as colunas nativas permanecem "
        "inalteradas. A preservação é deliberada: a área técnica precisa ver "
        "lado a lado o valor registrado no sistema e o valor tratado, sem o "
        "que a recomendação de correção não é verificável.")

    _titulo(documento, "2.5 Perspectiva de identidade no SINASC", 2)
    _paragrafo(documento,
        "A Declaração de Nascido Vivo registra dois sujeitos no mesmo "
        "documento: o recém-nascido e a mãe. Qual deles constitui a pessoa a "
        "ser pareada depende da pergunta epidemiológica. Na vigilância do "
        "óbito infantil, o sujeito é o recém-nascido, e o relacionamento com o "
        "SIM busca a criança que nasceu e morreu. Na investigação da "
        "transmissão vertical e do óbito materno, o sujeito é a mãe, e o "
        "relacionamento com o SINAN busca a gestante notificada.")
    _paragrafo(documento,
        "A distinção não é formalidade metodológica. Sem ela, o procedimento "
        "compara o nome do recém-nascido com o nome de um adulto e não "
        "encontra par algum — erro que não se manifesta como falha do "
        "programa, mas como resultado vazio, e por isso particularmente "
        "traiçoeiro na rotina. A ferramenta seleciona a perspectiva conforme o "
        "par de bases em relacionamento, admitindo fixação manual pelo usuário.")

    _titulo(documento, "2.6 Pareamento em dois estágios", 2)
    _paragrafo(documento,
        "Adotou-se estratégia sequencial em dois estágios. No primeiro, "
        "aplica-se o pareamento determinístico por chave composta; no segundo, "
        "os registros não pareados são submetidos à abordagem probabilística.")
    _paragrafo(documento,
        "O estágio determinístico aplica cinco conjuntos de chaves em ordem "
        "decrescente de especificidade, iniciando pelos identificadores "
        "unívocos — CPF e CNS — e prosseguindo pelas combinações de nome, nome "
        "da mãe, data de nascimento e sexo. Cada registro é pareado uma única "
        "vez: estabelecido o par por uma regra mais específica, o registro é "
        "retirado das rodadas seguintes, o que evita a explosão combinatória "
        "advertida pelos autores na presença de registros repetidos.")
    _paragrafo(documento,
        f"O estágio probabilístico adota a métrica de similitude "
        f"Jaro-Winkler ponderada por campo. A escolha se justifica por ser "
        f"essa a métrica mais robusta para cadeias nominais com erros de "
        f"digitação comuns em vigilância em saúde (Cohen et al., 2003) e "
        f"superior à distância de Levenshtein para nomes com variação de "
        f"grafia (Garcia; Miranda; Sousa, 2022). A ponderação por campo — "
        f"0,4 para o nome, 0,3 para o nome da mãe e 0,3 para a data de "
        f"nascimento — reflete a confiabilidade esperada de cada variável em "
        f"contexto de vigilância municipal. Um par é considerado pareado "
        f"quando o escore ponderado é igual ou superior a "
        f"{_numero(configuracao.limiar_pareamento, 2)}; pares com escore entre "
        f"{_numero(configuracao.limiar_revisao, 2)} e "
        f"{_numero(configuracao.limiar_pareamento, 2)} — intervalo "
        f"correspondente à análise de sensibilidade de ±0,05 em torno do "
        f"limiar — são encaminhados à verificação manual.")
    _paragrafo(documento,
        "Quando uma variável principal falta em um dos registros, seu peso é "
        "redistribuído entre as presentes, e não simplesmente descontado. "
        "Descontá-lo penalizaria o registro pela incompletude da base, e não "
        "pela ausência de evidência de identidade — distinção que importa "
        "porque a incompletude é justamente um dos problemas que o "
        "relacionamento se propõe a mitigar.")
    _paragrafo(documento,
        "A comparação de todos os registros de uma base com todos os da outra "
        "é computacionalmente inviável em bases municipais: duas bases de cem "
        "mil registros exigiriam dez bilhões de comparações. Adota-se, por "
        "isso, a blocagem, que restringe as comparações a subconjuntos "
        "plausíveis definidos por chaves múltiplas — código fonético do nome "
        "combinado ao ano de nascimento, data de nascimento integral, código "
        "fonético do nome da mãe, entre outras. Basta a coincidência em uma "
        "das chaves para que dois registros sejam comparados. O emprego de "
        "códigos fonéticos combinados a outras variáveis é a via sugerida por "
        "Garcia, Miranda e Sousa (2022) para aumentar a sensibilidade do "
        "método, e responde diretamente à limitação de memória que os autores "
        "registram entre as restrições da técnica.")

    _titulo(documento, "2.7 Proteção dos dados", 2)
    _paragrafo(documento,
        "O tratamento observa a Lei nº 13.709, de 2018. Tratando-se de dados "
        "pessoais sensíveis, fundamenta-se na hipótese legal de execução de "
        "políticas públicas por órgão da administração pública, restringindo-se "
        "à finalidade declarada no projeto. Observam-se, ainda, as Resoluções "
        "nº 466, de 2012, e nº 510, de 2016, do Conselho Nacional de Saúde.")
    _paragrafo(documento,
        "A garantia de que nenhum dado identificável deixa a estação de "
        "trabalho não é declaratória. A ferramenta opera em modo cofre: as "
        "primitivas de conexão do interpretador são substituídas em tempo de "
        "execução, de modo que qualquer tentativa de conexão externa — por "
        "qualquer componente do programa — falhe imediatamente e seja "
        "registrada na trilha de auditoria. O relatório informa, na seção de "
        "auditoria, quantas tentativas foram bloqueadas.")
    _paragrafo(documento,
        "Cada arquivo de entrada é identificado pelo seu resumo criptográfico "
        "SHA-256, registrado na trilha de auditoria. Isso permite demonstrar, "
        "em verificação posterior, exatamente qual versão da base originou "
        "cada produto, sem que seja necessário guardar cópia dos dados — "
        "atendendo simultaneamente à rastreabilidade exigida pela governança "
        "da informação (Ghaffari Heshajin et al., 2024) e ao princípio da "
        "minimização previsto na legislação.")


def _secao_qualidade(documento: Document, resultado: ResultadoExecucao,
                     imagens: dict, contadores: dict) -> None:
    _titulo(documento, "3 Resultados da qualificação das bases", 1,
            quebra_antes=True)

    _titulo(documento, "3.1 Caracterização das bases analisadas", 2)
    linhas = []
    for sigla, qualidade in resultado.qualidade.items():
        contagem = qualidade.contagem_por_classificacao()
        linhas.append([
            sigla, resultado.arquivos_de_origem.get(sigla, ""),
            _numero(qualidade.total_registros),
            _numero(len(qualidade.mapeamento)),
            _numero(qualidade.escore_global, 2),
            _numero(contagem[VERDE]), _numero(contagem[AMARELO]),
            _numero(contagem[VERMELHO]),
        ])
    contadores["tabela"] = _tabela(
        documento, contadores["tabela"],
        "Caracterização e qualidade geral das bases analisadas",
        ["Base", "Arquivo", "Registros", "Variáveis\nmapeadas",
         "Escore de\nqualidade", "Verdes", "Amarelas", "Vermelhas"],
        linhas, larguras=[1.8, 3.6, 1.8, 1.8, 1.8, 1.5, 1.6, 1.7])

    _paragrafo(documento,
        "O escore de qualidade sintetiza, em escala de 0 a 100, as quatro "
        "dimensões avaliadas, ponderadas em 0,35 para completude, 0,35 para "
        "acurácia, 0,20 para consistência e 0,10 para oportunidade. A "
        "ponderação reflete a prioridade declarada no projeto para acurácia, "
        "completude e consistência, mantendo a oportunidade como dimensão "
        "complementar. Trata-se de medida-resumo, útil à comparação entre "
        "bases e ao acompanhamento no tempo, que não substitui a leitura das "
        "dimensões em separado.")

    contadores["figura"] = _figura(
        documento, imagens.get("classificacao"), contadores["figura"],
        "Classificação dos registros por base, segundo a presença de "
        "inconsistências")

    _titulo(documento, "3.2 Completude", 2)
    completude = [l for q in resultado.qualidade.values() for l in q.completude
                  if l["OBRIGATORIO"] == "Sim"]
    criticas = sorted(completude, key=lambda l: l["COMPLETUDE_UTIL_%"])[:12]
    linhas = [[l["ROTULO"], l["BASE"], l["CAMPO_NA_ORIGEM"],
               _numero(l["EM_BRANCO"]), _numero(l["IGNORADOS"]),
               _numero(l["COMPLETUDE_BRUTA_%"], 2),
               _numero(l["COMPLETUDE_UTIL_%"], 2), l["CLASSIFICACAO"]]
              for l in criticas]
    contadores["tabela"] = _tabela(
        documento, contadores["tabela"],
        "Completude das variáveis de preenchimento obrigatório, em ordem "
        "crescente de completude útil",
        ["Variável", "Base", "Campo na\norigem", "Em\nbranco", "Ignorados",
         "Completude\nbruta (%)", "Completude\nútil (%)", "Classificação"],
        linhas, larguras=[3.6, 1.5, 2.2, 1.5, 1.5, 1.8, 1.8, 2.0])

    if criticas:
        pior = criticas[0]
        diferenca = pior["COMPLETUDE_BRUTA_%"] - pior["COMPLETUDE_UTIL_%"]
        _paragrafo(documento,
            f"A variável de menor completude útil é “{pior['ROTULO']}” na base "
            f"{pior['BASE']}, com {_numero(pior['COMPLETUDE_UTIL_%'], 2)}% de "
            f"preenchimento efetivo, classificada como "
            f"{pior['CLASSIFICACAO'].lower()}. A diferença de "
            f"{_numero(diferenca, 2)} pontos percentuais entre a completude "
            f"bruta e a útil corresponde aos registros preenchidos com código "
            f"de ignorado."
            + (" Essa diferença merece atenção específica: do ponto de vista "
               "do sistema, o campo consta preenchido e a base aparenta "
               "completude satisfatória; do ponto de vista analítico, a "
               "informação inexiste. É por essa razão que a ferramenta reporta "
               "as duas medidas em separado."
               if diferenca > 1 else ""))

    _paragrafo(documento,
        "A classificação segue a escala usual de avaliação de bases do SUS: "
        "excelente para completude igual ou superior a 95%, bom a partir de "
        "90%, regular a partir de 70%, ruim a partir de 50% e muito ruim "
        "abaixo desse valor.")

    contadores["figura"] = _figura(
        documento, imagens.get("completude"), contadores["figura"],
        "Completude útil das variáveis de preenchimento obrigatório")

    _titulo(documento, "3.3 Acurácia e consistência", 2)
    achados_por_tipo: dict[str, dict] = {}
    for sigla, qualidade in resultado.qualidade.items():
        for achado in qualidade.achados:
            chave = (sigla, achado.tipo)
            registro = achados_por_tipo.setdefault(chave, {
                "base": sigla, "tipo": achado.tipo,
                "gravidade": achado.gravidade, "dimensao": achado.dimensao,
                "linhas": set(), "descricao": achado.descricao})
            registro["linhas"].add(achado.linha)

    principais = sorted(achados_por_tipo.values(),
                        key=lambda r: -len(r["linhas"]))[:14]
    linhas = []
    for registro in principais:
        total = max(1, resultado.qualidade[registro["base"]].total_registros)
        linhas.append([
            rotulo_do_tipo(registro["tipo"]), registro["base"],
            registro["dimensao"],
            "Real" if registro["gravidade"] == VERMELHO else "Provável",
            _numero(len(registro["linhas"])),
            _numero(100 * len(registro["linhas"]) / total, 2),
        ])
    contadores["tabela"] = _tabela(
        documento, contadores["tabela"],
        "Tipos de inconsistência mais frequentes",
        ["Tipo de inconsistência", "Base", "Dimensão", "Natureza",
         "Registros", "% da base"], linhas,
        larguras=[4.8, 1.5, 2.4, 1.8, 1.7, 1.8])

    contadores["figura"] = _figura(
        documento, imagens.get("inconsistencias"), contadores["figura"],
        "Inconsistências mais frequentes, por base e gravidade")

    _paragrafo(documento,
        "A distinção entre inconsistência real e provável orienta a divisão do "
        "trabalho. As inconsistências reais admitem correção direta na base "
        "nativa, a partir do documento-fonte, e podem ser distribuídas como "
        "tarefa de rotina. As prováveis exigem juízo técnico e, por isso, "
        "devem ser alocadas a quem conheça o agravo e o fluxo de notificação.")

    _titulo(documento, "3.4 Oportunidade", 2)
    oportunidade = [l for q in resultado.qualidade.values() for l in q.oportunidade]
    if oportunidade:
        linhas = [[l["BASE"], _numero(l["PRAZO_NORMATIVO_DIAS"]),
                   _numero(l["REGISTROS_AVALIADOS"]),
                   _numero(l["MEDIANA_DIAS"], 1), _numero(l["MEDIA_DIAS"], 1),
                   f"{_numero(l['PERCENTIL_25'], 0)}–{_numero(l['PERCENTIL_75'], 0)}",
                   _numero(l["MAXIMO_DIAS"]), _numero(l["OPORTUNIDADE_%"], 2)]
                  for l in oportunidade]
        contadores["tabela"] = _tabela(
            documento, contadores["tabela"],
            "Oportunidade do registro, em dias entre o evento e a digitação",
            ["Base", "Prazo\nnormativo", "Registros\navaliados", "Mediana",
             "Média", "Intervalo\ninterquartil", "Máximo",
             "No prazo (%)"], linhas,
            larguras=[1.7, 1.9, 1.9, 1.5, 1.5, 2.2, 1.5, 1.9])
        _paragrafo(documento,
            "A oportunidade é calculada apenas sobre intervalos não negativos. "
            "Registros cuja data de digitação antecede a data do evento não "
            "medem atraso, mas erro: são tratados como inconsistência de "
            "consistência e reportados como tal, não compondo esta estatística.")
    else:
        _paragrafo(documento,
            "Não foi possível calcular a oportunidade: as bases analisadas não "
            "dispõem simultaneamente do campo de data do evento e do campo de "
            "data de digitação ou cadastro. Recomenda-se incluir o campo de "
            "data de digitação nas exportações futuras, uma vez que a "
            "oportunidade é uma das três dimensões de qualidade mais "
            "empregadas na literatura (Ghalavand et al., 2024).")

    _titulo(documento, "3.5 Duplicidades", 2)
    total_grupos = sum(len(g) for g in resultado.duplicidades.values())
    if total_grupos:
        from .duplicidades import resumir_duplicidades
        linhas = []
        for sigla, grupos in resultado.duplicidades.items():
            total = resultado.qualidade[sigla].total_registros
            for resumo in resumir_duplicidades(grupos, total, sigla):
                linhas.append([
                    resumo["BASE"],
                    rotulo_do_tipo(resumo["TIPO_DUPLICIDADE"]),
                    _numero(resumo["GRUPOS"]),
                    _numero(resumo["REGISTROS_ENVOLVIDOS"]),
                    _numero(resumo["REGISTROS_EXCEDENTES"]),
                    _numero(resumo["PROPORCAO_DA_BASE_%"], 3)])
        contadores["tabela"] = _tabela(
            documento, contadores["tabela"],
            "Duplicidades identificadas, por base e tipo",
            ["Base", "Tipo de duplicidade", "Grupos", "Registros\nenvolvidos",
             "Registros\nexcedentes", "% da base"], linhas,
            larguras=[1.8, 4.4, 1.7, 2.1, 2.1, 1.9])
        _paragrafo(documento,
            "A coluna de registros excedentes indica quantos registros seriam "
            "eliminados caso se mantivesse apenas um por grupo. É essa a medida "
            "do impacto da duplicidade sobre as contagens: o excedente "
            "corresponde à inflação artificial do número de eventos.")
        _paragrafo(documento,
            "Recomenda-se que a exclusão de duplicatas seja precedida da "
            "consolidação dos campos: registros duplicados frequentemente "
            "diferem entre si quanto ao preenchimento, e a eliminação sem "
            "conferência descarta informação existente. O procedimento "
            "indicado é reter o registro mais completo e transferir para ele "
            "os campos preenchidos apenas nos demais.")
    else:
        _paragrafo(documento,
            "Não foram identificados grupos de duplicidade nas bases "
            "analisadas.")


def _secao_pareamento(documento: Document, resultado: ResultadoExecucao,
                      imagens: dict, contadores: dict) -> None:
    configuracao = resultado.configuracao
    _titulo(documento, "4 Resultados do pareamento", 1, quebra_antes=True)

    _titulo(documento, "4.1 Variáveis disponíveis como chave", 2)
    chaves = [l for l in resultado.variaveis_comuns
              if l["E_CHAVE_DE_PAREAMENTO"] == "Sim"]
    if chaves:
        colunas = ["Variável", "Bases em que\nexiste", "Completude\nmínima (%)",
                   "Aptidão como chave"]
        linhas = [[l["ROTULO"], _numero(l["BASES_EM_QUE_EXISTE"]),
                   _numero(l["COMPLETUDE_MINIMA_%"], 2), l["APTIDAO_COMO_CHAVE"]]
                  for l in chaves]
        contadores["tabela"] = _tabela(
            documento, contadores["tabela"],
            "Variáveis candidatas a chave de pareamento e respectiva aptidão",
            colunas, linhas, larguras=[4.4, 2.3, 2.3, 6.5])

        cpf = next((l for l in chaves if l["VARIAVEL"] == "CPF"), None)
        if cpf and cpf["COMPLETUDE_MINIMA_%"] < 60:
            _paragrafo(documento,
                f"O CPF, identificador de maior poder discriminante entre os "
                f"disponíveis, apresenta completude mínima de "
                f"{_numero(cpf['COMPLETUDE_MINIMA_%'], 2)}% entre as bases. "
                f"Esse achado é a confirmação empírica, para o caso de "
                f"Salvador, do cenário descrito por Garcia, Miranda e Sousa "
                f"(2022): a inexistência de identificador único universal de "
                f"alta qualidade e preenchimento obrigatório em todos os "
                f"sistemas é precisamente o que torna necessário o record "
                f"linkage. Houvesse identificador de completude elevada, o "
                f"pareamento probabilístico seria dispensável.")

    _titulo(documento, "4.2 Efeito da adição sequencial de chaves", 2)
    _paragrafo(documento,
        "Garcia, Miranda e Sousa (2022) demonstram, em bases simuladas, que o "
        "uso isolado da variável nome resultou em 40.108 pares; o acréscimo da "
        "chave nome da mãe reduziu o resultado a 112 pares; e a inclusão da "
        "data de nascimento isolou apenas dois pares. A ferramenta reproduz o "
        "experimento sobre as bases em uso, o que documenta empiricamente, "
        "para a SUIS, o ganho de especificidade obtido a cada chave "
        "acrescentada.")
    if resultado.efeito_das_chaves:
        linhas = [[l["RELACIONAMENTO"], l["CONJUNTO_DE_CHAVES"],
                   _numero(l["PARES_CANDIDATOS"]),
                   (_numero(l["REDUCAO_EM_RELACAO_AO_ANTERIOR_%"], 2) + "%")
                   if l["REDUCAO_EM_RELACAO_AO_ANTERIOR_%"] != "" else "—"]
                  for l in resultado.efeito_das_chaves]
        contadores["tabela"] = _tabela(
            documento, contadores["tabela"],
            "Pares candidatos segundo o conjunto de chaves empregado",
            ["Relacionamento", "Conjunto de chaves", "Pares candidatos",
             "Redução"], linhas, larguras=[3.0, 6.6, 2.6, 2.3])
        contadores["figura"] = _figura(
            documento, imagens.get("efeito_chaves"), contadores["figura"],
            "Redução do número de pares candidatos a cada chave acrescentada")

    _titulo(documento, "4.3 Pares identificados", 2)
    linhas = []
    for pareamento in resultado.pareamentos:
        resumo = pareamento.resumo()
        linhas.append([
            resumo["RELACIONAMENTO"], _numero(resumo["REGISTROS_BASE_A"]),
            _numero(resumo["REGISTROS_BASE_B"]),
            _numero(resumo["PARES_DETERMINISTICOS"]),
            _numero(resumo["PARES_PROBABILISTICOS"]),
            _numero(resumo["PARES_TOTAIS"]),
            _numero(resumo["PARES_PARA_REVISAO_MANUAL"]),
            _numero(resumo["TAXA_DE_PAREAMENTO_%"], 2)])
    contadores["tabela"] = _tabela(
        documento, contadores["tabela"],
        "Resultado do pareamento, por relacionamento e estágio",
        ["Relacionamento", "Registros\nbase A", "Registros\nbase B",
         "Pares\ndeterminísticos", "Pares\nprobabilísticos", "Total de\npares",
         "Revisão\nmanual", "Taxa de\npareamento (%)"], linhas,
        larguras=[2.8, 1.8, 1.8, 2.1, 2.1, 1.6, 1.6, 2.0])

    contadores["figura"] = _figura(
        documento, imagens.get("pareamentos"), contadores["figura"],
        "Composição dos pares por estágio e situação")

    total_det = sum(l for pareamento in resultado.pareamentos
                    for l in [pareamento.resumo()["PARES_DETERMINISTICOS"]])
    total_prob = sum(pareamento.resumo()["PARES_PROBABILISTICOS"]
                     for pareamento in resultado.pareamentos)
    total_rev = sum(pareamento.resumo()["PARES_PARA_REVISAO_MANUAL"]
                    for pareamento in resultado.pareamentos)
    if total_det + total_prob:
        proporcao = 100 * total_prob / (total_det + total_prob)
        _paragrafo(documento,
            f"Do total de pares aceitos, {_numero(proporcao, 1)}% foram "
            f"estabelecidos no estágio probabilístico — isto é, não teriam "
            f"sido recuperados por procedimento determinístico. "
            + ("Esse é o ganho direto atribuível ao segundo estágio, e "
               "corresponde a registros que a rotina manual baseada em junção "
               "exata deixaria escapar."
               if proporcao > 5 else
               "A baixa proporção indica bases com chaves de boa qualidade, "
               "em que o estágio determinístico já recupera a maior parte dos "
               "pares verdadeiros."))

    _paragrafo(documento,
        f"Foram encaminhados {_numero(total_rev)} pares à verificação manual. "
        f"Esse conjunto não representa falha do procedimento, mas a sua "
        f"parte deliberadamente reservada ao juízo humano: são os pares cujo "
        f"escore se situa na faixa de incerteza, ou que apresentam chave "
        f"ambígua ou divergência em variável auxiliar. Adotar limiar mais "
        f"permissivo reduziria esse conjunto ao custo de incorporar "
        f"falsos-positivos ao resultado automático — troca que, em vigilância "
        f"em saúde, raramente compensa, porque o falso-positivo se propaga "
        f"silenciosamente aos indicadores, ao passo que o par em revisão "
        f"permanece visível.")


def _secao_desempenho(documento: Document, resultado: ResultadoExecucao,
                      imagens: dict, contadores: dict) -> None:
    _titulo(documento, "4.4 Desempenho do pareamento", 2)

    if not resultado.validacoes:
        _paragrafo(documento,
            "Não foi fornecida amostra de referência, razão pela qual não se "
            "calcularam a sensibilidade, o valor preditivo positivo e a "
            "proporção de falsos-positivos. Para obtê-los, conforme previsto "
            "no Quadro 4 do projeto, é necessário submeter à ferramenta um "
            "arquivo de referência com as colunas SISTEMA, ID_PESSOA e "
            "REGISTRO, produzido a partir de amostra aleatória de pares "
            "candidatos revisada por dois avaliadores independentes.")
        return

    linhas = []
    for validacao in resultado.validacoes:
        linhas.append([
            validacao.relacionamento, _numero(validacao.pares_de_referencia),
            _numero(validacao.pares_indicados),
            _numero(validacao.verdadeiros_positivos),
            _numero(validacao.falsos_positivos),
            _numero(validacao.falsos_negativos),
            _numero(100 * validacao.sensibilidade, 2),
            _numero(100 * validacao.valor_preditivo_positivo, 2),
            _numero(100 * validacao.medida_f, 2)])
    contadores["tabela"] = _tabela(
        documento, contadores["tabela"],
        "Desempenho do pareamento contra a amostra de referência",
        ["Relacionamento", "Pares de\nreferência", "Pares\nindicados",
         "VP", "FP", "FN", "Sensibi-\nlidade (%)",
         "VPP (%)", "Medida\nF (%)"], linhas,
        larguras=[2.6, 1.8, 1.7, 1.2, 1.2, 1.2, 1.8, 1.5, 1.6])

    contadores["figura"] = _figura(
        documento, imagens.get("desempenho"), contadores["figura"],
        "Sensibilidade e valor preditivo positivo, por relacionamento")

    melhor = max(resultado.validacoes, key=lambda v: v.valor_preditivo_positivo)
    media_sensibilidade = (sum(v.sensibilidade for v in resultado.validacoes)
                           / len(resultado.validacoes))
    media_preditivo = (sum(v.valor_preditivo_positivo for v in resultado.validacoes)
                       / len(resultado.validacoes))
    recuperaveis = sum(v.recuperaveis_na_revisao for v in resultado.validacoes)

    _paragrafo(documento,
        f"A sensibilidade média observada foi de "
        f"{_numero(100 * media_sensibilidade, 1)}% e o valor preditivo "
        f"positivo médio, de {_numero(100 * media_preditivo, 1)}%. A leitura "
        f"conjunta dos dois indicadores é o que permite julgar o "
        f"procedimento: o valor preditivo positivo mede a confiabilidade do "
        f"que a rotina afirma; a sensibilidade mede o quanto ela deixa de "
        f"encontrar.")

    if media_preditivo >= 0.95:
        _paragrafo(documento,
            "O valor preditivo positivo elevado indica que os pares aceitos "
            "automaticamente podem ser incorporados à análise sem conferência "
            "individual prévia, reservando-se o esforço de verificação aos "
            "pares da faixa de revisão manual. Esse é o comportamento "
            "desejável em vigilância: um procedimento conservador, que erra "
            "por omissão e não por afirmação.")
    else:
        _paragrafo(documento,
            "O valor preditivo positivo observado recomenda conferência por "
            "amostragem dos pares aceitos automaticamente antes da "
            "incorporação à análise, bem como a revisão do limiar adotado "
            "mediante nova análise de sensibilidade.")

    if recuperaveis:
        _paragrafo(documento,
            f"Encontram-se na faixa de revisão manual {_numero(recuperaveis)} "
            f"pares verdadeiros ainda não recuperados pelo procedimento "
            f"automático. Trata-se de informação operacionalmente relevante: "
            f"indica que o trabalho de conferência manual dessa faixa tem "
            f"rendimento alto e, portanto, justifica a alocação de equipe. A "
            f"sensibilidade potencial — somando os pares automáticos aos "
            f"recuperáveis por conferência — alcançaria "
            f"{_numero(100 * sum(v.verdadeiros_positivos + v.recuperaveis_na_revisao for v in resultado.validacoes) / max(1, sum(v.pares_de_referencia for v in resultado.validacoes)), 1)}%.")

    _paragrafo(documento,
        "Os falsos-negativos concentram-se, como esperado, nos registros com "
        "chaves incompletas ou com múltiplos erros simultâneos de digitação. "
        "Esse achado reforça a relação de dependência entre as duas etapas do "
        "procedimento: a eficácia e a precisão do linkage dependem da "
        "qualidade das bases originais, sendo a etapa de pré-processamento e "
        "limpeza um pré-requisito indispensável (Garcia; Miranda; Sousa, "
        "2022). Melhorar a completude do nome da mãe e da data de nascimento "
        "nas bases nativas é, portanto, a via mais direta para elevar a "
        "sensibilidade do pareamento em execuções futuras.")

    _titulo(documento, "4.5 Ganho de completude com o relacionamento", 2)
    if resultado.ganhos_completude:
        maiores = sorted(resultado.ganhos_completude,
                         key=lambda l: -l["GANHO_ABSOLUTO_PP"])[:10]
        linhas = [[l["ROTULO"], l["RELACIONAMENTO"],
                   _numero(l["COMPLETUDE_ANTES_%"], 2),
                   _numero(l["COMPLETUDE_DEPOIS_%"], 2),
                   _numero(l["GANHO_ABSOLUTO_PP"], 2),
                   _numero(l["REGISTROS_RECUPERADOS"]),
                   _numero(l["PROPORCAO_DIVERGENTE_%"], 2)] for l in maiores]
        contadores["tabela"] = _tabela(
            documento, contadores["tabela"],
            "Ganho de completude após o relacionamento, por variável",
            ["Variável", "Relacionamento", "Antes (%)", "Depois (%)",
             "Ganho (p.p.)", "Registros\nrecuperados",
             "Divergência\nentre bases (%)"], linhas,
            larguras=[3.4, 2.6, 1.7, 1.7, 1.8, 2.0, 2.2])

        maior = maiores[0]
        if maior["GANHO_ABSOLUTO_PP"] > 0:
            _paragrafo(documento,
                f"O maior ganho observado recaiu sobre a variável "
                f"“{maior['ROTULO']}” no relacionamento "
                f"{maior['RELACIONAMENTO']}, cuja completude passou de "
                f"{_numero(maior['COMPLETUDE_ANTES_%'], 2)}% para "
                f"{_numero(maior['COMPLETUDE_DEPOIS_%'], 2)}%, com "
                f"{_numero(maior['REGISTROS_RECUPERADOS'])} registros "
                f"recuperados. É esta a tradução numérica do benefício "
                f"operacional do relacionamento: informação que já existia no "
                f"conjunto dos sistemas, mas não estava disponível em nenhum "
                f"deles isoladamente.")
        contadores["figura"] = _figura(
            documento, imagens.get("ganho_completude"), contadores["figura"],
            "Completude antes e depois do relacionamento de bases")

    if resultado.consistencia_entre_bases:
        _titulo(documento, "4.6 Consistência entre bases", 2)
        piores = sorted(resultado.consistencia_entre_bases,
                        key=lambda l: l["CONCORDANCIA_%"])[:10]
        linhas = [[l["ROTULO"], l["RELACIONAMENTO"],
                   _numero(l["PARES_COMPARAVEIS"]), _numero(l["DIVERGENTES"]),
                   _numero(l["CONCORDANCIA_%"], 2)] for l in piores]
        contadores["tabela"] = _tabela(
            documento, contadores["tabela"],
            "Concordância de variáveis homônimas entre bases relacionadas",
            ["Variável", "Relacionamento", "Pares\ncomparáveis", "Divergentes",
             "Concordância (%)"], linhas, larguras=[3.8, 2.8, 2.2, 2.0, 2.6])
        _paragrafo(documento,
            "Este indicador, previsto no Quadro 4 do projeto e referenciado a "
            "Schmidt et al. (2020), mede a coerência semântica efetiva entre "
            "sistemas que, em tese, registram o mesmo atributo. Concordância "
            "baixa em uma variável não indica necessariamente erro de "
            "digitação: pode revelar que os instrumentos de coleta definem a "
            "variável de maneira distinta, hipótese que remete a problema de "
            "harmonização, e não de preenchimento.")


def _secao_epidemiologia(documento: Document, resultado: ResultadoExecucao,
                         imagens: dict, contadores: dict) -> None:
    configuracao = resultado.configuracao
    _titulo(documento, "5 Análise estatística e epidemiológica", 1,
            quebra_antes=True)

    _titulo(documento, "5.1 Distribuição temporal dos eventos", 2)
    if resultado.series_mensais:
        colunas = ["Mês"] + list(resultado.series_mensais)
        linhas = []
        for mes in range(1, 13):
            linha = [gr.MESES[mes - 1]]
            for serie in resultado.series_mensais.values():
                linha.append(_numero(int(serie.get(mes, 0))))
            linhas.append(linha)
        totais = ["Total"] + [_numero(int(s.sum()))
                              for s in resultado.series_mensais.values()]
        linhas.append(totais)
        contadores["tabela"] = _tabela(
            documento, contadores["tabela"],
            f"Distribuição mensal dos eventos registrados, "
            f"{configuracao.ano_referencia}",
            colunas, linhas,
            larguras=[3.0] + [2.4] * len(resultado.series_mensais))

        contadores["figura"] = _figura(
            documento, imagens.get("series"), contadores["figura"],
            f"Eventos registrados por mês, por base, "
            f"{configuracao.ano_referencia}")

    _titulo(documento, "5.2 Estatística descritiva das séries", 2)
    if resultado.estatisticas:
        linhas = []
        for sigla, medidas in resultado.estatisticas.items():
            if not medidas:
                continue
            linhas.append([
                sigla, _numero(medidas["MEDIA"], 2),
                _numero(medidas["DESVIO_PADRAO"], 2),
                f"{_numero(medidas['IC95_INFERIOR'], 1)} – "
                f"{_numero(medidas['IC95_SUPERIOR'], 1)}",
                _numero(medidas["MEDIANA"], 1),
                f"{_numero(medidas['MINIMO'], 0)} – {_numero(medidas['MAXIMO'], 0)}",
                _numero(medidas["COEFICIENTE_VARIACAO_%"], 2),
                _numero(medidas["ASSIMETRIA"], 3)])
        contadores["tabela"] = _tabela(
            documento, contadores["tabela"],
            "Estatística descritiva da distribuição mensal de eventos",
            ["Base", "Média", "Desvio\npadrão", "IC 95% da média", "Mediana",
             "Mínimo –\nmáximo", "Coeficiente de\nvariação (%)", "Assimetria"],
            linhas, larguras=[1.6, 1.5, 1.6, 2.8, 1.5, 2.0, 2.4, 1.8])

        _paragrafo(documento,
            "O coeficiente de variação expressa a dispersão relativa da série: "
            "valores acima de 30% indicam distribuição mensal heterogênea, "
            "compatível com sazonalidade ou com irregularidade do fluxo de "
            "alimentação do sistema — hipóteses que o dado isolado não "
            "distingue e que demandam confronto com a série histórica de anos "
            "anteriores. A assimetria positiva indica concentração de meses "
            "com poucos registros e alguns meses de pico; a negativa, o "
            "inverso.")

        maior_variacao = max(
            ((s, m) for s, m in resultado.estatisticas.items() if m),
            key=lambda item: item[1]["COEFICIENTE_VARIACAO_%"], default=None)
        if maior_variacao and maior_variacao[1]["COEFICIENTE_VARIACAO_%"] > 30:
            _paragrafo(documento,
                f"A base {maior_variacao[0]} apresenta o maior coeficiente de "
                f"variação "
                f"({_numero(maior_variacao[1]['COEFICIENTE_VARIACAO_%'], 1)}%), "
                f"o que recomenda investigar se a oscilação decorre do "
                f"comportamento do evento ou do processo de digitação. A "
                f"distinção é verificável: oscilação do evento tende a "
                f"reproduzir-se em anos anteriores; oscilação do processo "
                f"correlaciona-se com períodos de férias, mudanças de equipe "
                f"ou interrupções do sistema.")

    _titulo(documento, "5.3 Indicadores epidemiológicos", 2)
    if resultado.indicadores_epidemiologicos:
        linhas = [[l["INDICADOR"], _numero(l["NUMERADOR"]),
                   _numero(l["DENOMINADOR"]), _numero(l["VALOR"], 2),
                   f"{_numero(l['IC95_INFERIOR'], 2)} – "
                   f"{_numero(l['IC95_SUPERIOR'], 2)}", l["UNIDADE"]]
                  for l in resultado.indicadores_epidemiologicos]
        contadores["tabela"] = _tabela(
            documento, contadores["tabela"],
            f"Indicadores epidemiológicos calculados sobre as bases "
            f"analisadas, {configuracao.ano_referencia}",
            ["Indicador", "Numerador", "Denominador", "Valor", "IC 95%",
             "Unidade"], linhas, larguras=[4.6, 1.9, 2.1, 1.6, 2.4, 2.6])

        _paragrafo(documento,
            f"Os coeficientes foram calculados segundo as fórmulas da Rede "
            f"Interagencial de Informações para a Saúde, adotando-se como "
            f"denominador populacional {_numero(configuracao.populacao_referencia)} "
            f"habitantes. Os intervalos de confiança de 95% foram estimados "
            f"pelo método de Wilson, preferido ao intervalo de Wald por "
            f"manter cobertura adequada quando a proporção se aproxima dos "
            f"extremos e quando o denominador é pequeno — situação frequente "
            f"em recortes por bairro ou por faixa etária.")

        letalidade = next((l for l in resultado.indicadores_epidemiologicos
                           if "letalidade" in l["INDICADOR"].lower()), None)
        if letalidade:
            _paragrafo(documento,
                f"Merece destaque a taxa de letalidade, estimada em "
                f"{_numero(letalidade['VALOR'], 2)}% "
                f"(IC 95%: {_numero(letalidade['IC95_INFERIOR'], 2)}% – "
                f"{_numero(letalidade['IC95_SUPERIOR'], 2)}%). Esse indicador "
                f"só pode ser calculado mediante o relacionamento entre o "
                f"SINAN e o SIM: nenhum dos dois sistemas, isoladamente, "
                f"permite identificar quais casos notificados evoluíram para "
                f"óbito. É, portanto, o exemplo mais direto do tipo de "
                f"pergunta epidemiológica que o produto torna respondível — "
                f"pergunta que, como observado na introdução do projeto, "
                f"pressupõe que representações distintas da mesma pessoa, "
                f"produzidas em sistemas diferentes, sejam reconhecidas como "
                f"referentes ao mesmo sujeito.")
            _paragrafo(documento,
                "Cabe advertir que a estimativa é conservadora, porque "
                "depende da sensibilidade do pareamento: óbitos de casos "
                "notificados que não foram pareados não entram no numerador. "
                "A letalidade real é, portanto, igual ou superior à estimada, "
                "e a diferença entre ambas diminui à medida que a qualidade "
                "das bases nativas melhora.")

    _titulo(documento, "5.4 Projeções", 2)
    _paragrafo(documento,
        "As projeções foram obtidas por regressão linear pelo método dos "
        "mínimos quadrados, acompanhadas do intervalo de predição de 95%, que "
        "incorpora tanto a incerteza da estimativa dos parâmetros quanto a "
        "dispersão residual observada. O método é deliberadamente simples e "
        "auditável: modelos mais elaborados exigiriam séries históricas mais "
        "longas do que as disponíveis no recorte anual, e sua complexidade "
        "dificultaria a leitura por equipes que não são especialistas em "
        "estatística — público a que o produto se destina.")

    if resultado.projecoes:
        linhas = []
        for projecao in resultado.projecoes:
            linhas.append([
                projecao.rotulo.replace(" — eventos por mês", ""),
                _numero(projecao.inclinacao, 3),
                _numero(projecao.r_quadrado, 3),
                _numero(projecao.erro_padrao_estimativa, 2),
                _numero(sum(projecao.valores_projetados), 0),
                f"{_numero(sum(projecao.limite_inferior), 0)} – "
                f"{_numero(sum(projecao.limite_superior), 0)}"])
        contadores["tabela"] = _tabela(
            documento, contadores["tabela"],
            f"Parâmetros das projeções e total projetado para os "
            f"{configuracao.horizonte_projecao} meses subsequentes",
            ["Série", "Variação mensal\n(eventos/mês)", "R²",
             "Erro padrão da\nestimativa", "Total projetado",
             "IC 95% do total"], linhas,
            larguras=[2.6, 2.6, 1.4, 2.4, 2.2, 3.0])

        for projecao in resultado.projecoes:
            indice = resultado.projecoes.index(projecao) + 1
            contadores["figura"] = _figura(
                documento, imagens.get(f"projecao_{indice}"),
                contadores["figura"],
                f"Série observada e projeção — {projecao.rotulo}")
            _paragrafo(documento, projecao.interpretacao())

        fracos = [p for p in resultado.projecoes if p.r_quadrado < 0.4]
        if fracos:
            _paragrafo(documento,
                f"Registre-se que {len(fracos)} das "
                f"{len(resultado.projecoes)} séries apresentaram coeficiente "
                f"de determinação inferior a 0,4. Nesses casos, a projeção "
                f"deve ser lida como cenário de referência, e não como "
                f"previsão: a variação observada não é explicada pela "
                f"tendência linear, o que é compatível com sazonalidade, com "
                f"eventos epidêmicos pontuais ou com irregularidade do fluxo "
                f"de alimentação dos sistemas. A leitura honesta desse "
                f"resultado é que a série, no recorte disponível, não autoriza "
                f"previsão — e não que a projeção esteja errada.")

    _titulo(documento, "5.5 Análise comparativa entre as bases", 2)
    _paragrafo(documento,
        "A comparação entre as bases é o que distingue este relatório de três "
        "relatórios isolados. Três aspectos merecem leitura conjunta.")

    escores = {s: q.escore_global for s, q in resultado.qualidade.items()}
    if escores:
        melhor = max(escores, key=escores.get)
        pior = min(escores, key=escores.get)
        _paragrafo(documento,
            f"Quanto à qualidade, a base {melhor} apresentou o maior escore "
            f"({_numero(escores[melhor], 2)}) e a base {pior}, o menor "
            f"({_numero(escores[pior], 2)}). "
            + (f"A diferença de {_numero(escores[melhor] - escores[pior], 2)} "
               f"pontos é expressiva e recomenda priorizar a base {pior} no "
               f"plano de qualificação, tanto por seu impacto direto sobre os "
               f"indicadores quanto porque a base de menor qualidade limita o "
               f"pareamento de todas as demais com que se relacione."
               if escores[melhor] - escores[pior] > 5 else
               "As bases apresentam patamar de qualidade semelhante, o que "
               "sugere que os problemas identificados decorrem menos das "
               "particularidades de cada sistema e mais de fatores comuns ao "
               "processo de trabalho da rede notificadora."))

    if len(resultado.pareamentos) > 1:
        taxas = {p.rotulo: p.resumo()["TAXA_DE_PAREAMENTO_%"]
                 for p in resultado.pareamentos}
        maior = max(taxas, key=taxas.get)
        menor = min(taxas, key=taxas.get)
        _paragrafo(documento,
            f"Quanto ao pareamento, a maior taxa foi observada em {maior} "
            f"({_numero(taxas[maior], 2)}%) e a menor, em {menor} "
            f"({_numero(taxas[menor], 2)}%). A taxa de pareamento não mede "
            f"apenas o desempenho do procedimento: reflete, também, a "
            f"sobreposição real entre as populações registradas em cada "
            f"sistema. Uma taxa baixa entre bases cujas populações pouco se "
            f"sobrepõem é resultado esperado, e não deficiência.")

    _paragrafo(documento,
        "Quanto à completude, a comparação entre as bases permite identificar "
        "as variáveis cuja qualidade é sistematicamente inferior em todos os "
        "sistemas — indício de problema no instrumento de coleta ou na "
        "orientação às equipes — e distingui-las daquelas cuja qualidade varia "
        "entre sistemas, indício de problema circunscrito a um fluxo "
        "específico. A distinção importa porque as duas situações demandam "
        "intervenções diferentes: a primeira, revisão do instrumento; a "
        "segunda, atuação sobre o fluxo do sistema em que o problema se "
        "concentra.")


def _secao_orientacoes(documento: Document, resultado: ResultadoExecucao,
                       contadores: dict) -> None:
    _titulo(documento, "6 Orientações para as áreas técnicas", 1,
            quebra_antes=True)

    _paragrafo(documento,
        "Esta seção converte os achados em tarefas. As recomendações estão "
        "ordenadas por prioridade, entendida como a combinação entre a "
        "gravidade do problema e o número de registros afetados.")

    _titulo(documento, "6.1 Roteiro de trabalho sobre a planilha", 2)
    _lista(documento, [
        "Abrir a planilha de resultados e consultar a aba 01_RESUMO_EXECUTIVO "
        "para situar o conjunto: escore de qualidade por base e distribuição "
        "das cores.",
        "Nas abas das bases, filtrar a coluna CLASSIFICACAO pelo valor "
        "VERMELHO e trabalhar as correções em ordem de PRIORIDADE. Cada linha "
        "traz, nas colunas finais, a descrição do problema, a justificativa "
        "técnica e a recomendação de correção.",
        "Filtrar em seguida pelo valor AMARELO e distribuir a verificação "
        "manual entre os técnicos, orientando-se pela coluna "
        "SUGESTAO_PARA_A_AREA_TECNICA.",
        "Consultar a aba 25_DUPLICIDADES antes de qualquer exclusão de "
        "registro, consolidando no registro mantido os campos preenchidos "
        "apenas nas duplicatas.",
        "Trabalhar a aba 42_PARES_EM_REVISAO_MANUAL, que concentra os pares "
        "cuja decisão depende de juízo humano e onde o esforço de conferência "
        "tem maior rendimento.",
        "Consultar a aba 43_NAO_PAREADOS para distinguir os registros que não "
        "pareiam por ausência de chaves — problema corrigível — daqueles que "
        "não pareiam porque a pessoa efetivamente não consta da outra base.",
        "Aplicar as correções nos sistemas de origem e reexecutar a "
        "ferramenta, comparando os escores de qualidade para medir o efeito "
        "do trabalho realizado.",
    ], numerada=True)

    _titulo(documento, "6.2 Recomendações prioritárias", 2)
    from .planilha import _linhas_recomendacoes
    recomendacoes = _linhas_recomendacoes(resultado)
    prioritarias = sorted(
        recomendacoes,
        key=lambda l: (l["GRAVIDADE"] != VERMELHO, -l["REGISTROS_AFETADOS"]))[:10]

    if prioritarias:
        linhas = [[
            str(posicao),
            rotulo_do_tipo(l["TIPO_DE_INCONSISTENCIA"]),
            l["BASE"], _numero(l["REGISTROS_AFETADOS"]),
            _numero(l["PROPORCAO_DA_BASE_%"], 2),
            "Real" if l["GRAVIDADE"] == VERMELHO else "Provável",
        ] for posicao, l in enumerate(prioritarias, start=1)]
        contadores["tabela"] = _tabela(
            documento, contadores["tabela"],
            "Recomendações prioritárias, em ordem de gravidade e alcance",
            ["#", "Tipo de inconsistência", "Base", "Registros\nafetados",
             "% da base", "Natureza"], linhas,
            larguras=[1.0, 5.6, 1.6, 2.1, 1.8, 1.9])

        for posicao, recomendacao in enumerate(prioritarias[:6], start=1):
            _titulo(documento,
                    f"6.2.{posicao} "
                    f"{rotulo_do_tipo(recomendacao['TIPO_DE_INCONSISTENCIA'])}"
                    f" — {recomendacao['BASE']}", 3)
            _paragrafo(documento,
                f"Situação: {recomendacao['DESCRICAO_DO_PROBLEMA']} Foram "
                f"identificados {_numero(recomendacao['REGISTROS_AFETADOS'])} "
                f"registros afetados, correspondentes a "
                f"{_numero(recomendacao['PROPORCAO_DA_BASE_%'], 2)}% da base.")
            _paragrafo(documento,
                f"Por que importa: {recomendacao['JUSTIFICATIVA_TECNICA']}")
            _paragrafo(documento,
                f"O que fazer no registro: {recomendacao['RECOMENDACAO']}")
            _paragrafo(documento,
                f"O que fazer no processo: "
                f"{recomendacao['ACAO_ESTRUTURANTE_SUGERIDA']}")

    _titulo(documento, "6.3 Da correção pontual à ação estruturante", 2)
    _paragrafo(documento,
        "Quando um mesmo tipo de inconsistência atinge parcela expressiva dos "
        "registros, a correção caso a caso é necessária, mas insuficiente: o "
        "problema retornará na próxima competência. Madandola et al. (2023), "
        "em revisão integrativa registrada no PROSPERO, examinaram a relação "
        "entre as características das interfaces de entrada de dados e a "
        "qualidade da informação clínica registrada, e deslocam parte da "
        "explicação dos problemas de qualidade da conduta individual do "
        "notificador para o desenho dos instrumentos de registro. Esse achado "
        "fundamenta a proposição de medidas que atuem sobre o processo — "
        "crítica de preenchimento na entrada, listas de seleção restritas ao "
        "domínio válido, conferência prévia de duplicidade, padronização de "
        "convenções de preenchimento — e não apenas sobre o registro "
        "individual.")
    _paragrafo(documento,
        "Byrne e Saebo (2022), em revisão de escopo sobre o uso rotineiro dos "
        "dados do DHIS2, sustentam que nem a propriedade dos dados nem o "
        "acesso a dados de boa qualidade garantem, por si sós, o seu uso "
        "efetivo: para que a informação seja utilizada, os dados precisam ser "
        "coletados, processados e analisados em formato acessível. A produção "
        "regular deste relatório e da planilha que o acompanha é, nesse "
        "sentido, parte da intervenção, e não apenas seu registro.")


def _secao_limitacoes(documento: Document, resultado: ResultadoExecucao) -> None:
    _titulo(documento, "7 Limitações", 1, quebra_antes=True)

    _paragrafo(documento,
        "O procedimento apresenta limitações que devem ser explicitadas para "
        "que os resultados sejam lidos com a cautela devida.")

    _lista(documento, [
        "O pareamento não é solução de interoperabilidade. Opera sobre dados "
        "já produzidos, sem alterar os sistemas nem os padrões que os regem. "
        "Amplia a capacidade analítica sem resolver a fragmentação que o torna "
        "necessário.",
        "A eficácia e a precisão do linkage dependem da qualidade das bases "
        "originais. Registros com chaves ausentes ou com múltiplos erros "
        "simultâneos de digitação permanecem não pareados, qualquer que seja "
        "o limiar adotado.",
        "O emprego de bases secundárias comporta a possibilidade de erros "
        "sistemáticos, não detectáveis pelo procedimento: um campo "
        "consistentemente mal preenchido em toda a rede notificadora passa "
        "por todas as verificações de domínio e de coerência.",
        "A verificação manual de falsos-positivos é trabalhosa e, em bases "
        "extensas, só pode ser feita por amostragem. A ferramenta mitiga a "
        "dificuldade ao registrar, para cada par, o escore por campo e as "
        "divergências observadas, mas não a elimina.",
        "Os limiares adotados foram definidos com base na literatura e "
        "ajustados por análise de sensibilidade. Sua adequação a outros "
        "agravos, períodos ou recortes territoriais requer nova aferição "
        "contra amostra revisada por avaliadores independentes.",
        "As projeções supõem a continuidade das condições observadas no "
        "período. Mudanças no processo de notificação, campanhas, surtos ou "
        "alterações normativas rompem essa suposição e invalidam a projeção.",
        "A extração de dados a partir de arquivos em formato PDF é "
        "aproximada, por se tratar de formato de apresentação e não de "
        "intercâmbio. Bases assim obtidas exigem conferência reforçada.",
    ])

    if resultado.avisos:
        _titulo(documento, "7.1 Avisos registrados nesta execução", 2)
        _lista(documento, resultado.avisos)


def _secao_consideracoes(documento: Document, resultado: ResultadoExecucao) -> None:
    _titulo(documento, "8 Considerações finais", 1, quebra_antes=True)

    total_pares = sum(len([p for p in pa.pares if p.classificacao == PAREADO])
                      for pa in resultado.pareamentos)
    total_achados = sum(len(q.achados) for q in resultado.qualidade.values())

    _paragrafo(documento,
        f"A execução documentada neste relatório identificou "
        f"{_numero(total_achados)} inconsistências passíveis de correção nas "
        f"bases nativas e estabeleceu {_numero(total_pares)} correspondências "
        f"entre registros de sistemas distintos, em "
        f"{_numero(resultado.tempo_total, 1)} segundos de processamento. O "
        f"tempo de execução deve ser confrontado com o do procedimento manual "
        f"mapeado na etapa de diagnóstico situacional: é essa comparação, e "
        f"não o valor absoluto, que permite aferir o ganho de eficiência "
        f"previsto entre os indicadores de avaliação do produto.")

    _paragrafo(documento,
        "Os resultados sustentam a hipótese que orienta o projeto — a de que "
        "a automatização reduziria o tempo de execução e a margem de erro no "
        "pareamento entre sistemas —, com a ressalva de que a redução da "
        "margem de erro depende de um deslocamento no modo de trabalhar: o "
        "esforço humano deixa de ser aplicado à comparação registro a "
        "registro e passa a concentrar-se no conjunto, menor e explicitamente "
        "delimitado, dos pares que o procedimento não pôde decidir.")

    _paragrafo(documento,
        "Cabe insistir em um ponto de ordem conceitual. O produto não "
        "substitui uma agenda de interoperabilidade; torna-a mais visível. "
        "Cada inconsistência aqui relatada, cada par não recuperado por "
        "ausência de identificador comum, documenta uma consequência concreta "
        "da fragmentação entre sistemas concebidos em momentos distintos e "
        "sob concepções distintas quanto à própria finalidade da informação "
        "em saúde. Nesse sentido, o relatório serve a dois propósitos: "
        "qualificar as bases hoje disponíveis e reunir evidência empírica "
        "para sustentar, junto às instâncias competentes, a necessidade de "
        "padronização e de identificação unívoca do usuário no SUS.")

    _paragrafo(documento,
        "Recomenda-se, por fim, que a execução seja periódica e que os "
        "escores de qualidade sejam acompanhados ao longo do tempo. Uma "
        "execução isolada descreve uma situação; a série de execuções mede o "
        "efeito das intervenções realizadas — e é essa medida que converte o "
        "relatório em instrumento de gestão.")


def _secao_referencias(documento: Document) -> None:
    _titulo(documento, "Referências", 1, quebra_antes=True)

    referencias = [
        "ABDULLAHI YARI, I. et al. Security Engineering of Patient-Centered "
        "Health Care Information Systems in Peer-to-Peer Environments: "
        "Systematic Review. Journal of Medical Internet Research, v. 23, "
        "n. 11, e24460, 2021.",

        "BOGAERT, P. et al. Identifying common enablers and barriers in "
        "European health information systems. Health Policy, v. 125, n. 12, "
        "p. 1517-1526, 2021.",

        "BRASIL. Lei nº 13.709, de 14 de agosto de 2018. Lei Geral de "
        "Proteção de Dados Pessoais (LGPD). Brasília, DF: Presidência da "
        "República, 2018.",

        "BRASIL. Ministério da Saúde. Portaria de Consolidação nº 4, de 28 de "
        "setembro de 2017. Consolidação das normas sobre os sistemas e os "
        "subsistemas do Sistema Único de Saúde. Brasília, DF: Ministério da "
        "Saúde, 2017.",

        "BRASIL. Ministério da Saúde. Portaria nº 264, de 17 de fevereiro de "
        "2020. Altera a Lista Nacional de Notificação Compulsória de doenças, "
        "agravos e eventos de saúde pública. Brasília, DF: Ministério da "
        "Saúde, 2020.",

        "BYRNE, E.; SAEBO, J. I. Routine use of DHIS2 data: a scoping review. "
        "BMC Health Services Research, v. 22, n. 1, art. 1234, 2022.",

        "COHEN, W. W.; RAVIKUMAR, P.; FIENBERG, S. E. A comparison of string "
        "distance metrics for name-matching tasks. In: PROCEEDINGS OF THE "
        "IJCAI-03 WORKSHOP ON INFORMATION INTEGRATION ON THE WEB. Acapulco, "
        "2003. p. 73-78.",

        "CONSELHO NACIONAL DE SAÚDE (Brasil). Resolução nº 466, de 12 de "
        "dezembro de 2012. Brasília, DF: CNS, 2012.",

        "CONSELHO NACIONAL DE SAÚDE (Brasil). Resolução nº 510, de 7 de abril "
        "de 2016. Brasília, DF: CNS, 2016.",

        "ESMAEILZADEH, P.; SAMBASIVAN, M. Health Information Exchange (HIE): "
        "A literature review, assimilation pattern and a proposed "
        "classification for a new policy approach. Journal of Biomedical "
        "Informatics, v. 64, p. 74-86, 2016.",

        "GARCIA, K. K. S.; MIRANDA, C. B. de; SOUSA, F. N. e F. de. "
        "Procedures for health data linkage: applications in health "
        "surveillance. Epidemiologia e Serviços de Saúde, v. 31, n. 3, "
        "e20211272, 2022.",

        "GHAFFARI HESHAJIN, S. et al. A framework for health information "
        "governance: a scoping review. Health Research Policy and Systems, "
        "v. 22, n. 1, art. 109, 2024.",

        "GHALAVAND, H. et al. Common data quality elements for health "
        "information systems: a systematic review. BMC Medical Informatics "
        "and Decision Making, v. 24, n. 1, art. 243, 2024.",

        "HOLEMAN, I. et al. Building consensus on common features and "
        "interoperability use cases for community health information systems: "
        "a Delphi study. BMJ Global Health, v. 9, n. 4, e014001, 2024.",

        "MADANDOLA, O. O. et al. The relationship between electronic health "
        "records user interface features and data quality of patient clinical "
        "information: an integrative review. Journal of the American Medical "
        "Informatics Association, v. 31, n. 1, p. 240-255, 2023.",

        "ORGANIZACIÓN PANAMERICANA DE LA SALUD. eHealth in Latin America and "
        "the Caribbean: interoperability standards review. Washington, D.C.: "
        "OPAS, 2016.",

        "SCHMIDT, C. O. et al. Definitions, components and processes of data "
        "harmonisation in healthcare: a scoping review. BMC Medical "
        "Informatics and Decision Making, v. 20, n. 1, art. 222, 2020.",

        "TUMMERS, J. et al. Obstacles and features of health information "
        "systems: A systematic literature review. Computers in Biology and "
        "Medicine, v. 134, art. 104576, 2021.",

        "WINKLER, W. E. String comparator metrics and enhanced decision rules "
        "in the Fellegi-Sunter model of record linkage. In: PROCEEDINGS OF "
        "THE SECTION ON SURVEY RESEARCH METHODS. Alexandria: American "
        "Statistical Association, 1990. p. 354-359.",
    ]

    for referencia in sorted(referencias):
        paragrafo = documento.add_paragraph()
        paragrafo.paragraph_format.first_line_indent = Cm(0)
        paragrafo.paragraph_format.space_after = Pt(12)
        paragrafo.paragraph_format.line_spacing = 1.0
        paragrafo.alignment = WD_ALIGN_PARAGRAPH.LEFT
        execucao = paragrafo.add_run(referencia)
        execucao.font.size = Pt(12)
        execucao.font.name = FONTE


def _apendice_auditoria(documento: Document, resultado: ResultadoExecucao,
                        contadores: dict) -> None:
    _titulo(documento, "Apêndice A — Parâmetros de execução e auditoria", 1,
            quebra_antes=True)

    configuracao = resultado.configuracao
    trilha = resultado.trilha.como_dicionario()

    linhas = [
        ["Data e hora da execução",
         resultado.momento.strftime("%d/%m/%Y %H:%M:%S")],
        ["Limiar de pareamento", _numero(configuracao.limiar_pareamento, 2)],
        ["Limiar de revisão manual", _numero(configuracao.limiar_revisao, 2)],
        ["Limiar de duplicidade provável",
         _numero(configuracao.limiar_duplicidade, 2)],
        ["Ano de referência", str(configuracao.ano_referencia)],
        ["População de referência",
         _numero(configuracao.populacao_referencia)],
        ["Horizonte de projeção",
         f"{configuracao.horizonte_projecao} meses"],
        ["Pseudonimização na saída",
         "Sim" if configuracao.pseudonimizar_saida else "Não"],
        ["Modo cofre (bloqueio de rede)",
         "Ativo" if configuracao.modo_cofre else "Inativo"],
        ["Tentativas de saída de rede bloqueadas",
         _numero(len(trilha["tentativas_de_saida_de_rede_bloqueadas"]))],
        ["Tempo total de processamento",
         f"{_numero(resultado.tempo_total, 2)} segundos"],
        ["Sistema operacional", trilha["ambiente"]["sistema_operacional"]],
        ["Versão do interpretador", trilha["ambiente"]["python"]],
    ]
    contadores["tabela"] = _tabela(
        documento, contadores["tabela"], "Parâmetros da execução",
        ["Parâmetro", "Valor"], linhas, larguras=[7.5, 8.0])

    linhas = [[a["arquivo"], a["papel"], _numero(a["registros"])
               if a["registros"] != "" else "—",
               _numero(a["tamanho_bytes"]), a["sha256"][:32] + "…"]
              for a in trilha["arquivos"]]
    contadores["tabela"] = _tabela(
        documento, contadores["tabela"],
        "Arquivos processados e respectivos resumos criptográficos",
        ["Arquivo", "Papel", "Registros", "Bytes", "SHA-256 (32 primeiros)"],
        linhas, larguras=[4.2, 1.8, 1.8, 2.2, 5.5], tamanho=8)

    _paragrafo(documento,
        "O resumo criptográfico SHA-256 identifica univocamente o conteúdo de "
        "cada arquivo processado. Sua conferência permite demonstrar, em "
        "auditoria posterior, que os produtos gerados correspondem exatamente "
        "às versões das bases aqui relacionadas, sem que seja necessário "
        "armazenar cópia dos dados pessoais.")

    if not trilha["tentativas_de_saida_de_rede_bloqueadas"]:
        _paragrafo(documento,
            "Não foi registrada nenhuma tentativa de envio de dados para fora "
            "da estação de trabalho durante esta execução.")
    else:
        _paragrafo(documento,
            f"Foram bloqueadas "
            f"{len(trilha['tentativas_de_saida_de_rede_bloqueadas'])} "
            f"tentativas de conexão externa, todas impedidas antes de "
            f"qualquer transmissão. Os destinos constam da aba de auditoria "
            f"da planilha e do arquivo de trilha em formato JSON.")


# --------------------------------------------------------------------------- #
# Função principal
# --------------------------------------------------------------------------- #

def gerar_relatorio(resultado: ResultadoExecucao,
                    caminho: Path | str | None = None,
                    imagens: dict | None = None) -> Path:
    """Monta e grava o relatório analítico-descritivo completo."""
    configuracao = resultado.configuracao
    if caminho is None:
        marca = resultado.momento.strftime("%Y%m%d_%H%M")
        caminho = (Path(configuracao.diretorio_saida)
                   / f"ELO-SIS_relatorio_analitico_{marca}.docx")
    caminho = Path(caminho)

    if imagens is None:
        imagens = gr.gerar_todos(resultado,
                                 Path(configuracao.diretorio_saida) / "graficos")

    documento = Document()
    _configurar_documento(documento)
    contadores = {"figura": 1, "tabela": 1}

    _capa(documento, resultado)

    documento.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    _titulo(documento, "Sumário", 1)
    _sumario_automatico(documento)

    _secao_apresentacao(documento, resultado, contadores)
    _secao_metodologia(documento, resultado, contadores)
    _secao_qualidade(documento, resultado, imagens, contadores)
    _secao_pareamento(documento, resultado, imagens, contadores)
    _secao_desempenho(documento, resultado, imagens, contadores)
    _secao_epidemiologia(documento, resultado, imagens, contadores)
    _secao_orientacoes(documento, resultado, contadores)
    _secao_limitacoes(documento, resultado)
    _secao_consideracoes(documento, resultado)
    _secao_referencias(documento)
    _apendice_auditoria(documento, resultado, contadores)

    _numerar_paginas(documento)

    documento.core_properties.title = (
        "Relatório analítico-descritivo — qualificação, harmonização e "
        "pareamento das bases do SIM, do SINAN e do SINASC")
    documento.core_properties.author = "ELO-SIS"
    documento.core_properties.comments = (
        "Documento gerado automaticamente. Contém referência a dados pessoais "
        "sensíveis apenas de forma agregada.")

    caminho.parent.mkdir(parents=True, exist_ok=True)
    documento.save(caminho)
    resultado.trilha.registrar_arquivo(caminho, "saida")
    resultado.trilha.registrar("relatorio", f"Relatório gerado: {caminho.name}")
    return caminho
