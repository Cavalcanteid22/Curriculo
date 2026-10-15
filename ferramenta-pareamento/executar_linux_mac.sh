#!/usr/bin/env bash
# ============================================================
#  ELO-SIS - Qualificação, harmonização e pareamento de bases
#  dos sistemas de informação em saúde (SIM, SINAN e SINASC)
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

echo
echo "  ELO-SIS — iniciando..."
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "  [ERRO] O Python 3 não foi encontrado nesta estação."
    echo "  Instale o Python 3.9 ou superior e tente novamente."
    exit 1
fi

if ! python3 -c "import pandas, openpyxl, docx, matplotlib" >/dev/null 2>&1; then
    echo "  Instalando as bibliotecas necessárias. Isso ocorre apenas"
    echo "  na primeira execução e pode levar alguns minutos..."
    echo
    python3 -m pip install --quiet -r requirements.txt
fi

exec python3 -m elosis "$@"
