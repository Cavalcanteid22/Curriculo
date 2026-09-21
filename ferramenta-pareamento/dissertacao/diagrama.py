# -*- coding: utf-8 -*-
"""Diagrama do fluxo de processamento, para o capítulo da dissertação."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_SECUNDARIA = "#52514e"
AZUL = "#2a78d6"
AZUL_CLARO = "#cde2fb"
CINZA = "#e3e2de"

ETAPAS = [
    ("1. Leitura", "DBF · CSV · Excel · PDF\nIdentificação do sistema\npela assinatura de campos"),
    ("2. Qualificação", "Completude · Acurácia\nConsistência · Oportunidade\nClassificação por cor"),
    ("3. Duplicidades", "Técnica · De conteúdo\nProvável"),
    ("4. Harmonização", "Normalização das variáveis\nPerspectiva de identidade\nColunas nativas preservadas"),
    ("5. Pareamento", "Estágio determinístico\nEstágio probabilístico\nBlocagem"),
    ("6. Análise", "Indicadores de desempenho\nEpidemiologia · Projeções"),
]

SAIDAS = [
    ("Planilha", "28 abas · linhas pintadas\ncolunas de recomendação"),
    ("Relatório", "ABNT · tabelas · gráficos\nanálises e orientações"),
    ("Auditoria", "resumos SHA-256\nparâmetros e eventos"),
]


def _caixa(eixo, x, y, largura, altura, titulo, corpo, cor_borda, cor_fundo):
    eixo.add_patch(FancyBboxPatch(
        (x, y), largura, altura,
        boxstyle="round,pad=0.02,rounding_size=0.06",
        linewidth=1.6, edgecolor=cor_borda, facecolor=cor_fundo))
    eixo.text(x + largura / 2, y + altura - 0.26, titulo,
              ha="center", va="top", fontsize=10.5, fontweight="bold",
              color=TINTA)
    # O corpo é ancorado ao centro do espaço restante, de modo que o número de
    # linhas não empurre a última contra a borda.
    eixo.text(x + largura / 2, y + (altura - 0.42) / 2, corpo,
              ha="center", va="center", fontsize=8.2,
              color=TINTA_SECUNDARIA, linespacing=1.6)


def gerar(destino: Path) -> Path:
    # A geometria é derivada do conteúdo, e não fixada: caixas dimensionadas
    # por número de linhas de texto evitam que a última linha transborde a
    # borda inferior — defeito que só aparece ao olhar a figura pronta.
    largura, altura = 6.4, 1.55
    espaco = 0.34
    margem_moldura = 0.42

    altura_fluxo = len(ETAPAS) * altura + (len(ETAPAS) - 1) * espaco
    altura_saidas = 1.20
    altura_total = altura_fluxo + 2 * margem_moldura + altura_saidas + 1.15

    figura, eixo = plt.subplots(figsize=(8.6, 0.86 * altura_total))
    figura.patch.set_facecolor(SUPERFICIE)
    eixo.set_facecolor(SUPERFICIE)
    eixo.set_xlim(0, 10)
    eixo.set_ylim(0, altura_total)
    eixo.axis("off")

    topo_moldura = altura_total - 0.62
    base_moldura = topo_moldura - altura_fluxo - 2 * margem_moldura

    # Moldura do modo cofre: todo o fluxo ocorre dentro dela.
    eixo.add_patch(FancyBboxPatch(
        (0.55, base_moldura), 8.9, topo_moldura - base_moldura,
        boxstyle="round,pad=0.04,rounding_size=0.10",
        linewidth=1.4, edgecolor=AZUL, facecolor="none",
        linestyle=(0, (6, 4))))
    eixo.text(5.0, topo_moldura + 0.30,
              "MODO COFRE — nenhuma conexão externa é possível",
              ha="center", va="center", fontsize=9.5, color=AZUL,
              fontweight="bold")

    x = 1.8
    y = topo_moldura - margem_moldura - altura
    for indice, (titulo, corpo) in enumerate(ETAPAS):
        _caixa(eixo, x, y, largura, altura, titulo, corpo, AZUL, AZUL_CLARO)
        if indice < len(ETAPAS) - 1:
            eixo.add_patch(FancyArrowPatch(
                (x + largura / 2, y - 0.04),
                (x + largura / 2, y - espaco + 0.04),
                arrowstyle="-|>", mutation_scale=14, linewidth=1.5,
                color=TINTA_SECUNDARIA))
        y -= altura + espaco

    # Seta da moldura para os produtos.
    eixo.add_patch(FancyArrowPatch(
        (5.0, base_moldura - 0.04), (5.0, altura_saidas + 0.14),
        arrowstyle="-|>", mutation_scale=14, linewidth=1.5,
        color=TINTA_SECUNDARIA))

    largura_saida = 2.72
    for indice, (titulo, corpo) in enumerate(SAIDAS):
        x_saida = 0.62 + indice * (largura_saida + 0.30)
        _caixa(eixo, x_saida, 0.10, largura_saida, altura_saidas, titulo,
               corpo, TINTA_SECUNDARIA, "#f2f2f0")

    destino.parent.mkdir(parents=True, exist_ok=True)
    figura.savefig(destino, dpi=170, bbox_inches="tight",
                   facecolor=SUPERFICIE, edgecolor="none")
    plt.close(figura)
    return destino


if __name__ == "__main__":
    print(gerar(Path("figuras/fluxo.png")))
