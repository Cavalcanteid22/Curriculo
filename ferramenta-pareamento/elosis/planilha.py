# -*- coding: utf-8 -*-
"""
Geração da planilha de resultados (ELO-SIS).

Produz um arquivo Excel único, com abas correspondentes a cada etapa do fluxo,
em que cada registro das bases nativas recebe:

  - classificação por cor — verde para registros sem inconsistência, amarelo
    para prováveis inconsistências que exigem verificação manual e vermelho
    para inconsistências reais;
  - colunas finais com descrição do problema, campos afetados, recomendação de
    correção na base nativa, justificativa técnico-normativa e orientação
    dirigida à área técnica responsável pela investigação do caso.

A planilha é o instrumento de trabalho da equipe: por isso, cada aba traz
cabeçalho fixo, filtro automático e larguras de coluna ajustadas.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .pareamento import NAO_PAREADO, PAREADO, REVISAO_MANUAL
from .perfis import ROTULOS_CANONICOS
from .pipeline import ResultadoExecucao
from .qualidade import (AMARELO, SIGNIFICADO_CLASSIFICACAO, VERDE, VERMELHO,
                        rotulo_do_tipo)
from .seguranca import Pseudonimizador

# --------------------------------------------------------------------------- #
# Paleta
# --------------------------------------------------------------------------- #

PREENCHIMENTO = {
    VERDE: PatternFill("solid", fgColor="C6EFCE"),
    AMARELO: PatternFill("solid", fgColor="FFEB9C"),
    VERMELHO: PatternFill("solid", fgColor="FFC7CE"),
}
FONTE_CLASSIFICACAO = {
    VERDE: Font(color="006100"),
    AMARELO: Font(color="9C5700"),
    VERMELHO: Font(color="9C0006"),
}

AZUL_INSTITUCIONAL = "1F4E79"
CINZA_CLARO = "F2F2F2"

FONTE_CABECALHO = Font(bold=True, color="FFFFFF", size=10)
PREENCHIMENTO_CABECALHO = PatternFill("solid", fgColor=AZUL_INSTITUCIONAL)
PREENCHIMENTO_SUBTITULO = PatternFill("solid", fgColor=CINZA_CLARO)
ALINHAMENTO_CABECALHO = Alignment(horizontal="center", vertical="center",
                                  wrap_text=True)
BORDA_FINA = Border(*[Side(style="thin", color="BFBFBF")] * 4)

ALINHAMENTO_TOPO = Alignment(vertical="top")
ALINHAMENTO_QUEBRA = Alignment(vertical="top", wrap_text=True)
ALINHAMENTO_CENTRO = Alignment(horizontal="center", vertical="top")

LARGURA_MAXIMA = 62
LARGURA_MINIMA = 9

# Acima deste número de células, as bordas das células de dados deixam de ser
# aplicadas. São puramente cosméticas e, nessa ordem de grandeza, custam mais
# tempo de geração e tamanho de arquivo do que agregam em legibilidade.
LIMITE_CELULAS_COM_BORDA = 120_000

# Colunas analíticas acrescentadas ao final de cada base.
COLUNAS_ANALITICAS = [
    "CLASSIFICACAO", "N_INCONSISTENCIAS", "GRAVIDADE_MAXIMA", "CAMPOS_AFETADOS",
    "DESCRICAO_DAS_INCONSISTENCIAS", "DIMENSOES_DE_QUALIDADE_AFETADAS",
    "JUSTIFICATIVA_TECNICA", "RECOMENDACAO_DE_CORRECAO",
    "SUGESTAO_PARA_A_AREA_TECNICA", "PRIORIDADE", "SITUACAO_NO_PAREAMENTO",
    "BASES_RELACIONADAS", "OBSERVACOES_COMPLEMENTARES",
]


def _texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and pd.isna(valor):
        return ""
    return str(valor)


# --------------------------------------------------------------------------- #
# Formatação de abas
# --------------------------------------------------------------------------- #

def _escrever_quadro(aba: Worksheet, linhas: list[dict] | pd.DataFrame,
                     titulo: str = "", subtitulo: str = "",
                     congelar: str | None = None,
                     larguras: dict[str, int] | None = None) -> int:
    """Escreve um conjunto de linhas com cabeçalho formatado. Devolve a 1ª linha de dados."""
    if isinstance(linhas, pd.DataFrame):
        colunas = list(linhas.columns)
        registros = linhas.to_dict("records")
    else:
        registros = list(linhas)
        # União ordenada das chaves: registros heterogêneos (por exemplo, pares
        # de relacionamentos diferentes) perderiam colunas se o cabeçalho fosse
        # extraído apenas do primeiro deles.
        colunas = list(dict.fromkeys(
            chave for registro in registros for chave in registro))

    linha_atual = 1
    if titulo:
        aba.cell(row=1, column=1, value=titulo).font = Font(bold=True, size=13,
                                                            color=AZUL_INSTITUCIONAL)
        linha_atual = 2
    if subtitulo:
        celula = aba.cell(row=linha_atual, column=1, value=subtitulo)
        celula.font = Font(italic=True, size=9, color="595959")
        celula.alignment = Alignment(wrap_text=True, vertical="top")
        aba.row_dimensions[linha_atual].height = 30
        linha_atual += 1
    if titulo or subtitulo:
        linha_atual += 1

    if not colunas:
        aba.cell(row=linha_atual, column=1,
                 value="Não há registros a apresentar nesta aba.").font = Font(
            italic=True, color="808080")
        return linha_atual

    linha_cabecalho = linha_atual
    for indice, coluna in enumerate(colunas, start=1):
        celula = aba.cell(row=linha_cabecalho, column=indice,
                          value=coluna.replace("_", " "))
        celula.font = FONTE_CABECALHO
        celula.fill = PREENCHIMENTO_CABECALHO
        celula.alignment = ALINHAMENTO_CABECALHO
        celula.border = BORDA_FINA
    aba.row_dimensions[linha_cabecalho].height = 32

    total_celulas = len(registros) * len(colunas)
    aplicar_borda = total_celulas <= LIMITE_CELULAS_COM_BORDA
    # Em abas muito extensas, o alinhamento é aplicado apenas às colunas de
    # texto longo, que dele dependem para permanecer legíveis. Aplicá-lo a
    # todas as células dobraria o tempo de geração sem ganho perceptível.
    alinhar_tudo = total_celulas <= LIMITE_CELULAS_COM_BORDA

    # As colunas que comportam texto longo são decididas uma única vez, pela
    # amostra, em vez de medidas célula a célula.
    colunas_com_quebra = _colunas_de_texto_longo(colunas, registros)
    indices_com_quebra = [i for i, c in enumerate(colunas, start=1)
                          if c in colunas_com_quebra]

    # A escrita em bloco é sensivelmente mais rápida do que a atribuição
    # célula a célula, e é por ela que passam todas as linhas de dados.
    for registro in registros:
        aba.append([_converter(registro.get(coluna, "")) for coluna in colunas])

    primeira_linha = linha_cabecalho + 1
    ultima_linha = linha_cabecalho + len(registros)
    if alinhar_tudo:
        for linha_planilha in aba.iter_rows(min_row=primeira_linha,
                                            max_row=ultima_linha,
                                            min_col=1,
                                            max_col=len(colunas)):
            for indice, celula in enumerate(linha_planilha, start=1):
                celula.alignment = (ALINHAMENTO_QUEBRA
                                    if indice in indices_com_quebra
                                    else ALINHAMENTO_TOPO)
                if aplicar_borda:
                    celula.border = BORDA_FINA
    elif indices_com_quebra:
        for indice in indices_com_quebra:
            for linha_planilha in range(primeira_linha, ultima_linha + 1):
                aba.cell(row=linha_planilha, column=indice).alignment = (
                    ALINHAMENTO_QUEBRA)

    _ajustar_larguras(aba, colunas, registros, linha_cabecalho, larguras)
    if registros:
        aba.auto_filter.ref = (
            f"A{linha_cabecalho}:"
            f"{get_column_letter(len(colunas))}{linha_cabecalho + len(registros)}")
    aba.freeze_panes = congelar or f"A{linha_cabecalho + 1}"
    return linha_cabecalho + 1


def _colunas_de_texto_longo(colunas: list[str], registros: list[dict],
                            amostra: int = 300) -> set[str]:
    """Colunas cujos valores justificam quebra automática de linha."""
    longas = set()
    for registro in registros[:amostra]:
        for coluna in colunas:
            if coluna in longas:
                continue
            valor = registro.get(coluna, "")
            if isinstance(valor, str) and len(valor) > 45:
                longas.add(coluna)
    return longas


def _converter(valor):
    """Números permanecem numéricos na planilha; o restante vira texto."""
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return None if pd.isna(valor) else valor
    return _texto(valor)


def _ajustar_larguras(aba: Worksheet, colunas: list[str], registros: list[dict],
                      linha_cabecalho: int, larguras: dict[str, int] | None) -> None:
    larguras = larguras or {}
    amostra = registros[:400]
    for indice, coluna in enumerate(colunas, start=1):
        if coluna in larguras:
            aba.column_dimensions[get_column_letter(indice)].width = larguras[coluna]
            continue
        maior = len(str(coluna))
        for registro in amostra:
            maior = max(maior, len(_texto(registro.get(coluna, ""))))
        aba.column_dimensions[get_column_letter(indice)].width = max(
            LARGURA_MINIMA, min(LARGURA_MAXIMA, maior + 2))


# --------------------------------------------------------------------------- #
# Colunas analíticas das bases
# --------------------------------------------------------------------------- #

_PRIORIDADE = {
    VERMELHO: "1 - Alta (corrigir na base nativa)",
    AMARELO: "2 - Média (verificar manualmente)",
    VERDE: "3 - Sem pendência",
}


def _montar_colunas_analiticas(resultado: ResultadoExecucao,
                               sigla: str) -> pd.DataFrame:
    """Consolida, por linha, tudo o que a análise apurou sobre o registro."""
    qualidade = resultado.qualidade[sigla]
    quadro = resultado.bases[sigla]
    por_linha = qualidade.achados_por_linha()
    situacao = _situacao_no_pareamento(resultado, sigla)

    dados = []
    for linha in quadro.index:
        achados = por_linha.get(linha, [])
        classificacao = (qualidade.classificacao_linhas.at[linha]
                         if qualidade.classificacao_linhas is not None else VERDE)
        graves = [a for a in achados if a.gravidade == VERMELHO]
        suspeitos = [a for a in achados if a.gravidade == AMARELO]
        ordenados = graves + suspeitos

        campos = sorted({ROTULOS_CANONICOS.get(a.variavel, a.variavel)
                         for a in ordenados})
        dimensoes = sorted({a.dimensao for a in ordenados})
        pareamento = situacao.get(linha, {})

        if not achados:
            descricao = ("Nenhuma inconsistência detectada nas regras aplicadas "
                         "(completude de campos obrigatórios, domínio e formato "
                         "das variáveis, coerência entre datas e duplicidade).")
            recomendacao = ("Nenhuma ação corretiva necessária. Registro apto "
                            "ao uso analítico e ao relacionamento de bases.")
            sugestao = ""
            justificativa = ""
        else:
            descricao = " | ".join(f"({i}) {a.descricao}"
                                   for i, a in enumerate(ordenados, start=1))
            recomendacao = " | ".join(
                dict.fromkeys(f"({i}) {a.recomendacao}"
                              for i, a in enumerate(ordenados, start=1)))
            justificativa = " | ".join(
                dict.fromkeys(f"({i}) {a.justificativa}"
                              for i, a in enumerate(ordenados, start=1)))
            sugestao = _sugestao_area_tecnica(classificacao, ordenados,
                                              qualidade.perfil)

        dados.append({
            "CLASSIFICACAO": classificacao,
            "N_INCONSISTENCIAS": len(achados),
            "GRAVIDADE_MAXIMA": (VERMELHO if graves else
                                 AMARELO if suspeitos else "SEM PENDENCIA"),
            "CAMPOS_AFETADOS": "; ".join(campos),
            "DESCRICAO_DAS_INCONSISTENCIAS": descricao,
            "DIMENSOES_DE_QUALIDADE_AFETADAS": "; ".join(dimensoes),
            "JUSTIFICATIVA_TECNICA": justificativa,
            "RECOMENDACAO_DE_CORRECAO": recomendacao,
            "SUGESTAO_PARA_A_AREA_TECNICA": sugestao,
            "PRIORIDADE": _PRIORIDADE[classificacao],
            "SITUACAO_NO_PAREAMENTO": pareamento.get("situacao",
                                                     "Não pareado com outras bases"),
            "BASES_RELACIONADAS": pareamento.get("bases", ""),
            "OBSERVACOES_COMPLEMENTARES": pareamento.get("observacao", ""),
        })
    return pd.DataFrame(dados, index=quadro.index)


def _sugestao_area_tecnica(classificacao: str, achados, perfil) -> str:
    """Orientação prática, dirigida a quem vai investigar o caso."""
    tipos = {a.tipo for a in achados}
    partes = []

    if classificacao == VERMELHO:
        partes.append(
            f"Encaminhar à área técnica responsável pelo {perfil.sigla} para "
            f"correção no sistema, com retorno do documento-fonte "
            f"({perfil.instrumento}).")
    else:
        partes.append(
            "Submeter à conferência de um técnico antes de utilizar o registro "
            "em análise ou em relacionamento de bases.")

    if any(t.startswith("DUPLICATA") for t in tipos):
        partes.append(
            "Há indício de duplicidade: confrontar com os demais registros do "
            "mesmo grupo na aba de duplicidades antes de qualquer exclusão, "
            "consolidando no registro mantido a informação mais completa.")
    if "CAMPO_OBRIGATORIO_EM_BRANCO" in tipos:
        partes.append(
            "Campo obrigatório não preenchido: acionar o estabelecimento "
            "notificador para recuperação do dado, conforme fluxo de retorno "
            "de inconsistências da vigilância.")
    if any("DATA" in t or t.endswith("ANTERIOR_AO_NASCIMENTO") for t in tipos):
        partes.append(
            "Divergência entre datas: verificar inversão entre dia e mês, erro "
            "de ano e data do relógio da estação de digitação.")
    if "RESIDENCIA_FORA_DO_MUNICIPIO" in tipos:
        partes.append(
            "Residente de outro município: avaliar a transferência do registro "
            "ao município de residência, conforme pactuação vigente.")
    if any(t in tipos for t in ("NOME_INVALIDO", "CAMPO_OBRIGATORIO_IGNORADO")):
        partes.append(
            "A baixa qualidade do campo nominal compromete o pareamento: "
            "priorizar a correção, pois dela depende a recuperação de "
            "informação por relacionamento com as demais bases.")
    return " ".join(partes)


def _situacao_no_pareamento(resultado: ResultadoExecucao,
                            sigla: str) -> dict[int, dict]:
    """Para cada linha, em que relacionamentos ela foi pareada."""
    situacao: dict[int, dict] = defaultdict(
        lambda: {"pareados": [], "revisao": []})

    for pareamento in resultado.pareamentos:
        for par in pareamento.pares:
            if pareamento.base_a == sigla:
                linha, contraparte = par.linha_a, pareamento.base_b
            elif pareamento.base_b == sigla:
                linha, contraparte = par.linha_b, pareamento.base_a
            else:
                continue
            destino = ("pareados" if par.classificacao == PAREADO else "revisao")
            # Um par determinístico de escore 1,000 pode ir à revisão por
            # chave ambígua ou por divergência em variável auxiliar. Sem dizer
            # qual foi o motivo, a planilha deixa o técnico sem saber o que
            # conferir.
            motivo = ""
            if par.classificacao == REVISAO_MANUAL:
                if par.divergencias:
                    motivo = f"; motivo: divergência em {'; '.join(par.divergencias)}"
                elif "mesma chave" in par.justificativa:
                    motivo = ("; motivo: mais de um registro da outra base "
                              "compartilha esta chave")
                else:
                    motivo = "; motivo: escore na faixa de revisão manual"
            situacao[linha][destino].append(
                f"{contraparte} (escore {par.escore:.3f}, {par.regra}{motivo})")

    consolidada: dict[int, dict] = {}
    for linha, dados in situacao.items():
        if dados["pareados"]:
            texto = "Pareado"
            observacao = ("Registro relacionado a outra(s) base(s). A "
                          "informação faltante neste registro pode ser "
                          "recuperada a partir do par identificado.")
        elif dados["revisao"]:
            texto = "Par candidato em revisão manual"
            observacao = ("Há par candidato com escore na faixa de revisão. "
                          "Confrontar os documentos-fonte para confirmar ou "
                          "descartar a correspondência.")
        else:
            continue
        consolidada[linha] = {
            "situacao": texto,
            "bases": "; ".join(dados["pareados"] + dados["revisao"]),
            "observacao": observacao,
        }
    return consolidada


# --------------------------------------------------------------------------- #
# Abas
# --------------------------------------------------------------------------- #

def _aba_leia_me(livro: Workbook, resultado: ResultadoExecucao) -> None:
    aba = livro.create_sheet("00_LEIA-ME")
    configuracao = resultado.configuracao

    conteudo = [
        ("ELO-SIS — Qualificação, Harmonização e Pareamento de Bases dos "
         "Sistemas de Informação em Saúde", "titulo"),
        ("Produto técnico do projeto de intervenção “O Desafio da "
         "Interoperabilidade em Sistemas: proposta para linkage entre SIM, "
         "SINAN e SINASC”.", "subtitulo"),
        ("", ""),
        ("1. O QUE ESTE ARQUIVO CONTÉM", "secao"),
        ("Cada aba corresponde a uma etapa da análise. As abas iniciadas por "
         "10 trazem as bases nativas, registro a registro, com as colunas "
         "analíticas acrescentadas ao final. As demais abas consolidam a "
         "qualificação, as duplicidades, a harmonização, os pareamentos e as "
         "recomendações.", "texto"),
        ("", ""),
        ("2. COMO LER AS CORES DAS LINHAS", "secao"),
        (f"VERDE — {SIGNIFICADO_CLASSIFICACAO[VERDE]}", "verde"),
        (f"AMARELO — {SIGNIFICADO_CLASSIFICACAO[AMARELO]}", "amarelo"),
        (f"VERMELHO — {SIGNIFICADO_CLASSIFICACAO[VERMELHO]}", "vermelho"),
        ("A cor é atribuída pela regra da gravidade máxima: basta uma "
         "inconsistência real para que a linha seja vermelha; na ausência "
         "desta, uma inconsistência provável a torna amarela.", "texto"),
        ("", ""),
        ("3. COMO USAR NA ROTINA", "secao"),
        ("Passo 1 — Abrir a aba 01_RESUMO_EXECUTIVO e observar o escore de "
         "qualidade de cada base e a distribuição das cores.", "texto"),
        ("Passo 2 — Nas abas das bases, filtrar a coluna CLASSIFICACAO por "
         "VERMELHO e trabalhar as correções por ordem de PRIORIDADE.", "texto"),
        ("Passo 3 — Filtrar por AMARELO e distribuir a verificação manual "
         "entre os técnicos, usando a coluna SUGESTAO_PARA_A_AREA_TECNICA.",
         "texto"),
        ("Passo 4 — Conferir a aba 42_PARES_EM_REVISAO_MANUAL: é onde se "
         "concentram os pares que a rotina não pôde decidir sozinha e onde o "
         "trabalho humano tem maior rendimento.", "texto"),
        ("Passo 5 — Aplicar as correções nos sistemas de origem e reexecutar a "
         "ferramenta para medir a evolução dos indicadores.", "texto"),
        ("", ""),
        ("4. PARÂMETROS DESTA EXECUÇÃO", "secao"),
        (f"Data e hora: {resultado.momento.strftime('%d/%m/%Y às %H:%M:%S')}",
         "texto"),
        (f"Limiar de pareamento: {configuracao.limiar_pareamento:.2f} — pares "
         f"com escore igual ou superior são considerados pareados.", "texto"),
        (f"Limiar de revisão manual: {configuracao.limiar_revisao:.2f} — pares "
         f"entre este valor e o limiar de pareamento são encaminhados à "
         f"conferência humana.", "texto"),
        (f"Limiar de duplicidade provável: {configuracao.limiar_duplicidade:.2f}",
         "texto"),
        (f"Ano de referência: {configuracao.ano_referencia}", "texto"),
        (f"População de referência: {configuracao.populacao_referencia:,}"
         .replace(",", "."), "texto"),
        (f"Tempo de execução: {resultado.tempo_total:.1f} segundos", "texto"),
        ("", ""),
        ("5. PROTEÇÃO DE DADOS", "secao"),
        ("O processamento foi integralmente local. A ferramenta opera em modo "
         "cofre: as primitivas de conexão do interpretador são substituídas de "
         "modo que qualquer tentativa de envio de dados para fora da estação "
         "falhe e fique registrada na trilha de auditoria. Nenhum dado "
         "identificável é transmitido para serviços em nuvem.", "texto"),
        ("Tratamento fundamentado na Lei nº 13.709/2018 (LGPD), art. 7º, III e "
         "art. 11, II, “b” — execução de políticas públicas por órgão da "
         "administração pública, restrita à finalidade declarada no projeto.",
         "texto"),
        ("Este arquivo contém dados pessoais sensíveis. Sua guarda, circulação "
         "e descarte devem seguir as normas institucionais de segurança da "
         "informação da Secretaria Municipal da Saúde.", "alerta"),
    ]

    for indice, (texto, estilo) in enumerate(conteudo, start=1):
        celula = aba.cell(row=indice, column=1, value=texto)
        celula.alignment = Alignment(wrap_text=True, vertical="top")
        if estilo == "titulo":
            celula.font = Font(bold=True, size=14, color=AZUL_INSTITUCIONAL)
        elif estilo == "subtitulo":
            celula.font = Font(italic=True, size=10, color="595959")
        elif estilo == "secao":
            celula.font = Font(bold=True, size=11, color=AZUL_INSTITUCIONAL)
            celula.fill = PREENCHIMENTO_SUBTITULO
        elif estilo in PREENCHIMENTO_POR_ESTILO:
            celula.fill = PREENCHIMENTO_POR_ESTILO[estilo]
            celula.font = FONTE_POR_ESTILO[estilo]
        elif estilo == "alerta":
            celula.font = Font(bold=True, color="9C0006")
        else:
            celula.font = Font(size=10)
        aba.row_dimensions[indice].height = max(15, 15 * (len(texto) // 95 + 1))
    aba.column_dimensions["A"].width = 118


PREENCHIMENTO_POR_ESTILO = {"verde": PREENCHIMENTO[VERDE],
                            "amarelo": PREENCHIMENTO[AMARELO],
                            "vermelho": PREENCHIMENTO[VERMELHO]}
FONTE_POR_ESTILO = {"verde": FONTE_CLASSIFICACAO[VERDE],
                    "amarelo": FONTE_CLASSIFICACAO[AMARELO],
                    "vermelho": FONTE_CLASSIFICACAO[VERMELHO]}


def _aba_base(livro: Workbook, resultado: ResultadoExecucao, sigla: str,
              ordem: int, pseudonimizador: Pseudonimizador | None) -> None:
    """Base nativa completa, com colunas analíticas e linhas coloridas."""
    quadro = resultado.bases[sigla].copy()
    qualidade = resultado.qualidade[sigla]
    analiticas = _montar_colunas_analiticas(resultado, sigla)

    if pseudonimizador:
        quadro = _pseudonimizar(quadro, qualidade.mapeamento, pseudonimizador)

    completo = pd.concat([quadro, analiticas], axis=1)
    completo.insert(0, "LINHA_NA_BASE", [i + 2 for i in range(len(completo))])

    restricao = ""
    if resultado.configuracao.somente_pendencias_nas_bases:
        completo = completo[completo["CLASSIFICACAO"] != VERDE]
        restricao = (" ATENÇÃO: esta aba foi restringida aos registros com "
                     "pendência, conforme a opção escolhida na execução. Os "
                     "registros sem inconsistência não constam desta aba; as "
                     "contagens acima referem-se à base completa.")

    aba = livro.create_sheet(f"{10 + ordem}_BASE_{sigla}"[:31])
    contagem = qualidade.contagem_por_classificacao()
    subtitulo = (
        f"{qualidade.perfil.nome_extenso} — arquivo "
        f"{resultado.arquivos_de_origem.get(sigla, '')} | "
        f"{qualidade.total_registros} registros | escore de qualidade "
        f"{qualidade.escore_global} de 100 | verdes: {contagem[VERDE]}, "
        f"amarelas: {contagem[AMARELO]}, vermelhas: {contagem[VERMELHO]}. "
        f"As colunas nativas são preservadas sem alteração; as colunas "
        f"analíticas foram acrescentadas ao final.{restricao}")

    primeira = _escrever_quadro(
        aba, completo, titulo=f"Base {sigla} — registros e análise",
        subtitulo=subtitulo,
        larguras={"DESCRICAO_DAS_INCONSISTENCIAS": 60,
                  "RECOMENDACAO_DE_CORRECAO": 58,
                  "JUSTIFICATIVA_TECNICA": 58,
                  "SUGESTAO_PARA_A_AREA_TECNICA": 58,
                  "BASES_RELACIONADAS": 40,
                  "OBSERVACOES_COMPLEMENTARES": 45})

    # Pintura das linhas conforme a classificação.
    #
    # O acesso é feito por `aba.cell(...)`, e não por `aba[n]`. A indexação de
    # linha do openpyxl recalcula a largura da planilha a cada chamada,
    # percorrendo todas as células já escritas: o custo cresce com o quadrado
    # do número de linhas. Numa base anual completa isso significava mais de
    # uma hora por aba — o suficiente para inviabilizar o produto na escala
    # para a qual ele foi feito.
    n_colunas = len(completo.columns)
    classificacoes = completo["CLASSIFICACAO"].tolist()
    for deslocamento, classificacao in enumerate(classificacoes):
        preenchimento = PREENCHIMENTO.get(classificacao)
        if not preenchimento:
            continue
        numero_linha = primeira + deslocamento
        for coluna in range(1, n_colunas + 1):
            aba.cell(row=numero_linha, column=coluna).fill = preenchimento


def _pseudonimizar(quadro: pd.DataFrame, mapeamento: dict[str, str],
                   pseudonimizador: Pseudonimizador) -> pd.DataFrame:
    """Substitui identificadores diretos por pseudônimos estáveis."""
    copia = quadro.copy()
    for canonica in ("NOME", "NOME_MAE", "NOME_PAI"):
        coluna = mapeamento.get(canonica)
        if coluna and coluna in copia.columns:
            copia[coluna] = copia[coluna].map(pseudonimizador.pseudonimo)
    for canonica in ("CPF", "CNS"):
        coluna = mapeamento.get(canonica)
        if coluna and coluna in copia.columns:
            copia[coluna] = copia[coluna].map(
                lambda v: pseudonimizador.mascarar(v, 3))
    for canonica in ("LOGRADOURO", "CEP"):
        coluna = mapeamento.get(canonica)
        if coluna and coluna in copia.columns:
            copia[coluna] = copia[coluna].map(
                lambda v: pseudonimizador.mascarar(v, 2))
    return copia


def _aba_resumo(livro: Workbook, resultado: ResultadoExecucao) -> None:
    aba = livro.create_sheet("01_RESUMO_EXECUTIVO")
    linhas = resultado.resumo_executivo()
    primeira = _escrever_quadro(
        aba, linhas, titulo="Resumo executivo da análise",
        subtitulo=("Visão consolidada por base. O escore de qualidade pondera "
                   "completude (0,35), acurácia (0,35), consistência (0,20) e "
                   "oportunidade (0,10), conforme a priorização declarada no "
                   "projeto para acurácia, completude e consistência."))

    for deslocamento in range(len(linhas)):
        for coluna, cor in (("LINHAS_VERDES", VERDE), ("LINHAS_AMARELAS", AMARELO),
                            ("LINHAS_VERMELHAS", VERMELHO)):
            if coluna in linhas[0]:
                indice = list(linhas[0]).index(coluna) + 1
                celula = aba.cell(row=primeira + deslocamento, column=indice)
                celula.fill = PREENCHIMENTO[cor]
                celula.font = FONTE_CLASSIFICACAO[cor]

    proxima = primeira + len(linhas) + 2
    aba.cell(row=proxima, column=1,
             value="Pareamentos realizados").font = Font(
        bold=True, size=12, color=AZUL_INSTITUCIONAL)
    resumos = [p.resumo() for p in resultado.pareamentos]
    if resumos:
        colunas = list(resumos[0])
        for indice, coluna in enumerate(colunas, start=1):
            celula = aba.cell(row=proxima + 1, column=indice,
                              value=coluna.replace("_", " "))
            celula.font = FONTE_CABECALHO
            celula.fill = PREENCHIMENTO_CABECALHO
            celula.alignment = ALINHAMENTO_CABECALHO
        for deslocamento, linha in enumerate(resumos, start=2):
            for indice, coluna in enumerate(colunas, start=1):
                aba.cell(row=proxima + deslocamento, column=indice,
                         value=_converter(linha.get(coluna, "")))

    if resultado.avisos:
        linha_avisos = proxima + len(resumos) + 3
        aba.cell(row=linha_avisos, column=1, value="Avisos da execução").font = Font(
            bold=True, color="9C5700")
        for deslocamento, aviso in enumerate(resultado.avisos, start=1):
            aba.cell(row=linha_avisos + deslocamento, column=1, value=aviso)


def _aba_simples(livro: Workbook, nome: str, linhas, titulo: str,
                 subtitulo: str = "", larguras: dict | None = None) -> None:
    aba = livro.create_sheet(nome[:31])
    _escrever_quadro(aba, linhas, titulo=titulo, subtitulo=subtitulo,
                     larguras=larguras)


def _aba_com_cores(livro: Workbook, nome: str, linhas: list[dict], titulo: str,
                   subtitulo: str, coluna_cor: str,
                   mapa_cores: dict[str, str],
                   larguras: dict | None = None) -> None:
    aba = livro.create_sheet(nome[:31])
    primeira = _escrever_quadro(aba, linhas, titulo=titulo, subtitulo=subtitulo,
                                larguras=larguras)
    if not linhas:
        return
    colunas = list(linhas[0])
    if coluna_cor not in colunas:
        return
    for deslocamento, linha in enumerate(linhas):
        cor = mapa_cores.get(str(linha.get(coluna_cor, "")))
        preenchimento = PREENCHIMENTO.get(cor)
        if not preenchimento:
            continue
        for coluna in range(1, len(colunas) + 1):
            aba.cell(row=primeira + deslocamento, column=coluna).fill = preenchimento


# --------------------------------------------------------------------------- #
# Montagem das abas de pareamento
# --------------------------------------------------------------------------- #

def _linhas_de_pares(resultado: ResultadoExecucao, classificacoes: set[str],
                     estagios: set[str] | None = None) -> list[dict]:
    """Detalha cada par com os identificadores e as variáveis de decisão."""
    from .harmonizacao import PREFIXO_HARMONIZADO
    saida = []
    for pareamento in resultado.pareamentos:
        quadro_a = resultado.bases[pareamento.base_a]
        quadro_b = resultado.bases[pareamento.base_b]
        mapa_a = resultado.qualidade[pareamento.base_a].mapeamento
        mapa_b = resultado.qualidade[pareamento.base_b].mapeamento

        def valor(quadro, mapa, linha, canonica):
            coluna = mapa.get(canonica)
            if not coluna or coluna not in quadro.columns:
                return ""
            return _texto(quadro[coluna].at[linha])

        for par in pareamento.pares:
            if par.classificacao not in classificacoes:
                continue
            if estagios and par.estagio not in estagios:
                continue
            classificacao_a = resultado.qualidade[pareamento.base_a] \
                .classificacao_linhas
            classificacao_b = resultado.qualidade[pareamento.base_b] \
                .classificacao_linhas
            saida.append({
                "RELACIONAMENTO": pareamento.rotulo,
                "ESTAGIO": par.estagio,
                "REGRA_APLICADA": par.regra,
                "ESCORE": round(par.escore, 4),
                "CLASSIFICACAO_DO_PAR": par.classificacao,
                "BASE_A": pareamento.base_a,
                "LINHA_A": par.linha_a + 2,
                "ID_A": valor(quadro_a, mapa_a, par.linha_a, "NUMERO_REGISTRO"),
                "NOME_A": valor(quadro_a, mapa_a, par.linha_a, "NOME"),
                "MAE_A": valor(quadro_a, mapa_a, par.linha_a, "NOME_MAE"),
                "NASCIMENTO_A": valor(quadro_a, mapa_a, par.linha_a,
                                      "DATA_NASCIMENTO"),
                "EVENTO_A": valor(quadro_a, mapa_a, par.linha_a, "DATA_EVENTO"),
                "BASE_B": pareamento.base_b,
                "LINHA_B": par.linha_b + 2,
                "ID_B": valor(quadro_b, mapa_b, par.linha_b, "NUMERO_REGISTRO"),
                "NOME_B": valor(quadro_b, mapa_b, par.linha_b, "NOME"),
                "MAE_B": valor(quadro_b, mapa_b, par.linha_b, "NOME_MAE"),
                "NASCIMENTO_B": valor(quadro_b, mapa_b, par.linha_b,
                                      "DATA_NASCIMENTO"),
                "EVENTO_B": valor(quadro_b, mapa_b, par.linha_b, "DATA_EVENTO"),
                "SIMILARIDADE_POR_CAMPO": "; ".join(
                    f"{ROTULOS_CANONICOS.get(k, k)}: {v:.3f}"
                    for k, v in par.escores_por_campo.items()),
                "DIVERGENCIAS_OBSERVADAS": "; ".join(par.divergencias) or "Nenhuma",
                "QUALIDADE_DO_REGISTRO_A": (classificacao_a.at[par.linha_a]
                                            if classificacao_a is not None else ""),
                "QUALIDADE_DO_REGISTRO_B": (classificacao_b.at[par.linha_b]
                                            if classificacao_b is not None else ""),
                "JUSTIFICATIVA": par.justificativa,
                "RECOMENDACAO": _recomendacao_do_par(par),
            })
    return saida


def _recomendacao_do_par(par) -> str:
    if par.classificacao == PAREADO and par.estagio == "Determinístico":
        return ("Par aceito automaticamente. Utilizar para recuperar informação "
                "faltante e para compor o indicador que motivou o relacionamento.")
    if par.classificacao == PAREADO:
        return ("Par aceito pelo escore de similaridade. Recomenda-se conferência "
                "por amostragem, conforme rotina de controle de qualidade do setor.")
    return ("Conferência manual obrigatória: confrontar os documentos-fonte dos "
            "dois registros. Confirmando-se a identidade, registrar a decisão e, "
            "sempre que possível, corrigir na base nativa o campo que impediu o "
            "pareamento automático — é essa correção que evita a reincidência do "
            "problema nas próximas execuções.")


def _linhas_nao_pareados(resultado: ResultadoExecucao) -> tuple[list[dict], dict]:
    """Lista os registros sem par que comportam ação corretiva.

    A distinção é a razão de ser desta aba. Um registro que não pareou por lhe
    faltarem as chaves é um problema de qualidade, corrigível na base nativa.
    Um registro cujas chaves estão completas e ainda assim não encontrou
    correspondente apenas indica que a pessoa não consta da outra base — o que
    é o resultado esperado para a maior parte dos registros e não enseja
    providência alguma.

    Listar os segundos produziria, em bases municipais completas, centenas de
    milhares de linhas sem uso, encobrindo justamente as que exigem ação. Eles
    são, por isso, contabilizados e reportados no subtítulo da aba.
    """
    saida: list[dict] = []
    omitidos: dict[str, int] = defaultdict(int)

    for pareamento in resultado.pareamentos:
        for sigla, linhas, contraparte in (
                (pareamento.base_a, pareamento.nao_pareados_a, pareamento.base_b),
                (pareamento.base_b, pareamento.nao_pareados_b, pareamento.base_a)):
            quadro = resultado.bases[sigla]
            mapa = resultado.qualidade[sigla].mapeamento
            classificacao = resultado.qualidade[sigla].classificacao_linhas
            for linha in linhas:
                motivo = _motivo_nao_pareamento(quadro, mapa, linha)
                if not motivo["acionavel"]:
                    omitidos[pareamento.rotulo] += 1
                    continue
                saida.append({
                    "RELACIONAMENTO": pareamento.rotulo,
                    "BASE_DE_ORIGEM": sigla,
                    "BASE_DE_DESTINO": contraparte,
                    "LINHA_NA_BASE": linha + 2,
                    "ID_DO_REGISTRO": _valor_seguro(quadro, mapa, linha,
                                                    "NUMERO_REGISTRO"),
                    "NOME": _valor_seguro(quadro, mapa, linha, "NOME"),
                    "NOME_DA_MAE": _valor_seguro(quadro, mapa, linha, "NOME_MAE"),
                    "DATA_NASCIMENTO": _valor_seguro(quadro, mapa, linha,
                                                     "DATA_NASCIMENTO"),
                    "QUALIDADE_DO_REGISTRO": (classificacao.at[linha]
                                              if classificacao is not None else ""),
                    "CHAVES_AUSENTES": motivo["chaves_ausentes"],
                    "MOTIVO_PROVAVEL": motivo["motivo"],
                    "RECOMENDACAO": motivo["recomendacao"],
                })
    return saida, dict(omitidos)


def _valor_seguro(quadro, mapa, linha, canonica) -> str:
    coluna = mapa.get(canonica)
    if not coluna or coluna not in quadro.columns:
        return ""
    return _texto(quadro[coluna].at[linha])


def _motivo_nao_pareamento(quadro, mapa, linha) -> dict:
    """Explica por que o registro não encontrou par — informação acionável."""
    from . import normalizacao as nz
    nome = nz.normalizar_nome(_valor_seguro(quadro, mapa, linha, "NOME"))
    mae = nz.normalizar_nome(_valor_seguro(quadro, mapa, linha, "NOME_MAE"))
    nascimento = nz.normalizar_data(_valor_seguro(quadro, mapa, linha,
                                                  "DATA_NASCIMENTO"))
    ausentes = [rotulo for valor, rotulo in
                ((nome, "nome"), (mae, "nome da mãe"),
                 (nascimento, "data de nascimento")) if not valor]

    if len(ausentes) >= 2:
        return {
            "acionavel": True,
            "chaves_ausentes": "; ".join(ausentes),
            "motivo": (f"Chaves de pareamento ausentes: {', '.join(ausentes)}. "
                       "Com menos de duas chaves preenchidas, não há base para "
                       "afirmar identidade."),
            "recomendacao": ("Recuperar os campos no documento-fonte. Enquanto "
                             "permanecerem em branco, o registro não pode ser "
                             "relacionado por nenhum método."),
        }
    if ausentes:
        return {
            "acionavel": True,
            "chaves_ausentes": ausentes[0],
            "motivo": (f"Chave ausente: {ausentes[0]}. O pareamento foi tentado "
                       "com as chaves remanescentes, sem sucesso."),
            "recomendacao": (f"Preencher o campo '{ausentes[0]}' na base nativa "
                             "eleva a sensibilidade do relacionamento em "
                             "execuções futuras."),
        }
    return {
        "acionavel": False,
        "chaves_ausentes": "",
        "motivo": ("Chaves preenchidas, sem correspondente na outra base acima "
                   "do limiar de similaridade. O mais provável é que a pessoa "
                   "realmente não conste da outra base."),
        "recomendacao": ("Nenhuma ação corretiva necessária quanto à qualidade "
                         "do registro."),
    }


def _linhas_duplicidades(resultado: ResultadoExecucao) -> list[dict]:
    saida = []
    for sigla, grupos in resultado.duplicidades.items():
        quadro = resultado.bases[sigla]
        mapeamento = resultado.qualidade[sigla].mapeamento
        for grupo in grupos:
            saida.extend(grupo.como_linhas(sigla, quadro, mapeamento))
    return saida


def _linhas_recomendacoes(resultado: ResultadoExecucao) -> list[dict]:
    """Recomendações consolidadas, por base e por tipo de problema."""
    saida = []
    for sigla, qualidade in resultado.qualidade.items():
        total = max(1, qualidade.total_registros)
        por_tipo: dict[str, list] = defaultdict(list)
        for achado in qualidade.achados:
            por_tipo[achado.tipo].append(achado)

        for tipo, achados in sorted(por_tipo.items(),
                                    key=lambda item: -len(item[1])):
            exemplar = achados[0]
            linhas_afetadas = sorted({a.linha + 2 for a in achados})
            variaveis = sorted({ROTULOS_CANONICOS.get(a.variavel, a.variavel)
                                for a in achados})
            saida.append({
                "BASE": sigla,
                "TIPO_DE_INCONSISTENCIA": tipo,
                "INCONSISTENCIA": rotulo_do_tipo(tipo),
                "GRAVIDADE": exemplar.gravidade,
                "DIMENSAO_DE_QUALIDADE": exemplar.dimensao,
                "VARIAVEIS_AFETADAS": "; ".join(variaveis),
                "OCORRENCIAS": len(achados),
                "REGISTROS_AFETADOS": len(linhas_afetadas),
                "PROPORCAO_DA_BASE_%": round(100 * len(linhas_afetadas) / total, 2),
                "DESCRICAO_DO_PROBLEMA": exemplar.descricao,
                "JUSTIFICATIVA_TECNICA": exemplar.justificativa,
                "RECOMENDACAO": exemplar.recomendacao,
                "ACAO_ESTRUTURANTE_SUGERIDA": _acao_estruturante(
                    tipo, len(linhas_afetadas) / total, qualidade.perfil),
                "PRIMEIRAS_LINHAS_AFETADAS": ", ".join(
                    map(str, linhas_afetadas[:25]))
                + (" ..." if len(linhas_afetadas) > 25 else ""),
            })
    return saida


def _acao_estruturante(tipo: str, proporcao: float, perfil) -> str:
    """Quando o problema é frequente, a correção caso a caso não basta.

    Madandola et al. (2023) deslocam parte da explicação dos problemas de
    qualidade da conduta individual do notificador para o desenho dos
    instrumentos de registro — o que justifica propor, acima de certo patamar
    de frequência, medidas que atuem sobre o processo, e não sobre o registro.
    """
    if proporcao < 0.02:
        return ("Frequência baixa: a correção individual dos registros é "
                "suficiente.")

    intensidade = ("muito frequente" if proporcao > 0.15
                   else "frequente" if proporcao > 0.05 else "recorrente")
    acoes = {
        "CAMPO_OBRIGATORIO_EM_BRANCO": (
            "Instituir crítica de preenchimento obrigatório na entrada de dados "
            "e incluir o campo no roteiro de conferência antes do envio do lote."),
        "CAMPO_OBRIGATORIO_IGNORADO": (
            "Revisar com os notificadores a diferença entre 'ignorado' e 'não "
            "coletado': o uso indiscriminado do código de ignorado produz "
            "completude aparente sem informação."),
        "NOME_INVALIDO": (
            "Padronizar a convenção de preenchimento de nomes, em especial para "
            "recém-nascidos ainda não nominados, e incluir a regra no "
            "procedimento operacional padrão do setor."),
        "DUPLICATA_TECNICA": (
            "Revisar o fluxo de importação de lotes: a repetição da chave "
            "primária indica reimportação do mesmo arquivo."),
        "DUPLICATA_DE_CONTEUDO": (
            "Implantar conferência de duplicidade antes da digitação e "
            "capacitar as equipes na busca prévia do registro."),
        "VALOR_FORA_DO_DOMINIO": (
            "Substituir campos de digitação livre por listas de seleção "
            "restritas ao domínio válido da variável."),
        "RESIDENCIA_FORA_DO_MUNICIPIO": (
            "Pactuar e operar rotina periódica de transferência de registros de "
            "não residentes aos municípios de residência."),
        "SEXO_IGNORADO": (
            "Incluir o campo sexo entre os itens de conferência obrigatória "
            "antes do encerramento do registro."),
    }
    especifica = acoes.get(tipo, (
        "Incluir a verificação deste item no roteiro de crítica das bases e "
        "pautá-lo na capacitação periódica dos notificadores."))
    return (f"Problema {intensidade} ({proporcao * 100:.1f}% dos registros): a "
            f"correção caso a caso é insuficiente. {especifica} Responsável "
            f"sugerido: área técnica gestora do {perfil.sigla} em articulação "
            f"com a SUIS.")


def _linhas_auditoria(resultado: ResultadoExecucao) -> list[dict]:
    trilha = resultado.trilha.como_dicionario()
    saida = []
    for arquivo in trilha["arquivos"]:
        saida.append({
            "CATEGORIA": "Arquivo processado",
            "ITEM": arquivo["arquivo"],
            "VALOR": f"{arquivo['registros']} registros | "
                     f"{arquivo['tamanho_bytes']:,} bytes".replace(",", "."),
            "DETALHE": f"SHA-256: {arquivo['sha256']}",
            "MOMENTO": arquivo["momento"],
        })
    for chave, valor in trilha["ambiente"].items():
        saida.append({"CATEGORIA": "Ambiente de execução",
                      "ITEM": chave.replace("_", " ").capitalize(),
                      "VALOR": _texto(valor), "DETALHE": "", "MOMENTO": ""})
    for chave, valor in trilha["parametros"].items():
        saida.append({"CATEGORIA": "Parâmetro",
                      "ITEM": chave.replace("_", " ").capitalize(),
                      "VALOR": _texto(valor), "DETALHE": "", "MOMENTO": ""})
    tentativas = trilha["tentativas_de_saida_de_rede_bloqueadas"]
    saida.append({
        "CATEGORIA": "Proteção de dados",
        "ITEM": "Tentativas de saída de rede bloqueadas",
        "VALOR": len(tentativas),
        "DETALHE": ("Nenhuma tentativa de envio de dados para fora da estação "
                    "foi registrada." if not tentativas
                    else "; ".join(t["destino"] for t in tentativas[:20])),
        "MOMENTO": "",
    })
    for evento in trilha["eventos"]:
        saida.append({"CATEGORIA": "Evento", "ITEM": evento["etapa"],
                      "VALOR": evento.get("detalhe", ""), "DETALHE": "",
                      "MOMENTO": evento["momento"]})
    return saida


# --------------------------------------------------------------------------- #
# Função principal
# --------------------------------------------------------------------------- #

def gerar_planilha(resultado: ResultadoExecucao,
                   caminho: Path | str | None = None) -> Path:
    """Monta e grava a planilha completa."""
    configuracao = resultado.configuracao
    if caminho is None:
        marca = resultado.momento.strftime("%Y%m%d_%H%M")
        caminho = Path(configuracao.diretorio_saida) / f"ELO-SIS_resultados_{marca}.xlsx"
    caminho = Path(caminho)

    pseudonimizador = Pseudonimizador() if configuracao.pseudonimizar_saida else None

    livro = Workbook()
    livro.remove(livro.active)

    _aba_leia_me(livro, resultado)
    _aba_resumo(livro, resultado)

    # --- Bases nativas -------------------------------------------------- #
    for ordem, sigla in enumerate(resultado.bases):
        _aba_base(livro, resultado, sigla, ordem, pseudonimizador)

    # --- Qualidade ------------------------------------------------------ #
    completude = [linha for q in resultado.qualidade.values() for linha in q.completude]
    _aba_com_cores(
        livro, "20_QUALIDADE_COMPLETUDE", completude,
        "Completude por variável e por base",
        ("Completude bruta considera qualquer preenchimento; completude útil "
         "desconta os códigos de ignorado, que produzem preenchimento sem "
         "informação. A classificação segue a escala usual de avaliação de "
         "bases do SUS (excelente ≥95%, bom ≥90%, regular ≥70%, ruim ≥50%)."),
        "CLASSIFICACAO",
        {"Excelente": VERDE, "Bom": VERDE, "Regular": AMARELO,
         "Ruim": VERMELHO, "Muito ruim": VERMELHO})

    acuracia = [linha for q in resultado.qualidade.values() for linha in q.acuracia]
    _aba_simples(livro, "21_QUALIDADE_ACURACIA", acuracia,
                 "Acurácia por variável e por base",
                 ("Proporção de registros com valores compatíveis com o domínio "
                  "e com as regras de formação da variável (Ghalavand et al., "
                  "2024; Madandola et al., 2023)."))

    consistencia = [linha for q in resultado.qualidade.values()
                    for linha in q.consistencia]
    _aba_simples(livro, "22_QUALIDADE_CONSISTENCIA", consistencia,
                 "Consistência interna — divergências lógicas por tipo",
                 ("Relações lógicas verificadas entre variáveis do mesmo "
                  "registro: ordem cronológica dos eventos, plausibilidade "
                  "biológica e coerência entre campos correlatos."))

    oportunidade = [linha for q in resultado.qualidade.values()
                    for linha in q.oportunidade]
    _aba_com_cores(
        livro, "23_QUALIDADE_OPORTUNIDADE", oportunidade,
        "Oportunidade do registro",
        ("Intervalo, em dias, entre a ocorrência do evento e o seu registro no "
         "sistema, confrontado com o prazo normativo de cada sistema. Registros "
         "digitados antes do evento são excluídos deste cálculo e tratados como "
         "inconsistência."),
        "CLASSIFICACAO",
        {"Excelente": VERDE, "Bom": VERDE, "Regular": AMARELO,
         "Ruim": VERMELHO, "Muito ruim": VERMELHO})

    achados = [a.como_dicionario(sigla)
               for sigla, q in resultado.qualidade.items() for a in q.achados]
    achados.sort(key=lambda linha: (linha["BASE"], linha["GRAVIDADE"] != VERMELHO,
                                    linha["LINHA"]))
    for linha in achados:
        linha["LINHA"] = linha["LINHA"] + 2
    _aba_com_cores(
        livro, "24_INCONSISTENCIAS", achados,
        "Inconsistências detectadas — lista completa",
        ("Uma linha por achado. A coluna LINHA indica a posição do registro na "
         "planilha da base correspondente, já considerando a linha de "
         "cabeçalho."),
        "GRAVIDADE", {VERMELHO: VERMELHO, AMARELO: AMARELO},
        larguras={"DESCRICAO": 58, "JUSTIFICATIVA": 58, "RECOMENDACAO": 58})

    duplicidades = _linhas_duplicidades(resultado)
    _aba_com_cores(
        livro, "25_DUPLICIDADES", duplicidades,
        "Duplicidades identificadas",
        ("Três fenômenos distintos: duplicata técnica (mesma chave primária), "
         "duplicata de conteúdo (identificação idêntica sob chaves distintas) e "
         "duplicata provável (similaridade elevada sem identidade exata). "
         "Garcia, Miranda e Sousa (2022) advertem que a duplicidade não tratada "
         "multiplica pares espúrios no relacionamento."),
        "TIPO_DUPLICIDADE",
        {"DUPLICATA_TECNICA": VERMELHO, "DUPLICATA_DE_CONTEUDO": VERMELHO,
         "DUPLICATA_PROVAVEL": AMARELO},
        larguras={"DESCRICAO": 58, "RECOMENDACAO": 58})

    obrigatorios = [linha for linha in completude if linha["OBRIGATORIO"] == "Sim"]
    _aba_com_cores(
        livro, "26_CAMPOS_OBRIGATORIOS", obrigatorios,
        "Campos obrigatórios — preenchimento",
        ("Campos de preenchimento obrigatório segundo os instrumentos de coleta "
         "e as normativas vigentes. A coluna IGNORADOS quantifica os registros "
         "preenchidos com código de ignorado: formalmente preenchidos, "
         "materialmente vazios."),
        "CLASSIFICACAO",
        {"Excelente": VERDE, "Bom": VERDE, "Regular": AMARELO,
         "Ruim": VERMELHO, "Muito ruim": VERMELHO})

    # --- Harmonização --------------------------------------------------- #
    _aba_simples(livro, "30_HARMONIZACAO", resultado.dicionario_harmonizacao,
                 "Harmonização — dicionário de transformações",
                 ("Regras aplicadas para tornar as variáveis comparáveis entre "
                  "sistemas, conforme os procedimentos de Garcia, Miranda e "
                  "Sousa (2022). As colunas nativas são preservadas; as "
                  "harmonizadas recebem o prefixo H_."),
                 larguras={"REGRA_APLICADA": 70})

    _aba_simples(livro, "31_VARIAVEIS_COMUNS", resultado.variaveis_comuns,
                 "Variáveis comuns e aptidão como chave de pareamento",
                 ("Responde à pergunta que antecede o linkage: quais chaves "
                  "estão efetivamente disponíveis nas bases a relacionar."),
                 larguras={"OBSERVACAO": 70})

    _aba_simples(livro, "32_EFEITO_DAS_CHAVES", resultado.efeito_das_chaves,
                 "Efeito da adição sequencial de chaves",
                 ("Reprodução, nas bases em uso, do experimento de Garcia, "
                  "Miranda e Sousa (2022): em bases simuladas, a chave 'nome' "
                  "isolada produziu 40.108 pares; o acréscimo de 'nome da mãe' "
                  "reduziu a 112; e a inclusão da 'data de nascimento' isolou "
                  "dois pares."),
                 larguras={"INTERPRETACAO": 70})

    # --- Pareamento ----------------------------------------------------- #
    larguras_pares = {"JUSTIFICATIVA": 62, "RECOMENDACAO": 62,
                      "SIMILARIDADE_POR_CAMPO": 48, "DIVERGENCIAS_OBSERVADAS": 40}

    _aba_simples(livro, "40_PAREAMENTO_DETERMINISTICO",
                 _linhas_de_pares(resultado, {PAREADO}, {"Determinístico"}),
                 "Pareamento determinístico — pares aceitos",
                 ("Primeiro estágio: chave composta aplicada em ordem "
                  "decrescente de especificidade. Cada registro é pareado uma "
                  "única vez, o que evita a explosão combinatória na presença "
                  "de duplicatas."), larguras_pares)

    _aba_simples(livro, "41_PAREAMENTO_PROBABILISTICO",
                 _linhas_de_pares(resultado, {PAREADO}, {"Probabilístico"}),
                 "Pareamento probabilístico — pares aceitos",
                 (f"Segundo estágio: similaridade Jaro-Winkler ponderada por "
                  f"campo (0,4 nome; 0,3 nome da mãe; 0,3 data de nascimento), "
                  f"aplicada aos registros não pareados no primeiro estágio. "
                  f"Limiar de aceitação: "
                  f"{configuracao.limiar_pareamento:.2f}."), larguras_pares)

    _aba_com_cores(
        livro, "42_PARES_EM_REVISAO_MANUAL",
        _linhas_de_pares(resultado, {REVISAO_MANUAL}),
        "Pares que exigem verificação manual",
        (f"Pares com escore entre {configuracao.limiar_revisao:.2f} e "
         f"{configuracao.limiar_pareamento:.2f} — intervalo de sensibilidade de "
         f"±0,05 em torno do limiar —, além dos pares com chave ambígua ou "
         f"divergência em variável auxiliar. Esta é a aba de maior rendimento "
         f"para o trabalho humano: nela se concentram os pares que a rotina não "
         f"pôde decidir sozinha."),
        "CLASSIFICACAO_DO_PAR", {REVISAO_MANUAL: AMARELO}, larguras_pares)

    nao_pareados, omitidos_por_relacionamento = _linhas_nao_pareados(resultado)
    total_omitidos = sum(omitidos_por_relacionamento.values())
    detalhe_omitidos = ("; ".join(f"{rotulo}: {quantidade}"
                                  for rotulo, quantidade
                                  in omitidos_por_relacionamento.items())
                        if omitidos_por_relacionamento else "")
    _aba_simples(livro, "43_NAO_PAREADOS", nao_pareados,
                 "Registros sem par que comportam ação corretiva",
                 (f"Esta aba lista apenas os registros que não parearam por "
                  f"lhes faltarem chaves de identificação — situação "
                  f"corrigível na base nativa. Outros {total_omitidos} "
                  f"registros também não parearam, mas com as chaves "
                  f"completas, o que indica apenas que a pessoa não consta da "
                  f"outra base: resultado esperado, que não enseja "
                  f"providência e por isso não é listado registro a registro"
                  + (f" ({detalhe_omitidos})" if detalhe_omitidos else "")
                  + ". A situação de cada registro quanto ao pareamento consta "
                    "também das abas das bases, na coluna SITUACAO NO "
                    "PAREAMENTO."),
                 larguras={"MOTIVO_PROVAVEL": 58, "RECOMENDACAO": 58,
                           "CHAVES_AUSENTES": 30})

    # --- Indicadores e análises ----------------------------------------- #
    indicadores = [linha for v in resultado.validacoes for linha in v.como_linhas()]
    if indicadores:
        _aba_simples(livro, "50_INDICADORES_PAREAMENTO", indicadores,
                     "Indicadores de avaliação do pareamento",
                     ("Sensibilidade, valor preditivo positivo e proporção de "
                      "falsos-positivos, aferidos contra a amostra de "
                      "referência, conforme o Quadro 4 do projeto."),
                     larguras={"INTERPRETACAO": 70})

    _aba_simples(livro, "51_GANHO_DE_COMPLETUDE", resultado.ganhos_completude,
                 "Ganho de completude após o relacionamento",
                 ("Mede quanto de informação faltante em uma base é recuperada "
                  "a partir da base relacionada — tradução numérica do benefício "
                  "operacional do linkage."))

    _aba_simples(livro, "52_CONSISTENCIA_ENTRE_BASES",
                 resultado.consistencia_entre_bases,
                 "Consistência entre bases",
                 ("Proporção de divergências em variáveis homônimas presentes "
                  "em mais de uma base, entre os pares confirmados "
                  "(Schmidt et al., 2020)."),
                 larguras={"INTERPRETACAO": 70})

    _aba_simples(livro, "53_INDICADORES_EPIDEMIOLOGICOS",
                 resultado.indicadores_epidemiologicos,
                 "Indicadores epidemiológicos",
                 ("Coeficientes calculados sobre as bases analisadas, com "
                  "intervalo de confiança de 95% pelo método de Wilson. "
                  "Fórmulas conforme a RIPSA."),
                 larguras={"INTERPRETACAO": 62, "FORMULA": 45})

    series = []
    for sigla, serie in resultado.series_mensais.items():
        for mes, valor in serie.items():
            series.append({"BASE": sigla,
                           "ANO": configuracao.ano_referencia,
                           "MES": int(mes),
                           "PERIODO": f"{configuracao.ano_referencia}-{int(mes):02d}",
                           "EVENTOS": int(valor)})
    _aba_simples(livro, "54_SERIE_TEMPORAL", series,
                 "Série temporal de eventos por mês",
                 "Contagem mensal de eventos por base, no ano de referência.")

    projecoes = [linha for p in resultado.projecoes for linha in p.como_linhas()]
    _aba_simples(livro, "55_PROJECOES", projecoes,
                 "Projeção das séries",
                 ("Projeção por regressão linear com intervalo de predição de "
                  "95%. As projeções devem ser lidas como cenário de "
                  "referência, e não como previsão."))

    estatisticas = [{"BASE": sigla, **medidas}
                    for sigla, medidas in resultado.estatisticas.items() if medidas]
    _aba_simples(livro, "56_ESTATISTICA_DESCRITIVA", estatisticas,
                 "Estatística descritiva das séries mensais",
                 ("Medidas de tendência central, dispersão e forma da "
                  "distribuição mensal de eventos."))

    # --- Recomendações e auditoria -------------------------------------- #
    _aba_com_cores(
        livro, "60_RECOMENDACOES", _linhas_recomendacoes(resultado),
        "Recomendações consolidadas por tipo de inconsistência",
        ("Agrupa os achados por tipo e, quando o problema é frequente, propõe "
         "ação estruturante sobre o processo de trabalho — e não apenas a "
         "correção caso a caso."),
        "GRAVIDADE", {VERMELHO: VERMELHO, AMARELO: AMARELO},
        larguras={"DESCRICAO_DO_PROBLEMA": 58, "JUSTIFICATIVA_TECNICA": 58,
                  "RECOMENDACAO": 58, "ACAO_ESTRUTURANTE_SUGERIDA": 65,
                  "PRIMEIRAS_LINHAS_AFETADAS": 40})

    _aba_simples(livro, "99_AUDITORIA", _linhas_auditoria(resultado),
                 "Trilha de auditoria da execução",
                 ("Registro verificável do que foi processado. Cada arquivo de "
                  "entrada é identificado pelo seu resumo criptográfico "
                  "SHA-256, o que permite demonstrar qual versão da base "
                  "originou este produto sem guardar cópia dos dados."),
                 larguras={"DETALHE": 70, "VALOR": 40})

    livro.properties.title = "ELO-SIS — Resultados"
    livro.properties.creator = "ELO-SIS"
    livro.properties.description = (
        "Qualificação, harmonização e pareamento de bases dos sistemas de "
        "informação em saúde. Contém dados pessoais sensíveis.")

    caminho.parent.mkdir(parents=True, exist_ok=True)
    livro.save(caminho)
    resultado.trilha.registrar_arquivo(caminho, "saida")
    resultado.trilha.registrar("planilha", f"Planilha gerada: {caminho.name}")
    return caminho
