@echo off
chcp 65001 >nul
title 打包精準執法儀表板系統

echo.
echo ========================================
echo 📦 打包精準執法儀表板系統成 EXE
echo ========================================
echo.

REM 安裝打包所需依賴
echo 📥 安裝打包依賴...
pip install -r requirements_launcher.txt
echo.

REM 執行打包腳本
echo 🚀 開始打包...
python build_exe.py

echo.
echo ========================================
echo 按任意鍵退出...
pause >nul
