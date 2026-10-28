@echo off
chcp 65001 > nul
cd /d "%~dp0"
title Índice de Saúde Municipal do Brasil — Servidor Local
echo ===================================================================
echo   Iniciando Servidor Local — Índice de Saúde Municipal do Brasil
echo   Versão: v0.7.5 (Fase 2: Urgência + Oncologia & CACON/UNACON)
echo ===================================================================
echo.
echo Iniciando servidor sem cache e abrindo navegador automaticamente...
echo.

python serve_local.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Ocorreu um erro ao iniciar o servidor com o Python.
    echo Tentando inicializacao alternativa...
    python -m http.server 8000
)

pause
