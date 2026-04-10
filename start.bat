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
echo [1] 啟動完整系統 (後端 + 前端 開發模式)
echo [2] 僅啟動後端
echo [3] 僅啟動前端
echo [4] 開啟 API 文件
echo [5] 開啟前端網頁
echo [6] 關閉所有服務
echo [7] 清除資料庫 (重置系統)
echo [8] 內網分享模式 (Port 80, 同事可連線)
echo [9] 重新打包前端 (更新後需執行)
echo [0] 離開
echo.

set /p c=請選擇 [0-9]:

if "%c%"=="1" goto all
if "%c%"=="2" goto be
if "%c%"=="3" goto fe
if "%c%"=="4" goto docs
if "%c%"=="5" goto web
if "%c%"=="6" goto stop
if "%c%"=="7" goto reset
if "%c%"=="8" goto prod
if "%c%"=="9" goto rebuild
if "%c%"=="0" exit
goto menu

:all
echo.
echo 正在啟動後端服務...
start "Backend Server" cmd /k "cd /d %~dp0backend && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080"
timeout /t 5 >nul
echo 正在啟動前端服務...
start "Frontend Dev Server" cmd /k "cd /d %~dp0animal-crossing-dashboard && npm run dev"
timeout /t 5 >nul
echo 正在開啟瀏覽器...
start "" "http://localhost:5173"
goto done

:be
echo.
echo 正在啟動後端服務...
start "Backend Server" cmd /k "cd /d %~dp0backend && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080"
goto done

:fe
echo.
echo 正在啟動前端服務...
start "Frontend Dev Server" cmd /k "cd /d %~dp0animal-crossing-dashboard && npm run dev"
goto done

:docs
start "" "http://localhost:8080/docs"
goto done

:web
start "" "http://localhost:5173"
goto done

:stop
echo.
echo 正在關閉所有服務...
echo.
REM 關閉 Python/uvicorn 進程 (後端)
taskkill /f /im python.exe >nul 2>&1
REM 關閉 Node 進程 (前端)
taskkill /f /im node.exe >nul 2>&1
echo.
echo 所有服務已關閉！
echo 所有服務已關閉！
goto done

:reset
echo.
echo 警告：這將刪除所有資料庫內容並重置系統！
set /p confirm=確定要繼續嗎？ (Y/N): 
if /i not "%confirm%"=="Y" goto menu

echo.
echo 正在停止服務以解鎖資料庫...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im uvicorn.exe >nul 2>&1

echo.
echo 正在刪除資料庫檔案...
if exist "backend\data\traffic_enforcement.db" (
    del /f /q "backend\data\traffic_enforcement.db"
    echo 資料庫已刪除。
) else (
    echo 資料庫檔案不存在 (無需刪除)。
)

echo.
echo 請重新選擇 [1] 或 [2] 以啟動系統 (系統將自動建立新資料庫)。
goto done

:prod
echo.
echo ========================================
echo   內網分享模式 (Port 80)
echo ========================================
echo.

REM 取得本機 IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4" ^| findstr /v "127.0.0.1"') do (
    set "LOCAL_IP=%%a"
    goto :got_ip
)
:got_ip
set LOCAL_IP=%LOCAL_IP: =%

echo 同事連線: http://%LOCAL_IP%
echo 唯讀模式: http://%LOCAL_IP%/#view
echo.

REM 優先使用 deploy 的 embedded Python（繞過防火牆封鎖 python.exe）
set "DEPLOY_PYTHON=%~dp0deploy\精準執法儀表板\python\python.exe"

if exist "%DEPLOY_PYTHON%" (
    echo 使用 embedded Python 啟動（繞過防火牆）...
    start "Production Server" cmd /k "cd /d %~dp0backend && "%DEPLOY_PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 80"
) else (
    echo 找不到 embedded Python，使用 venv 啟動...
    echo 若同事無法連線，請先執行 python build_portable.py 建立 deploy 資料夾
    start "Production Server" cmd /k "cd /d %~dp0backend && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 80"
)
timeout /t 3 >nul
echo 正在開啟瀏覽器...
start "" "http://localhost"
goto done

:rebuild
echo.
echo 正在重新打包前端...
cd /d %~dp0animal-crossing-dashboard
call npx vite build --outDir ../backend/static
echo.
echo 前端已重新打包完成！
goto done

:done
echo.
echo 操作完成！按任意鍵返回選單...
pause >nul
goto menu
