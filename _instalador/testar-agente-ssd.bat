@echo off
REM Sobe o agente MQTT do SSD direto (sem start /b).
REM So rode quando NENHUM outro agente estiver conectado (mesmo device_id).
setlocal
set "RAIZ=%~dp0.."
for %%I in ("%RAIZ%") do set "RAIZ=%%~fI"

set "PREGACAO_HOME=%RAIZ%\pregacao-recorder"
set "PATH=%RAIZ%\runtime\nodejs;%RAIZ%\runtime\ffmpeg\bin;%RAIZ%\runtime\rclone;%RAIZ%\runtime\python311;%PATH%"
set "RCLONE_CONFIG=%RAIZ%\runtime\rclone\rclone.conf"
set "REQUESTS_CA_BUNDLE=%RAIZ%\runtime\certs\windows-root-store.pem"
set "SSL_CERT_FILE=%RAIZ%\runtime\certs\windows-root-store.pem"
set "NODE_EXTRA_CA_CERTS=%RAIZ%\runtime\certs\windows-root-store.pem"
set "PREGACAO_LOG_FILE=pregacao-agente-teste.log"

cd /d "%PREGACAO_HOME%"

REM ---- troca de letra de unidade: conserta os venvs antes de usar o venv ----
if exist "%RAIZ%\_instalador\ajustar_caminhos.py" if exist "%RAIZ%\runtime\python311\python.exe" (
    "%RAIZ%\runtime\python311\python.exe" "%RAIZ%\_instalador\ajustar_caminhos.py"
)

call "%PREGACAO_HOME%\.venv\Scripts\activate.bat"

python -m app.remote.agent
