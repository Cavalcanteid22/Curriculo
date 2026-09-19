# -*- coding: utf-8 -*-
"""
Indicadores de avaliação do produto técnico e análises epidemiológicas.

Operacionaliza o Quadro 4 do projeto — completude por variável, acurácia,
oportunidade, consistência entre bases, sensibilidade e valor preditivo
positivo do pareamento, ganho de completude e tempo de execução — e acrescenta
os cálculos estatísticos e epidemiológicos que sustentam o relatório analítico.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from . import normalizacao as nz
from .harmonizacao import PREFIXO_HARMONIZADO, ResultadoHarmonizacao
from .pareamento import PAREADO, REVISAO_MANUAL, ResultadoPareamento
from .perfis import ROTULOS_CANONICOS

# População de Salvador (Censo 2022, IBGE) — denominador dos coeficientes.
POPULACAO_SALVADOR_2022 = 2_418_005


# --------------------------------------------------------------------------- #
# Validação do pareamento contra amostra de referência
# --------------------------------------------------------------------------- #

@dataclass
class ValidacaoPareamento:
    relacionamento: str
    verdadeiros_positivos: int
    falsos_positivos: int
    falsos_negativos: int
    pares_de_referencia: int
    pares_indicados: int
    recuperaveis_na_revisao: int = 0

    @property
    def sensibilidade(self) -> float:
        denominador = self.verdadeiros_positivos + self.falsos_negativos
        return self.verdadeiros_positivos / denominador if denominador else 0.0

    @property
    def valor_preditivo_positivo(self) -> float:
        denominador = self.verdadeiros_positivos + self.falsos_positivos
        return self.verdadeiros_positivos / denominador if denominador else 0.0

    @property
    def proporcao_falsos_positivos(self) -> float:
        return 1 - self.valor_preditivo_positivo if self.pares_indicados else 0.0

    @property
    def medida_f(self) -> float:
        s, v = self.sensibilidade, self.valor_preditivo_positivo
        return 2 * s * v / (s + v) if (s + v) else 0.0

    def como_linhas(self) -> list[dict]:
        return [
            {"RELACIONAMENTO": self.relacionamento, "INDICADOR": "Pares de referência",
             "VALOR": self.pares_de_referencia, "UNIDADE": "pares",
             "INTERPRETACAO": "Total de pares verdadeiros na amostra de referência."},
            {"RELACIONAMENTO": self.relacionamento, "INDICADOR": "Pares indicados pela rotina",
             "VALOR": self.pares_indicados, "UNIDADE": "pares",
             "INTERPRETACAO": "Total de pares classificados como pareados."},
            {"RELACIONAMENTO": self.relacionamento, "INDICADOR": "Verdadeiros-positivos",
             "VALOR": self.verdadeiros_positivos, "UNIDADE": "pares",
             "INTERPRETACAO": "Pares indicados que constam da referência."},
            {"RELACIONAMENTO": self.relacionamento, "INDICADOR": "Falsos-positivos",
             "VALOR": self.falsos_positivos, "UNIDADE": "pares",
             "INTERPRETACAO": "Pares indicados que não constam da referência."},
            {"RELACIONAMENTO": self.relacionamento, "INDICADOR": "Falsos-negativos",
             "VALOR": self.falsos_negativos, "UNIDADE": "pares",
             "INTERPRETACAO": "Pares verdadeiros não recuperados pela rotina."},
            {"RELACIONAMENTO": self.relacionamento, "INDICADOR": "Sensibilidade",
             "VALOR": round(100 * self.sensibilidade, 2), "UNIDADE": "%",
             "INTERPRETACAO": "Proporção dos pares verdadeiros recuperada pela rotina."},
            {"RELACIONAMENTO": self.relacionamento, "INDICADOR": "Valor preditivo positivo",
             "VALOR": round(100 * self.valor_preditivo_positivo, 2), "UNIDADE": "%",
             "INTERPRETACAO": "Proporção dos pares indicados que são verdadeiros."},
            {"RELACIONAMENTO": self.relacionamento, "INDICADOR": "Proporção de falsos-positivos",
             "VALOR": round(100 * self.proporcao_falsos_positivos, 2), "UNIDADE": "%",
             "INTERPRETACAO": "Complemento do valor preditivo positivo."},
            {"RELACIONAMENTO": self.relacionamento, "INDICADOR": "Medida F",
             "VALOR": round(100 * self.medida_f, 2), "UNIDADE": "%",
             "INTERPRETACAO": "Média harmônica entre sensibilidade e valor preditivo positivo."},
            {"RELACIONAMENTO": self.relacionamento,
             "INDICADOR": "Pares verdadeiros na zona de revisão manual",
             "VALOR": self.recuperaveis_na_revisao, "UNIDADE": "pares",
             "INTERPRETACAO": ("Pares verdadeiros situados entre os limiares de "
                               "revisão e de pareamento, recuperáveis por "
                               "conferência da área técnica.")},
        ]


def validar_contra_referencia(resultado: ResultadoPareamento,
                              quadro_a: pd.DataFrame, quadro_b: pd.DataFrame,
                              coluna_id_a: str, coluna_id_b: str,
                              referencia: pd.DataFrame,
                              papeis_a: set[str] | None = None,
                              papeis_b: set[str] | None = None
                              ) -> ValidacaoPareamento | None:
    """Afere sensibilidade e VPP contra um gabarito de pares verdadeiros.

    O gabarito deve conter as colunas SISTEMA, ID_PESSOA e REGISTRO. No piloto,
    é produzido junto com as bases fictícias; em produção, corresponde à
    amostra aleatória revisada por dois avaliadores independentes, conforme o
    Quadro 4 do projeto.
    """
    if referencia is None or referencia.empty:
        return None
    necessarias = {"SISTEMA", "ID_PESSOA", "REGISTRO"}
    if not necessarias.issubset(referencia.columns):
        return None

    def mapa(sistema: str, papeis: set[str] | None) -> dict[str, str]:
        recorte = referencia[referencia["SISTEMA"].astype(str).str.upper()
                             == sistema.upper()]
        if papeis and "PAPEL" in recorte.columns:
            recorte = recorte[recorte["PAPEL"].astype(str).str.upper().isin(papeis)]
        return {str(r["REGISTRO"]).strip(): str(r["ID_PESSOA"]).strip()
                for _, r in recorte.iterrows()}

    mapa_a = mapa(resultado.base_a, papeis_a)
    mapa_b = mapa(resultado.base_b, papeis_b)
    if not mapa_a or not mapa_b:
        return None

    pessoas_a: dict[str, set[str]] = {}
    for registro, pessoa in mapa_a.items():
        pessoas_a.setdefault(pessoa, set()).add(registro)
    pessoas_b: dict[str, set[str]] = {}
    for registro, pessoa in mapa_b.items():
        pessoas_b.setdefault(pessoa, set()).add(registro)

    # Uma pessoa presente nas duas bases constitui um par verdadeiro. Quando há
    # duplicatas, exige-se da rotina a recuperação de um par por pessoa — não de
    # todas as combinações, que seriam artefato da duplicidade.
    pessoas_comuns = set(pessoas_a) & set(pessoas_b)

    identificadores_a = quadro_a[coluna_id_a].astype(str).str.strip()
    identificadores_b = quadro_b[coluna_id_b].astype(str).str.strip()

    def pessoa_do_par(par) -> tuple[str | None, str | None]:
        registro_a = identificadores_a.at[par.linha_a] if par.linha_a in identificadores_a.index else ""
        registro_b = identificadores_b.at[par.linha_b] if par.linha_b in identificadores_b.index else ""
        return mapa_a.get(registro_a), mapa_b.get(registro_b)

    pessoas_recuperadas: set[str] = set()
    falsos_positivos = 0
    pares_indicados = 0
    for par in resultado.pares:
        if par.classificacao != PAREADO:
            continue
        pares_indicados += 1
        pessoa_a, pessoa_b = pessoa_do_par(par)
        if pessoa_a and pessoa_a == pessoa_b:
            pessoas_recuperadas.add(pessoa_a)
        else:
            falsos_positivos += 1

    na_revisao: set[str] = set()
    for par in resultado.pares:
        if par.classificacao != REVISAO_MANUAL:
            continue
        pessoa_a, pessoa_b = pessoa_do_par(par)
        if pessoa_a and pessoa_a == pessoa_b and pessoa_a not in pessoas_recuperadas:
            na_revisao.add(pessoa_a)

    verdadeiros = len(pessoas_recuperadas & pessoas_comuns)
    return ValidacaoPareamento(
        relacionamento=resultado.rotulo,
        verdadeiros_positivos=verdadeiros,
        falsos_positivos=falsos_positivos,
        falsos_negativos=len(pessoas_comuns) - verdadeiros,
        pares_de_referencia=len(pessoas_comuns),
        pares_indicados=pares_indicados,
        recuperaveis_na_revisao=len(na_revisao & pessoas_comuns))


# --------------------------------------------------------------------------- #
# Ganho de completude após o relacionamento
# --------------------------------------------------------------------------- #

def calcular_ganho_de_completude(harmonizado_a: ResultadoHarmonizacao,
                                 harmonizado_b: ResultadoHarmonizacao,
                                 resultado: ResultadoPareamento) -> list[dict]:
    """Mede quanto o relacionamento recupera de informação faltante na base A.

    É o indicador que traduz, em número, o benefício operacional do linkage:
    registros incompletos em uma base passam a contar com o valor existente na
    outra (Garcia; Miranda; Sousa, 2022).
    """
    quadro_a, quadro_b = harmonizado_a.quadro, harmonizado_b.quadro
    pares = [p for p in resultado.pares if p.classificacao == PAREADO]
    if not pares:
        return []

    linhas = []
    comuns = (set(harmonizado_a.variaveis_harmonizadas)
              & set(harmonizado_b.variaveis_harmonizadas))
    for variavel in sorted(comuns):
        coluna = PREFIXO_HARMONIZADO + variavel
        serie_a = quadro_a[coluna].astype(str).str.strip()
        serie_b = quadro_b[coluna].astype(str).str.strip()
        total = len(serie_a)
        preenchidos_antes = int((serie_a != "").sum())

        recuperados = 0
        divergentes = 0
        for par in pares:
            valor_a = serie_a.at[par.linha_a] if par.linha_a in serie_a.index else ""
            valor_b = serie_b.at[par.linha_b] if par.linha_b in serie_b.index else ""
            if not valor_a and valor_b:
                recuperados += 1
            elif valor_a and valor_b and valor_a != valor_b:
                divergentes += 1

        depois = preenchidos_antes + recuperados
        linhas.append({
            "RELACIONAMENTO": resultado.rotulo,
            "VARIAVEL": variavel,
            "ROTULO": ROTULOS_CANONICOS.get(variavel, variavel),
            "TOTAL_REGISTROS_BASE_A": total,
            "COMPLETUDE_ANTES_%": round(100 * preenchidos_antes / total, 2) if total else 0.0,
            "REGISTROS_RECUPERADOS": recuperados,
            "COMPLETUDE_DEPOIS_%": round(100 * depois / total, 2) if total else 0.0,
            "GANHO_ABSOLUTO_PP": round(100 * recuperados / total, 2) if total else 0.0,
            "GANHO_RELATIVO_%": round(100 * recuperados / max(1, total - preenchidos_antes), 2),
            "DIVERGENCIAS_ENTRE_BASES": divergentes,
            "PROPORCAO_DIVERGENTE_%": round(100 * divergentes / len(pares), 2),
        })
    return sorted(linhas, key=lambda l: -l["GANHO_ABSOLUTO_PP"])


def calcular_consistencia_entre_bases(harmonizado_a: ResultadoHarmonizacao,
                                      harmonizado_b: ResultadoHarmonizacao,
                                      resultado: ResultadoPareamento) -> list[dict]:
    """Proporção de divergências em variáveis homônimas presentes nas duas bases.

    Indicador previsto no Quadro 4 do projeto, referenciado a Schmidt et al.
    (2020): mede a coerência semântica efetiva entre sistemas que, em tese,
    registram o mesmo atributo.
    """
    quadro_a, quadro_b = harmonizado_a.quadro, harmonizado_b.quadro
    pares = [p for p in resultado.pares if p.classificacao == PAREADO]
    if not pares:
        return []

    linhas = []
    comuns = (set(harmonizado_a.variaveis_harmonizadas)
              & set(harmonizado_b.variaveis_harmonizadas))
    for variavel in sorted(comuns):
        coluna = PREFIXO_HARMONIZADO + variavel
        serie_a = quadro_a[coluna].astype(str).str.strip()
        serie_b = quadro_b[coluna].astype(str).str.strip()
        comparaveis = concordantes = 0
        for par in pares:
            valor_a = serie_a.at[par.linha_a] if par.linha_a in serie_a.index else ""
            valor_b = serie_b.at[par.linha_b] if par.linha_b in serie_b.index else ""
            if valor_a and valor_b:
                comparaveis += 1
                concordantes += int(valor_a == valor_b)
        if not comparaveis:
            continue
        divergentes = comparaveis - concordantes
        linhas.append({
            "RELACIONAMENTO": resultado.rotulo,
            "VARIAVEL": variavel,
            "ROTULO": ROTULOS_CANONICOS.get(variavel, variavel),
            "PARES_COMPARAVEIS": comparaveis,
            "CONCORDANTES": concordantes,
            "DIVERGENTES": divergentes,
            "CONCORDANCIA_%": round(100 * concordantes / comparaveis, 2),
            "DIVERGENCIA_%": round(100 * divergentes / comparaveis, 2),
            "INTERPRETACAO": _interpretar_concordancia(
                variavel, 100 * concordantes / comparaveis),
        })
    return sorted(linhas, key=lambda l: l["CONCORDANCIA_%"])


def _interpretar_concordancia(variavel: str, percentual: float) -> str:
    if percentual >= 98:
        return ("Concordância muito alta: a variável é registrada de forma "
                "equivalente nos dois sistemas.")
    if percentual >= 90:
        return ("Concordância alta. As divergências residuais concentram-se, "
                "em geral, em erros de digitação pontuais.")
    if percentual >= 70:
        return ("Concordância moderada. Recomenda-se investigar se a divergência "
                "decorre de erro de preenchimento ou de diferença de definição "
                "da variável entre os instrumentos de coleta.")
    return ("Concordância baixa. Indica provável diferença de definição ou de "
            "domínio entre os sistemas — problema de harmonização semântica, "
            "e não apenas de digitação (Schmidt et al., 2020).")


# --------------------------------------------------------------------------- #
# Estatística descritiva e inferencial
# --------------------------------------------------------------------------- #

def intervalo_confianca_proporcao(sucessos: int, total: int,
                                  confianca: float = 0.95) -> tuple[float, float]:
    """Intervalo de confiança de Wilson.

    Preferido ao intervalo de Wald porque mantém cobertura adequada quando a
    proporção se aproxima de 0 ou de 1 e quando o denominador é pequeno —
    situação comum em recortes de vigilância por bairro ou por faixa etária.
    """
    if total == 0:
        return 0.0, 0.0
    z = 1.959964 if abs(confianca - 0.95) < 1e-9 else 2.575829
    proporcao = sucessos / total
    denominador = 1 + z ** 2 / total
    centro = (proporcao + z ** 2 / (2 * total)) / denominador
    margem = (z * math.sqrt(proporcao * (1 - proporcao) / total
                            + z ** 2 / (4 * total ** 2))) / denominador
    return max(0.0, centro - margem), min(1.0, centro + margem)


def descrever_serie(valores: pd.Series) -> dict:
    """Medidas de tendência central, dispersão e forma."""
    serie = pd.to_numeric(valores, errors="coerce").dropna()
    if serie.empty:
        return {}
    n = len(serie)
    media = float(serie.mean())
    desvio = float(serie.std(ddof=1)) if n > 1 else 0.0
    erro = desvio / math.sqrt(n) if n else 0.0
    return {
        "N": n,
        "MEDIA": round(media, 3),
        "DESVIO_PADRAO": round(desvio, 3),
        "ERRO_PADRAO": round(erro, 4),
        "IC95_INFERIOR": round(media - 1.959964 * erro, 3),
        "IC95_SUPERIOR": round(media + 1.959964 * erro, 3),
        "MINIMO": round(float(serie.min()), 3),
        "PERCENTIL_25": round(float(serie.quantile(0.25)), 3),
        "MEDIANA": round(float(serie.median()), 3),
        "PERCENTIL_75": round(float(serie.quantile(0.75)), 3),
        "MAXIMO": round(float(serie.max()), 3),
        "AMPLITUDE_INTERQUARTIL": round(float(serie.quantile(0.75)
                                              - serie.quantile(0.25)), 3),
        "COEFICIENTE_VARIACAO_%": round(100 * desvio / media, 2) if media else 0.0,
        "ASSIMETRIA": round(float(serie.skew()), 3) if n > 2 else 0.0,
        "CURTOSE": round(float(serie.kurtosis()), 3) if n > 3 else 0.0,
    }


def qui_quadrado_aderencia(observados: list[int],
                           esperados: list[float] | None = None) -> dict:
    """Teste de aderência do qui-quadrado, com valor-p por aproximação.

    Implementado sem dependência de SciPy, para que a ferramenta execute em
    estações sem permissão de instalação de pacotes adicionais.
    """
    observados = [o for o in observados if o is not None]
    n = len(observados)
    if n < 2 or sum(observados) == 0:
        return {}
    if esperados is None:
        media = sum(observados) / n
        esperados = [media] * n
    estatistica = sum((o - e) ** 2 / e for o, e in zip(observados, esperados) if e > 0)
    graus = n - 1
    return {
        "ESTATISTICA_QUI_QUADRADO": round(estatistica, 4),
        "GRAUS_DE_LIBERDADE": graus,
        "VALOR_P": round(_valor_p_qui_quadrado(estatistica, graus), 5),
        "SIGNIFICANTE_5%": "Sim" if _valor_p_qui_quadrado(estatistica, graus) < 0.05 else "Não",
    }


def _valor_p_qui_quadrado(estatistica: float, graus: int) -> float:
    """Função de sobrevivência da distribuição qui-quadrado."""
    if graus <= 0 or estatistica <= 0:
        return 1.0
    if graus % 2 == 0:  # forma fechada para graus pares
        metade = estatistica / 2
        termo = math.exp(-metade)
        soma = termo
        for i in range(1, graus // 2):
            termo *= metade / i
            soma += termo
        return min(1.0, soma)
    # Graus ímpares: aproximação de Wilson-Hilferty
    razao = estatistica / graus
    z = (razao ** (1 / 3) - (1 - 2 / (9 * graus))) / math.sqrt(2 / (9 * graus))
    return 0.5 * math.erfc(z / math.sqrt(2))


def correlacao_pearson(x: list[float], y: list[float]) -> dict:
    if len(x) < 3 or len(x) != len(y):
        return {}
    vetor_x, vetor_y = np.array(x, dtype=float), np.array(y, dtype=float)
    if vetor_x.std() == 0 or vetor_y.std() == 0:
        return {}
    r = float(np.corrcoef(vetor_x, vetor_y)[0, 1])
    n = len(x)
    t = r * math.sqrt((n - 2) / max(1e-12, 1 - r ** 2))
    return {
        "COEFICIENTE_R": round(r, 4),
        "R_QUADRADO": round(r ** 2, 4),
        "N": n,
        "ESTATISTICA_T": round(t, 4),
        "VALOR_P_APROXIMADO": round(2 * (1 - _normal_acumulada(abs(t))), 5),
        "INTERPRETACAO": _interpretar_correlacao(r),
    }


def _normal_acumulada(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _interpretar_correlacao(r: float) -> str:
    magnitude = abs(r)
    sentido = "positiva" if r > 0 else "negativa"
    if magnitude >= 0.7:
        return f"Correlação {sentido} forte."
    if magnitude >= 0.4:
        return f"Correlação {sentido} moderada."
    if magnitude >= 0.2:
        return f"Correlação {sentido} fraca."
    return "Correlação desprezível."


# --------------------------------------------------------------------------- #
# Indicadores epidemiológicos
# --------------------------------------------------------------------------- #

def serie_mensal(quadro: pd.DataFrame, coluna_data: str,
                 ano: int | None = None) -> pd.Series:
    """Contagem de eventos por mês, com os doze meses sempre representados."""
    datas = quadro[coluna_data].map(nz.normalizar_data)
    datas = datas[datas != ""]
    if datas.empty:
        return pd.Series(dtype=int)
    convertidas = pd.to_datetime(datas, format="%Y-%m-%d", errors="coerce").dropna()
    if ano:
        convertidas = convertidas[convertidas.dt.year == ano]
    if convertidas.empty:
        return pd.Series(dtype=int)
    contagem = convertidas.dt.month.value_counts().sort_index()
    return contagem.reindex(range(1, 13), fill_value=0)


def calcular_indicadores_epidemiologicos(
        contagens: dict[str, int], populacao: int = POPULACAO_SALVADOR_2022
) -> list[dict]:
    """Coeficientes clássicos de vigilância, com intervalo de confiança.

    Fórmulas conforme a Rede Interagencial de Informações para a Saúde
    (RIPSA) — Indicadores e Dados Básicos para a Saúde.
    """
    nascidos = contagens.get("SINASC", 0)
    obitos = contagens.get("SIM", 0)
    casos = contagens.get("SINAN", 0)
    obitos_pelo_agravo = contagens.get("OBITOS_PELO_AGRAVO", 0)

    indicadores = []

    def adicionar(nome, numerador, denominador, base, unidade, formula,
                  interpretacao):
        if not denominador:
            return
        valor = numerador / denominador * base
        inferior, superior = intervalo_confianca_proporcao(numerador, denominador)
        indicadores.append({
            "INDICADOR": nome,
            "NUMERADOR": numerador,
            "DENOMINADOR": denominador,
            "VALOR": round(valor, 2),
            "UNIDADE": unidade,
            "IC95_INFERIOR": round(inferior * base, 2),
            "IC95_SUPERIOR": round(superior * base, 2),
            "FORMULA": formula,
            "INTERPRETACAO": interpretacao,
        })

    adicionar("Coeficiente geral de mortalidade", obitos, populacao, 1000,
              "por 1.000 habitantes",
              "(óbitos de residentes ÷ população residente) × 1.000",
              "Mede o risco de morte na população residente no período.")
    adicionar("Taxa bruta de natalidade", nascidos, populacao, 1000,
              "por 1.000 habitantes",
              "(nascidos vivos de residentes ÷ população residente) × 1.000",
              "Mede a frequência de nascimentos na população residente.")
    adicionar("Coeficiente de incidência do agravo", casos, populacao, 100_000,
              "por 100.000 habitantes",
              "(casos novos notificados ÷ população residente) × 100.000",
              "Mede o risco de adoecimento pelo agravo sob vigilância.")
    adicionar("Taxa de letalidade do agravo", obitos_pelo_agravo, casos, 100,
              "%", "(óbitos pelo agravo ÷ casos do agravo) × 100",
              "Mede a gravidade do agravo entre os casos notificados. "
              "Sua estimação depende do relacionamento entre SINAN e SIM.")
    adicionar("Mortalidade proporcional pelo agravo", obitos_pelo_agravo, obitos,
              100, "%", "(óbitos pelo agravo ÷ total de óbitos) × 100",
              "Mede a participação do agravo no conjunto dos óbitos.")
    return indicadores


# --------------------------------------------------------------------------- #
# Projeção
# --------------------------------------------------------------------------- #

@dataclass
class Projecao:
    rotulo: str
    periodos_observados: list[str]
    valores_observados: list[float]
    periodos_projetados: list[str]
    valores_projetados: list[float]
    limite_inferior: list[float] = field(default_factory=list)
    limite_superior: list[float] = field(default_factory=list)
    inclinacao: float = 0.0
    intercepto: float = 0.0
    r_quadrado: float = 0.0
    erro_padrao_estimativa: float = 0.0
    metodo: str = "Regressão linear pelo método dos mínimos quadrados"

    def interpretacao(self) -> str:
        direcao = ("ascendente" if self.inclinacao > 0
                   else "descendente" if self.inclinacao < 0 else "estável")
        qualidade = ("bom" if self.r_quadrado >= 0.7
                     else "moderado" if self.r_quadrado >= 0.4 else "baixo")
        return (
            f"A série apresenta tendência {direcao}, com variação média de "
            f"{self.inclinacao:+.2f} evento(s) por período. O coeficiente de "
            f"determinação (R² = {self.r_quadrado:.3f}) indica ajuste {qualidade} "
            f"do modelo linear aos dados observados. "
            + ("Com R² baixo, a projeção deve ser lida como cenário de "
               "referência, e não como previsão: a série apresenta variação "
               "não explicada pela tendência linear, possivelmente sazonal."
               if self.r_quadrado < 0.4 else
               "As bandas representam o intervalo de predição de 95%, que "
               "incorpora tanto a incerteza da estimativa quanto a dispersão "
               "residual observada."))

    def como_linhas(self) -> list[dict]:
        linhas = []
        for periodo, valor in zip(self.periodos_observados, self.valores_observados):
            linhas.append({"SERIE": self.rotulo, "PERIODO": periodo,
                           "TIPO": "Observado", "VALOR": round(valor, 2),
                           "LIMITE_INFERIOR": "", "LIMITE_SUPERIOR": ""})
        for i, (periodo, valor) in enumerate(zip(self.periodos_projetados,
                                                 self.valores_projetados)):
            linhas.append({
                "SERIE": self.rotulo, "PERIODO": periodo, "TIPO": "Projetado",
                "VALOR": round(valor, 2),
                "LIMITE_INFERIOR": round(self.limite_inferior[i], 2)
                if i < len(self.limite_inferior) else "",
                "LIMITE_SUPERIOR": round(self.limite_superior[i], 2)
                if i < len(self.limite_superior) else ""})
        return linhas


def projetar_serie(valores: list[float], rotulos: list[str], horizonte: int = 6,
                   rotulo_serie: str = "Série") -> Projecao | None:
    """Projeção por regressão linear com intervalo de predição de 95%.

    O método é deliberadamente simples e auditável. Modelos mais elaborados
    exigiriam séries históricas mais longas do que as disponíveis no recorte
    anual do piloto, e sua complexidade dificultaria a leitura por equipes que
    não são especialistas em estatística — público a que o produto se destina.
    """
    if len(valores) < 3:
        return None
    y = np.array(valores, dtype=float)
    x = np.arange(len(y), dtype=float)
    n = len(y)

    inclinacao, intercepto = np.polyfit(x, y, 1)
    ajustados = inclinacao * x + intercepto
    residuos = y - ajustados
    soma_residuos = float(np.sum(residuos ** 2))
    soma_total = float(np.sum((y - y.mean()) ** 2))
    r_quadrado = 1 - soma_residuos / soma_total if soma_total > 0 else 0.0
    erro_padrao = math.sqrt(soma_residuos / (n - 2)) if n > 2 else 0.0

    media_x = float(x.mean())
    soma_quadrados_x = float(np.sum((x - media_x) ** 2)) or 1.0

    futuros = np.arange(n, n + horizonte, dtype=float)
    projetados = inclinacao * futuros + intercepto
    inferior, superior = [], []
    for posicao, valor in zip(futuros, projetados):
        erro_predicao = erro_padrao * math.sqrt(
            1 + 1 / n + (posicao - media_x) ** 2 / soma_quadrados_x)
        margem = 1.959964 * erro_predicao
        inferior.append(max(0.0, valor - margem))
        superior.append(valor + margem)

    ultimo = rotulos[-1] if rotulos else ""
    rotulos_futuros = _proximos_rotulos(ultimo, horizonte)

    return Projecao(
        rotulo=rotulo_serie, periodos_observados=list(rotulos),
        valores_observados=[float(v) for v in y],
        periodos_projetados=rotulos_futuros,
        valores_projetados=[max(0.0, float(v)) for v in projetados],
        limite_inferior=inferior, limite_superior=superior,
        inclinacao=float(inclinacao), intercepto=float(intercepto),
        r_quadrado=float(r_quadrado), erro_padrao_estimativa=float(erro_padrao))


def _proximos_rotulos(ultimo: str, horizonte: int) -> list[str]:
    """Continua a sequência de rótulos AAAA-MM; havendo falha, numera."""
    try:
        ano, mes = map(int, str(ultimo).split("-")[:2])
    except (ValueError, AttributeError):
        return [f"t+{i}" for i in range(1, horizonte + 1)]
    rotulos = []
    for _ in range(horizonte):
        mes += 1
        if mes > 12:
            mes, ano = 1, ano + 1
        rotulos.append(f"{ano}-{mes:02d}")
    return rotulos


def media_movel(valores: list[float], janela: int = 3) -> list[float]:
    if len(valores) < janela:
        return list(valores)
    serie = pd.Series(valores)
    return serie.rolling(window=janela, min_periods=1, center=True).mean().tolist()
