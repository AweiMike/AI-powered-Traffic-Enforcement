"""
統計分析 API
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, extract
from typing import Optional, List
from datetime import datetime, timedelta

from app.database import get_db
from app.models.core import Ticket, Crash

router = APIRouter()


@router.get("/overview")
async def get_overview(days: int = 30, db: Session = Depends(get_db)):
    """
    總覽統計（無個資，僅統計數據）

    參數：
    - days: 統計天數，預設30天

    返回：
    - 違規總數
    - 事故總數
    - 主題分布
    - 高齡者統計
    """
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    # 違規統計
    total_tickets = (
        db.query(func.count(Ticket.id))
        .filter(
            and_(Ticket.violation_date >= start_date, Ticket.violation_date <= end_date)
        )
        .scalar()
        or 0
    )

    # 事故統計
    total_crashes = (
        db.query(func.count(Crash.id))
        .filter(
            and_(Crash.occurred_date >= start_date, Crash.occurred_date <= end_date)
        )
        .scalar()
        or 0
    )

    # 主題分布
    dui_count = (
        db.query(func.count(Ticket.id))
        .filter(
            and_(
                Ticket.violation_date >= start_date,
                Ticket.violation_date <= end_date,
                Ticket.topic_dui == True,
            )
        )
        .scalar()
        or 0
    )

    red_light_count = (
        db.query(func.count(Ticket.id))
        .filter(
            and_(
                Ticket.violation_date >= start_date,
                Ticket.violation_date <= end_date,
                Ticket.topic_red_light == True,
            )
        )
        .scalar()
        or 0
    )

    dangerous_count = (
        db.query(func.count(Ticket.id))
        .filter(
            and_(
                Ticket.violation_date >= start_date,
                Ticket.violation_date <= end_date,
                Ticket.topic_dangerous == True,
            )
        )
        .scalar()
        or 0
    )

    # 高齡者統計
    elderly_tickets = (
        db.query(func.count(Ticket.id))
        .filter(
            and_(
                Ticket.violation_date >= start_date,
                Ticket.violation_date <= end_date,
                Ticket.is_elderly == True,
            )
        )
        .scalar()
        or 0
    )

    elderly_crashes = (
        db.query(func.count(Crash.id))
        .filter(
            and_(
                Crash.occurred_date >= start_date,
                Crash.occurred_date <= end_date,
                Crash.is_elderly == True,
            )
        )
        .scalar()
        or 0
    )

    return {
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": days,
        },
        "tickets": {
            "total": total_tickets,
            "elderly": elderly_tickets,
            "elderly_percentage": round(elderly_tickets / total_tickets * 100, 1)
            if total_tickets > 0
            else 0,
        },
        "crashes": {
            "total": total_crashes,
            "elderly": elderly_crashes,
            "elderly_percentage": round(elderly_crashes / total_crashes * 100, 1)
            if total_crashes > 0
            else 0,
        },
        "topics": {
            "dui": dui_count,
            "red_light": red_light_count,
            "dangerous_driving": dangerous_count,
        },
        "note": "統計資料已完全去識別化",
    }


@router.get("/monthly")
async def get_monthly_stats(
    year: int = Query(..., description="年份"),
    month: int = Query(..., ge=1, le=12, description="月份 (1-12)"),
    db: Session = Depends(get_db),
):
    """
    月度統計（含去年同期比較）

    參數：
    - year: 統計年份
    - month: 統計月份 (1-12)

    返回：
    - 當月統計
    - 去年同期統計
    - 增減率
    """
    # 驗證日期
    try:
        datetime(year, month, 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="無效的年月")

    # 當年統計
    current_tickets = (
        db.query(func.count(Ticket.id))
        .filter(and_(Ticket.year == year, Ticket.month == month))
        .scalar()
        or 0
    )

    current_crashes = (
        db.query(func.count(Crash.id))
        .filter(and_(Crash.year == year, Crash.month == month))
        .scalar()
        or 0
    )

    # 去年同期統計
    last_year = year - 1
    last_year_tickets = (
        db.query(func.count(Ticket.id))
        .filter(and_(Ticket.year == last_year, Ticket.month == month))
        .scalar()
        or 0
    )

    last_year_crashes = (
        db.query(func.count(Crash.id))
        .filter(and_(Crash.year == last_year, Crash.month == month))
        .scalar()
        or 0
    )

    # 計算變化率
    tickets_change = 0
    if last_year_tickets > 0:
        tickets_change = round(
            (current_tickets - last_year_tickets) / last_year_tickets * 100, 1
        )

    crashes_change = 0
    if last_year_crashes > 0:
        crashes_change = round(
            (current_crashes - last_year_crashes) / last_year_crashes * 100, 1
        )

    # 主題統計
    current_topics = {
        "dui": db.query(func.count(Ticket.id))
        .filter(
            and_(Ticket.year == year, Ticket.month == month, Ticket.topic_dui == True)
        )
        .scalar()
        or 0,
        "red_light": db.query(func.count(Ticket.id))
        .filter(
            and_(
                Ticket.year == year,
                Ticket.month == month,
                Ticket.topic_red_light == True,
            )
        )
        .scalar()
        or 0,
        "dangerous_driving": db.query(func.count(Ticket.id))
        .filter(
            and_(
                Ticket.year == year,
                Ticket.month == month,
                Ticket.topic_dangerous == True,
            )
        )
        .scalar()
        or 0,
    }

    last_year_topics = {
        "dui": db.query(func.count(Ticket.id))
        .filter(
            and_(
                Ticket.year == last_year,
                Ticket.month == month,
                Ticket.topic_dui == True,
            )
        )
        .scalar()
        or 0,
        "red_light": db.query(func.count(Ticket.id))
        .filter(
            and_(
                Ticket.year == last_year,
                Ticket.month == month,
                Ticket.topic_red_light == True,
            )
        )
        .scalar()
        or 0,
        "dangerous_driving": db.query(func.count(Ticket.id))
        .filter(
            and_(
                Ticket.year == last_year,
                Ticket.month == month,
                Ticket.topic_dangerous == True,
            )
        )
        .scalar()
        or 0,
    }

    return {
        "period": {"year": year, "month": month},
        "current": {
            "tickets": current_tickets,
            "crashes": current_crashes,
            "topics": current_topics,
        },
        "last_year": {
            "year": last_year,
            "tickets": last_year_tickets,
            "crashes": last_year_crashes,
            "topics": last_year_topics,
        },
        "comparison": {
            "tickets_change": tickets_change,
            "crashes_change": crashes_change,
            "tickets_trend": "上升"
            if tickets_change > 0
            else ("下降" if tickets_change < 0 else "持平"),
            "crashes_trend": "上升"
            if crashes_change > 0
            else ("下降" if crashes_change < 0 else "持平"),
        },
        "note": "僅統計分析，無個資",
    }


@router.get("/elderly")
async def get_elderly_stats(days: int = 30, db: Session = Depends(get_db)):
    """
    高齡者事故防治統計（無個資，僅統計）

    參數：
    - days: 統計天數，預設30天

    返回：
    - 高齡者違規統計
    - 高齡者事故統計
    - 時段分布
    - 地區分布
    """
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    # 高齡者違規統計
    elderly_tickets = db.query(Ticket).filter(
        and_(
            Ticket.violation_date >= start_date,
            Ticket.violation_date <= end_date,
            Ticket.is_elderly == True,
        )
    )

    total_elderly_tickets = elderly_tickets.count()

    # 按年齡組統計
    age_group_stats = (
        db.query(Ticket.driver_age_group, func.count(Ticket.id).label("count"))
        .filter(
            and_(
                Ticket.violation_date >= start_date,
                Ticket.violation_date <= end_date,
                Ticket.is_elderly == True,
            )
        )
        .group_by(Ticket.driver_age_group)
        .all()
    )

    # 按性別統計
    gender_stats = (
        db.query(Ticket.driver_gender, func.count(Ticket.id).label("count"))
        .filter(
            and_(
                Ticket.violation_date >= start_date,
                Ticket.violation_date <= end_date,
                Ticket.is_elderly == True,
            )
        )
        .group_by(Ticket.driver_gender)
        .all()
    )

    # 班別分布
    shift_stats = (
        db.query(Ticket.shift_id, func.count(Ticket.id).label("count"))
        .filter(
            and_(
                Ticket.violation_date >= start_date,
                Ticket.violation_date <= end_date,
                Ticket.is_elderly == True,
            )
        )
        .group_by(Ticket.shift_id)
        .order_by(Ticket.shift_id)
        .all()
    )

    # 高齡者事故統計
    elderly_crashes = db.query(Crash).filter(
        and_(
            Crash.occurred_date >= start_date,
            Crash.occurred_date <= end_date,
            Crash.is_elderly == True,
        )
    )

    total_elderly_crashes = elderly_crashes.count()

    # 事故嚴重度統計
    severity_stats = (
        db.query(Crash.severity, func.count(Crash.id).label("count"))
        .filter(
            and_(
                Crash.occurred_date >= start_date,
                Crash.occurred_date <= end_date,
                Crash.is_elderly == True,
            )
        )
        .group_by(Crash.severity)
        .all()
    )

    # 地區分布（無個資）
    district_stats = (
        db.query(Crash.district, func.count(Crash.id).label("count"))
        .filter(
            and_(
                Crash.occurred_date >= start_date,
                Crash.occurred_date <= end_date,
                Crash.is_elderly == True,
            )
        )
        .group_by(Crash.district)
        .order_by(func.count(Crash.id).desc())
        .limit(10)
        .all()
    )

    # 主題分布
    topic_stats = {
        "dui": elderly_tickets.filter(Ticket.topic_dui == True).count(),
        "red_light": elderly_tickets.filter(Ticket.topic_red_light == True).count(),
        "dangerous_driving": elderly_tickets.filter(
            Ticket.topic_dangerous == True
        ).count(),
    }

    return {
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": days,
        },
        "tickets": {"total": total_elderly_tickets, "topics": topic_stats},
        "crashes": {
            "total": total_elderly_crashes,
            "severity": [{"severity": s, "count": c} for s, c in severity_stats],
        },
        "demographics": {
            "age_groups": [{"age_group": a, "count": c} for a, c in age_group_stats],
            "gender": [{"gender": g, "count": c} for g, c in gender_stats],
        },
        "distribution": {
            "shifts": [{"shift_id": s, "count": c} for s, c in shift_stats],
            "districts": [{"district": d, "count": c} for d, c in district_stats],
        },
        "note": "高齡者防治統計，已完全去識別化",
    }


@router.get("/shifts")
async def get_shift_analysis(days: int = 30, db: Session = Depends(get_db)):
    """
    班別分析（12班制）

    參數：
    - days: 統計天數，預設30天

    返回：
    - 各班別違規/事故統計
    - 各班別主題分布
    """
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    shift_analysis = []

    for shift_num in range(1, 13):
        shift_id = f"{shift_num:02d}"

        # 違規統計
        tickets_count = (
            db.query(func.count(Ticket.id))
            .filter(
                and_(
                    Ticket.violation_date >= start_date,
                    Ticket.violation_date <= end_date,
                    Ticket.shift_id == shift_id,
                )
            )
            .scalar()
            or 0
        )

        # 事故統計
        crashes_count = (
            db.query(func.count(Crash.id))
            .filter(
                and_(
                    Crash.occurred_date >= start_date,
                    Crash.occurred_date <= end_date,
                    Crash.shift_id == shift_id,
                )
            )
            .scalar()
            or 0
        )

        # 主題統計
        dui_count = (
            db.query(func.count(Ticket.id))
            .filter(
                and_(
                    Ticket.violation_date >= start_date,
                    Ticket.violation_date <= end_date,
                    Ticket.shift_id == shift_id,
                    Ticket.topic_dui == True,
                )
            )
            .scalar()
            or 0
        )

        red_light_count = (
            db.query(func.count(Ticket.id))
            .filter(
                and_(
                    Ticket.violation_date >= start_date,
                    Ticket.violation_date <= end_date,
                    Ticket.shift_id == shift_id,
                    Ticket.topic_red_light == True,
                )
            )
            .scalar()
            or 0
        )

        dangerous_count = (
            db.query(func.count(Ticket.id))
            .filter(
                and_(
                    Ticket.violation_date >= start_date,
                    Ticket.violation_date <= end_date,
                    Ticket.shift_id == shift_id,
                    Ticket.topic_dangerous == True,
                )
            )
            .scalar()
            or 0
        )

        # 高齡者統計
        elderly_count = (
            db.query(func.count(Ticket.id))
            .filter(
                and_(
                    Ticket.violation_date >= start_date,
                    Ticket.violation_date <= end_date,
                    Ticket.shift_id == shift_id,
                    Ticket.is_elderly == True,
                )
            )
            .scalar()
            or 0
        )

        # 計算時間範圍
        start_hour = (shift_num - 1) * 2
        end_hour = start_hour + 2
        time_range = f"{start_hour:02d}:00-{end_hour:02d}:00"

        shift_analysis.append(
            {
                "shift_id": shift_id,
                "shift_number": shift_num,
                "time_range": time_range,
                "tickets": tickets_count,
                "crashes": crashes_count,
                "topics": {
                    "dui": dui_count,
                    "red_light": red_light_count,
                    "dangerous_driving": dangerous_count,
                },
                "elderly": elderly_count,
            }
        )

    return {
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": days,
        },
        "shifts": shift_analysis,
        "note": "班別統計分析，無個資",
    }


@router.get("/violations")
async def get_violation_stats(days: int = 30, db: Session = Depends(get_db)):
    """
    違規分析統計（無個資）

    參數：
    - days: 統計天數，預設30天

    返回：
    - 各行政區違規統計
    - 前十大違規項目
    - 主題分佈
    """
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    # 1. 各行政區統計
    district_stats = (
        db.query(Ticket.district, func.count(Ticket.id).label("count"))
        .filter(
            and_(Ticket.violation_date >= start_date, Ticket.violation_date <= end_date)
        )
        .group_by(Ticket.district)
        .order_by(func.count(Ticket.id).desc())
        .all()
    )

    # 2. 前十大違規項目
    top_violations = (
        db.query(
            Ticket.violation_code,
            Ticket.violation_name,
            func.count(Ticket.id).label("count"),
        )
        .filter(
            and_(Ticket.violation_date >= start_date, Ticket.violation_date <= end_date)
        )
        .group_by(Ticket.violation_code, Ticket.violation_name)
        .order_by(func.count(Ticket.id).desc())
        .limit(10)
        .all()
    )

    # 3. 主題分佈
    dui_count = (
        db.query(func.count(Ticket.id))
        .filter(
            and_(
                Ticket.violation_date >= start_date,
                Ticket.violation_date <= end_date,
                Ticket.topic_dui == True,
            )
        )
        .scalar()
        or 0
    )

    red_light_count = (
        db.query(func.count(Ticket.id))
        .filter(
            and_(
                Ticket.violation_date >= start_date,
                Ticket.violation_date <= end_date,
                Ticket.topic_red_light == True,
            )
        )
        .scalar()
        or 0
    )

    dangerous_count = (
        db.query(func.count(Ticket.id))
        .filter(
            and_(
                Ticket.violation_date >= start_date,
                Ticket.violation_date <= end_date,
                Ticket.topic_dangerous == True,
            )
        )
        .scalar()
        or 0
    )

    total_tickets = (
        db.query(func.count(Ticket.id))
        .filter(
            and_(Ticket.violation_date >= start_date, Ticket.violation_date <= end_date)
        )
        .scalar()
        or 0
    )

    return {
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": days,
        },
        "total_tickets": total_tickets,
        "districts": [
            {
                "district": d,
                "count": c,
                "percentage": round(c / total_tickets * 100, 1)
                if total_tickets > 0
                else 0,
            }
            for d, c in district_stats
        ],
        "top_violations": [
            {"code": code, "name": name, "count": c} for code, name, c in top_violations
        ],
        "topics": {
            "dui": dui_count,
            "red_light": red_light_count,
            "dangerous_driving": dangerous_count,
            "others": total_tickets - (dui_count + red_light_count + dangerous_count),
        },
    }
