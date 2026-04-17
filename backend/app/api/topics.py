"""
主題管理 API
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional, List
from datetime import datetime, timedelta

from app.database import get_db
from app.models.core import Ticket, Crash

router = APIRouter()


# 主題定義
TOPICS = {
    "DUI": {
        "code": "DUI",
        "name": "酒駕精準打擊",
        "emoji": "🍺",
        "description": "酒後駕車及肇事防制",
        "color": "#E57373"
    },
    "RED_LIGHT": {
        "code": "RED_LIGHT",
        "name": "闖紅燈",
        "emoji": "🚦",
        "description": "號誌違規防制",
        "color": "#FFB74D"
    },
    "DANGEROUS_DRIVING": {
        "code": "DANGEROUS_DRIVING",
        "name": "危險駕駛",
        "emoji": "⚡",
        "description": "超速及危險駕駛防制",
        "color": "#64B5F6"
    }
}


@router.get("/")
async def get_topics():
    """
    取得所有主題列表

    返回：
    - 三大主題基本資訊（無個資）
    """
    return {
        "topics": list(TOPICS.values()),
        "total": len(TOPICS)
    }


@router.get("/{topic_code}")
async def get_topic_detail(topic_code: str):
    """
    取得特定主題詳細資訊

    參數：
    - topic_code: 主題代碼 (DUI/RED_LIGHT/DANGEROUS_DRIVING)
    """
    if topic_code not in TOPICS:
        raise HTTPException(status_code=404, detail="主題不存在")

    return TOPICS[topic_code]


@router.get("/{topic_code}/stats")
async def get_topic_stats(
    topic_code: str,
    shift_id: Optional[str] = None,
    days: int = 30,
    start_date: Optional[str] = Query(default=None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """
    取得主題統計資料（無個資，僅統計）

    參數：
    - topic_code: 主題代碼
    - shift_id: 班別 (01-12)，選填
    - days: 統計天數，預設30天

    返回：
    - 違規案件數
    - 事故案件數
    - 高齡者相關統計
    - 性別統計
    - 時段分布
    """
    if topic_code not in TOPICS:
        raise HTTPException(status_code=404, detail="主題不存在")

    # 計算日期範圍（優先 start_date/end_date，否則用 days 從資料最新日期往回推）
    if start_date and end_date:
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
    else:
        # 取資料最新日期作為基準，避免今天超出資料範圍時結果為空
        max_crash = db.query(func.max(Crash.occurred_date)).scalar()
        max_ticket = db.query(func.max(Ticket.violation_date)).scalar()
        dates = [d for d in [max_crash, max_ticket] if d is not None]
        end_date = max(dates) if dates else datetime.now().date()
        start_date = end_date - timedelta(days=days)

    # 基礎查詢條件
    base_conditions = [
        Ticket.violation_date >= start_date,
        Ticket.violation_date <= end_date
    ]

    # 根據主題添加條件
    if topic_code == "DUI":
        base_conditions.append(Ticket.topic_dui == True)
    elif topic_code == "RED_LIGHT":
        base_conditions.append(Ticket.topic_red_light == True)
    elif topic_code == "DANGEROUS_DRIVING":
        base_conditions.append(Ticket.topic_dangerous == True)

    # 班別過濾
    if shift_id:
        base_conditions.append(Ticket.shift_id == shift_id)

    # 查詢違規案件統計
    tickets_query = db.query(Ticket).filter(and_(*base_conditions))

    total_tickets = tickets_query.count()

    # 高齡者統計
    elderly_tickets = tickets_query.filter(Ticket.is_elderly == True).count()

    # 性別統計（無個資，僅統計）
    gender_stats = db.query(
        Ticket.driver_gender,
        func.count(Ticket.id).label('count')
    ).filter(and_(*base_conditions)).group_by(Ticket.driver_gender).all()

    # 年齡組統計
    age_group_stats = db.query(
        Ticket.driver_age_group,
        func.count(Ticket.id).label('count')
    ).filter(and_(*base_conditions)).group_by(Ticket.driver_age_group).all()

    # 班別分布
    shift_stats = db.query(
        Ticket.shift_id,
        func.count(Ticket.id).label('count')
    ).filter(and_(*base_conditions)).group_by(Ticket.shift_id).order_by(Ticket.shift_id).all()

    # 地區分布（無個資，僅統計）
    district_stats = db.query(
        Ticket.district,
        func.count(Ticket.id).label('count')
    ).filter(and_(*base_conditions)).group_by(Ticket.district).order_by(func.count(Ticket.id).desc()).limit(10).all()

    # 相關事故統計
    crash_conditions = [
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date
    ]

    if shift_id:
        crash_conditions.append(Crash.shift_id == shift_id)

    # 根據主題統計相關事故
    # 註：這裡簡化處理，實際可能需要更複雜的邏輯來判斷事故與主題的關聯
    total_crashes = db.query(Crash).filter(and_(*crash_conditions)).count()

    elderly_crashes = db.query(Crash).filter(
        and_(*crash_conditions),
        Crash.is_elderly == True
    ).count()

    return {
        "topic": TOPICS[topic_code],
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": days
        },
        "shift_id": shift_id,
        "tickets": {
            "total": total_tickets,
            "elderly": elderly_tickets,
            "elderly_percentage": round(elderly_tickets / total_tickets * 100, 1) if total_tickets > 0 else 0
        },
        "crashes": {
            "total": total_crashes,
            "elderly": elderly_crashes
        },
        "demographics": {
            "gender": [{"gender": g, "count": c} for g, c in gender_stats],
            "age_groups": [{"age_group": a, "count": c} for a, c in age_group_stats]
        },
        "distribution": {
            "shifts": [{"shift_id": s, "count": c} for s, c in shift_stats],
            "districts": [{"district": d, "count": c} for d, c in district_stats]
        },
        "note": "統計資料已完全去識別化，無任何個資"
    }


@router.get("/{topic_code}/trends")
async def get_topic_trends(
    topic_code: str,
    months: int = 12,
    db: Session = Depends(get_db)
):
    """
    取得主題趨勢分析（去年同期比較）

    參數：
    - topic_code: 主題代碼
    - months: 統計月數，預設12個月

    返回：
    - 每月統計數據
    - 同期比較
    - 趨勢方向
    """
    if topic_code not in TOPICS:
        raise HTTPException(status_code=404, detail="主題不存在")

    # 計算月份範圍
    current_date = datetime.now().date()
    current_year = current_date.year
    current_month = current_date.month

    # 主題條件
    if topic_code == "DUI":
        topic_condition = Ticket.topic_dui == True
    elif topic_code == "RED_LIGHT":
        topic_condition = Ticket.topic_red_light == True
    else:
        topic_condition = Ticket.topic_dangerous == True

    monthly_stats = []

    for i in range(months):
        # 計算目標月份
        target_month = current_month - i
        target_year = current_year

        if target_month <= 0:
            target_month += 12
            target_year -= 1

        # 當年數據
        current_count = db.query(func.count(Ticket.id)).filter(
            and_(
                topic_condition,
                Ticket.year == target_year,
                Ticket.month == target_month
            )
        ).scalar() or 0

        # 去年同期數據
        last_year_count = db.query(func.count(Ticket.id)).filter(
            and_(
                topic_condition,
                Ticket.year == target_year - 1,
                Ticket.month == target_month
            )
        ).scalar() or 0

        # 計算變化率
        change_rate = 0
        if last_year_count > 0:
            change_rate = round((current_count - last_year_count) / last_year_count * 100, 1)

        monthly_stats.append({
            "year": target_year,
            "month": target_month,
            "count": current_count,
            "last_year_count": last_year_count,
            "change_rate": change_rate,
            "trend": "上升" if change_rate > 0 else ("下降" if change_rate < 0 else "持平")
        })

    # 反轉列表，使其按時間順序排列
    monthly_stats.reverse()

    return {
        "topic": TOPICS[topic_code],
        "months": monthly_stats,
        "summary": {
            "total_months": len(monthly_stats),
            "average_count": round(sum(m["count"] for m in monthly_stats) / len(monthly_stats), 1) if monthly_stats else 0,
            "average_change_rate": round(sum(m["change_rate"] for m in monthly_stats) / len(monthly_stats), 1) if monthly_stats else 0
        },
        "note": "僅統計分析，無個資"
    }
