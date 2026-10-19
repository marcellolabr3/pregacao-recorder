@echo off
REM ============================================================
REM Verificacao integral da instalacao no SSD.
REM Reproduz exatamente o ambiente dos iniciar-*.bat.
REM ============================================================
setlocal

set "RAIZ=%~dp0.."
for %%I in ("%RAIZ%") do set "RAIZ=%%~fI"

set "PREGACAO_HOME=%RAIZ%\pregacao-recorder"
set "SERMON_HOME=%RAIZ%\sermon-pipeline"
set "PATH=%RAIZ%\runtime\nodejs;%RAIZ%\runtime\ffmpeg\bin;%RAIZ%\runtime\rclone;%RAIZ%\runtime\python311;%PATH%"
set "RCLONE_CONFIG=%RAIZ%\runtime\rclone\rclone.conf"
set "PLAYWRIGHT_BROWSERS_PATH=%RAIZ%\runtime\playwright"
set "REQUESTS_CA_BUNDLE=%RAIZ%\runtime\certs\windows-root-store.pem"
set "SSL_CERT_FILE=%RAIZ%\runtime\certs\windows-root-store.pem"
set "NODE_EXTRA_CA_CERTS=%RAIZ%\runtime\certs\windows-root-store.pem"

set "PV=%PREGACAO_HOME%\.venv\Scripts\python.exe"
set "SV=%SERMON_HOME%\.venv\Scripts\python.exe"

cd /d "%PREGACAO_HOME%"

echo ============================================================
echo  VERIFICACAO INTEGRAL - SSD
echo ============================================================
echo  Raiz : %RAIZ%
echo ============================================================
echo.

echo --- [1] PREGACAO_HOME resolvido pelo app ---
"%PV%" -c "from app import paths; print('home =', paths.home()); print('OK' if paths.home().name=='pregacao-recorder' else 'ERRO')"
if errorlevel 1 echo [ERRO] paths
echo.

echo --- [2] config carregado do SSD ---
"%PV%" -c "from app.config import config; config.reload(); print('device_name:', config.get('device_name')); print('recordings_root:', config.recordings_root); print('estudos.python:', config.get('estudos.python')); print('estudos.pasta:', config.get('estudos.pasta')); print('device_id:', config.device_id)"
if errorlevel 1 echo [ERRO] config
echo.

echo --- [3] app.main.build() sobe o servidor ---
"%PV%" -c "from app.main import build; app, mgr, upl = build(); print('build OK - Flask app criado')"
if errorlevel 1 echo [ERRO] build
echo.

echo --- [4] agente MQTT ---
"%PV%" -c "from app.remote.agent import RemoteAgent; a = RemoteAgent(); print('agent OK'); print('topics:', sorted(a.topics.keys()))"
if errorlevel 1 echo [ERRO] agent
echo.

echo --- [5] pipeline.py do sermon carrega ---
"%SV%" -c "import sys; sys.path.insert(0, r'%SERMON_HOME%'); import pipeline; print('pipeline.py OK'); print('NLM:', pipeline.NLM); print('NLM existe:', pipeline.NLM.exists()); print('RCLONE:', pipeline.RCLONE)"
if errorlevel 1 echo [ERRO] pipeline
echo.

echo --- [6] node + send.js do WhatsApp ---
where node >nul 2>nul
if errorlevel 1 (echo [ERRO] node nao esta no PATH) else (node --version)
if exist "%SERMON_HOME%\whatsapp\send.js" (echo send.js OK) else (echo [ERRO] send.js)
if exist "%SERMON_HOME%\node_modules\baileys" (echo baileys OK) else (echo [ERRO] baileys)
echo.

echo --- [7] sessao do WhatsApp (auth) ---
"%SV%" -c "import os; p=r'%SERMON_HOME%\whatsapp\auth'; n=len([f for f in os.listdir(p) if os.path.isfile(os.path.join(p,f))]); print('arquivos de sessao:', n); print('OK' if n>100 else 'ERRO - parear de novo')"
if errorlevel 1 echo [ERRO] auth
echo.

echo --- [8] rclone com o conf do SSD (qual binario esta sendo usado) ---
where rclone >nul 2>nul
if errorlevel 1 (echo [ERRO] rclone nao esta no PATH) else (for /f "delims=" %%i in ('where rclone') do echo   rclone: %%i)
echo   remotes: & rclone listremotes
echo.

echo --- [9] ffmpeg e node no PATH (qual binario esta sendo usado) ---
where ffmpeg >nul 2>nul
if errorlevel 1 (echo [ERRO] ffmpeg) else (for /f "delims=" %%i in ('where ffmpeg') do echo   ffmpeg: %%i)
where ffprobe >nul 2>nul
if errorlevel 1 (echo [ERRO] ffprobe) else (for /f "delims=" %%i in ('where ffprobe') do echo   ffprobe: %%i)
echo.

echo --- [10] token do Google Drive ---
if exist "%PREGACAO_HOME%\config\google_token.json" (echo google_token.json OK) else (echo [ERRO] google_token)
echo.

echo --- [11] .env do EMQX ---
if exist "%PREGACAO_HOME%\.env" (echo .env OK) else (echo [ERRO] .env)
echo.

echo --- [12] perfil do NotebookLM ---
"%SV%" -c "import os; p=os.path.expanduser(r'~\.notebooklm\profiles\default\storage_state.json'); print('storage_state.json:', 'OK' if os.path.exists(p) else 'AUSENTE')"
if errorlevel 1 echo [ERRO] perfil
echo.

echo ============================================================
echo  VERIFICACAO CONCLUIDA
echo ============================================================
