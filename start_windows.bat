@echo off
setlocal
cd /d "%~dp0"
title Career Story Agent - Start

echo =========================================
echo   Career Story Agent - Local Startup

echo =========================================
where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python was not found. Install Python 3.11+ and restart this script.
  goto fail
)
where npm >nul 2>nul
if errorlevel 1 (
  echo ERROR: Node.js/npm was not found. Install Node.js 22 LTS and restart.
  goto fail
)
if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Creating Python virtual environment...
  python -m venv .venv
  if errorlevel 1 goto fail
)
echo [2/4] Installing backend dependencies...
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 goto fail
echo [3/4] Installing frontend dependencies...
pushd frontend
call npm install
if errorlevel 1 (
  popd
  goto fail
)
popd
echo [4/4] Starting backend and frontend in separate terminals...
start "Career Story API" /D "%CD%" cmd /k ".venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000"
start "Career Story Web" /D "%CD%\frontend" cmd /k "npm run dev"
timeout /t 4 /nobreak >nul
start "" http://127.0.0.1:5173
echo.
echo Started. Keep both command windows open while using the app.
echo Configure .env and restart to enable real AI.
pause
exit /b 0
:fail
echo.
echo Startup failed. Check the message above and README.md.
pause
exit /b 1
