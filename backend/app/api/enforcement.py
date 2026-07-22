"""
執法績效統計 API
- 酒後駕車防制成效（各派出所取締件數 + 事故數 + 同期比較）
- 大型車事故防制成效（各派出所取締細項 + 事故數 + 同期比較）
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case
from typing import Optional
from datetime import datetime, date, timedelta

from app.database import get_db
from app.models.core import Ticket, Crash
from app.utils.dui_crash import dui_crash_filter, dui_refusal_filter, crash_dui_real_filter
from app.utils.drug_drive import drug_drive_filter, drug_crash_filter, not_drug_filter
from app.utils.trend_engine import compute_trend, weekly_trend

router = APIRouter()


# 4 管區分組規則（與 analytics_engine.STATION_GROUPS 對齊）
# 用 substring 比對 sub_unit / unit_code，吸收「新化分局」前綴與罕見字寫法（𦰡拔/那拔）
DUI_STATION_GROUPS = [
    {"display": "新化派出所（含那拔）", "members": ["新化派出所", "那拔派出所", "𦰡拔派出所"]},
    {"display": "唪口派出所（含知義）", "members": ["唪口派出所", "知義派出所"]},
    {"display": "山上分駐所", "members": ["山上分駐所"]},
    {"display": "左鎮分駐所", "members": ["左鎮分駐所", "岡林派出所"]},
]


def classify_to_group(unit: str) -> Optional[str]:
    """歸類到 4 管區之一；統籌單位（交通分隊等）回傳 None。"""
    if not unit:
        return None
    for g in DUI_STATION_GROUPS:
        for m in g["members"]:
            if m in unit:
                return g["display"]
    return None


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
# 酒駕週趨勢（移動平均 / 環比 / Z-score 異常偵測 + 專業判讀）
# ============================================
@router.get("/dui/trend")
async def get_dui_weekly_trend(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """酒駕週趨勢：將區間內酒駕取締依「週」彙總，拆主動 vs 肇事，
    並計算 4 週移動平均、環比 (MoM)、Z-score 異常偵測與專業判讀。

    - 肇事 (is_crash) 採 UNION 信號（subtype=攔舉-肇事 OR violation_name 關鍵字）
    - 排除毒駕（not_drug_filter），與 /dui 口徑一致
    - 補零連續週序，確保移動平均與異常基準完整
    """
    sd = parse_date(start_date)
    ed = parse_date(end_date)
    if not sd or not ed:
        return {"error": "日期格式錯誤"}

    # secondary = 肇事(UNION 信號)；primary(主動) = total - secondary
    is_crash_expr = case((dui_crash_filter(), 1), else_=0)

    def query_daily(s, e):
        rows = db.query(
            Ticket.violation_date.label("d"),
            is_crash_expr.label("is_crash"),
            func.count(Ticket.id).label("c"),
        ).filter(
            Ticket.violation_date >= s,
            Ticket.violation_date <= e,
            Ticket.topic_dui == True,
            not_drug_filter(),
        ).group_by(
            Ticket.violation_date, is_crash_expr,
        ).all()
        return [(r.d, r.c, r.c if r.is_crash else 0) for r in rows]

    daily = query_daily(sd, ed)
    daily_prev = query_daily(sd - timedelta(weeks=52), ed - timedelta(weeks=52))
    result = weekly_trend(daily, sd, ed, daily_prev=daily_prev, window=4, metric_name="件", higher_is_worse=False)
    return {"period": {"start_date": start_date, "end_date": end_date}, **result}


# ============================================
# 毒駕週趨勢
# ============================================
@router.get("/drug/trend")
async def get_drug_weekly_trend(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """毒駕週趨勢：取締(primary) vs 肇事(secondary)，移動平均/環比/異常偵測。"""
    sd = parse_date(start_date)
    ed = parse_date(end_date)
    if not sd or not ed:
        return {"error": "日期格式錯誤"}

    is_crash_expr = case((drug_crash_filter(), 1), else_=0)

    def query_daily(s, e):
        rows = db.query(
            Ticket.violation_date.label("d"),
            is_crash_expr.label("is_crash"),
            func.count(Ticket.id).label("c"),
        ).filter(
            Ticket.violation_date >= s,
            Ticket.violation_date <= e,
            drug_drive_filter(),
        ).group_by(
            Ticket.violation_date, is_crash_expr,
        ).all()
        return [(r.d, r.c, r.c if r.is_crash else 0) for r in rows]

    daily = query_daily(sd, ed)
    daily_prev = query_daily(sd - timedelta(weeks=52), ed - timedelta(weeks=52))
    result = weekly_trend(daily, sd, ed, daily_prev=daily_prev, window=4, metric_name="件", higher_is_worse=False)
    return {"period": {"start_date": start_date, "end_date": end_date}, **result}


# ============================================
# 大型車週趨勢
# ============================================
@router.get("/heavy-vehicle/trend")
async def get_heavy_vehicle_weekly_trend(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """大型車週趨勢：取締(primary) vs 肇事舉發(secondary=攔舉-肇事)。"""
    sd = parse_date(start_date)
    ed = parse_date(end_date)
    if not sd or not ed:
        return {"error": "日期格式錯誤"}

    vehicle_conds = [Ticket.vehicle_type.ilike(f"%{kw}%") for kw in HEAVY_VEHICLE_KEYWORDS]
    is_crash_expr = case((Ticket.enforcement_subtype == "攔舉-肇事", 1), else_=0)

    def query_daily(s, e):
        rows = db.query(
            Ticket.violation_date.label("d"),
            is_crash_expr.label("is_crash"),
            func.count(Ticket.id).label("c"),
        ).filter(
            Ticket.violation_date >= s,
            Ticket.violation_date <= e,
            or_(*vehicle_conds),
        ).group_by(
            Ticket.violation_date, is_crash_expr,
        ).all()
        return [(r.d, r.c, r.c if r.is_crash else 0) for r in rows]

    daily = query_daily(sd, ed)
    daily_prev = query_daily(sd - timedelta(weeks=52), ed - timedelta(weeks=52))
    result = weekly_trend(daily, sd, ed, daily_prev=daily_prev, window=4, metric_name="件", higher_is_worse=False)
    return {"period": {"start_date": start_date, "end_date": end_date}, **result}


# ============================================
# 超速週趨勢（無乾淨肇事子集 → 單序列總量）
# ============================================
@router.get("/speed/trend")
async def get_speed_weekly_trend(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """超速週趨勢：總取締量(secondary=0)，移動平均/環比/異常偵測。"""
    sd = parse_date(start_date)
    ed = parse_date(end_date)
    if not sd or not ed:
        return {"error": "日期格式錯誤"}

    def query_daily(s, e):
        rows = db.query(
            Ticket.violation_date.label("d"),
            func.count(Ticket.id).label("c"),
        ).filter(
            Ticket.violation_date >= s,
            Ticket.violation_date <= e,
            Ticket.violation_name.like("%超速%"),
        ).group_by(
            Ticket.violation_date,
        ).all()
        return [(r.d, r.c, 0) for r in rows]

    daily = query_daily(sd, ed)
    daily_prev = query_daily(sd - timedelta(weeks=52), ed - timedelta(weeks=52))
    result = weekly_trend(daily, sd, ed, daily_prev=daily_prev, window=4, metric_name="件", higher_is_worse=False)
    return {"period": {"start_date": start_date, "end_date": end_date}, **result}


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

    # --- 取締件數（各派出所 × enforcement_subtype × 是否肇事 × 是否拒檢）---
    # is_crash 採 UNION 信號：subtype = 攔舉-肇事 OR violation_name 含肇事/致人/重傷 等關鍵字
    # is_refusal: violation_name 含「拒絕」或「不依指示停車接受稽查」(§35-IV 系列)
    def query_dui_tickets(s, e):
        is_crash_expr = case((dui_crash_filter(), 1), else_=0)
        is_refusal_expr = case((dui_refusal_filter(), 1), else_=0)
        return db.query(
            Ticket.unit_code.label("unit"),
            Ticket.enforcement_subtype.label("subtype"),
            is_crash_expr.label("is_crash"),
            is_refusal_expr.label("is_refusal"),
            func.count(Ticket.id).label("count"),
        ).filter(
            Ticket.violation_date >= s,
            Ticket.violation_date <= e,
            Ticket.topic_dui == True,
            not_drug_filter(),  # 排除毒駕（§35 I-2/IV），酒駕成效頁只算純酒精
        ).group_by(
            Ticket.unit_code, Ticket.enforcement_subtype,
            is_crash_expr, is_refusal_expr,
        ).all()

    def aggregate_tickets(rows):
        """5 桶分類：肇事 / 拒檢 / 主動 / 民檢 / 慢車

        優先序（高至低）：
        1. is_crash=1 → 肇事桶（最嚴重的後果）
        2. is_refusal=1 → 拒檢桶（規避酒測，§35-IV）
        3. subtype = '攔舉-一般' → 主動桶
        4. subtype = '逕舉_民眾檢舉' → 民檢桶
        5. else → 慢車桶（攔舉-慢行攤 + 其他逕舉子類）
        """
        result = {}
        for r in rows:
            unit = r.unit or "未知"
            if unit not in result:
                result[unit] = {
                    "total": 0, "proactive": 0, "crash_derived": 0,
                    "refusal": 0, "citizen": 0, "other": 0,
                }
            result[unit]["total"] += r.count
            if r.is_crash == 1:
                result[unit]["crash_derived"] += r.count
            elif r.is_refusal == 1:
                result[unit]["refusal"] += r.count
            else:
                st = r.subtype or ""
                if st == "攔舉-一般":
                    result[unit]["proactive"] += r.count
                elif st == "逕舉_民眾檢舉":
                    result[unit]["citizen"] += r.count
                else:
                    # 攔舉-慢行攤、其他逕舉子類等都歸「慢車」
                    result[unit]["other"] += r.count
        return result

    curr_tickets = aggregate_tickets(query_dui_tickets(sd, ed))
    prev_tickets = aggregate_tickets(query_dui_tickets(cmp_sd, cmp_ed))

    # --- A1/A2 酒駕事故數（各派出所）---
    def query_dui_crashes(s, e):
        return db.query(
            Crash.sub_unit.label("unit"),
            Crash.severity,
            func.count(Crash.id).label("count"),
        ).filter(
            Crash.occurred_date >= s,
            Crash.occurred_date <= e,
            crash_dui_real_filter(),  # 改用 ground truth (飲酒情形 4-8 排除行人)
        ).group_by(Crash.sub_unit, Crash.severity).all()

    def aggregate_crashes(rows):
        result = {}
        for r in rows:
            unit = r.unit or "未知"
            if unit not in result:
                result[unit] = {"A1": 0, "A2": 0, "A3": 0}
            if r.severity in ("A1", "A2", "A3"):
                result[unit][r.severity] += r.count
        return result

    curr_crashes = aggregate_crashes(query_dui_crashes(sd, ed))
    prev_crashes = aggregate_crashes(query_dui_crashes(cmp_sd, cmp_ed))

    # 彙整所有派出所
    all_units = sorted(set(
        list(curr_tickets.keys()) + list(prev_tickets.keys()) +
        list(curr_crashes.keys()) + list(prev_crashes.keys())
    ))

    EMPTY_BREAKDOWN = {"total": 0, "proactive": 0, "crash_derived": 0, "refusal": 0, "citizen": 0, "other": 0}

    rows = []
    for unit in all_units:
        if unit == "未知":
            continue
        ct = curr_tickets.get(unit, EMPTY_BREAKDOWN)
        pt = prev_tickets.get(unit, EMPTY_BREAKDOWN)
        cc = curr_crashes.get(unit, {"A1": 0, "A2": 0, "A3": 0})
        pc = prev_crashes.get(unit, {"A1": 0, "A2": 0, "A3": 0})
        rows.append({
            "unit": unit,
            "tickets": ct["total"],
            "tickets_prev": pt["total"],
            "tickets_diff": ct["total"] - pt["total"],
            "tickets_breakdown": {
                "proactive": ct["proactive"],
                "crash_derived": ct["crash_derived"],
                "refusal": ct["refusal"],
                "citizen": ct["citizen"],
                "other": ct["other"],
            },
            "tickets_prev_breakdown": {
                "proactive": pt["proactive"],
                "crash_derived": pt["crash_derived"],
                "refusal": pt["refusal"],
                "citizen": pt["citizen"],
                "other": pt["other"],
            },
            "a1_crashes": cc["A1"],
            "a1_crashes_prev": pc["A1"],
            "a2_crashes": cc["A2"],
            "a2_crashes_prev": pc["A2"],
            "a3_crashes": cc["A3"],
            "a3_crashes_prev": pc["A3"],
        })

    # 合計
    total = {
        "tickets": sum(r["tickets"] for r in rows),
        "tickets_prev": sum(r["tickets_prev"] for r in rows),
        "tickets_breakdown": {
            "proactive": sum(r["tickets_breakdown"]["proactive"] for r in rows),
            "crash_derived": sum(r["tickets_breakdown"]["crash_derived"] for r in rows),
            "refusal": sum(r["tickets_breakdown"]["refusal"] for r in rows),
            "citizen": sum(r["tickets_breakdown"]["citizen"] for r in rows),
            "other": sum(r["tickets_breakdown"]["other"] for r in rows),
        },
        "tickets_prev_breakdown": {
            "proactive": sum(r["tickets_prev_breakdown"]["proactive"] for r in rows),
            "crash_derived": sum(r["tickets_prev_breakdown"]["crash_derived"] for r in rows),
            "refusal": sum(r["tickets_prev_breakdown"]["refusal"] for r in rows),
            "citizen": sum(r["tickets_prev_breakdown"]["citizen"] for r in rows),
            "other": sum(r["tickets_prev_breakdown"]["other"] for r in rows),
        },
        "a1_crashes": sum(r["a1_crashes"] for r in rows),
        "a1_crashes_prev": sum(r["a1_crashes_prev"] for r in rows),
        "a2_crashes": sum(r["a2_crashes"] for r in rows),
        "a2_crashes_prev": sum(r["a2_crashes_prev"] for r in rows),
        "a3_crashes": sum(r["a3_crashes"] for r in rows),
        "a3_crashes_prev": sum(r["a3_crashes_prev"] for r in rows),
    }
    total["tickets_diff"] = total["tickets"] - total["tickets_prev"]

    # ----- 管區績效排名（扣除肇事舉發）-----
    # 將所有派出所歸類到 4 管區，計算「主動取締」= 總取締 − 肇事舉發
    # 排名依「主動取締」由高到低，反映派出所主動出擊（路檢）的績效
    group_agg: dict[str, dict] = {
        g["display"]: {
            "group": g["display"],
            "tickets_total": 0,
            "tickets_proactive": 0,
            "tickets_crash_derived": 0,
            "tickets_refusal": 0,
            "tickets_citizen": 0,
            "tickets_other": 0,
            "tickets_excl_crash": 0,  # 扣除肇事的取締（= 總 − 肇事）
            "a1_crashes": 0, "a2_crashes": 0, "a3_crashes": 0,
            "crashes_total": 0,
            "members": [],
        } for g in DUI_STATION_GROUPS
    }
    for r in rows:
        g = classify_to_group(r["unit"])
        if g is None:
            continue
        bucket = group_agg[g]
        bucket["members"].append(r["unit"])
        bd = r["tickets_breakdown"]
        bucket["tickets_total"] += r["tickets"]
        bucket["tickets_proactive"] += bd["proactive"]
        bucket["tickets_crash_derived"] += bd["crash_derived"]
        bucket["tickets_refusal"] += bd["refusal"]
        bucket["tickets_citizen"] += bd["citizen"]
        bucket["tickets_other"] += bd["other"]
        bucket["a1_crashes"] += r["a1_crashes"]
        bucket["a2_crashes"] += r["a2_crashes"]
        bucket["a3_crashes"] += r["a3_crashes"]

    for bucket in group_agg.values():
        # crashes_total = Crash 側 ground truth (is_dui_crash_party 加總，亦即 a1+a2+a3)
        bucket["crashes_total"] = bucket["a1_crashes"] + bucket["a2_crashes"] + bucket["a3_crashes"]
        # 肇事舉發 採 Crash 側為準（法律規定酒駕事故必開單，Ticket 應與 Crash 等量）
        bucket["tickets_excl_crash"] = bucket["tickets_total"] - bucket["crashes_total"]

        # 酒駕肇事率：以事故表 ground truth / 總取締
        group_total = bucket["tickets_total"]
        bucket["dui_crash_rate"] = (
            bucket["crashes_total"] / group_total if group_total > 0 else 0.0
        )
        bucket["proactive_rate"] = (
            bucket["tickets_proactive"] / group_total if group_total > 0 else 0.0
        )

        # 執法缺口判定：
        # - HIGH (有缺口):  肇事率 ≥ 30% 且 主動率 < 50% → 事先沒攔到、事故才補開
        # - LOW  (無缺口):  主動率 ≥ 70% 且 肇事率 < 15% → 路檢有效
        # - INSUFFICIENT_DATA: 總取締 < 5 件，量太少不判斷
        # - NEUTRAL: 其他狀況
        if group_total < 5:
            bucket["enforcement_gap"] = "INSUFFICIENT_DATA"
        elif bucket["dui_crash_rate"] >= 0.30 and bucket["proactive_rate"] < 0.50:
            bucket["enforcement_gap"] = "HIGH"
        elif bucket["proactive_rate"] >= 0.70 and bucket["dui_crash_rate"] < 0.15:
            bucket["enforcement_gap"] = "LOW"
        else:
            bucket["enforcement_gap"] = "NEUTRAL"

    unit_group_ranking = sorted(
        group_agg.values(),
        key=lambda b: (-b["tickets_excl_crash"], b["crashes_total"]),
    )
    for idx, b in enumerate(unit_group_ranking, start=1):
        b["rank"] = idx

    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "compare_period": {"start_date": cmp_sd.isoformat(), "end_date": cmp_ed.isoformat()},
        "rows": rows,
        "total": total,
        "unit_group_ranking": unit_group_ranking,
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

    # --- 取締件數（各派出所 × enforcement_subtype 子類細分）---
    def query_heavy_tickets(s, e):
        return db.query(
            Ticket.unit_code.label("unit"),
            Ticket.enforcement_subtype.label("subtype"),
            func.count(Ticket.id).label("count"),
        ).filter(
            Ticket.violation_date >= s,
            Ticket.violation_date <= e,
            heavy_ticket_filter(),
        ).group_by(Ticket.unit_code, Ticket.enforcement_subtype).all()

    def aggregate_tickets(rows):
        """依 enforcement_subtype 拆 主動/肇事/民檢/其他

        - 主動 = 攔舉-一般（警方主動攔停）
        - 肇事 = 攔舉-肇事（事故後舉發）
        - 民檢 = 逕舉_民眾檢舉
        - 其他 = 逕舉_一般/標示單/拖吊等
        """
        result = {}
        for r in rows:
            unit = r.unit or "未知"
            if unit not in result:
                result[unit] = {"total": 0, "proactive": 0, "crash_derived": 0, "citizen": 0, "other": 0}
            result[unit]["total"] += r.count
            st = r.subtype or ""
            if st == "攔舉-肇事":
                result[unit]["crash_derived"] += r.count
            elif st == "攔舉-一般":
                result[unit]["proactive"] += r.count
            elif st == "逕舉_民眾檢舉":
                result[unit]["citizen"] += r.count
            else:
                result[unit]["other"] += r.count
        return result

    curr_tickets = aggregate_tickets(query_heavy_tickets(sd, ed))
    prev_tickets = aggregate_tickets(query_heavy_tickets(cmp_sd, cmp_ed))

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
                result[unit] = {"A1": 0, "A2": 0, "A3": 0}
            if r.severity in ("A1", "A2", "A3"):
                result[unit][r.severity] += r.count
        return result

    curr_crashes = aggregate_crashes(query_heavy_crashes(sd, ed))
    prev_crashes = aggregate_crashes(query_heavy_crashes(cmp_sd, cmp_ed))

    # 彙整
    all_units = sorted(set(
        list(curr_tickets.keys()) + list(prev_tickets.keys()) +
        list(curr_crashes.keys()) + list(prev_crashes.keys())
    ))

    EMPTY_T = {"total": 0, "proactive": 0, "crash_derived": 0, "citizen": 0, "other": 0}

    rows = []
    for unit in all_units:
        if unit == "未知":
            continue
        ct = curr_tickets.get(unit, EMPTY_T)
        pt = prev_tickets.get(unit, EMPTY_T)
        cc = curr_crashes.get(unit, {"A1": 0, "A2": 0, "A3": 0})
        pc = prev_crashes.get(unit, {"A1": 0, "A2": 0, "A3": 0})
        rows.append({
            "unit": unit,
            "tickets": ct["total"],
            "tickets_prev": pt["total"],
            "tickets_diff": ct["total"] - pt["total"],
            "tickets_breakdown": {
                "proactive": ct["proactive"], "crash_derived": ct["crash_derived"],
                "citizen": ct["citizen"], "other": ct["other"],
            },
            "tickets_prev_breakdown": {
                "proactive": pt["proactive"], "crash_derived": pt["crash_derived"],
                "citizen": pt["citizen"], "other": pt["other"],
            },
            "a1_crashes": cc["A1"],
            "a1_crashes_prev": pc["A1"],
            "a2_crashes": cc["A2"],
            "a2_crashes_prev": pc["A2"],
            "a3_crashes": cc["A3"],
            "a3_crashes_prev": pc["A3"],
        })

    total = {
        "tickets": sum(r["tickets"] for r in rows),
        "tickets_prev": sum(r["tickets_prev"] for r in rows),
        "tickets_breakdown": {
            "proactive": sum(r["tickets_breakdown"]["proactive"] for r in rows),
            "crash_derived": sum(r["tickets_breakdown"]["crash_derived"] for r in rows),
            "citizen": sum(r["tickets_breakdown"]["citizen"] for r in rows),
            "other": sum(r["tickets_breakdown"]["other"] for r in rows),
        },
        "tickets_prev_breakdown": {
            "proactive": sum(r["tickets_prev_breakdown"]["proactive"] for r in rows),
            "crash_derived": sum(r["tickets_prev_breakdown"]["crash_derived"] for r in rows),
            "citizen": sum(r["tickets_prev_breakdown"]["citizen"] for r in rows),
            "other": sum(r["tickets_prev_breakdown"]["other"] for r in rows),
        },
        "a1_crashes": sum(r["a1_crashes"] for r in rows),
        "a1_crashes_prev": sum(r["a1_crashes_prev"] for r in rows),
        "a2_crashes": sum(r["a2_crashes"] for r in rows),
        "a2_crashes_prev": sum(r["a2_crashes_prev"] for r in rows),
        "a3_crashes": sum(r["a3_crashes"] for r in rows),
        "a3_crashes_prev": sum(r["a3_crashes_prev"] for r in rows),
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


# ============================================
# 速度管理（超速違規）專區
# ============================================
import re as _re

# 超速 violation_name 解析：提取「超速 X 公里」的 X
_SPEED_OVER_RE = _re.compile(r"超速\s*(\d+)\s*公里")
# 解析「限速 X 公里」
_SPEED_LIMIT_RE = _re.compile(r"限速\s*(\d+)\s*公里")


def _classify_speed_severity(violation_name: str) -> str:
    """從 violation_name 解析超速嚴重度：light/medium/heavy"""
    if not violation_name:
        return "unknown"
    m = _SPEED_OVER_RE.search(violation_name)
    if not m:
        # violation_name 含「超速」但沒具體公里數 → 歸為 unknown
        return "unknown"
    over = int(m.group(1))
    if over <= 20:
        return "light"      # 輕度：11-20 km/h
    if over <= 40:
        return "medium"     # 中度：21-40 km/h
    return "heavy"          # 重度：40+ km/h


def _extract_speed_limit(violation_name: str) -> int | None:
    """從 violation_name 解析速限"""
    if not violation_name:
        return None
    m = _SPEED_LIMIT_RE.search(violation_name)
    return int(m.group(1)) if m else None


@router.get("/speed")
async def get_speed_performance(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    速度管理（超速違規）專區統計
    - 總取締件數 + 去年同期比較
    - 嚴重度分級（輕/中/重）
    - 各派出所取締件數
    - 速限分布
    - 超速事故關聯（從 Crash.cause 撈「超速」相關）
    """
    sd = parse_date(start_date)
    ed = parse_date(end_date)
    if not sd or not ed:
        return {"error": "日期格式錯誤"}

    cmp_sd = shift_year(sd, -1)
    cmp_ed = shift_year(ed, -1)

    # --- 超速 Ticket（含 violation_name 以便解析嚴重度 & 速限）---
    def query_speed_tickets(s, e):
        return db.query(
            Ticket.id,
            Ticket.unit_code,
            Ticket.violation_name,
        ).filter(
            Ticket.violation_date >= s,
            Ticket.violation_date <= e,
            Ticket.violation_name.like('%超速%'),
        ).all()

    curr_rows = query_speed_tickets(sd, ed)
    prev_rows = query_speed_tickets(cmp_sd, cmp_ed)

    def tally(rows):
        """計算 unit 件數 + 嚴重度 + 速限分布"""
        unit_counts = {}
        severity_counts = {"light": 0, "medium": 0, "heavy": 0, "unknown": 0}
        limit_counts = {}
        for r in rows:
            unit = r.unit_code or "未知"
            unit_counts[unit] = unit_counts.get(unit, 0) + 1

            sev = _classify_speed_severity(r.violation_name)
            severity_counts[sev] += 1

            limit = _extract_speed_limit(r.violation_name)
            if limit is not None:
                limit_counts[limit] = limit_counts.get(limit, 0) + 1
        return {
            "total": len(rows),
            "unit_counts": unit_counts,
            "severity": severity_counts,
            "by_limit": limit_counts,
        }

    curr = tally(curr_rows)
    prev = tally(prev_rows)

    # --- 超速事故（Crash.cause LIKE '%超速%'）---
    def query_speed_crashes(s, e):
        return db.query(
            Crash.sub_unit,
            Crash.severity,
            Crash.death_count,
            Crash.injury_count,
        ).filter(
            Crash.occurred_date >= s,
            Crash.occurred_date <= e,
            Crash.cause.like('%超速%'),
        ).all()

    def tally_crashes(rows):
        total = len(rows)
        a1 = sum(1 for r in rows if r.severity == 'A1')
        a2 = sum(1 for r in rows if r.severity == 'A2')
        deaths = sum(r.death_count or 0 for r in rows)
        injuries = sum(r.injury_count or 0 for r in rows)
        unit_counts = {}
        for r in rows:
            u = r.sub_unit or "未知"
            unit_counts[u] = unit_counts.get(u, 0) + 1
        return {
            "total": total,
            "a1_crashes": a1,
            "a2_crashes": a2,
            "deaths": deaths,
            "injuries": injuries,
            "unit_counts": unit_counts,
        }

    curr_crashes = tally_crashes(query_speed_crashes(sd, ed))
    prev_crashes = tally_crashes(query_speed_crashes(cmp_sd, cmp_ed))

    # --- 派出所 Top 10 取締表 ---
    all_units = sorted(set(curr["unit_counts"].keys()) | set(prev["unit_counts"].keys()))
    unit_rows = []
    for u in all_units:
        if u == "未知":
            continue
        c = curr["unit_counts"].get(u, 0)
        p = prev["unit_counts"].get(u, 0)
        unit_rows.append({
            "unit": u,
            "tickets": c,
            "tickets_prev": p,
            "tickets_diff": c - p,
        })
    unit_rows.sort(key=lambda x: x["tickets"], reverse=True)

    # --- 熱點（本期超速取締 Top 5 路段）---
    hotspot_rows = db.query(
        Ticket.district,
        Ticket.location_desc,
        func.count(Ticket.id).label('count'),
    ).filter(
        Ticket.violation_date >= sd,
        Ticket.violation_date <= ed,
        Ticket.violation_name.like('%超速%'),
        Ticket.location_desc.isnot(None),
        Ticket.location_desc != "",
    ).group_by(Ticket.district, Ticket.location_desc).order_by(func.count(Ticket.id).desc()).limit(10).all()

    hotspots = []
    for row in hotspot_rows:
        if row.location_desc and "未知" not in row.location_desc and "不詳" not in row.location_desc:
            hotspots.append({
                "rank": len(hotspots) + 1,
                "district": row.district,
                "location": row.location_desc,
                "count": row.count,
            })
        if len(hotspots) >= 5:
            break

    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "compare_period": {"start_date": cmp_sd.isoformat(), "end_date": cmp_ed.isoformat()},
        "summary": {
            "current": curr,
            "previous": prev,
            "diff_pct": round((curr["total"] - prev["total"]) / prev["total"] * 100, 1) if prev["total"] > 0 else None,
        },
        "crashes": {
            "current": curr_crashes,
            "previous": prev_crashes,
        },
        "unit_rows": unit_rows,
        "hotspots": hotspots,
    }


