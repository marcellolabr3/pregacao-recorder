@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente Python ausente. Consulte docs\WINDOWS.md.
  exit /b 1
)
".venv\Scripts\python.exe" -m app.cli %*
exit /b %errorlevel%
