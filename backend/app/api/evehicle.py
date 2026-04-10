"""
微型電動二輪車與電動輔助自行車分析 API
專注於青少年事故防制與精準執法
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case
from typing import Optional, List
from datetime import datetime, timedelta, date

from app.database import get_db
from app.models.core import Ticket, Crash

router = APIRouter()


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def _get_date_range(days: int, start_date: Optional[str], end_date: Optional[str]):
    """回傳 (sd, ed)，優先使用 start_date/end_date，否則用 days 計算"""
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)
    if sd and ed:
        return sd, ed
    ed = datetime.now().date()
    sd = ed - timedelta(days=days)
    return sd, ed


# ============================================
# 慢車/微電車類型定義
# ============================================
EVEHICLE_TYPES = [
    "微型電動二輪車",
    "電動輔助自行車",
    "一般自行車",
]

EVEHICLE_VIOLATIONS = [
    "未掛牌",
    "未戴安全帽",
    "雙載",
    "改裝",
    "無照駕駛",
    "未滿14歲騎乘",
]


@router.get("/overview")
async def get_evehicle_overview(
    days: int = Query(default=30, ge=1, le=365, description="統計天數"),
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    慢車/微電車事故與違規總覽
    """
    sd, ed = _get_date_range(days, start_date, end_date)

    # === 事故統計 ===
    crash_query = db.query(Crash).filter(Crash.occurred_date >= sd, Crash.occurred_date <= ed)
    
    # 慢車相關事故（使用 party_type 或 evehicle_type）
    evehicle_crash_query = crash_query.filter(
        or_(
            Crash.evehicle_type.isnot(None),
            Crash.party_type.ilike("%自行車%"),
            Crash.party_type.ilike("%電動%"),
            Crash.party_type.ilike("%腳踏車%"),
        )
    )
    
    total_evehicle_crashes = evehicle_crash_query.count()
    
    # 微電車事故
    micro_evehicle_crashes = crash_query.filter(
        or_(
            Crash.evehicle_type == "微型電動二輪車",
            Crash.party_type.ilike("%微型電動%"),
            Crash.party_type.ilike("%微電%"),
        )
    ).count()
    
    # 電輔車事故
    eassist_crashes = crash_query.filter(
        or_(
            Crash.evehicle_type == "電動輔助自行車",
            Crash.party_type.ilike("%電動輔助%"),
            Crash.party_type.ilike("%電輔%"),
        )
    ).count()
    
    # 青少年事故（driver_age_group = '<18' 或 is_youth）
    youth_crashes = evehicle_crash_query.filter(
        or_(
            Crash.is_youth == True,
            Crash.driver_age_group == "<18",
        )
    ).count()
    
    # 未滿14歲騎乘微電車
    underage_14_crashes = crash_query.filter(
        Crash.is_underage_14 == True
    ).count()
    
    # 事故嚴重度
    severity_stats = db.query(
        Crash.severity,
        func.count(Crash.id).label("count")
    ).filter(
        Crash.occurred_date >= sd,
        Crash.occurred_date <= ed,
        or_(
            Crash.evehicle_type.isnot(None),
            Crash.party_type.ilike("%自行車%"),
            Crash.party_type.ilike("%電動%"),
            Crash.party_type.ilike("%腳踏車%"),
        )
    ).group_by(Crash.severity).all()
    
    severity_dict = {s.severity: s.count for s in severity_stats}

    # === 違規統計 ===
    ticket_query = db.query(Ticket).filter(Ticket.violation_date >= sd, Ticket.violation_date <= ed)
    
    # 慢車相關違規（使用 vehicle_type 關鍵字匹配）
    evehicle_ticket_query = ticket_query.filter(
        or_(
            Ticket.evehicle_type.isnot(None),
            Ticket.vehicle_type.ilike("%自行車%"),
            Ticket.vehicle_type.ilike("%電動%"),
            Ticket.vehicle_type.ilike("%腳踏車%"),
            Ticket.vehicle_type.ilike("%電輔%"),
        )
    )
    
    total_evehicle_tickets = evehicle_ticket_query.count()
    
    # 青少年違規（driver_age_group = '<18' 或 is_youth）
    youth_tickets = evehicle_ticket_query.filter(
        or_(
            Ticket.is_youth == True,
            Ticket.driver_age_group == "<18",
        )
    ).count()
    
    # 違規態樣分布（使用 evehicle_violation 或從 violation_name 推斷）
    violation_type_stats = db.query(
        Ticket.evehicle_violation,
        func.count(Ticket.id).label("count")
    ).filter(
        Ticket.violation_date >= sd,
        Ticket.violation_date <= ed,
        Ticket.evehicle_violation.isnot(None),
    ).group_by(Ticket.evehicle_violation).all()
    
    violation_types = [
        {"type": v.evehicle_violation, "count": v.count}
        for v in violation_type_stats
    ]

    # 計算青少年佔比
    youth_crash_ratio = (youth_crashes / total_evehicle_crashes * 100) if total_evehicle_crashes > 0 else 0
    youth_ticket_ratio = (youth_tickets / total_evehicle_tickets * 100) if total_evehicle_tickets > 0 else 0

    return {
        "period_days": days,
        "crashes": {
            "total": total_evehicle_crashes,
            "micro_evehicle": micro_evehicle_crashes,
            "eassist_bike": eassist_crashes,
            "youth_count": youth_crashes,
            "youth_ratio": round(youth_crash_ratio, 1),
            "underage_14": underage_14_crashes,
            "severity": {
                "a1": severity_dict.get("A1", 0),
                "a2": severity_dict.get("A2", 0),
                "a3": severity_dict.get("A3", 0),
            }
        },
        "tickets": {
            "total": total_evehicle_tickets,
            "youth_count": youth_tickets,
            "youth_ratio": round(youth_ticket_ratio, 1),
            "violation_types": violation_types,
        },
        "highlight": {
            "youth_warning": youth_crash_ratio > 30,
            "underage_alert": underage_14_crashes > 0,
        }
    }


