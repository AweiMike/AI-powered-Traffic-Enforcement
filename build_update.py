"""
build_update.py - 建立更新包（僅更新程式碼，不重建 Python 環境）

使用方式：python build_update.py
產出位置：deploy/精準執法儀表板-更新檔/

同事只需將更新檔內容覆蓋到既有的「精準執法儀表板」資料夾即可。
"""

import os
import sys
import shutil
import subprocess
import textwrap
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOY_DIR = os.path.join(BASE_DIR, "deploy", "精準執法儀表板")
UPDATE_DIR = os.path.join(BASE_DIR, "deploy", "精準執法儀表板-更新檔")
FRONTEND_DIR = os.path.join(BASE_DIR, "animal-crossing-dashboard")
BACKEND_SRC = os.path.join(BASE_DIR, "backend")


def step(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def build_frontend():
    """打包前端"""
    step("打包前端 (vite build)...")
    out_dir = os.path.join(BACKEND_SRC, "static")

    # 清理舊的 static
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)

    subprocess.check_call(
        ["npx", "vite", "build", "--outDir", out_dir],
        cwd=FRONTEND_DIR,
        shell=True,
    )
    print(f"  前端打包完成: {out_dir}")


def prepare_update_dir():
    """準備更新資料夾"""
    step("準備更新資料夾...")
    if os.path.exists(UPDATE_DIR):
        shutil.rmtree(UPDATE_DIR)
    os.makedirs(UPDATE_DIR, exist_ok=True)


def copy_backend():
    """複製後端程式碼（排除 DB、venv 等）"""
    step("複製後端程式碼...")

    exclude_dirs = {'__pycache__', '.pytest_cache', 'venv', '.venv', 'data', 'static'}
    exclude_files = {'.env', '.env.local'}
    exclude_exts = {'.db', '.sqlite', '.sqlite3', '.pyc', '.log'}

    dst_backend = os.path.join(UPDATE_DIR, "backend")

    for root, dirs, files in os.walk(BACKEND_SRC):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        rel_path = os.path.relpath(root, BACKEND_SRC)
        dst_dir = os.path.join(dst_backend, rel_path)
        os.makedirs(dst_dir, exist_ok=True)

        for f in files:
            if f in exclude_files:
                continue
            if os.path.splitext(f)[1] in exclude_exts:
                continue
            if f.startswith("test_"):
                continue
            shutil.copy2(os.path.join(root, f), os.path.join(dst_dir, f))

    print(f"  複製完成: {dst_backend}")


def copy_frontend_static():
    """複製前端打包檔"""
    step("複製前端靜態檔案...")
    src = os.path.join(BACKEND_SRC, "static")
    dst = os.path.join(UPDATE_DIR, "backend", "static")

    if not os.path.exists(src) or not os.path.exists(os.path.join(src, "index.html")):
        print("  [ERROR] backend/static/ 不存在，請先打包前端")
        sys.exit(1)

    shutil.copytree(src, dst)
    print(f"  複製完成: {dst}")


def copy_bat_files():
    """複製啟動腳本（可能有更新）"""
    step("複製啟動腳本...")

    # 從完整 deploy 複製，或從 build_portable 產生的位置
    for bat_name in ["啟動儀表板.bat", "匯入資料.bat"]:
        src = os.path.join(DEPLOY_DIR, bat_name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(UPDATE_DIR, bat_name))
            print(f"  複製: {bat_name}")


