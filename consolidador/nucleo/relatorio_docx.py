"""Montagem do relatorio analitico descritivo e comparativo em .docx."""

from __future__ import annotations

import datetime as _dt
from collections import Counter
from typing import Dict, List, Optional, Tuple

from . import texto as tx
from .docx_writer import Documento
from .normalizacao import Consolidado
from .pareamento import ResultadoPareamento
from .qualidade import (DIMENSOES, GRAVIDADE_ALTA, GRAVIDADE_BAIXA, GRAVIDADE_MEDIA,
                        ResultadoQualidade, classificar)
from .resultado import ResultadoGeral

VERMELHO = "C0392B"
VERDE = "2E7D32"
AMBAR = "B7791F"
CINZA = "595959"


def gerar(resultado: ResultadoGeral, caminho: str) -> str:
    documento = Documento(
        titulo=f"Relatorio analitico - {resultado.nome_a} x {resultado.nome_b}"
    )
    estatisticas = resultado.estatisticas()

    documento.titulo_principal(
        "Relatorio analitico, descritivo e comparativo",
        f"Consolidacao, analise de qualidade e pareamento entre {resultado.nome_a} e "
        f"{resultado.nome_b} - emitido em {resultado.inicio:%d/%m/%Y as %H:%M}",
    )
    _sumario_executivo(documento, resultado, estatisticas)
    documento.sumario()
    documento.quebra_pagina()

    _secao_objetivo(documento, resultado)
    _secao_metodologia(documento, resultado)
    _secao_arquivos(documento, resultado)
    documento.quebra_pagina()

    _secao_consolidacao(documento, resultado)
    documento.quebra_pagina()

    _secao_qualidade(documento, resultado)
    documento.quebra_pagina()

    _secao_pareamento(documento, resultado, estatisticas)
    _secao_comparacao(documento, resultado, estatisticas)
    documento.quebra_pagina()

    _secao_conclusoes(documento, resultado, estatisticas)
    _secao_anexo(documento, resultado)
    documento.salvar(caminho)
    return caminho


# --------------------------------------------------------------------------
# Sumario executivo
# --------------------------------------------------------------------------


def _sumario_executivo(documento: Documento, resultado: ResultadoGeral, estatisticas: Dict) -> None:
    documento.secao("Sumario executivo", 1)
    nota_a = resultado.qualidade_a.nota_geral if resultado.qualidade_a else 0.0
    nota_b = resultado.qualidade_b.nota_geral if resultado.qualidade_b else 0.0
    documento.paragrafo(
        f"Foram processados {len(resultado.arquivos)} arquivo(s), dos quais "
        f"{estatisticas['registros_a']} registros foram consolidados em {resultado.nome_a} e "
        f"{estatisticas['registros_b']} em {resultado.nome_b}. O pareamento localizou "
        f"{estatisticas['pares']} correspondencia(s), o que cobre "
        f"{estatisticas['cobertura_a']:.1f}% da base de {resultado.nome_a} e "
        f"{estatisticas['cobertura_b']:.1f}% da base de {resultado.nome_b}."
    )
    documento.paragrafo(
        f"A qualidade dos dados foi avaliada em sete dimensoes. {resultado.nome_a} obteve nota "
        f"{nota_a:.1f} ({classificar(nota_a)}) e {resultado.nome_b} obteve {nota_b:.1f} "
        f"({classificar(nota_b)}). {_frase_comparativa_qualidade(resultado, nota_a, nota_b)}"
    )
    documento.paragrafo(
        f"Do ponto de vista da comparacao entre as bases, {estatisticas['somente_a']} registro(s) "
        f"existem apenas em {resultado.nome_a}, {estatisticas['somente_b']} existem apenas em "
        f"{resultado.nome_b} e {estatisticas['divergentes']} par(es) apresentam divergencia de "
        f"conteudo entre os dois sistemas. Esses tres numeros medem, em conjunto, o grau de "
        f"desalinhamento entre as bases."
    )
    documento.tabela(
        ["Indicador", resultado.nome_a, resultado.nome_b],
        [
            ["Registros consolidados", estatisticas["registros_a"], estatisticas["registros_b"]],
            ["Registros pareados",
             estatisticas["registros_a"] - estatisticas["somente_a"],
             estatisticas["registros_b"] - estatisticas["somente_b"]],
            ["Registros exclusivos", estatisticas["somente_a"], estatisticas["somente_b"]],
            ["Cobertura do pareamento",
             f"{estatisticas['cobertura_a']:.1f}%", f"{estatisticas['cobertura_b']:.1f}%"],
            ["Nota de qualidade", f"{nota_a:.1f}", f"{nota_b:.1f}"],
            ["Ocorrencias de qualidade",
             len(resultado.qualidade_a.ocorrencias) if resultado.qualidade_a else 0,
             len(resultado.qualidade_b.ocorrencias) if resultado.qualidade_b else 0],
        ],
        larguras=[4200, 2400, 2400],
        alinhamentos=["left", "center", "center"],
        legenda="Tabela 1 - Painel comparativo dos dois sistemas.",
    )


