@echo off
REM ============================================================
REM Agente MQTT do controle remoto - PC da igreja (Windows)
REM
REM Abra este arquivo (duplo clique) e deixe a janela aberta.
REM Ele le o .env desta pasta e conecta no EMQX Cloud; o app do
REM celular passa a mostrar ONLINE. Sem o agente, o app fica
REM OFFLINE - e' o unico "servico" que o controle remoto pede.
REM
REM Para abrir sozinho ao ligar o PC:
REM   schtasks /create /tn "Pregacao Agente" /tr "\"%~f0\"" /sc onlogon /rl highest
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

echo [PC] iniciando agente de controle remoto (EMQX)...
echo [PC] PREGACAO_HOME=%PREGACAO_HOME%
python -m app.remote.agent
echo.
echo [PC] agente encerrado. Feche esta janela ou pressione qualquer tecla.
pause
