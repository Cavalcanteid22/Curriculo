# -*- coding: utf-8 -*-
"""
Orquestração do fluxo completo (ELO-SIS).

Encadeia as etapas previstas na metodologia do projeto:

  1. leitura das bases nos formatos aceitos;
  2. identificação do sistema de origem;
  3. qualificação segundo os atributos de qualidade;
  4. detecção de duplicidades;
  5. harmonização;
  6. pareamento determinístico e probabilístico;
  7. cálculo dos indicadores de avaliação e das análises epidemiológicas;
  8. geração da planilha e do relatório analítico.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd

from . import indicadores as ind
from . import seguranca
from .duplicidades import (GrupoDuplicidade, detectar_duplicidades,
                           resumir_duplicidades)
from .harmonizacao import (ResultadoHarmonizacao, harmonizar,
                           identificar_variaveis_comuns,
                           registrar_dicionario_harmonizacao)
from .leitura import ErroLeitura, contar_registros, ler_base
from .pareamento import (ResultadoPareamento, demonstrar_efeito_das_chaves,
                         parear)
from .perfis import (PERFIS, identificar_sistema, mapear_com_perspectiva,
                     perspectiva_sugerida)
from .qualidade import ResultadoQualidade, classificar_linhas, qualificar_base


@dataclass
class Configuracao:
    """Parâmetros de execução, todos expostos na interface."""
    arquivos: list[Path] = field(default_factory=list)
    diretorio_saida: Path = Path("resultados_elosis")
    limiar_pareamento: float = 0.90
    limiar_revisao: float = 0.85
    limiar_duplicidade: float = 0.92
    ano_referencia: int = 2024
    populacao_referencia: int = ind.POPULACAO_SALVADOR_2022
    horizonte_projecao: int = 6
    pseudonimizar_saida: bool = False
    gerar_relatorio: bool = True
    gerar_planilha: bool = True
    limite_registros: int | None = None
    arquivo_referencia: Path | None = None
    perspectivas: dict[str, str] = field(default_factory=dict)
    modo_cofre: bool = True
    # Em bases municipais completas, as abas das bases chegam a dezenas de
    # milhares de linhas. Restringi-las aos registros com pendência produz
    # um arquivo de trabalho muito mais leve, sem perda para a equipe: os
    # registros verdes são, por definição, os que nada exigem.
    somente_pendencias_nas_bases: bool = False
    sistemas_forcados: dict[str, str] = field(default_factory=dict)


@dataclass
class ResultadoExecucao:
    """Tudo o que a execução produziu, pronto para a geração dos produtos."""
    configuracao: Configuracao
    trilha: seguranca.TrilhaAuditoria
    bases: dict[str, pd.DataFrame] = field(default_factory=dict)
    arquivos_de_origem: dict[str, str] = field(default_factory=dict)
    qualidade: dict[str, ResultadoQualidade] = field(default_factory=dict)
    duplicidades: dict[str, list[GrupoDuplicidade]] = field(default_factory=dict)
    harmonizadas: dict[str, ResultadoHarmonizacao] = field(default_factory=dict)
    pareamentos: list[ResultadoPareamento] = field(default_factory=list)
    validacoes: list[ind.ValidacaoPareamento] = field(default_factory=list)
    ganhos_completude: list[dict] = field(default_factory=list)
    consistencia_entre_bases: list[dict] = field(default_factory=list)
    efeito_das_chaves: list[dict] = field(default_factory=list)
    variaveis_comuns: list[dict] = field(default_factory=list)
    dicionario_harmonizacao: list[dict] = field(default_factory=list)
    series_mensais: dict[str, pd.Series] = field(default_factory=dict)
    projecoes: list[ind.Projecao] = field(default_factory=list)
    indicadores_epidemiologicos: list[dict] = field(default_factory=list)
    estatisticas: dict[str, dict] = field(default_factory=dict)
    tempo_total: float = 0.0
    avisos: list[str] = field(default_factory=list)
    momento: datetime = field(default_factory=datetime.now)

    def resumo_executivo(self) -> list[dict]:
        linhas = []
        for sigla, resultado in self.qualidade.items():
            contagem = resultado.contagem_por_classificacao()
            total = max(1, resultado.total_registros)
            linhas.append({
                "BASE": sigla,
                "ARQUIVO": self.arquivos_de_origem.get(sigla, ""),
                "REGISTROS": resultado.total_registros,
                "ESCORE_DE_QUALIDADE": resultado.escore_global,
                "LINHAS_VERDES": contagem["VERDE"],
                "LINHAS_AMARELAS": contagem["AMARELO"],
                "LINHAS_VERMELHAS": contagem["VERMELHO"],
                "%_VERDES": round(100 * contagem["VERDE"] / total, 2),
                "%_AMARELAS": round(100 * contagem["AMARELO"] / total, 2),
                "%_VERMELHAS": round(100 * contagem["VERMELHO"] / total, 2),
                "INCONSISTENCIAS": len(resultado.achados),
                "GRUPOS_DE_DUPLICIDADE": len(self.duplicidades.get(sigla, [])),
                "VARIAVEIS_MAPEADAS": len(resultado.mapeamento),
                "VARIAVEIS_OBRIGATORIAS_AUSENTES": len(resultado.variaveis_ausentes),
            })
        return linhas


def executar(configuracao: Configuracao,
             progresso: Callable[[str, float], None] | None = None
             ) -> ResultadoExecucao:
    """Executa o fluxo completo e devolve todos os produtos intermediários."""
    inicio = time.time()

    if configuracao.modo_cofre:
        seguranca.ativar_modo_cofre()

    configuracao.diretorio_saida = Path(configuracao.diretorio_saida)
    configuracao.diretorio_saida.mkdir(parents=True, exist_ok=True)
    trilha = seguranca.TrilhaAuditoria(configuracao.diretorio_saida)
    trilha.registrar_parametros(
        limiar_pareamento=configuracao.limiar_pareamento,
        limiar_revisao_manual=configuracao.limiar_revisao,
        limiar_duplicidade=configuracao.limiar_duplicidade,
        ano_referencia=configuracao.ano_referencia,
        populacao_referencia=configuracao.populacao_referencia,
        horizonte_projecao_meses=configuracao.horizonte_projecao,
        pseudonimizacao_na_saida=configuracao.pseudonimizar_saida,
        somente_pendencias_nas_bases=configuracao.somente_pendencias_nas_bases,
        modo_cofre=configuracao.modo_cofre,
        perspectivas=configuracao.perspectivas,
    )

    resultado = ResultadoExecucao(configuracao=configuracao, trilha=trilha)

    def avisar(passo: str, fracao: float):
        trilha.registrar("progresso", passo)
        if progresso:
            progresso(passo, fracao)

    # ---------------------------------------------------------------- #
    # 1-2. Leitura e identificação
    # ---------------------------------------------------------------- #
    total_arquivos = max(1, len(configuracao.arquivos))
    for posicao, caminho in enumerate(configuracao.arquivos):
        caminho = Path(caminho)
        faixa = 0.05 + 0.35 * posicao / total_arquivos
        avisar(f"Lendo {caminho.name}...", faixa)
        try:
            quadro = ler_base(caminho, limite=configuracao.limite_registros)
        except ErroLeitura as erro:
            resultado.avisos.append(f"{caminho.name}: {erro}")
            trilha.registrar("erro_leitura", str(erro), arquivo=caminho.name)
            continue

        forcado = configuracao.sistemas_forcados.get(str(caminho))
        perfil = (PERFIS.get(forcado) if forcado
                  else identificar_sistema(list(quadro.columns), caminho.name))
        perfil = perfil or identificar_sistema(list(quadro.columns), caminho.name)

        sigla = perfil.sigla
        if sigla in resultado.bases:  # duas bases do mesmo sistema
            sufixo = 2
            while f"{sigla}_{sufixo}" in resultado.bases:
                sufixo += 1
            sigla = f"{sigla}_{sufixo}"

        if caminho.suffix.lower() == ".pdf":
            # O PDF é formato de apresentação, não de intercâmbio: células
            # sobrepostas e quebras de linha produzem valores embaralhados que
            # nenhuma verificação posterior recupera. O usuário precisa saber
            # disso antes de agir sobre os resultados.
            resultado.avisos.append(
                f"A base '{caminho.name}' foi extraída de um arquivo PDF. A "
                f"extração de dados tabulares de PDF é sempre aproximada: "
                f"valores podem vir truncados, embaralhados ou deslocados de "
                f"coluna, sem que isso seja detectável pelas verificações de "
                f"qualidade. Confira a aba desta base antes de usar os "
                f"resultados e, sempre que possível, solicite a exportação em "
                f"CSV, DBF ou Excel na origem.")

        quadro = quadro.reset_index(drop=True)
        resultado.bases[sigla] = quadro
        resultado.arquivos_de_origem[sigla] = caminho.name
        trilha.registrar_arquivo(caminho, "entrada", len(quadro))
        trilha.registrar("identificacao",
                         f"{caminho.name} identificado como {perfil.sigla}",
                         registros=len(quadro), colunas=len(quadro.columns))

        # ------------------------------------------------------------ #
        # 3-4. Qualificação e duplicidades
        # ------------------------------------------------------------ #
        avisar(f"Qualificando {sigla} ({len(quadro):,} registros)...".replace(",", "."),
               faixa + 0.35 / total_arquivos * 0.5)
        qualidade = qualificar_base(quadro, perfil, caminho.name)

        grupos, achados_duplicidade = detectar_duplicidades(
            quadro, perfil, qualidade.mapeamento,
            limiar_provavel=configuracao.limiar_duplicidade)
        qualidade.achados.extend(achados_duplicidade)
        qualidade.classificacao_linhas = classificar_linhas(quadro, qualidade.achados)
        qualidade.consistencia = _atualizar_consistencia(qualidade, perfil)
        qualidade.escore_global = _recalcular_escore(qualidade)

        resultado.qualidade[sigla] = qualidade
        resultado.duplicidades[sigla] = grupos

        # ------------------------------------------------------------ #
        # 5. Harmonização
        # ------------------------------------------------------------ #
        perspectiva = configuracao.perspectivas.get(perfil.sigla, "")
        mapeamento = mapear_com_perspectiva(perfil, list(quadro.columns),
                                            perspectiva or None)
        resultado.harmonizadas[sigla] = harmonizar(quadro, perfil, mapeamento,
                                                   perspectiva)

    if not resultado.bases:
        # A mensagem precisa dizer o que houve com cada arquivo. Um erro
        # genérico deixaria o usuário sem saber se o problema é o formato, a
        # permissão de leitura ou o conteúdo do arquivo.
        detalhes = ("\n  • " + "\n  • ".join(resultado.avisos)
                    if resultado.avisos else "")
        raise ErroLeitura(
            f"Nenhuma das {len(configuracao.arquivos)} base(s) selecionada(s) "
            f"pôde ser lida.{detalhes}")

    resultado.variaveis_comuns = identificar_variaveis_comuns(resultado.harmonizadas)
    resultado.dicionario_harmonizacao = registrar_dicionario_harmonizacao(
        resultado.harmonizadas)

    # ---------------------------------------------------------------- #
    # 6. Pareamento entre todos os pares de bases
    # ---------------------------------------------------------------- #
    referencia = _carregar_referencia(configuracao.arquivo_referencia,
                                      resultado.avisos)
    siglas = list(resultado.harmonizadas)
    combinacoes = [(a, b) for i, a in enumerate(siglas) for b in siglas[i + 1:]]

    cache_perspectivas: dict[tuple[str, str], ResultadoHarmonizacao] = {}

    for posicao, (sigla_a, sigla_b) in enumerate(combinacoes):
        avisar(f"Pareando {sigla_a} x {sigla_b}...",
               0.45 + 0.30 * posicao / max(1, len(combinacoes)))
        # A perspectiva de identidade depende do par a relacionar: no SINASC,
        # o sujeito é o recém-nascido quando se relaciona com o SIM (óbito
        # infantil) e a mãe quando se relaciona com o SINAN (agravo na
        # gestação). Quando o usuário fixa a perspectiva, ela prevalece.
        sugestao = perspectiva_sugerida(sigla_a.split("_")[0], sigla_b.split("_")[0])
        harmonizado_a = _harmonizar_para_par(resultado, sigla_a, sugestao,
                                             cache_perspectivas)
        harmonizado_b = _harmonizar_para_par(resultado, sigla_b, sugestao,
                                             cache_perspectivas)

        pareamento = parear(harmonizado_a, harmonizado_b,
                            limiar=configuracao.limiar_pareamento,
                            limiar_revisao=configuracao.limiar_revisao)
        resultado.pareamentos.append(pareamento)
        trilha.registrar("pareamento", f"{sigla_a} x {sigla_b}",
                         **{k: v for k, v in pareamento.resumo().items()
                            if isinstance(v, (int, float, str))})

        resultado.efeito_das_chaves.extend(
            demonstrar_efeito_das_chaves(harmonizado_a, harmonizado_b))
        resultado.ganhos_completude.extend(
            ind.calcular_ganho_de_completude(harmonizado_a, harmonizado_b,
                                             pareamento))
        resultado.consistencia_entre_bases.extend(
            ind.calcular_consistencia_entre_bases(harmonizado_a, harmonizado_b,
                                                  pareamento))

        if referencia is not None:
            validacao = _validar(pareamento, resultado, sigla_a, sigla_b,
                                 referencia, harmonizado_a, harmonizado_b)
            if validacao:
                resultado.validacoes.append(validacao)

    # ---------------------------------------------------------------- #
    # 7. Análises epidemiológicas e projeções
    # ---------------------------------------------------------------- #
    avisar("Calculando indicadores e projeções...", 0.80)
    _calcular_analises(resultado)

    resultado.tempo_total = time.time() - inicio
    trilha.registrar("conclusao", f"Execução concluída em "
                                  f"{resultado.tempo_total:.1f} segundos.")
    avisar("Análise concluída.", 0.85)
    return resultado


# --------------------------------------------------------------------------- #
# Auxiliares
# --------------------------------------------------------------------------- #

def _atualizar_consistencia(qualidade: ResultadoQualidade, perfil) -> list[dict]:
    """Recalcula o resumo de consistência após a inclusão das duplicidades."""
    from .qualidade import detectar_consistencia_interna
    return detectar_consistencia_interna(qualidade.total_registros,
                                         qualidade.achados, perfil)


def _recalcular_escore(qualidade: ResultadoQualidade) -> float:
    from .qualidade import calcular_escore_global
    return calcular_escore_global(qualidade)


def _carregar_referencia(caminho: Path | None, avisos: list[str]):
    if not caminho:
        return None
    caminho = Path(caminho)
    if not caminho.exists():
        avisos.append(f"Amostra de referência não encontrada: {caminho.name}")
        return None
    try:
        referencia = ler_base(caminho)
    except ErroLeitura as erro:
        avisos.append(f"Amostra de referência não pôde ser lida: {erro}")
        return None
    if not {"SISTEMA", "ID_PESSOA", "REGISTRO"}.issubset(referencia.columns):
        avisos.append(
            "A amostra de referência precisa conter as colunas SISTEMA, "
            "ID_PESSOA e REGISTRO. Os indicadores de sensibilidade e de valor "
            "preditivo positivo não serão calculados.")
        return None
    return referencia


_PAPEIS_POR_PERSPECTIVA = {
    ("SINASC", "mae"): {"MAE"},
    ("SINASC", "recem_nascido"): {"RECEM_NASCIDO"},
    ("SINASC", ""): {"MAE", "RECEM_NASCIDO"},
    ("SIM", ""): {"FALECIDO", "RECEM_NASCIDO"},
    ("SINAN", ""): {"PACIENTE"},
}


def _papeis(sigla: str, harmonizado: ResultadoHarmonizacao) -> set[str] | None:
    base = sigla.split("_")[0]
    chave = (base, harmonizado.perspectiva or "")
    return _PAPEIS_POR_PERSPECTIVA.get(chave) or _PAPEIS_POR_PERSPECTIVA.get((base, ""))


def _harmonizar_para_par(resultado: ResultadoExecucao, sigla: str,
                         sugestao: dict[str, str],
                         cache: dict) -> ResultadoHarmonizacao:
    """Devolve a harmonização da base sob a perspectiva adequada ao par."""
    base = sigla.split("_")[0]
    fixada = resultado.configuracao.perspectivas.get(base)
    if fixada:
        return resultado.harmonizadas[sigla]
    perspectiva = sugestao.get(base)
    if not perspectiva or perspectiva == resultado.harmonizadas[sigla].perspectiva:
        return resultado.harmonizadas[sigla]

    chave = (sigla, perspectiva)
    if chave not in cache:
        perfil = resultado.qualidade[sigla].perfil
        quadro = resultado.bases[sigla]
        mapeamento = mapear_com_perspectiva(perfil, list(quadro.columns),
                                            perspectiva)
        cache[chave] = harmonizar(quadro, perfil, mapeamento, perspectiva)
    return cache[chave]


def _validar(pareamento, resultado: ResultadoExecucao, sigla_a: str,
             sigla_b: str, referencia,
             harmonizado_a: ResultadoHarmonizacao | None = None,
             harmonizado_b: ResultadoHarmonizacao | None = None):
    from .perfis import NUMERO_REGISTRO
    mapeamento_a = resultado.qualidade[sigla_a].mapeamento
    mapeamento_b = resultado.qualidade[sigla_b].mapeamento
    coluna_a = mapeamento_a.get(NUMERO_REGISTRO)
    coluna_b = mapeamento_b.get(NUMERO_REGISTRO)
    if not coluna_a or not coluna_b:
        return None
    return ind.validar_contra_referencia(
        pareamento, resultado.bases[sigla_a], resultado.bases[sigla_b],
        coluna_a, coluna_b, referencia,
        _papeis(sigla_a, harmonizado_a or resultado.harmonizadas[sigla_a]),
        _papeis(sigla_b, harmonizado_b or resultado.harmonizadas[sigla_b]))


def _calcular_analises(resultado: ResultadoExecucao) -> None:
    """Séries temporais, indicadores epidemiológicos e projeções."""
    configuracao = resultado.configuracao
    contagens: dict[str, int] = {}

    for sigla, quadro in resultado.bases.items():
        mapeamento = resultado.qualidade[sigla].mapeamento
        coluna_evento = mapeamento.get("DATA_EVENTO")
        if not coluna_evento:
            continue
        serie = ind.serie_mensal(quadro, coluna_evento, configuracao.ano_referencia)
        if serie.empty:
            continue
        resultado.series_mensais[sigla] = serie
        contagens[sigla.split("_")[0]] = int(serie.sum())

        rotulos = [f"{configuracao.ano_referencia}-{m:02d}" for m in serie.index]
        projecao = ind.projetar_serie(
            [float(v) for v in serie.values], rotulos,
            horizonte=configuracao.horizonte_projecao,
            rotulo_serie=f"{sigla} — eventos por mês")
        if projecao:
            resultado.projecoes.append(projecao)
        resultado.estatisticas[sigla] = ind.descrever_serie(serie)

    # Óbitos atribuíveis ao agravo, recuperados pelo relacionamento SINAN x SIM.
    for pareamento in resultado.pareamentos:
        if {pareamento.base_a.split("_")[0],
            pareamento.base_b.split("_")[0]} == {"SINAN", "SIM"}:
            from .pareamento import PAREADO
            contagens["OBITOS_PELO_AGRAVO"] = len(
                [p for p in pareamento.pares if p.classificacao == PAREADO])
            break

    resultado.indicadores_epidemiologicos = ind.calcular_indicadores_epidemiologicos(
        contagens, configuracao.populacao_referencia)