def _frase_comparativa_qualidade(resultado: ResultadoGeral, nota_a: float, nota_b: float) -> str:
    diferenca = abs(nota_a - nota_b)
    if diferenca < 2:
        return "As duas bases apresentam nivel de qualidade equivalente."
    melhor = resultado.nome_a if nota_a > nota_b else resultado.nome_b
    pior = resultado.nome_b if nota_a > nota_b else resultado.nome_a
    return (
        f"A base de {melhor} apresenta qualidade superior a de {pior}, com diferenca de "
        f"{diferenca:.1f} ponto(s); as causas dessa diferenca estao detalhadas na secao 4."
    )


# --------------------------------------------------------------------------
# 1. Objetivo / 2. Metodologia / 3. Arquivos
# --------------------------------------------------------------------------


def _secao_objetivo(documento: Documento, resultado: ResultadoGeral) -> None:
    documento.secao("1. Objetivo e escopo", 1)
    documento.paragrafo(
        f"Este relatorio documenta a rotina de consolidacao, verificacao de qualidade e "
        f"pareamento das bases de {resultado.nome_a} e {resultado.nome_b}. O objetivo e "
        f"produzir uma visao unica de cada sistema a partir dos arquivos recebidos, medir a "
        f"confiabilidade das informacoes de cada base e identificar, de forma rastreavel, o que "
        f"consta em um sistema e nao consta no outro."
    )
    documento.paragrafo(
        "O relatorio acompanha a planilha gerada na mesma execucao, que traz os dados completos "
        "em abas separadas: consolidado de cada sistema, analise de qualidade de cada sistema, "
        "pareamento e as duas listas de registros exclusivos, com realce em cor."
    )


def _secao_metodologia(documento: Documento, resultado: ResultadoGeral) -> None:
    documento.secao("2. Metodologia", 1)
    documento.paragrafo(
        "A rotina segue seis etapas encadeadas, todas executadas automaticamente:"
    )
    modo = resultado.deteccao.modo if resultado.deteccao else "automatico"
    identificacao = (
        "os arquivos foram classificados pelas regras do perfil configurado (nome do arquivo, "
        "nome da aba e colunas esperadas)"
        if modo == "perfil" else
        "os arquivos foram classificados automaticamente, agrupando-os por semelhanca de "
        "cabecalho e de nome de arquivo"
    )
    documento.lista([
        "Leitura: cada arquivo e interpretado conforme seu formato (planilha, texto delimitado, "
        "HTML, DBF, JSON ou XML), com deteccao de codificacao, de separador e da linha de "
        "cabecalho real.",
        f"Identificacao do sistema: {identificacao}.",
        "Consolidacao: os arquivos de um mesmo sistema sao empilhados em uma unica tabela, com "
        "alinhamento das colunas equivalentes e registro da origem de cada linha.",
        "Analise de qualidade: cada base e avaliada nas dimensoes de completude, unicidade, "
        "validade, consistencia, padronizacao, acuracia e atualidade.",
        "Pareamento: os registros dos dois sistemas sao casados por chave exata e, quando nao ha "
        "chave, por similaridade textual controlada por limiar.",
        "Comparacao: os registros sem correspondencia sao listados dos dois lados, com o motivo "
        "da ausencia e o registro mais parecido encontrado.",
    ])
    if resultado.pareamento and resultado.pareamento.chaves_usadas:
        chaves = "; ".join(f"{a} = {b}" for a, b in resultado.pareamento.chaves_usadas)
        documento.paragrafo(
            f"Chaves utilizadas no pareamento: {chaves}. A comparacao de valores desconsidera "
            f"diferenca de acentuacao, caixa, pontuacao e formatacao de numeros e datas."
        )
    if resultado.pareamento and resultado.pareamento.campos_similaridade:
        campos = "; ".join(f"{a} ~ {b}" for a, b in resultado.pareamento.campos_similaridade)
        documento.paragrafo(
            f"Campos usados na comparacao por similaridade: {campos}. Foram aceitos como par "
            f"provavel os casos com semelhanca igual ou superior a "
            f"{resultado.perfil.pareamento.limiar_provavel:.0%} e marcados para revisao os casos "
            f"entre {resultado.perfil.pareamento.limiar_duvidoso:.0%} e esse limite."
        )


