@echo off
title Faceless Shorts Studio v2 (English + YouTube Scheduler)
echo ============================================================
echo   Faceless Shorts Automation Studio v2
echo   Backend: http://127.0.0.1:8765
echo   Frontend: http://localhost:5173
echo ============================================================

set PYTHON_EXE=python
if exist ".venv\Scripts\python.exe" (
    set PYTHON_EXE=.venv\Scripts\python.exe
) else if exist "..\automatic-YT\.venv\Scripts\python.exe" (
    set PYTHON_EXE=..\automatic-YT\.venv\Scripts\python.exe
)

echo Using Python: %PYTHON_EXE%

start "Shorts-v2-Backend" cmd /k "%PYTHON_EXE% -m uvicorn backend.main:app --host 127.0.0.1 --port 8765 --reload --reload-dir backend"
start "Shorts-v2-Frontend" cmd /k "cd frontend && npm run dev"

echo Both servers starting... Open http://localhost:5173 in your browser.
