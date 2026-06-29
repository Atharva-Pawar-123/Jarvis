@echo off
echo ============================================
echo         JARVIS Setup Script
echo ============================================

REM Activate venv
call D:\JARVIS\venv\Scripts\activate.bat

REM Install all requirements
echo.
echo [1/3] Installing Python dependencies...
pip install -r D:\JARVIS\requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed. Check requirements.txt and your internet connection.
    pause
    exit /b 1
)

REM Download Piper voice model if not present
echo.
echo [2/3] Checking Piper voice model...
if not exist "D:\JARVIS\models\piper\en_US-lessac-high.onnx" (
    echo Downloading Piper voice model (approx 108MB)...
    mkdir D:\JARVIS\models\piper 2>nul
    powershell -Command "Invoke-WebRequest -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high/en_US-lessac-high.onnx' -OutFile 'D:\JARVIS\models\piper\en_US-lessac-high.onnx' -UseBasicParsing"
    powershell -Command "Invoke-WebRequest -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high/en_US-lessac-high.onnx.json' -OutFile 'D:\JARVIS\models\piper\en_US-lessac-high.onnx.json' -UseBasicParsing"
    echo Piper voice model downloaded.
) else (
    echo Piper voice model already present. Skipping download.
)

echo.
echo [3/3] Verifying Ollama...
curl -s http://localhost:11434 >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Ollama does not appear to be running at http://localhost:11434
    echo Please start Ollama before running JARVIS.
    echo Run: ollama serve
) else (
    echo Ollama is running.
)

echo.
echo ============================================
echo Setup complete!
echo Run JARVIS with:
echo     cd D:\JARVIS
echo     .\venv\Scripts\Activate.ps1
echo     python main.py
echo ============================================
pause