def _secao_arquivos(documento: Documento, resultado: ResultadoGeral) -> None:
    documento.secao("3. Arquivos processados", 1)
    linhas = []
    cores: Dict[int, Dict[int, str]] = {}
    for indice, arquivo in enumerate(resultado.arquivos):
        linhas.append([
            arquivo.nome, arquivo.extensao, arquivo.sistema or "-",
            f"{arquivo.confianca:.0%}" if arquivo.confianca else "-",
            arquivo.registros, arquivo.erro or arquivo.justificativa,
        ])
        if arquivo.erro:
            cores[indice] = {i: "F8D7DA" for i in range(6)}
        elif arquivo.confianca and arquivo.confianca < 0.6:
            cores[indice] = {3: "FFF3CD"}
    documento.tabela(
        ["Arquivo", "Formato", "Sistema", "Confianca", "Registros", "Criterio / observacao"],
        linhas or [["Nenhum arquivo processado", "-", "-", "-", 0, "-"]],
        larguras=[2600, 800, 1400, 900, 900, 3400],
        cores_celula=cores,
        alinhamentos=["left", "center", "left", "center", "center", "left"],
        legenda="Tabela 2 - Origem dos dados e criterio de identificacao de cada arquivo.",
    )
    erros = [a for a in resultado.arquivos if a.erro]
    if erros:
        documento.paragrafo(
            f"Atencao: {len(erros)} arquivo(s) nao puderam ser lidos e ficaram de fora da "
            f"consolidacao. Enquanto nao forem corrigidos, os numeros deste relatorio "
            f"representam apenas os arquivos processados com sucesso.",
            cor=VERMELHO,
        )


# --------------------------------------------------------------------------
# 4. Consolidacao
# --------------------------------------------------------------------------


def _secao_consolidacao(documento: Documento, resultado: ResultadoGeral) -> None:
    documento.secao("4. Consolidacao das bases", 1)
    for indice, consolidado in enumerate(
        [c for c in (resultado.consolidado_a, resultado.consolidado_b) if c], start=1
    ):
        documento.secao(f"4.{indice} {consolidado.nome}", 2)
        origens = ", ".join(
            f"{a['arquivo']}" + (f" (aba {a['aba']})" if a["aba"] else "") +
            f": {a['registros']} registros"
            for a in consolidado.arquivos
        ) or "nenhum arquivo"
        documento.paragrafo(
            f"A base consolidada de {consolidado.nome} reune {len(consolidado.tabela.linhas)} "
            f"registros e {len(consolidado.colunas_dados)} colunas, provenientes de "
            f"{len(consolidado.arquivos)} arquivo(s)/aba(s): {origens}."
        )
        chaves = consolidado.chaves
        if chaves:
            documento.paragrafo(
                f"Campo(s) identificado(s) como chave do sistema: {', '.join(chaves)}. "
                f"Esse campo e a base do pareamento com o outro sistema."
            )
        else:
            documento.paragrafo(
                "Nenhum campo com poder de identificacao suficiente foi encontrado nesta base; "
                "o pareamento dependeu de comparacao aproximada, com maior chance de revisao "
                "manual.", cor=AMBAR,
            )
        documento.tabela(
            ["Campo", "Tipo reconhecido", "Chave", "Preenchimento", "Valores distintos"],
            [
                [
                    campo.nome, campo.tipo, "sim" if campo.chave else "",
                    _percentual_preenchimento(consolidado, campo.nome),
                    _valores_distintos(consolidado, campo.nome),
                ]
                for campo in consolidado.campos[:30]
            ] or [["-", "-", "", "-", "-"]],
            larguras=[3000, 1800, 800, 1800, 1600],
            alinhamentos=["left", "left", "center", "center", "center"],
            legenda=f"Tabela {2 + indice} - Estrutura reconhecida em {consolidado.nome}"
                    + (" (30 primeiros campos)." if len(consolidado.campos) > 30 else "."),
        )


def _percentual_preenchimento(consolidado: Consolidado, coluna: str) -> str:
    total = len(consolidado.tabela.linhas)
    if not total:
        return "-"
    preenchidos = sum(1 for l in consolidado.tabela.linhas if tx.limpar(l.get(coluna)))
    return f"{100.0 * preenchidos / total:.1f}%"


def _valores_distintos(consolidado: Consolidado, coluna: str) -> int:
    return len({tx.normalizar(l.get(coluna)) for l in consolidado.tabela.linhas if tx.limpar(l.get(coluna))})


