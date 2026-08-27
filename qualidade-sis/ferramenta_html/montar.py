#!/usr/bin/env python3
"""Monta a versão para navegador em um único arquivo HTML.

Junta o modelo da página, o estilo, o motor de crítica em JavaScript e os
dicionários de dados de `configs/` num arquivo só — que abre com dois cliques,
sem instalar nada e sem internet.

    python ferramenta_html/montar.py
"""

from __future__ import annotations

import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTE = os.path.join(RAIZ, "ferramenta_html")
SAIDA_PADRAO = os.path.join(RAIZ, "QualiSIS_navegador.html")


def ler(nome):
    with open(os.path.join(FONTE, nome), "r", encoding="utf-8") as fh:
        return fh.read()


def configs():
    pasta = os.path.join(RAIZ, "configs")
    saida = {}
    for arquivo in sorted(os.listdir(pasta)):
        if not arquivo.endswith(".json"):
            continue
        with open(os.path.join(pasta, arquivo), "r", encoding="utf-8") as fh:
            dados = json.load(fh)
        dados.pop("_leia_me", None)
        saida[os.path.splitext(arquivo)[0]] = dados
    return saida


def montar(destino=SAIDA_PADRAO):
    pagina = ler("pagina.html")
    blocos = {
        "/*CSS*/": ler("estilo.css"),
        "/*CONFIGS*/": "const CONFIGS = " + json.dumps(
            configs(), ensure_ascii=False, separators=(",", ":")) + ";",
        "/*MOTOR*/": ler("motor.js"),
        "/*EXEMPLO*/": ler("exemplo.js"),
        "/*APP*/": ler("app.js"),
    }
    for marca, conteudo in blocos.items():
        if marca not in pagina:
            raise SystemExit(f"Marcação {marca} não encontrada em pagina.html")
        pagina = pagina.replace(marca, conteudo)
    with open(destino, "w", encoding="utf-8") as fh:
        fh.write(pagina)
    tamanho = os.path.getsize(destino) / 1024
    print(f"gerado: {destino} ({tamanho:,.0f} KB)".replace(",", "."))
    return destino


if __name__ == "__main__":
    montar(sys.argv[1] if len(sys.argv) > 1 else SAIDA_PADRAO)
