@echo off
title UAE Real Estate Decision Intelligence Platform
color 0A

REM ── Resolve project root ────────────────────────────────────────
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

REM ── Use venv Python if available ────────────────────────────────
set "PYTHON=%ROOT%\venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    set "PYTHON=python"
    echo  [INFO] Venv not found, using system Python
) else (
    echo  [OK] Using venv Python ^(Python 3.10^)
)

echo.
echo  ===================================================
echo   UAE Real Estate Decision Intelligence Platform
echo   v2.0 Enterprise
echo  ===================================================
echo.

REM ── FastAPI Backend ─────────────────────────────────────────────
echo  [1/2] Starting FastAPI Backend on port 8000 ...
start "FastAPI Backend" cmd /k "cd /d "%ROOT%" && "%PYTHON%" run_backend.py"

echo  Waiting 15 seconds for backend to load data lake ...
timeout /t 15 /nobreak > nul

REM ── Streamlit Frontend ──────────────────────────────────────────
echo  [2/2] Starting Streamlit Frontend on port 8501 ...
start "Streamlit Frontend" cmd /k "cd /d "%ROOT%" && set PYTHONPATH=%ROOT% && "%PYTHON%" -m streamlit run frontend\app.py --server.port 8501 --server.headless false --browser.gatherUsageStats false"

echo.
echo  ===================================================
echo   Platform is live:
echo     Frontend  ->  http://localhost:8501
echo     API Docs  ->  http://localhost:8000/docs
echo     Health    ->  http://localhost:8000/health
echo  ===================================================
echo.
echo  Press any key to open the browser ...
pause > nul
start http://localhost:8501