# --------------------------------------------------------------------------
# 5. Qualidade
# --------------------------------------------------------------------------


def _secao_qualidade(documento: Documento, resultado: ResultadoGeral) -> None:
    documento.secao("5. Analise dos atributos de qualidade", 1)
    documento.paragrafo(
        "Cada base foi avaliada em sete dimensoes de qualidade, com nota de 0 a 100. As notas "
        "resultam da proporcao de registros conformes em cada dimensao; a nota geral e a media "
        "ponderada, com maior peso para completude, validade e unicidade."
    )
    pares = [
        (resultado.qualidade_a, resultado.consolidado_a),
        (resultado.qualidade_b, resultado.consolidado_b),
    ]
    numero_tabela = 5
    for indice, (qualidade, consolidado) in enumerate(
        [(q, c) for q, c in pares if q and c], start=1
    ):
        documento.secao(f"5.{indice} {qualidade.nome}", 2)
        for frase in qualidade.resumo_texto:
            documento.paragrafo(frase)
        documento.tabela(
            ["Dimensao", "Nota", "Classificacao", "Ocorrencias", "Interpretacao"],
            [
                [
                    dimensao, f"{qualidade.notas_dimensao.get(dimensao, 0):.1f}",
                    classificar(qualidade.notas_dimensao.get(dimensao, 0)),
                    qualidade.por_dimensao().get(dimensao, 0),
                    _interpretacao_dimensao(dimensao, qualidade.notas_dimensao.get(dimensao, 0)),
                ]
                for dimensao in DIMENSOES
            ],
            larguras=[1600, 800, 1300, 1100, 4200],
            cores_celula={
                posicao: {1: _cor_nota(qualidade.notas_dimensao.get(dimensao, 0))}
                for posicao, dimensao in enumerate(DIMENSOES)
            },
            alinhamentos=["left", "center", "center", "center", "left"],
            legenda=f"Tabela {numero_tabela} - Notas por dimensao em {qualidade.nome}.",
        )
        numero_tabela += 1
        _detalhar_ocorrencias(documento, qualidade, numero_tabela)
        numero_tabela += 1

    if resultado.qualidade_a and resultado.qualidade_b:
        documento.secao("5.3 Comparacao de qualidade entre os dois sistemas", 2)
        _comparar_qualidade(documento, resultado, numero_tabela)


def _interpretacao_dimensao(dimensao: str, nota: float) -> str:
    if nota >= 95:
        base = "Situacao controlada"
    elif nota >= 85:
        base = "Pequenos ajustes recomendados"
    elif nota >= 70:
        base = "Requer correcao planejada"
    else:
        base = "Requer acao corretiva imediata"
    complementos = {
        "Completude": "campos em branco comprometem analises e cruzamentos",
        "Unicidade": "duplicidade infla contagens e gera pagamento ou atendimento em duplicidade",
        "Validade": "valores fora do formato impedem integracao automatica",
        "Consistencia": "campos que se contradizem dentro do mesmo registro",
        "Padronizacao": "a mesma informacao escrita de formas diferentes dificulta o cruzamento",
        "Acuracia": "valores implausiveis distorcem totais e medias",
        "Atualidade": "dados antigos reduzem a utilidade da base para decisao",
    }
    return f"{base}: {complementos.get(dimensao, '')}"


def _cor_nota(nota: float) -> str:
    if nota >= 95:
        return "D5F5E3"
    if nota >= 85:
        return "EAF6E4"
    if nota >= 70:
        return "FFF3CD"
    return "F8D7DA"


