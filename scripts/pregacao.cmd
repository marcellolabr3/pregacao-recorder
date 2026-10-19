@echo off
setlocal
pushd "%~dp0.."
if errorlevel 1 exit /b 1
set "PREGACAO_PYTHON=.venv\Scripts\python.exe"
set "PREGACAO_MODULE=app.cli"
for %%I in ("%CD%") do set "PREGACAO_FOLDER=%%~nxI"
if /I "%PREGACAO_FOLDER%"=="gravador" if exist "..\package-manifest.json" (
  set "PREGACAO_PYTHON=..\runtime\python\python.exe"
  set "PREGACAO_MODULE=app.launcher --cli"
)
if not exist "%PREGACAO_PYTHON%" (
  echo Ambiente Python ausente. Consulte docs\WINDOWS.md.
  popd
  exit /b 1
)
"%PREGACAO_PYTHON%" -B -m %PREGACAO_MODULE% %*
set "RESULTADO=%ERRORLEVEL%"
popd
exit /b %RESULTADO%
