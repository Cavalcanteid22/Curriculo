# -*- coding: utf-8 -*-
"""Monta o capítulo completo da dissertação."""

import sys
from pathlib import Path

from docx import Document

import capitulo_parte1, capitulo_parte2, capitulo_parte3
import capitulo_parte4, capitulo_parte5
from gerar_capitulo import configurar, numerar_paginas


def main(destino: str = "CAPITULO_PRODUTO_TECNICO.docx") -> Path:
    documento = Document()
    configurar(documento)

    contadores = {"programa": 1, "tabela": 1, "figura": 1}

    for modulo in (capitulo_parte1, capitulo_parte2, capitulo_parte3,
                   capitulo_parte4, capitulo_parte5):
        modulo.escrever(documento, contadores)

    numerar_paginas(documento)

    documento.core_properties.title = (
        "Produto técnico: a ferramenta ELO-SIS — capítulo de dissertação")
    documento.core_properties.author = "Ivna Dutra Cavalcante"
    documento.core_properties.subject = (
        "Mestrado Profissional em Saúde Coletiva — Informação e Saúde Digital, "
        "Instituto de Saúde Coletiva, Universidade Federal da Bahia")

    caminho = Path(destino)
    documento.save(caminho)

    print(f"gerado: {caminho}")
    print(f"  programas: {contadores['programa'] - 1}")
    print(f"  tabelas:   {contadores['tabela'] - 1}")
    print(f"  figuras:   {contadores['figura'] - 1}")
    return caminho


if __name__ == "__main__":
    main(*sys.argv[1:])
