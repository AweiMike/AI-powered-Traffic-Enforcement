"""
統計分析 API
"""

import statistics
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, extract
from typing import Optional, List
from datetime import datetime, timedelta

from app.database import get_db
from app.models.core import Ticket, Crash
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