def _detalhar_ocorrencias(documento: Documento, qualidade: ResultadoQualidade, numero_tabela: int) -> None:
    if not qualidade.ocorrencias:
        documento.paragrafo(
            "Nenhuma inconsistencia foi identificada nesta base.", cor=VERDE,
        )
        return
    contagem = Counter(
        (o.gravidade, o.dimensao, o.campo, o.descricao.split("(")[0].strip())
        for o in qualidade.ocorrencias
    )
    ordem = {GRAVIDADE_ALTA: 0, GRAVIDADE_MEDIA: 1, GRAVIDADE_BAIXA: 2}
    principais = sorted(
        contagem.items(), key=lambda item: (ordem.get(item[0][0], 3), -item[1])
    )[:12]
    linhas = [
        [gravidade, dimensao, campo, descricao, quantidade]
        for (gravidade, dimensao, campo, descricao), quantidade in principais
    ]
    cores = {
        indice: {0: {"Alta": "F8D7DA", "Media": "FFF3CD"}.get(linha[0], "EDEDED")}
        for indice, linha in enumerate(linhas)
    }
    documento.tabela(
        ["Gravidade", "Dimensao", "Campo", "Inconsistencia", "Qtd."],
        linhas,
        larguras=[1100, 1400, 1900, 3800, 800],
        cores_celula=cores,
        alinhamentos=["center", "left", "left", "left", "center"],
        legenda=f"Tabela {numero_tabela} - Principais inconsistencias de {qualidade.nome} "
                f"(a lista completa esta na aba 'Qualidade {qualidade.nome}' da planilha).",
    )
    graves = [o for o in qualidade.ocorrencias if o.gravidade == GRAVIDADE_ALTA]
    if graves:
        campos_criticos = Counter(o.campo for o in graves).most_common(3)
        detalhe = ", ".join(f"{campo} ({quantidade})" for campo, quantidade in campos_criticos)
        documento.paragrafo(
            f"As {len(graves)} ocorrencias de gravidade alta concentram-se em: {detalhe}. "
            f"Sao os pontos que comprometem diretamente o cruzamento entre os sistemas e devem "
            f"ser tratados primeiro.", cor=VERMELHO,
        )


def _comparar_qualidade(documento: Documento, resultado: ResultadoGeral, numero_tabela: int) -> None:
    qualidade_a, qualidade_b = resultado.qualidade_a, resultado.qualidade_b
    linhas, cores = [], {}
    for indice, dimensao in enumerate(DIMENSOES):
        nota_a = qualidade_a.notas_dimensao.get(dimensao, 0.0)
        nota_b = qualidade_b.notas_dimensao.get(dimensao, 0.0)
        diferenca = nota_a - nota_b
        if abs(diferenca) < 2:
            leitura = "equivalentes"
        else:
            melhor = resultado.nome_a if diferenca > 0 else resultado.nome_b
            leitura = f"vantagem de {melhor} ({abs(diferenca):.1f} pontos)"
        linhas.append([dimensao, f"{nota_a:.1f}", f"{nota_b:.1f}",
                       f"{diferenca:+.1f}", leitura])
        cores[indice] = {1: _cor_nota(nota_a), 2: _cor_nota(nota_b)}
    documento.tabela(
        ["Dimensao", resultado.nome_a, resultado.nome_b, "Diferenca", "Leitura"],
        linhas,
        larguras=[1600, 1400, 1400, 1100, 3500],
        cores_celula=cores,
        alinhamentos=["left", "center", "center", "center", "left"],
        legenda=f"Tabela {numero_tabela} - Comparacao das notas de qualidade por dimensao.",
    )
    maiores = sorted(
        DIMENSOES,
        key=lambda d: -abs(qualidade_a.notas_dimensao.get(d, 0) - qualidade_b.notas_dimensao.get(d, 0)),
    )[:2]
    detalhes = []
    for dimensao in maiores:
        nota_a = qualidade_a.notas_dimensao.get(dimensao, 0)
        nota_b = qualidade_b.notas_dimensao.get(dimensao, 0)
        if abs(nota_a - nota_b) < 2:
            continue
        pior = resultado.nome_b if nota_a > nota_b else resultado.nome_a
        detalhes.append(f"{dimensao} (diferenca de {abs(nota_a - nota_b):.1f} pontos, "
                        f"desfavoravel a {pior})")
    if detalhes:
        documento.paragrafo(
            "As diferencas mais relevantes entre as bases estao em: " + "; ".join(detalhes) +
            ". Esse desequilibrio costuma indicar diferenca de regra de preenchimento ou de "
            "critica no cadastro de origem, e nao apenas erro pontual de digitacao."
        )


# --------------------------------------------------------------------------
# 6. Pareamento
# --------------------------------------------------------------------------


