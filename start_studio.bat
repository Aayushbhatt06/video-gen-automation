@echo off
title Antigravity Faceless Shorts Studio (Backend + React.js Dashboard)
echo ============================================================================
echo   Starting Antigravity Faceless Shorts Studio...
echo   - Local Backend API : http://127.0.0.1:8765
echo   - React.js Dashboard: http://127.0.0.1:5173
echo ============================================================================
start "Shorts Backend API" cmd /k "cd /d %~dp0 && .\.venv\Scripts\python.exe scripts/server.py"
cd /d "%~dp0dashboard"
npm run dev
