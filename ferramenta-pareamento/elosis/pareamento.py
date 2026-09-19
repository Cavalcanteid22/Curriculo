# -*- coding: utf-8 -*-
"""
Pareamento (record linkage) entre bases de sistemas de informação em saúde.

Implementa a estratégia sequencial em dois estágios definida na metodologia do
projeto:

  Estágio 1 — pareamento determinístico por chave composta, com aplicação
  sequencial de conjuntos de chaves em ordem decrescente de especificidade;

  Estágio 2 — pareamento probabilístico dos registros não pareados no primeiro
  estágio, por similaridade Jaro-Winkler ponderada por campo (0,4 para nome;
  0,3 para nome da mãe; 0,3 para data de nascimento), com par considerado
  pareado quando o escore ≥ 0,90 e zona de revisão manual entre 0,85 e 0,90,
  correspondente à análise de sensibilidade de ±0,05.

A blocagem (blocking) restringe as comparações do estágio probabilístico a
subconjuntos plausíveis. Sem ela, o relacionamento de duas bases de 100 mil
registros exigiria 10 bilhões de comparações; com ela, o problema torna-se
tratável em estação de trabalho comum — resposta direta à limitação de memória
apontada por Garcia, Miranda e Sousa (2022) entre as restrições da técnica.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

import pandas as pd

from .harmonizacao import PREFIXO_HARMONIZADO, ResultadoHarmonizacao
from .perfis import (LIMIAR_PAREAMENTO, LIMIAR_REVISAO_MANUAL,
                     PESOS_AUXILIARES, PESOS_PROBABILISTICO, ROTULOS_CANONICOS)
from .similaridade import (similaridade_codigo, similaridade_data,
                           similaridade_nome)

PAREADO = "PAREADO"
REVISAO_MANUAL = "REVISAO_MANUAL"
NAO_PAREADO = "NAO_PAREADO"

# Conjuntos de chaves do estágio determinístico, em ordem decrescente de
# especificidade. A ordem reproduz o efeito demonstrado por Garcia, Miranda e
# Sousa (2022): a adição sequencial de chaves reduz drasticamente o número de
# pares candidatos e, com ele, a ambiguidade.
CONJUNTOS_DETERMINISTICOS = [
    (["CPF"], "R1", "CPF idêntico",
     "Identificador unívoco de pessoa natural. Coincidência integral do CPF "
     "válido constitui evidência de identidade de maior força entre as "
     "disponíveis nas bases."),
    (["CNS"], "R2", "CNS idêntico",
     "Identificador nacional do usuário do SUS. Coincidência integral do CNS "
     "válido é evidência forte de identidade."),
    (["NOME", "NOME_MAE", "DATA_NASCIMENTO"], "R3",
     "Nome + nome da mãe + data de nascimento",
     "Chave composta de três variáveis. Garcia, Miranda e Sousa (2022) "
     "demonstram, em bases simuladas, que a adição sequencial dessas chaves "
     "reduziu de 40.108 para 2 o número de pares, isolando os verdadeiros."),
    (["NOME", "DATA_NASCIMENTO", "SEXO"], "R4",
     "Nome + data de nascimento + sexo",
     "Aplicada quando o nome da mãe está ausente em uma das bases. O sexo "
     "substitui parcialmente a função discriminante do nome da mãe."),
    (["NOME_MAE", "DATA_NASCIMENTO", "SEXO"], "R5",
     "Nome da mãe + data de nascimento + sexo",
     "Aplicada a registros de recém-nascidos sem nome atribuído — situação "
     "frequente no SINASC e determinante para a vigilância do óbito infantil."),
]


@dataclass
class Par:
    """Um par de registros candidato a representar a mesma pessoa."""
    linha_a: int
    linha_b: int
    estagio: str
    regra: str
    escore: float
    escores_por_campo: dict[str, float]
    classificacao: str
    justificativa: str = ""
    divergencias: list[str] = field(default_factory=list)


@dataclass
class ResultadoPareamento:
    base_a: str
    base_b: str
    total_a: int
    total_b: int
    pares: list[Par]
    tempo_segundos: float
    comparacoes: int
    blocos: int
    nao_pareados_a: list[int]
    nao_pareados_b: list[int]
    chaves_utilizadas: list[str]
    limiar: float
    limiar_revisao: float

    @property
    def rotulo(self) -> str:
        return f"{self.base_a}x{self.base_b}"

    def por_classificacao(self, classificacao: str) -> list[Par]:
        return [p for p in self.pares if p.classificacao == classificacao]

    def resumo(self) -> dict:
        pareados = self.por_classificacao(PAREADO)
        revisao = self.por_classificacao(REVISAO_MANUAL)
        deterministicos = [p for p in pareados if p.estagio == "Determinístico"]
        probabilisticos = [p for p in pareados if p.estagio == "Probabilístico"]
        menor = min(self.total_a, self.total_b) or 1
        return {
            "RELACIONAMENTO": self.rotulo,
            "REGISTROS_BASE_A": self.total_a,
            "REGISTROS_BASE_B": self.total_b,
            "PARES_DETERMINISTICOS": len(deterministicos),
            "PARES_PROBABILISTICOS": len(probabilisticos),
            "PARES_TOTAIS": len(pareados),
            "PARES_PARA_REVISAO_MANUAL": len(revisao),
            "TAXA_DE_PAREAMENTO_%": round(100 * len(pareados) / menor, 2),
            "NAO_PAREADOS_A": len(self.nao_pareados_a),
            "NAO_PAREADOS_B": len(self.nao_pareados_b),
            "COMPARACOES_REALIZADAS": self.comparacoes,
            "BLOCOS_FORMADOS": self.blocos,
            "TEMPO_EXECUCAO_S": round(self.tempo_segundos, 2),
            "LIMIAR_PAREAMENTO": self.limiar,
            "LIMIAR_REVISAO_MANUAL": self.limiar_revisao,
        }


# --------------------------------------------------------------------------- #
# Estágio 1 — determinístico
# --------------------------------------------------------------------------- #

def _valores_chave(quadro: pd.DataFrame, chaves: list[str]) -> pd.Series | None:
    """Monta a chave composta; devolve None se alguma variável não existir."""
    colunas = []
    for chave in chaves:
        coluna = PREFIXO_HARMONIZADO + chave
        if coluna not in quadro.columns:
            return None
        colunas.append(quadro[coluna].astype(str).str.strip())
    composta = colunas[0]
    for coluna in colunas[1:]:
        composta = composta + "|" + coluna
    # Chave inválida se qualquer componente estiver vazio: chaves parciais
    # produzem junções espúrias em massa.
    vazio = colunas[0] == ""
    for coluna in colunas[1:]:
        vazio = vazio | (coluna == "")
    return composta.mask(vazio, "")


def parear_deterministico(quadro_a: pd.DataFrame, quadro_b: pd.DataFrame,
                          conjuntos=None) -> tuple[list[Par], set[int], set[int]]:
    """Aplica os conjuntos de chaves em sequência, do mais ao menos específico.

    Cada registro é pareado uma única vez: uma vez estabelecido o par por uma
    regra mais específica, o registro é retirado das rodadas seguintes. É essa
    exclusão progressiva que evita a explosão combinatória advertida por
    Garcia, Miranda e Sousa (2022) na presença de registros repetidos.
    """
    conjuntos = conjuntos or CONJUNTOS_DETERMINISTICOS
    pares: list[Par] = []
    usados_a: set[int] = set()
    usados_b: set[int] = set()

    for chaves, codigo, rotulo, fundamento in conjuntos:
        serie_a = _valores_chave(quadro_a, chaves)
        serie_b = _valores_chave(quadro_b, chaves)
        if serie_a is None or serie_b is None:
            continue

        indice_b: dict[str, list[int]] = defaultdict(list)
        for linha, valor in serie_b.items():
            if valor and linha not in usados_b:
                indice_b[valor].append(int(linha))

        for linha_a, valor in serie_a.items():
            linha_a = int(linha_a)
            if not valor or linha_a in usados_a:
                continue
            candidatos = [l for l in indice_b.get(valor, ()) if l not in usados_b]
            if not candidatos:
                continue

            # Mais de um candidato com a mesma chave: a base B contém
            # duplicidade não resolvida. O par é encaminhado à revisão manual,
            # e não descartado — o registro existe e precisa ser tratado.
            ambiguo = len(candidatos) > 1
            linha_b = candidatos[0]
            escores = {c: 1.0 for c in chaves}
            divergencias = _verificar_divergencias(quadro_a, quadro_b,
                                                   linha_a, linha_b, chaves)
            pares.append(Par(
                linha_a=linha_a, linha_b=linha_b, estagio="Determinístico",
                regra=f"{codigo} — {rotulo}", escore=1.0,
                escores_por_campo=escores,
                classificacao=REVISAO_MANUAL if (ambiguo or divergencias) else PAREADO,
                justificativa=(
                    f"{fundamento}"
                    + (f" ATENÇÃO: {len(candidatos)} registros da base de destino "
                       f"compartilham esta mesma chave, o que indica duplicidade "
                       f"não resolvida na origem; o par exige conferência."
                       if ambiguo else "")
                    + (f" Divergência observada em variáveis auxiliares: "
                       f"{'; '.join(divergencias)}." if divergencias else "")),
                divergencias=divergencias))
            usados_a.add(linha_a)
            usados_b.add(linha_b)
    return pares, usados_a, usados_b


def _verificar_divergencias(quadro_a, quadro_b, linha_a: int, linha_b: int,
                            chaves_usadas: list[str]) -> list[str]:
    """Confronta variáveis auxiliares que não compuseram a chave do par."""
    divergencias = []
    for variavel in ("SEXO", "DATA_NASCIMENTO", "MUNICIPIO_RESIDENCIA", "CPF"):
        if variavel in chaves_usadas:
            continue
        coluna = PREFIXO_HARMONIZADO + variavel
        if coluna not in quadro_a.columns or coluna not in quadro_b.columns:
            continue
        valor_a = str(quadro_a[coluna].at[linha_a]).strip()
        valor_b = str(quadro_b[coluna].at[linha_b]).strip()
        if valor_a and valor_b and valor_a != valor_b:
            if variavel == "SEXO" and "I" in (valor_a, valor_b):
                continue  # 'ignorado' não constitui divergência
            rotulo = ROTULOS_CANONICOS.get(variavel, variavel)
            divergencias.append(f"{rotulo} ('{valor_a}' na base A, '{valor_b}' na base B)")
    return divergencias


# --------------------------------------------------------------------------- #
# Estágio 2 — probabilístico
# --------------------------------------------------------------------------- #

def _construir_blocos(quadro: pd.DataFrame, linhas: list[int]) -> dict[str, list[int]]:
    """Chaves de blocagem múltiplas — basta coincidir em uma para comparar."""
    blocos: dict[str, list[int]] = defaultdict(list)
    tem = quadro.columns

    for linha in linhas:
        fonetico = str(quadro["H_NOME_FONETICO"].at[linha]) if "H_NOME_FONETICO" in tem else ""
        mae_fonetico = str(quadro["H_MAE_FONETICO"].at[linha]) if "H_MAE_FONETICO" in tem else ""
        nascimento = str(quadro[PREFIXO_HARMONIZADO + "DATA_NASCIMENTO"].at[linha]) \
            if PREFIXO_HARMONIZADO + "DATA_NASCIMENTO" in tem else ""
        ano = nascimento[:4]
        nome = str(quadro[PREFIXO_HARMONIZADO + "NOME"].at[linha]) \
            if PREFIXO_HARMONIZADO + "NOME" in tem else ""
        sexo = str(quadro[PREFIXO_HARMONIZADO + "SEXO"].at[linha]) \
            if PREFIXO_HARMONIZADO + "SEXO" in tem else ""

        if fonetico and ano:
            blocos[f"F{fonetico}|{ano}"].append(linha)
        if nascimento:
            blocos[f"D{nascimento}"].append(linha)
        if mae_fonetico and ano:
            blocos[f"M{mae_fonetico}|{ano}"].append(linha)
        if nome and ano:
            blocos[f"P{nome[:5]}|{ano}"].append(linha)
        if nome and sexo and ano:
            blocos[f"S{nome.split()[-1][:5] if nome.split() else ''}|{sexo}|{ano}"].append(linha)
    return blocos


def calcular_escore(quadro_a: pd.DataFrame, quadro_b: pd.DataFrame,
                    linha_a: int, linha_b: int) -> tuple[float, dict[str, float]]:
    """Escore Jaro-Winkler ponderado por campo, com ajuste por variáveis auxiliares.

    Os pesos principais (0,4 nome; 0,3 nome da mãe; 0,3 data de nascimento)
    são os definidos na fundamentação teórica do projeto e refletem a
    confiabilidade esperada de cada variável em contexto de vigilância
    municipal. Quando uma variável principal falta em um dos registros, seu
    peso é redistribuído entre as presentes, e não simplesmente descontado:
    descontá-lo penalizaria o registro pela incompletude da base, não pela
    falta de evidência de identidade.
    """
    escores: dict[str, float] = {}
    componentes: list[tuple[float, float]] = []

    for variavel, peso in PESOS_PROBABILISTICO.items():
        coluna = PREFIXO_HARMONIZADO + variavel
        if coluna not in quadro_a.columns or coluna not in quadro_b.columns:
            continue
        valor_a = str(quadro_a[coluna].at[linha_a]).strip()
        valor_b = str(quadro_b[coluna].at[linha_b]).strip()
        if not valor_a or not valor_b:
            continue
        if variavel == "DATA_NASCIMENTO":
            similaridade = similaridade_data(valor_a, valor_b)
        else:
            similaridade = similaridade_nome(valor_a, valor_b)
        escores[variavel] = round(similaridade, 4)
        componentes.append((peso, similaridade))

    if not componentes:
        return 0.0, escores

    peso_total = sum(p for p, _ in componentes)
    # Exige-se ao menos o nome, ou duas variáveis secundárias, para pontuar.
    if peso_total < 0.40:
        return 0.0, escores
    escore = sum(p * v for p, v in componentes) / peso_total

    # Variáveis auxiliares: bonificam a concordância e penalizam a divergência.
    ajuste = 0.0
    for variavel, peso in PESOS_AUXILIARES.items():
        coluna = PREFIXO_HARMONIZADO + variavel
        if coluna not in quadro_a.columns or coluna not in quadro_b.columns:
            continue
        valor_a = str(quadro_a[coluna].at[linha_a]).strip()
        valor_b = str(quadro_b[coluna].at[linha_b]).strip()
        if not valor_a or not valor_b:
            continue
        if variavel in ("CPF", "CNS"):
            similaridade = similaridade_codigo(valor_a, valor_b)
            escores[variavel] = round(similaridade, 4)
            ajuste += peso if similaridade >= 0.99 else (-peso if similaridade == 0 else 0)
        elif variavel == "SEXO":
            if "I" in (valor_a, valor_b):
                continue
            escores[variavel] = 1.0 if valor_a == valor_b else 0.0
            ajuste += peso if valor_a == valor_b else -peso * 3
        else:
            escores[variavel] = 1.0 if valor_a == valor_b else 0.0
            ajuste += peso if valor_a == valor_b else 0.0

    return max(0.0, min(1.0, escore + ajuste)), escores


def parear_probabilistico(quadro_a: pd.DataFrame, quadro_b: pd.DataFrame,
                          candidatos_a: list[int], candidatos_b: list[int],
                          limiar: float = LIMIAR_PAREAMENTO,
                          limiar_revisao: float = LIMIAR_REVISAO_MANUAL,
                          maximo_comparacoes: int = 50_000_000,
                          bloco_maximo: int = 1500,
                          progresso=None) -> tuple[list[Par], int, int]:
    """Compara, sob blocagem, os registros não pareados no estágio determinístico."""
    blocos_a = _construir_blocos(quadro_a, candidatos_a)
    blocos_b = _construir_blocos(quadro_b, candidatos_b)
    chaves_comuns = set(blocos_a) & set(blocos_b)

    melhores: dict[int, tuple[float, int, dict]] = {}
    pares_avaliados: set[tuple[int, int]] = set()
    comparacoes = 0

    excedeu_teto = False
    for ordem, chave in enumerate(sorted(chaves_comuns)):
        if excedeu_teto:
            break
        lista_a = blocos_a[chave]
        lista_b = blocos_b[chave]
        if len(lista_a) * len(lista_b) > bloco_maximo * bloco_maximo:
            continue  # bloco degenerado: chave sem poder de seleção
        for linha_a in lista_a:
            if excedeu_teto:
                break
            for linha_b in lista_b:
                par = (linha_a, linha_b)
                if par in pares_avaliados:
                    continue
                pares_avaliados.add(par)
                comparacoes += 1
                if comparacoes > maximo_comparacoes:
                    excedeu_teto = True
                    break
                escore, escores = calcular_escore(quadro_a, quadro_b,
                                                  linha_a, linha_b)
                if escore < limiar_revisao:
                    continue
                atual = melhores.get(linha_a)
                if atual is None or escore > atual[0]:
                    melhores[linha_a] = (escore, linha_b, escores)
        if progresso and ordem % 500 == 0:
            progresso(ordem, len(chaves_comuns))

    # Resolve conflitos: cada registro de B pode participar de um único par.
    # Prevalece o par de maior escore — regra de atribuição gulosa, adequada
    # quando os escores são bem separados, como ocorre sob limiar de 0,90.
    ordenados = sorted(melhores.items(), key=lambda item: -item[1][0])
    ocupados_b: set[int] = set()
    pares: list[Par] = []
    for linha_a, (escore, linha_b, escores) in ordenados:
        if linha_b in ocupados_b:
            continue
        ocupados_b.add(linha_b)
        classificacao = PAREADO if escore >= limiar else REVISAO_MANUAL
        divergencias = _verificar_divergencias(quadro_a, quadro_b, linha_a,
                                               linha_b, [])
        detalhe = ", ".join(f"{ROTULOS_CANONICOS.get(k, k)}={v:.3f}"
                            for k, v in escores.items())
        if classificacao == PAREADO:
            justificativa = (
                f"Escore Jaro-Winkler ponderado de {escore:.4f}, igual ou "
                f"superior ao limiar de {limiar:.2f} adotado. Similaridade por "
                f"campo: {detalhe}.")
        else:
            justificativa = (
                f"Escore de {escore:.4f}, situado na faixa de revisão manual "
                f"({limiar_revisao:.2f} a {limiar:.2f}) — intervalo de "
                f"sensibilidade de ±0,05 em torno do limiar. Similaridade por "
                f"campo: {detalhe}. Exige conferência por técnico da área.")
        if divergencias:
            classificacao = REVISAO_MANUAL
            justificativa += (f" Divergência em variáveis auxiliares: "
                              f"{'; '.join(divergencias)}.")
        pares.append(Par(
            linha_a=linha_a, linha_b=linha_b, estagio="Probabilístico",
            regra=f"P1 — Jaro-Winkler ponderado (0,4/0,3/0,3)",
            escore=round(escore, 4), escores_por_campo=escores,
            classificacao=classificacao, justificativa=justificativa,
            divergencias=divergencias))
    return pares, comparacoes, len(chaves_comuns)


# --------------------------------------------------------------------------- #
# Orquestração do relacionamento entre duas bases
# --------------------------------------------------------------------------- #

def parear(harmonizado_a: ResultadoHarmonizacao,
           harmonizado_b: ResultadoHarmonizacao,
           limiar: float = LIMIAR_PAREAMENTO,
           limiar_revisao: float = LIMIAR_REVISAO_MANUAL,
           progresso=None) -> ResultadoPareamento:
    """Executa os dois estágios e consolida o resultado."""
    inicio = time.time()
    quadro_a, quadro_b = harmonizado_a.quadro, harmonizado_b.quadro

    if progresso:
        progresso(f"Estágio determinístico: {harmonizado_a.sigla} x "
                  f"{harmonizado_b.sigla}")
    pares_det, usados_a, usados_b = parear_deterministico(quadro_a, quadro_b)

    restantes_a = [int(i) for i in quadro_a.index if int(i) not in usados_a]
    restantes_b = [int(i) for i in quadro_b.index if int(i) not in usados_b]

    if progresso:
        progresso(f"Estágio probabilístico: {len(restantes_a)} x "
                  f"{len(restantes_b)} registros remanescentes")
    pares_prob, comparacoes, blocos = parear_probabilistico(
        quadro_a, quadro_b, restantes_a, restantes_b, limiar, limiar_revisao)

    pares = pares_det + pares_prob
    pareados_a = {p.linha_a for p in pares if p.classificacao == PAREADO}
    pareados_b = {p.linha_b for p in pares if p.classificacao == PAREADO}

    chaves = []
    for conjunto, codigo, rotulo, _ in CONJUNTOS_DETERMINISTICOS:
        if all(PREFIXO_HARMONIZADO + c in quadro_a.columns
               and PREFIXO_HARMONIZADO + c in quadro_b.columns
               for c in conjunto):
            chaves.append(f"{codigo}: {rotulo}")

    return ResultadoPareamento(
        base_a=harmonizado_a.sigla, base_b=harmonizado_b.sigla,
        total_a=len(quadro_a), total_b=len(quadro_b), pares=pares,
        tempo_segundos=time.time() - inicio, comparacoes=comparacoes,
        blocos=blocos,
        nao_pareados_a=[i for i in quadro_a.index if int(i) not in pareados_a],
        nao_pareados_b=[i for i in quadro_b.index if int(i) not in pareados_b],
        chaves_utilizadas=chaves, limiar=limiar, limiar_revisao=limiar_revisao)


def demonstrar_efeito_das_chaves(harmonizado_a: ResultadoHarmonizacao,
                                 harmonizado_b: ResultadoHarmonizacao
                                 ) -> list[dict]:
    """Reproduz, nas bases em uso, o experimento de Garcia, Miranda e Sousa (2022).

    Os autores demonstram que a chave "nome" isolada produziu 40.108 pares; o
    acréscimo de "nome da mãe" reduziu o resultado a 112; e a inclusão da "data
    de nascimento" isolou dois pares. Executar o mesmo experimento sobre as
    bases municipais documenta empiricamente, para a SUIS, o ganho de
    especificidade obtido a cada chave adicionada.
    """
    quadro_a, quadro_b = harmonizado_a.quadro, harmonizado_b.quadro
    sequencias = [
        (["NOME"], "Apenas nome"),
        (["NOME", "NOME_MAE"], "Nome + nome da mãe"),
        (["NOME", "NOME_MAE", "DATA_NASCIMENTO"],
         "Nome + nome da mãe + data de nascimento"),
        (["NOME", "NOME_MAE", "DATA_NASCIMENTO", "SEXO"],
         "Nome + nome da mãe + data de nascimento + sexo"),
    ]
    linhas = []
    anterior = None
    for chaves, rotulo in sequencias:
        serie_a = _valores_chave(quadro_a, chaves)
        serie_b = _valores_chave(quadro_b, chaves)
        if serie_a is None or serie_b is None:
            continue
        contagem_b: dict[str, int] = defaultdict(int)
        for valor in serie_b:
            if valor:
                contagem_b[valor] += 1
        pares = sum(contagem_b.get(valor, 0) for valor in serie_a if valor)
        reducao = (round(100 * (1 - pares / anterior), 2)
                   if anterior not in (None, 0) else "")
        linhas.append({
            "RELACIONAMENTO": f"{harmonizado_a.sigla} x {harmonizado_b.sigla}",
            "CONJUNTO_DE_CHAVES": rotulo,
            "N_CHAVES": len(chaves),
            "PARES_CANDIDATOS": pares,
            "REDUCAO_EM_RELACAO_AO_ANTERIOR_%": reducao,
            "INTERPRETACAO": _interpretar_reducao(len(chaves), pares, reducao),
        })
        anterior = pares
    return linhas


def _interpretar_reducao(n_chaves: int, pares: int, reducao) -> str:
    if n_chaves == 1:
        return ("Alta sensibilidade e baixa especificidade: o uso isolado do "
                "nome recupera quase todos os pares verdadeiros, mas ao custo "
                "de numerosas correspondências falsas por homonímia.")
    if reducao == "" or reducao == 0:
        return ("A chave adicionada não alterou o número de pares candidatos, "
                "o que sugere que ela é redundante em relação às anteriores ou "
                "apresenta completude insuficiente nestas bases.")
    if isinstance(reducao, (int, float)) and reducao > 50:
        return (f"Redução de {reducao}% no número de pares candidatos. O ganho "
                "de especificidade confirma, nestas bases, o efeito descrito "
                "por Garcia, Miranda e Sousa (2022).")
    return (f"Redução de {reducao}% — ganho de especificidade moderado, "
            "compatível com chave de completude parcial.")
