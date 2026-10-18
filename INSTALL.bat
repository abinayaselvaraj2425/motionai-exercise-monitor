@echo off
setlocal
cd /d "%~dp0"
set "SETUP_PYTHON=python"
if defined MOTIONAI_PYTHON set "SETUP_PYTHON=%MOTIONAI_PYTHON%"
where node >nul 2>nul
if errorlevel 1 goto missing_node
"%SETUP_PYTHON%" -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 goto failed
if exist ".venv\Scripts\python.exe" goto install
"%SETUP_PYTHON%" -m venv .venv
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
call npm ci
if errorlevel 1 goto failed
".venv\Scripts\python.exe" scripts/download_assets.py
if errorlevel 1 goto failed
".venv\Scripts\python.exe" scripts/download_checkpoint.py
if errorlevel 1 goto failed
call npm run build
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m backend.launch --check
if errorlevel 1 goto failed
echo Setup complete. Double-click START_APP.bat. Keep its window open.
pause
exit /b 0
:missing_node
echo Install Node.js 22 or newer, then retry.
:failed
echo Setup failed. Install Python 3.11+ and Node.js 22+, check your internet connection, and review the error above.
pause
exit /b 1
