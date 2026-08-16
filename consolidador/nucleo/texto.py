"""Normalizacao de texto, chaves e medidas de similaridade.

Tudo aqui usa apenas a biblioteca padrao do Python, para que o aplicativo
funcione em qualquer maquina que tenha Python 3.9+ instalado.
"""

from __future__ import annotations

import datetime as _dt
import re
import unicodedata
from functools import lru_cache

# --------------------------------------------------------------------------
# Normalizacao basica
# --------------------------------------------------------------------------

_ESPACOS = re.compile(r"\s+")
_NAO_ALNUM = re.compile(r"[^0-9a-z]+")


# O pareamento compara os mesmos textos milhares de vezes; guardar o resultado
# da limpeza e da normalizacao evita refazer o mesmo trabalho.
@lru_cache(maxsize=200_000)
def sem_acento(texto: str) -> str:
    """Remove acentos preservando as letras (São Paulo -> Sao Paulo)."""
    if not texto:
        return ""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


@lru_cache(maxsize=200_000)
def _limpar_texto(texto: str) -> str:
    texto = texto.replace(" ", " ")  # espaco nao separavel vindo de HTML
    return _ESPACOS.sub(" ", texto).strip()


def limpar(valor) -> str:
    """Converte para texto, remove espacos duplicados e espacos nas pontas."""
    if valor is None:
        return ""
    if isinstance(valor, str):
        return _limpar_texto(valor)
    if isinstance(valor, float) and valor != valor:  # NaN
        return ""
    if isinstance(valor, (_dt.date, _dt.datetime)):
        return valor.isoformat()
    return _limpar_texto(str(valor))


@lru_cache(maxsize=200_000)
def _normalizar_texto(texto: str) -> str:
    texto = _NAO_ALNUM.sub(" ", sem_acento(texto).lower())
    return _ESPACOS.sub(" ", texto).strip()


def normalizar(valor) -> str:
    """Forma canonica para comparacao: minusculas, sem acento, sem pontuacao."""
    return _normalizar_texto(limpar(valor))


def chave_cabecalho(valor) -> str:
    """Forma canonica de um nome de coluna (sem espacos)."""
    return normalizar(valor).replace(" ", "")


def so_digitos(valor) -> str:
    return re.sub(r"\D", "", limpar(valor))


def apenas_letras(valor) -> str:
    return re.sub(r"[^a-z ]", "", normalizar(valor)).strip()


def titulo(valor) -> str:
    """Nome proprio em caixa de titulo, respeitando preposicoes."""
    texto = limpar(valor)
    if not texto:
        return ""
    minusculas = {"de", "da", "do", "das", "dos", "e", "em", "na", "no", "a", "o"}
    partes = []
    for i, palavra in enumerate(texto.lower().split(" ")):
        if i > 0 and palavra in minusculas:
            partes.append(palavra)
        elif len(palavra) <= 3 and palavra.isupper():
            partes.append(palavra.upper())
        else:
            partes.append(palavra.capitalize())
    return " ".join(partes)


# --------------------------------------------------------------------------
# Similaridade
# --------------------------------------------------------------------------


