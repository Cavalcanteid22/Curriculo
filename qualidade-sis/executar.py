#!/usr/bin/env python3
"""Ponto de entrada do QualiSIS.

Uso rápido:
    python executar.py                       -> menu interativo
    python executar.py listar                -> sistemas configurados
    python executar.py analisar -s sim -b base.csv
    python executar.py consolidar            -> painel comparativo
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qualisis.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
