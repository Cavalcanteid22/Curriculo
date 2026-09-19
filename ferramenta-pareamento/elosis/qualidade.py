# -*- coding: utf-8 -*-
"""
Qualificação das bases segundo os atributos de qualidade (ELO-SIS).

Operacionaliza as dimensões identificadas por Ghalavand et al. (2024) em
revisão sistemática de 58 estudos. O projeto adota como prioritárias a
acurácia, a completude e a consistência — dimensões rotineiramente avaliadas
na SUIS —, acrescidas da oportunidade, apontada pelos autores entre as três
mais empregadas na literatura.

Cada achado produz um registro com: variável afetada, natureza do problema,
gravidade, descrição em linguagem corrente, justificativa técnico-normativa e
recomendação de correção dirigida à área técnica responsável.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from . import normalizacao as nz
from .perfis import (CODIGO_IBGE_SALVADOR, NATUREZA, ROTULOS_CANONICOS,
                     PerfilSistema)

# --------------------------------------------------------------------------- #
# Classificação de linhas
# --------------------------------------------------------------------------- #

VERDE = "VERDE"
AMARELO = "AMARELO"
VERMELHO = "VERMELHO"

SIGNIFICADO_CLASSIFICACAO = {
    VERDE: ("Sem inconsistências detectadas. Registro apto ao uso analítico e "
            "ao pareamento."),
    AMARELO: ("Provável inconsistência. Exige verificação manual pela área "
              "técnica antes do uso analítico."),
    VERMELHO: ("Inconsistência real. Registro com erro objetivo que demanda "
               "correção na base nativa."),
}

# Gravidade de cada tipo de achado.
GRAVE = VERMELHO
SUSPEITO = AMARELO


@dataclass
class Achado:
    """Um problema identificado em um registro específico."""
    linha: int
    variavel: str
    tipo: str
    gravidade: str
    descricao: str
    valor_observado: str
    justificativa: str
    recomendacao: str
    dimensao: str

    def como_dicionario(self, base: str) -> dict:
        return {
            "BASE": base,
            "LINHA": self.linha,
            "VARIAVEL": self.variavel,
            "ROTULO": ROTULOS_CANONICOS.get(self.variavel, self.variavel),
            "DIMENSAO_QUALIDADE": self.dimensao,
            "TIPO_INCONSISTENCIA": self.tipo,
            "GRAVIDADE": self.gravidade,
            "VALOR_OBSERVADO": self.valor_observado,
            "DESCRICAO": self.descricao,
            "JUSTIFICATIVA": self.justificativa,
            "RECOMENDACAO": self.recomendacao,
        }


@dataclass
class ResultadoQualidade:
    """Consolida a qualificação de uma base."""
    sigla: str
    arquivo: str
    perfil: PerfilSistema
    total_registros: int
    mapeamento: dict[str, str]
    achados: list[Achado] = field(default_factory=list)
    completude: list[dict] = field(default_factory=list)
    acuracia: list[dict] = field(default_factory=list)
    consistencia: list[dict] = field(default_factory=list)
    oportunidade: list[dict] = field(default_factory=list)
    variaveis_ausentes: list[str] = field(default_factory=list)
    classificacao_linhas: pd.Series | None = None
    escore_global: float = 0.0

    def achados_por_linha(self) -> dict[int, list[Achado]]:
        indice: dict[int, list[Achado]] = defaultdict(list)
        for achado in self.achados:
            indice[achado.linha].append(achado)
        return indice

    def contagem_por_classificacao(self) -> dict[str, int]:
        if self.classificacao_linhas is None:
            return {VERDE: 0, AMARELO: 0, VERMELHO: 0}
        contagem = Counter(self.classificacao_linhas)
        return {cor: int(contagem.get(cor, 0)) for cor in (VERDE, AMARELO, VERMELHO)}


# --------------------------------------------------------------------------- #
# Regras de validação por variável
# --------------------------------------------------------------------------- #

_JUSTIFICATIVA_OBRIGATORIO = (
    "Campo de preenchimento obrigatório no instrumento de coleta. A ausência "
    "impede o cálculo de indicadores e inviabiliza o relacionamento de bases."
)
_JUSTIFICATIVA_IGNORADO = (
    "O preenchimento com código de 'ignorado' é admitido pelo sistema, mas "
    "equivale à perda de informação: o campo consta preenchido nas estatísticas "
    "de completude sem que o dado exista."
)


def _achado(linha, variavel, tipo, gravidade, descricao, valor, justificativa,
            recomendacao, dimensao) -> Achado:
    return Achado(linha=linha, variavel=variavel, tipo=tipo, gravidade=gravidade,
                  descricao=descricao, valor_observado=str(valor)[:120],
                  justificativa=justificativa, recomendacao=recomendacao,
                  dimensao=dimensao)


def _avaliar_obrigatorios(quadro: pd.DataFrame, perfil: PerfilSistema,
                          mapeamento: dict[str, str]) -> list[Achado]:
    """Campos obrigatórios em branco ou preenchidos com código de ignorado."""
    achados: list[Achado] = []
    for canonica, fundamento in perfil.obrigatorios.items():
        coluna = mapeamento.get(canonica)
        rotulo = ROTULOS_CANONICOS.get(canonica, canonica)
        if not coluna:
            continue
        natureza = NATUREZA.get(canonica, "texto")
        serie = quadro[coluna].astype(str).str.strip()

        vazios = serie == ""
        for linha in quadro.index[vazios]:
            achados.append(_achado(
                linha, canonica, "CAMPO_OBRIGATORIO_EM_BRANCO", GRAVE,
                f"O campo obrigatório '{rotulo}' está em branco.",
                "", f"{_JUSTIFICATIVA_OBRIGATORIO} Fundamento: {fundamento}",
                f"Recuperar o valor no documento-fonte ({perfil.instrumento}) e "
                f"corrigir o registro no {perfil.sigla}.",
                "Completude"))

        for linha in quadro.index[~vazios]:
            valor = serie.at[linha]
            if nz.e_ignorado(valor, natureza):
                achados.append(_achado(
                    linha, canonica, "CAMPO_OBRIGATORIO_IGNORADO", SUSPEITO,
                    f"O campo obrigatório '{rotulo}' está preenchido com código "
                    f"de ignorado/não informado ('{valor}').",
                    valor, f"{_JUSTIFICATIVA_IGNORADO} Fundamento: {fundamento}",
                    f"Verificar no documento-fonte se a informação existe; "
                    f"havendo, substituir o código de ignorado pelo valor real.",
                    "Completude"))
    return achados


def _avaliar_dominios_e_formatos(quadro: pd.DataFrame, perfil: PerfilSistema,
                                 mapeamento: dict[str, str]) -> list[Achado]:
    """Acurácia: valores fora do domínio ou fora do formato esperado."""
    achados: list[Achado] = []
    for canonica, coluna in mapeamento.items():
        natureza = NATUREZA.get(canonica, "texto")
        rotulo = ROTULOS_CANONICOS.get(canonica, canonica)
        serie = quadro[coluna].astype(str).str.strip()
        dominio = perfil.dominios.get(canonica)
        chaves_dominio = ({k.upper() for k in dominio} if dominio else set())

        for linha, valor in serie.items():
            if not valor:
                continue

            if dominio is not None:
                chave = nz.remover_acentos(valor).upper().strip()
                if chave not in dominio and chave not in chaves_dominio:
                    achados.append(_achado(
                        linha, canonica, "VALOR_FORA_DO_DOMINIO", GRAVE,
                        f"O campo '{rotulo}' contém o valor '{valor}', que não "
                        f"pertence ao domínio do {perfil.sigla}.",
                        valor,
                        "Valor fora do conjunto de códigos válidos do sistema. "
                        f"Domínio admitido: {', '.join(f'{k}={v}' for k, v in list(dominio.items())[:8])}.",
                        "Corrigir o código conforme a tabela de domínio do "
                        f"{perfil.sigla}; se o valor real for desconhecido, "
                        "registrar o código de ignorado previsto no instrumento.",
                        "Acurácia"))
                continue

            if natureza in ("data", "cpf", "cns", "cep", "cid", "nome"):
                valido, motivo = nz.validar_por_natureza(valor, natureza)
                if not valido and motivo != "campo em branco":
                    gravidade = GRAVE if natureza != "nome" else SUSPEITO
                    if natureza == "nome":
                        descricao = (f"O campo '{rotulo}' contém preenchimento "
                                     f"que não caracteriza nome de pessoa: {motivo}.")
                        recomendacao = (
                            "Conferir o documento-fonte. Em recém-nascidos sem "
                            "nome atribuído, adotar a convenção 'RN DE <nome da "
                            "mãe>' e garantir o preenchimento do nome da mãe, "
                            "que passa a ser a chave de pareamento disponível.")
                        justificativa = (
                            "Campos nominais preenchidos com marcadores genéricos "
                            "reduzem a sensibilidade do pareamento e impedem a "
                            "identificação do caso pela área técnica.")
                    else:
                        descricao = (f"O campo '{rotulo}' contém o valor "
                                     f"'{valor}', inválido: {motivo}.")
                        recomendacao = (
                            f"Corrigir o valor no {perfil.sigla} a partir do "
                            f"documento-fonte ({perfil.instrumento}).")
                        justificativa = (
                            "Valor que não satisfaz a regra de formação da "
                            "variável. Dados inválidos propagam-se aos "
                            "indicadores e produzem pareamentos falsos.")
                    achados.append(_achado(linha, canonica,
                                           f"{natureza.upper()}_INVALIDO",
                                           gravidade, descricao, valor,
                                           justificativa, recomendacao,
                                           "Acurácia"))
    return achados


def _avaliar_coerencia_interna(quadro: pd.DataFrame, perfil: PerfilSistema,
                               mapeamento: dict[str, str]) -> list[Achado]:
    """Consistência: relações lógicas entre variáveis do mesmo registro."""
    achados: list[Achado] = []
    col = mapeamento.get
    vazio = [""] * len(quadro)

    def valores(canonica) -> list[str]:
        coluna = col(canonica)
        if not coluna:
            return list(vazio)
        return quadro[coluna].astype(str).str.strip().tolist()

    def presente(canonica) -> bool:
        return bool(col(canonica))

    nascimento = valores("DATA_NASCIMENTO")
    evento = valores("DATA_EVENTO")
    sintomas = valores("DATA_SINTOMAS")
    encerramento = valores("DATA_ENCERRAMENTO")
    obito = valores("DATA_OBITO")
    registro = valores("DATA_REGISTRO")
    sexo = valores("SEXO")
    municipio = valores("MUNICIPIO_RESIDENCIA")
    peso = valores("PESO_NASCIMENTO")
    evolucao = valores("EVOLUCAO")

    tem_sexo = presente("SEXO")
    tem_municipio = presente("MUNICIPIO_RESIDENCIA")
    tem_peso = presente("PESO_NASCIMENTO")
    tem_evolucao = presente("EVOLUCAO")

    hoje = date.today()
    indices = list(quadro.index)

    for posicao, linha in enumerate(indices):
        dn = nz.normalizar_data(nascimento[posicao])
        de = nz.normalizar_data(evento[posicao])
        ds = nz.normalizar_data(sintomas[posicao])
        dc = nz.normalizar_data(encerramento[posicao])
        do = nz.normalizar_data(obito[posicao])
        dr = nz.normalizar_data(registro[posicao])

        # 1. Evento anterior ao nascimento
        if dn and de and de < dn:
            achados.append(_achado(
                linha, "DATA_EVENTO", "EVENTO_ANTERIOR_AO_NASCIMENTO", GRAVE,
                f"A data do evento ({de}) é anterior à data de nascimento ({dn}).",
                de,
                "Impossibilidade lógica: nenhum evento de saúde do indivíduo "
                "pode preceder o seu nascimento. Indica erro de digitação em "
                "uma das duas datas.",
                "Conferir ambas as datas no documento-fonte e corrigir a que "
                "estiver equivocada. Verificar inversão entre dia e mês.",
                "Consistência"))

        # 2. Idade implausível
        if dn and de:
            anos = nz.idade_em_anos(dn, de)
            if anos is not None and anos > 120:
                achados.append(_achado(
                    linha, "DATA_NASCIMENTO", "IDADE_IMPLAUSIVEL", GRAVE,
                    f"A data de nascimento implica idade de {anos} anos na data "
                    f"do evento.",
                    dn,
                    "Idade superior a 120 anos. A longevidade máxima documentada "
                    "torna o valor incompatível com registro válido; a causa mais "
                    "frequente é erro no ano de nascimento.",
                    "Conferir o ano de nascimento no documento-fonte.",
                    "Consistência"))
            elif anos is not None and 105 < anos <= 120:
                achados.append(_achado(
                    linha, "DATA_NASCIMENTO", "IDADE_MUITO_ELEVADA", SUSPEITO,
                    f"A data de nascimento implica idade de {anos} anos na data "
                    f"do evento.",
                    dn,
                    "Idade possível, porém rara. Registros nessa faixa "
                    "concentram erros de digitação do ano de nascimento.",
                    "Conferir o ano de nascimento no documento-fonte; "
                    "confirmando-se, manter o registro.",
                    "Consistência"))

        # 3. Sintomas posteriores à notificação
        if ds and de and ds > de:
            achados.append(_achado(
                linha, "DATA_SINTOMAS", "SINTOMAS_APOS_NOTIFICACAO", GRAVE,
                f"A data dos primeiros sintomas ({ds}) é posterior à data da "
                f"notificação ({de}).",
                ds,
                "Impossibilidade lógica: a notificação decorre da suspeita "
                "clínica, que pressupõe sintomas já instalados.",
                "Conferir as duas datas na Ficha Individual de Notificação.",
                "Consistência"))

        # 4. Encerramento anterior à notificação
        if dc and de and dc < de:
            achados.append(_achado(
                linha, "DATA_ENCERRAMENTO", "ENCERRAMENTO_ANTES_DA_NOTIFICACAO",
                GRAVE,
                f"A data de encerramento ({dc}) é anterior à data da notificação "
                f"({de}).",
                dc,
                "Impossibilidade lógica na sequência do fluxo de investigação.",
                "Corrigir a data de encerramento no SINAN.",
                "Consistência"))

        # 5. Data de digitação anterior ao evento
        if dr and de and dr < de:
            achados.append(_achado(
                linha, "DATA_REGISTRO", "DIGITACAO_ANTERIOR_AO_EVENTO", SUSPEITO,
                f"A data de digitação ({dr}) é anterior à data do evento ({de}).",
                dr,
                "O registro não pode ser digitado antes de o evento ocorrer. "
                "Ocorre por erro de digitação ou por data de sistema incorreta "
                "na estação de trabalho.",
                "Conferir a data de digitação e o relógio da estação usada na "
                "alimentação do sistema.",
                "Consistência"))

        # 6. Óbito registrado sem evolução compatível (SINAN)
        if do and tem_evolucao:
            codigo_evolucao = evolucao[posicao]
            if codigo_evolucao and codigo_evolucao not in ("2", "3"):
                achados.append(_achado(
                    linha, "EVOLUCAO", "OBITO_SEM_EVOLUCAO_COMPATIVEL", SUSPEITO,
                    f"Há data de óbito preenchida ({do}), mas a evolução do caso "
                    f"está registrada como '{codigo_evolucao}'.",
                    codigo_evolucao,
                    "Divergência interna: a existência de data de óbito implica "
                    "evolução para óbito (códigos 2 ou 3 no SINAN).",
                    "Conferir o desfecho do caso e harmonizar os dois campos; "
                    "o cruzamento com o SIM permite confirmar o óbito.",
                    "Consistência"))

        # 7. Data futura
        for canonica, valor in (("DATA_EVENTO", de), ("DATA_NASCIMENTO", dn),
                                ("DATA_REGISTRO", dr), ("DATA_OBITO", do)):
            if valor and date.fromisoformat(valor) > hoje:
                achados.append(_achado(
                    linha, canonica, "DATA_FUTURA", GRAVE,
                    f"O campo '{ROTULOS_CANONICOS.get(canonica, canonica)}' "
                    f"contém a data {valor}, posterior à data de hoje.",
                    valor,
                    "Datas futuras não correspondem a eventos ocorridos e "
                    "distorcem séries temporais e indicadores de oportunidade.",
                    "Corrigir a data no sistema de origem.",
                    "Acurácia"))

        # 8. Município de residência fora de Salvador
        if tem_municipio:
            codigo = nz.normalizar_codigo(municipio[posicao], 6)[:6]
            if codigo and codigo != CODIGO_IBGE_SALVADOR:
                achados.append(_achado(
                    linha, "MUNICIPIO_RESIDENCIA", "RESIDENCIA_FORA_DO_MUNICIPIO",
                    SUSPEITO,
                    f"O município de residência informado ({codigo}) não é "
                    f"Salvador ({CODIGO_IBGE_SALVADOR}).",
                    codigo,
                    "O recorte territorial do projeto abrange residentes de "
                    "Salvador. Registros de não residentes devem ser remetidos "
                    "ao município de residência, conforme o princípio da "
                    "territorialização da vigilância.",
                    "Confirmar o endereço no documento-fonte. Confirmando-se a "
                    "residência em outro município, proceder à transferência do "
                    "registro conforme fluxo pactuado na CIB.",
                    "Consistência"))

        # 9. Peso ao nascer implausível (SINASC)
        if tem_peso:
            valor_peso = nz.normalizar_codigo(peso[posicao])
            if valor_peso and valor_peso.isdigit():
                gramas = int(valor_peso)
                if gramas and (gramas < 200 or gramas > 7000):
                    achados.append(_achado(
                        linha, "PESO_NASCIMENTO", "PESO_IMPLAUSIVEL", GRAVE,
                        f"O peso ao nascer registrado ({gramas} g) está fora do "
                        f"intervalo biologicamente plausível.",
                        gramas,
                        "Pesos abaixo de 200 g ou acima de 7.000 g são "
                        "incompatíveis com nascido vivo. Erro frequente: "
                        "registro em quilogramas em campo que espera gramas.",
                        "Conferir o peso na Declaração de Nascido Vivo e "
                        "registrar o valor em gramas.",
                        "Acurácia"))
                elif gramas and gramas < 500:
                    achados.append(_achado(
                        linha, "PESO_NASCIMENTO", "PESO_MUITO_BAIXO", SUSPEITO,
                        f"O peso ao nascer registrado ({gramas} g) é extremamente "
                        f"baixo.",
                        gramas,
                        "Peso abaixo de 500 g caracteriza limite de viabilidade; "
                        "exige conferência para distinguir nascido vivo de óbito "
                        "fetal.",
                        "Conferir a DN e, se for o caso, verificar a "
                        "classificação do evento (nascido vivo versus óbito fetal).",
                        "Consistência"))

        # 10. Sexo ignorado
        if tem_sexo:
            codigo_sexo = nz.normalizar_sexo(sexo[posicao])
            if codigo_sexo == "I" and sexo[posicao]:
                achados.append(_achado(
                    linha, "SEXO", "SEXO_IGNORADO", SUSPEITO,
                    "O campo sexo está registrado como ignorado.",
                    sexo[posicao],
                    "O sexo é variável de estratificação obrigatória em todos os "
                    "indicadores de vigilância e atua como variável auxiliar de "
                    "corroboração no pareamento.",
                    "Recuperar a informação no documento-fonte.",
                    "Completude"))
    return achados


# --------------------------------------------------------------------------- #
# Métricas por dimensão
# --------------------------------------------------------------------------- #

def calcular_completude(quadro: pd.DataFrame, perfil: PerfilSistema,
                        mapeamento: dict[str, str]) -> list[dict]:
    """Proporção de registros com preenchimento válido, por variável.

    Distingue três situações que a literatura frequentemente confunde: campo
    em branco, campo preenchido com código de ignorado e campo preenchido com
    valor útil. Apenas a terceira constitui completude efetiva.
    """
    total = len(quadro)
    linhas = []
    for canonica, coluna in mapeamento.items():
        natureza = NATUREZA.get(canonica, "texto")
        serie = quadro[coluna].astype(str).str.strip()
        em_branco = int((serie == "").sum())
        # A contagem distinta é pequena; avaliar uma vez por valor único e
        # multiplicar pela frequência evita percorrer a base inteira.
        frequencias = serie[serie != ""].value_counts()
        ignorados = int(sum(quantidade for valor, quantidade in frequencias.items()
                            if nz.e_ignorado(valor, natureza)))
        preenchidos = total - em_branco
        uteis = preenchidos - ignorados
        obrigatorio = canonica in perfil.obrigatorios
        linhas.append({
            "BASE": perfil.sigla,
            "VARIAVEL": canonica,
            "ROTULO": ROTULOS_CANONICOS.get(canonica, canonica),
            "CAMPO_NA_ORIGEM": coluna,
            "OBRIGATORIO": "Sim" if obrigatorio else "Não",
            "TOTAL_REGISTROS": total,
            "PREENCHIDOS": preenchidos,
            "EM_BRANCO": em_branco,
            "IGNORADOS": ignorados,
            "PREENCHIMENTO_UTIL": uteis,
            "COMPLETUDE_BRUTA_%": round(100 * preenchidos / total, 2) if total else 0.0,
            "COMPLETUDE_UTIL_%": round(100 * uteis / total, 2) if total else 0.0,
            "CLASSIFICACAO": _classificar_completude(100 * uteis / total if total else 0),
        })
    return sorted(linhas, key=lambda l: (l["OBRIGATORIO"] == "Não",
                                         l["COMPLETUDE_UTIL_%"]))


def _classificar_completude(percentual: float) -> str:
    """Escala de Romero e Cunha, usual na avaliação de bases do SUS."""
    if percentual >= 95:
        return "Excelente"
    if percentual >= 90:
        return "Bom"
    if percentual >= 70:
        return "Regular"
    if percentual >= 50:
        return "Ruim"
    return "Muito ruim"


def calcular_acuracia(quadro: pd.DataFrame, achados: list[Achado],
                      perfil: PerfilSistema,
                      mapeamento: dict[str, str]) -> list[dict]:
    """Proporção de registros com valores compatíveis com o domínio da variável."""
    total = len(quadro)
    por_variavel: dict[str, set[int]] = defaultdict(set)
    for achado in achados:
        if achado.dimensao == "Acurácia":
            por_variavel[achado.variavel].add(achado.linha)

    linhas = []
    for canonica, coluna in mapeamento.items():
        serie = quadro[coluna].astype(str).str.strip()
        avaliaveis = int((serie != "").sum())
        invalidos = len(por_variavel.get(canonica, ()))
        validos = max(0, avaliaveis - invalidos)
        linhas.append({
            "BASE": perfil.sigla,
            "VARIAVEL": canonica,
            "ROTULO": ROTULOS_CANONICOS.get(canonica, canonica),
            "CAMPO_NA_ORIGEM": coluna,
            "REGISTROS_AVALIAVEIS": avaliaveis,
            "VALORES_VALIDOS": validos,
            "VALORES_INVALIDOS": invalidos,
            "ACURACIA_%": round(100 * validos / avaliaveis, 2) if avaliaveis else 100.0,
            "TOTAL_BASE": total,
        })
    return sorted(linhas, key=lambda l: l["ACURACIA_%"])


def calcular_oportunidade(quadro: pd.DataFrame, perfil: PerfilSistema,
                          mapeamento: dict[str, str]) -> list[dict]:
    """Intervalo, em dias, entre a ocorrência do evento e o seu registro."""
    coluna_evento = mapeamento.get("DATA_EVENTO")
    coluna_registro = mapeamento.get("DATA_REGISTRO")
    if not coluna_evento or not coluna_registro:
        return []

    intervalos = []
    for linha in quadro.index:
        dias = nz.diferenca_em_dias(quadro[coluna_evento].at[linha],
                                    quadro[coluna_registro].at[linha])
        if dias is not None and -365 <= dias <= 3650:
            intervalos.append(dias)

    if not intervalos:
        return []

    serie = pd.Series(intervalos)
    prazo = perfil.prazo_registro_dias
    # Só entram no cálculo os intervalos não negativos: um registro digitado
    # antes do evento é erro de consistência, não medida de oportunidade.
    nao_negativos = serie[serie >= 0]
    validos = int(len(nao_negativos))
    no_prazo = int((nao_negativos <= prazo).sum())
    return [{
        "BASE": perfil.sigla,
        "PRAZO_NORMATIVO_DIAS": prazo,
        "REGISTROS_AVALIADOS": len(serie),
        "MEDIA_DIAS": round(float(serie.mean()), 1),
        "MEDIANA_DIAS": float(serie.median()),
        "PERCENTIL_25": float(serie.quantile(0.25)),
        "PERCENTIL_75": float(serie.quantile(0.75)),
        "MINIMO_DIAS": int(serie.min()),
        "MAXIMO_DIAS": int(serie.max()),
        "REGISTROS_NO_PRAZO": no_prazo,
        "OPORTUNIDADE_%": round(100 * no_prazo / validos, 2) if validos else 0.0,
        "CLASSIFICACAO": _classificar_completude(100 * no_prazo / validos
                                                 if validos else 0),
    }]


def detectar_consistencia_interna(quadro: pd.DataFrame, achados: list[Achado],
                                  perfil: PerfilSistema) -> list[dict]:
    """Sumariza as divergências lógicas por tipo."""
    total = len(quadro)
    contagem = Counter(a.tipo for a in achados if a.dimensao == "Consistência")
    linhas_afetadas = {a.linha for a in achados if a.dimensao == "Consistência"}
    resumo = [{
        "BASE": perfil.sigla,
        "TIPO_DIVERGENCIA": tipo,
        "OCORRENCIAS": quantidade,
        "PROPORCAO_%": round(100 * quantidade / total, 3) if total else 0.0,
    } for tipo, quantidade in contagem.most_common()]
    resumo.append({
        "BASE": perfil.sigla,
        "TIPO_DIVERGENCIA": "TOTAL DE REGISTROS COM ALGUMA DIVERGÊNCIA LÓGICA",
        "OCORRENCIAS": len(linhas_afetadas),
        "PROPORCAO_%": round(100 * len(linhas_afetadas) / total, 3) if total else 0.0,
    })
    return resumo


# --------------------------------------------------------------------------- #
# Classificação das linhas e escore global
# --------------------------------------------------------------------------- #

def classificar_linhas(quadro: pd.DataFrame,
                       achados: list[Achado]) -> pd.Series:
    """Atribui verde, amarelo ou vermelho a cada registro.

    A regra é a da gravidade máxima: basta um achado grave para que a linha
    seja vermelha; na ausência de graves, um achado suspeito a torna amarela.
    """
    classificacao = pd.Series(VERDE, index=quadro.index, dtype=object)
    for achado in achados:
        if achado.linha not in classificacao.index:
            continue
        if achado.gravidade == VERMELHO:
            classificacao.at[achado.linha] = VERMELHO
        elif classificacao.at[achado.linha] == VERDE:
            classificacao.at[achado.linha] = AMARELO
    return classificacao


def calcular_escore_global(resultado: ResultadoQualidade) -> float:
    """Escore sintético de 0 a 100, ponderando as dimensões prioritárias.

    A ponderação (completude 0,35; acurácia 0,35; consistência 0,20;
    oportunidade 0,10) reflete a prioridade declarada no projeto para
    acurácia, completude e consistência, mantendo a oportunidade como
    dimensão complementar.
    """
    obrigatorias = [l for l in resultado.completude if l["OBRIGATORIO"] == "Sim"]
    base_completude = obrigatorias or resultado.completude
    completude = (sum(l["COMPLETUDE_UTIL_%"] for l in base_completude)
                  / len(base_completude)) if base_completude else 0.0
    acuracia = (sum(l["ACURACIA_%"] for l in resultado.acuracia)
                / len(resultado.acuracia)) if resultado.acuracia else 100.0

    total = max(1, resultado.total_registros)
    linhas_divergentes = len({a.linha for a in resultado.achados
                              if a.dimensao == "Consistência"})
    consistencia = 100 * (1 - linhas_divergentes / total)

    oportunidade = (resultado.oportunidade[0]["OPORTUNIDADE_%"]
                    if resultado.oportunidade else completude)

    return round(0.35 * completude + 0.35 * acuracia
                 + 0.20 * consistencia + 0.10 * oportunidade, 2)


# --------------------------------------------------------------------------- #
# Orquestração
# --------------------------------------------------------------------------- #

def qualificar_base(quadro: pd.DataFrame, perfil: PerfilSistema,
                    arquivo: str = "") -> ResultadoQualidade:
    """Executa a qualificação completa de uma base."""
    mapeamento = perfil.mapear(list(quadro.columns))
    ausentes = [c for c in perfil.obrigatorios if c not in mapeamento]

    achados: list[Achado] = []
    achados += _avaliar_obrigatorios(quadro, perfil, mapeamento)
    achados += _avaliar_dominios_e_formatos(quadro, perfil, mapeamento)
    achados += _avaliar_coerencia_interna(quadro, perfil, mapeamento)

    resultado = ResultadoQualidade(
        sigla=perfil.sigla, arquivo=arquivo, perfil=perfil,
        total_registros=len(quadro), mapeamento=mapeamento, achados=achados,
        variaveis_ausentes=ausentes,
    )
    resultado.completude = calcular_completude(quadro, perfil, mapeamento)
    resultado.acuracia = calcular_acuracia(quadro, achados, perfil, mapeamento)
    resultado.consistencia = detectar_consistencia_interna(quadro, achados, perfil)
    resultado.oportunidade = calcular_oportunidade(quadro, perfil, mapeamento)
    resultado.classificacao_linhas = classificar_linhas(quadro, achados)
    resultado.escore_global = calcular_escore_global(resultado)
    return resultado


# --------------------------------------------------------------------------- #
# Rótulos legíveis para os tipos de inconsistência
# --------------------------------------------------------------------------- #
#
# Os identificadores de tipo são constantes em caixa alta e sem acentuação,
# adequadas ao processamento; os rótulos abaixo são a forma como devem chegar
# ao leitor do relatório e da planilha.

ROTULOS_TIPO = {
    "CAMPO_OBRIGATORIO_EM_BRANCO": "Campo obrigatório em branco",
    "CAMPO_OBRIGATORIO_IGNORADO": "Campo obrigatório preenchido como ignorado",
    "VALOR_FORA_DO_DOMINIO": "Valor fora do domínio da variável",
    "DATA_INVALIDO": "Data inválida",
    "CPF_INVALIDO": "CPF inválido",
    "CNS_INVALIDO": "CNS inválido",
    "CEP_INVALIDO": "CEP inválido",
    "CID_INVALIDO": "Código CID-10 inválido",
    "NOME_INVALIDO": "Preenchimento nominal inválido",
    "EVENTO_ANTERIOR_AO_NASCIMENTO": "Evento anterior à data de nascimento",
    "IDADE_IMPLAUSIVEL": "Idade implausível",
    "IDADE_MUITO_ELEVADA": "Idade muito elevada",
    "SINTOMAS_APOS_NOTIFICACAO": "Sintomas posteriores à notificação",
    "ENCERRAMENTO_ANTES_DA_NOTIFICACAO": "Encerramento anterior à notificação",
    "DIGITACAO_ANTERIOR_AO_EVENTO": "Digitação anterior ao evento",
    "OBITO_SEM_EVOLUCAO_COMPATIVEL": "Óbito sem evolução compatível",
    "DATA_FUTURA": "Data futura",
    "RESIDENCIA_FORA_DO_MUNICIPIO": "Residência fora do município",
    "PESO_IMPLAUSIVEL": "Peso ao nascer implausível",
    "PESO_MUITO_BAIXO": "Peso ao nascer muito baixo",
    "SEXO_IGNORADO": "Sexo registrado como ignorado",
    "DUPLICATA_TECNICA": "Duplicata técnica (mesma chave do sistema)",
    "DUPLICATA_DE_CONTEUDO": "Duplicata de conteúdo (identificação idêntica)",
    "DUPLICATA_PROVAVEL": "Duplicata provável (similaridade elevada)",
}


def rotulo_do_tipo(tipo: str) -> str:
    """Forma legível de um tipo de inconsistência."""
    return ROTULOS_TIPO.get(tipo, tipo.replace("_", " ").capitalize())
