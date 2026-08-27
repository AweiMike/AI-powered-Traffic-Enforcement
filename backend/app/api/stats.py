"""
統計分析 API
"""

import math
import statistics
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, extract
from typing import Optional, List
from datetime import datetime, timedelta

from app.database import get_db
from app.models.core import Ticket, Crash
from app.models.dimension import Population
from app.utils.epdo import epdo_sql_sum

router = APIRouter()


def _resolve_range(
    days: int,
    start_date: Optional[str],
    end_date: Optional[str],
    fallback_end=None,
):
    """
    統一處理 (days vs start_date/end_date) 兩種輸入方式。
    - 若 start_date + end_date 均提供 → 直接解析
    - 否則 → 用 days 從「資料最新日期」往回推（而非 datetime.now()，
      避免今天日期超出資料範圍時出現空結果）
    回傳 (start, end) 皆為 date 物件。
    """
    from datetime import datetime as _dt
    if start_date and end_date:
        try:
            sd = _dt.strptime(start_date, "%Y-%m-%d").date()
            ed = _dt.strptime(end_date, "%Y-%m-%d").date()
            return sd, ed
        except ValueError:
            pass  # 格式錯誤，退回 days 邏輯

    ed = fallback_end or _dt.now().date()
    sd = ed - timedelta(days=days)
    return sd, ed


def _data_end_date(db: Session):
    """取資料庫內最新的事故/違規日期；未有資料則返回今天"""
    max_crash = db.query(func.max(Crash.occurred_date)).scalar()
    max_ticket = db.query(func.max(Ticket.violation_date)).scalar()
    dates = [d for d in [max_crash, max_ticket] if d is not None]
    return max(dates) if dates else datetime.now().date()


def _median(values: list) -> Optional[float]:
    """中位數（Python 端計算，SQLite 無 percentile 函數）。空列回傳 None。"""
    if not values:
        return None
    return round(statistics.median(values), 1)


def _p90(values: list) -> Optional[float]:
    """P90 = sorted(values)[int(len*0.9)]，索引界內取（超界夾到最後一筆）。空列回傳 None。"""
    if not values:
        return None
    s = sorted(values)
    idx = min(int(len(s) * 0.9), len(s) - 1)
    return round(s[idx], 1)


