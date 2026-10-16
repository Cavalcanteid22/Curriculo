# -*- coding: utf-8 -*-
"""
Implementação de referência do pareamento SICLOM x SINAN (HEPANET).

Reproduz os critérios, pesos e pontos de corte registrados na aba
"Metodologia" do produto entregue à SUIS em outubro de 2026. Serve a dois
propósitos: documentar o método de forma executável, para que a dissertação
possa ser verificada, e permitir a reexecução da rotina em competências
futuras.

Premissa central: o número da notificação do SINAN, quando informado no
cadastro do SICLOM, é tratado como padrão de referência — é o único vínculo
declarado entre os dois sistemas. Todo o restante do procedimento consiste em
suprir a sua ausência, que ocorre em mais da metade dos cadastros.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from rapidfuzz import fuzz

# --------------------------------------------------------------------------- #
# Parâmetros do método
# --------------------------------------------------------------------------- #

# Pesos do escore composto. Somam 1,00 quando todas as variáveis estão
# presentes; na ausência do nome da mãe ou da data de nascimento, o peso é
# redistribuído entre as variáveis remanescentes, e não descontado — descontá-lo
# penalizaria o par pela incompletude do cadastro, e não pela falta de
# evidência de identidade.
PESOS = {
    "nome": 0.35,
    "primeiro_nome": 0.10,
    "ultimo_nome": 0.10,
    "nome_mae": 0.25,
    "data_nascimento": 0.20,
}

# Blocagem: um par só é avaliado quando satisfaz uma destas condições. Sem ela,
# o cruzamento de 900 cadastros com 4.213 notificações exigiria 3,8 milhões de
# comparações.
BLOCAGEM_PRIMEIRO_NOME = 80.0
BLOCAGEM_NOME_COM_DATA = 60.0

# Pontos de corte da decisão.
CORTE_NOME_COM_DATA_EXATA = 88.0   # correspondência aceita
CORTE_NOME_REVISAO = 90.0          # revisão manual, sem data exata
CORTE_COMPOSTO_REVISAO = 80.0      # revisão manual, pelo escore composto
CORTE_NOME_COMPOSTO = 80.0

# Confirmação pelo nome da mãe — não decide o par, qualifica-o.
MAE_CONFERE = 85.0
MAE_PARCIAL = 70.0

# Similaridade mínima para aceitar o vínculo declarado pelo número SINAN.
CORTE_VALIDACAO_CHAVE_DIRETA = 80.0

# Pontuação atribuída à data de nascimento.
DATA_EXATA = 100.0
DATA_PARCIAL = 60.0   # inversão dia-mês ou coincidência parcial
DATA_DIVERGENTE = 0.0


# --------------------------------------------------------------------------- #
# Padronização
# --------------------------------------------------------------------------- #

_RE_NAO_ALFA = re.compile(r"[^A-Z\s]")
_RE_ESPACOS = re.compile(r"\s+")


def padronizar_nome(valor) -> str:
    """Caixa alta, sem acentos, sem caracteres não alfabéticos, sem espaços duplos.

    O valor original é preservado nas saídas: a padronização existe para a
    comparação, não para substituir o dado registrado.
    """
    if valor is None:
        return ""
    decomposto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in decomposto if not unicodedata.combining(c)).upper()
    return _RE_ESPACOS.sub(" ", _RE_NAO_ALFA.sub(" ", texto)).strip()


def primeiro_e_ultimo(nome_padronizado: str) -> tuple[str, str]:
    """Separa o primeiro nome e o último sobrenome.

    Ambos entram no escore com peso próprio porque erram de modo distinto: o
    primeiro nome raramente é abreviado, ao passo que o sobrenome final é o
    que mais sofre supressão nos cadastros.
    """
    partes = [p for p in nome_padronizado.split() if len(p) > 1]
    if not partes:
        return "", ""
    return partes[0], partes[-1]


def normalizar_numero_sinan(valor) -> str:
    """Retém apenas os dígitos e remove zeros à esquerda.

    O SICLOM registra o número da notificação como texto digitado pelo
    operador; o SINAN o armazena com preenchimento à esquerda. Sem esta
    normalização, vínculos declarados corretamente deixam de ser reconhecidos.
    """
    digitos = re.sub(r"\D", "", str(valor or ""))
    return digitos.lstrip("0")


# --------------------------------------------------------------------------- #
# Similaridade
# --------------------------------------------------------------------------- #

def similaridade_nome(a: str, b: str) -> float:
    """token_sort_ratio: insensível à ordem dos componentes do nome.

    A escolha responde a uma característica dos cadastros: a inversão entre
    prenome e sobrenome é frequente, e uma métrica sensível à ordem a trataria
    como divergência.
    """
    if not a or not b:
        return 0.0
    return float(fuzz.token_sort_ratio(a, b))


def pontuar_data(a: date | None, b: date | None) -> float:
    """Pontua a coincidência entre datas de nascimento.

    A inversão entre dia e mês é o erro de transcrição mais comum em data de
    nascimento e recebe pontuação intermediária, em vez de ser tratada como
    divergência total.
    """
    if a is None or b is None:
        return DATA_DIVERGENTE
    if a == b:
        return DATA_EXATA
    if a.year == b.year and a.day == b.month and a.month == b.day:
        return DATA_PARCIAL
    if a.year == b.year and (a.month == b.month or a.day == b.day):
        return DATA_PARCIAL
    return DATA_DIVERGENTE


def escore_composto(escores: dict[str, float | None]) -> float:
    """Média ponderada com redistribuição do peso das variáveis ausentes."""
    presentes = {k: v for k, v in escores.items() if v is not None}
    if not presentes:
        return 0.0
    peso_total = sum(PESOS[k] for k in presentes)
    if peso_total == 0:
        return 0.0
    return sum(PESOS[k] * v for k, v in presentes.items()) / peso_total


# --------------------------------------------------------------------------- #
# Estruturas
# --------------------------------------------------------------------------- #

@dataclass
class Usuario:
    """Cadastro do SICLOM."""
    identificador: str
    nome: str
    nome_mae: str = ""
    data_nascimento: date | None = None
    numero_sinan: str = ""
    cpf: str = ""

    def __post_init__(self):
        self.nome_p = padronizar_nome(self.nome)
        self.mae_p = padronizar_nome(self.nome_mae)
        self.primeiro, self.ultimo = primeiro_e_ultimo(self.nome_p)
        self.sinan_n = normalizar_numero_sinan(self.numero_sinan)


@dataclass
class Notificacao:
    """Registro do HEPANET/SINAN."""
    numero: str
    nome: str
    nome_mae: str = ""
    data_nascimento: date | None = None

    def __post_init__(self):
        self.nome_p = padronizar_nome(self.nome)
        self.mae_p = padronizar_nome(self.nome_mae)
        self.primeiro, self.ultimo = primeiro_e_ultimo(self.nome_p)
        self.numero_n = normalizar_numero_sinan(self.numero)


@dataclass
class Resultado:
    usuario: Usuario
    notificacao: Notificacao | None
    codigo: str
    categoria: str
    escore_nome: float = 0.0
    escore_mae: float | None = None
    escore_composto: float = 0.0
    pontuacao_data: float = 0.0
    mae_confere: str = "Sem dado"
    localizado_por_nome_e_data: bool = False
    acao: str = ""


CATEGORIAS = {
    "1": "Confirmado — vínculo direto (número SINAN localizado)",
    "2": ("Divergência — número informado não localizado (ou pertencente a "
          "outro paciente), mas nome + data de nascimento conferem"),
    "3": ("Correspondência provável por nome + data de nascimento (sem número "
          "SINAN no SICLOM)"),
    "4A": "Revisão manual — nome localizado, data de nascimento não confere",
    "4B": "Revisão manual — número SINAN localizado, mas pertence a outro paciente",
    "5": ("Divergência — número não localizado; nome similar, mas data de "
          "nascimento diverge/ausente"),
    "6": "Divergência — número informado não localizado e sem correspondência por nome",
    "7": "Não notificado no SINAN — possível subnotificação",
}


# --------------------------------------------------------------------------- #
# Blocagem e comparação
# --------------------------------------------------------------------------- #

def candidatos(usuario: Usuario,
               notificacoes: Iterable[Notificacao]) -> list[Notificacao]:
    """Restringe as comparações aos pares plausíveis.

    Duas portas de entrada, e basta uma: similaridade do primeiro nome
    suficientemente alta, ou data de nascimento idêntica com alguma
    similaridade de nome. A segunda recupera casos em que o prenome foi
    registrado de forma muito diferente nos dois sistemas.
    """
    selecionados = []
    for notificacao in notificacoes:
        if (usuario.primeiro and notificacao.primeiro
                and similaridade_nome(usuario.primeiro,
                                      notificacao.primeiro) >= BLOCAGEM_PRIMEIRO_NOME):
            selecionados.append(notificacao)
            continue
        if (usuario.data_nascimento
                and usuario.data_nascimento == notificacao.data_nascimento
                and similaridade_nome(usuario.nome_p,
                                      notificacao.nome_p) >= BLOCAGEM_NOME_COM_DATA):
            selecionados.append(notificacao)
    return selecionados


def comparar(usuario: Usuario, notificacao: Notificacao) -> dict:
    """Calcula os escores de um par candidato."""
    escore_nome = similaridade_nome(usuario.nome_p, notificacao.nome_p)
    escore_mae = (similaridade_nome(usuario.mae_p, notificacao.mae_p)
                  if usuario.mae_p and notificacao.mae_p else None)
    pontuacao_data = pontuar_data(usuario.data_nascimento,
                                  notificacao.data_nascimento)
    tem_data = (usuario.data_nascimento is not None
                and notificacao.data_nascimento is not None)

    composto = escore_composto({
        "nome": escore_nome,
        "primeiro_nome": similaridade_nome(usuario.primeiro, notificacao.primeiro),
        "ultimo_nome": similaridade_nome(usuario.ultimo, notificacao.ultimo),
        "nome_mae": escore_mae,
        "data_nascimento": pontuacao_data if tem_data else None,
    })

    if escore_mae is None:
        mae = "Sem dado"
    elif escore_mae >= MAE_CONFERE:
        mae = "Confere"
    elif escore_mae >= MAE_PARCIAL:
        mae = "Parcial"
    else:
        mae = "Não confere"

    return {"notificacao": notificacao, "escore_nome": escore_nome,
            "escore_mae": escore_mae, "escore_composto": composto,
            "pontuacao_data": pontuacao_data, "mae_confere": mae,
            "data_exata": pontuacao_data == DATA_EXATA}


def melhor_candidato(usuario: Usuario,
                     notificacoes: Iterable[Notificacao]) -> dict | None:
    """Escolhe o candidato de maior escore composto dentro do bloco."""
    avaliados = [comparar(usuario, n) for n in candidatos(usuario, notificacoes)]
    if not avaliados:
        return None
    return max(avaliados, key=lambda a: (a["data_exata"], a["escore_composto"]))


# --------------------------------------------------------------------------- #
# Classificação
# --------------------------------------------------------------------------- #

def classificar(usuario: Usuario, notificacoes: list[Notificacao]) -> Resultado:
    """Atribui ao usuário uma das categorias de 1 a 7.

    A ordem das verificações reproduz a hierarquia de evidência: o vínculo
    declarado pelo número SINAN é examinado primeiro, mas só é aceito se o
    nome do paciente for compatível — a conferência existe porque o número é
    digitado manualmente no SICLOM e pode pertencer a outro paciente, situação
    que deu origem à categoria 4B.
    """
    por_numero = {n.numero_n: n for n in notificacoes if n.numero_n}
    candidato = melhor_candidato(usuario, notificacoes)
    localizado_por_nome = bool(
        candidato and candidato["data_exata"]
        and candidato["escore_nome"] >= CORTE_NOME_COM_DATA_EXATA)

    def montar(codigo, acao):
        return Resultado(
            usuario=usuario,
            notificacao=candidato["notificacao"] if candidato else None,
            codigo=codigo, categoria=CATEGORIAS[codigo],
            escore_nome=candidato["escore_nome"] if candidato else 0.0,
            escore_mae=candidato["escore_mae"] if candidato else None,
            escore_composto=candidato["escore_composto"] if candidato else 0.0,
            pontuacao_data=candidato["pontuacao_data"] if candidato else 0.0,
            mae_confere=candidato["mae_confere"] if candidato else "Sem dado",
            localizado_por_nome_e_data=localizado_por_nome, acao=acao)

    # --- O SICLOM declara um número de notificação ---------------------- #
    if usuario.sinan_n:
        declarada = por_numero.get(usuario.sinan_n)
        if declarada is not None:
            confere = comparar(usuario, declarada)
            if (confere["escore_nome"] >= CORTE_VALIDACAO_CHAVE_DIRETA
                    or confere["data_exata"]):
                resultado = montar("1", "Nenhuma — vínculo confirmado.")
                resultado.notificacao = declarada
                resultado.escore_nome = confere["escore_nome"]
                resultado.escore_mae = confere["escore_mae"]
                resultado.escore_composto = confere["escore_composto"]
                resultado.mae_confere = confere["mae_confere"]
                return resultado
            # O número existe, mas identifica outro paciente.
            return montar("4B", "Conferir: o número informado pertence a "
                                "outro paciente. Corrigir no SICLOM.")
        # O número informado não existe na base.
        if localizado_por_nome:
            return montar("2", "Corrigir o número da notificação no SICLOM "
                               "com o número localizado por nome e data.")
        if candidato and candidato["escore_nome"] >= CORTE_NOME_REVISAO:
            return montar("5", "Revisão manual: nome similar sem data "
                               "coincidente.")
        return montar("6", "Busca ativa: conferir se há notificação com dados "
                           "divergentes ou em outro município.")

    # --- O SICLOM não declara número ------------------------------------ #
    if localizado_por_nome:
        return montar("3", "Registrar no SICLOM o número da notificação "
                           "localizada.")
    if candidato and (candidato["escore_nome"] >= CORTE_NOME_REVISAO
                      or (candidato["escore_composto"] >= CORTE_COMPOSTO_REVISAO
                          and candidato["escore_nome"] >= CORTE_NOME_COMPOSTO)):
        return montar("4A", "Revisão manual: nome localizado, data de "
                            "nascimento não confere.")
    return montar("7", "Busca ativa: possível subnotificação. Verificar se o "
                       "caso foi notificado.")
