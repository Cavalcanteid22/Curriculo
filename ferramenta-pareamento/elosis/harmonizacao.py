# -*- coding: utf-8 -*-
"""
Harmonização de bases (ELO-SIS).

Schmidt et al. (2020) descrevem a harmonização como processo de múltiplos
passos que integra duas ou mais bases eletrônicas de tipos diferentes com
vistas a subsidiar a decisão gerencial em saúde. Os autores registram que seis
termos são empregados como sinônimos — record linkage, data linkage, data
warehousing, data sharing, data interoperability e health information
exchange — designando, porém, operações tecnicamente distintas.

Esta ferramenta adota a distinção: a harmonização é a etapa que torna as
variáveis comparáveis (aqui implementada); o pareamento é a etapa que
identifica registros da mesma pessoa (módulo `pareamento`); a
interoperabilidade seria propriedade do desenho dos sistemas, e não é objeto
do produto — conforme registrado na introdução do projeto.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import normalizacao as nz
from .perfis import (CHAVES_PAREAMENTO, DOMINIO_RACA_COR, NATUREZA,
                     ROTULOS_CANONICOS, PerfilSistema)
from .similaridade import chave_fonetica_nome

PREFIXO_HARMONIZADO = "H_"


@dataclass
class ResultadoHarmonizacao:
    sigla: str
    quadro: pd.DataFrame
    mapeamento: dict[str, str]
    variaveis_harmonizadas: list[str]
    registro_de_transformacoes: list[dict] = field(default_factory=list)
    variaveis_comuns: list[str] = field(default_factory=list)
    perspectiva: str = ""

    @property
    def rotulo(self) -> str:
        """Identificação da base incluindo a perspectiva, quando houver."""
        if not self.perspectiva:
            return self.sigla
        from .perfis import PERSPECTIVAS
        return f"{self.sigla} ({PERSPECTIVAS[self.perspectiva]['rotulo']})"

    def coluna(self, canonica: str) -> str:
        return PREFIXO_HARMONIZADO + canonica


def harmonizar(quadro: pd.DataFrame, perfil: PerfilSistema,
               mapeamento: dict[str, str],
               perspectiva: str = "") -> ResultadoHarmonizacao:
    """Cria as colunas harmonizadas, preservando integralmente as nativas.

    A preservação é deliberada: a área técnica precisa ver lado a lado o valor
    registrado no sistema e o valor tratado, sem o que a recomendação de
    correção não é verificável.
    """
    harmonizado = quadro.copy()
    transformacoes: list[dict] = []
    criadas: list[str] = []

    for canonica, coluna in mapeamento.items():
        natureza = NATUREZA.get(canonica, "texto")
        destino = PREFIXO_HARMONIZADO + canonica
        original = quadro[coluna].astype(str)

        if natureza == "categoria" and canonica == "SEXO":
            harmonizado[destino] = original.map(nz.normalizar_sexo)
            regra = ("Códigos 1/2 (SIM e SINASC) e M/F (SINAN) convertidos para "
                     "M, F ou I — harmonização semântica entre sistemas.")
        elif natureza == "categoria" and canonica == "RACA_COR":
            harmonizado[destino] = original.map(
                lambda v: nz.normalizar_codigo(v, 1) if str(v).strip() else "")
            regra = ("Raça/cor padronizada no domínio de um dígito "
                     f"({', '.join(f'{k}={v}' for k, v in DOMINIO_RACA_COR.items())}).")
        else:
            harmonizado[destino] = original.map(
                lambda v, n=natureza: nz.normalizar_por_natureza(v, n, perfil.sigla))
            regra = _descrever_regra(natureza)

        criadas.append(canonica)
        alterados = int((harmonizado[destino].astype(str).str.strip()
                         != original.str.strip()).sum())
        transformacoes.append({
            "BASE": perfil.sigla,
            "VARIAVEL_CANONICA": canonica,
            "ROTULO": ROTULOS_CANONICOS.get(canonica, canonica),
            "CAMPO_NA_ORIGEM": coluna,
            "CAMPO_HARMONIZADO": destino,
            "NATUREZA": natureza,
            "REGRA_APLICADA": regra,
            "REGISTROS_ALTERADOS": alterados,
            "PROPORCAO_ALTERADA_%": round(100 * alterados / len(quadro), 2)
            if len(quadro) else 0.0,
        })

    # Valores determinados pela perspectiva de identidade adotada.
    from .perfis import valores_fixos_da_perspectiva
    for canonica, valor in valores_fixos_da_perspectiva(perfil, perspectiva).items():
        destino = PREFIXO_HARMONIZADO + canonica
        harmonizado[destino] = valor
        if canonica not in criadas:
            criadas.append(canonica)
        transformacoes.append({
            "BASE": perfil.sigla,
            "VARIAVEL_CANONICA": canonica,
            "ROTULO": ROTULOS_CANONICOS.get(canonica, canonica),
            "CAMPO_NA_ORIGEM": "(não aplicável)",
            "CAMPO_HARMONIZADO": destino,
            "NATUREZA": NATUREZA.get(canonica, "texto"),
            "REGRA_APLICADA": (
                f"Valor fixado em '{valor}' pela perspectiva de identidade "
                f"adotada: o instrumento de coleta determina esse valor para o "
                f"sujeito em questão, não o coletando como variável."),
            "REGISTROS_ALTERADOS": len(quadro),
            "PROPORCAO_ALTERADA_%": 100.0,
        })

    # Chaves auxiliares derivadas, usadas pela blocagem e pelo pareamento.
    coluna_nome = PREFIXO_HARMONIZADO + "NOME"
    if coluna_nome in harmonizado:
        harmonizado["H_NOME_FONETICO"] = harmonizado[coluna_nome].map(
            chave_fonetica_nome)
        harmonizado["H_NOME_INICIAIS"] = harmonizado[coluna_nome].map(nz.iniciais)
    coluna_mae = PREFIXO_HARMONIZADO + "NOME_MAE"
    if coluna_mae in harmonizado:
        harmonizado["H_MAE_FONETICO"] = harmonizado[coluna_mae].map(
            chave_fonetica_nome)
    coluna_nascimento = PREFIXO_HARMONIZADO + "DATA_NASCIMENTO"
    if coluna_nascimento in harmonizado:
        harmonizado["H_ANO_NASCIMENTO"] = harmonizado[coluna_nascimento].str[:4]

    return ResultadoHarmonizacao(
        sigla=perfil.sigla, quadro=harmonizado, mapeamento=mapeamento,
        variaveis_harmonizadas=criadas, registro_de_transformacoes=transformacoes,
        perspectiva=perspectiva)


def _descrever_regra(natureza: str) -> str:
    return {
        "nome": ("Conversão para maiúsculas, remoção de acentos e de caracteres "
                 "especiais, supressão de espaços duplos e das preposições de "
                 "ligação (DA, DE, DO, DAS, DOS), conforme Garcia, Miranda e "
                 "Sousa (2022)."),
        "texto": ("Conversão para maiúsculas, remoção de acentos, de caracteres "
                  "especiais e de espaços duplos."),
        "data": ("Conversão para o formato ISO 8601 (AAAA-MM-DD) a partir dos "
                 "formatos aceitos pelos sistemas de origem."),
        "cpf": ("Remoção de pontos e traços e preenchimento com zeros à esquerda "
                "até 11 dígitos, conforme Garcia, Miranda e Sousa (2022)."),
        "cns": "Remoção de separadores e padronização em 15 dígitos.",
        "cep": "Remoção de separadores e padronização em 8 dígitos.",
        "cid": "Padronização do código CID-10: letra maiúscula seguida de dígitos.",
        "ibge": "Padronização do código IBGE de município em 6 dígitos.",
        "cnes": "Padronização do código CNES em 7 dígitos.",
        "numero": "Retenção apenas dos dígitos.",
        "codigo": "Conversão para maiúsculas e remoção de acentos.",
        "categoria": "Padronização do código no domínio do sistema.",
    }.get(natureza, "Padronização textual básica.")


def identificar_variaveis_comuns(resultados: dict[str, ResultadoHarmonizacao]
                                 ) -> list[dict]:
    """Determina quais variáveis canônicas existem em quais bases.

    A etapa responde à pergunta prática que antecede o linkage: quais chaves
    estão efetivamente disponíveis nas bases a relacionar. A ausência de
    identificador único de alta qualidade e preenchimento obrigatório em todos
    os sistemas é precisamente o cenário descrito por Garcia, Miranda e Sousa
    (2022) para justificar o record linkage.
    """
    siglas = list(resultados)
    todas = sorted({v for r in resultados.values() for v in r.variaveis_harmonizadas},
                   key=lambda v: (v not in CHAVES_PAREAMENTO,
                                  CHAVES_PAREAMENTO.index(v)
                                  if v in CHAVES_PAREAMENTO else 0, v))
    linhas = []
    for variavel in todas:
        presenca = {s: variavel in resultados[s].variaveis_harmonizadas
                    for s in siglas}
        completudes = {}
        for sigla, presente in presenca.items():
            if not presente:
                completudes[sigla] = 0.0
                continue
            coluna = PREFIXO_HARMONIZADO + variavel
            serie = resultados[sigla].quadro[coluna].astype(str).str.strip()
            completudes[sigla] = round(100 * (serie != "").mean(), 2) if len(serie) else 0.0

        n_presentes = sum(presenca.values())
        registro = {
            "VARIAVEL": variavel,
            "ROTULO": ROTULOS_CANONICOS.get(variavel, variavel),
            "BASES_EM_QUE_EXISTE": n_presentes,
            "E_CHAVE_DE_PAREAMENTO": "Sim" if variavel in CHAVES_PAREAMENTO else "Não",
        }
        for sigla in siglas:
            registro[f"EXISTE_EM_{sigla}"] = "Sim" if presenca[sigla] else "Não"
            registro[f"COMPLETUDE_{sigla}_%"] = completudes[sigla]

        menor = min((completudes[s] for s in siglas if presenca[s]), default=0.0)
        registro["COMPLETUDE_MINIMA_%"] = menor
        registro["APTIDAO_COMO_CHAVE"] = _classificar_aptidao(
            variavel, n_presentes, len(siglas), menor)
        registro["OBSERVACAO"] = _observacao_variavel(variavel, presenca, completudes)
        linhas.append(registro)
    return linhas


def _classificar_aptidao(variavel: str, presentes: int, total: int,
                         completude_minima: float) -> str:
    if variavel not in CHAVES_PAREAMENTO:
        return "Não aplicável (variável de conteúdo)"
    if presentes < 2:
        return "Inapta — ausente em ao menos uma das bases"
    if presentes < total:
        return "Parcial — disponível apenas em parte das bases"
    if completude_minima >= 95:
        return "Apta — alta completude em todas as bases"
    if completude_minima >= 80:
        return "Apta com ressalva — completude intermediária"
    if completude_minima >= 50:
        return "Frágil — completude insuficiente para uso isolado"
    return "Inapta — completude crítica"


def _observacao_variavel(variavel: str, presenca: dict, completudes: dict) -> str:
    ausentes = [s for s, p in presenca.items() if not p]
    if ausentes:
        return (f"Variável ausente em: {', '.join(ausentes)}. Não pode compor a "
                "chave composta do estágio determinístico envolvendo essas bases.")
    if variavel == "CPF":
        media = sum(completudes.values()) / max(1, len(completudes))
        if media < 60:
            return ("Completude insuficiente para servir como identificador "
                    "principal. É esse o cenário — ausência de identificador "
                    "único universal de alta qualidade — que justifica o "
                    "recurso ao record linkage (Garcia; Miranda; Sousa, 2022).")
        return ("Identificador de maior poder discriminante entre os "
                "disponíveis; quando preenchido, dispensa o estágio probabilístico.")
    if variavel == "NOME":
        return ("Chave de primeira ordem. O uso isolado do nome oferece alta "
                "sensibilidade, mas gera grande número de correspondências "
                "falsas por homonímia (Garcia; Miranda; Sousa, 2022).")
    if variavel == "NOME_MAE":
        return ("Chave de segunda ordem. Sua adição ao nome reduz drasticamente "
                "a ambiguidade, sendo decisiva na identificação de homônimos.")
    if variavel == "DATA_NASCIMENTO":
        return ("Chave de terceira ordem. Combinada às duas anteriores, isola os "
                "pares verdadeiros com elevada especificidade.")
    if variavel == "SEXO":
        return ("Variável auxiliar de corroboração: não identifica, mas "
                "contesta pares em que haja divergência.")
    return ""


def registrar_dicionario_harmonizacao(resultados: dict[str, ResultadoHarmonizacao]
                                      ) -> list[dict]:
    """Dicionário de-para consolidado entre os sistemas."""
    linhas = []
    for sigla, resultado in resultados.items():
        for transformacao in resultado.registro_de_transformacoes:
            linhas.append(transformacao)
    return sorted(linhas, key=lambda l: (l["VARIAVEL_CANONICA"], l["BASE"]))
