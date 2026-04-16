@echo off
chcp 65001 >nul
title PageIndex Knowledge Base

:menu
cls
echo ========================================
echo    PageIndex Knowledge Base
echo ========================================
echo.
echo   [1] Start All Services
echo   [2] Stop All Services (keep data)
echo   [3] Restart All Services
echo   [4] Rebuild (after code update)
echo   [5] View Service Status
echo   [0] Exit
echo.
set /p choice=Select option [1-5, 0 to exit]:

if "%choice%"=="1" goto start
if "%choice%"=="2" goto stop
if "%choice%"=="3" goto restart
if "%choice%"=="4" goto rebuild
if "%choice%"=="5" goto status
if "%choice%"=="0" exit
goto menu

:start
echo.
echo [Start] Checking Docker...
docker --context desktop-linux info >nul 2>&1
if errorlevel 1 (
    echo [Error] Docker not running. Please start Docker Desktop first.
    pause
    goto menu
)

echo [Start] Stopping old services...
docker --context desktop-linux compose down >nul 2>&1

echo [Start] Starting all services...
docker --context desktop-linux compose up -d --remove-orphans

echo [Start] Waiting for services (8s)...
timeout /t 8 /nobreak >nul

echo.
echo [Start] Service Status:
docker --context desktop-linux compose ps
echo.
echo URLs:
echo   - Frontend: http://localhost:3001
echo   - API:      http://localhost:8001
echo   - Ollama:   http://localhost:11434
echo.
pause
goto menu

:stop
echo.
echo [Stop] Stopping all services...
docker --context desktop-linux compose stop
echo [Stop] All services stopped. Data preserved.
echo.
pause
goto menu

:restart
echo.
echo [Restart] Restarting all services...
docker --context desktop-linux compose down
docker --context desktop-linux compose up -d --remove-orphans
echo.
echo [Restart] Service Status:
docker --context desktop-linux compose ps
echo.
pause
goto menu

:rebuild
echo.
echo [Rebuild] Building and starting all services...
docker --context desktop-linux compose build
docker --context desktop-linux compose up -d --remove-orphans
echo.
echo [Rebuild] Done.
echo.
pause
goto menu

:status
echo.
docker --context desktop-linux compose ps
echo.
pause
goto menu
