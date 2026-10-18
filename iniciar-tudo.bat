@echo off
REM ============================================================
REM Pregacao - tudo de uma vez (PC da igreja, Windows)
REM
REM Sobe o agente MQTT (janela minimizada) e depois o gravador
REM (janela principal). Unico atalho necessario no dia a dia.
REM
REM Automatico ao ligar o PC (com o usuario ja logado):
REM   schtasks /create /tn "Pregacao" /tr "\"%~f0\"" /sc onlogon /rl highest
REM ============================================================
setlocal
cd /d "%~dp0"

if not exist "iniciar-agente.bat" goto :falta
if not exist "iniciar-gravador.bat" goto :falta

start "Pregacao Agente MQTT" /min "%~dp0iniciar-agente.bat"
start "Pregacao Gravador" /min "%~dp0iniciar-gravador.bat"
exit /b 0

:falta
echo [ERRO] iniciar-agente.bat / iniciar-gravador.bat nao encontrados em %~dp0
pause
