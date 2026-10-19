@echo off
REM Verifica os 4 runtimes portateis do E:
set "RT=%~dp0..\runtime"

echo === PYTHON ===
"%RT%\python311\python.exe" --version
if errorlevel 1 (echo [ERRO] python) else (echo [OK] python)

echo.
echo === NODE ===
"%RT%\nodejs\node.exe" --version
if errorlevel 1 (echo [ERRO] node) else (echo [OK] node)

echo.
echo === NPM ===
"%RT%\nodejs\npm.cmd" --version
if errorlevel 1 (echo [ERRO] npm) else (echo [OK] npm)

echo.
echo === FFMPEG ===
"%RT%\ffmpeg\bin\ffmpeg.exe" -version 2>&1 | findstr /i "ffmpeg version"
if errorlevel 1 (echo [ERRO] ffmpeg) else (echo [OK] ffmpeg)

echo.
echo === RCLONE ===
"%RT%\rclone\rclone.exe" version 2>&1 | findstr /i "rclone"
if errorlevel 1 (echo [ERRO] rclone) else (echo [OK] rclone)
