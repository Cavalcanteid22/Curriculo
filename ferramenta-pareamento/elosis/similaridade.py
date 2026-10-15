# -*- coding: utf-8 -*-
"""
Métricas de similaridade entre cadeias de caracteres e codificação fonética
adaptada ao português brasileiro (ELO-SIS).

A métrica principal é a Jaro-Winkler, adotada no projeto por ser a mais
robusta para cadeias nominais com erros de digitação característicos da
vigilância em saúde (Cohen et al., 2003) e superior à distância de
Levenshtein para nomes com variação de grafia (Garcia; Miranda; Sousa, 2022).

Implementação em Python puro, sem dependências externas: o produto precisa
executar em estações institucionais sem acesso a repositórios de pacotes.
"""

from __future__ import annotations

from functools import lru_cache

# --------------------------------------------------------------------------- #
# Jaro e Jaro-Winkler
# --------------------------------------------------------------------------- #

def jaro(s1: str, s2: str) -> float:
    """Similaridade de Jaro no intervalo [0, 1]."""
    if s1 == s2:
        return 1.0 if s1 else 0.0
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0

    janela = max(len1, len2) // 2 - 1
    if janela < 0:
        janela = 0

    marcas1 = [False] * len1
    marcas2 = [False] * len2
    correspondencias = 0

    for i in range(len1):
        inicio = max(0, i - janela)
        fim = min(i + janela + 1, len2)
        for j in range(inicio, fim):
            if marcas2[j] or s1[i] != s2[j]:
                continue
            marcas1[i] = marcas2[j] = True
            correspondencias += 1
            break

    if correspondencias == 0:
        return 0.0

    # Transposições: metade do número de pares correspondentes fora de ordem.
    transposicoes = 0
    k = 0
    for i in range(len1):
        if not marcas1[i]:
            continue
        while not marcas2[k]:
            k += 1
        if s1[i] != s2[k]:
            transposicoes += 1
        k += 1
    transposicoes //= 2

    m = float(correspondencias)
    return (m / len1 + m / len2 + (m - transposicoes) / m) / 3.0


def jaro_winkler(s1: str, s2: str, fator: float = 0.1,
                 prefixo_maximo: int = 4, limiar_bonus: float = 0.7) -> float:
    """Jaro-Winkler: privilegia coincidência no prefixo da cadeia.

    O fator de escala 0,1 e o prefixo máximo de 4 caracteres são os valores
    canônicos propostos por Winkler e os adotados nas rotinas de linkage em
    saúde pública.
    """
    distancia = jaro(s1, s2)
    if distancia < limiar_bonus:
        return distancia
    prefixo = 0
    for c1, c2 in zip(s1[:prefixo_maximo], s2[:prefixo_maximo]):
        if c1 != c2:
            break
        prefixo += 1
    return distancia + prefixo * fator * (1.0 - distancia)


# --------------------------------------------------------------------------- #
# Levenshtein (usado em verificações auxiliares e em campos numéricos)
# --------------------------------------------------------------------------- #

def levenshtein(s1: str, s2: str, teto: int | None = None) -> int:
    """Distância de edição. O parâmetro ``teto`` interrompe o cálculo cedo."""
    if s1 == s2:
        return 0
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    if not s2:
        return len(s1)
    if teto is not None and abs(len(s1) - len(s2)) > teto:
        return teto + 1

    linha_anterior = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        linha_atual = [i + 1]
        minimo_linha = linha_atual[0]
        for j, c2 in enumerate(s2):
            custo = 0 if c1 == c2 else 1
            valor = min(linha_anterior[j + 1] + 1,
                        linha_atual[j] + 1,
                        linha_anterior[j] + custo)
            linha_atual.append(valor)
            minimo_linha = min(minimo_linha, valor)
        if teto is not None and minimo_linha > teto:
            return teto + 1
        linha_anterior = linha_atual
    return linha_anterior[-1]


def similaridade_levenshtein(s1: str, s2: str) -> float:
    maior = max(len(s1), len(s2))
    if maior == 0:
        return 0.0
    return 1.0 - levenshtein(s1, s2) / maior


# --------------------------------------------------------------------------- #
# Codificação fonética para o português brasileiro
# --------------------------------------------------------------------------- #

_SUBSTITUICOES_FONETICAS = [
    ("LH", "L"), ("NH", "N"), ("CH", "X"), ("PH", "F"), ("RR", "R"),
    ("SS", "S"), ("SC", "S"), ("SÇ", "S"), ("XC", "S"), ("GE", "JE"),
    ("GI", "JI"), ("QU", "K"), ("GU", "G"), ("CE", "SE"), ("CI", "SI"),
    ("Ç", "S"), ("Y", "I"), ("W", "V"), ("Z", "S"), ("H", ""),
]

_CONSOANTES_EQUIVALENTES = str.maketrans({"K": "C", "Q": "C", "W": "V"})


