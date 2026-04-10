"""
build_portable.py - 建立可攜式部署資料夾
產出一個完整的資料夾，複製到任何 Windows 電腦即可執行（不需安裝 Python）

使用方式：python build_portable.py
產出位置：deploy/精準執法儀表板/
"""

import os
import sys
import shutil
import subprocess
import urllib.request
import zipfile
import textwrap

# ============================================
# 設定
# ============================================
PYTHON_VERSION = "3.12.7"
PYTHON_ZIP = f"python-{PYTHON_VERSION}-embed-amd64.zip"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/{PYTHON_ZIP}"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOY_DIR = os.path.join(BASE_DIR, "deploy", "精準執法儀表板")
PYTHON_DIR = os.path.join(DEPLOY_DIR, "python")
BACKEND_DIR = os.path.join(DEPLOY_DIR, "backend")


def step(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def clean_deploy():
    """清理舊的部署資料夾"""
    if os.path.exists(DEPLOY_DIR):
        step("清理舊的部署資料夾...")
        shutil.rmtree(DEPLOY_DIR)
    os.makedirs(DEPLOY_DIR, exist_ok=True)


def download_python():
    """下載 Python Embeddable Package"""
    step(f"下載 Python {PYTHON_VERSION} Embeddable...")
    zip_path = os.path.join(BASE_DIR, "deploy", PYTHON_ZIP)

    if not os.path.exists(zip_path):
        print(f"  下載中: {PYTHON_URL}")
        urllib.request.urlretrieve(PYTHON_URL, zip_path)
        print(f"  完成: {zip_path}")
    else:
        print(f"  已存在，跳過下載: {zip_path}")

    # 解壓
    print(f"  解壓到: {PYTHON_DIR}")
    os.makedirs(PYTHON_DIR, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(PYTHON_DIR)

    # 啟用 import site（讓 pip 的 site-packages 可用）
    pth_file = os.path.join(PYTHON_DIR, f"python312._pth")
    if os.path.exists(pth_file):
        with open(pth_file, 'r') as f:
            content = f.read()
        # 取消 import site 的註解
        content = content.replace("#import site", "import site")
        with open(pth_file, 'w') as f:
            f.write(content)
        print("  已啟用 import site")


def install_pip():
    """安裝 pip"""
    step("安裝 pip...")
    python_exe = os.path.join(PYTHON_DIR, "python.exe")
    get_pip_path = os.path.join(PYTHON_DIR, "get-pip.py")

    print(f"  下載 get-pip.py...")
    urllib.request.urlretrieve(GET_PIP_URL, get_pip_path)

    print(f"  執行 get-pip.py...")
    subprocess.check_call([python_exe, get_pip_path, "--no-warn-script-location"],
                          cwd=PYTHON_DIR)
    os.remove(get_pip_path)
    print("  pip 安裝完成")


def install_packages():
    """安裝後端依賴套件"""
    step("安裝後端依賴套件...")
    python_exe = os.path.join(PYTHON_DIR, "python.exe")
    req_file = os.path.join(BASE_DIR, "backend", "requirements.txt")

    subprocess.check_call([
        python_exe, "-m", "pip", "install",
        "-r", req_file,
        "--no-warn-script-location",
        "--disable-pip-version-check"
    ], cwd=PYTHON_DIR)
    print("  套件安裝完成")


def copy_backend():
    """複製後端程式碼（排除不需要的檔案）"""
    step("複製後端程式碼...")

    # 要排除的檔案/目錄
    exclude_dirs = {'__pycache__', '.pytest_cache', 'venv', '.venv', 'data', 'static'}
    exclude_files = {'.env', '.env.local'}
    exclude_exts = {'.db', '.sqlite', '.sqlite3', '.pyc', '.log'}

    src = os.path.join(BASE_DIR, "backend")

    for root, dirs, files in os.walk(src):
        # 排除目錄
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        rel_path = os.path.relpath(root, src)
        dst_dir = os.path.join(BACKEND_DIR, rel_path)
        os.makedirs(dst_dir, exist_ok=True)

        for f in files:
            if f in exclude_files:
                continue
            if os.path.splitext(f)[1] in exclude_exts:
                continue
            # 排除測試檔案
            if f.startswith("test_"):
                continue

            shutil.copy2(os.path.join(root, f), os.path.join(dst_dir, f))

    # 確保 data 目錄存在（空的，供執行時建立 DB）
    os.makedirs(os.path.join(BACKEND_DIR, "data"), exist_ok=True)
    print(f"  複製完成: {BACKEND_DIR}")


def copy_frontend_build():
    """複製前端已打包檔案"""
    step("複製前端打包檔案...")
    src_static = os.path.join(BASE_DIR, "backend", "static")
    dst_static = os.path.join(BACKEND_DIR, "static")

    if not os.path.exists(src_static) or not os.path.exists(os.path.join(src_static, "index.html")):
        print("  [WARN] backend/static/ 不存在或缺少 index.html")
        print("  請先執行: cd animal-crossing-dashboard && npx vite build --outDir ../backend/static")
        sys.exit(1)

    shutil.copytree(src_static, dst_static)
    print(f"  複製完成: {dst_static}")


def create_start_bat():
    """建立啟動腳本"""
    step("建立啟動腳本...")

    bat_content = textwrap.dedent(r"""
        @echo off
        chcp 65001 >nul
        title 精準執法儀表板系統

        set "BASE=%~dp0"
        set "PYTHON=%BASE%python\python.exe"
        set "BACKEND=%BASE%backend"

        echo.
        echo ========================================
        echo   精準執法儀表板系統
        echo ========================================
        echo.

        REM 檢查 Python
        if not exist "%PYTHON%" (
            echo [ERROR] 找不到 Python，請確認資料夾完整性
            pause
            exit /b 1
        )

        REM 初始化資料庫（如不存在）
        if not exist "%BACKEND%\data\traffic_enforcement.db" (
            echo [INFO] 首次啟動，正在初始化資料庫...
            "%PYTHON%" -c "import sys; sys.path.insert(0, r'%BACKEND%'); from app.database import engine; from app.models.core import Base; Base.metadata.create_all(bind=engine)"
            echo [OK] 資料庫初始化完成
            echo.
        )

        echo [START] 正在啟動系統...
        echo.
        echo   本機瀏覽: http://localhost
        echo   關閉視窗即可停止服務
        echo.

        start "" "http://localhost"
        cd /d "%BACKEND%"
        "%PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 80
        pause
    """).strip()

    bat_path = os.path.join(DEPLOY_DIR, "啟動儀表板.bat")
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.write(bat_content)
    print(f"  建立: {bat_path}")

    # 匯入資料用的 bat（自動偵測檔案類型）
    import_bat = textwrap.dedent(r"""
        @echo off
        chcp 65001 >nul
        title 匯入資料

        set "BASE=%~dp0"
        set "PYTHON=%BASE%python\python.exe"
        set "BACKEND=%BASE%backend"

        echo.
        echo ========================================
        echo   匯入資料到儀表板
        echo ========================================
        echo.
        echo 使用方式：將 Excel/TXT 檔案拖曳到此視窗
        echo.
        echo 自動偵測規則：
        echo   .xls          → 事故資料（交通事故案件清冊）
        echo   .txt          → 事故資料（EIS 事故調查表）
        echo   .xlsx         → 舉發資料（舉發案件綜合查詢）
        echo.

        set /p filepath=請輸入或拖曳檔案路徑:

        REM 去除引號
        set filepath=%filepath:"=%

        if not exist "%filepath%" (
            echo [ERROR] 檔案不存在: %filepath%
            pause
            exit /b 1
        )

        REM 自動偵測檔案類型
        set "EXT=%filepath:~-4%"
        set "EXT5=%filepath:~-5%"
        set "IMPORT_FLAG="

        if /i "%EXT%"==".xls" set "IMPORT_FLAG=--crash"
        if /i "%EXT%"==".txt" set "IMPORT_FLAG=--crash"
        if /i "%EXT5%"==".xlsx" set "IMPORT_FLAG=--ticket"

        if not defined IMPORT_FLAG (
            echo [ERROR] 無法辨識檔案格式，僅支援 .xls / .txt（事故）或 .xlsx（舉發）
            pause
            exit /b 1
        )

        echo.
        if "%IMPORT_FLAG%"=="--crash" (
            echo [INFO] 偵測為事故資料，正在匯入: %filepath%
        ) else (
            echo [INFO] 偵測為舉發資料，正在匯入: %filepath%
        )

        cd /d "%BACKEND%"
        "%PYTHON%" scripts\import_data.py %IMPORT_FLAG% "%filepath%"
        echo.
        pause
    """).strip()

    import_path = os.path.join(DEPLOY_DIR, "匯入資料.bat")
    with open(import_path, 'w', encoding='utf-8') as f:
        f.write(import_bat)
    print(f"  建立: {import_path}")


def create_readme():
    """建立使用說明"""
    step("建立使用說明...")

    readme = textwrap.dedent("""
    # 精準執法儀表板系統 - 可攜式版本

    ## 使用方式

    1. 雙擊「啟動儀表板.bat」即可啟動系統
    2. 瀏覽器會自動開啟 http://localhost
    3. 關閉命令列視窗即可停止服務

    ## 匯入資料

    1. 雙擊「匯入資料.bat」
    2. 將 Excel 檔案拖曳到視窗中（或輸入檔案路徑）
    3. 支援格式：
       - 交通事故案件清冊 (.xls)
       - 舉發案件綜合查詢 (.xlsx)

    ## 注意事項

    - 本系統為可攜式版本，不需安裝任何軟體
    - 資料庫檔案位於 backend/data/ 目錄
    - 首次啟動會自動建立資料庫
    - 系統預設使用 Port 80，請確認無其他程式佔用
    """).strip()

    readme_path = os.path.join(DEPLOY_DIR, "使用說明.txt")
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme)
    print(f"  建立: {readme_path}")


def show_summary():
    """顯示打包結果"""
    # 計算資料夾大小
    total_size = 0
    for root, dirs, files in os.walk(DEPLOY_DIR):
        for f in files:
            total_size += os.path.getsize(os.path.join(root, f))

    size_mb = total_size / (1024 * 1024)

    step("打包完成!")
    print(f"""
  產出位置: {DEPLOY_DIR}
  總大小:   {size_mb:.0f} MB

  部署方式:
    1. 將「精準執法儀表板」資料夾複製到目標電腦
    2. 雙擊「啟動儀表板.bat」
    3. 完成！

  資料夾內容:
    精準執法儀表板/
      啟動儀表板.bat     <- 雙擊啟動
      匯入資料.bat       <- 匯入 Excel 資料
      使用說明.txt
      python/            <- 內嵌 Python (免安裝)
      backend/           <- 後端程式 + 前端打包檔
    """)


def main():
    print()
    print("=" * 60)
    print("  精準執法儀表板系統 - 可攜式版本打包工具")
    print("=" * 60)

    clean_deploy()
    download_python()
    install_pip()
    install_packages()
    copy_backend()
    copy_frontend_build()
    create_start_bat()
    create_readme()
    show_summary()


if __name__ == "__main__":
    main()
