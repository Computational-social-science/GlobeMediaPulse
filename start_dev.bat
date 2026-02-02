@echo off
echo ===================================================
echo   Globe Media Pulse - Development Environment
echo ===================================================
echo.
echo [MODE] Static Frontend Development (Zero-cost)
echo   - Frontend: Local (localhost:5173)
echo   - Backend:  Disabled (uses built-time static data)
echo.
echo Syncing frontend resources...
python scripts/build_frontend_data.py
echo.
echo Starting Frontend...
if "%VITE_STATIC_MODE%"=="" set VITE_STATIC_MODE=1
cd frontend
call npm run dev
pause
