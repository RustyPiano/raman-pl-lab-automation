@echo off
REM Windows installation script for Raman/PL Automation Platform

cd /d "%~dp0.."

echo ========================================
echo  Raman/PL Platform - Windows Installation
echo ========================================
echo.

REM Check Python
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.12+ from https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version
echo.

REM Check Node.js
echo [2/5] Checking Node.js installation...
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js 20.19+ from https://nodejs.org/
    pause
    exit /b 1
)
node --version
npm --version
echo.

REM Create virtual environment
echo [3/5] Creating Python virtual environment...
if exist .venv (
    echo Virtual environment already exists, skipping...
) else (
    python -m venv .venv
    echo Virtual environment created successfully
)
echo.

REM Install Python dependencies
echo [4/5] Installing Python dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -e ".[api,recognition]"
echo Python dependencies installed successfully
echo.

REM Install frontend dependencies
echo [5/5] Installing frontend dependencies...
cd frontend
call npm install
cd ..
echo Frontend dependencies installed successfully
echo.

echo ========================================
echo  Installation Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Configure devices.yaml with your hardware settings
echo 2. Run start_api.bat to start the backend
echo 3. Run start_frontend.bat to start the frontend
echo.
echo For detailed instructions, see WINDOWS_SETUP.md
echo.

pause
