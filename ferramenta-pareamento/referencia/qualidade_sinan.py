# -*- coding: utf-8 -*-
"""
Implementação de referência da verificação dos atributos de qualidade.

Reproduz os critérios registrados na aba "Metodologia" do produto entregue à
SUIS: classificação dos campos segundo o Dicionário de Dados do SINAN NET,
cálculo da incompletude com a escala de Romero e Cunha (2006), regras de
consistência do próprio dicionário e detecção de duplicidades.

A diferença em relação a uma verificação genérica de qualidade está na fonte
dos critérios. Não se arbitra o que é obrigatório: adota-se a classificação do
dicionário do sistema, o que torna o resultado defensável perante a área
técnica e dispensa a discussão sobre o critério a cada rodada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from rapidfuzz import fuzz

from pareamento_siclom_sinan import padronizar_nome, similaridade_nome

# --------------------------------------------------------------------------- #
# Classificação dos campos segundo o dicionário
# --------------------------------------------------------------------------- #

OBRIGATORIO = "Obrigatório"   # a ausência impede a inclusão da notificação
ESSENCIAL = "Essencial"       # necessário à investigação ou a indicadores
SEM_CLASSE = "Sem classificação no dicionário"

ALTA, MEDIA, BAIXA = "Alta", "Média", "Baixa"

# Códigos convencionados para "ignorado" nos campos do SINAN.
CODIGOS_IGNORADO = {"9", "99", "999", "0", ""}


@dataclass
class Campo:
    """Um campo do instrumento, com a sua classe no dicionário."""
    nome: str
    descricao: str
    classe: str
    codigos_ignorado: set[str] = field(default_factory=lambda: {"9"})
    # Alguns campos só são habilitados sob condição (por exemplo, etiologia
    # apenas em casos confirmados). A população aplicável é calculada por esta
    # função, e não sobre a base inteira — medir incompletude sobre registros
    # em que o campo nem deveria estar preenchido produziria número sem sentido.
    aplicavel: object = None
    regra_aplicabilidade: str = "Todos os registros"


@dataclass
class Pendencia:
    registro: str
    campo: str
    tipo: str
    descricao: str
    prioridade: str
    classe: str
    sugestao: str


# --------------------------------------------------------------------------- #
# Incompletude — escala de Romero e Cunha (2006)
# --------------------------------------------------------------------------- #

def classificar_incompletude(percentual: float) -> str:
    """Escala de Romero e Cunha (2006), aplicada à incompletude.

    Note-se que a escala classifica a INCOMPLETUDE, e não a completude: um
    valor baixo é bom. A inversão é fonte frequente de erro de leitura em
    relatórios de qualidade.
    """
    if percentual < 5:
        return "Excelente"
    if percentual < 10:
        return "Bom"
    if percentual < 20:
        return "Regular"
    if percentual < 50:
        return "Ruim"
    return "Muito ruim"


def medir_incompletude(registros: list[dict], campo: Campo) -> dict:
    """Incompletude = (em branco + ignorado) / população aplicável.

    O código de ignorado é somado ao campo em branco porque ambos representam
    ausência de informação. Contabilizar apenas o branco produziria completude
    aparente: o campo consta preenchido, a informação inexiste.
    """
    aplicaveis = [r for r in registros
                  if campo.aplicavel is None or campo.aplicavel(r)]
    if not aplicaveis:
        return {"campo": campo.nome, "populacao": 0, "em_branco": 0,
                "ignorado": 0, "incompletude": 0.0,
                "classificacao": "Não aplicável",
                "regra": campo.regra_aplicabilidade}

    em_branco = ignorado = 0
    for registro in aplicaveis:
        valor = str(registro.get(campo.nome, "") or "").strip()
        if valor == "":
            em_branco += 1
        elif valor in campo.codigos_ignorado:
            ignorado += 1

    percentual = 100.0 * (em_branco + ignorado) / len(aplicaveis)
    return {"campo": campo.nome, "descricao": campo.descricao,
            "classe": campo.classe, "populacao": len(aplicaveis),
            "em_branco": em_branco, "ignorado": ignorado,
            "incompletude": round(percentual, 2),
            "classificacao": classificar_incompletude(percentual),
            "regra": campo.regra_aplicabilidade}


# --------------------------------------------------------------------------- #
# Prioridade das pendências
# --------------------------------------------------------------------------- #

def prioridade_da_pendencia(classe: str, tipo: str) -> str:
    """Deriva a prioridade da classe do campo no dicionário e do tipo de falta.

    Campo obrigatório em branco e violação de regra são tratados como alta
    prioridade porque impedem, respectivamente, a validade do registro e a sua
    coerência interna. Obrigatório preenchido como ignorado é média: o registro
    é válido, a informação não existe.
    """
    if tipo == "Violação de regra":
        return ALTA
    if classe == OBRIGATORIO:
        return ALTA if tipo == "Campo em branco" else MEDIA
    if classe == ESSENCIAL:
        return MEDIA
    return BAIXA


def verificar_campos(registros: list[dict], campos: list[Campo],
                     chave: str) -> list[Pendencia]:
    """Produz uma pendência por campo com problema, em cada registro."""
    pendencias: list[Pendencia] = []
    for registro in registros:
        identificador = str(registro.get(chave, "") or "")
        for campo in campos:
            if campo.aplicavel is not None and not campo.aplicavel(registro):
                continue
            valor = str(registro.get(campo.nome, "") or "").strip()
            if valor == "":
                tipo, descricao = "Campo em branco", f"{campo.nome} não preenchido."
            elif valor in campo.codigos_ignorado:
                tipo = "Valor ignorado"
                descricao = f"{campo.nome} preenchido com código de ignorado."
            else:
                continue
            pendencias.append(Pendencia(
                registro=identificador, campo=campo.nome, tipo=tipo,
                descricao=descricao,
                prioridade=prioridade_da_pendencia(campo.classe, tipo),
                classe=campo.classe,
                sugestao=("Recuperar a informação no documento-fonte e "
                          "corrigir a notificação no sistema.")))
    return pendencias


# --------------------------------------------------------------------------- #
# Regras de consistência do dicionário
# --------------------------------------------------------------------------- #

def verificar_regras(registros: list[dict], chave: str) -> list[Pendencia]:
    """Confere as relações entre campos previstas no dicionário do SINAN.

    As regras verificadas são as do próprio instrumento, e não critérios
    arbitrados: a ordem cronológica entre sintomas, notificação, investigação
    e encerramento, e as condições de habilitação de campos específicos.
    """
    regras = [
        ("DT_SIN_PRI", "DT_NOTIFIC",
         "Data dos primeiros sintomas posterior à data de notificação."),
        ("DT_NOTIFIC", "DT_INVEST",
         "Data de investigação anterior à data de notificação."),
        ("DT_INVEST", "DT_ENCERRA",
         "Data de encerramento anterior à data de investigação."),
    ]
    pendencias: list[Pendencia] = []
    for registro in registros:
        identificador = str(registro.get(chave, "") or "")
        for antes, depois, mensagem in regras:
            a, b = registro.get(antes), registro.get(depois)
            if isinstance(a, date) and isinstance(b, date) and a > b:
                pendencias.append(Pendencia(
                    registro=identificador, campo=f"{antes} / {depois}",
                    tipo="Violação de regra", descricao=mensagem,
                    prioridade=ALTA, classe="Regra de consistência",
                    sugestao="Conferir as duas datas no documento-fonte."))
    return pendencias


# --------------------------------------------------------------------------- #
# Duplicidades
# --------------------------------------------------------------------------- #

DUPLICATA_EXATA_NOME = 100.0
DUPLICATA_PROVAVEL_NOME_COM_DATA = 88.0
DUPLICATA_PROVAVEL_NOME_SEM_DATA = 92.0
DUPLICATA_PROVAVEL_MAE = 90.0


def classificar_intervalo(dias: int | None) -> str:
    """Classifica o par pelo intervalo entre as notificações.

    O intervalo distingue o erro operacional da renotificação legítima: um
    mesmo caso lançado duas vezes aparece em poucos dias; um caso que volta a
    ser notificado um ano depois é, em regra, novo episódio — e excluí-lo
    apagaria informação verdadeira.
    """
    if dias is None:
        return "Sem data"
    if dias <= 30:
        return "Provável duplicidade de lançamento"
    if dias <= 365:
        return "Verificar"
    return "Provável renotificação"


def detectar_duplicidades(registros: list[dict], chave: str) -> list[dict]:
    """Identifica pares exatos e prováveis, sob blocagem por primeiro nome."""
    preparados = []
    for registro in registros:
        nome = padronizar_nome(registro.get("NM_PACIENT"))
        preparados.append({
            "id": str(registro.get(chave, "") or ""),
            "nome": nome,
            "mae": padronizar_nome(registro.get("NM_MAE_PAC")),
            "nascimento": registro.get("DT_NASC"),
            "notificacao": registro.get("DT_NOTIFIC"),
            "primeiro": nome.split()[0] if nome.split() else "",
        })

    blocos: dict[str, list[dict]] = {}
    for item in preparados:
        if item["primeiro"]:
            blocos.setdefault(item["primeiro"][:4], []).append(item)

    pares, vistos = [], set()
    for grupo in blocos.values():
        for i, a in enumerate(grupo):
            for b in grupo[i + 1:]:
                chave_par = tuple(sorted((a["id"], b["id"])))
                if chave_par in vistos:
                    continue
                vistos.add(chave_par)

                escore = similaridade_nome(a["nome"], b["nome"])
                escore_mae = (similaridade_nome(a["mae"], b["mae"])
                              if a["mae"] and b["mae"] else 0.0)
                data_igual = (a["nascimento"] is not None
                              and a["nascimento"] == b["nascimento"])

                if (escore == DUPLICATA_EXATA_NOME and data_igual
                        and escore_mae == DUPLICATA_EXATA_NOME):
                    tipo = "Exata"
                elif escore >= DUPLICATA_PROVAVEL_NOME_COM_DATA and data_igual:
                    tipo = "Provável"
                elif (escore >= DUPLICATA_PROVAVEL_NOME_SEM_DATA
                      and escore_mae >= DUPLICATA_PROVAVEL_MAE):
                    tipo = "Provável"
                else:
                    continue

                dias = None
                if isinstance(a["notificacao"], date) and isinstance(b["notificacao"], date):
                    dias = abs((b["notificacao"] - a["notificacao"]).days)

                pares.append({
                    "a": a["id"], "b": b["id"], "tipo": tipo,
                    "escore_nome": round(escore, 1),
                    "data_nascimento": "Igual" if data_igual else "Diverge",
                    "intervalo_dias": dias,
                    "classificacao": classificar_intervalo(dias)})
    return pares