@lru_cache(maxsize=200_000)
def codigo_fonetico(palavra: str) -> str:
    """Código fonético aproximado, no espírito do Soundex adaptado ao português.

    Serve à blocagem (etapa que restringe as comparações a subconjuntos
    plausíveis) e ao aumento de sensibilidade sugerido por Garcia, Miranda e
    Sousa (2022) ao recomendarem o emprego de códigos fonéticos combinados a
    outras variáveis.
    """
    if not palavra:
        return ""
    texto = palavra.upper()
    for origem, destino in _SUBSTITUICOES_FONETICAS:
        texto = texto.replace(origem, destino)
    texto = texto.translate(_CONSOANTES_EQUIVALENTES)
    if not texto:
        return ""

    primeira = texto[0]
    grupos = {
        "B": "1", "F": "1", "P": "1", "V": "1",
        "C": "2", "G": "2", "J": "2", "S": "2", "X": "2",
        "D": "3", "T": "3",
        "L": "4",
        "M": "5", "N": "5",
        "R": "6",
    }
    codigo = [primeira]
    ultimo = grupos.get(primeira, "")
    for letra in texto[1:]:
        digito = grupos.get(letra, "")
        if digito and digito != ultimo:
            codigo.append(digito)
        if letra not in "AEIOU":
            ultimo = digito
        else:
            ultimo = ""
        if len(codigo) == 4:
            break
    return "".join(codigo).ljust(4, "0")


def chave_fonetica_nome(nome: str, partes: int = 2) -> str:
    """Concatena os códigos fonéticos do primeiro nome e do último sobrenome."""
    if not nome:
        return ""
    tokens = nome.split()
    if not tokens:
        return ""
    if len(tokens) == 1:
        return codigo_fonetico(tokens[0])
    selecionados = [tokens[0], tokens[-1]][:partes]
    return "".join(codigo_fonetico(t) for t in selecionados)


# --------------------------------------------------------------------------- #
# Similaridades especializadas
# --------------------------------------------------------------------------- #

def similaridade_nome(nome1: str, nome2: str) -> float:
    """Jaro-Winkler sobre o nome completo, com reforço por tokens.

    Nomes de vigilância frequentemente diferem por supressão ou inversão de
    sobrenomes intermediários. Compara-se, por isso, tanto a cadeia integral
    quanto o conjunto de tokens, retendo-se o maior valor — o que reduz o
    falso-negativo sem elevar de forma apreciável o falso-positivo, já que o
    pareamento exige também concordância de outras chaves.
    """
    if not nome1 or not nome2:
        return 0.0
    if nome1 == nome2:
        return 1.0

    direto = jaro_winkler(nome1, nome2)

    tokens1 = [t for t in nome1.split() if len(t) > 1]
    tokens2 = [t for t in nome2.split() if len(t) > 1]
    if not tokens1 or not tokens2:
        return direto

    # Casamento guloso entre tokens, ponderado pelo comprimento.
    pendentes = list(tokens2)
    soma, peso_total = 0.0, 0
    for t1 in tokens1:
        if not pendentes:
            break
        melhor, indice = 0.0, 0
        for i, t2 in enumerate(pendentes):
            valor = jaro_winkler(t1, t2)
            if valor > melhor:
                melhor, indice = valor, i
        pendentes.pop(indice)
        soma += melhor * len(t1)
        peso_total += len(t1)
    por_token = soma / peso_total if peso_total else 0.0

    # Concordância de primeiro nome e último sobrenome é fortemente indicativa.
    extremos = (jaro_winkler(tokens1[0], tokens2[0])
                + jaro_winkler(tokens1[-1], tokens2[-1])) / 2.0

    return max(direto, 0.6 * por_token + 0.4 * extremos)


def similaridade_data(data1: str, data2: str) -> float:
    """Similaridade entre datas no formato AAAA-MM-DD.

    Penaliza de modo graduado os erros mais comuns da digitação em vigilância:
    inversão entre dia e mês e troca de um único dígito.
    """
    if not data1 or not data2:
        return 0.0
    if data1 == data2:
        return 1.0
    if len(data1) != 10 or len(data2) != 10:
        return jaro_winkler(data1, data2)

    a1, m1, d1 = data1[:4], data1[5:7], data1[8:10]
    a2, m2, d2 = data2[:4], data2[5:7], data2[8:10]

    if a1 == a2 and m1 == d2 and d1 == m2:
        return 0.90  # inversão dia/mês: erro clássico de transcrição
    if a1 == a2 and m1 == m2:
        return 0.85 if levenshtein(d1, d2, teto=1) <= 1 else 0.55
    if a1 == a2 and d1 == d2:
        return 0.80 if levenshtein(m1, m2, teto=1) <= 1 else 0.50
    if m1 == m2 and d1 == d2:
        return 0.75 if levenshtein(a1, a2, teto=1) <= 1 else 0.45
    return jaro_winkler(data1.replace("-", ""), data2.replace("-", "")) * 0.6


def similaridade_codigo(cod1: str, cod2: str) -> float:
    """Similaridade para identificadores numéricos (CPF, CNS, CEP)."""
    if not cod1 or not cod2:
        return 0.0
    if cod1 == cod2:
        return 1.0
    if len(cod1) == len(cod2):
        distancia = levenshtein(cod1, cod2, teto=2)
        if distancia == 1:
            return 0.85
        if distancia == 2:
            return 0.65
    return 0.0