def _secao_pareamento(documento: Documento, resultado: ResultadoGeral, estatisticas: Dict) -> None:
    documento.secao("6. Pareamento entre os sistemas", 1)
    pareamento: Optional[ResultadoPareamento] = resultado.pareamento
    if not pareamento:
        documento.paragrafo("O pareamento nao pode ser executado nesta rodada.", cor=VERMELHO)
        return
    contagem = pareamento.contagem_por_tipo()
    documento.paragrafo(
        f"Foram identificados {pareamento.total_pares} pares entre as duas bases. "
        f"{contagem.get('Exato por chave', 0)} par(es) resultaram de igualdade exata da chave "
        f"principal, {contagem.get('Exato por chave alternativa', 0)} de chave alternativa, "
        f"{contagem.get('Provavel por similaridade', 0)} de semelhanca alta e "
        f"{contagem.get('Duvidoso - revisar', 0)} ficaram na faixa duvidosa, que exige "
        f"conferencia manual."
    )
    documento.tabela(
        ["Tipo de pareamento", "Pares", "Participacao", "Confiabilidade"],
        [
            [tipo, quantidade,
             f"{100.0 * quantidade / max(pareamento.total_pares, 1):.1f}%",
             _confiabilidade(tipo)]
            for tipo, quantidade in sorted(contagem.items(), key=lambda item: -item[1])
        ] or [["Nenhum par encontrado", 0, "0%", "-"]],
        larguras=[3000, 1100, 1400, 3500],
        alinhamentos=["left", "center", "center", "left"],
        legenda="Tabela 9 - Composicao do pareamento por criterio de casamento.",
    )
    divergentes = [p for p in pareamento.pares if p.divergencias]
    if divergentes:
        contagem_campos = Counter(
            d.campo_a for par in divergentes for d in par.divergencias
        )
        documento.paragrafo(
            f"Entre os pares localizados, {len(divergentes)} apresentam ao menos um campo com "
            f"valor diferente entre os sistemas "
            f"({100.0 * len(divergentes) / max(pareamento.total_pares, 1):.1f}% dos pares). "
            f"Isso significa que o registro existe nos dois lugares, mas a informacao nao esta "
            f"igual - situacao que costuma gerar retrabalho e decisao com base em dado errado."
        )
        documento.tabela(
            ["Campo", "Pares divergentes", "% dos pares", "Exemplo (valor em cada sistema)"],
            [
                [campo, quantidade,
                 f"{100.0 * quantidade / max(pareamento.total_pares, 1):.1f}%",
                 _exemplo_divergencia(divergentes, campo)]
                for campo, quantidade in contagem_campos.most_common(10)
            ],
            larguras=[2200, 1400, 1100, 4300],
            alinhamentos=["left", "center", "center", "left"],
            legenda="Tabela 10 - Campos que mais divergem entre registros pareados.",
        )
    else:
        documento.paragrafo(
            "Nenhum par apresentou divergencia de conteudo nos campos comparados: onde os dois "
            "sistemas se encontram, a informacao esta igual.", cor=VERDE,
        )
    duvidosos = [p for p in pareamento.pares if p.tipo.startswith("Duvidoso")]
    if duvidosos:
        documento.paragrafo(
            f"{len(duvidosos)} par(es) foram classificados como duvidosos e estao marcados na aba "
            f"'Pareamento'. Recomenda-se conferencia manual antes de considerar esses registros "
            f"como equivalentes.", cor=AMBAR,
        )
    multiplos = [p for p in pareamento.pares if p.multiplicidade != "1:1"]
    if multiplos:
        documento.paragrafo(
            f"{len(multiplos)} par(es) envolvem registros que casaram com mais de um registro do "
            f"outro sistema. Isso indica duplicidade em uma das bases e deve ser resolvido na "
            f"origem, pois impede o cruzamento um-para-um.", cor=AMBAR,
        )


def _confiabilidade(tipo: str) -> str:
    return {
        "Exato por chave": "Alta - identidade confirmada pela chave principal",
        "Exato por chave alternativa": "Alta - identidade confirmada por chave secundaria",
        "Provavel por similaridade": "Media - semelhanca acima do limite de aceite",
        "Duvidoso - revisar": "Baixa - exige conferencia manual",
    }.get(tipo, "-")


def _exemplo_divergencia(divergentes, campo: str) -> str:
    for par in divergentes:
        for divergencia in par.divergencias:
            if divergencia.campo_a == campo:
                return (f"'{divergencia.valor_a[:40] or '(vazio)'}' x "
                        f"'{divergencia.valor_b[:40] or '(vazio)'}'")
    return "-"


# --------------------------------------------------------------------------
# 7. Comparacao das listas
# --------------------------------------------------------------------------