def create_update_bat():
    """建立一鍵更新腳本，供同事使用"""
    step("建立更新腳本...")

    bat = textwrap.dedent(r"""
        @echo off
        chcp 65001 >nul
        title 精準執法儀表板 - 更新程式

        echo.
        echo ========================================
        echo   精準執法儀表板 - 程式更新
        echo   更新日期：__DATE__
        echo ========================================
        echo.
        echo 注意：
        echo   - 請先關閉儀表板系統再更新
        echo   - 資料庫不會被影響（保留既有資料）
        echo.

        set "UPDATE_DIR=%~dp0"
        set "TARGET=%UPDATE_DIR%..\精準執法儀表板"

        REM 自動偵測目標資料夾
        if not exist "%TARGET%\python\python.exe" (
            echo [WARN] 找不到目標資料夾: %TARGET%
            echo.
            set /p TARGET=請輸入「精準執法儀表板」資料夾路徑:
            set TARGET=%TARGET:"=%
        )

        if not exist "%TARGET%\python\python.exe" (
            echo [ERROR] 目標資料夾無效，找不到 python\python.exe
            pause
            exit /b 1
        )

        echo [INFO] 更新目標: %TARGET%
        echo.
        echo 即將覆蓋後端程式碼與前端頁面，是否繼續？
        set /p confirm=輸入 Y 確認:
        if /i not "%confirm%"=="Y" (
            echo 已取消更新。
            pause
            exit /b 0
        )

        echo.
        echo [1/3] 備份舊版後端...
        if exist "%TARGET%\backend\app" (
            set "BACKUP=%TARGET%\backend\app_backup"
            if exist "%BACKUP%" rmdir /S /Q "%BACKUP%" >nul 2>&1
            robocopy "%TARGET%\backend\app" "%BACKUP%\app" /E /NFL /NDL /NJH /NJS /NC /NS /NP >nul 2>&1
            echo       備份完成
        )

        echo [2/3] 更新後端程式碼...
        robocopy "%UPDATE_DIR%backend" "%TARGET%\backend" /E /NFL /NDL /NJH /NJS /NC /NS /NP >nul 2>&1
        echo       後端更新完成

        echo [3/3] 更新啟動腳本...
        if exist "%UPDATE_DIR%啟動儀表板.bat" copy /Y "%UPDATE_DIR%啟動儀表板.bat" "%TARGET%\" >nul
        if exist "%UPDATE_DIR%匯入資料.bat" copy /Y "%UPDATE_DIR%匯入資料.bat" "%TARGET%\" >nul
        echo       腳本更新完成

        echo.
        echo ========================================
        echo   更新完成！
        echo   請重新啟動「啟動儀表板.bat」
        echo ========================================
        echo.
        pause
    """).strip().replace("__DATE__", datetime.now().strftime("%Y-%m-%d"))

    bat_path = os.path.join(UPDATE_DIR, "執行更新.bat")
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.write(bat)
    print(f"  建立: {bat_path}")


def create_changelog():
    """建立更新說明"""
    step("建立更新說明...")

    changelog = textwrap.dedent(f"""
    精準執法儀表板 - 更新說明
    更新日期：{datetime.now().strftime("%Y-%m-%d")}
    ========================================

    本次更新重點：酒駕模組全面強化

    【酒駕成效專區】
    - 新增 A3 事故欄位（原本只有 A1/A2，A3 案件被遺漏）
    - 取締件數依舉發子類細分顯示：主動 / 肇事 / 民檢 / 其他
      ｜可一眼分辨派出所是「主動出擊」還是「被動受理」
    - 新增「管區績效排名（扣除肇事舉發）」區塊：
      ｜以「主動取締」(總取締 − 肇事) 排名 4 個業務管區
      ｜含合併規則：新化+那拔、唪口+知義、左鎮+岡林、山上單獨
      ｜排名 🥇🥈🥉 徽章 + 末位紅色提醒
    - 新增「酒駕肇事率」與「執法缺口」自動判定：
      ｜肇事率 ≥ 30% 且主動率 < 50% → ⚠️ 有缺口
      ｜主動率 ≥ 70% 且肇事率 < 15% → ✅ 無缺口

    【執法缺口頁 → 酒駕分析 tab】
    - 該分頁完全 DUI 專屬化：移除「全因事故」「全因 A1」混雜資料
    - 摘要卡片改版：新增「酒駕肇事率」(取代誤導的全因 A1 死亡卡)
    - 高發區域排名：欄位由「事故/A1」改為「酒駕肇事/無肇事」
    - 時段條形圖視覺強化：
      ｜紅色段 = 無肇事告發、紫色段 = 含肇事舉發
      ｜含肇事時段自動框紫提醒 + 顯示「🚨 肇事 N」徽章
      ｜可直接看出哪個時段最危險

    【資料品質改善（重要）】
    - 既有「酒駕肇事數」誤用 Crash 表 suspected_alcohol 欄位，
      該欄位被派出所避免填寫導致系統性低估（之前長期顯示 0）
    - 改用 Ticket 表 enforcement_subtype = '攔舉-肇事' 為真實計數
      ｜法定強制填寫，比 Crash 表 A1/A2/A3 可靠
    - 影響範圍：酒駕分析 tab、管區排名、時段分析、防治建議

    【Bug 修復】
    - 修復酒駕成效摘要卡片數字消失問題（變數覆寫導致 API 回傳整數而非 dict）

    更新方式：
    1. 關閉正在執行的儀表板系統
    2. 雙擊「執行更新.bat」
    3. 按提示操作，完成後重新啟動儀表板
    4. 既有資料無需重新匯入，新統計邏輯立即生效

    注意事項：
    - 資料庫不會被覆蓋，既有資料完整保留
    - 更新前會自動備份舊版程式碼到 backend/app_backup/
    - 大型車成效頁面同樣缺 A3、缺子類細分（待後續更新處理）
    """).strip()

    path = os.path.join(UPDATE_DIR, "更新說明.txt")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(changelog)
    print(f"  建立: {path}")


