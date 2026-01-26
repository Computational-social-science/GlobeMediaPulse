@echo off
echo ===================================================
echo   Globe Media Pulse - Development Environment
echo ===================================================
echo.
echo [MODE] Hybrid Development
echo   - Frontend: Local (localhost:5173)
echo   - Backend:  Remote (https://globe-media-pulse.fly.dev)
echo.
echo Syncing frontend resources...
python scripts/build_frontend_data.py
echo.
echo Starting Frontend...
set VITE_API_URL=https://globe-media-pulse.fly.dev
set VITE_WS_URL=wss://globe-media-pulse.fly.dev
cd frontend
call npm run dev
pause