def _secao_comparacao(documento: Documento, resultado: ResultadoGeral, estatisticas: Dict) -> None:
    documento.secao("7. Comparacao: o que existe em um sistema e nao existe no outro", 1)
    pareamento = resultado.pareamento
    if not pareamento:
        return
    for indice, (lado, nome, nome_oposto, itens, total) in enumerate((
        ("A", resultado.nome_a, resultado.nome_b, pareamento.somente_a, estatisticas["registros_a"]),
        ("B", resultado.nome_b, resultado.nome_a, pareamento.somente_b, estatisticas["registros_b"]),
    ), start=1):
        documento.secao(f"7.{indice} Registros exclusivos de {nome}", 2)
        percentual = 100.0 * len(itens) / total if total else 0.0
        if not itens:
            documento.paragrafo(
                f"Todos os {total} registros de {nome} foram localizados em {nome_oposto}.",
                cor=VERDE,
            )
            continue
        documento.paragrafo(
            f"{len(itens)} registro(s) de {nome} ({percentual:.1f}% da base) nao foram "
            f"localizados em {nome_oposto}. A lista completa, com todas as colunas e realce em "
            f"cor, esta na aba 'Somente em {nome}' da planilha."
        )
        motivos = Counter(_classificar_motivo(item) for item in itens)
        documento.tabela(
            ["Motivo da ausencia", "Registros", "Participacao"],
            [[motivo, quantidade, f"{100.0 * quantidade / len(itens):.1f}%"]
             for motivo, quantidade in motivos.most_common()],
            larguras=[5200, 1600, 1600],
            alinhamentos=["left", "center", "center"],
            legenda=f"Tabela {10 + indice} - Motivos apurados para a ausencia em {nome_oposto}.",
        )
        exemplos = itens[:8]
        chave = pareamento.chaves_usadas[0][0] if pareamento.chaves_usadas and lado == "A" else (
            pareamento.chaves_usadas[0][1] if pareamento.chaves_usadas else ""
        )
        colunas_exemplo = _colunas_exemplo(resultado, lado, chave)
        documento.tabela(
            ["ID"] + colunas_exemplo + ["Mais parecido no outro sistema"],
            [
                [item.linha.get("ID_Registro", "")] +
                [tx.limpar(item.linha.get(coluna))[:38] for coluna in colunas_exemplo] +
                [f"{item.melhor_candidato[:38]} ({item.escore_candidato:.0%})"
                 if item.melhor_candidato else "nenhum"]
                for item in exemplos
            ],
            larguras=[1100] + [2200] * len(colunas_exemplo) + [2600],
            cores_celula={i: {0: "FCE4D6" if lado == "A" else "DDEBF7"} for i in range(len(exemplos))},
            alinhamentos=["left"] * (len(colunas_exemplo) + 2),
            legenda=f"Tabela {12 + indice} - Amostra dos registros exclusivos de {nome} "
                    f"({len(exemplos)} de {len(itens)}).",
        )


def _classificar_motivo(item) -> str:
    if "sem valor no campo-chave" in item.motivo:
        return "Registro sem chave preenchida (impossivel localizar no outro sistema)"
    if item.escore_candidato >= 0.85:
        return "Ha registro muito parecido no outro sistema (provavel erro de digitacao na chave)"
    if item.escore_candidato >= 0.60:
        return "Ha registro parecido, mas abaixo do limite de aceite (exige conferencia)"
    return "Ausencia efetiva: nenhum registro semelhante no outro sistema"


def _colunas_exemplo(resultado: ResultadoGeral, lado: str, chave: str) -> List[str]:
    consolidado = resultado.consolidado_a if lado == "A" else resultado.consolidado_b
    if not consolidado:
        return []
    colunas = [c for c in consolidado.colunas_dados if c == chave]
    for campo in consolidado.campos:
        if len(colunas) >= 3:
            break
        if campo.nome not in colunas:
            colunas.append(campo.nome)
    return colunas[:3]


# --------------------------------------------------------------------------
# 8. Conclusoes / Anexo
# --------------------------------------------------------------------------


