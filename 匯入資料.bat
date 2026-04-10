@echo off
chcp 65001 > nul
title 精準執法 - 資料匯入工具

echo.
echo ============================================================
echo           精準執法儀表板系統 - 資料匯入工具
echo ============================================================
echo.

cd /d "%~dp0backend"

if not exist "venv\Scripts\activate.bat" (
    echo ❌ 找不到 Python 虛擬環境，請先執行安裝。
    pause
    exit /b 1
)

call venv\Scripts\activate

echo 📂 請將 Excel 檔案放在專案根目錄，然後選擇操作：
echo.
echo    [1] 匯入全部（事故 + 舉發）
echo    [2] 僅匯入事故資料
echo    [3] 僅匯入舉發資料
echo    [4] 初始化資料庫（不匯入資料）
echo    [5] 查看資料庫統計
echo    [0] 離開
echo.

set /p choice=請選擇 (0-5): 

if "%choice%"=="1" goto import_all
if "%choice%"=="2" goto import_crash
if "%choice%"=="3" goto import_ticket
if "%choice%"=="4" goto init_db
if "%choice%"=="5" goto show_stats
if "%choice%"=="0" goto end

echo ❌ 無效選項
pause
goto end

:import_all
echo.
echo 🔄 匯入全部資料...
python scripts\import_data.py --crash "..\交通事故案件清冊_已處理.xlsx" --ticket "..\舉發案件綜合查詢.xlsx"
goto done

:import_crash
echo.
set /p crash_file=請輸入事故 Excel 路徑 (或按 Enter 使用預設): 
if "%crash_file%"=="" set crash_file=..\交通事故案件清冊_已處理.xlsx
python scripts\import_data.py --crash "%crash_file%"
goto done

:import_ticket
echo.
set /p ticket_file=請輸入舉發 Excel 路徑 (或按 Enter 使用預設): 
if "%ticket_file%"=="" set ticket_file=..\舉發案件綜合查詢.xlsx
python scripts\import_data.py --ticket "%ticket_file%"
goto done

:init_db
echo.
echo 🔧 初始化資料庫...
python scripts\import_data.py --init
goto done

:show_stats
echo.
echo 📊 資料庫統計...
python -c "
import sys
sys.path.insert(0, 'app')
from database import SessionLocal
from models.core import Crash, Ticket

db = SessionLocal()
print()
print('='*50)
print('資料庫統計')
print('='*50)
print(f'事故總數: {db.query(Crash).count()}')
print(f'舉發總數: {db.query(Ticket).count()}')
print(f'  - 酒駕: {db.query(Ticket).filter(Ticket.topic_dui == True).count()}')
print(f'  - 闘紅燈: {db.query(Ticket).filter(Ticket.topic_red_light == True).count()}')
print(f'  - 危險駕駛: {db.query(Ticket).filter(Ticket.topic_dangerous == True).count()}')
print(f'  - 高齡者: {db.query(Ticket).filter(Ticket.is_elderly == True).count()}')
db.close()
"
goto done

:done
echo.
echo ✅ 操作完成！
pause
goto end

:end
