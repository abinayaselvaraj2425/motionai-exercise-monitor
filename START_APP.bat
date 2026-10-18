@echo off
setlocal
cd /d "%~dp0"
set "APP_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "APP_PYTHON=%~dp0.venv\Scripts\python.exe"
if defined MOTIONAI_PYTHON set "APP_PYTHON=%MOTIONAI_PYTHON%"
"%APP_PYTHON%" -m backend.launch --open-browser
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo MotionAI could not start. Read the message above. Run INSTALL.bat if setup is incomplete.
pause
exit /b 1
