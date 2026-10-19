@echo off
REM Prova que o .env do SSD e lido e o device_id fica o da igreja.
setlocal
set "RAIZ=%~dp0.."
for %%I in ("%RAIZ%") do set "RAIZ=%%~fI"

set "PREGACAO_HOME=%RAIZ%\pregacao-recorder"
set "PATH=%RAIZ%\runtime\nodejs;%RAIZ%\runtime\ffmpeg\bin;%RAIZ%\runtime\rclone;%RAIZ%\runtime\python311;%PATH%"
set "RCLONE_CONFIG=%RAIZ%\runtime\rclone\rclone.conf"

cd /d "%PREGACAO_HOME%"

echo --- .env lido pelo app ---
"%PREGACAO_HOME%\.venv\Scripts\python.exe" -c "from app.config import config, load_env; load_env(); print('device_id      :', config.device_id); print('broker host    :', __import__('os').environ.get('PREGACAO_REMOTE_HOST')); print('broker porta   :', __import__('os').environ.get('PREGACAO_REMOTE_PORT')); print('usuario        :', __import__('os').environ.get('PREGACAO_REMOTE_USERNAME')); print('token operador :', __import__('os').environ.get('PREGACAO_OPERATOR_TOKEN'))"

echo.
echo --- agente com o .env carregado ---
"%PREGACAO_HOME%\.venv\Scripts\python.exe" -c "from app.config import load_env; load_env(); from app.remote.agent import RemoteAgent; a = RemoteAgent(); print('device_id:', a.settings.device_id); print('topico raiz:', a.topics['root']); print('jobs:', a.topics['jobs'])"
