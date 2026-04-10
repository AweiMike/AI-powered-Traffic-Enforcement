@echo off
chcp 65001 >nul
title 初始化 SQLite 資料庫

echo ========================================
echo 精準執法儀表板系統
echo SQLite 資料庫初始化
echo ========================================
echo.

cd /d "%~dp0backend"

echo 正在初始化資料庫...
echo.

call venv\Scripts\activate.bat
python scripts\init_sqlite.py

if errorlevel 1 (
    echo.
    echo ❌ 初始化失敗！
    echo.
) else (
    echo.
    echo ✅ 初始化成功！
    echo.
)

pause
