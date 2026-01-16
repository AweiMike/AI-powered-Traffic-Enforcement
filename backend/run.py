import os
import sys
import uvicorn

# 強制設定當前目錄為 backend
current_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_dir)

# 將 backend 目錄加入搜尋路徑
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

if __name__ == "__main__":
    print("🌿 正在啟動精準執法後端伺服器 (Port 8080)...")
    print(f"📍 工作目錄: {current_dir}")

    # 啟動 FastAPI，指定 Port 8080
    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=8080, reload=True, log_level="info"
    )
