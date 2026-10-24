@echo off
chcp 65001 > nul
title Índice de Saúde Municipal do Brasil
echo ===================================================================
echo   Iniciando Servidor Local — Índice de Saúde Municipal do Brasil
echo ===================================================================
echo.
echo O navegador será aberto automaticamente em:
echo http://localhost:8000/site/index.html
echo.
echo (Para encerrar o servidor, basta fechar esta janela.)
echo.
start http://localhost:8000/site/index.html
python -m http.server 8000
pause
