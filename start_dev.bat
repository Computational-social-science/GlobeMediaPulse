@echo off
setlocal

echo ==================================================
echo       SpellAtlas Development Environment
echo ==================================================

echo.
echo [1/3] Running Environment Health Check...
python scripts/health_check.py
if %errorlevel% neq 0 (
    echo [ERROR] Health Check Failed. Please fix issues before starting.
    pause
    exit /b %errorlevel%
)

echo.
echo [2/3] Starting Backend (New Window)...
start "Globe Media Pulse Backend" cmd /k "python -m backend.main"

echo.
echo [3/3] Starting Frontend (New Window)...
cd frontend
start "Globe Media Pulse Frontend" cmd /k "npm run dev"
cd ..

echo.
echo [SUCCESS] Services started in separate windows.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo.
pause
