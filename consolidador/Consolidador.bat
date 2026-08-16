@echo off
rem Atalho para abrir o Consolidador de Sistemas no Windows.
cd /d "%~dp0"
python executar.py
if errorlevel 1 (
  echo.
  echo Nao foi possivel abrir o aplicativo.
  echo Verifique se o Python 3.8 ou superior esta instalado e no PATH.
  pause
)
