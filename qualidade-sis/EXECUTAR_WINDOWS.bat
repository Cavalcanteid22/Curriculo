@echo off
chcp 65001 >nul
title QualiSIS - Avaliacao da qualidade dos sistemas de informacao
cd /d "%~dp0"

REM Procura o Python instalado (o comando muda conforme a instalacao).
set PY=
where python >nul 2>&1 && set PY=python
if "%PY%"=="" (where py >nul 2>&1 && set PY=py)
if "%PY%"=="" (where python3 >nul 2>&1 && set PY=python3)

if "%PY%"=="" (
  echo.
  echo ============================================================
  echo   O Python nao foi encontrado neste computador.
  echo ============================================================
  echo.
  echo   Ele e' gratuito e precisa ser instalado uma unica vez:
  echo.
  echo     1. Acesse  https://www.python.org/downloads/
  echo     2. Clique em "Download Python"
  echo     3. IMPORTANTE: na primeira tela da instalacao, marque
  echo        a caixinha "Add Python to PATH" antes de continuar
  echo     4. Conclua a instalacao e abra este arquivo novamente
  echo.
  echo   Sem permissao para instalar? Peca ao suporte de TI da
  echo   Secretaria - e' um programa padrao, sem custo.
  echo.
  pause
  exit /b 1
)

%PY% executar.py
if errorlevel 1 pause
