"""
FastAPI 主應用程式
精準執法儀表板系統 - 個資保護版本
"""

import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from app.config import settings
from app.database import init_db
from app.api import topics, stats, recommendations, imports, admin, hotspots, report, evehicle, enforcement

# 前端靜態檔案目錄
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


# ============================================
# 生命週期管理
# ============================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式啟動/關閉事件"""
    # 啟動時
    print(f"\n[START] {settings.PROJECT_NAME} 啟動中...")
    print(f"  API 端點：http://localhost:8000{settings.API_V1_PREFIX}")
    print(f"  API 文件：http://localhost:8000/docs")
    print(f"  個資保護：已啟用（完全去識別化）")

    # 初始化資料庫
    try:
        init_db()
    except Exception as e:
        print(f"[WARN] 資料庫初始化警告：{e}")

    yield

    # 關閉時
    print(f"\n[STOP] {settings.PROJECT_NAME} 關閉中...")


# ============================================
# 創建 FastAPI 應用程式
# ============================================
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
    ## 🌿 精準執法儀表板系統 API

    **系統定位**：統計分析 + 精準執法建議工具

    ### 核心功能
    - 📊 統計分析（去年同期比較）
    - 🎯 精準執法建議（Top 5 推薦）
    - 📈 趨勢預測（違規態勢分析）
    - 👴 高齡者事故防治
    - 🍺 酒駕精準打擊

    ### 🔒 個資保護
    - ✅ 完全去識別化（無姓名、身分證、車號）
    - ✅ 地址去識別化（無門牌號）
    - ✅ 年齡分組（不儲存精確年齡）
    - ✅ 僅統計分析，無個案查詢

    ### 📝 與現有系統整合
    - 本系統：統計分析、執法建議
    - 現有系統：個案查詢、詳細資料
    """,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ============================================
# CORS 中間件
# ============================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# 路由註冊
# ============================================
app.include_router(
    topics.router, prefix=f"{settings.API_V1_PREFIX}/topics", tags=["主題管理"]
)

app.include_router(
    stats.router, prefix=f"{settings.API_V1_PREFIX}/stats", tags=["統計分析"]
)

app.include_router(
    recommendations.router,
    prefix=f"{settings.API_V1_PREFIX}/recommendations",
    tags=["推薦系統"],
)

app.include_router(
    imports.router,
    prefix=f"{settings.API_V1_PREFIX}/import",
    tags=["資料匯入"],
)

app.include_router(
    admin.router,
    prefix=f"{settings.API_V1_PREFIX}/admin",
    tags=["系統管理"],
)

app.include_router(
    hotspots.router,
    prefix=f"{settings.API_V1_PREFIX}/hotspots",
    tags=["熱點分析"],
)

app.include_router(
    report.router,
    prefix=f"{settings.API_V1_PREFIX}/report",
    tags=["AI 報告"],
)

app.include_router(
    evehicle.router,
    prefix=f"{settings.API_V1_PREFIX}/evehicle",
    tags=["慢車與微電車分析"],
)

app.include_router(
    enforcement.router,
    prefix=f"{settings.API_V1_PREFIX}/enforcement",
    tags=["執法績效統計"],
)


# ============================================
# 根路由
# ============================================
@app.get("/", tags=["系統"])
async def root():
    """系統資訊 / 前端入口"""
    # Production 模式：回傳前端頁面
    if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
        return FileResponse(str(STATIC_DIR / "index.html"))
    # Development 模式：回傳 API 資訊
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "running",
        "description": "統計分析 + 精準執法建議工具（無個資）",
        "docs": "/docs",
        "data_privacy": {
            "level": "高（完全去識別化）",
            "features": [
                "移除所有姓名、身分證、車號",
                "地址去識別化（無門牌號）",
                "年齡分組（不儲存精確年齡）",
                "僅統計分析，無個案查詢",
            ],
        },
    }


@app.get("/health", tags=["系統"])
async def health_check():
    """健康檢查"""
    db_type = "sqlite" if settings.DATABASE_URL.startswith("sqlite") else "postgresql"
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": db_type,
        "mode": "full",
    }


# ============================================
# 前端靜態檔案服務（Production 模式）
# ============================================
if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    # 掛載 assets 子目錄（JS/CSS/圖片等）
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="static-assets")

    # 所有非 API 路徑都回傳 index.html（支援前端 SPA 路由）
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(request: Request, full_path: str):
        # 如果檔案存在就直接回傳（favicon 等）
        file_path = STATIC_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        # 否則回傳 index.html（SPA fallback）
        return FileResponse(str(STATIC_DIR / "index.html"))

    print("[Production] 前端靜態檔案已掛載")
else:
    print("[Development] 前端請透過 Vite dev server 存取")


# ============================================
# 主程式入口（開發用）
# ============================================
if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("精準執法儀表板系統 - 開發伺服器")
    print("=" * 60)
    print(f"  API：http://localhost:8000{settings.API_V1_PREFIX}")
    print(f"  文件：http://localhost:8000/docs")
    print(f"  個資保護：已啟用")
    print("=" * 60 + "\n")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 開發模式自動重載
        log_level="info",
    )
