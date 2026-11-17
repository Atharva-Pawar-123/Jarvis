@echo off
title JARVIS System Launcher
cd /d "%~dp0"

echo ===================================================================
echo         J.A.R.V.I.S — ONE-CLICK LAUNCHER (V2.2)                    
echo ===================================================================

if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" "%~dp0start_jarvis.py"
) else (
    python "%~dp0start_jarvis.py"
)

pause
