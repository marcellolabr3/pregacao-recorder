@echo off
REM Prova que o Playwright abre o Chromium de dentro do SSD.
setlocal
set "RAIZ=%~dp0.."
for %%I in ("%RAIZ%") do set "RAIZ=%%~fI"

set "SERMON_HOME=%RAIZ%\sermon-pipeline"
set "PATH=%RAIZ%\runtime\nodejs;%RAIZ%\runtime\python311;%PATH%"
set "PLAYWRIGHT_BROWSERS_PATH=%RAIZ%\runtime\playwright"
set "NODE_EXTRA_CA_CERTS=%RAIZ%\runtime\certs\windows-root-store.pem"

cd /d "%SERMON_HOME%"

echo --- navegadores no SSD ---
dir /b "%RAIZ%\runtime\playwright"

echo.
echo --- abrindo o Chromium ---
"%SERMON_HOME%\.venv\Scripts\python.exe" -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(); pg=b.new_page(); pg.set_content('<h1>SSD OK</h1>'); print('titulo renderizado:', pg.inner_text('h1')); b.close(); p.stop(); print('PLAYWRIGHT OK')"
if errorlevel 1 (
    echo [ERRO] playwright
    pause
    exit /b 1
)
