"""
執法績效統計 API
- 酒後駕車防制成效（各派出所取締件數 + 事故數 + 同期比較）
- 大型車事故防制成效（各派出所取締細項 + 事故數 + 同期比較）
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case
from typing import Optional
from datetime import datetime, date

from app.database import get_db
from app.models.core import Ticket, Crash

router = APIRouter()


def parse_date(s: Optional[str]) -> Optional[date]:
    """解析 YYYY-MM-DD 字串"""
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def shift_year(d: date, years: int) -> date:
    """將日期前/後推 N 年"""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        # 處理 2/29
        return d.replace(year=d.year + years, day=28)


# ============================================
# 大型車車種關鍵字（精確匹配，排除小客貨/小貨車/大型重機）
# ============================================
# 資料庫中實際大型車車種：
#   自用大貨車、營業大貨車、自用大客車、營業大客車
#   營業遊覽大客車、營業貨運曳引車、營業貨櫃曳引車
#   營業大貨曳引車、自用大貨曳引車、自用曳引車
#   營業半拖車、營業全拖車、自用全拖車
HEAVY_VEHICLE_KEYWORDS = [
    "大貨車", "大客車", "曳引車", "拖車", "遊覽",
]


def _get_unit_column():
    """取得派出所欄位 - Ticket 用 unit_code"""
    return Ticket.unit_code


def _build_unit_list(db: Session) -> list:
    """取得所有有資料的派出所列表"""
    units = db.query(Ticket.unit_code).filter(
        Ticket.unit_code.isnot(None),
        Ticket.unit_code != ""
    ).distinct().all()
    return sorted([u[0] for u in units if u[0]])


# ============================================
# 酒後駕車防制成效
# ============================================
@router.get("/dui")
async def get_dui_performance(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    酒後駕車防制成效統計
    回傳各派出所取締件數 + A1/A2 事故數，含去年同期比較
    """
    sd = parse_date(start_date)
    ed = parse_date(end_date)
    if not sd or not ed:
        return {"error": "日期格式錯誤"}

    # 去年同期
    cmp_sd = shift_year(sd, -1)
    cmp_ed = shift_year(ed, -1)

    # --- 取締件數（各派出所）---
    def query_dui_tickets(s, e):
        return db.query(
            Ticket.unit_code.label("unit"),
            func.count(Ticket.id).label("count"),
        ).filter(
            Ticket.violation_date >= s,
            Ticket.violation_date <= e,
            Ticket.topic_dui == True,
        ).group_by(Ticket.unit_code).all()

    curr_tickets = {r.unit or "未知": r.count for r in query_dui_tickets(sd, ed)}
    prev_tickets = {r.unit or "未知": r.count for r in query_dui_tickets(cmp_sd, cmp_ed)}

    # --- A1/A2 酒駕事故數（各派出所）---
    def query_dui_crashes(s, e):
        return db.query(
            Crash.sub_unit.label("unit"),
            Crash.severity,
            func.count(Crash.id).label("count"),
        ).filter(
            Crash.occurred_date >= s,
            Crash.occurred_date <= e,
            Crash.suspected_alcohol == True,
        ).group_by(Crash.sub_unit, Crash.severity).all()

    def aggregate_crashes(rows):
        result = {}
        for r in rows:
            unit = r.unit or "未知"
            if unit not in result:
                result[unit] = {"A1": 0, "A2": 0}
            if r.severity in ("A1", "A2"):
                result[unit][r.severity] += r.count
        return result

    curr_crashes = aggregate_crashes(query_dui_crashes(sd, ed))
    prev_crashes = aggregate_crashes(query_dui_crashes(cmp_sd, cmp_ed))

    # 彙整所有派出所
    all_units = sorted(set(
        list(curr_tickets.keys()) + list(prev_tickets.keys()) +
        list(curr_crashes.keys()) + list(prev_crashes.keys())
    ))

    rows = []
    for unit in all_units:
        if unit == "未知":
            continue
        ct = curr_tickets.get(unit, 0)
        pt = prev_tickets.get(unit, 0)
        cc = curr_crashes.get(unit, {"A1": 0, "A2": 0})
        pc = prev_crashes.get(unit, {"A1": 0, "A2": 0})
        rows.append({
            "unit": unit,
            "tickets": ct,
            "tickets_prev": pt,
            "tickets_diff": ct - pt,
            "a1_crashes": cc["A1"],
            "a1_crashes_prev": pc["A1"],
            "a2_crashes": cc["A2"],
            "a2_crashes_prev": pc["A2"],
        })

    # 合計
    total = {
        "tickets": sum(r["tickets"] for r in rows),
        "tickets_prev": sum(r["tickets_prev"] for r in rows),
        "a1_crashes": sum(r["a1_crashes"] for r in rows),
        "a1_crashes_prev": sum(r["a1_crashes_prev"] for r in rows),
        "a2_crashes": sum(r["a2_crashes"] for r in rows),
        "a2_crashes_prev": sum(r["a2_crashes_prev"] for r in rows),
    }
    total["tickets_diff"] = total["tickets"] - total["tickets_prev"]

    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "compare_period": {"start_date": cmp_sd.isoformat(), "end_date": cmp_ed.isoformat()},
        "rows": rows,
        "total": total,
    }


