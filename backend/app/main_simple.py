"""
簡化版 FastAPI 後端 - 無需資料庫
使用模擬數據進行測試
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import random

app = FastAPI(
    title="精準執法儀表板系統（簡化版）",
    description="統計分析 + 精準執法建議工具（模擬數據）",
    version="1.0.0-simple",
)

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "name": "精準執法儀表板系統（簡化版）",
        "description": "統計分析 + 精準執法建議工具（模擬數據）",
        "version": "1.0.0-simple",
        "note": "此為簡化版，使用模擬數據。完整版需要 PostgreSQL。"
    }

@app.get("/health")
async def health_check():
    return {"status": "ok", "mode": "simple", "database": "mock"}

# ============================================
# 統計分析 API
# ============================================

@app.get("/api/v1/stats/overview")
async def get_overview(days: int = 30):
    """總覽統計（模擬數據）"""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    return {
        "tickets": {
            "total": 1638,
            "elderly": 156
        },
        "crashes": {
            "total": 89,
            "a1": 2,
            "a2": 34,
            "a3": 53
        },
        "topics": {
            "dui": 26,
            "red_light": 478,
            "dangerous_driving": 1134
        },
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": days
        },
        "note": "模擬數據，僅供測試"
    }

@app.get("/api/v1/stats/monthly")
async def get_monthly_stats(year: int, month: int):
    """月度統計（模擬數據）"""
    return {
        "period": {
            "year": year,
            "month": month
        },
        "current": {
            "tickets": 1638,
            "crashes": 89,
            "topics": {
                "dui": 26,
                "red_light": 478,
                "dangerous_driving": 1134
            }
        },
        "last_year": {
            "year": year - 1,
            "tickets": 1520,
            "crashes": 95
        },
        "comparison": {
            "tickets_change": 7.8,
            "crashes_change": -6.3,
            "tickets_trend": "up",
            "crashes_trend": "down"
        },
        "note": "模擬數據，僅供測試"
    }

# ============================================
# 推薦系統 API
# ============================================

def generate_mock_site(rank: int, topic_code: str):
    """生成模擬點位數據"""
    locations = [
        {"name": "中正路與中山路路口", "district": "新化區"},
        {"name": "中興路與民生路路口", "district": "新化區"},
        {"name": "信義街路段", "district": "新化區"},
        {"name": "和平路與自由路路口", "district": "新化區"},
        {"name": "復興路路段（近公園）", "district": "新化區"}
    ]

    loc = locations[rank - 1] if rank <= len(locations) else locations[0]

    # 根據主題調整分數
    score_multiplier = {
        "DUI": 1.0,
        "RED_LIGHT": 0.8,
        "DANGEROUS_DRIVING": 0.7
    }.get(topic_code, 1.0)

    base_score = (6 - rank) * 20 * score_multiplier

    return {
        "rank": rank,
        "site_id": 100 + rank,
        "site_name": loc["name"],
        "district": loc["district"],
        "location_desc": f"{loc['name']}附近",
        "coordinates": {
            "latitude": 23.0386 + (rank * 0.001),
            "longitude": 120.3109 + (rank * 0.001)
        },
        "metrics": {
            "vpi": round(base_score * 0.7, 2),
            "cri": round(base_score * 0.3, 2),
            "score": round(base_score, 2)
        },
        "statistics": {
            "tickets": 20 - (rank * 2),
            "crashes": 6 - rank,
            "violation_days": 10 - rank,
            "avg_tickets_per_day": round((20 - rank * 2) / 30, 2)
        }
    }

@app.get("/api/v1/recommendations/top5")
async def get_top5(topic_code: str, shift_id: str = None, days: int = 30):
    """Top 5 推薦（模擬數據）"""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    recommendations = [generate_mock_site(i, topic_code) for i in range(1, 6)]

    return {
        "topic_code": topic_code,
        "shift_id": shift_id,
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": days
        },
        "recommendations": recommendations,
        "total_sites_analyzed": 23,
        "methodology": {
            "vpi": "違規案件數 × 主題權重",
            "cri": "事故案件數 × 平均嚴重度權重",
            "score": "基於主題的加權綜合評分"
        },
        "note": "推薦點位基於模擬數據，僅供測試"
    }

@app.get("/api/v1/recommendations/briefing-card")
async def get_briefing_card(topic_code: str, shift_id: str, date: str = None):
    """班前勤務建議卡（模擬數據）"""
    target_date = datetime.now().date() if not date else datetime.fromisoformat(date).date()
    shift_num = int(shift_id)
    start_hour = (shift_num - 1) * 2
    end_hour = start_hour + 2

    topics = {
        "DUI": {"name": "酒駕精準打擊", "emoji": "🍺", "focus": "加強酒測攔檢"},
        "RED_LIGHT": {"name": "闖紅燈防制", "emoji": "🚦", "focus": "重點路口號誌執法"},
        "DANGEROUS_DRIVING": {"name": "危險駕駛防制", "emoji": "⚡", "focus": "測速及危險駕駛取締"}
    }

    topic_info = topics.get(topic_code, topics["DUI"])
    top5_sites = [generate_mock_site(i, topic_code) for i in range(1, 6)]

    return {
        "date": target_date.isoformat(),
        "shift": {
            "shift_id": shift_id,
            "shift_number": shift_num,
            "time_range": f"{start_hour:02d}:00-{end_hour:02d}:00"
        },
        "topic": {
            "code": topic_code,
            "name": topic_info["name"],
            "emoji": topic_info["emoji"],
            "focus": topic_info["focus"]
        },
        "top5_sites": top5_sites,
        "statistics": {
            "period_days": 30,
            "total_sites": 23
        },
        "notes": [
            "⚠️ 本建議基於模擬數據",
            "🎯 建議優先部署於 Top 3 點位",
            "👴 注意高齡駕駛人執法態度",
            "📊 執法後請回報實際成效"
        ],
        "generated_at": datetime.now().isoformat(),
        "privacy_note": "本建議卡為模擬數據，僅供測試"
    }

if __name__ == "__main__":
    import uvicorn
    print("[START] 精準執法儀表板系統（簡化版）啟動中...")
    print("  API 端點：http://localhost:8000/api/v1")
    print("  API 文件：http://localhost:8000/docs")
    print("[WARN] 注意：使用模擬數據，非真實資料")
    uvicorn.run(app, host="0.0.0.0", port=8000)
