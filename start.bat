@echo off
chcp 65001 >nul
title 精準執法儀表板系統

:menu
cls
echo.
echo ========================================
echo   精準執法儀表板系統 啟動選單
echo ========================================
echo.
echo [1] 啟動完整系統 (後端 + 前端)
echo [2] 僅啟動後端
echo [3] 僅啟動前端
echo [4] 開啟 API 文件
echo [5] 開啟前端網頁
echo [6] 關閉所有服務
echo [0] 離開
echo.

set /p c=請選擇 [0-6]: 

if "%c%"=="1" goto all
if "%c%"=="2" goto be
if "%c%"=="3" goto fe
if "%c%"=="4" goto docs
if "%c%"=="5" goto web
if "%c%"=="6" goto stop
if "%c%"=="0" exit
goto menu

:all
echo.
echo 正在啟動後端服務...
start "Backend Server" cmd /c "cd /d "%~dp0backend" && call venv\Scripts\activate.bat && python run.py"
timeout /t 3 >nul
echo 正在啟動前端服務...
start "Frontend Dev Server" cmd /c "cd /d "%~dp0animal-crossing-dashboard" && npm run dev"
timeout /t 5 >nul
echo 正在開啟瀏覽器...
start chrome http://localhost:5173
goto done

:be
echo.
echo 正在啟動後端服務...
start "Backend Server" cmd /c "cd /d "%~dp0backend" && call venv\Scripts\activate.bat && python run.py"
goto done

:fe
echo.
echo 正在啟動前端服務...
start "Frontend Dev Server" cmd /c "cd /d "%~dp0animal-crossing-dashboard" && npm run dev"
goto done

:docs
start http://localhost:8080/docs
goto done

:web
start chrome http://localhost:5173
goto done

:stop
echo.
echo 正在關閉所有服務...
echo.
REM 關閉 Python 進程 (後端)
taskkill /f /fi "WINDOWTITLE eq Backend Server*" >nul 2>&1
taskkill /f /im python.exe /fi "WINDOWTITLE eq Backend*" >nul 2>&1
REM 關閉 Node 進程 (前端)
taskkill /f /fi "WINDOWTITLE eq Frontend Dev Server*" >nul 2>&1
taskkill /f /im node.exe /fi "WINDOWTITLE eq Frontend*" >nul 2>&1
REM 清理任何殘留的 uvicorn
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8080 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)
echo.
echo 所有服務已關閉！
goto done

:done
echo.
echo 操作完成！按任意鍵返回選單...
pause >nul
goto menu