# ============================================
# 大型車事故防制成效
# ============================================
@router.get("/heavy-vehicle")
async def get_heavy_vehicle_performance(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    大型車事故防制成效統計
    回傳各派出所取締件數（依法條分類）+ A1/A2 事故數，含去年同期比較
    """
    sd = parse_date(start_date)
    ed = parse_date(end_date)
    if not sd or not ed:
        return {"error": "日期格式錯誤"}

    cmp_sd = shift_year(sd, -1)
    cmp_ed = shift_year(ed, -1)

    # 大型車違規篩選條件（僅依車種判斷）
    def heavy_ticket_filter():
        """大型車取締 = 車種含大型車關鍵字"""
        vehicle_conds = [Ticket.vehicle_type.ilike(f"%{kw}%") for kw in HEAVY_VEHICLE_KEYWORDS]
        return or_(*vehicle_conds)

    # --- 取締件數（各派出所 × 法條分類）---
    def query_heavy_tickets(s, e):
        return db.query(
            Ticket.unit_code.label("unit"),
            func.count(Ticket.id).label("count"),
        ).filter(
            Ticket.violation_date >= s,
            Ticket.violation_date <= e,
            heavy_ticket_filter(),
        ).group_by(Ticket.unit_code).all()

    curr_tickets = {r.unit or "未知": r.count for r in query_heavy_tickets(sd, ed)}
    prev_tickets = {r.unit or "未知": r.count for r in query_heavy_tickets(cmp_sd, cmp_ed)}

    # --- 大型車 A1/A2 事故（各派出所）---
    def query_heavy_crashes(s, e):
        return db.query(
            Crash.sub_unit.label("unit"),
            Crash.severity,
            func.count(Crash.id).label("count"),
        ).filter(
            Crash.occurred_date >= s,
            Crash.occurred_date <= e,
            or_(
                *[Crash.party_type.ilike(f"%{kw}%") for kw in HEAVY_VEHICLE_KEYWORDS]
            ),
        ).group_by(Crash.sub_unit, Crash.severity).all()

    def aggregate_crashes(rows):
        result = {}
        for r in rows:
            unit = r.unit or "未知"
            if unit not in result:
                result[unit] = {"A1": 0, "A2": 0}
            if r.severity in ("A1", "A2"):
                result[unit][r.severity] += r.count
        return result

    curr_crashes = aggregate_crashes(query_heavy_crashes(sd, ed))
    prev_crashes = aggregate_crashes(query_heavy_crashes(cmp_sd, cmp_ed))

    # 彙整
    all_units = sorted(set(
        list(curr_tickets.keys()) + list(prev_tickets.keys()) +
        list(curr_crashes.keys()) + list(prev_crashes.keys())
    ))

    rows = []
    for unit in all_units:
        if unit == "未知":
            continue
        ct = curr_tickets.get(unit, 0)
        pt = prev_tickets.get(unit, 0)
        cc = curr_crashes.get(unit, {"A1": 0, "A2": 0})
        pc = prev_crashes.get(unit, {"A1": 0, "A2": 0})
        rows.append({
            "unit": unit,
            "tickets": ct,
            "tickets_prev": pt,
            "tickets_diff": ct - pt,
            "a1_crashes": cc["A1"],
            "a1_crashes_prev": pc["A1"],
            "a2_crashes": cc["A2"],
            "a2_crashes_prev": pc["A2"],
        })

    total = {
        "tickets": sum(r["tickets"] for r in rows),
        "tickets_prev": sum(r["tickets_prev"] for r in rows),
        "a1_crashes": sum(r["a1_crashes"] for r in rows),
        "a1_crashes_prev": sum(r["a1_crashes_prev"] for r in rows),
        "a2_crashes": sum(r["a2_crashes"] for r in rows),
        "a2_crashes_prev": sum(r["a2_crashes_prev"] for r in rows),
    }
    total["tickets_diff"] = total["tickets"] - total["tickets_prev"]

    # 重點違規態樣說明表（參考用）
    code_labels = {
        "18-21": "行車紀錄器/視野輔助系統",
        "29-1-1": "貨物超長寬高",
        "29-1-2": "載運整體物品違規",
        "29-22": "超載",
        "30-1-1": "載運整體物品違規",
        "48": "轉彎未依規定",
        "53": "闖紅燈",
        "55,56": "違規停車",
        "60-2-2": "未申請路權行駛",
        "60-2-3": "不遵守禁制標誌",
    }

    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "compare_period": {"start_date": cmp_sd.isoformat(), "end_date": cmp_ed.isoformat()},
        "rows": rows,
        "total": total,
        "code_labels": code_labels,
    }
