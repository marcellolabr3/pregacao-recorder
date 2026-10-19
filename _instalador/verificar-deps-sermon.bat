@echo off
REM Verifica que todas as dependencias do sermon-pipeline importam
set "SER=%~dp0..\sermon-pipeline"
"%SER%\.venv\Scripts\python.exe" -c "import notebooklm, markdown, xhtml2pdf, sounddevice, numpy, playwright, pystray, PIL, lameenc, rookie_cookies; print('DEPS SERMON OK')"
