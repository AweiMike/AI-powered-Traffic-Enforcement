@echo off
chcp 65001 >nul
title 精準執法儀表板 - 後端伺服器

echo.
echo ========================================
echo 🌿 精準執法儀表板系統 - 後端啟動
echo ========================================
echo.

cd /d "%~dp0backend"

REM 檢查虛擬環境是否存在
if not exist "venv\" (
    echo ⚠️  虛擬環境不存在，正在創建...
    python -m venv venv
    echo ✅ 虛擬環境創建完成
    echo.

    echo 📦 安裝依賴套件...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    echo ✅ 依賴安裝完成
    echo.
) else (
    call venv\Scripts\activate.bat
)

echo 🚀 啟動後端伺服器...
echo.
echo 📍 API 端點: http://localhost:8000/api/v1
echo 📚 API 文件: http://localhost:8000/docs
echo.
echo ⚠️  按 Ctrl+C 可停止伺服器
echo ========================================
echo.

python run.py

pause
