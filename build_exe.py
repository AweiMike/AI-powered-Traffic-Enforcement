"""
打包腳本 - 將啟動器打包成 exe
使用 PyInstaller
"""

import os
import subprocess
import sys

def build_exe():
    """打包成 exe"""

    print("=" * 60)
    print("🌿 精準執法儀表板系統 - 打包成 EXE")
    print("=" * 60)
    print()

    # 檢查 PyInstaller
    try:
        import PyInstaller
        print("✅ PyInstaller 已安裝")
    except ImportError:
        print("⚠️  PyInstaller 未安裝，正在安裝...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller 安裝完成")

    print()
    print("📦 開始打包...")
    print()

    # PyInstaller 命令
    cmd = [
        "pyinstaller",
        "--name=精準執法儀表板系統",
        "--onefile",
        "--windowed",
        "--icon=NONE",  # 可以添加自定義圖標
        "--add-data=backend;backend",
        "--add-data=animal-crossing-dashboard;animal-crossing-dashboard",
        "--hidden-import=tkinter",
        "--hidden-import=psutil",
        "launcher.py"
    ]

    try:
        subprocess.check_call(cmd)
        print()
        print("=" * 60)
        print("✅ 打包完成！")
        print("=" * 60)
        print()
        print("📁 執行檔位置：dist/精準執法儀表板系統.exe")
        print()
        print("使用方式：")
        print("  1. 將 exe 複製到專案根目錄")
        print("  2. 雙擊執行即可")
        print()
    except subprocess.CalledProcessError as e:
        print()
        print("❌ 打包失敗！")
        print(f"錯誤：{e}")
        return False

    return True

if __name__ == "__main__":
    build_exe()