def jaro(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    limite = max(len(a), len(b)) // 2 - 1
    if limite < 0:
        limite = 0
    marca_a = [False] * len(a)
    marca_b = [False] * len(b)
    comuns = 0
    for i, ca in enumerate(a):
        inicio = max(0, i - limite)
        fim = min(i + limite + 1, len(b))
        for j in range(inicio, fim):
            if marca_b[j] or b[j] != ca:
                continue
            marca_a[i] = True
            marca_b[j] = True
            comuns += 1
            break
    if comuns == 0:
        return 0.0
    transposicoes = 0
    j = 0
    for i in range(len(a)):
        if not marca_a[i]:
            continue
        while not marca_b[j]:
            j += 1
        if a[i] != b[j]:
            transposicoes += 1
        j += 1
    transposicoes //= 2
    return (comuns / len(a) + comuns / len(b) + (comuns - transposicoes) / comuns) / 3.0


def jaro_winkler(a: str, b: str, peso: float = 0.1) -> float:
    """Similaridade 0..1 com bonus para prefixo comum (bom para nomes)."""
    base = jaro(a, b)
    prefixo = 0
    for ca, cb in zip(a[:4], b[:4]):
        if ca != cb:
            break
        prefixo += 1
    return base + prefixo * peso * (1 - base)


def similaridade_tokens(a: str, b: str) -> float:
    """Compara conjuntos de palavras: robusto a ordem e nomes do meio."""
    ta = set(a.split())
    tb = set(b.split())
    if not ta or not tb:
        return 0.0
    intersecao = len(ta & tb)
    return (2 * intersecao) / (len(ta) + len(tb))


def similaridade(a: str, b: str) -> float:
    """Medida combinada usada no pareamento por semelhanca (0..1)."""
    a = normalizar(a)
    b = normalizar(b)
    if not a and not b:
        return 0.0
    if a == b:
        return 1.0
    return max(jaro_winkler(a, b), 0.5 * similaridade_tokens(a, b) + 0.5 * jaro_winkler(a, b))


_VOGAIS = str.maketrans("", "", "aeiou")
_PREPOSICOES = {"de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas", "a", "o"}


def _sem_preposicoes(valor: str) -> str:
    return "".join(p for p in normalizar(valor).split() if p not in _PREPOSICOES)


def esqueleto(valor: str) -> str:
    """Remove preposicoes e vogais para aproximar abreviacoes.

    'Data de admissao' e 'DTADMISSA' viram ambos 'dtdmss'.
    """
    return _sem_preposicoes(valor).translate(_VOGAIS)


def similaridade_nomes(a: str, b: str) -> float:
    """Compara nomes de coluna, tolerando abreviacao e truncamento.

    Arquivos DBF cortam o nome do campo em 10 caracteres e relatorios HTML
    escrevem o nome por extenso; 'NOMECOMPL' e 'Nome completo' precisam ser
    reconhecidos como o mesmo campo.
    """
    chave_a = _sem_preposicoes(a)
    chave_b = _sem_preposicoes(b)
    if not chave_a or not chave_b:
        return 0.0
    if chave_a == chave_b:
        return 1.0
    menor, maior = sorted((chave_a, chave_b), key=len)
    if len(menor) >= 3 and menor in maior:
        return 0.90 if maior.startswith(menor) else 0.85
    esq_a, esq_b = esqueleto(a), esqueleto(b)
    if esq_a and esq_a == esq_b:
        return 0.85
    menor_esq, maior_esq = sorted((esq_a, esq_b), key=len)
    if len(menor_esq) >= 4 and maior_esq.startswith(menor_esq):
        return 0.80
    return similaridade(a, b)


def similaridade_conjuntos(a, b) -> float:
    """Indice de Jaccard entre dois conjuntos (usado no reconhecimento)."""
    ca, cb = set(a), set(b)
    if not ca or not cb:
        return 0.0
    return len(ca & cb) / len(ca | cb)


# --------------------------------------------------------------------------
# Validadores de documentos e formatos brasileiros
# --------------------------------------------------------------------------


def cpf_valido(valor) -> bool:
    numeros = so_digitos(valor)
    if len(numeros) != 11 or numeros == numeros[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(numeros[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11
        digito = 0 if digito == 10 else digito
        if digito != int(numeros[tamanho]):
            return False
    return True


def cnpj_valido(valor) -> bool:
    numeros = so_digitos(valor)
    if len(numeros) != 14 or numeros == numeros[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    for pesos, posicao in ((pesos1, 12), (pesos2, 13)):
        soma = sum(int(numeros[i]) * pesos[i] for i in range(posicao))
        resto = soma % 11
        digito = 0 if resto < 2 else 11 - resto
        if digito != int(numeros[posicao]):
            return False
    return True


_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]{2,}$")


def email_valido(valor) -> bool:
    return bool(_RE_EMAIL.match(limpar(valor)))


def cep_valido(valor) -> bool:
    return len(so_digitos(valor)) == 8


def telefone_valido(valor) -> bool:
    return len(so_digitos(valor)) in (8, 9, 10, 11, 12, 13)


def formatar_cpf(valor) -> str:
    n = so_digitos(valor)
    if len(n) != 11:
        return limpar(valor)
    return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}"


def formatar_cnpj(valor) -> str:
    n = so_digitos(valor)
    if len(n) != 14:
        return limpar(valor)
    return f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}"


# --------------------------------------------------------------------------
# Conversao de tipos
# --------------------------------------------------------------------------

_FORMATOS_DATA = (
    "%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y",
    "%Y/%m/%d", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y%m%d",
)


def para_data(valor):
    """Converte texto/numero em date. Devolve None se nao for data."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, _dt.datetime):
        return valor.date()
    if isinstance(valor, _dt.date):
        return valor
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        # numero de serie do Excel (1899-12-30 como base)
        if 1 <= float(valor) <= 80000:
            return _dt.date(1899, 12, 30) + _dt.timedelta(days=int(valor))
        return None
    texto = limpar(valor)
    if not texto:
        return None
    texto = texto.replace("T", " ").strip() if texto.count("-") == 2 else texto
    for formato in _FORMATOS_DATA:
        try:
            return _dt.datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


_RE_NUMERO = re.compile(r"^[-+]?[\d.,\s]*\d(?:[.,]\d+)?$")


def para_numero(valor):
    """Converte texto em float aceitando 1.234,56 e 1,234.56. None se falhar."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = limpar(valor)
    if not texto:
        return None
    negativo = texto.startswith("(") and texto.endswith(")")
    texto = texto.strip("()")
    texto = re.sub(r"(?i)^(r\$|us\$|\$|%)\s*", "", texto).strip()
    texto = re.sub(r"\s*%$", "", texto).strip()
    if not _RE_NUMERO.match(texto.replace(" ", "")):
        return None
    texto = texto.replace(" ", "")
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif texto.count(".") > 1:
        texto = texto.replace(".", "")
    try:
        numero = float(texto)
    except ValueError:
        return None
    return -numero if negativo else numero


def formatar_numero(valor) -> str:
    numero = para_numero(valor)
    if numero is None:
        return limpar(valor)
    inteiro = f"{abs(numero):,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    return ("-" if numero < 0 else "") + inteiro