# ============================================
# 行人事故專區
# ============================================
# 明確屬於「車輛對行人」的事故肇因關鍵字 — 行人為受害者
_CAUSE_DRIVER_FAULT = ["未禮讓", "車輛未依規定暫停讓", "未讓行人"]
# 行人自身違規的肇因關鍵字
_CAUSE_PEDESTRIAN_FAULT = ["穿越道路未注意", "未依標誌或標線穿越", "未依號誌或手勢指揮"]


@router.get("/pedestrian")
async def get_pedestrian_analysis(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    行人事故發生率專區統計
    - 行人事故件數 + 佔比（Wave 31-A：改用 involves_pedestrian 精確口徑，
      取代舊版 party_type in ["行人","人","其他人"] 判定）
    - 死傷人數＝行人本身傷亡（ped_death_count/ped_injury_count，Wave 31-A 與
      AI 報告 _sum_pedestrian_casualties 口徑一致；不含同案其他當事者傷亡）
    - 高齡行人占比
    - 肇因分類（駕駛違規 / 行人違規）
    - 熱點地點
    """
    sd = parse_date(start_date)
    ed = parse_date(end_date)
    if not sd or not ed:
        return {"error": "日期格式錯誤"}

    cmp_sd = shift_year(sd, -1)
    cmp_ed = shift_year(ed, -1)

    def query_crashes(s, e, pedestrian_only: bool):
        q = db.query(
            Crash.id,
            Crash.party_type,
            Crash.severity,
            Crash.is_elderly,
            Crash.cause,
            Crash.district,
            Crash.location_desc,
            Crash.death_count,
            Crash.injury_count,
            Crash.ped_death_count,
            Crash.ped_injury_count,
        ).filter(
            Crash.occurred_date >= s,
            Crash.occurred_date <= e,
        )
        if pedestrian_only:
            q = q.filter(Crash.involves_pedestrian == True)  # Wave 31-A：精確口徑
        return q.all()

    def classify_cause(cause: str | None) -> str:
        """分類肇因：driver_fault / pedestrian_fault / other"""
        if not cause:
            return "other"
        if any(kw in cause for kw in _CAUSE_DRIVER_FAULT):
            return "driver_fault"
        if any(kw in cause for kw in _CAUSE_PEDESTRIAN_FAULT):
            return "pedestrian_fault"
        return "other"

    def tally(rows):
        total = len(rows)
        a1 = sum(1 for r in rows if r.severity == 'A1')
        a2 = sum(1 for r in rows if r.severity == 'A2')
        a3 = sum(1 for r in rows if r.severity == 'A3')
        # Wave 31-A 指揮官裁決：死傷改計「行人本身」（ped_death/injury_count），
        # 與頁面口徑註記及 AI 報告 _sum_pedestrian_casualties 一致；
        # 案件總死傷（含駕駛）不再作為行人傷亡呈現
        deaths = sum(r.ped_death_count or 0 for r in rows)
        injuries = sum(r.ped_injury_count or 0 for r in rows)
        elderly = sum(1 for r in rows if r.is_elderly)

        fault_counts = {"driver_fault": 0, "pedestrian_fault": 0, "other": 0}
        for r in rows:
            fault_counts[classify_cause(r.cause)] += 1

        return {
            "total": total,
            "a1": a1,
            "a2": a2,
            "a3": a3,
            "deaths": deaths,
            "injuries": injuries,
            "elderly": elderly,
            "elderly_pct": round(elderly / total * 100, 1) if total > 0 else 0,
            "fault_breakdown": fault_counts,
        }

    curr_ped = query_crashes(sd, ed, pedestrian_only=True)
    prev_ped = query_crashes(cmp_sd, cmp_ed, pedestrian_only=True)

    curr_all_count = db.query(func.count(Crash.id)).filter(
        Crash.occurred_date >= sd,
        Crash.occurred_date <= ed,
    ).scalar() or 0
    prev_all_count = db.query(func.count(Crash.id)).filter(
        Crash.occurred_date >= cmp_sd,
        Crash.occurred_date <= cmp_ed,
    ).scalar() or 0

    curr_stats = tally(curr_ped)
    prev_stats = tally(prev_ped)

    # 佔比計算
    curr_stats["pct_of_all"] = round(curr_stats["total"] / curr_all_count * 100, 2) if curr_all_count > 0 else 0
    prev_stats["pct_of_all"] = round(prev_stats["total"] / prev_all_count * 100, 2) if prev_all_count > 0 else 0
    curr_stats["all_crashes"] = curr_all_count
    prev_stats["all_crashes"] = prev_all_count

    # 熱點地點（本期行人事故 Top 5）
    hotspots_raw = {}
    for r in curr_ped:
        if r.location_desc and "未知" not in (r.location_desc or "") and r.location_desc.strip():
            key = f"{r.district}|{r.location_desc}"
            if key not in hotspots_raw:
                hotspots_raw[key] = {
                    "district": r.district, "location": r.location_desc,
                    "count": 0, "elderly_count": 0, "deaths": 0, "injuries": 0,
                }
            hotspots_raw[key]["count"] += 1
            if r.is_elderly:
                hotspots_raw[key]["elderly_count"] += 1
            hotspots_raw[key]["deaths"] += r.death_count or 0
            hotspots_raw[key]["injuries"] += r.injury_count or 0

    hotspots = sorted(hotspots_raw.values(), key=lambda x: x["count"], reverse=True)[:5]
    for i, h in enumerate(hotspots, 1):
        h["rank"] = i

    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "compare_period": {"start_date": cmp_sd.isoformat(), "end_date": cmp_ed.isoformat()},
        "current": curr_stats,
        "previous": prev_stats,
        "hotspots": hotspots,
    }


# ============================================
# 毒品駕駛防制分析（取締側；事故側受限於 EIS 無毒品欄位）
# ============================================
# shift_id → (duty_order 派出所勤務班序, 時段標籤)
_DRUG_SHIFT_MAP = {
    "05": (1, "08-10"), "06": (2, "10-12"), "07": (3, "12-14"), "08": (4, "14-16"),
    "09": (5, "16-18"), "10": (6, "18-20"), "11": (7, "20-22"), "12": (8, "22-24"),
    "01": (9, "00-02"), "02": (10, "02-04"), "03": (11, "04-06"), "04": (12, "06-08"),
}


@router.get("/drug")
async def get_drug_performance(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """毒品駕駛防制分析（取締側）

    資料來源：Ticket 法條代碼 §35 I-2 吸食毒品 / §35 IV 毒品拒檢。
    ⚠️ 事故側受限：EIS 事故調查表無毒品專屬欄位，故本端點僅做取締分析。
    回傳：總取締/含肇事/去年同期 + 各派出所 + 4管區排名 + 區域分析 + 時段分析。
    """
    sd = parse_date(start_date)
    ed = parse_date(end_date)
    if not sd or not ed:
        return {"error": "日期格式錯誤"}

    cmp_sd = shift_year(sd, -1)
    cmp_ed = shift_year(ed, -1)

    def query_drug(s, e):
        """回傳 (unit, district, shift_id, is_crash, count) tuples"""
        is_crash_expr = case((drug_crash_filter(), 1), else_=0)
        return db.query(
            Ticket.unit_code.label("unit"),
            Ticket.district.label("district"),
            Ticket.shift_id.label("shift_id"),
            is_crash_expr.label("is_crash"),
            func.count(Ticket.id).label("count"),
        ).filter(
            Ticket.violation_date >= s,
            Ticket.violation_date <= e,
            drug_drive_filter(),
        ).group_by(
            Ticket.unit_code, Ticket.district, Ticket.shift_id, is_crash_expr,
        ).all()

    curr = query_drug(sd, ed)
    prev = query_drug(cmp_sd, cmp_ed)

    # --- 各派出所明細 ---
    def agg_by_unit(rows):
        d = {}
        for r in rows:
            unit = r.unit or "未知"
            if unit not in d:
                d[unit] = {"tickets": 0, "crash": 0}
            d[unit]["tickets"] += r.count
            if r.is_crash == 1:
                d[unit]["crash"] += r.count
        return d

    curr_unit = agg_by_unit(curr)
    prev_unit = agg_by_unit(prev)

    all_units = sorted(set(list(curr_unit.keys()) + list(prev_unit.keys())))
    rows_out = []
    for unit in all_units:
        if unit == "未知":
            continue
        c = curr_unit.get(unit, {"tickets": 0, "crash": 0})
        p = prev_unit.get(unit, {"tickets": 0, "crash": 0})
        rows_out.append({
            "unit": unit,
            "tickets": c["tickets"],
            "tickets_prev": p["tickets"],
            "tickets_diff": c["tickets"] - p["tickets"],
            "crash": c["crash"],
            "crash_prev": p["crash"],
        })

    total = {
        "tickets": sum(r["tickets"] for r in rows_out),
        "tickets_prev": sum(r["tickets_prev"] for r in rows_out),
        "crash": sum(r["crash"] for r in rows_out),
        "crash_prev": sum(r["crash_prev"] for r in rows_out),
    }
    total["tickets_diff"] = total["tickets"] - total["tickets_prev"]
    total["crash_diff"] = total["crash"] - total["crash_prev"]

    # --- 4 管區排名（依取締數）---
    group_agg = {g["display"]: {"group": g["display"], "tickets": 0, "crash": 0}
                 for g in DUI_STATION_GROUPS}
    for r in rows_out:
        g = classify_to_group(r["unit"])
        if g is None:
            continue
        group_agg[g]["tickets"] += r["tickets"]
        group_agg[g]["crash"] += r["crash"]
    unit_group_ranking = sorted(group_agg.values(), key=lambda b: -b["tickets"])
    for i, b in enumerate(unit_group_ranking, 1):
        b["rank"] = i

    # --- 區域分析（依行政區）---
    district_agg = {}
    for r in curr:
        dist = r.district or "未知"
        if dist not in district_agg:
            district_agg[dist] = {"district": dist, "tickets": 0, "crash": 0}
        district_agg[dist]["tickets"] += r.count
        if r.is_crash == 1:
            district_agg[dist]["crash"] += r.count
    by_district = sorted(
        [v for v in district_agg.values() if v["district"] != "未知"],
        key=lambda x: -x["tickets"],
    )

    # --- 時段分析（依 shift_id，附 duty_order）---
    shift_agg = {}
    for r in curr:
        sid = r.shift_id or "未知"
        if sid not in shift_agg:
            duty, label = _DRUG_SHIFT_MAP.get(sid, (99, sid))
            shift_agg[sid] = {"shift_id": sid, "duty_order": duty,
                              "time_range": label, "tickets": 0, "crash": 0}
        shift_agg[sid]["tickets"] += r.count
        if r.is_crash == 1:
            shift_agg[sid]["crash"] += r.count
    by_shift = sorted(
        [v for v in shift_agg.values() if v["shift_id"] != "未知"],
        key=lambda x: x["duty_order"],
    )

    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "compare_period": {"start_date": cmp_sd.isoformat(), "end_date": cmp_ed.isoformat()},
        "total": total,
        "rows": rows_out,
        "unit_group_ranking": unit_group_ranking,
        "by_district": by_district,
        "by_shift": by_shift,
        "note": "毒駕事故側資料受限於 EIS 無毒品專屬欄位，本分析僅涵蓋取締(舉發)資料",
    }
