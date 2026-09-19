# -*- coding: utf-8 -*-
"""
Geração dos gráficos do relatório analítico (ELO-SIS).

Os gráficos são produzidos em arquivo de imagem e embutidos no relatório em
formato Word. Como o relatório se destina à leitura impressa e à circulação
institucional, adotam-se três cuidados que não são estéticos, mas de
legibilidade:

  1. a cor nunca carrega sozinha o significado — toda série traz legenda e
     rótulo direto, e as barras de classificação recebem textura, de modo que o
     gráfico permaneça legível em impressão monocromática e para leitores com
     visão de cores atípica;
  2. nenhum gráfico usa dois eixos verticais, prática que induz a leitura de
     correlações inexistentes entre medidas de escalas diferentes;
  3. eixos e grade são recessivos, para que a atenção recaia sobre os dados.

A paleta de estado (verde, amarelo e vermelho) é a mesma empregada na pintura
das linhas da planilha, o que preserva a correspondência visual entre os dois
produtos.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # sem servidor gráfico: executa em qualquer estação
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator

from .qualidade import AMARELO, VERDE, VERMELHO, rotulo_do_tipo

# --------------------------------------------------------------------------- #
# Paleta
# --------------------------------------------------------------------------- #

SUPERFICIE = "#fcfcfb"
TEXTO_PRIMARIO = "#0b0b0b"
TEXTO_SECUNDARIO = "#52514e"
GRADE = "#e3e2de"

# Paleta categórica: as três primeiras posições validam-se em todos os pares.
SERIE = ["#2a78d6", "#eb6834", "#1baf7a"]

# Paleta de estado — reservada à classificação dos registros.
CORES_CLASSIFICACAO = {VERDE: "#0ca30c", AMARELO: "#fab219", VERMELHO: "#d03b3b"}
TEXTURA_CLASSIFICACAO = {VERDE: "", AMARELO: "///", VERMELHO: "\\\\\\"}
ROTULO_CLASSIFICACAO = {VERDE: "Sem inconsistências",
                        AMARELO: "Verificação manual",
                        VERMELHO: "Inconsistência real"}

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
         "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _preparar(figura, eixo, titulo: str = "", rotulo_y: str = "",
              rotulo_x: str = "") -> None:
    """Aplica o tratamento comum: grade recessiva e moldura reduzida."""
    figura.patch.set_facecolor(SUPERFICIE)
    eixo.set_facecolor(SUPERFICIE)
    for lado in ("top", "right"):
        eixo.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        eixo.spines[lado].set_color(GRADE)
        eixo.spines[lado].set_linewidth(1.0)
    eixo.grid(axis="y", color=GRADE, linewidth=0.8, alpha=0.9)
    eixo.set_axisbelow(True)
    eixo.tick_params(colors=TEXTO_SECUNDARIO, labelsize=9, length=0)
    if titulo:
        eixo.set_title(titulo, color=TEXTO_PRIMARIO, fontsize=12,
                       fontweight="bold", pad=14, loc="left")
    if rotulo_y:
        eixo.set_ylabel(rotulo_y, color=TEXTO_SECUNDARIO, fontsize=9.5)
    if rotulo_x:
        eixo.set_xlabel(rotulo_x, color=TEXTO_SECUNDARIO, fontsize=9.5)


def _salvar(figura, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    figura.savefig(destino, dpi=160, bbox_inches="tight",
                   facecolor=SUPERFICIE, edgecolor="none")
    plt.close(figura)
    return destino


# --------------------------------------------------------------------------- #
# 1. Classificação dos registros por base
# --------------------------------------------------------------------------- #

def grafico_classificacao(contagens: dict[str, dict[str, int]],
                          destino: Path) -> Path:
    """Barras empilhadas horizontais com a composição de cada base."""
    bases = list(contagens)
    figura, eixo = plt.subplots(figsize=(9, 0.85 * len(bases) + 2.2))
    _preparar(figura, eixo, "Classificação dos registros por base",
              rotulo_x="Registros")
    eixo.grid(axis="y", visible=False)
    eixo.grid(axis="x", color=GRADE, linewidth=0.8)

    posicoes = range(len(bases))
    totais = [sum(contagens[b].values()) or 1 for b in bases]
    acumulado = [0.0] * len(bases)
    for classificacao in (VERDE, AMARELO, VERMELHO):
        valores = [contagens[b].get(classificacao, 0) for b in bases]
        eixo.barh(list(posicoes), valores, left=acumulado, height=0.52,
                  color=CORES_CLASSIFICACAO[classificacao],
                  hatch=TEXTURA_CLASSIFICACAO[classificacao],
                  edgecolor=SUPERFICIE, linewidth=2.0,  # separador de 2 px
                  label=ROTULO_CLASSIFICACAO[classificacao])
        for indice, valor in enumerate(valores):
            if valor > 0 and valor / totais[indice] >= 0.16:
                # Rótulo interno apenas quando o segmento o comporta com folga;
                # nos demais casos, a legenda e a tabela do relatório carregam
                # o valor — texto recortado é pior do que texto ausente.
                eixo.text(acumulado[indice] + valor / 2, indice,
                          f"{valor} ({100 * valor / totais[indice]:.1f}%)",
                          ha="center", va="center", fontsize=8.5,
                          color="#ffffff" if classificacao != AMARELO else "#3d2a00",
                          fontweight="bold")
            acumulado[indice] += valor

    for indice, total in enumerate(totais):
        eixo.text(total + max(totais) * 0.015, indice, f"{total} registros",
                  va="center", fontsize=8.5, color=TEXTO_SECUNDARIO)
    eixo.set_xlim(0, max(totais) * 1.18)

    eixo.set_yticks(list(posicoes))
    eixo.set_yticklabels(bases, fontsize=10, color=TEXTO_PRIMARIO)
    eixo.invert_yaxis()
    eixo.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3,
                frameon=False, fontsize=9.5, labelcolor=TEXTO_SECUNDARIO)
    return _salvar(figura, destino)


# --------------------------------------------------------------------------- #
# 2. Completude das variáveis obrigatórias
# --------------------------------------------------------------------------- #

def grafico_completude(linhas: list[dict], destino: Path,
                       maximo: int = 16) -> Path:
    """Barras horizontais da completude útil, ordenadas do pior para o melhor."""
    selecionadas = [l for l in linhas if l.get("OBRIGATORIO") == "Sim"] or linhas
    selecionadas = sorted(selecionadas,
                          key=lambda l: l["COMPLETUDE_UTIL_%"])[:maximo]
    if not selecionadas:
        return destino

    rotulos = [f"{l['ROTULO']} ({l['BASE']})" for l in selecionadas]
    valores = [l["COMPLETUDE_UTIL_%"] for l in selecionadas]
    cores = [CORES_CLASSIFICACAO[VERDE] if v >= 90
             else CORES_CLASSIFICACAO[AMARELO] if v >= 70
             else CORES_CLASSIFICACAO[VERMELHO] for v in valores]
    texturas = [TEXTURA_CLASSIFICACAO[VERDE] if v >= 90
                else TEXTURA_CLASSIFICACAO[AMARELO] if v >= 70
                else TEXTURA_CLASSIFICACAO[VERMELHO] for v in valores]

    figura, eixo = plt.subplots(figsize=(9.2, 0.42 * len(selecionadas) + 2.4))
    _preparar(figura, eixo,
              "Completude útil das variáveis de preenchimento obrigatório",
              rotulo_x="Completude útil (%) — desconta códigos de ignorado")
    eixo.grid(axis="y", visible=False)
    eixo.grid(axis="x", color=GRADE, linewidth=0.8)

    posicoes = range(len(selecionadas))
    for indice, (valor, cor, textura) in enumerate(zip(valores, cores, texturas)):
        eixo.barh(indice, valor, height=0.62, color=cor, hatch=textura,
                  edgecolor=SUPERFICIE, linewidth=2.0)
        eixo.text(valor + 1.2, indice, f"{valor:.1f}%", va="center",
                  fontsize=8.5, color=TEXTO_PRIMARIO)

    eixo.axvline(90, color=TEXTO_SECUNDARIO, linestyle=":", linewidth=1.2)
    eixo.text(90, -0.9, "  referência: 90%", fontsize=8.5,
              color=TEXTO_SECUNDARIO, va="top")
    eixo.set_yticks(list(posicoes))
    eixo.set_yticklabels(rotulos, fontsize=9, color=TEXTO_PRIMARIO)
    eixo.set_xlim(0, 108)
    eixo.invert_yaxis()
    eixo.legend(handles=[
        Patch(facecolor=CORES_CLASSIFICACAO[VERDE], label="Bom ou excelente (≥90%)"),
        Patch(facecolor=CORES_CLASSIFICACAO[AMARELO], hatch="///",
              label="Regular (70% a 89%)"),
        Patch(facecolor=CORES_CLASSIFICACAO[VERMELHO], hatch="\\\\\\",
              label="Ruim (<70%)")],
        loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=3, frameon=False,
        fontsize=9, labelcolor=TEXTO_SECUNDARIO)
    return _salvar(figura, destino)


# --------------------------------------------------------------------------- #
# 3. Série temporal e projeção
# --------------------------------------------------------------------------- #

def grafico_projecao(projecao, destino: Path) -> Path:
    """Série observada, tendência ajustada e projeção com banda de predição."""
    figura, eixo = plt.subplots(figsize=(9.4, 4.6))
    _preparar(figura, eixo, projecao.rotulo, rotulo_y="Eventos no mês")

    n = len(projecao.valores_observados)
    x_observado = list(range(n))
    x_projetado = list(range(n - 1, n + len(projecao.valores_projetados)))

    eixo.plot(x_observado, projecao.valores_observados, color=SERIE[0],
              linewidth=2.0, marker="o", markersize=5,
              markerfacecolor=SERIE[0], markeredgecolor=SUPERFICIE,
              markeredgewidth=1.5, label="Observado", zorder=3)

    tendencia = [projecao.intercepto + projecao.inclinacao * i
                 for i in range(n + len(projecao.valores_projetados))]
    eixo.plot(range(len(tendencia)), tendencia, color=TEXTO_SECUNDARIO,
              linewidth=1.2, linestyle=":", label="Tendência linear ajustada",
              zorder=2)

    valores_projetados = [projecao.valores_observados[-1]] + projecao.valores_projetados
    eixo.plot(x_projetado, valores_projetados, color=SERIE[1], linewidth=2.0,
              linestyle="--", marker="s", markersize=5,
              markerfacecolor=SERIE[1], markeredgecolor=SUPERFICIE,
              markeredgewidth=1.5, label="Projetado", zorder=3)

    if projecao.limite_inferior:
        inferior = [projecao.valores_observados[-1]] + projecao.limite_inferior
        superior = [projecao.valores_observados[-1]] + projecao.limite_superior
        eixo.fill_between(x_projetado, inferior, superior, color=SERIE[1],
                          alpha=0.14, linewidth=0,
                          label="Intervalo de predição de 95%")

    rotulos = (projecao.periodos_observados
               + projecao.periodos_projetados)
    passo = max(1, len(rotulos) // 12)
    eixo.set_xticks(list(range(0, len(rotulos), passo)))
    eixo.set_xticklabels([rotulos[i] for i in range(0, len(rotulos), passo)],
                         rotation=45, ha="right", fontsize=8.5)
    eixo.yaxis.set_major_locator(MaxNLocator(nbins=6, integer=True))

    # A folga superior é reservada antes de posicionar a marcação, para que o
    # texto não seja escrito sobre a série.
    teto = max(projecao.valores_observados
               + (projecao.limite_superior or projecao.valores_projetados))
    eixo.set_ylim(0, teto * 1.22)
    eixo.axvline(n - 1, color=GRADE, linewidth=1.4)
    eixo.annotate("início da projeção", xy=(n - 1, teto * 1.16),
                  xytext=(4, 0), textcoords="offset points", fontsize=8.5,
                  color=TEXTO_SECUNDARIO, va="center", ha="left")

    eixo.legend(loc="upper center", bbox_to_anchor=(0.5, -0.30), ncol=4,
                frameon=False, fontsize=9, labelcolor=TEXTO_SECUNDARIO)

    eixo.text(0.0, -0.42,
              f"R² = {projecao.r_quadrado:.3f} | variação média de "
              f"{projecao.inclinacao:+.2f} evento(s) por mês | "
              f"{projecao.metodo}.",
              transform=eixo.transAxes, fontsize=8.5, color=TEXTO_SECUNDARIO)
    return _salvar(figura, destino)


# --------------------------------------------------------------------------- #
# 4. Séries comparadas entre bases
# --------------------------------------------------------------------------- #

def grafico_series_comparadas(series: dict, ano: int, destino: Path) -> Path:
    """Comparação das séries mensais das bases, em um único eixo."""
    if not series:
        return destino
    figura, eixo = plt.subplots(figsize=(9.4, 4.6))
    _preparar(figura, eixo, f"Eventos registrados por mês — {ano}",
              rotulo_y="Eventos no mês")

    for indice, (sigla, serie) in enumerate(series.items()):
        valores = [int(v) for v in serie.values]
        cor = SERIE[indice % len(SERIE)]
        eixo.plot(range(len(valores)), valores, color=cor, linewidth=2.0,
                  marker="o", markersize=5, markerfacecolor=cor,
                  markeredgecolor=SUPERFICIE, markeredgewidth=1.5, label=sigla)
        # Rótulo direto no fim da linha: a identidade não depende só da cor.
        eixo.annotate(f" {sigla}", (len(valores) - 1, valores[-1]),
                      color=cor, fontsize=9, fontweight="bold",
                      va="center", ha="left")

    eixo.set_xticks(range(12))
    eixo.set_xticklabels(MESES, fontsize=9)
    eixo.set_xlim(-0.4, 12.4)
    eixo.yaxis.set_major_locator(MaxNLocator(nbins=6, integer=True))
    eixo.set_ylim(bottom=0)
    eixo.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14),
                ncol=min(4, len(series)), frameon=False, fontsize=9,
                labelcolor=TEXTO_SECUNDARIO)
    return _salvar(figura, destino)


# --------------------------------------------------------------------------- #
# 5. Efeito da adição sequencial de chaves
# --------------------------------------------------------------------------- #

def grafico_efeito_chaves(linhas: list[dict], destino: Path) -> Path:
    """Queda do número de pares candidatos a cada chave acrescentada."""
    if not linhas:
        return destino
    relacionamento = linhas[0]["RELACIONAMENTO"]
    recorte = [l for l in linhas if l["RELACIONAMENTO"] == relacionamento]
    if len(recorte) < 2:
        return destino

    rotulos = [l["CONJUNTO_DE_CHAVES"] for l in recorte]
    valores = [l["PARES_CANDIDATOS"] for l in recorte]

    figura, eixo = plt.subplots(figsize=(9.2, 4.4))
    _preparar(figura, eixo,
              f"Efeito da adição sequencial de chaves — {relacionamento}",
              rotulo_y="Pares candidatos")

    barras = eixo.bar(range(len(valores)), valores, width=0.55, color=SERIE[0],
                      edgecolor=SUPERFICIE, linewidth=2.0)
    for barra, valor in zip(barras, valores):
        eixo.text(barra.get_x() + barra.get_width() / 2,
                  barra.get_height() + max(valores) * 0.02, f"{valor:,}".replace(",", "."),
                  ha="center", fontsize=9, color=TEXTO_PRIMARIO,
                  fontweight="bold")

    eixo.set_xticks(range(len(rotulos)))
    eixo.set_xticklabels([r.replace(" + ", "\n+ ") for r in rotulos],
                         fontsize=8.5, color=TEXTO_PRIMARIO)
    eixo.yaxis.set_major_locator(MaxNLocator(nbins=6, integer=True))
    eixo.text(0.0, -0.34,
              "Reprodução, nas bases analisadas, do experimento de Garcia, "
              "Miranda e Sousa (2022).",
              transform=eixo.transAxes, fontsize=8.5, color=TEXTO_SECUNDARIO)
    return _salvar(figura, destino)


# --------------------------------------------------------------------------- #
# 6. Composição dos pareamentos
# --------------------------------------------------------------------------- #

def grafico_pareamentos(resumos: list[dict], destino: Path) -> Path:
    """Composição dos pares por estágio e situação, em cada relacionamento."""
    if not resumos:
        return destino
    rotulos = [r["RELACIONAMENTO"] for r in resumos]
    determinísticos = [r["PARES_DETERMINISTICOS"] for r in resumos]
    probabilisticos = [r["PARES_PROBABILISTICOS"] for r in resumos]
    revisao = [r["PARES_PARA_REVISAO_MANUAL"] for r in resumos]

    figura, eixo = plt.subplots(figsize=(9.2, 0.95 * len(rotulos) + 2.4))
    _preparar(figura, eixo, "Composição dos pares por relacionamento",
              rotulo_x="Pares")
    eixo.grid(axis="y", visible=False)
    eixo.grid(axis="x", color=GRADE, linewidth=0.8)

    posicoes = list(range(len(rotulos)))
    acumulado = [0] * len(rotulos)
    conjuntos = (
        (determinísticos, SERIE[0], "", "Pareamento determinístico"),
        (probabilisticos, SERIE[2], "//", "Pareamento probabilístico"),
        (revisao, CORES_CLASSIFICACAO[AMARELO], "xx", "Revisão manual"),
    )
    for valores, cor, textura, rotulo in conjuntos:
        eixo.barh(posicoes, valores, left=acumulado, height=0.5, color=cor,
                  hatch=textura, edgecolor=SUPERFICIE, linewidth=2.0,
                  label=rotulo)
        for indice, valor in enumerate(valores):
            if valor > 0 and valor / max(1, sum(
                    [determinísticos[indice], probabilisticos[indice],
                     revisao[indice]])) > 0.10:
                eixo.text(acumulado[indice] + valor / 2, indice, str(valor),
                          ha="center", va="center", fontsize=9,
                          fontweight="bold",
                          color="#ffffff" if cor != CORES_CLASSIFICACAO[AMARELO]
                          else "#3d2a00")
            acumulado[indice] += valor

    eixo.set_yticks(posicoes)
    eixo.set_yticklabels(rotulos, fontsize=10, color=TEXTO_PRIMARIO)
    eixo.invert_yaxis()
    eixo.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3,
                frameon=False, fontsize=9, labelcolor=TEXTO_SECUNDARIO)
    return _salvar(figura, destino)


# --------------------------------------------------------------------------- #
# 7. Ganho de completude com o relacionamento
# --------------------------------------------------------------------------- #

def grafico_ganho_completude(linhas: list[dict], destino: Path,
                             maximo: int = 10) -> Path:
    """Completude antes e depois do relacionamento, por variável."""
    selecionadas = sorted([l for l in linhas if l["GANHO_ABSOLUTO_PP"] > 0],
                          key=lambda l: -l["GANHO_ABSOLUTO_PP"])[:maximo]
    if not selecionadas:
        return destino

    rotulos = [f"{l['ROTULO']}\n({l['RELACIONAMENTO']})" for l in selecionadas]
    antes = [l["COMPLETUDE_ANTES_%"] for l in selecionadas]
    depois = [l["COMPLETUDE_DEPOIS_%"] for l in selecionadas]

    figura, eixo = plt.subplots(figsize=(9.2, 0.62 * len(selecionadas) + 2.6))
    _preparar(figura, eixo,
              "Completude antes e depois do relacionamento de bases",
              rotulo_x="Completude (%)")
    eixo.grid(axis="y", visible=False)
    eixo.grid(axis="x", color=GRADE, linewidth=0.8)

    posicoes = list(range(len(selecionadas)))
    altura = 0.34
    eixo.barh([p - altura / 2 - 0.02 for p in posicoes], antes, height=altura,
              color=TEXTO_SECUNDARIO, alpha=0.55, edgecolor=SUPERFICIE,
              linewidth=2.0, label="Antes do relacionamento")
    eixo.barh([p + altura / 2 + 0.02 for p in posicoes], depois, height=altura,
              color=SERIE[2], edgecolor=SUPERFICIE, linewidth=2.0,
              label="Depois do relacionamento")

    for indice, (valor_antes, valor_depois) in enumerate(zip(antes, depois)):
        eixo.text(valor_depois + 1.0, indice + altura / 2 + 0.02,
                  f"{valor_depois:.1f}% (+{valor_depois - valor_antes:.1f} p.p.)",
                  va="center", fontsize=8.5, color=TEXTO_PRIMARIO)
        eixo.text(valor_antes + 1.0, indice - altura / 2 - 0.02,
                  f"{valor_antes:.1f}%", va="center", fontsize=8.5,
                  color=TEXTO_SECUNDARIO)

    eixo.set_yticks(posicoes)
    eixo.set_yticklabels(rotulos, fontsize=8.5, color=TEXTO_PRIMARIO)
    eixo.set_xlim(0, 118)
    eixo.invert_yaxis()
    eixo.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=2,
                frameon=False, fontsize=9, labelcolor=TEXTO_SECUNDARIO)
    return _salvar(figura, destino)


# --------------------------------------------------------------------------- #
# 8. Desempenho do pareamento
# --------------------------------------------------------------------------- #

def grafico_desempenho(validacoes, destino: Path) -> Path:
    """Sensibilidade e valor preditivo positivo por relacionamento."""
    if not validacoes:
        return destino
    rotulos = [v.relacionamento for v in validacoes]
    sensibilidade = [100 * v.sensibilidade for v in validacoes]
    preditivo = [100 * v.valor_preditivo_positivo for v in validacoes]

    figura, eixo = plt.subplots(figsize=(9.2, 0.9 * len(rotulos) + 2.6))
    _preparar(figura, eixo,
              "Desempenho do pareamento contra a amostra de referência",
              rotulo_x="Percentual (%)")
    eixo.grid(axis="y", visible=False)
    eixo.grid(axis="x", color=GRADE, linewidth=0.8)

    posicoes = list(range(len(rotulos)))
    altura = 0.32
    eixo.barh([p - altura / 2 - 0.02 for p in posicoes], sensibilidade,
              height=altura, color=SERIE[0], edgecolor=SUPERFICIE,
              linewidth=2.0, label="Sensibilidade")
    eixo.barh([p + altura / 2 + 0.02 for p in posicoes], preditivo,
              height=altura, color=SERIE[2], hatch="//", edgecolor=SUPERFICIE,
              linewidth=2.0, label="Valor preditivo positivo")

    for indice, (s, v) in enumerate(zip(sensibilidade, preditivo)):
        eixo.text(s + 1.0, indice - altura / 2 - 0.02, f"{s:.1f}%", va="center",
                  fontsize=9, color=TEXTO_PRIMARIO)
        eixo.text(v + 1.0, indice + altura / 2 + 0.02, f"{v:.1f}%", va="center",
                  fontsize=9, color=TEXTO_PRIMARIO)

    eixo.set_yticks(posicoes)
    eixo.set_yticklabels(rotulos, fontsize=10, color=TEXTO_PRIMARIO)
    eixo.set_xlim(0, 112)
    eixo.invert_yaxis()
    eixo.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2,
                frameon=False, fontsize=9, labelcolor=TEXTO_SECUNDARIO)
    return _salvar(figura, destino)


# --------------------------------------------------------------------------- #
# 9. Inconsistências mais frequentes
# --------------------------------------------------------------------------- #

def grafico_inconsistencias(linhas: list[dict], destino: Path,
                            maximo: int = 12) -> Path:
    """Tipos de inconsistência mais frequentes, por gravidade."""
    selecionadas = sorted(linhas, key=lambda l: -l["REGISTROS_AFETADOS"])[:maximo]
    if not selecionadas:
        return destino

    rotulos = [f"{rotulo_do_tipo(l['TIPO_DE_INCONSISTENCIA'])} ({l['BASE']})"
               for l in selecionadas]
    valores = [l["REGISTROS_AFETADOS"] for l in selecionadas]
    gravidades = [l["GRAVIDADE"] for l in selecionadas]

    figura, eixo = plt.subplots(figsize=(9.4, 0.46 * len(selecionadas) + 2.6))
    _preparar(figura, eixo, "Inconsistências mais frequentes",
              rotulo_x="Registros afetados")
    eixo.grid(axis="y", visible=False)
    eixo.grid(axis="x", color=GRADE, linewidth=0.8)

    for indice, (valor, gravidade) in enumerate(zip(valores, gravidades)):
        eixo.barh(indice, valor, height=0.6,
                  color=CORES_CLASSIFICACAO.get(gravidade, SERIE[0]),
                  hatch=TEXTURA_CLASSIFICACAO.get(gravidade, ""),
                  edgecolor=SUPERFICIE, linewidth=2.0)
        eixo.text(valor + max(valores) * 0.012, indice,
                  f"{valor} ({selecionadas[indice]['PROPORCAO_DA_BASE_%']:.1f}%)",
                  va="center", fontsize=8.5, color=TEXTO_PRIMARIO)

    eixo.set_yticks(range(len(rotulos)))
    eixo.set_yticklabels(rotulos, fontsize=8.5, color=TEXTO_PRIMARIO)
    eixo.set_xlim(0, max(valores) * 1.22)
    eixo.invert_yaxis()
    eixo.legend(handles=[
        Patch(facecolor=CORES_CLASSIFICACAO[VERMELHO], hatch="\\\\\\",
              label="Inconsistência real"),
        Patch(facecolor=CORES_CLASSIFICACAO[AMARELO], hatch="///",
              label="Provável — verificação manual")],
        loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=2, frameon=False,
        fontsize=9, labelcolor=TEXTO_SECUNDARIO)
    return _salvar(figura, destino)


# --------------------------------------------------------------------------- #
# Orquestração
# --------------------------------------------------------------------------- #

def gerar_todos(resultado, diretorio: Path) -> dict[str, Path]:
    """Produz todos os gráficos e devolve o caminho de cada um."""
    diretorio = Path(diretorio)
    diretorio.mkdir(parents=True, exist_ok=True)
    produzidos: dict[str, Path] = {}

    def registrar(nome: str, funcao, *argumentos) -> None:
        destino = diretorio / f"{nome}.png"
        try:
            caminho = funcao(*argumentos, destino)
            if Path(caminho).exists():
                produzidos[nome] = Path(caminho)
        except Exception as erro:  # um gráfico não pode interromper o relatório
            resultado.avisos.append(f"Gráfico '{nome}' não pôde ser gerado: {erro}")

    contagens = {sigla: q.contagem_por_classificacao()
                 for sigla, q in resultado.qualidade.items()}
    registrar("classificacao", grafico_classificacao, contagens)

    completude = [l for q in resultado.qualidade.values() for l in q.completude]
    registrar("completude", grafico_completude, completude)

    registrar("series", grafico_series_comparadas, resultado.series_mensais,
              resultado.configuracao.ano_referencia)

    for indice, projecao in enumerate(resultado.projecoes, start=1):
        registrar(f"projecao_{indice}", grafico_projecao, projecao)

    registrar("efeito_chaves", grafico_efeito_chaves, resultado.efeito_das_chaves)
    registrar("pareamentos", grafico_pareamentos,
              [p.resumo() for p in resultado.pareamentos])
    registrar("ganho_completude", grafico_ganho_completude,
              resultado.ganhos_completude)
    registrar("desempenho", grafico_desempenho, resultado.validacoes)

    from .planilha import _linhas_recomendacoes
    registrar("inconsistencias", grafico_inconsistencias,
              _linhas_recomendacoes(resultado))
    return produzidos
