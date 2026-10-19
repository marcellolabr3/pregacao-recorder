@echo off
REM Sobe o painel do SSD numa porta de teste (8081) para nao conflitar
REM com a instalacao que ja roda na 8080.
setlocal
set "RAIZ=%~dp0.."
for %%I in ("%RAIZ%") do set "RAIZ=%%~fI"

set "PREGACAO_HOME=%RAIZ%\pregacao-recorder"
set "PATH=%RAIZ%\runtime\nodejs;%RAIZ%\runtime\ffmpeg\bin;%RAIZ%\runtime\rclone;%RAIZ%\runtime\python311;%PATH%"
set "RCLONE_CONFIG=%RAIZ%\runtime\rclone\rclone.conf"
set "PLAYWRIGHT_BROWSERS_PATH=%RAIZ%\runtime\playwright"
set "REQUESTS_CA_BUNDLE=%RAIZ%\runtime\certs\windows-root-store.pem"
set "SSL_CERT_FILE=%RAIZ%\runtime\certs\windows-root-store.pem"
set "NODE_EXTRA_CA_CERTS=%RAIZ%\runtime\certs\windows-root-store.pem"
set "PREGACAO_PORT=8081"
set "PREGACAO_LOG_FILE=pregacao-teste-ssd.log"

cd /d "%PREGACAO_HOME%"
call "%PREGACAO_HOME%\.venv\Scripts\activate.bat"

echo [SSD] painel de teste em http://127.0.0.1:8081
python -m app.main
