# -*- coding: utf-8 -*-
"""
Pré-processamento e padronização de variáveis (ELO-SIS).

Segue os procedimentos descritos por Garcia, Miranda e Sousa (2022):
conversão de todas as letras para maiúsculas, remoção de acentos, de
caracteres especiais e de espaços duplos, supressão das preposições que ligam
sobrenomes e, para variáveis numéricas como o CPF, remoção de pontuação com
preenchimento de zeros à esquerda até o comprimento padronizado.

Todas as funções preservam o valor original: a normalização produz colunas
novas, nunca sobrescreve as nativas. A rastreabilidade entre o dado bruto e o
dado tratado é requisito de auditoria em saúde pública.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from functools import lru_cache

from .perfis import CODIGOS_IGNORADO, NOMES_INVALIDOS

# Preposições e partículas de ligação suprimidas nas chaves de pareamento.
PREPOSICOES = {"DA", "DE", "DO", "DAS", "DOS", "E", "D", "DI", "DU",
               "DEL", "DELLA", "VON", "VAN", "Y", "LA", "LE", "DAL"}

# Sufixos de geração, que variam de registro para registro.
SUFIXOS = {"JUNIOR", "JR", "FILHO", "NETO", "SOBRINHO", "SEGUNDO", "TERCEIRO",
           "FILHA", "NETA", "I", "II", "III", "IV"}

_RE_NAO_ALFA = re.compile(r"[^A-Z\s]")
_RE_ESPACOS = re.compile(r"\s+")
_RE_NAO_DIGITO = re.compile(r"\D")

_FORMATOS_DATA = (
    "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y%m%d", "%d%m%Y",
    "%d.%m.%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S",
    "%d/%m/%y", "%Y-%m-%dT%H:%M:%S",
)


# --------------------------------------------------------------------------- #
# Texto e nomes
# --------------------------------------------------------------------------- #

@lru_cache(maxsize=300_000)
def _remover_acentos_cache(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def remover_acentos(texto: str) -> str:
    """Remove a acentuação preservando as demais letras.

    O resultado é memorizado: a decomposição Unicode é custosa e os valores
    se repetem intensamente em bases de vigilância.
    """
    if not texto:
        return ""
    return _remover_acentos_cache(str(texto))


def normalizar_texto(valor) -> str:
    """Maiúsculas, sem acentos, sem caracteres especiais, sem espaços duplos."""
    if valor is None:
        return ""
    texto = remover_acentos(str(valor)).upper()
    texto = _RE_NAO_ALFA.sub(" ", texto)
    return _RE_ESPACOS.sub(" ", texto).strip()


@lru_cache(maxsize=300_000)
def _normalizar_nome_cache(valor: str, remover_preposicoes: bool,
                           remover_sufixos: bool) -> str:
    texto = normalizar_texto(valor)
    if not texto:
        return ""
    tokens = texto.split()
    if remover_preposicoes:
        tokens = [t for t in tokens if t not in PREPOSICOES]
    if remover_sufixos:
        tokens = [t for t in tokens if t not in SUFIXOS]
    # Remove iniciais isoladas: não discriminam e distorcem a similaridade.
    tokens = [t for t in tokens if len(t) > 1] or tokens
    return " ".join(tokens)


def normalizar_nome(valor, remover_preposicoes: bool = True,
                    remover_sufixos: bool = False) -> str:
    """Padroniza um campo nominal para uso como chave de pareamento."""
    if valor is None:
        return ""
    return _normalizar_nome_cache(str(valor), remover_preposicoes,
                                  remover_sufixos)


def nome_e_invalido(valor) -> tuple[bool, str]:
    """Verifica preenchimentos que não constituem nome de pessoa.

    Devolve (é inválido, motivo). Os padrões verificados são os observados com
    maior frequência nas bases de vigilância: marcadores de ausência, nomes de
    teste, caracteres repetidos e registros de recém-nascido não nominados.
    """
    texto = normalizar_nome(valor, remover_preposicoes=False)
    if not texto:
        return True, "campo em branco"
    if texto in NOMES_INVALIDOS:
        return True, f"preenchimento genérico ('{texto}')"
    if any(texto.startswith(f"{marca} ") for marca in ("RN", "NATIMORTO", "IGNORADO")):
        return True, f"preenchimento genérico iniciado por '{texto.split()[0]}'"
    if len(texto.replace(" ", "")) < 3:
        return True, "nome com menos de 3 letras"
    if len(set(texto.replace(" ", ""))) <= 2:
        return True, "caractere repetido (ex.: 'AAAA')"
    if len(texto.split()) < 2:
        return True, "nome sem sobrenome"
    if re.search(r"(.)\1{3,}", texto):
        return True, "sequência de caractere repetido quatro vezes ou mais"
    return False, ""


def iniciais(nome: str) -> str:
    return "".join(t[0] for t in normalizar_nome(nome).split() if t)


# --------------------------------------------------------------------------- #
# Datas
# --------------------------------------------------------------------------- #

_RE_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def normalizar_data(valor) -> str:
    """Converte para AAAA-MM-DD. Devolve "" quando a data não é interpretável."""
    if valor is None:
        return ""
    texto = str(valor).strip()
    # Caminho rápido: o valor já está no formato de destino. Evita o custo do
    # strptime na maioria esmagadora dos registros das bases do DATASUS.
    correspondencia = _RE_ISO.match(texto)
    if correspondencia:
        ano, mes, dia = (int(g) for g in correspondencia.groups())
        if 1850 <= ano <= 2100 and 1 <= mes <= 12 and 1 <= dia <= 31:
            try:
                return date(ano, mes, dia).isoformat()
            except ValueError:
                return ""
    return _normalizar_data_lenta(texto)


@lru_cache(maxsize=200_000)
def _normalizar_data_lenta(texto: str) -> str:
    """Interpreta os demais formatos aceitos pelos sistemas de origem."""
    if not texto or texto.upper() in {"NAN", "NAT", "NONE", "NULL", "//", "  /  /"}:
        return ""
    texto = texto.replace("\\", "/")

    for formato in _FORMATOS_DATA:
        try:
            convertida = datetime.strptime(texto[:len(formato) + 6].strip(), formato)
            if 1850 <= convertida.year <= 2100:
                return convertida.strftime("%Y-%m-%d")
        except ValueError:
            continue

    digitos = _RE_NAO_DIGITO.sub("", texto)
    if len(digitos) == 8:
        for ordem in ((0, 4, 4, 6, 6, 8), (4, 8, 2, 4, 0, 2)):
            try:
                if ordem[0] == 0:
                    ano, mes, dia = digitos[0:4], digitos[4:6], digitos[6:8]
                else:
                    ano, mes, dia = digitos[4:8], digitos[2:4], digitos[0:2]
                convertida = date(int(ano), int(mes), int(dia))
                if 1850 <= convertida.year <= 2100:
                    return convertida.isoformat()
            except ValueError:
                continue
    return ""


def data_e_valida(valor) -> tuple[bool, str]:
    """Verifica se a data é interpretável e plausível."""
    texto = str(valor or "").strip()
    if not texto:
        return False, "campo em branco"
    normalizada = normalizar_data(texto)
    if not normalizada:
        digitos = _RE_NAO_DIGITO.sub("", texto)
        if len(digitos) == 8:
            return False, "data inexistente no calendário (ex.: 31/02 ou mês 13)"
        return False, "formato de data não reconhecido"
    convertida = date.fromisoformat(normalizada)
    if convertida > date.today():
        return False, "data futura"
    if convertida.year < 1900:
        return False, "data anterior a 1900"
    return True, ""


def diferenca_em_dias(data_inicial, data_final) -> int | None:
    inicio = normalizar_data(data_inicial)
    fim = normalizar_data(data_final)
    if not inicio or not fim:
        return None
    return (date.fromisoformat(fim) - date.fromisoformat(inicio)).days


def idade_em_anos(data_nascimento, data_referencia=None) -> int | None:
    nascimento = normalizar_data(data_nascimento)
    if not nascimento:
        return None
    referencia = (date.fromisoformat(normalizar_data(data_referencia))
                  if data_referencia and normalizar_data(data_referencia)
                  else date.today())
    nasc = date.fromisoformat(nascimento)
    anos = referencia.year - nasc.year
    if (referencia.month, referencia.day) < (nasc.month, nasc.day):
        anos -= 1
    return anos


# --------------------------------------------------------------------------- #
# Identificadores numéricos
# --------------------------------------------------------------------------- #

def normalizar_cpf(valor) -> str:
    """Remove pontuação e completa com zeros à esquerda até 11 dígitos."""
    digitos = _RE_NAO_DIGITO.sub("", str(valor or ""))
    if not digitos or int(digitos or 0) == 0:
        return ""
    if len(digitos) > 11:
        digitos = digitos[-11:]
    return digitos.zfill(11)


def cpf_e_valido(valor) -> tuple[bool, str]:
    """Valida o CPF pelos dígitos verificadores (módulo 11)."""
    texto = str(valor or "").strip()
    if not texto:
        return False, "campo em branco"
    cpf = normalizar_cpf(texto)
    if not cpf:
        return False, "CPF nulo ou composto apenas por zeros"
    if len(cpf) != 11:
        return False, f"CPF com {len(cpf)} dígitos (esperados 11)"
    if cpf == cpf[0] * 11:
        return False, "CPF com todos os dígitos iguais"
    for posicao in (9, 10):
        soma = sum(int(cpf[i]) * ((posicao + 1) - i) for i in range(posicao))
        digito = (soma * 10) % 11
        digito = 0 if digito == 10 else digito
        if digito != int(cpf[posicao]):
            return False, "dígito verificador inválido"
    return True, ""


def normalizar_cns(valor) -> str:
    digitos = _RE_NAO_DIGITO.sub("", str(valor or ""))
    return digitos if len(digitos) == 15 else (digitos.zfill(15)
                                               if 0 < len(digitos) < 15 else "")


def cns_e_valido(valor) -> tuple[bool, str]:
    """Valida o Cartão Nacional de Saúde pela regra de soma ponderada (mód. 11)."""
    texto = str(valor or "").strip()
    if not texto:
        return False, "campo em branco"
    digitos = _RE_NAO_DIGITO.sub("", texto)
    if len(digitos) != 15:
        return False, f"CNS com {len(digitos)} dígitos (esperados 15)"
    if digitos == digitos[0] * 15:
        return False, "CNS com todos os dígitos iguais"
    if digitos[0] in "12":   # cartões definitivos
        soma = sum(int(digitos[i]) * (15 - i) for i in range(15))
        if soma % 11 != 0:
            return False, "soma de verificação inválida"
        return True, ""
    if digitos[0] in "789":  # cartões provisórios
        soma = sum(int(digitos[i]) * (15 - i) for i in range(15))
        if soma % 11 != 0:
            return False, "soma de verificação inválida"
        return True, ""
    return False, "primeiro dígito fora do padrão do CNS (1, 2, 7, 8 ou 9)"


def normalizar_codigo(valor, tamanho: int | None = None) -> str:
    """Padroniza códigos numéricos preservando zeros à esquerda."""
    digitos = _RE_NAO_DIGITO.sub("", str(valor or ""))
    if not digitos:
        return ""
    if tamanho and len(digitos) < tamanho:
        digitos = digitos.zfill(tamanho)
    if tamanho and len(digitos) > tamanho:
        digitos = digitos[:tamanho]
    return digitos


def normalizar_cid(valor) -> str:
    """Padroniza código da CID-10: letra maiúscula seguida de dígitos."""
    texto = remover_acentos(str(valor or "")).upper()
    texto = re.sub(r"[^A-Z0-9]", "", texto)
    return texto[:4]


def cid_e_valido(valor) -> tuple[bool, str]:
    texto = str(valor or "").strip()
    if not texto:
        return False, "campo em branco"
    codigo = normalizar_cid(texto)
    if not re.fullmatch(r"[A-Z]\d{2,3}", codigo):
        return False, "código fora do padrão da CID-10 (letra seguida de 2 a 3 dígitos)"
    if codigo[0] in "UV" and codigo[0] == "U" and codigo[1:3] not in ("04", "07", "08", "09", "10", "99"):
        return False, "capítulo U reservado a códigos de uso provisório"
    return True, ""


def normalizar_cep(valor) -> str:
    return normalizar_codigo(valor, 8)


def cep_e_valido(valor) -> tuple[bool, str]:
    texto = str(valor or "").strip()
    if not texto:
        return False, "campo em branco"
    cep = normalizar_cep(texto)
    if len(cep) != 8 or cep == "0" * 8:
        return False, "CEP fora do padrão de 8 dígitos"
    return True, ""


def normalizar_sexo(valor, sigla_sistema: str = "") -> str:
    """Harmoniza o sexo em M, F ou I, qualquer que seja a codificação de origem.

    O SIM e o SINASC codificam 1/2; o SINAN codifica M/F. A harmonização é
    condição para que a variável possa ser comparada entre as bases.
    """
    texto = remover_acentos(str(valor or "")).upper().strip()
    if not texto:
        return ""
    if texto in ("1", "M", "MASC", "MASCULINO", "H", "HOMEM"):
        return "M"
    if texto in ("2", "F", "FEM", "FEMININO", "MULHER"):
        return "F"
    if texto in ("0", "3", "9", "I", "IGN", "IGNORADO", "NAO INFORMADO"):
        return "I"
    return "I"


@lru_cache(maxsize=100_000)
def e_ignorado(valor, natureza: str = "") -> bool:
    """Identifica os códigos convencionados de "ignorado"/"não informado"."""
    texto = remover_acentos(str(valor or "")).upper().strip()
    if not texto:
        return False  # campo em branco é tratado como incompletude, não como ignorado
    if natureza in ("nome", "texto"):
        return texto in NOMES_INVALIDOS
    if natureza in ("cpf", "cns", "cep", "data", "numero"):
        return bool(re.fullmatch(r"9{2,}|0{2,}", texto))
    return texto in CODIGOS_IGNORADO


# --------------------------------------------------------------------------- #
# Aplicação por natureza da variável
# --------------------------------------------------------------------------- #

_NORMALIZADORES = {
    "nome": normalizar_nome,
    "texto": normalizar_texto,
    "data": normalizar_data,
    "cpf": normalizar_cpf,
    "cns": normalizar_cns,
    "cep": normalizar_cep,
    "cid": normalizar_cid,
    "categoria": lambda v: remover_acentos(str(v or "")).upper().strip(),
    "ibge": lambda v: normalizar_codigo(v, 6)[:6],
    "cnes": lambda v: normalizar_codigo(v, 7),
    "numero": lambda v: _RE_NAO_DIGITO.sub("", str(v or "")),
    "codigo": lambda v: remover_acentos(str(v or "")).upper().strip(),
}

_VALIDADORES = {
    "data": data_e_valida,
    "cpf": cpf_e_valido,
    "cns": cns_e_valido,
    "cep": cep_e_valido,
    "cid": cid_e_valido,
    "nome": lambda v: (lambda r: (not r[0], r[1]))(nome_e_invalido(v)),
}


def normalizar_por_natureza(valor, natureza: str, sigla_sistema: str = ""):
    if natureza == "categoria" and sigla_sistema:
        return str(valor or "").strip().upper()
    funcao = _NORMALIZADORES.get(natureza)
    return funcao(valor) if funcao else str(valor or "").strip()


def validar_por_natureza(valor, natureza: str) -> tuple[bool, str]:
    funcao = _VALIDADORES.get(natureza)
    if not funcao:
        texto = str(valor or "").strip()
        return (bool(texto), "" if texto else "campo em branco")
    return funcao(valor)
