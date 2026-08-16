#!/usr/bin/env python3
"""Abre a janela do Consolidador de Sistemas.

No Windows, basta dar duplo clique neste arquivo (ou em 'Consolidador.bat').
Sem interface grafica disponivel, use: python consolidar.py <pasta> -s <saida>
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    if sys.version_info < (3, 8):
        print("E necessario Python 3.8 ou superior.")
        return 1
    try:
        from nucleo.gui import abrir
    except SystemExit as erro:
        print(erro)
        return 1
    abrir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
