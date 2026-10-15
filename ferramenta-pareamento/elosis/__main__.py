# -*- coding: utf-8 -*-
"""
Ponto de entrada do ELO-SIS.

Executado sem argumentos, abre a interface gráfica — via recomendada para o
uso cotidiano. Com argumentos, comporta-se como interface de linha de comando.
"""

import sys


def main() -> int:
    if len(sys.argv) > 1:
        from .cli import principal
        return principal()
    try:
        from .gui import abrir_interface
        return abrir_interface()
    except ImportError:
        # Estações sem a biblioteca gráfica recaem na linha de comando.
        print("A interface gráfica não está disponível nesta instalação "
              "(biblioteca tkinter ausente).\n"
              "Use a linha de comando. Para ver as opções:\n"
              "    python -m elosis --help\n")
        from .cli import principal
        return principal(["--help"])


if __name__ == "__main__":
    sys.exit(main())
