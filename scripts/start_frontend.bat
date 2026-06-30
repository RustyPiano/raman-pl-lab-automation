@echo off
REM Startup script for React frontend on Windows

cd /d "%~dp0\frontend"

echo ========================================
echo  Raman/PL Automation Platform - Frontend
echo ========================================
echo.
echo Starting Vite development server...
echo Frontend will be available at http://localhost:5173
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

npm run dev

pause
