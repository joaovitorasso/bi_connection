@echo off
title Power BI Metadata Editor
echo =========================================
echo  Power BI Metadata Editor - Iniciando...
echo =========================================
echo.

cd /d "%~dp0"
set "TOM_LOCAL_DIR=%~dp0tom_libs"
set "TOM_DLL=%TOM_LOCAL_DIR%\Microsoft.AnalysisServices.Tabular.dll"

:: ---- Verifica se a DLL TOM ja existe em caminhos conhecidos ----
if exist "%TOM_DLL%" goto :tom_found

set "FOUND_DLL="
for %%P in (
  "C:\Program Files\Microsoft.NET\ADOMD.NET\160\Microsoft.AnalysisServices.Tabular.dll"
  "C:\Program Files\Microsoft SQL Server\160\SDK\Assemblies\Microsoft.AnalysisServices.Tabular.dll"
  "C:\Program Files\Microsoft SQL Server Management Studio 21\Release\Common7\IDE\Microsoft.AnalysisServices.Tabular.dll"
  "C:\Program Files\Tabular Editor 3\Microsoft.AnalysisServices.Tabular.dll"
  "C:\Program Files\Power BI ALM Toolkit\Power BI ALM Toolkit\Microsoft.AnalysisServices.Tabular.dll"
  "C:\Program Files\On-premises data gateway\FabricIntegrationRuntime\5.0\Gateway\Microsoft.AnalysisServices.Tabular.dll"
) do (
  if exist %%P set "FOUND_DLL=%%~P"
)

if defined FOUND_DLL (
  set "TOM_ASSEMBLY_PATH=%FOUND_DLL%"
  echo [TOM] DLL encontrada em: %FOUND_DLL%
  goto :start_server
)

:: ---- DLL nao encontrada: baixar via NuGet ----
echo [TOM] DLL nao encontrada. Baixando dependencias TOM via NuGet...
echo.

if not exist "%TOM_LOCAL_DIR%" mkdir "%TOM_LOCAL_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { " ^
  "  $pkg = '%TOM_LOCAL_DIR%\tom.nupkg'; " ^
  "  $url = 'https://www.nuget.org/api/v2/package/Microsoft.AnalysisServices.retail.amd64/19.84.1'; " ^
  "  Write-Host '[TOM] Baixando pacote NuGet...'; " ^
  "  Invoke-WebRequest -Uri $url -OutFile $pkg -UseBasicParsing; " ^
  "  Write-Host '[TOM] Extraindo DLLs...'; " ^
  "  $extract = '%TOM_LOCAL_DIR%\extract'; " ^
  "  if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }; " ^
  "  Expand-Archive -Path $pkg -DestinationPath $extract -Force; " ^
  "  $dlls = Get-ChildItem -Path $extract -Filter '*.dll' -Recurse | Where-Object { $_.FullName -match 'net6.0|net8.0|netstandard' }; " ^
  "  foreach ($dll in $dlls) { Copy-Item $dll.FullName '%TOM_LOCAL_DIR%\' -Force }; " ^
  "  Write-Host '[TOM] DLLs copiadas com sucesso.'; " ^
  "} catch { Write-Host '[TOM] Erro ao baixar: ' + $_.Exception.Message; exit 1 }"

if errorlevel 1 (
  echo.
  echo [AVISO] Nao foi possivel baixar as DLLs TOM automaticamente.
  echo O servidor iniciara em modo demonstracao.
  echo Para corrigir, instale o Power BI Desktop ou o SSMS no computador.
  echo.
  goto :start_server
)

if not exist "%TOM_DLL%" (
  echo [AVISO] DLL nao encontrada apos extracao. Iniciando em modo demonstracao.
  goto :start_server
)

:tom_found
set "TOM_ASSEMBLY_PATH=%TOM_DLL%"
echo [TOM] Usando DLL local em: %TOM_DLL%

:start_server
echo.
cd /d "%~dp0backend"

echo [1/2] Instalando dependencias Python...
python -m pip install -r requirements.txt -q
if errorlevel 1 (
  echo.
  echo [ERRO] Falha ao instalar dependencias Python.
  echo Verifique se o Python esta instalado e tente novamente.
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