@router.get("/youth-hotspots")
async def get_youth_hotspots(
    days: int = Query(default=30, ge=1, le=365),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(default=10, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """青少年事故與違規熱點分析"""
    sd, ed = _get_date_range(days, start_date, end_date)

    # 慢車條件
    evehicle_filter_crash = or_(
        Crash.evehicle_type.isnot(None),
        Crash.party_type.ilike("%自行車%"),
        Crash.party_type.ilike("%電動%"),
        Crash.party_type.ilike("%腳踏車%"),
    )
    
    evehicle_filter_ticket = or_(
        Ticket.evehicle_type.isnot(None),
        Ticket.vehicle_type.ilike("%自行車%"),
        Ticket.vehicle_type.ilike("%電動%"),
        Ticket.vehicle_type.ilike("%腳踏車%"),
    )

    # 青少年事故熱點
    crash_hotspots = db.query(
        Crash.district,
        func.count(Crash.id).label("crash_count"),
        func.sum(case((Crash.severity == "A1", 1), else_=0)).label("a1_count"),
        func.sum(case((Crash.severity == "A2", 1), else_=0)).label("a2_count"),
        func.sum(case((Crash.severity == "A3", 1), else_=0)).label("a3_count"),
    ).filter(
        Crash.occurred_date >= sd,
        Crash.occurred_date <= ed,
        or_(Crash.is_youth == True, Crash.driver_age_group == "<18"),
        evehicle_filter_crash,
        Crash.district.isnot(None),
    ).group_by(Crash.district).all()

    # 青少年違規熱點
    ticket_hotspots = db.query(
        Ticket.district,
        func.count(Ticket.id).label("ticket_count"),
    ).filter(
        Ticket.violation_date >= sd,
        Ticket.violation_date <= ed,
        or_(Ticket.is_youth == True, Ticket.driver_age_group == "<18"),
        evehicle_filter_ticket,
        Ticket.district.isnot(None),
    ).group_by(Ticket.district).all()

    # 合併資料
    crash_dict = {h.district: {"crash_count": h.crash_count, "a1": h.a1_count or 0, "a2": h.a2_count or 0, "a3": h.a3_count or 0} for h in crash_hotspots}
    ticket_dict = {h.district: h.ticket_count for h in ticket_hotspots}
    
    all_districts = set(crash_dict.keys()) | set(ticket_dict.keys())
    
    result = []
    for district in all_districts:
        crash_info = crash_dict.get(district, {"crash_count": 0, "a1": 0, "a2": 0, "a3": 0})
        ticket_count = ticket_dict.get(district, 0)
        total = crash_info["crash_count"] + ticket_count
        weighted_score = crash_info["a1"] * 5 + crash_info["a2"] * 3 + crash_info["a3"] * 1 + ticket_count
        
        result.append({
            "district": district,
            "crash_count": crash_info["crash_count"],
            "ticket_count": ticket_count,
            "total": total,
            "a1_count": crash_info["a1"],
            "a2_count": crash_info["a2"],
            "a3_count": crash_info["a3"],
            "weighted_score": weighted_score,
        })
    
    # 按總數排序
    result.sort(key=lambda x: x["weighted_score"], reverse=True)
    result = result[:limit]

    return {
        "period_days": days,
        "hotspots": result,
        "total_districts": len(result),
    }


@router.get("/time-analysis")
async def get_time_analysis(
    days: int = Query(default=30, ge=1, le=365),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """通學時段分析"""
    sd, ed = _get_date_range(days, start_date, end_date)

    # 慢車條件
    evehicle_filter_ticket = or_(
        Ticket.evehicle_type.isnot(None),
        Ticket.vehicle_type.ilike("%自行車%"),
        Ticket.vehicle_type.ilike("%電動%"),
        Ticket.vehicle_type.ilike("%腳踏車%"),
    )

    # 青少年違規時段分析
    ticket_time_stats = db.query(
        Ticket.shift_id,
        func.count(Ticket.id).label("total"),
        func.sum(case((or_(Ticket.is_youth == True, Ticket.driver_age_group == "<18"), 1), else_=0)).label("youth_count"),
    ).filter(
        Ticket.violation_date >= sd,
        Ticket.violation_date <= ed,
        evehicle_filter_ticket,
    ).group_by(Ticket.shift_id).all()

    # 轉換班別為時段
    shift_mapping = {
        "01": "00-02", "02": "02-04", "03": "04-06", "04": "06-08",
        "05": "08-10", "06": "10-12", "07": "12-14", "08": "14-16",
        "09": "16-18", "10": "18-20", "11": "20-22", "12": "22-24",
    }

    time_distribution = []
    school_time_total = 0
    school_time_youth = 0
    total_all = 0
    total_youth = 0
    
    for t in ticket_time_stats:
        if not t.shift_id:
            continue
        time_range = shift_mapping.get(t.shift_id, t.shift_id)
        is_school_time = t.shift_id in ["04", "05", "09"]  # 06-10, 16-18
        
        total_all += t.total
        total_youth += t.youth_count or 0
        
        if is_school_time:
            school_time_total += t.total
            school_time_youth += t.youth_count or 0
        
        time_distribution.append({
            "shift_id": t.shift_id,
            "time_range": time_range,
            "total": t.total,
            "youth_count": t.youth_count or 0,
            "is_school_time": is_school_time,
        })

    # 排序
    time_distribution.sort(key=lambda x: x["shift_id"] or "99")

    return {
        "period_days": days,
        "time_distribution": time_distribution,
        "school_time_summary": {
            "total_violations": school_time_total,
            "youth_violations": school_time_youth,
            "peak_periods": ["06:00-10:00 (上學)", "16:00-18:00 (放學)"],
        },
        "summary": {
            "total": total_all,
            "youth_total": total_youth,
        },
        "recommendation": "建議在通學時段加強校園周邊巡邏" if school_time_youth > 0 else None,
    }


@router.get("/violation-types")
async def get_violation_types(
    days: int = Query(default=30, ge=1, le=365),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """違規態樣分布分析"""
    sd, ed = _get_date_range(days, start_date, end_date)

    # 違規態樣統計
    violation_stats = db.query(
        Ticket.evehicle_violation,
        func.count(Ticket.id).label("total"),
        func.sum(case((or_(Ticket.is_youth == True, Ticket.driver_age_group == "<18"), 1), else_=0)).label("youth_count"),
    ).filter(
        Ticket.violation_date >= sd,
        Ticket.violation_date <= ed,
        Ticket.evehicle_violation.isnot(None),
    ).group_by(Ticket.evehicle_violation).order_by(func.count(Ticket.id).desc()).all()

    violations = []
    total_youth = 0
    total_all = 0
    
    for v in violation_stats:
        total_all += v.total
        total_youth += v.youth_count or 0
        violations.append({
            "violation_type": v.evehicle_violation,
            "total": v.total,
            "youth_count": v.youth_count or 0,
            "youth_ratio": round((v.youth_count or 0) / v.total * 100, 1) if v.total > 0 else 0,
        })

    # 法規提醒
    legal_notes = {
        "未掛牌": "依道交條例第71-1條開罰，可沒入車輛",
        "未戴安全帽": "微電車強制規定，電輔車建議配戴",
        "未滿14歲騎乘": "依第72-2條處罰監護人",
        "雙載": "微電車與電輔車皆禁止載人",
    }

    return {
        "period_days": days,
        "violations": violations,
        "summary": {
            "total": total_all,
            "youth_total": total_youth,
            "youth_ratio": round(total_youth / total_all * 100, 1) if total_all > 0 else 0,
        },
        "legal_notes": legal_notes,
    }


@router.get("/age-distribution")
async def get_age_distribution(
    days: int = Query(default=30, ge=1, le=365),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """年齡分布分析"""
    sd, ed = _get_date_range(days, start_date, end_date)

    # 事故年齡分布
    crash_age_stats = db.query(
        Crash.driver_age_group,
        func.count(Crash.id).label("count"),
    ).filter(
        Crash.occurred_date >= sd,
        Crash.occurred_date <= ed,
        or_(
            Crash.evehicle_type.isnot(None),
            Crash.party_type.ilike("%自行車%"),
            Crash.party_type.ilike("%電動%"),
        ),
        Crash.driver_age_group.isnot(None),
    ).group_by(Crash.driver_age_group).all()

    # 違規年齡分布
    ticket_age_stats = db.query(
        Ticket.driver_age_group,
        func.count(Ticket.id).label("count"),
    ).filter(
        Ticket.violation_date >= sd,
        Ticket.violation_date <= ed,
        or_(
            Ticket.evehicle_type.isnot(None),
            Ticket.vehicle_type.ilike("%自行車%"),
            Ticket.vehicle_type.ilike("%電動%"),
        ),
        Ticket.driver_age_group.isnot(None),
    ).group_by(Ticket.driver_age_group).all()

    age_order = ["<18", "18-24", "25-44", "45-64", "65+", "未知"]
    
    crash_distribution = {a.driver_age_group: a.count for a in crash_age_stats}
    ticket_distribution = {a.driver_age_group: a.count for a in ticket_age_stats}

    distribution = []
    for age_group in age_order:
        distribution.append({
            "age_group": age_group,
            "crash_count": crash_distribution.get(age_group, 0),
            "ticket_count": ticket_distribution.get(age_group, 0),
            "is_youth": age_group == "<18",
        })

    return {
        "period_days": days,
        "distribution": distribution,
        "youth_highlight": {
            "crashes": crash_distribution.get("<18", 0),
            "tickets": ticket_distribution.get("<18", 0),
            "warning": "青少年（<18歲）事故佔比偏高" if crash_distribution.get("<18", 0) > 0 else None,
        },
    }


@router.get("/youth-age-breakdown")
async def get_youth_age_breakdown(
    days: int = Query(default=365, ge=1, le=730, description="統計天數"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """青少年個別年齡統計"""
    sd, ed = _get_date_range(days, start_date, end_date)

    # 慢車條件
    evehicle_filter = or_(
        Ticket.evehicle_type.isnot(None),
        Ticket.vehicle_type.ilike("%自行車%"),
        Ticket.vehicle_type.ilike("%電動%"),
        Ticket.vehicle_type.ilike("%電輔%"),
        Ticket.vehicle_type.ilike("%腳踏車%"),
    )

    # 查詢有 driver_age 的違規資料
    age_stats = db.query(
        Ticket.driver_age,
        func.count(Ticket.id).label("count")
    ).filter(
        Ticket.violation_date >= sd,
        Ticket.violation_date <= ed,
        Ticket.driver_age.isnot(None),
        Ticket.driver_age < 18,
        Ticket.driver_age >= 9,
        evehicle_filter,
    ).group_by(Ticket.driver_age).all()

    # 若沒有 driver_age 資料，從 driver_age_group 統計總數
    youth_total_from_group = db.query(func.count(Ticket.id)).filter(
        Ticket.violation_date >= sd,
        Ticket.violation_date <= ed,
        Ticket.driver_age_group == "<18",
        evehicle_filter,
    ).scalar() or 0

    # 建立完整的 9-17 歲分布
    age_distribution = {age: 0 for age in range(9, 18)}
    for stat in age_stats:
        if stat.driver_age in age_distribution:
            age_distribution[stat.driver_age] = stat.count

    # 分類
    under_14 = []
    over_14 = []
    
    for age in range(9, 14):
        under_14.append({
            "age": age,
            "count": age_distribution.get(age, 0),
            "label": f"{age}歲",
        })
    
    for age in range(14, 18):
        over_14.append({
            "age": age,
            "count": age_distribution.get(age, 0),
            "label": f"{age}歲",
        })

    under_14_total = sum(a["count"] for a in under_14)
    over_14_total = sum(a["count"] for a in over_14)
    
    # 如果有個別年齡資料就用個別統計，否則用 age_group 總計
    has_individual_data = len(age_stats) > 0
    final_youth_total = (under_14_total + over_14_total) if has_individual_data else youth_total_from_group

    return {
        "period_days": days,
        "under_14": {
            "ages": under_14,
            "total": under_14_total,
            "warning": "未滿14歲禁止騎乘微電車",
        },
        "age_14_to_17": {
            "ages": over_14,
            "total": over_14_total,
        },
        "youth_total": final_youth_total,
        "youth_total_from_group": youth_total_from_group,
        "data_available": has_individual_data,
    }


@router.get("/yearly-trend")
async def get_yearly_trend(
    years: int = Query(default=4, ge=2, le=5, description="比較年數"),
    db: Session = Depends(get_db),
):
    """
    年度同期月份趨勢比較

    返回：
    - 近 3-4 年各月份青少年慢車違規數量
    - 同期比較與趨勢分析
    """
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    # 慢車條件
    evehicle_filter = or_(
        Ticket.evehicle_type.isnot(None),
        Ticket.vehicle_type.ilike("%自行車%"),
        Ticket.vehicle_type.ilike("%電動%"),
        Ticket.vehicle_type.ilike("%腳踏車%"),
    )

    # 查詢近 N 年的月份統計
    yearly_stats = db.query(
        Ticket.year,
        Ticket.month,
        func.count(Ticket.id).label("total"),
        func.sum(case((or_(Ticket.is_youth == True, Ticket.driver_age_group == "<18"), 1), else_=0)).label("youth_count"),
    ).filter(
        Ticket.year >= current_year - years + 1,
        evehicle_filter,
    ).group_by(Ticket.year, Ticket.month).all()

    # 整理資料
    year_data = {}
    for year in range(current_year - years + 1, current_year + 1):
        year_data[year] = {m: {"total": 0, "youth": 0} for m in range(1, 13)}
    
    for stat in yearly_stats:
        if stat.year in year_data and stat.month in year_data[stat.year]:
            year_data[stat.year][stat.month] = {
                "total": stat.total,
                "youth": stat.youth_count or 0,
            }

    # 計算各年度總計
    yearly_totals = {}
    for year, months in year_data.items():
        yearly_totals[year] = {
            "total": sum(m["total"] for m in months.values()),
            "youth": sum(m["youth"] for m in months.values()),
        }

    # 月份趨勢（用於圖表）
    monthly_trend = []
    for month in range(1, 13):
        month_data = {
            "month": month,
            "month_name": f"{month}月",
        }
        for year in range(current_year - years + 1, current_year + 1):
            month_data[f"y{year}"] = year_data[year][month]["youth"]
            month_data[f"y{year}_total"] = year_data[year][month]["total"]
        monthly_trend.append(month_data)

    # 同期比較（當月與去年同月）
    if current_month in year_data.get(current_year, {}) and current_month in year_data.get(current_year - 1, {}):
        this_month_youth = year_data[current_year][current_month]["youth"]
        last_year_same_month_youth = year_data[current_year - 1][current_month]["youth"]
        yoy_change = this_month_youth - last_year_same_month_youth
        yoy_percent = round((yoy_change / last_year_same_month_youth * 100), 1) if last_year_same_month_youth > 0 else 0
    else:
        this_month_youth = 0
        last_year_same_month_youth = 0
        yoy_change = 0
        yoy_percent = 0

    return {
        "years_compared": years,
        "current_year": current_year,
        "current_month": current_month,
        "yearly_totals": yearly_totals,
        "monthly_trend": monthly_trend,
        "yoy_comparison": {
            "current_month": current_month,
            "this_year": this_month_youth,
            "last_year": last_year_same_month_youth,
            "change": yoy_change,
            "change_percent": yoy_percent,
            "trend": "增加" if yoy_change > 0 else "減少" if yoy_change < 0 else "持平",
        },
    }
