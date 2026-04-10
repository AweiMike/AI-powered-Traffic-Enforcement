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
    year: Optional[int] = Query(default=None, description="年份 (若指定 start_date/end_date 則忽略)"),
    month: Optional[int] = Query(default=None, ge=1, le=12, description="月份 (需配合 year)"),
    start_date: Optional[str] = Query(default=None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    月度/區間統計（含去年同期比較）

    支援兩種模式：
    1. year + month：傳統月度統計
    2. start_date + end_date：自訂日期區間統計（自動計算去年同期）
    """
    import calendar

    use_date_range = start_date and end_date

    if use_date_range:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d").date()
            ed = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式錯誤，請使用 YYYY-MM-DD")
        # 去年同期
        prev_sd = sd.replace(year=sd.year - 1)
        prev_ed = ed.replace(year=ed.year - 1)
    else:
        if not year or not month:
            raise HTTPException(status_code=400, detail="需提供 year+month 或 start_date+end_date")
        try:
            datetime(year, month, 1)
        except ValueError:
            raise HTTPException(status_code=400, detail="無效的年月")
        _, last_day = calendar.monthrange(year, month)
        sd = datetime(year, month, 1).date()
        ed = datetime(year, month, last_day).date()
        prev_sd = sd.replace(year=sd.year - 1)
        prev_ed = ed.replace(year=ed.year - 1)

    # --- 共用查詢函數 ---
    def count_tickets(s, e):
        return db.query(func.count(Ticket.id)).filter(
            and_(Ticket.violation_date >= s, Ticket.violation_date <= e)
        ).scalar() or 0

    def count_crashes(s, e):
        return db.query(func.count(Crash.id)).filter(
            and_(Crash.occurred_date >= s, Crash.occurred_date <= e)
        ).scalar() or 0

    def count_tickets_topic(s, e, col):
        return db.query(func.count(Ticket.id)).filter(
            and_(Ticket.violation_date >= s, Ticket.violation_date <= e, col == True)
        ).scalar() or 0

    def count_tickets_enforcement(s, e, etype):
        return db.query(func.count(Ticket.id)).filter(
            and_(Ticket.violation_date >= s, Ticket.violation_date <= e, Ticket.enforcement_type == etype)
        ).scalar() or 0

    def count_crashes_severity(s, e, sev):
        return db.query(func.count(Crash.id)).filter(
            and_(Crash.occurred_date >= s, Crash.occurred_date <= e, Crash.severity == sev)
        ).scalar() or 0

    # 當期統計
    current_tickets = count_tickets(sd, ed)
    current_crashes = count_crashes(sd, ed)

    # 去年同期統計
    last_year_tickets = count_tickets(prev_sd, prev_ed)
    last_year_crashes = count_crashes(prev_sd, prev_ed)

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
        "dui": count_tickets_topic(sd, ed, Ticket.topic_dui),
        "red_light": count_tickets_topic(sd, ed, Ticket.topic_red_light),
        "dangerous_driving": count_tickets_topic(sd, ed, Ticket.topic_dangerous),
    }
    last_year_topics = {
        "dui": count_tickets_topic(prev_sd, prev_ed, Ticket.topic_dui),
        "red_light": count_tickets_topic(prev_sd, prev_ed, Ticket.topic_red_light),
        "dangerous_driving": count_tickets_topic(prev_sd, prev_ed, Ticket.topic_dangerous),
    }

    # 舉發類型統計
    current_enforcement = {
        "stop": count_tickets_enforcement(sd, ed, "攔停舉發"),
        "auto": count_tickets_enforcement(sd, ed, "逕行舉發"),
    }
    last_year_enforcement = {
        "stop": count_tickets_enforcement(prev_sd, prev_ed, "攔停舉發"),
        "auto": count_tickets_enforcement(prev_sd, prev_ed, "逕行舉發"),
    }

    # 事故嚴重度統計
    current_severity = {
        "a1": count_crashes_severity(sd, ed, "A1"),
        "a2": count_crashes_severity(sd, ed, "A2"),
        "a3": count_crashes_severity(sd, ed, "A3"),
    }
    last_year_severity = {
        "a1": count_crashes_severity(prev_sd, prev_ed, "A1"),
        "a2": count_crashes_severity(prev_sd, prev_ed, "A2"),
        "a3": count_crashes_severity(prev_sd, prev_ed, "A3"),
    }

    period_info = {"year": year, "month": month}
    if use_date_range:
        period_info = {"start_date": str(sd), "end_date": str(ed)}

    return {
        "period": period_info,
        "current": {
            "tickets": current_tickets,
            "crashes": current_crashes,
            "topics": current_topics,
            "severity": current_severity,
            "enforcement": current_enforcement,
        },
        "last_year": {
            "year": prev_sd.year,
            "tickets": last_year_tickets,
            "crashes": last_year_crashes,
            "topics": last_year_topics,
            "severity": last_year_severity,
            "enforcement": last_year_enforcement,
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


@router.get("/data-info")
async def get_data_info(db: Session = Depends(get_db)):
    """
    取得資料庫中事故與違規的資料起訖日期及最後上傳時間
    """
    # 事故資料日期範圍
    crash_min = db.query(func.min(Crash.occurred_date)).scalar()
    crash_max = db.query(func.max(Crash.occurred_date)).scalar()
    crash_count = db.query(func.count(Crash.id)).scalar() or 0

    # 違規資料日期範圍
    ticket_min = db.query(func.min(Ticket.violation_date)).scalar()
    ticket_max = db.query(func.max(Ticket.violation_date)).scalar()
    ticket_count = db.query(func.count(Ticket.id)).scalar() or 0

    # 最後上傳時間（用 created_at 推斷）
    last_crash_upload = db.query(func.max(Crash.created_at)).scalar()
    last_ticket_upload = db.query(func.max(Ticket.created_at)).scalar()

    # 取最新的上傳時間
    upload_times = [t for t in [last_crash_upload, last_ticket_upload] if t]
    last_upload = max(upload_times) if upload_times else None

    return {
        "crash": {
            "earliest": str(crash_min) if crash_min else None,
            "latest": str(crash_max) if crash_max else None,
            "count": crash_count,
            "last_upload": last_crash_upload.isoformat() if last_crash_upload else None,
        },
        "ticket": {
            "earliest": str(ticket_min) if ticket_min else None,
            "latest": str(ticket_max) if ticket_max else None,
            "count": ticket_count,
            "last_upload": last_ticket_upload.isoformat() if last_ticket_upload else None,
        },
        "last_upload": last_upload.isoformat() if last_upload else None,
    }
