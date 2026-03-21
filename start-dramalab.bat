@echo off
title DramaLab Studio
echo ============================================
echo   DramaLab Studio - Starting...
echo ============================================
echo.

cd /d "C:\Users\david\dev\dramalab"

:: Kill any existing processes on our ports
echo Cleaning up old processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING" 2^>nul') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000.*LISTENING" 2^>nul') do taskkill /f /pid %%a >nul 2>&1
timeout /t 1 /nobreak >nul

:: Start API backend (use packages\studio as cwd so uvicorn finds the module)
echo [1/2] Starting API backend on port 8000...
cd /d "C:\Users\david\dev\dramalab\packages\studio"
start /b "" python -m uvicorn dramalab_studio.server:app --host 0.0.0.0 --port 8000 2>&1

:: Wait for API to be ready
timeout /t 3 /nobreak >nul

:: Start frontend
echo [2/2] Starting frontend on port 3000...
cd /d "C:\Users\david\dev\dramalab\packages\studio\frontend"
start /b "" npx next dev --port 3000 2>&1

:: Wait for frontend to be ready
timeout /t 6 /nobreak >nul

echo.
echo ============================================
echo   DramaLab Studio is running!
echo.
echo   Frontend: http://localhost:3000
echo   API:      http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo ============================================
echo.
echo Opening browser...
start http://localhost:3000

echo.
echo Press any key to stop all services...
pause >nul

:: Cleanup - kill processes by port (most reliable)
echo Stopping services...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING" 2^>nul') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000.*LISTENING" 2^>nul') do taskkill /f /pid %%a >nul 2>&1
echo Done. Bye!
