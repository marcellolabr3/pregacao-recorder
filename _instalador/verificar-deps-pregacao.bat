@echo off
REM Verifica que todas as dependencias do pregacao-recorder importam
set "PREG=%~dp0..\pregacao-recorder"
"%PREG%\.venv\Scripts\python.exe" -c "import flask, werkzeug, waitress, googleapiclient, google_auth_oauthlib, google_auth_httplib2, paho.mqtt.client; print('DEPS PREGACAO OK')"
