@echo off
REM ============================================================
REM Gravador pregacao-recorder - PC da igreja (Windows)
REM
REM Sobe a interface local (http://127.0.0.1:8080) e a captura
REM de audio (ffmpeg/DirectShow). O controle remoto EMQX fica
REM por conta do iniciar-agente.bat; para subir os dois de uma
REM vez use iniciar-tudo.bat.
REM
REM Para abrir sozinho ao ligar o PC:
REM   schtasks /create /tn "Pregacao Gravador" /tr "\"%~f0\"" /sc onlogon /rl highest
REM ============================================================
setlocal
set "PREGACAO_HOME=%~dp0"
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo [ERRO] .venv nao encontrado em %~dp0
    pause
    exit /b 1
)
call ".venv\Scripts\activate.bat"

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo [ERRO] ffmpeg nao encontrado. Instale com:  winget install Gyan.FFmpeg
    pause
    exit /b 1
)

echo [PC] iniciando gravador (interface em http://127.0.0.1:8080)...
python -m app.main
echo.
echo [PC] gravador encerrado. Feche esta janela ou pressione qualquer tecla.
pause
