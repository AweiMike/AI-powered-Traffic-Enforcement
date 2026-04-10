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
            set "BACKUP=%TARGET%\backend\app_backup_%date:~0,4%%date:~5,2%%date:~8,2%"
            xcopy "%TARGET%\backend\app" "%BACKUP%\app\" /E /I /Q >nul 2>&1
            echo       備份完成
        )

        echo [2/3] 更新後端程式碼...
        xcopy "%UPDATE_DIR%backend" "%TARGET%\backend" /E /I /Y /Q >nul
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

    本次更新內容：
    - 地圖視覺化：事故/違規點位新增「時間」顯示
    - 地圖視覺化：違規點位新增「舉發類型」顯示
    - 綜合執法成效：違規案件新增攔停/逕行舉發細分比較
    - 資料匯入：支援回補既有資料的舉發類型欄位
    - 資料匯入：支援瀏覽器批次上傳多檔案
    - 修復地圖點位顯示問題

    更新方式：
    1. 關閉正在執行的儀表板系統
    2. 雙擊「執行更新.bat」
    3. 按提示操作，完成後重新啟動儀表板
    4. 至「資料匯入」頁面重新批次匯入舉發資料以補齊舉發類型

    注意事項：
    - 資料庫不會被覆蓋，既有資料完整保留
    - 更新前會自動備份舊版程式碼
    """).strip()

    path = os.path.join(UPDATE_DIR, "更新說明.txt")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(changelog)
    print(f"  建立: {path}")


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
    show_summary()


if __name__ == "__main__":
    main()
