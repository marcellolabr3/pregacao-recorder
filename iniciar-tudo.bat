@echo off
setlocal
REM Unico ponto de entrada. Os servicos continuam independentes.
pushd "%~dp0"
if errorlevel 1 exit /b 1

set "PREGACAO_PYTHON=.venv\Scripts\python.exe"
for %%I in ("%CD%") do set "PREGACAO_FOLDER=%%~nxI"
if /I "%PREGACAO_FOLDER%"=="gravador" if exist "..\package-manifest.json" (
    set "PREGACAO_PYTHON=..\runtime\python\python.exe"
)
if not exist "%PREGACAO_PYTHON%" (
    echo [ERRO] Ambiente Python ausente. Consulte docs\WINDOWS.md.
    pause
    popd
    exit /b 1
)

"%PREGACAO_PYTHON%" -B -m app.launcher %*
set "RESULTADO=%ERRORLEVEL%"
if not "%RESULTADO%"=="0" (
    echo.
    echo Inicializacao incompleta. Consulte a mensagem acima e a pasta logs.
    pause
)
popd
exit /b %RESULTADO%
