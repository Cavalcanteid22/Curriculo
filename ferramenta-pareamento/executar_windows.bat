@echo off
REM ============================================================
REM  ELO-SIS - Qualificacao, harmonizacao e pareamento de bases
REM  dos sistemas de informacao em saude (SIM, SINAN e SINASC)
REM
REM  Basta dar dois cliques neste arquivo.
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo   ELO-SIS - iniciando...
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo   [ERRO] O Python nao foi encontrado nesta estacao.
    echo.
    echo   Instale o Python 3.9 ou superior a partir de python.org
    echo   e marque a opcao "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

python -c "import pandas, openpyxl, docx, matplotlib" >nul 2>nul
if errorlevel 1 (
    echo   Instalando as bibliotecas necessarias. Isso ocorre apenas
    echo   na primeira execucao e pode levar alguns minutos...
    echo.
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -r requirements.txt
    if errorlevel 1 (
        echo.
        echo   [ERRO] Nao foi possivel instalar as bibliotecas.
        echo   Verifique com a area de TI se ha restricao de rede ou
        echo   de permissao nesta estacao.
        echo.
        pause
        exit /b 1
    )
)

python -m elosis
if errorlevel 1 pause
endlocal
