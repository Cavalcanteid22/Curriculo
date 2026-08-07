@echo off
REM Duplo clique para abrir o menu do QualiSIS no Windows.
cd /d "%~dp0"
python executar.py
if errorlevel 1 pause
