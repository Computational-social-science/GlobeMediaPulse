@echo off
echo ===================================================
echo   Globe Media Pulse - Development Environment
echo ===================================================
echo.
echo [MODE] Hybrid Development
echo   - Frontend: Local (localhost:5173)
echo   - Backend:  Remote (globe-media-pulse.fly.dev)
echo.
echo Starting Frontend...
cd frontend
call npm run dev
pause