@router.get("/overview")
async def get_overview(
    days: int = 30,
    start_date: Optional[str] = Query(default=None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    總覽統計（無個資，僅統計數據）

    參數：
    - days: 統計天數（當未指定 start_date/end_date 時使用）
    - start_date / end_date: 自訂日期區間（優先）

    返回：
    - 違規總數
    - 事故總數
    - 主題分布
    - 高齡者統計
    """
    start_date, end_date = _resolve_range(days, start_date, end_date, fallback_end=_data_end_date(db))

    # 去年同期（起迄各減一年，供 EPDO 去年同期比較用；C2）
    last_year_start = start_date.replace(year=start_date.year - 1)
    last_year_end = end_date.replace(year=end_date.year - 1)

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

    # EPDO 指標（台灣道安標準公式，人數口徑）：本期與去年同期的 EPDO 總和
    # 單案 EPDO = 30日死亡人數×9.5 + 調整受傷人數×3.5 + 1（見 app/utils/epdo.py）
    epdo = round(
        db.query(epdo_sql_sum())
        .filter(
            and_(Crash.occurred_date >= start_date, Crash.occurred_date <= end_date)
        )
        .scalar()
        or 0,
        1,
    )
    epdo_last_year = round(
        db.query(epdo_sql_sum())
        .filter(
            and_(Crash.occurred_date >= last_year_start, Crash.occurred_date <= last_year_end)
        )
        .scalar()
        or 0,
        1,
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
            "days": (end_date - start_date).days,
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
            "epdo": epdo,
            "epdo_last_year": epdo_last_year,
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

    def count_tickets_enforcement(s, e, subtype):
        return db.query(func.count(Ticket.id)).filter(
            and_(Ticket.violation_date >= s, Ticket.violation_date <= e, Ticket.enforcement_subtype == subtype)
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

    # 舉發子類型統計
    enforcement_subtypes = [
        "攔舉-一般", "攔舉-肇事", "攔舉-慢行攤",
        "逕舉_一般", "逕舉_民眾檢舉", "逕舉_標示單", "逕舉_拖吊", "逕舉_微電車",
    ]
    current_enforcement = {st: count_tickets_enforcement(sd, ed, st) for st in enforcement_subtypes}
    last_year_enforcement = {st: count_tickets_enforcement(prev_sd, prev_ed, st) for st in enforcement_subtypes}

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

    # 傷亡事故數（A1+A2，不含 A3 財損）：向後相容新增欄位，供趨勢圖對齊「傷亡」口徑用
    current_casualty_crashes = current_severity["a1"] + current_severity["a2"]
    last_year_casualty_crashes = last_year_severity["a1"] + last_year_severity["a2"]

    period_info = {"year": year, "month": month}
    if use_date_range:
        period_info = {"start_date": str(sd), "end_date": str(ed)}

    return {
        "period": period_info,
        "current": {
            "tickets": current_tickets,
            "crashes": current_crashes,
            "casualty_crashes": current_casualty_crashes,  # 傷亡事故數（A1+A2），新增欄位，不含 A3 財損
            "topics": current_topics,
            "severity": current_severity,
            "enforcement": current_enforcement,
        },
        "last_year": {
            "year": prev_sd.year,
            "tickets": last_year_tickets,
            "crashes": last_year_crashes,
            "casualty_crashes": last_year_casualty_crashes,  # 傷亡事故數（A1+A2）
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
async def get_elderly_stats(
    days: int = 30,
    start_date: Optional[str] = Query(default=None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    高齡者事故防治統計（無個資，僅統計）

    參數：
    - days: 統計天數（備援）
    - start_date / end_date: 自訂日期區間（優先）
    """
    start_date, end_date = _resolve_range(days, start_date, end_date, fallback_end=_data_end_date(db))

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
async def get_shift_analysis(
    days: int = 30,
    start_date: Optional[str] = Query(default=None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    班別分析（12班制）

    參數：
    - days: 統計天數（備援）
    - start_date / end_date: 自訂日期區間（優先）

    返回：
    - 各班別違規/事故統計
    - 各班別主題分布
    """
    start_date, end_date = _resolve_range(days, start_date, end_date, fallback_end=_data_end_date(db))

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
async def get_violation_stats(
    days: int = 30,
    start_date: Optional[str] = Query(default=None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    違規分析統計（無個資）

    參數：
    - days: 統計天數（備援）
    - start_date / end_date: 自訂日期區間（優先）
    """
    start_date, end_date = _resolve_range(days, start_date, end_date, fallback_end=_data_end_date(db))

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


@router.get("/clearance-efficiency")
async def get_clearance_efficiency(
    days: int = 90,
    start_date: Optional[str] = Query(default=None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    事故處理時效／道路恢復效率統計（Wave 30-1）。

    以「到場反應時間」（發生→到場，response_minutes）與「排除清空時長」
    （到場→排除，clearance_minutes，即道路恢復所需時間）衡量事故處理效率。
    兩者皆於匯入時依 EIS 到場/排除日期時間欄位計算並夾制界外離群值
    （見 app/api/imports.py extract_road_engineering_fields）。

    框架鐵則（用戶拍板）：道路恢復效率為主，不做各所反應時間排名——
    本端點刻意不提供任何 per-unit／per-所 反應時間拆分，避免跨單位比較
    （反應時間受案發地點、警力配置等因素影響，非單位績效指標）。

    median/p90 皆於 Python 端計算（SQLite 無 percentile 函數）；
    count<1 的分組（by_severity/by_shift 為固定 3/12 列全列）median/p90 回 None。

    參數：
    - days: 統計天數（備援，未提供 start_date/end_date 時使用）
    - start_date / end_date: 自訂日期區間（優先）
    """
    start_date, end_date = _resolve_range(days, start_date, end_date, fallback_end=_data_end_date(db))

    base_filter = and_(Crash.occurred_date >= start_date, Crash.occurred_date <= end_date)

    # --- 總覽：反應/排除中位數、排除 P90 ---
    response_vals = [
        v for (v,) in db.query(Crash.response_minutes)
        .filter(base_filter, Crash.response_minutes.isnot(None))
        .all()
    ]
    clearance_vals = [
        v for (v,) in db.query(Crash.clearance_minutes)
        .filter(base_filter, Crash.clearance_minutes.isnot(None))
        .all()
    ]

    summary = {
        "median_response_min": _median(response_vals),
        "median_clearance_min": _median(clearance_vals),
        "p90_clearance_min": _p90(clearance_vals),
        "sample_n": len(clearance_vals),
    }

    # --- by_severity：A1/A2/A3 固定三列全列 ---
    severity_rows = (
        db.query(Crash.severity, Crash.clearance_minutes)
        .filter(base_filter, Crash.clearance_minutes.isnot(None))
        .all()
    )
    severity_groups = {"A1": [], "A2": [], "A3": []}
    for sev, cm in severity_rows:
        if sev in severity_groups:
            severity_groups[sev].append(cm)
    by_severity = [
        {
            "severity": sev,
            "median_clearance": _median(vals),
            "p90": _p90(vals),
            "count": len(vals),
        }
        for sev, vals in severity_groups.items()
    ]

    # --- by_shift：12 班固定全列 ---
    shift_rows = (
        db.query(Crash.shift_id, Crash.clearance_minutes)
        .filter(base_filter, Crash.clearance_minutes.isnot(None))
        .all()
    )
    shift_groups = {f"{i:02d}": [] for i in range(1, 13)}
    for sid, cm in shift_rows:
        if sid in shift_groups:
            shift_groups[sid].append(cm)

    def _shift_label(shift_id: str) -> str:
        """班別代碼轉時段文字，如 "01" -> "00-02時"（(int-1)*2 起，2 小時一段）"""
        n = int(shift_id)
        start_hour = (n - 1) * 2
        return f"{start_hour:02d}-{start_hour + 2:02d}時"

    by_shift = [
        {
            "shift_id": sid,
            "label": _shift_label(sid),
            "median_clearance": _median(vals),
            "count": len(vals),
        }
        for sid, vals in shift_groups.items()
    ]

    # --- by_route：route_name 非空，top5 依 count ---
    route_rows = (
        db.query(Crash.route_name, Crash.clearance_minutes)
        .filter(
            base_filter,
            Crash.clearance_minutes.isnot(None),
            Crash.route_name.isnot(None),
        )
        .all()
    )
    route_groups = {}
    for route_name, cm in route_rows:
        route_groups.setdefault(route_name, []).append(cm)
    by_route = sorted(
        (
            {"route_name": rn, "median_clearance": _median(vals), "count": len(vals)}
            for rn, vals in route_groups.items()
        ),
        key=lambda x: x["count"],
        reverse=True,
    )[:5]

    # --- slow_cases：clearance 最久 top10 ---
    slow_crashes = (
        db.query(Crash)
        .filter(base_filter, Crash.clearance_minutes.isnot(None))
        .order_by(Crash.clearance_minutes.desc())
        .limit(10)
        .all()
    )
    slow_cases = [
        {
            "date": c.occurred_date.isoformat(),
            "time": c.occurred_time.strftime("%H:%M") if c.occurred_time else "",
            "location": c.location_desc,
            "severity": c.severity,
            "clearance_min": c.clearance_minutes,
            "latitude": c.latitude,
            "longitude": c.longitude,
        }
        for c in slow_crashes
    ]

    return {
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": (end_date - start_date).days,
        },
        "summary": summary,
        "by_severity": by_severity,
        "by_shift": by_shift,
        "by_route": by_route,
        "slow_cases": slow_cases,
        "note": "道路恢復效率統計（不提供各單位反應時間排名）",
    }


# ================================================================
# 訊號／雜訊判讀（三項監測指標）
# ================================================================
# 動機：系統原本只顯示「較去年 ±N%」，不說那是真變化還是隨機波動。
# 113 年高齡事故率 130.1 曾被寫成「四年最佳」並據以追問「當年做對什麼」，
# 事後查核為統計假象：降幅 p=0.136 不顯著、非高齡同步下降、減少量 86% 來自
# 兩個僅占 9.8% 量體的小區且隔年全數反彈。本組指標即為擋掉此類誤判而設。
#
# 判讀順序：
#   1 過度代表倍數  該族群是否被「單獨」惡化（免疫於全般事故量變動）
#   2 控制組差分比  變化可否歸因於針對性作為（2x2 卡方，不需人口分母）
#   3 月別管制界限  是否已達趨勢認定門檻（單月破界不算）
# 三者皆通過，才可對外宣稱防制成效。

def _chi2_yates(a: int, b: int, c: int, d: int):
    """2x2 卡方（Yates 連續性校正）→ (chi2, p)。任一邊際為 0 時回 (0.0, 1.0)"""
    n = a + b + c + d
    if min(a + b, c + d, a + c, b + d) == 0 or n == 0:
        return 0.0, 1.0
    num = max(abs(a * d - b * c) - n / 2, 0)
    chi = n * num ** 2 / ((a + b) * (c + d) * (a + c) * (b + d))
    return round(chi, 3), round(math.erfc(math.sqrt(chi / 2)), 4)


def _poisson_limits(center: float):
    """95% 卜瓦松管制界限（中心線 ±1.96√中心線）"""
    if center <= 0:
        return 0.0, 0.0
    half = 1.96 * math.sqrt(center)
    return round(max(0.0, center - half), 1), round(center + half, 1)


def _population_for(db, ym: str):
    """取某民國年月三區合計人口 → (總人口, 65歲以上)；查無回 (None, None)"""
    row = db.query(
        func.sum(Population.total_pop), func.sum(Population.elderly_pop)
    ).filter(Population.year_month == ym).one()
    return (row[0], row[1]) if row and row[0] else (None, None)


def _roc_ym(d) -> str:
    """西元日期 → 民國年月字串（115-06）"""
    return "%03d-%02d" % (d.year - 1911, d.month)


@router.get("/signal-check")
async def signal_check(
    topic: str = Query("elderly", description="主題：elderly/pedestrian/evehicle/dui/heavy"),
    start_date: str = Query(..., description="本期起 YYYY-MM-DD"),
    end_date: str = Query(..., description="本期迄 YYYY-MM-DD"),
    baseline_start: Optional[str] = Query(None, description="基準期起；預設去年同期"),
    baseline_end: Optional[str] = Query(None, description="基準期迄；預設去年同期"),
    casualty_only: bool = Query(True, description="僅計 A1+A2 傷亡事故（長官指示口徑）"),
    db: Session = Depends(get_db),
):
    """訊號／雜訊判讀：回答「這個增減是真的，還是隨機波動？」

    基準期預設為「去年同期」且事前固定。請勿於看過數據後才挑基準期——
    以序列極值當基準會系統性膨脹率比與顯著性（實測：以四年最低點為基準時
    某區率比 3.76、p=0.012「顯著」，改用首期或四期趨勢檢定後 p=0.851／0.371 全不顯著）。
    """
    from app.api.recommendations import crash_topic_filter

    try:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="日期格式錯誤，需 YYYY-MM-DD")

    if baseline_start and baseline_end:
        try:
            bs = datetime.strptime(baseline_start, "%Y-%m-%d").date()
            be = datetime.strptime(baseline_end, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="基準期日期格式錯誤")
        baseline_note = "使用者指定"
    else:
        bs, be = sd.replace(year=sd.year - 1), ed.replace(year=ed.year - 1)
        baseline_note = "去年同期（預設，事前固定）"

    cond = crash_topic_filter(topic)
    if cond is None:
        raise HTTPException(status_code=400, detail="未知主題：%s" % topic)

    def _count(s, e, topic_side: bool):
        q = db.query(func.count(Crash.id)).filter(
            Crash.occurred_date >= s, Crash.occurred_date <= e
        )
        if casualty_only:
            q = q.filter(Crash.severity.in_(("A1", "A2")))
        return q.filter(cond if topic_side else ~cond).scalar() or 0

    t_now, t_base = _count(sd, ed, True), _count(bs, be, True)
    o_now, o_base = _count(sd, ed, False), _count(bs, be, False)

    # ---- 指標2：控制組差分比（2x2 卡方，不需人口分母）----
    chi2, p_share = _chi2_yates(t_base, o_base, t_now, o_now)
    share_base = t_base / (t_base + o_base) if (t_base + o_base) else 0
    share_now = t_now / (t_now + o_now) if (t_now + o_now) else 0
    t_ratio = (t_now / t_base) if t_base else None
    o_ratio = (o_now / o_base) if o_base else None
    diff_ratio = round(t_ratio / o_ratio, 3) if (t_ratio and o_ratio) else None
    if diff_ratio is None:
        verdict2 = "資料不足"
    elif diff_ratio <= 0.85:
        verdict2 = "該族群確有額外改善"
    elif diff_ratio >= 1.30:
        verdict2 = "該族群被單獨惡化，應立即檢討"
    else:
        verdict2 = "與全般同步，不可歸功於針對性作為"

    # ---- 指標1：過度代表倍數（需人口分母；目前僅高齡有分母）----
    pop_now = _population_for(db, _roc_ym(ed))
    pop_base = _population_for(db, _roc_ym(be))
    data_through = db.query(func.max(Population.year_month)).scalar()

    def _over_rep(cnt_topic, cnt_other, pop):
        total_pop, eld_pop = pop
        if topic != "elderly" or not total_pop or not eld_pop:
            return None
        cases = cnt_topic + cnt_other
        if not cases:
            return None
        return round((cnt_topic / cases) / (eld_pop / total_pop), 2)

    over_now = _over_rep(t_now, o_now, pop_now)
    over_base = _over_rep(t_base, o_base, pop_base)
    ind1 = {
        "supported": over_now is not None,
        "now": over_now,
        "baseline": over_base,
        "alert_threshold": 1.80,
        "normal_band": [1.50, 1.60],
        "status": (("alert" if over_now >= 1.80 else "normal") if over_now else None),
        "population_data_through": data_through,
        "note": (None if over_now is not None
                 else "僅 elderly 主題支援（公開人口資料僅有 65 歲以上單一級距）"),
    }

    # ---- 指標3：月別卜瓦松管制界限（前三年同月平均為中心線）----
    def _month_count(year: int, month: int) -> int:
        q = db.query(func.count(Crash.id)).filter(
            cond,
            extract("year", Crash.occurred_date) == year,
            extract("month", Crash.occurred_date) == month,
        )
        if casualty_only:
            q = q.filter(Crash.severity.in_(("A1", "A2")))
        return q.scalar() or 0

    def _has_coverage(year: int, month: int) -> bool:
        """該年月是否有任何事故資料（不分主題）。

        ⚠️ 必須排除無資料的年份：資料庫自 112 年起，若回推三年時把 111/110 年
        當成 0 件納入平均，中心線會被拉垮，導致實績全部假性「突破上界」——
        實測 113H1 曾算出管制帶 4.0–16.6 而六個月全部誤判為 ▲。
        """
        return (db.query(func.count(Crash.id)).filter(
            extract("year", Crash.occurred_date) == year,
            extract("month", Crash.occurred_date) == month,
        ).scalar() or 0) > 0

    months = []
    consec_below = 0
    max_consec_below = 0
    insufficient_baseline = False
    for m in range(sd.month, ed.month + 1):
        valid_years = [sd.year - b for b in (1, 2, 3) if _has_coverage(sd.year - b, m)]
        actual = _month_count(sd.year, m)
        if len(valid_years) < 2:
            # 基準年不足 2 年，管制界限無統計意義，誠實回 null 不硬算
            insufficient_baseline = True
            consec_below = 0
            months.append({"month": m, "center": None, "lcl": None, "ucl": None,
                           "actual": actual, "breach": None,
                           "baseline_years": len(valid_years)})
            continue
        hist = [_month_count(y, m) for y in valid_years]
        center = round(sum(hist) / len(hist), 1)
        lcl, ucl = _poisson_limits(center)
        breach = "below" if actual < lcl else ("above" if actual > ucl else None)
        if breach == "below":
            consec_below += 1
            max_consec_below = max(max_consec_below, consec_below)
        else:
            consec_below = 0
        months.append({
            "month": m, "center": center, "lcl": lcl, "ucl": ucl,
            "actual": actual, "breach": breach,
            "baseline_years": len(valid_years),
        })

    if insufficient_baseline and all(x["center"] is None for x in months):
        verdict3 = "基準年資料不足（需至少 2 個同月歷史年），無法建立管制界限"
    elif max_consec_below >= 3:
        verdict3 = "連續 3 個月低於下界，達趨勢認定門檻"
    elif any(x["breach"] == "above" for x in months):
        verdict3 = "有月份突破上界，需注意"
    elif max_consec_below > 0:
        verdict3 = "最多連續 %d 個月低於下界，未達門檻（需連 3 月）" % max_consec_below
    else:
        verdict3 = "全數位於管制帶內，尚無趨勢性變化"

    ind1_ok = (ind1["status"] != "alert") if ind1["supported"] else True
    ind2_ok = diff_ratio is not None and diff_ratio <= 0.85
    ind3_ok = (max_consec_below >= 3) and not insufficient_baseline
    can_claim = ind1_ok and ind2_ok and ind3_ok

    return {
        "topic": topic,
        "casualty_only": casualty_only,
        "period": {"start": start_date, "end": end_date},
        "baseline": {"start": bs.isoformat(), "end": be.isoformat(), "note": baseline_note},
        "counts": {
            "topic_now": t_now, "topic_baseline": t_base,
            "other_now": o_now, "other_baseline": o_base,
            "topic_share_now": round(share_now * 100, 1),
            "topic_share_baseline": round(share_base * 100, 1),
        },
        "indicator_1_over_representation": ind1,
        "indicator_2_control_diff": {
            "topic_ratio": round(t_ratio, 3) if t_ratio else None,
            "other_ratio": round(o_ratio, 3) if o_ratio else None,
            "diff_ratio": diff_ratio,
            "chi2": chi2,
            "p_value": p_share,
            "significant": p_share < 0.05,
            "verdict": verdict2,
        },
        "indicator_3_control_limits": {
            "months": months,
            "max_consecutive_below": max_consec_below,
            "insufficient_baseline": insufficient_baseline,
            "verdict": verdict3,
        },
        "can_claim_effectiveness": can_claim,
        "summary": ("三項指標皆通過，可對外宣稱防制成效" if can_claim
                    else "未達宣稱成效之門檻——變化尚無法與隨機波動區分"),
    }


@router.get("/enforcement-gap-ratio")
async def enforcement_gap_ratio(
    topic: str = Query("elderly", description="主題：elderly/youth/dui/evehicle"),
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    casualty_only: bool = Query(True, description="事故側僅計 A1+A2 傷亡事故"),
    db: Session = Depends(get_db),
):
    """執法落差倍數：該族群占事故的比重 ÷ 占舉發的比重。

    與 Wave 29 的「執法錯位引擎」互補——那個比的是**空間**（事故熱區 vs 取締熱區），
    這個比的是**對象**（誰在肇事 vs 誰在被取締）。

    實例：高齡者占 115H1 傷亡事故 36.7%，卻只占舉發 4.2%，落差 8.7 倍。
    ⚠️ 倍數高不等於「應該多開單」，有兩個獨立的理由：
    一、該族群可能多為**非肇責方**（高齡者 32.8% 為非主責，唯一死亡案即屬此類），
        此時防制對象應是其他用路人，不是他們自己。
    二、該族群的主要肇事行為可能**根本無從取締**。本轄高齡事故前兩大肇因
        「轉彎車不讓直行車」與「未保持安全距離」均屬主觀認定，現場無客觀事證；
        實測全庫這兩項分別有 72%（167/233）、71%（197/278）是**肇事後補單**，
        「安全距離」31 件中更有 30 件來自民眾檢舉。
        此時落差反映的是「不可取締」而非「執法不足」，
        對策應轉向工程改善與見警率，並改以可客觀舉發之替代項目
        （轉彎不打方向燈、闖紅燈類、跨越分向線）執行。
    """
    from app.api.recommendations import crash_topic_filter

    try:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="日期格式錯誤，需 YYYY-MM-DD")

    crash_cond = crash_topic_filter(topic)
    if crash_cond is None:
        raise HTTPException(status_code=400, detail="未知主題：%s" % topic)

    TICKET_COND = {
        "elderly": Ticket.is_elderly == True,
        "youth": Ticket.is_youth == True,
        "dui": Ticket.topic_dui == True,
        "evehicle": Ticket.evehicle_type.isnot(None),
    }
    ticket_cond = TICKET_COND.get(topic)
    if ticket_cond is None:
        return {
            "topic": topic,
            "supported": False,
            "note": "此主題無對應之舉發側欄位（如行人、大型車），無法計算對象落差",
        }

    cq = db.query(func.count(Crash.id)).filter(
        Crash.occurred_date >= sd, Crash.occurred_date <= ed
    )
    if casualty_only:
        cq = cq.filter(Crash.severity.in_(("A1", "A2")))
    crash_total = cq.scalar() or 0
    crash_topic = cq.filter(crash_cond).scalar() or 0

    tq = db.query(func.count(Ticket.id)).filter(
        Ticket.violation_date >= sd, Ticket.violation_date <= ed
    )
    ticket_total = tq.scalar() or 0
    ticket_topic = tq.filter(ticket_cond).scalar() or 0

    crash_share = (crash_topic / crash_total * 100) if crash_total else 0.0
    ticket_share = (ticket_topic / ticket_total * 100) if ticket_total else 0.0
    gap_ratio = round(crash_share / ticket_share, 1) if ticket_share else None

    if gap_ratio is None:
        verdict = "舉發側無該族群資料，無法判讀"
    elif gap_ratio >= 5:
        verdict = "執法對象與事故對象嚴重錯位，建議檢討專項"
    elif gap_ratio >= 2:
        verdict = "存在對象落差，值得檢視"
    elif gap_ratio >= 0.5:
        verdict = "事故與舉發之對象結構相當"
    else:
        verdict = "舉發相對集中於該族群，高於其事故占比"

    # 肇事後補單比例：舉發子類型含「肇事」者，反映是否為被動執法
    post_crash = None
    if ticket_topic:
        pc = db.query(func.count(Ticket.id)).filter(
            Ticket.violation_date >= sd, Ticket.violation_date <= ed,
            ticket_cond, Ticket.enforcement_subtype.like("%肇事%"),
        ).scalar() or 0
        post_crash = round(pc / ticket_topic * 100, 1)

    return {
        "topic": topic,
        "supported": True,
        "casualty_only": casualty_only,
        "period": {"start": start_date, "end": end_date},
        "crash": {"topic": crash_topic, "total": crash_total,
                  "share_pct": round(crash_share, 1)},
        "ticket": {"topic": ticket_topic, "total": ticket_total,
                   "share_pct": round(ticket_share, 1),
                   "post_crash_pct": post_crash},
        "gap_ratio": gap_ratio,
        "verdict": verdict,
        "caveat": ("倍數高不等於應多開單：須併看該族群是否多為非肇責方，"
                   "若是則防制對象應為其他用路人（可查 /recommendations/profile 之責任結構）"),
    }


@router.get("/special-causes")
async def special_causes(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    topic: Optional[str] = Query(None, description="可選：限定主題 elderly/pedestrian/…"),
    casualty_only: bool = Query(False, description="是否僅計 A1+A2"),
    db: Session = Depends(get_db),
):
    """特殊致因（文本挖掘）：結構化肇因欄看不到的事故成因。

    來源為現場處理摘要之規則式標籤——**資料庫只存標籤，不存原文**
    （摘要含車牌／姓名／地址，原文永遠留在原始 EIS 檔）。

    存在理由：「動物竄出」85 件中，結構化肇因欄僅 4 件（4.7%）正確歸類，
    45 件掛「恍神、緊張、心不在焉分心駕駛」——嚴重低登錄。此類特殊致因平時只能靠人工翻閱挖掘。
    """
    from app.models.core import CrashTextTag
    from app.api.recommendations import crash_topic_filter

    try:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="日期格式錯誤，需 YYYY-MM-DD")

    q = db.query(CrashTextTag.tag, func.count(func.distinct(CrashTextTag.case_id))).join(
        Crash, Crash.case_id == CrashTextTag.case_id
    ).filter(Crash.occurred_date >= sd, Crash.occurred_date <= ed)

    base = db.query(func.count(Crash.id)).filter(
        Crash.occurred_date >= sd, Crash.occurred_date <= ed
    )
    if casualty_only:
        q = q.filter(Crash.severity.in_(("A1", "A2")))
        base = base.filter(Crash.severity.in_(("A1", "A2")))
    if topic:
        cond = crash_topic_filter(topic)
        if cond is None:
            raise HTTPException(status_code=400, detail="未知主題：%s" % topic)
        q = q.filter(cond)
        base = base.filter(cond)

    rows = q.group_by(CrashTextTag.tag).all()
    total_cases = base.scalar() or 0
    # ⚠️ tagged 必須套用與 q 相同的 topic/severity 篩選，否則會回全期間所有標記案件，
    #    與各標籤加總對不起來（曾出現 tagged=114 但明細加總僅 23 的不一致）。
    tagged = q.with_entities(
        func.count(func.distinct(CrashTextTag.case_id))
    ).scalar() or 0

    items = [
        {"tag": t, "cases": c,
         "pct_of_total": round(c / total_cases * 100, 1) if total_cases else 0.0}
        for t, c in sorted(rows, key=lambda x: -x[1])
    ]
    return {
        "period": {"start": start_date, "end": end_date},
        "topic": topic,
        "casualty_only": casualty_only,
        "total_cases": total_cases,
        "tagged_cases": tagged,
        "coverage_pct": round(tagged / total_cases * 100, 1) if total_cases else 0.0,
        "items": items,
        "note": ("標籤取自現場處理摘要之規則式比對；資料庫僅存標籤與命中關鍵詞，"
                 "不存原文。需回查個案原文請至原始 EIS 檔以案件編號檢索。"),
    }
