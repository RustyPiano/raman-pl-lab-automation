@echo off
REM Check available COM ports on Windows

cd /d "%~dp0.."

echo ========================================
echo  COM Port Detection
echo ========================================
echo.

call .venv\Scripts\activate.bat 2>nul
if errorlevel 1 (
    echo Virtual environment not found. Creating temporary environment...
    python -m venv .venv_temp
    call .venv_temp\Scripts\activate.bat
    pip install pyserial -q
    set TEMP_ENV=1
)

echo Scanning for available COM ports...
echo.

python -m serial.tools.list_ports

echo.
echo ========================================
echo Configure these ports in devices.yaml
echo ========================================

if defined TEMP_ENV (
    deactivate
    rmdir /S /Q .venv_temp
)

pause