def sync_to_main_deploy():
    """將更新內容同步到 deploy/精準執法儀表板/ 主程式資料夾
    讓主程式資料夾保持最新，方便直接複製給新同事安裝。
    """
    if not os.path.exists(DEPLOY_DIR):
        step("[跳過] 主程式資料夾不存在，未同步")
        print(f"  {DEPLOY_DIR}")
        print("  若要建立完整部署資料夾，請執行 build_portable.py")
        return

    if "--no-sync" in sys.argv:
        step("[跳過] --no-sync 已指定，未同步主程式資料夾")
        return

    step("同步更新到主程式資料夾...")

    # 同步 backend
    src_backend = os.path.join(UPDATE_DIR, "backend")
    dst_backend = os.path.join(DEPLOY_DIR, "backend")

    # 使用 shutil 逐檔覆蓋（避免 robocopy 編碼問題）
    count = 0
    for root, dirs, files in os.walk(src_backend):
        # 排除 __pycache__
        dirs[:] = [d for d in dirs if d != '__pycache__']
        rel = os.path.relpath(root, src_backend)
        dst_dir = os.path.join(dst_backend, rel)
        os.makedirs(dst_dir, exist_ok=True)
        for f in files:
            shutil.copy2(os.path.join(root, f), os.path.join(dst_dir, f))
            count += 1

    print(f"  backend/ 已同步 {count} 個檔案")

    # 同步 bat 檔案
    for bat_name in ["啟動儀表板.bat", "匯入資料.bat"]:
        src = os.path.join(UPDATE_DIR, bat_name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(DEPLOY_DIR, bat_name))
            print(f"  {bat_name} 已同步")

    print(f"\n  主程式資料夾已更新至最新版：{DEPLOY_DIR}")
    print("  可直接複製此資料夾給新同事安裝")


def show_summary():
    """顯示結果"""
    total_size = 0
    for root, dirs, files in os.walk(UPDATE_DIR):
        for f in files:
            total_size += os.path.getsize(os.path.join(root, f))
    size_mb = total_size / (1024 * 1024)

    step("更新包建立完成!")
    print(f"""
  產出位置: {UPDATE_DIR}
  總大小:   {size_mb:.1f} MB

  資料夾內容:
    精準執法儀表板-更新檔/
      執行更新.bat       <- 同事雙擊此檔案即可更新
      更新說明.txt       <- 更新內容說明
      啟動儀表板.bat     <- 更新版啟動腳本
      匯入資料.bat       <- 更新版匯入腳本
      backend/           <- 更新的後端程式 + 前端打包檔

  分發方式:
    將「精準執法儀表板-更新檔」資料夾複製給同事，
    放在「精準執法儀表板」旁邊，雙擊「執行更新.bat」即可。
    """)


def main():
    print()
    print("=" * 60)
    print("  精準執法儀表板 - 更新包建立工具")
    print("=" * 60)

    # 詢問是否需要重新打包前端
    if "--skip-frontend" in sys.argv:
        print("\n  [跳過前端打包]")
    else:
        build_frontend()

    prepare_update_dir()
    copy_backend()
    copy_frontend_static()
    copy_bat_files()
    create_update_bat()
    create_changelog()
    sync_to_main_deploy()
    show_summary()


if __name__ == "__main__":
    main()
