@echo off
setlocal
REM Unico ponto de entrada. Os servicos continuam independentes.
pushd "%~dp0"
if errorlevel 1 exit /b 1

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente Python ausente. Consulte docs\WINDOWS.md.
    pause
    popd
    exit /b 1
)

".venv\Scripts\python.exe" -B -m app.launcher %*
set "RESULTADO=%ERRORLEVEL%"
if not "%RESULTADO%"=="0" (
    echo.
    echo Inicializacao incompleta. Consulte a mensagem acima e a pasta logs.
    pause
)
popd
exit /b %RESULTADO%
