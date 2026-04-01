@echo off
title Power BI Metadata Editor
echo =========================================
echo  Power BI Metadata Editor - Iniciando...
echo =========================================
echo.

cd /d "%~dp0backend"

echo [1/2] Instalando dependencias Python...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [ERRO] Falha ao instalar dependencias.
  echo Verifique o ambiente Python e tente novamente.
  echo.
  pause
  exit /b 1
)

echo.
echo [2/2] Iniciando servidor na porta 8000...
echo.
echo Acesse: http://localhost:8000
echo.
echo Pressione Ctrl+C para encerrar.
echo.

python main.py

pause
