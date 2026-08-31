@echo off
REM Startup script for FastAPI backend on Windows

cd /d "%~dp0.."
call .venv\Scripts\activate.bat

set PYTHONPATH=src

echo ========================================
echo  Raman/PL Automation Platform - API
echo ========================================
echo.
echo Starting FastAPI server on http://127.0.0.1:8008
echo API documentation: http://127.0.0.1:8008/docs
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

uvicorn lab_auto.api.main:app --host 127.0.0.1 --port 8008

pause
