@echo off
chcp 65001 >nul
title 精準執法儀表板 - 前端介面

echo.
echo ========================================
echo 🌿 精準執法儀表板系統 - 前端啟動
echo ========================================
echo.

cd /d "%~dp0animal-crossing-dashboard"

REM 檢查 node_modules 是否存在
if not exist "node_modules\" (
    echo ⚠️  依賴套件未安裝，正在安裝...
    call npm install
    echo ✅ 依賴安裝完成
    echo.
)

echo 🚀 啟動前端開發伺服器...
echo.
echo 🌐 前端網址: http://localhost:5173
echo 📡 後端連接: http://localhost:8000
echo.
echo ⚠️  按 Ctrl+C 可停止伺服器
echo ========================================
echo.

call npm run dev

pause