def _secao_conclusoes(documento: Documento, resultado: ResultadoGeral, estatisticas: Dict) -> None:
    documento.secao("8. Conclusoes e recomendacoes", 1)
    conclusoes: List[str] = []
    alinhamento = min(estatisticas["cobertura_a"], estatisticas["cobertura_b"])
    if alinhamento >= 95:
        conclusoes.append(
            f"As bases estao bem alinhadas: ao menos {alinhamento:.1f}% dos registros de cada "
            f"sistema tem correspondencia no outro."
        )
    elif alinhamento >= 80:
        conclusoes.append(
            f"O alinhamento entre as bases e razoavel ({alinhamento:.1f}% de cobertura minima), "
            f"mas o volume de registros exclusivos ja e suficiente para gerar divergencia em "
            f"relatorios gerenciais."
        )
    else:
        conclusoes.append(
            f"As bases estao materialmente desalinhadas: a cobertura minima e de "
            f"{alinhamento:.1f}%. Qualquer numero extraido de um sistema isoladamente tende a "
            f"divergir do outro."
        )
    if estatisticas["divergentes"]:
        conclusoes.append(
            f"{estatisticas['divergentes']} registro(s) existem nos dois sistemas com conteudo "
            f"diferente; e a situacao mais critica, porque nao aparece em conferencia por "
            f"contagem e so e detectada no cruzamento campo a campo."
        )
    for qualidade in (resultado.qualidade_a, resultado.qualidade_b):
        if not qualidade:
            continue
        graves = qualidade.por_gravidade().get(GRAVIDADE_ALTA, 0)
        if graves:
            conclusoes.append(
                f"{qualidade.nome} apresenta {graves} ocorrencia(s) de gravidade alta "
                f"(nota geral {qualidade.nota_geral:.1f}), com impacto direto na confiabilidade "
                f"do cruzamento."
            )
    documento.paragrafo("Principais constatacoes desta apuracao:")
    documento.lista(conclusoes)

    documento.paragrafo("Encaminhamentos sugeridos, em ordem de prioridade:")
    recomendacoes = [
        "Corrigir na origem as ocorrencias de gravidade alta (chave duplicada, chave ausente e "
        "documento invalido), pois sao elas que impedem o pareamento automatico.",
        "Tratar os registros exclusivos de cada sistema: confirmar se sao cadastros que faltam "
        "no outro sistema ou registros que deveriam ter sido baixados.",
        "Conferir manualmente os pares classificados como duvidosos antes de considera-los "
        "equivalentes.",
        "Padronizar o preenchimento dos campos com maior numero de divergencias de grafia, "
        "preferencialmente com lista de valores no proprio sistema de origem.",
        "Repetir esta rotina no mesmo intervalo (mensal ou quinzenal) e acompanhar a evolucao "
        "das notas de qualidade e da cobertura do pareamento.",
    ]
    documento.lista(recomendacoes, numerada=True)
    documento.paragrafo(
        f"Rotina executada em {resultado.duracao_segundos:.1f} segundos sobre "
        f"{len(resultado.arquivos)} arquivo(s). Planilha de apoio: "
        f"{resultado.caminho_planilha or 'gerada na mesma pasta'}.",
        italico=True, cor=CINZA,
    )


def _secao_anexo(documento: Documento, resultado: ResultadoGeral) -> None:
    documento.secao("Anexo A - Como ler a planilha gerada", 1)
    documento.tabela(
        ["Aba", "Conteudo"],
        [
            ["Resumo", "Painel executivo com volumes, notas de qualidade e resultado do pareamento."],
            [f"Consolidado {resultado.nome_a}",
             f"Todos os registros de {resultado.nome_a}, com origem de cada linha e situacao no pareamento."],
            [f"Consolidado {resultado.nome_b}",
             f"Todos os registros de {resultado.nome_b}, no mesmo formato."],
            [f"Qualidade {resultado.nome_a}",
             "Notas por dimensao, indicadores por campo e lista completa de inconsistencias."],
            [f"Qualidade {resultado.nome_b}", "Mesma estrutura, para o segundo sistema."],
            ["Pareamento",
             "Pares encontrados, criterio, escore e comparacao campo a campo (divergencias em amarelo)."],
            [f"Somente em {resultado.nome_a}",
             f"Registros de {resultado.nome_a} ausentes em {resultado.nome_b}, realcados em laranja."],
            [f"Somente em {resultado.nome_b}",
             f"Registros de {resultado.nome_b} ausentes em {resultado.nome_a}, realcados em azul."],
            ["Arquivos lidos", "Auditoria: qual arquivo virou qual sistema e por que criterio."],
        ],
        larguras=[2800, 6200],
        legenda="Tabela 15 - Guia das abas da planilha.",
    )
    documento.secao("Anexo B - Glossario das dimensoes de qualidade", 1)
    documento.tabela(
        ["Dimensao", "O que mede", "Exemplo de problema"],
        [
            ["Completude", "Proporcao de campos preenchidos", "CPF em branco no cadastro"],
            ["Unicidade", "Ausencia de repeticao indevida", "Mesma matricula em dois registros"],
            ["Validade", "Formato e dominio corretos", "Data '32/13/2024' ou CPF com digito errado"],
            ["Consistencia", "Coerencia entre campos", "Data de encerramento anterior a de inicio"],
            ["Padronizacao", "Escrita uniforme", "'SAO PAULO', 'Sao Paulo' e 'S. Paulo'"],
            ["Acuracia", "Plausibilidade dos valores", "Salario de R$ 9.999.999,00"],
            ["Atualidade", "Idade da informacao", "Base cujo registro mais novo tem tres anos"],
        ],
        larguras=[1800, 3400, 3800],
        legenda="Tabela 16 - Definicao das dimensoes usadas na analise.",
    )
