"""
推薦系統 API - Top 5 精準執法建議
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, case, or_
from typing import Optional, List
from datetime import datetime, timedelta, date

from app.database import get_db
from app.models.core import Ticket, Crash
from app.models.dimension import Site
from app.utils.dui_crash import dui_crash_filter, crash_dui_real_filter
from app.utils.drug_drive import drug_drive_filter, drug_crash_filter, not_drug_filter
from app.utils.trend_engine import weekly_trend
from app.utils.epdo import crash_epdo, epdo_sum, epdo_sql_sum

router = APIRouter()


# ============================================
# 專區共通強化：主題篩選共用 helper（跨端點共用）
# ============================================

# 大型車關鍵字（與 enforcement.py 一致）
HEAVY_VEHICLE_KEYWORDS = ["大貨車", "大客車", "曳引車", "拖車", "遊覽"]


def crash_topic_filter(topic: str):
    """依主題代碼回傳對應的 Crash 篩選條件（SQLAlchemy 條件式）。

    支援的 topic：
    - elderly：高齡者事故
    - pedestrian：行人事故
    - evehicle：慢車（微電車等）事故
    - dui：酒駕肇事
    - heavy：大型車事故

    不認得的 topic 回傳 None，呼叫端應視為錯誤（回 400 或 {"error": ...}）。
    """
    if topic == "elderly":
        return Crash.is_elderly == True
    if topic == "pedestrian":
        return or_(Crash.party_type.like("%行人%"), Crash.party_type == "人")
    if topic == "evehicle":
        return Crash.evehicle_type.isnot(None)
    if topic == "dui":
        return Crash.is_dui_crash_party == True
    if topic == "heavy":
        return or_(*[Crash.party_type.like(f"%{kw}%") for kw in HEAVY_VEHICLE_KEYWORDS])
    return None


# ============================================
# 週事故趨勢（總覽用）：傷亡事故 A1+A2(total=primary 主訊號) + A1 死亡(secondary)，
# 另附 A3 財損事故第三參考序列（tertiary），higher_is_worse
# ============================================
@router.get("/accidents/trend")
async def get_accident_weekly_trend(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    topic: str = Query(None, description="主題篩選：elderly/pedestrian/evehicle/dui/heavy，未提供時行為與原本相同"),
    db: Session = Depends(get_db),
):
    """週事故趨勢：傷亡事故 A1+A2（total=primary 主訊號）+ A1 死亡（secondary），
    A3 財損事故僅作為第三參考序列（tertiary），不併入 total/primary 主訊號。

    口徑依道安檢討慣例與國際 KABCO（Injury vs PDO）：傷亡事故（A1+A2）才是
    執法與異常偵測應優先關注的重點；A3 純財損事故雖量體大，但風險意義較低，
    併入 primary 會稀釋傷亡訊號、降低異常偵測靈敏度，故只看不列重點。

    事故越多越糟（higher_is_worse=True → 判讀用「惡化/改善」、配色橙/紅）。
    共用 trend_engine.weekly_trend：移動平均 / 環比 / Z-score 異常偵測 + 專業判讀。
    ⚠️ 不修改 trend_engine.weekly_trend 本身（其他主題端點共用），僅在此端點
    餵入「傷亡口徑」的 daily/daily_prev，並於取得回傳結果後另外 merge A3 參考序列。

    topic 未提供時行為與原本完全相同（向後相容）；提供時本期與去年同期
    查詢皆加上 crash_topic_filter 條件，可用於各專區的週趨勢卡。
    """
    try:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return {"error": "日期格式錯誤"}

    topic_condition = None
    if topic is not None:
        topic_condition = crash_topic_filter(topic)
        if topic_condition is None:
            return {"error": "未知主題"}

    def query_daily_by_severity(s, e):
        """依日期 × severity 分組取件數（本期/去年同期共用），回傳 ORM row 清單。"""
        query = db.query(
            Crash.occurred_date.label("d"),
            Crash.severity.label("sev"),
            func.count(Crash.id).label("c"),
        ).filter(
            Crash.occurred_date >= s,
            Crash.occurred_date <= e,
        )
        if topic_condition is not None:
            query = query.filter(topic_condition)
        return query.group_by(Crash.occurred_date, Crash.severity).all()

    def to_injury_daily(rows):
        """把 (date, severity, count) 轉成傷亡口徑：(date, total=A1+A2 件數, secondary=A1 件數)。"""
        by_date: dict = {}
        for r in rows:
            b = by_date.setdefault(r.d, {"a1": 0, "a2": 0})
            if r.sev == "A1":
                b["a1"] += r.c
            elif r.sev == "A2":
                b["a2"] += r.c
        return [(d, b["a1"] + b["a2"], b["a1"]) for d, b in by_date.items()]

    def to_a3_by_week(rows):
        """把 (date, severity, count) 轉成 {週一日期: A3 件數}；週一規則與 trend_engine._week_start 一致。"""
        by_week: dict = {}
        for r in rows:
            if r.sev != "A3":
                continue
            ws = r.d - timedelta(days=r.d.weekday())
            by_week[ws] = by_week.get(ws, 0) + r.c
        return by_week

    rows_cur = query_daily_by_severity(sd, ed)
    rows_prev = query_daily_by_severity(sd - timedelta(weeks=52), ed - timedelta(weeks=52))

    daily = to_injury_daily(rows_cur)
    daily_prev = to_injury_daily(rows_prev)
    a3_by_week = to_a3_by_week(rows_cur)  # A3 參考線只看本期，不疊去年同期

    result = weekly_trend(daily, sd, ed, daily_prev=daily_prev, window=4, metric_name="件", higher_is_worse=True)

    # 加欄不破壞：weekly_trend 回傳後，依每週 week_start（週一）merge 進 A3 參考件數
    for w in result["weeks"]:
        ws = date.fromisoformat(w["week_start"])
        w["tertiary"] = a3_by_week.get(ws, 0)

    return {"period": {"start_date": start_date, "end_date": end_date}, **result}


# ============================================
# 道路照明故障事故清單（Phase 1 快贏：通報養工處修燈）
# ============================================
@router.get("/road-lighting-issues")
async def get_road_lighting_issues(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """「有照明未開啟或故障」的事故清冊 + 分區統計。

    資料源：EIS「5.道路照明設備」（全選條件匯出）。
    用途：一鍵產出含 GPS 的修燈通報清單給養工處，並附死傷佐證。
    夜間定義：18:00-05:59（shift 10-12、01-03），照明故障於此時段最具改善急迫性。
    """
    try:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return {"error": "日期格式錯誤"}

    NIGHT_SHIFTS = {"10", "11", "12", "01", "02", "03"}

    rows = db.query(Crash).filter(
        Crash.road_lighting == "有照明未開啟或故障",
        Crash.occurred_date >= sd,
        Crash.occurred_date <= ed,
    ).order_by(Crash.occurred_date.desc(), Crash.occurred_time.desc()).all()

    items = []
    night = 0
    deaths = 0
    injuries = 0
    by_district: dict = {}
    for c in rows:
        is_night = c.shift_id in NIGHT_SHIFTS
        if is_night:
            night += 1
        deaths += c.death_count or 0
        injuries += c.injury_count or 0
        d = c.district or "未知"
        by_district[d] = by_district.get(d, 0) + 1
        items.append({
            "date": c.occurred_date.isoformat(),
            "time": c.occurred_time.strftime("%H:%M") if c.occurred_time else "",
            "is_night": is_night,
            "district": d,
            "sub_unit": c.sub_unit,
            "location": c.location_desc,
            "route": (f"{c.route_name} {c.route_km}K" if c.route_name and c.route_km is not None
                      else (c.route_name or "")),
            "latitude": c.latitude,
            "longitude": c.longitude,
            "severity": c.severity,
            "deaths": c.death_count or 0,
            "injuries": c.injury_count or 0,
        })

    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "summary": {
            "total": len(items),
            "night": night,
            "night_pct": round(night * 100 / len(items), 1) if items else 0,
            "deaths": deaths,
            "injuries": injuries,
        },
        "by_district": sorted(
            [{"district": k, "count": v} for k, v in by_district.items()],
            key=lambda x: -x["count"],
        ),
        "items": items,
    }


def normalize_district(district: str) -> str:
    """標準化區域名稱，移除「市」前綴"""
    if district and district.startswith('市'):
        return district[1:]
    return district


def get_district_variants(district: str) -> list:
    """取得區域名稱的所有可能變體（用於查詢匹配）"""
    base = normalize_district(district)
    return [base, f"市{base}"]


def get_data_end_date(db: Session):
    """
    取得資料庫中最新的事故/違規日期作為查詢結束日期。
    這樣即使當前日期超過資料日期範圍，篩選仍能正確運作。
    """
    max_crash_date = db.query(func.max(Crash.occurred_date)).scalar()
    max_ticket_date = db.query(func.max(Ticket.violation_date)).scalar()
    
    today = datetime.now().date()
    dates = [d for d in [max_crash_date, max_ticket_date] if d is not None]
    
    if not dates:
        return today
    
    max_data_date = max(dates)
    return min(max_data_date, today)


def calculate_vpi(ticket_count: int, theme: str) -> float:
    """計算 VPI (Violation Pressure Index)"""
    weights = {
        "DUI": 10.0,
        "RED_LIGHT": 2.0,
        "DANGEROUS_DRIVING": 1.5
    }
    return ticket_count * weights.get(theme, 1.0)


def calculate_cri(crash_count: int, a1_count: int, a2_count: int) -> float:
    """計算 CRI (Crash Risk Index)"""
    return crash_count * 1.0 + a1_count * 5.0 + a2_count * 2.0


def calculate_score(vpi: float, cri: float, theme: str) -> float:
    """計算綜合推薦分數"""
    weights = {
        "DUI": (0.6, 0.4),
        "RED_LIGHT": (0.5, 0.5),
        "DANGEROUS_DRIVING": (0.4, 0.6)
    }
    alpha, beta = weights.get(theme, (0.5, 0.5))
    return alpha * vpi + beta * cri


# 台南各區中心座標
DISTRICT_COORDINATES = {
    "新化區": (23.0386, 120.3108),
    "山上區": (23.0975, 120.3547),
    "左鎮區": (23.0578, 120.4014),
    "玉井區": (23.1239, 120.4614),
    "楠西區": (23.1814, 120.4853),
    "南化區": (23.1417, 120.4731),
    "仁德區": (22.9722, 120.2331),
    "歸仁區": (22.9667, 120.2933),
    "關廟區": (22.9617, 120.3278),
    "龍崎區": (22.9622, 120.3847),
    "永康區": (23.0264, 120.2567),
    "東區": (22.9833, 120.2167),
    "南區": (22.9500, 120.1833),
    "北區": (23.0000, 120.2000),
    "中西區": (22.9917, 120.1917),
    "安南區": (23.0500, 120.1667),
    "安平區": (22.9917, 120.1667),
    "新營區": (23.3103, 120.3167),
    "鹽水區": (23.3203, 120.2661),
    "白河區": (23.3517, 120.4156),
    "柳營區": (23.2778, 120.3114),
    "後壁區": (23.3664, 120.3583),
    "東山區": (23.3258, 120.4036),
    "麻豆區": (23.1817, 120.2483),
    "下營區": (23.2347, 120.2647),
    "六甲區": (23.2319, 120.3478),
    "官田區": (23.1942, 120.3142),
    "大內區": (23.1203, 120.3497),
    "佳里區": (23.1647, 120.1772),
    "學甲區": (23.2328, 120.1803),
    "西港區": (23.1233, 120.2033),
    "七股區": (23.1453, 120.1314),
    "將軍區": (23.2000, 120.1500),
    "北門區": (23.2672, 120.1256),
    "新市區": (23.0786, 120.2919),
    "善化區": (23.1336, 120.2964),
    "安定區": (23.1017, 120.2364),
    "市新化區": (23.0386, 120.3108),
    "市山上區": (23.0975, 120.3547),
    "市左鎮區": (23.0578, 120.4014),
}

DEFAULT_COORDS = (23.0, 120.2)


@router.get("/top5")
async def get_top5_recommendations(
    topic_code: str = Query(..., description="主題代碼 (DUI/RED_LIGHT/DANGEROUS_DRIVING)"),
    shift_id: Optional[str] = Query(None, description="班別 (01-12)"),
    days: int = Query(30, ge=1, le=365, description="統計天數"),
    db: Session = Depends(get_db)
):
    """取得 Top 5 精準執法推薦"""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    topic_column_map = {
        "DUI": Ticket.topic_dui,
        "RED_LIGHT": Ticket.topic_red_light,
        "DANGEROUS_DRIVING": Ticket.topic_dangerous
    }
    
    topic_column = topic_column_map.get(topic_code)
    if not topic_column:
        raise HTTPException(status_code=400, detail="Invalid topic_code")
    
    conditions = [
        Ticket.violation_date >= start_date,
        Ticket.violation_date <= end_date,
        topic_column == True
    ]
    
    if shift_id:
        conditions.append(Ticket.shift_id == shift_id)
    
    # 依區域統計
    district_stats = db.query(
        Ticket.district,
        func.count(Ticket.id).label('ticket_count')
    ).filter(and_(*conditions)).group_by(Ticket.district).all()
    
    # 事故統計
    crash_conditions = [
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date
    ]
    
    crash_stats = db.query(
        Crash.district,
        func.count(Crash.id).label('crash_count'),
        func.sum(case((Crash.severity == 'A1', 1), else_=0)).label('a1_count'),
        func.sum(case((Crash.severity == 'A2', 1), else_=0)).label('a2_count')
    ).filter(and_(*crash_conditions)).group_by(Crash.district).all()
    
    crash_dict = {s.district: (s.crash_count, s.a1_count or 0, s.a2_count or 0) for s in crash_stats}
    
    recommendations = []
    for district, ticket_count in district_stats:
        if not district:
            continue
            
        crash_count, a1, a2 = crash_dict.get(district, (0, 0, 0))
        vpi = calculate_vpi(ticket_count, topic_code)
        cri = calculate_cri(crash_count, a1, a2)
        score = calculate_score(vpi, cri, topic_code)
        
        coords = DISTRICT_COORDINATES.get(district, DEFAULT_COORDS)
        
        recommendations.append({
            'rank': 0,  # Will be set after sorting
            'site_id': district,
            'site_name': district,
            'district': district,
            'location_desc': district,
            'coordinates': {
                'latitude': coords[0],
                'longitude': coords[1]
            },
            'metrics': {
                'vpi': round(vpi, 2),
                'cri': round(cri, 2),
                'score': round(score, 2)
            },
            'statistics': {
                'tickets': ticket_count,
                'crashes': crash_count,
                'a1_count': a1,
                'a2_count': a2
            }
        })
    
    recommendations.sort(key=lambda x: x['metrics']['score'], reverse=True)
    for i, rec in enumerate(recommendations[:5]):
        rec['rank'] = i + 1
    
    return {
        'topic_code': topic_code,
        'shift_id': shift_id,
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days
        },
        'recommendations': recommendations[:5],
        'total_sites': len(recommendations)
    }


@router.get("/heatmap")
async def get_heatmap_data(
    topic_code: str = Query(..., description="主題代碼"),
    shift_id: Optional[str] = Query(None, description="班別"),
    days: int = Query(30, ge=1, le=365, description="統計天數"),
    db: Session = Depends(get_db)
):
    """取得熱力圖資料"""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    topic_column_map = {
        "DUI": Ticket.topic_dui,
        "RED_LIGHT": Ticket.topic_red_light,
        "DANGEROUS_DRIVING": Ticket.topic_dangerous
    }
    
    topic_column = topic_column_map.get(topic_code)
    if not topic_column:
        raise HTTPException(status_code=400, detail="Invalid topic_code")
    
    conditions = [
        Ticket.violation_date >= start_date,
        Ticket.violation_date <= end_date,
        topic_column == True
    ]
    
    if shift_id:
        conditions.append(Ticket.shift_id == shift_id)
    
    district_stats = db.query(
        Ticket.district,
        func.count(Ticket.id).label('intensity')
    ).filter(and_(*conditions)).group_by(Ticket.district).all()
    
    heatmap_points = []
    for district, intensity in district_stats:
        if not district:
            continue
        coords = DISTRICT_COORDINATES.get(district, DEFAULT_COORDS)
        heatmap_points.append({
            'latitude': coords[0],
            'longitude': coords[1],
            'intensity': intensity,
            'site_name': f"{district}（區域統計）",
            'district': district
        })
    
    return {
        'topic_code': topic_code,
        'shift_id': shift_id,
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days
        },
        'points': heatmap_points,
        'total_points': len(heatmap_points)
    }


@router.get("/briefing-card")
async def get_briefing_card(
    topic_code: str = Query(..., description="主題代碼"),
    shift_id: str = Query(..., description="班別"),
    date: Optional[str] = Query(None, description="日期 (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """取得勤務建議卡"""
    target_date = datetime.now().date()
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    
    start_date = target_date - timedelta(days=30)
    
    topic_column_map = {
        "DUI": Ticket.topic_dui,
        "RED_LIGHT": Ticket.topic_red_light,
        "DANGEROUS_DRIVING": Ticket.topic_dangerous
    }
    
    topic_column = topic_column_map.get(topic_code)
    if not topic_column:
        raise HTTPException(status_code=400, detail="Invalid topic_code")
    
    conditions = [
        Ticket.violation_date >= start_date,
        Ticket.violation_date <= target_date,
        topic_column == True,
        Ticket.shift_id == shift_id
    ]
    
    # 取得 Top 5 區域
    top_districts = db.query(
        Ticket.district,
        func.count(Ticket.id).label('count')
    ).filter(and_(*conditions)).group_by(Ticket.district).order_by(desc('count')).limit(5).all()
    
    total_violations = db.query(func.count(Ticket.id)).filter(and_(*conditions)).scalar() or 0
    
    # 取得事故統計
    crash_conditions = [
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= target_date
    ]
    crash_stats = db.query(
        Crash.district,
        func.count(Crash.id).label('crash_count'),
        func.sum(case((Crash.severity == 'A1', 1), else_=0)).label('a1_count'),
        func.sum(case((Crash.severity == 'A2', 1), else_=0)).label('a2_count')
    ).filter(and_(*crash_conditions)).group_by(Crash.district).all()
    
    crash_dict = {s.district: (s.crash_count, s.a1_count or 0, s.a2_count or 0) for s in crash_stats}
    
    shift_names = {
        "01": "00:00-02:00", "02": "02:00-04:00", "03": "04:00-06:00",
        "04": "06:00-08:00", "05": "08:00-10:00", "06": "10:00-12:00",
        "07": "12:00-14:00", "08": "14:00-16:00", "09": "16:00-18:00",
        "10": "18:00-20:00", "11": "20:00-22:00", "12": "22:00-24:00"
    }
    
    topic_info = {
        "DUI": {"name": "酒駕", "emoji": "🍺", "focus": "酒後駕車取締"},
        "RED_LIGHT": {"name": "闘紅燈", "emoji": "🚦", "focus": "路口闖紅燈取締"},
        "DANGEROUS_DRIVING": {"name": "危險駕駛", "emoji": "⚠️", "focus": "危險駕駛行為取締"}
    }
    
    # 建立 top5_sites 陣列 (與 SiteRecommendation 格式一致)
    top5_sites = []
    for i, (district, ticket_count) in enumerate(top_districts):
        if not district:
            continue
        crash_count, a1, a2 = crash_dict.get(district, (0, 0, 0))
        vpi = calculate_vpi(ticket_count, topic_code)
        cri = calculate_cri(crash_count, a1, a2)
        score = calculate_score(vpi, cri, topic_code)
        coords = DISTRICT_COORDINATES.get(district, DEFAULT_COORDS)
        
        top5_sites.append({
            'rank': i + 1,
            'site_id': district,
            'site_name': district,
            'district': district,
            'location_desc': district,
            'coordinates': {
                'latitude': coords[0],
                'longitude': coords[1]
            },
            'metrics': {
                'vpi': round(vpi, 2),
                'cri': round(cri, 2),
                'score': round(score, 2)
            },
            'statistics': {
                'tickets': ticket_count,
                'crashes': crash_count,
                'violation_days': 30,
                'avg_tickets_per_day': round(ticket_count / 30, 2)
            }
        })
    
    topic_data = topic_info.get(topic_code, {"name": topic_code, "emoji": "📋", "focus": "取締作業"})
    
    return {
        "date": target_date.isoformat(),
        "shift": {
            "shift_id": shift_id,
            "shift_number": int(shift_id) if shift_id.isdigit() else 0,
            "time_range": shift_names.get(shift_id, shift_id)
        },
        "topic": {
            "code": topic_code,
            "name": topic_data["name"],
            "emoji": topic_data["emoji"],
            "focus": topic_data["focus"]
        },
        "top5_sites": top5_sites,
        "statistics": {
            "period_days": 30,
            "total_sites": len(top_districts)
        },
        "notes": [
            f"本班別共有 {total_violations} 件違規紀錄",
            "建議優先巡邏排名前 3 區域",
            "注意高齡駕駛人取締程序"
        ],
        "generated_at": datetime.now().isoformat(),
        "privacy_note": "本建議卡無任何個資，僅統計分析資料"
    }


# ============================================
# 事故熱點分析 API
# ============================================

TOPIC_NAMES = {
    'DUI': '酒駕',
    'RED_LIGHT': '闘紅燈',
    'DANGEROUS_DRIVING': '危險駕駛'
}


@router.get("/accidents/hotspots")
async def get_accident_hotspots(
    days: int = Query(30, ge=1, le=365, description="統計天數"),
    is_elderly: Optional[bool] = Query(False, description="是否僅統計高齡者事故"),
    start_date_param: str = Query(None, alias="start_date", description="起始日期 YYYY-MM-DD"),
    end_date_param: str = Query(None, alias="end_date", description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """事故熱點分析"""
    if start_date_param and end_date_param:
        end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
        start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
    else:
        end_date = get_data_end_date(db)
        start_date = end_date - timedelta(days=days)
    
    # 建立基礎篩選條件
    filters = [
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date,
        Crash.district.isnot(None)
    ]
    
    # 加入高齡者篩選
    if is_elderly:
        filters.append(Crash.is_elderly == True)
    
    crash_stats = db.query(
        Crash.district,
        func.count(Crash.id).label('total'),
        func.sum(case((Crash.severity == 'A1', 1), else_=0)).label('a1_count'),
        func.sum(case((Crash.severity == 'A2', 1), else_=0)).label('a2_count'),
        func.sum(case((Crash.severity == 'A3', 1), else_=0)).label('a3_count'),
        func.sum(Crash.severity_weight).label('severity_score'),
        # 改用 is_dui_crash_party (飲酒情形 4-8 + 排除行人) ground truth
        func.sum(case((Crash.is_dui_crash_party == True, 1), else_=0)).label('dui_crashes'),
        func.coalesce(func.sum(Crash.death_count), 0).label('death_total'),
        func.coalesce(func.sum(Crash.injury_count), 0).label('injury_total'),
    ).filter(
        *filters
    ).group_by(Crash.district).order_by(desc('severity_score')).all()

    hotspots = []
    a1_total = a2_total = a3_total = dui_crash_total = 0
    crash_dui_real_total = 0  # 事故表 ground truth (is_dui_crash_party 加總)
    death_grand_total = injury_grand_total = 0

    for district, total, a1, a2, a3, severity_score, dui_crashes, deaths, injuries in crash_stats:
        if not district:
            continue
        
        # 標準化區域名稱
        normalized_district = normalize_district(district)
        district_variants = get_district_variants(district)
        
        a1 = a1 or 0
        a2 = a2 or 0
        a3 = a3 or 0
        dui_crashes = dui_crashes or 0  # 事故表 ground truth (is_dui_crash_party)
        a1_total += a1
        a2_total += a2
        a3_total += a3
        crash_dui_real_total += dui_crashes  # 累加事故表側真實酒駕案件數
        # dui_crash_total 改用 Ticket 攔舉-肇事真實計數，於下方計算後累加
        death_grand_total += deaths or 0
        injury_grand_total += injuries or 0
        
        violation_stats = db.query(
            func.count(Ticket.id).label('total_violations'),
            # 酒駕 = topic_dui AND NOT 毒駕（排除 §35 I-2/IV 毒品案件）
            func.sum(case(((Ticket.topic_dui == True) & not_drug_filter(), 1), else_=0)).label('dui'),
            # 酒駕肇事舉發（UNION：subtype = '攔舉-肇事' OR violation_name 含肇事關鍵字）
            # 修復同仁將肇事誤標為「攔舉-一般」的黑數，實測較舊版多抓約 44%
            func.sum(
                case(
                    ((Ticket.topic_dui == True) & not_drug_filter() & dui_crash_filter(), 1),
                    else_=0,
                )
            ).label('dui_crash_derived'),
            # 毒駕舉發數（per-district，給地圖/毒駕專區用）
            func.sum(case((drug_drive_filter(), 1), else_=0)).label('drug'),
            func.sum(case((drug_drive_filter() & drug_crash_filter(), 1), else_=0)).label('drug_crash'),
            func.sum(case((Ticket.topic_red_light == True, 1), else_=0)).label('red_light'),
            func.sum(case((Ticket.topic_dangerous == True, 1), else_=0)).label('dangerous')
        ).filter(
            Ticket.violation_date >= start_date,
            Ticket.violation_date <= end_date,
            Ticket.district.in_(district_variants)  # 匹配兩種格式
        ).first()

        # Per-district 酒駕肇事顯示採 Crash 側 ground truth (= dui_crashes from crash_stats)
        # 因為 §35 法律規定酒駕事故必開單，所以「肇事舉發」應等於「酒駕事故」。
        # 但 dui_crash_total summary 仍累加 Ticket UNION 作為 banner「subtype 品質」對照。
        dui_total_for_district = int(violation_stats.dui or 0)
        dui_crash_real = int(dui_crashes)  # Crash 側：per-district 顯示用
        dui_crash_subtype = int(violation_stats.dui_crash_derived or 0)  # Ticket UNION：summary 用
        dui_no_crash_real = max(0, dui_total_for_district - dui_crash_real)
        dui_crash_total += dui_crash_subtype  # summary 累加 Ticket UNION (給 banner 顯示 subtype 標記漏標)

        violation_counts = {
            'DUI': dui_total_for_district,
            'RED_LIGHT': violation_stats.red_light or 0,
            'DANGEROUS_DRIVING': violation_stats.dangerous or 0
        }
        priority_topic = max(violation_counts, key=violation_counts.get) if any(violation_counts.values()) else None

        coords = DISTRICT_COORDINATES.get(normalized_district, DISTRICT_COORDINATES.get(district, DEFAULT_COORDS))
        enforcement_focus = "需要更多數據分析"
        if priority_topic:
            enforcement_focus = f"建議加強{TOPIC_NAMES.get(priority_topic, '')}取締"

        hotspots.append({
            'district': normalized_district,  # 省略「市」前綴
            'latitude': coords[0],
            'longitude': coords[1],
            'accidents': {
                'total': total,
                'a1_count': a1,
                'a2_count': a2,
                'a3_count': a3,
                'severity_score': severity_score or 0,
                'death_count': deaths or 0,
                'injury_count': injuries or 0,
            },
            'violations': {
                'total': violation_stats.total_violations or 0,
                'dui': dui_total_for_district,
                'dui_no_crash': dui_no_crash_real,  # 酒駕無肇事 = 總酒駕 − 攔舉-肇事
                'red_light': violation_stats.red_light or 0,
                'dangerous_driving': violation_stats.dangerous or 0
            },
            'dui_stats': {
                'total_dui': dui_total_for_district,
                'dui_with_crash': dui_crash_real,  # 酒駕有肇事（資料源：攔舉-肇事舉發）
                'dui_no_crash': dui_no_crash_real,  # 酒駕無肇事
                'dui_crash_source': 'ticket_subtype',  # 標明資料來源
            },
            'recommendation': {
                'priority_topic': priority_topic,
                'enforcement_focus': enforcement_focus
            }
        })
    
    return {
        'query_period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days
        },
        'hotspots': hotspots,
        'total_districts': len(hotspots),
        'summary': {
            'total_accidents': sum(h['accidents']['total'] for h in hotspots),
            'a1_total': a1_total,
            'a2_total': a2_total,
            'a3_total': a3_total,
            'dui_crash_total': dui_crash_total,             # Ticket UNION (有開單的酒駕肇事)
            'crash_dui_real_total': crash_dui_real_total,    # Crash ground truth (事故表側真實酒駕案件)
            'dui_dark_figure': max(0, crash_dui_real_total - dui_crash_total),  # 黑數 = 涉酒事故未對應到舉發
            'total_dui_violations': sum(h['violations']['dui'] for h in hotspots),
            'death_total': death_grand_total,
            'injury_total': injury_grand_total,
        }
    }


@router.get("/accidents/peak-times/{district}")
async def get_accident_peak_times(
    district: str,
    days: int = Query(30, ge=1, le=365, description="統計天數"),
    is_elderly: Optional[bool] = Query(False, description="是否僅統計高齡者事故"),
    start_date_param: str = Query(None, alias="start_date", description="起始日期 YYYY-MM-DD"),
    end_date_param: str = Query(None, alias="end_date", description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """特定區域的時段分布分析"""
    if start_date_param and end_date_param:
        end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
        start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
    else:
        end_date = get_data_end_date(db)
        start_date = end_date - timedelta(days=days)
    
    shift_names = {
        "01": "00:00-02:00", "02": "02:00-04:00", "03": "04:00-06:00",
        "04": "06:00-08:00", "05": "08:00-10:00", "06": "10:00-12:00",
        "07": "12:00-14:00", "08": "14:00-16:00", "09": "16:00-18:00",
        "10": "18:00-20:00", "11": "20:00-22:00", "12": "22:00-24:00"
    }
    
    # 使用區域名稱變體匹配（支援「新化區」和「市新化區」兩種格式）
    district_variants = get_district_variants(district)
    
    # 建立基礎篩選條件
    filters = [
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date,
        Crash.district.in_(district_variants)
    ]
    
    # 加入高齡者篩選
    if is_elderly:
        filters.append(Crash.is_elderly == True)
    
    crash_by_shift = db.query(
        Crash.shift_id,
        func.count(Crash.id).label('count')
    ).filter(
        *filters
    ).group_by(Crash.shift_id).all()
    
    violation_by_shift = db.query(
        Ticket.shift_id,
        func.count(Ticket.id).label('count')
    ).filter(
        Ticket.violation_date >= start_date,
        Ticket.violation_date <= end_date,
        Ticket.district.in_(district_variants)
    ).group_by(Ticket.shift_id).all()

    dui_by_shift = db.query(
        Ticket.shift_id,
        func.count(Ticket.id).label('count')
    ).filter(
        Ticket.violation_date >= start_date,
        Ticket.violation_date <= end_date,
        Ticket.district.in_(district_variants),
        Ticket.topic_dui == True,
        not_drug_filter(),  # 排除毒駕
    ).group_by(Ticket.shift_id).all()

    # 酒駕肇事 per shift：改用 Crash 側 ground truth (is_dui_crash_party)
    # 因 §35 法律規定酒駕事故必開單，Crash 側計數即為真實肇事舉發數。
    # 注意：此處 group by Crash.shift_id (= 事故發生時段)，
    # 跟 Ticket.shift_id (= 違規舉發時段) 通常一致，但分析角度更準確。
    dui_crash_by_shift = db.query(
        Crash.shift_id,
        func.count(Crash.id).label('count')
    ).filter(
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date,
        Crash.district.in_(district_variants),
        Crash.is_dui_crash_party == True,
    ).group_by(Crash.shift_id).all()

    crash_dict = {s.shift_id: s.count for s in crash_by_shift}
    violation_dict = {s.shift_id: s.count for s in violation_by_shift}
    dui_dict = {s.shift_id: s.count for s in dui_by_shift}
    dui_crash_dict = {s.shift_id: s.count for s in dui_crash_by_shift}

    shifts = []
    for shift_id in sorted(shift_names.keys()):
        accidents = crash_dict.get(shift_id, 0)
        violations = violation_dict.get(shift_id, 0)
        dui_citations = dui_dict.get(shift_id, 0)
        dui_crash_citations = dui_crash_dict.get(shift_id, 0)
        shifts.append({
            'shift_id': shift_id,
            'time_range': shift_names[shift_id],
            'accidents': accidents,
            'violations': violations,
            'dui_citations': dui_citations,
            'dui_crash_citations': dui_crash_citations,  # 含肇事的酒駕舉發數
        })
    
    peak_shifts = sorted(shifts, key=lambda x: x['accidents'], reverse=True)[:3]
    priority_shifts = [s['shift_id'] for s in peak_shifts if s['accidents'] > 0]
    
    return {
        'district': district,
        'query_period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days
        },
        'shifts': shifts,
        'recommendations': {
            'priority_shifts': priority_shifts,
            'enforcement_suggestion': f"建議在{', '.join([shift_names[s] for s in priority_shifts[:2]])}加強取締" if priority_shifts else "無明顯高峰時段",
            'rationale': "該時段事故發生率較高"
        }
    }


@router.get("/heatmap/accidents")
async def get_accident_heatmap(
    shift_id: Optional[str] = Query(None, description="班別"),
    days: int = Query(30, ge=1, le=365, description="統計天數"),
    db: Session = Depends(get_db)
):
    """事故熱力圖資料"""
    end_date = get_data_end_date(db)
    start_date = end_date - timedelta(days=days)
    
    conditions = [
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date,
        Crash.district.isnot(None)
    ]
    
    if shift_id:
        conditions.append(Crash.shift_id == shift_id)
    
    district_stats = db.query(
        Crash.district,
        func.count(Crash.id).label('intensity'),
        func.sum(case((Crash.severity == 'A1', 1), else_=0)).label('a1'),
        func.sum(case((Crash.severity == 'A2', 1), else_=0)).label('a2')
    ).filter(and_(*conditions)).group_by(Crash.district).all()
    
    points = []
    for district, intensity, a1, a2 in district_stats:
        if not district:
            continue
        coords = DISTRICT_COORDINATES.get(district, DEFAULT_COORDS)
        points.append({
            'latitude': coords[0],
            'longitude': coords[1],
            'intensity': intensity,
            'a1_count': a1 or 0,
            'a2_count': a2 or 0,
            'district': district
        })
    
    return {
        'shift_id': shift_id,
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days
        },
        'points': points,
        'total_points': len(points)
    }


@router.get("/cross-analysis")
async def get_cross_analysis(
    district: Optional[str] = Query(None, description="區域篩選"),
    days: int = Query(30, ge=1, le=365, description="統計天數"),
    start_date_param: str = Query(None, alias="start_date", description="起始日期 YYYY-MM-DD"),
    end_date_param: str = Query(None, alias="end_date", description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """事故與違規交叉分析"""
    if start_date_param and end_date_param:
        end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
        start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
    else:
        end_date = get_data_end_date(db)
        start_date = end_date - timedelta(days=days)
    
    shift_names = {
        "01": "00:00-02:00", "02": "02:00-04:00", "03": "04:00-06:00",
        "04": "06:00-08:00", "05": "08:00-10:00", "06": "10:00-12:00",
        "07": "12:00-14:00", "08": "14:00-16:00", "09": "16:00-18:00",
        "10": "18:00-20:00", "11": "20:00-22:00", "12": "22:00-24:00"
    }
    
    crash_conditions = [
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date,
        Crash.district.isnot(None)
    ]
    if district:
        district_variants = get_district_variants(district)
        crash_conditions.append(Crash.district.in_(district_variants))
    
    crash_stats = db.query(
        Crash.district,
        Crash.shift_id,
        func.count(Crash.id).label('accidents')
    ).filter(and_(*crash_conditions)).group_by(Crash.district, Crash.shift_id).all()
    
    ticket_conditions = [
        Ticket.violation_date >= start_date,
        Ticket.violation_date <= end_date,
        Ticket.district.isnot(None)
    ]
    if district:
        district_variants = get_district_variants(district)
        ticket_conditions.append(Ticket.district.in_(district_variants))
    
    ticket_stats = db.query(
        Ticket.district,
        Ticket.shift_id,
        func.count(Ticket.id).label('violations')
    ).filter(and_(*ticket_conditions)).group_by(Ticket.district, Ticket.shift_id).all()
    
    # 建立 ticket_dict，標準化區域名稱
    ticket_dict = {}
    for t in ticket_stats:
        normalized = normalize_district(t.district)
        key = (normalized, t.shift_id)
        ticket_dict[key] = ticket_dict.get(key, 0) + t.violations
    
    cross_analysis = []
    for c in crash_stats:
        normalized_district = normalize_district(c.district)
        violations = ticket_dict.get((normalized_district, c.shift_id), 0)
        gap = c.accidents - (violations * 0.1) if violations else c.accidents
        
        priority = 'LOW'
        if gap > 5:
            priority = 'HIGH'
        elif gap > 2:
            priority = 'MEDIUM'
        
        cross_analysis.append({
            'district': normalized_district,  # 標準化區域名稱（省略「市」）
            'shift_id': c.shift_id,
            'time_range': shift_names.get(c.shift_id, c.shift_id),
            'accidents': c.accidents,
            'violations': violations,
            'enforcement_gap': round(gap, 1),
            'priority': priority
        })
    
    cross_analysis.sort(key=lambda x: x['enforcement_gap'], reverse=True)
    
    high_priority = [x for x in cross_analysis if x['priority'] == 'HIGH']
    medium_priority = [x for x in cross_analysis if x['priority'] == 'MEDIUM']
    low_priority = [x for x in cross_analysis if x['priority'] == 'LOW']
    
    return {
        'query_period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days
        },
        'district_filter': district,
        'cross_analysis': cross_analysis,
        'summary': {
            'total_combinations': len(cross_analysis),
            'high_priority_count': len(high_priority),
            'medium_priority_count': len(medium_priority),
            'low_priority_count': len(low_priority)
        },
        'recommendations': {
            'high_priority_targets': high_priority[:5],
            'suggestion': '針對執法缺口高的區域/時段加強取締，可有效降低事故發生率'
        }
    }


# ============================================
# 進階分析 API
# ============================================

@router.get("/analysis/elderly-vehicle-types")
async def get_elderly_vehicle_analysis(
    days: int = Query(default=365, description="分析期間天數"),
    start_date_param: str = Query(None, alias="start_date", description="起始日期 YYYY-MM-DD"),
    end_date_param: str = Query(None, alias="end_date", description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """
    高齡者車種分析
    分析高齡者事故中的車種分佈（機車、行人、自小客等）
    """
    if start_date_param and end_date_param:
        end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
        start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
    else:
        end_date = get_data_end_date(db)
        start_date = end_date - timedelta(days=days)
    
    # 查詢高齡者事故的車種分佈
    vehicle_stats = db.query(
        Crash.party_type,
        func.count(Crash.id).label('count'),
        func.sum(case((Crash.severity == 'A1', 1), else_=0)).label('a1_count'),
        func.sum(case((Crash.severity == 'A2', 1), else_=0)).label('a2_count')
    ).filter(
        Crash.is_elderly == True,
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date,
        Crash.party_type.isnot(None)
    ).group_by(Crash.party_type).order_by(desc('count')).all()
    
    # 查詢總計
    total_elderly = db.query(func.count(Crash.id)).filter(
        Crash.is_elderly == True,
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date
    ).scalar() or 0
    
    vehicle_breakdown = []
    for v in vehicle_stats:
        vehicle_breakdown.append({
            'vehicle_type': v.party_type or '未知',
            'count': v.count,
            'a1_count': v.a1_count or 0,
            'a2_count': v.a2_count or 0,
            'percentage': round(v.count / total_elderly * 100, 1) if total_elderly > 0 else 0
        })
    
    # 分析建議
    top_vehicle = vehicle_breakdown[0]['vehicle_type'] if vehicle_breakdown else '未知'
    
    return {
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days
        },
        'total_elderly_accidents': total_elderly,
        'vehicle_breakdown': vehicle_breakdown,
        'insights': {
            'most_common_vehicle': top_vehicle,
            'recommendation': f'高齡者最常涉及的車種為「{top_vehicle}」，建議針對該車種加強宣導'
        },
        'note': '統計數據已去識別化，僅供執法參考'
    }


@router.get("/analysis/dui-environment")
async def get_dui_environment_analysis(
    days: int = Query(default=365, description="分析期間天數"),
    db: Session = Depends(get_db)
):
    """
    酒駕環境分析
    分析酒駕事故的天候與光線分佈
    """
    end_date = get_data_end_date(db)
    start_date = end_date - timedelta(days=days)
    
    # 天候分佈
    weather_stats = db.query(
        Crash.weather,
        func.count(Crash.id).label('count')
    ).filter(
        Crash.is_dui_crash_party == True,
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date,
        Crash.weather.isnot(None)
    ).group_by(Crash.weather).order_by(desc('count')).all()
    
    # 光線分佈
    light_stats = db.query(
        Crash.light,
        func.count(Crash.id).label('count')
    ).filter(
        Crash.is_dui_crash_party == True,
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date,
        Crash.light.isnot(None)
    ).group_by(Crash.light).order_by(desc('count')).all()
    
    # 總計
    total_dui = db.query(func.count(Crash.id)).filter(
        Crash.is_dui_crash_party == True,
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date
    ).scalar() or 0
    
    weather_breakdown = [
        {'weather': w.weather or '未知', 'count': w.count, 
         'percentage': round(w.count / total_dui * 100, 1) if total_dui > 0 else 0}
        for w in weather_stats
    ]
    
    light_breakdown = [
        {'light': l.light or '未知', 'count': l.count,
         'percentage': round(l.count / total_dui * 100, 1) if total_dui > 0 else 0}
        for l in light_stats
    ]
    
    # 分析夜間比例
    night_keywords = ['夜間', '暗', '無照明', '晨昏']
    night_count = sum(l.count for l in light_stats if any(k in (l.light or '') for k in night_keywords))
    night_percentage = round(night_count / total_dui * 100, 1) if total_dui > 0 else 0
    
    return {
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days
        },
        'total_dui_crashes': total_dui,
        'weather_breakdown': weather_breakdown,
        'light_breakdown': light_breakdown,
        'insights': {
            'night_percentage': night_percentage,
            'recommendation': f'酒駕事故有 {night_percentage}% 發生於視線不良環境，建議加強夜間稽查'
        },
        'note': '統計數據已去識別化，僅供執法參考'
    }


# ---------------------------------------------------------------------------
# 派出所 → 行政區 對照表
# ---------------------------------------------------------------------------
# 事故資料絕大多數歸類於「交通分隊」，並未細分到派出所層級（本資料約 95% 是 交通分隊）。
# 為了讓「派出所篩選」對事故仍有意義，使用以下對照表，將派出所名稱映射回所屬行政區，
# 篩選事故時改用 district 欄位作為後備條件。
# ---------------------------------------------------------------------------
STATION_TO_DISTRICTS: dict[str, list[str]] = {
    # 新化區
    "新化分局新化派出所": ["新化區"],
    "新化分局唪口派出所": ["新化區"],
    "新化分局知義派出所": ["新化區"],
    "新化分局那拔派出所": ["新化區"],
    # 山上區
    "新化分局山上分駐所": ["山上區"],
    # 左鎮區
    "新化分局左鎮分駐所": ["左鎮區"],
    "新化分局岡林派出所": ["左鎮區"],
    # 全分局共用單位（不限定行政區）
    "新化分局交通分隊": ["新化區", "山上區", "左鎮區"],
    "新化分局交通組": ["新化區", "山上區", "左鎮區"],
    "新化分局警備隊": ["新化區", "山上區", "左鎮區"],
}


@router.get("/map/units")
async def get_map_units(
    days: int = Query(default=90, description="統計期間天數（計數用）"),
    start_date: str = Query(default=None, description="起始日期 YYYY-MM-DD"),
    end_date_param: str = Query(default=None, alias="end_date", description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    取得所有派出所/單位名稱，並附上該期間內的事故與違規點位數。
    前端 Checkbox 列表顯示用。
    """
    # 決定統計期間
    if start_date and end_date_param:
        from datetime import datetime as dt
        end_date = dt.strptime(end_date_param, "%Y-%m-%d").date()
        start_date = dt.strptime(start_date, "%Y-%m-%d").date()
    else:
        end_date = get_data_end_date(db)
        start_date = end_date - timedelta(days=days)

    # 事故計數（含 district fallback，與 /map/points 一致）
    crash_counts_raw = dict(
        db.query(Crash.sub_unit, func.count(Crash.id))
        .filter(
            Crash.sub_unit.isnot(None),
            Crash.occurred_date >= start_date,
            Crash.occurred_date <= end_date,
        )
        .group_by(Crash.sub_unit)
        .all()
    )

    # district → 該 district 內的 crash 總數（供 fallback 計算用）
    district_crash_counts = dict(
        db.query(Crash.district, func.count(Crash.id))
        .filter(
            Crash.district.isnot(None),
            Crash.sub_unit.like('%交通分隊%'),
            Crash.occurred_date >= start_date,
            Crash.occurred_date <= end_date,
        )
        .group_by(Crash.district)
        .all()
    )

    # 違規計數
    ticket_counts = dict(
        db.query(Ticket.unit_code, func.count(Ticket.id))
        .filter(
            Ticket.unit_code.isnot(None),
            Ticket.violation_date >= start_date,
            Ticket.violation_date <= end_date,
        )
        .group_by(Ticket.unit_code)
        .all()
    )

    # 聯集所有單位
    crash_units = set(r[0] for r in db.query(Crash.sub_unit).filter(Crash.sub_unit.isnot(None)).distinct().all() if r[0])
    ticket_units = set(ticket_counts.keys())
    all_units = sorted(crash_units | ticket_units)

    # 幕僚/統籌單位：不處理事故（交通組、警備隊是幕僚單位，只製違規單，無事故轄區）
    # 交通分隊雖也是統籌，但仍有舊資料殘留未回補轄區，保留其原始 sub_unit 計數
    STAFF_UNITS_NO_CRASH = ("交通組", "警備隊")

    units_with_count = []
    for unit in all_units:
        if any(kw in unit for kw in STAFF_UNITS_NO_CRASH):
            # 幕僚單位：事故恆為 0（不做 district fallback 亂塞）
            crash_count = 0
        else:
            # 派出所 + 交通分隊：直接用 sub_unit 計數
            crash_count = crash_counts_raw.get(unit, 0)

        ticket_count = ticket_counts.get(unit, 0)
        units_with_count.append({
            "unit": unit,
            "crash_count": crash_count,
            "ticket_count": ticket_count,
            "total": crash_count + ticket_count,
        })

    # 保留舊格式相容
    return {
        "units": all_units,
        "units_with_count": units_with_count,
    }


@router.get("/map/points")
async def get_map_points(
    days: int = Query(default=90, description="分析期間天數（當 start_date/end_date 未提供時使用）"),
    start_date: str = Query(default=None, description="起始日期 YYYY-MM-DD"),
    end_date_param: str = Query(default=None, alias="end_date", description="結束日期 YYYY-MM-DD"),
    point_type: str = Query(default="all", description="資料類型: all, crash, ticket"),
    severity: str = Query(default=None, description="嚴重度篩選: A1, A2, A3（逗號分隔可複選）"),
    topic: str = Query(default=None, description="主題篩選: DUI, RED_LIGHT, DANGEROUS_DRIVING"),
    units: str = Query(default=None, description="派出所/單位篩選（逗號分隔可複選，如：新化分局新化派出所,新化分局知義派出所）"),
    db: Session = Depends(get_db)
):
    """
    取得地圖點位資料
    返回帶有真實座標的事故/違規資料供地圖顯示
    """
    if start_date and end_date_param:
        from datetime import datetime as dt
        end_date = dt.strptime(end_date_param, "%Y-%m-%d").date()
        start_date = dt.strptime(start_date, "%Y-%m-%d").date()
    else:
        end_date = get_data_end_date(db)
        start_date = end_date - timedelta(days=days)
    
    result = {
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days
        },
        'crash_points': [],
        'ticket_points': [],
        'summary': {
            'total_crashes': 0,
            'total_tickets': 0,
            'crashes_with_coords': 0,
            'tickets_with_coords': 0
        }
    }
    
    unit_list = [u.strip() for u in units.split(",") if u.strip()] if units else None

    # 取得事故點位
    if point_type in ['all', 'crash']:
        crash_query = db.query(
            Crash.id,
            Crash.latitude,
            Crash.longitude,
            Crash.district,
            Crash.location_desc,
            Crash.severity,
            Crash.occurred_date,
            Crash.occurred_time,
            Crash.shift_id,
            Crash.is_elderly,
            Crash.suspected_alcohol,
            Crash.is_dui_crash_party,  # ground truth (飲酒情形 4-8)
            Crash.party_type,
            Crash.sub_unit,
            Crash.death_count,    # 實際死亡人數（不是件數）
            Crash.injury_count    # 實際受傷人數（不是件數）
        ).filter(
            Crash.occurred_date >= start_date,
            Crash.occurred_date <= end_date
        )

        if severity:
            sev_list = [s.strip() for s in severity.split(",")]
            if len(sev_list) == 1:
                crash_query = crash_query.filter(Crash.severity == sev_list[0])
            else:
                crash_query = crash_query.filter(Crash.severity.in_(sev_list))

        if unit_list:
            # 直接以 sub_unit 比對「所轄單位名稱」。
            # 對於尚未回補轄區派出所的舊資料（sub_unit 仍為交通分隊），
            # 以派出所→行政區對照表將 district 吻合的舊資料納入，避免選派出所時事故歸零。
            mapped_districts: set[str] = set()
            for u in unit_list:
                for d in STATION_TO_DISTRICTS.get(u, []):
                    mapped_districts.add(d)

            crash_filters = [Crash.sub_unit.in_(unit_list)]
            if mapped_districts:
                # 僅在 sub_unit 仍為「交通分隊」等催化單位時才套用 district fallback
                crash_filters.append(and_(
                    Crash.sub_unit.like('%交通分隊%'),
                    Crash.district.in_(list(mapped_districts))
                ))
            crash_query = crash_query.filter(or_(*crash_filters))

        crashes = crash_query.all()
        result['summary']['total_crashes'] = len(crashes)

        # 涉酒事故計數（Crash 側 ground truth：is_dui_crash_party）
        dui_real_crash_count = 0

        for c in crashes:
            # 用 is_dui_crash_party (ground truth, 飲酒情形 4-8 + 排除行人)
            # 為相容歷史資料，若 is_dui_crash_party 為 False/None 則 fallback 到 suspected_alcohol
            is_dui_crash = bool(getattr(c, 'is_dui_crash_party', None) or c.suspected_alcohol)
            if is_dui_crash:
                dui_real_crash_count += 1
            if c.latitude and c.longitude:
                result['crash_points'].append({
                    'id': c.id,
                    'lat': c.latitude,
                    'lng': c.longitude,
                    'district': c.district,
                    'location': c.location_desc,
                    'severity': c.severity,
                    'date': c.occurred_date.isoformat() if c.occurred_date else None,
                    'time': c.occurred_time.strftime('%H:%M') if c.occurred_time else None,
                    'shift': c.shift_id,
                    'is_elderly': c.is_elderly,
                    'is_dui': is_dui_crash,
                    'vehicle_type': c.party_type,
                    'unit': c.sub_unit,
                    'death_count': c.death_count or 0,        # 實際死亡人數
                    'injury_count': c.injury_count or 0,       # 實際受傷人數
                })
        result['summary']['crashes_with_coords'] = len(result['crash_points'])
        result['summary']['dui_real_crashes'] = dui_real_crash_count  # Crash 側真實涉酒事故
    
    # 取得違規點位
    if point_type in ['all', 'ticket']:
        # is_dui_crash: 採 UNION 信號（subtype=攔舉-肇事 OR violation_name 含肇事/致人/重傷等關鍵字）
        # 注意：排除毒駕（not_drug_filter），酒駕肇事只算純酒精
        is_dui_crash_expr = case(
            ((Ticket.topic_dui == True) & not_drug_filter() & dui_crash_filter(), 1),
            else_=0,
        )
        # is_drug: 毒駕標記（§35 I-2 吸食毒品 / §35 IV 毒品拒檢）
        is_drug_expr = case((drug_drive_filter(), 1), else_=0)
        is_drug_crash_expr = case((drug_drive_filter() & drug_crash_filter(), 1), else_=0)
        ticket_query = db.query(
            Ticket.id,
            Ticket.latitude,
            Ticket.longitude,
            Ticket.district,
            Ticket.location_desc,
            Ticket.topic_dui,
            Ticket.topic_red_light,
            Ticket.topic_dangerous,
            Ticket.violation_name,
            Ticket.violation_date,
            Ticket.violation_time,
            Ticket.shift_id,
            Ticket.is_elderly,
            Ticket.vehicle_type,
            Ticket.enforcement_subtype,
            Ticket.unit_code,
            is_dui_crash_expr.label('is_dui_crash'),
            is_drug_expr.label('is_drug'),
            is_drug_crash_expr.label('is_drug_crash'),
        ).filter(
            Ticket.violation_date >= start_date,
            Ticket.violation_date <= end_date
        )

        if topic:
            if topic == 'DUI':
                # 酒駕：排除毒駕
                ticket_query = ticket_query.filter(Ticket.topic_dui == True, not_drug_filter())
            elif topic == 'DRUG':
                ticket_query = ticket_query.filter(drug_drive_filter())
            elif topic == 'RED_LIGHT':
                ticket_query = ticket_query.filter(Ticket.topic_red_light == True)
            elif topic == 'DANGEROUS_DRIVING':
                ticket_query = ticket_query.filter(Ticket.topic_dangerous == True)

        if unit_list:
            ticket_query = ticket_query.filter(Ticket.unit_code.in_(unit_list))

        tickets = ticket_query.all()
        result['summary']['total_tickets'] = len(tickets)

        # DUI / 毒駕 統計
        dui_total_count = 0
        dui_crash_count = 0
        drug_total_count = 0
        drug_crash_count = 0

        for t in tickets:
            if t.latitude and t.longitude:
                is_drug_flag = bool(getattr(t, 'is_drug', 0))
                # 判斷主題（毒駕優先，因毒品案件 topic_dui 也是 True）
                topic_name = None
                if is_drug_flag:
                    topic_name = 'DRUG'
                elif t.topic_dui:
                    topic_name = 'DUI'
                elif t.topic_red_light:
                    topic_name = 'RED_LIGHT'
                elif t.topic_dangerous:
                    topic_name = 'DANGEROUS_DRIVING'

                is_crash_flag = bool(getattr(t, 'is_dui_crash', 0))
                is_drug_crash_flag = bool(getattr(t, 'is_drug_crash', 0))
                if is_drug_flag:
                    drug_total_count += 1
                    if is_drug_crash_flag:
                        drug_crash_count += 1
                elif t.topic_dui:
                    dui_total_count += 1
                    if is_crash_flag:
                        dui_crash_count += 1

                result['ticket_points'].append({
                    'id': t.id,
                    'lat': t.latitude,
                    'lng': t.longitude,
                    'district': t.district,
                    'location': t.location_desc,
                    'topic': topic_name,
                    'violation_name': t.violation_name,
                    'date': t.violation_date.isoformat() if t.violation_date else None,
                    'time': t.violation_time.strftime('%H:%M') if t.violation_time else None,
                    'shift': t.shift_id,
                    'is_elderly': t.is_elderly,
                    'vehicle_type': t.vehicle_type,
                    'enforcement_type': t.enforcement_subtype,
                    'unit': t.unit_code,
                    'is_dui_crash': is_crash_flag,
                    'is_drug': is_drug_flag,
                    'is_drug_crash': is_drug_crash_flag,
                })
        result['summary']['tickets_with_coords'] = len(result['ticket_points'])
        result['summary']['dui_tickets'] = dui_total_count
        result['summary']['dui_crash_tickets'] = dui_crash_count
        result['summary']['drug_tickets'] = drug_total_count
        result['summary']['drug_crash_tickets'] = drug_crash_count
    
    result['note'] = '點位資料已去識別化，座標僅供執法分析使用'
    return result


@router.get("/map/heatmap-data")
async def get_precise_heatmap_data(
    days: int = Query(default=90, description="分析期間天數"),
    data_type: str = Query(default="crash", description="資料類型: crash 或 ticket"),
    db: Session = Depends(get_db)
):
    """
    取得精準熱力圖資料
    基於真實座標聚合的熱點資料
    """
    end_date = get_data_end_date(db)
    start_date = end_date - timedelta(days=days)
    
    if data_type == "crash":
        # 聚合事故點位
        points = db.query(
            func.round(Crash.latitude, 3).label('lat'),
            func.round(Crash.longitude, 3).label('lng'),
            func.count(Crash.id).label('count'),
            func.sum(case((Crash.severity == 'A1', 5), (Crash.severity == 'A2', 3), else_=1)).label('weight')
        ).filter(
            Crash.occurred_date >= start_date,
            Crash.occurred_date <= end_date,
            Crash.latitude.isnot(None),
            Crash.longitude.isnot(None)
        ).group_by(
            func.round(Crash.latitude, 3),
            func.round(Crash.longitude, 3)
        ).order_by(desc('weight')).limit(200).all()
    else:
        # 聚合違規點位
        points = db.query(
            func.round(Ticket.latitude, 3).label('lat'),
            func.round(Ticket.longitude, 3).label('lng'),
            func.count(Ticket.id).label('count'),
            func.count(Ticket.id).label('weight')
        ).filter(
            Ticket.violation_date >= start_date,
            Ticket.violation_date <= end_date,
            Ticket.latitude.isnot(None),
            Ticket.longitude.isnot(None)
        ).group_by(
            func.round(Ticket.latitude, 3),
            func.round(Ticket.longitude, 3)
        ).order_by(desc('count')).limit(200).all()
    
    heatmap_points = []
    max_weight = max([p.weight for p in points], default=1)
    
    for p in points:
        if p.lat and p.lng:
            heatmap_points.append({
                'lat': float(p.lat),
                'lng': float(p.lng),
                'count': p.count,
                'weight': p.weight,
                'intensity': round(p.weight / max_weight, 2)
            })
    
    return {
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days
        },
        'data_type': data_type,
        'points': heatmap_points,
        'total_points': len(heatmap_points),
        'note': '熱力圖資料已去識別化'
    }


@router.put("/map/crash/{crash_id}/coordinates")
async def update_crash_coordinates(
    crash_id: int,
    latitude: float = Query(..., description="新緯度"),
    longitude: float = Query(..., description="新經度"),
    db: Session = Depends(get_db)
):
    """
    更新事故點位座標
    用於手動校正自動分配的區域座標
    """
    crash = db.query(Crash).filter(Crash.id == crash_id).first()
    if not crash:
        raise HTTPException(status_code=404, detail="事故資料不存在")
    
    # 記錄舊座標
    old_lat = crash.latitude
    old_lng = crash.longitude
    
    # 更新座標
    crash.latitude = latitude
    crash.longitude = longitude
    db.commit()
    
    return {
        'success': True,
        'crash_id': crash_id,
        'old_coordinates': {'lat': old_lat, 'lng': old_lng},
        'new_coordinates': {'lat': latitude, 'lng': longitude},
        'message': '座標已更新'
    }


@router.put("/map/ticket/{ticket_id}/coordinates")
async def update_ticket_coordinates(
    ticket_id: int,
    latitude: float = Query(..., description="新緯度"),
    longitude: float = Query(..., description="新經度"),
    db: Session = Depends(get_db)
):
    """
    更新違規點位座標
    用於手動校正自動分配的區域座標
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="違規資料不存在")

    old_lat = ticket.latitude
    old_lng = ticket.longitude

    ticket.latitude = latitude
    ticket.longitude = longitude
    db.commit()

    return {
        'success': True,
        'ticket_id': ticket_id,
        'old_coordinates': {'lat': old_lat, 'lng': old_lng},
        'new_coordinates': {'lat': latitude, 'lng': longitude},
        'message': '座標已更新'
    }


@router.put("/map/crashes/coordinates/batch")
async def batch_update_crash_coordinates(
    updates: list = [],
    db: Session = Depends(get_db)
):
    """
    批次更新多個事故點位座標
    updates: [{'id': 1, 'lat': 23.0, 'lng': 120.0}, ...]
    """
    from fastapi import Body
    
    updated_count = 0
    errors = []
    
    for item in updates:
        crash_id = item.get('id')
        lat = item.get('lat')
        lng = item.get('lng')
        
        if not crash_id or lat is None or lng is None:
            errors.append(f"無效資料: {item}")
            continue
        
        crash = db.query(Crash).filter(Crash.id == crash_id).first()
        if crash:
            crash.latitude = lat
            crash.longitude = lng
            updated_count += 1
        else:
            errors.append(f"ID {crash_id} 不存在")
    
    db.commit()
    
    return {
        'success': True,
        'updated_count': updated_count,
        'errors': errors if errors else None,
        'message': f'已更新 {updated_count} 筆座標'
    }


# ============================================
# Phase 2：廊帶線性分析 / 會勘資料包 / 勤務建議單
# ============================================

@router.get("/corridor-analysis")
async def get_corridor_analysis(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    route: str = Query(None, description="公路路線名稱（如：台20線），未提供時回傳路線排名"),
    db: Session = Depends(get_db),
):
    """廊帶（公路路線）線性分析。

    模式 A（route 未指定）：依路線彙整事故件數與 EPDO（台灣道安標準公式，人數口徑，
    見 app/utils/epdo.py），依 EPDO 降冪排序，用於找出應優先介入的路線。
    模式 B（route 指定）：將該路線切成 500 公尺一段，逐段統計事故樣態，
    用於鎖定路線內的具體「熱段」供工程改善。
    """
    try:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return {"error": "日期格式錯誤"}

    period = {"start_date": start_date, "end_date": end_date}

    if not route:
        # ---- 模式 A：路線排名 ----
        rows = db.query(
            Crash.route_name,
            func.count(Crash.id).label("total"),
            func.sum(case((Crash.severity == "A1", 1), else_=0)).label("a1"),
            func.sum(case((Crash.severity == "A2", 1), else_=0)).label("a2"),
            func.sum(case((Crash.severity == "A3", 1), else_=0)).label("a3"),
            func.coalesce(func.sum(Crash.death_count), 0).label("deaths"),
            func.coalesce(func.sum(Crash.injury_count), 0).label("injuries"),
            epdo_sql_sum().label("epdo"),
        ).filter(
            Crash.route_name.isnot(None),
            Crash.occurred_date >= sd,
            Crash.occurred_date <= ed,
        ).group_by(Crash.route_name).order_by(desc("epdo")).all()

        routes = [{
            "route": r.route_name,
            "total": r.total,
            "a1": int(r.a1 or 0),
            "a2": int(r.a2 or 0),
            "a3": int(r.a3 or 0),
            "deaths": int(r.deaths or 0),
            "injuries": int(r.injuries or 0),
            "epdo": round(r.epdo or 0, 1),
        } for r in rows]

        return {"period": period, "mode": "routes", "routes": routes}

    # ---- 模式 B：該路線 500 公尺分段 ----
    import math
    from collections import Counter

    NIGHT_SHIFTS = {"10", "11", "12", "01", "02", "03"}

    crashes = db.query(Crash).filter(
        Crash.route_name == route,
        Crash.route_km.isnot(None),
        Crash.occurred_date >= sd,
        Crash.occurred_date <= ed,
    ).all()

    def mode_value(values):
        """計算眾數（NULL/空值不計，無資料回傳 None）"""
        filtered = [v for v in values if v]
        if not filtered:
            return None
        return Counter(filtered).most_common(1)[0][0]

    # 依 0.5 公里分段（key = 該段起點公里數）
    seg_map: dict = {}
    for c in crashes:
        seg_key = round(math.floor(c.route_km * 2) / 2, 1)
        seg_map.setdefault(seg_key, []).append(c)

    segments = []
    for seg_key in sorted(seg_map.keys()):
        items = seg_map[seg_key]
        segments.append({
            "km_start": seg_key,
            "km_end": round(seg_key + 0.5, 1),
            "total": len(items),
            "a1": sum(1 for c in items if c.severity == "A1"),
            "a2": sum(1 for c in items if c.severity == "A2"),
            "a3": sum(1 for c in items if c.severity == "A3"),
            "deaths": sum(c.death_count or 0 for c in items),
            "injuries": sum(c.injury_count or 0 for c in items),
            "epdo": epdo_sum(items),
            "top_crash_type": mode_value([c.crash_type for c in items]),
            "top_cause": mode_value([c.cause for c in items]),
            "night_count": sum(1 for c in items if c.shift_id in NIGHT_SHIFTS),
        })

    top_segments = sorted(segments, key=lambda s: -s["epdo"])[:5]

    return {
        "period": period,
        "mode": "segments",
        "route": route,
        "total_with_km": len(crashes),
        "segments": segments,
        "top_segments": top_segments,
    }


@router.get("/site-dossier")
async def get_site_dossier(
    lat: float = Query(..., description="會勘點緯度"),
    lng: float = Query(..., description="會勘點經度"),
    radius_m: int = Query(200, description="搜尋半徑（公尺），限制 50~1000"),
    end_date: str = Query(None, description="分析窗結束日期 YYYY-MM-DD，未提供時採資料庫最新事故日期"),
    db: Session = Depends(get_db),
):
    """會勘資料包（site dossier）。

    給定座標與半徑，彙整過去 3 年內事故清單、樣態統計、涉及人員類型，
    並依規則引擎產出改善建議，供警力會同工務/養工單位現場會勘時使用。
    """
    import math
    from collections import Counter

    # radius_m 限制 50~1000，超界夾住
    radius_m = max(50, min(1000, radius_m))

    if end_date:
        try:
            ed = datetime.strptime(end_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return {"error": "日期格式錯誤"}
    else:
        ed = db.query(func.max(Crash.occurred_date)).scalar() or datetime.now().date()

    sd = ed - timedelta(days=365 * 3)

    # bounding box 預過濾：1 度緯度約 111000 公尺；經度依緯度用 cos 修正
    lat_delta = radius_m / 111000.0
    cos_lat = math.cos(math.radians(lat))
    lng_delta = radius_m / (111000.0 * cos_lat) if cos_lat != 0 else 180.0

    candidates = db.query(Crash).filter(
        Crash.latitude.isnot(None),
        Crash.longitude.isnot(None),
        Crash.latitude >= lat - lat_delta,
        Crash.latitude <= lat + lat_delta,
        Crash.longitude >= lng - lng_delta,
        Crash.longitude <= lng + lng_delta,
        Crash.occurred_date >= sd,
        Crash.occurred_date <= ed,
    ).all()

    def haversine_m(lat1, lng1, lat2, lng2):
        """Haversine 公式計算兩點間距離（公尺），供精算過濾用"""
        R = 6371000.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lng2 - lng1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    crashes = [c for c in candidates if haversine_m(lat, lng, c.latitude, c.longitude) <= radius_m]

    total = len(crashes)
    a1 = sum(1 for c in crashes if c.severity == "A1")
    a2 = sum(1 for c in crashes if c.severity == "A2")
    a3 = sum(1 for c in crashes if c.severity == "A3")
    deaths = sum(c.death_count or 0 for c in crashes)
    injuries = sum(c.injury_count or 0 for c in crashes)
    # 2-30日內死亡人數加總（僅註記用；案件分類仍為 A2，不併入 deaths/死亡統計口徑）
    late_deaths = sum(c.late_death_count or 0 for c in crashes)
    # EPDO（台灣道安標準公式，人數口徑）：見 app/utils/epdo.py
    epdo = epdo_sum(crashes)

    by_year_counter = Counter(c.occurred_date.year for c in crashes)
    by_year = [{"year": y, "count": by_year_counter[y]} for y in sorted(by_year_counter.keys())]

    def top_n(values, n=None):
        """依出現次數由高到低排列（NULL/空值不計），n=None 表示回傳全部"""
        filtered = [v for v in values if v]
        return [{"name": k, "count": v} for k, v in Counter(filtered).most_common(n)]

    top_crash_types = top_n([c.crash_type for c in crashes], 5)
    top_causes = top_n([c.cause for c in crashes], 5)
    road_types = top_n([c.road_type for c in crashes])
    signal_types = top_n([c.signal_type for c in crashes])
    by_weather = top_n([c.weather for c in crashes])

    NIGHT_SHIFTS = {"10", "11", "12", "01", "02", "03"}
    night_count = sum(1 for c in crashes if c.shift_id in NIGHT_SHIFTS)
    night_pct = round(night_count * 100 / total, 1) if total else 0.0

    lighting_issue_count = sum(
        1 for c in crashes
        if c.road_lighting == "有照明未開啟或故障" and c.shift_id in NIGHT_SHIFTS
    )

    shift_counter = Counter(c.shift_id for c in crashes)
    by_shift = [{"shift": f"{i:02d}", "count": shift_counter.get(f"{i:02d}", 0)} for i in range(1, 13)]

    elderly = sum(1 for c in crashes if c.is_elderly)
    youth = sum(1 for c in crashes if c.is_youth)
    dui = sum(1 for c in crashes if c.is_dui_crash_party)
    unlicensed = sum(1 for c in crashes if c.license_status and "無照" in c.license_status)
    pedestrian = sum(1 for c in crashes if c.party_type and ("行人" in c.party_type or c.party_type == "人"))
    hit_and_run = sum(1 for c in crashes if c.is_hit_and_run)

    sorted_cases = sorted(
        crashes,
        key=lambda c: (c.occurred_date, c.occurred_time or datetime.min),
        reverse=True,
    )[:200]
    cases = [{
        "date": c.occurred_date.isoformat(),
        "time": c.occurred_time.strftime("%H:%M") if c.occurred_time else "",
        "severity": c.severity,
        "crash_type": c.crash_type,
        "cause": c.cause,
        "deaths": c.death_count or 0,
        "injuries": c.injury_count or 0,
        "late_deaths": c.late_death_count or 0,  # 2-30日內死亡人數（僅註記用，不影響 severity 分類）
        "location": c.location_desc,
    } for c in sorted_cases]

    # === suggestions 規則引擎：依序檢查，符合即加入；全部不符合時加入預設項 ===
    suggestions = []

    # 規則 1：照明改善
    if night_pct >= 40 or lighting_issue_count >= 3:
        suggestions.append({
            "title": "照明改善",
            "reason": f"夜間事故占比 {night_pct}%、照明未開啟/故障 {lighting_issue_count} 件，建議會同養工單位檢視路燈配置與開啟時制",
        })

    # 規則 2：路口管制設施（無號誌占比 >=50% 且前二大事故型態含側撞/路口交岔撞）
    signal_total = sum(s["count"] for s in signal_types)
    no_signal_count = next((s["count"] for s in signal_types if s["name"] == "無號誌"), 0)
    no_signal_pct = round(no_signal_count * 100 / signal_total, 1) if signal_total else 0.0
    top2_type_names = [t["name"] for t in top_crash_types[:2]]
    matched_type = next((n for n in top2_type_names if n in ("側撞", "路口交岔撞")), None)
    if no_signal_pct >= 50 and matched_type:
        matched_count = next((t["count"] for t in top_crash_types if t["name"] == matched_type), 0)
        suggestions.append({
            "title": "路口管制設施",
            "reason": f"無號誌占 {no_signal_pct}%、以{matched_type}為主 {matched_count} 件，建議評估增設閃光號誌或停讓標誌標線",
        })

    # 規則 3：速度管理（追撞為首且速限眾數 >=60）
    if top_crash_types and top_crash_types[0]["name"] == "追撞":
        speed_limits = [c.speed_limit for c in crashes if c.speed_limit is not None]
        if speed_limits:
            speed_mode = Counter(speed_limits).most_common(1)[0][0]
            if speed_mode >= 60:
                suggestions.append({
                    "title": "速度管理",
                    "reason": f"以追撞為主 {top_crash_types[0]['count']} 件且速限 {speed_mode}km/h，建議評估測速執法或速限檢討",
                })

    # 規則 4：行人安全設施
    if pedestrian >= 3:
        suggestions.append({
            "title": "行人安全設施",
            "reason": f"行人事故 {pedestrian} 件，建議檢視行穿線、行人庇護與照明",
        })

    # 規則 5：防追撞宣導與執法（肇因前五名含「未保持行車安全距離」）
    following_distance_cause = next(
        (c for c in top_causes if "未保持行車安全距離" in c["name"]), None
    )
    if following_distance_cause:
        suggestions.append({
            "title": "防追撞宣導與執法",
            "reason": f"「未保持行車安全距離」為肇因 {following_distance_cause['count']} 件，建議加強防追撞宣導與科技執法",
        })

    # 規則 6：酒駕熱點攔查
    if dui >= 2:
        suggestions.append({
            "title": "酒駕熱點攔查",
            "reason": f"酒駕事故 {dui} 件，建議列入夜間攔檢點",
        })

    # 規則 7：都未觸發時的預設項
    if not suggestions:
        suggestions.append({
            "title": "持續觀察",
            "reason": "事故樣態分散，建議持續監測並優先加強執法見警率",
        })

    return {
        "center": {"lat": lat, "lng": lng, "radius_m": radius_m},
        "window": {"start_date": sd.isoformat(), "end_date": ed.isoformat()},
        "summary": {
            "total": total,
            "a1": a1,
            "a2": a2,
            "a3": a3,
            "deaths": deaths,
            "injuries": injuries,
            "late_deaths": late_deaths,  # 2-30日內死亡人數加總（僅註記；案件仍列A2，死亡統計採24hr口徑不含此數）
            "epdo": epdo,
            "by_year": by_year,
        },
        "patterns": {
            "top_crash_types": top_crash_types,
            "top_causes": top_causes,
            "road_types": road_types,
            "signal_types": signal_types,
            "night_count": night_count,
            "night_pct": night_pct,
            "lighting_issue_count": lighting_issue_count,
            "by_shift": by_shift,
            "by_weather": by_weather,
        },
        "involved": {
            "elderly": elderly,
            "youth": youth,
            "dui": dui,
            "unlicensed": unlicensed,
            "pedestrian": pedestrian,
            "hit_and_run": hit_and_run,
        },
        "cases": cases,
        "suggestions": suggestions,
    }


@router.get("/patrol-plan")
async def get_patrol_plan(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """勤務建議單（DDACTS 簡化版）。

    僅分析新化分局轄下 7 個轄區所，依「事故能量（EPDO）」找出每所前 3 高風險班別，
    並比對現有舉發張數，標記出 EPDO 高但取締密度偏低的「勤務缺口（gap）」，
    產出可直接排勤參考的建議文字。
    """
    try:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return {"error": "日期格式錯誤"}

    from collections import Counter, defaultdict

    # 僅分析這 7 個轄區所（清單寫死）
    PATROL_UNITS = [
        "新化派出所", "唪口派出所", "知義派出所", "那拔派出所",
        "山上分駐所", "左鎮分駐所", "岡林派出所",
    ]

    def shift_label(shift_id: str) -> str:
        """班別代碼轉時段文字，如 "01" -> "00-02時"（(int-1)*2 起，2 小時一段）"""
        n = int(shift_id)
        start_hour = (n - 1) * 2
        return f"{start_hour:02d}-{start_hour + 2:02d}時"

    def mode_value(values):
        """計算眾數（NULL/空值不計，無資料回傳 None）"""
        filtered = [v for v in values if v]
        if not filtered:
            return None
        return Counter(filtered).most_common(1)[0][0]

    def top_locations(values, n=2):
        """地點描述眾數前 n 名，排除「未知地點」"""
        filtered = [v for v in values if v and v != "未知地點"]
        return [{"location": k, "count": v} for k, v in Counter(filtered).most_common(n)]

    # 一次撈出 7 所在區間內的全部事故，於 Python 端依（單位, 班別）分組，
    # 避免對每個班別再各別查詢明細造成大量重複查詢。
    crashes = db.query(Crash).filter(
        Crash.sub_unit.in_(PATROL_UNITS),
        Crash.occurred_date >= sd,
        Crash.occurred_date <= ed,
    ).all()

    unit_shift_map: dict = defaultdict(list)
    for c in crashes:
        unit_shift_map[(c.sub_unit, c.shift_id)].append(c)

    units_result = []
    for unit in PATROL_UNITS:
        shift_stats = []
        shift_ids = sorted({sid for (u, sid) in unit_shift_map.keys() if u == unit})
        for shift_id in shift_ids:
            items = unit_shift_map[(unit, shift_id)]
            shift_stats.append({
                "shift_id": shift_id,
                "count": len(items),
                # EPDO（台灣道安標準公式，人數口徑）：見 app/utils/epdo.py
                "epdo": epdo_sum(items),
                "dui_count": sum(1 for c in items if c.is_dui_crash_party),
                "items": items,
            })

        # 依 epdo 前 3 班別，epdo 同分以 count 高者先
        shift_stats.sort(key=lambda s: (-s["epdo"], -s["count"]))
        top3 = shift_stats[:3]

        top_slots = []
        for s in top3:
            items = s["items"]
            top_crash_type = mode_value([c.crash_type for c in items])
            top_cause = mode_value([c.cause for c in items])
            hotspots = top_locations([c.location_desc for c in items])

            # 違規側：該所（unit_code 含該所名）該班區間內張數
            existing_tickets = db.query(func.count(Ticket.id)).filter(
                Ticket.unit_code.like(f"%{unit}%"),
                Ticket.shift_id == s["shift_id"],
                Ticket.violation_date >= sd,
                Ticket.violation_date <= ed,
            ).scalar() or 0

            # gap 標記：事故能量高但取締密度偏低（張數 < 件數*3）
            # 門檻改為 epdo>=15（新公式量級與舊 severity_weight 不同：
            # 一件單傷事故 EPDO=1*3.5+1=4.5，一件死亡事故=1*9.5+1=10.5；
            # 15 約略等於 3 件輕重傷亡事故的能量，對應舊門檻 10 的抓漏水準）
            is_gap = s["epdo"] >= 15 and existing_tickets < s["count"] * 3

            label = shift_label(s["shift_id"])
            if hotspots:
                suggestion = f"{label}於{hotspots[0]['location']}等熱點加強{top_crash_type or '交通'}防制勤務"
            else:
                suggestion = "加強巡邏見警率"
            if s["dui_count"] > 0:
                suggestion += "，並列入酒駕攔檢"

            top_slots.append({
                "shift_id": s["shift_id"],
                "shift_label": label,
                "crash_count": s["count"],
                "epdo": s["epdo"],
                "dui_count": s["dui_count"],
                "top_crash_type": top_crash_type,
                "top_cause": top_cause,
                "hotspots": hotspots,
                "existing_tickets": existing_tickets,
                "is_gap": is_gap,
                "suggestion": suggestion,
            })

        units_result.append({
            "unit": unit,
            "total_crashes": sum(s["count"] for s in shift_stats),
            "total_epdo": sum(s["epdo"] for s in shift_stats),
            "top_slots": top_slots,
        })

    units_result.sort(key=lambda u: -u["total_epdo"])

    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "units": units_result,
    }


# ============================================
# 明日風險預警（Phase 3 B2）
# ============================================
@router.get("/risk-forecast")
async def get_risk_forecast(
    target_date: str = Query(None, description="目標日期 YYYY-MM-DD（預設＝資料庫最新事故日+1天）"),
    db: Session = Depends(get_db),
):
    """明日風險預警：歷史頻率＋平滑演算法，找出（轄區所, 班別）明日風險最高組合。

    Recall 優先（本系統原則「寧可多攔不可漏網」）：
    - 分數 = 同星期幾歷史平均 EPDO * 0.7 + 全週歷史平均 EPDO * 0.3
      （樣本數小的組合用全週平均做平滑，避免單一極端值誤導）
    - per_unit_top 額外確保 7 所皆有預警項目，不因某所整體風險偏低而被 Top 10 排除。
    """
    from collections import Counter, defaultdict

    # 僅分析這 7 個轄區所（與 patrol-plan 一致）
    PATROL_UNITS = [
        "新化派出所", "唪口派出所", "知義派出所", "那拔派出所",
        "山上分駐所", "左鎮分駐所", "岡林派出所",
    ]

    def shift_label(shift_id: str) -> str:
        """班別代碼轉時段文字，如 "01" -> "00-02時"（(int-1)*2 起，2 小時一段）"""
        n = int(shift_id)
        start_hour = (n - 1) * 2
        return f"{start_hour:02d}-{start_hour + 2:02d}時"

    def mode_value(values):
        """計算眾數（NULL/空值不計，無資料回傳 None）"""
        filtered = [v for v in values if v]
        if not filtered:
            return None
        return Counter(filtered).most_common(1)[0][0]

    # 決定 target_date：預設＝DB 最新 occurred_date + 1 天
    max_crash_date = db.query(func.max(Crash.occurred_date)).scalar()
    if target_date:
        try:
            td = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            return {"error": "日期格式錯誤"}
    elif max_crash_date:
        td = max_crash_date + timedelta(days=1)
    else:
        td = datetime.now().date()

    target_weekday = td.weekday()
    weekday_labels = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
    weekday_label = weekday_labels[target_weekday]

    # 歷史窗：DB 全部事故，一次撈 7 所必要欄位，Python 端分組
    # death_count/late_death_count/injury_count：供 crash_epdo() 計算單案 EPDO 用
    crashes = db.query(
        Crash.occurred_date,
        Crash.shift_id,
        Crash.sub_unit,
        Crash.death_count,
        Crash.late_death_count,
        Crash.injury_count,
        Crash.cause,
        Crash.is_dui_crash_party,
    ).filter(
        Crash.sub_unit.in_(PATROL_UNITS),
    ).all()

    # 歷史涵蓋週數：(data_end - data_start).days / 7，至少 1
    dates = [c.occurred_date for c in crashes if c.occurred_date]
    if dates:
        data_start, data_end = min(dates), max(dates)
        n_weeks = max(1, (data_end - data_start).days / 7)
    else:
        n_weeks = 1

    # 依 (unit, shift_id) 分組，組內再拆「同星期幾」子集
    group_all: dict = defaultdict(list)
    for c in crashes:
        group_all[(c.sub_unit, c.shift_id)].append(c)

    combo_results = []
    for (unit, shift_id), items in group_all.items():
        same_dow = [c for c in items if c.occurred_date.weekday() == target_weekday]

        # EPDO（台灣道安標準公式，人數口徑）：見 app/utils/epdo.py
        same_dow_epdo = epdo_sum(same_dow)
        all_epdo = epdo_sum(items)

        same_dow_rate = same_dow_epdo / n_weeks
        all_dow_rate = all_epdo / (n_weeks * 7)

        score = same_dow_rate * 0.7 + all_dow_rate * 0.3

        samples = len(same_dow)
        avg_epdo = same_dow_epdo / max(1, samples)
        top_cause = mode_value([c.cause for c in same_dow])
        dui_count = sum(1 for c in same_dow if c.is_dui_crash_party)

        combo_results.append({
            "unit": unit,
            "shift_id": shift_id,
            "shift_label": shift_label(shift_id),
            "score": round(score, 2),
            "samples": samples,
            "avg_epdo": round(avg_epdo, 1),
            "top_cause": top_cause,
            "dui_count": dui_count,
        })

    # Top 10 依 score 降冪
    combo_results.sort(key=lambda r: -r["score"])
    top_risks = combo_results[:10]

    # per_unit_top：每所 score 最高的 1 筆（確保 7 所都有預警，Recall 優先）
    per_unit_top = []
    for unit in PATROL_UNITS:
        unit_combos = [r for r in combo_results if r["unit"] == unit]
        if unit_combos:
            best = max(unit_combos, key=lambda r: r["score"])
            per_unit_top.append(best)

    return {
        "target_date": td.isoformat(),
        "weekday_label": weekday_label,
        "history_weeks": round(n_weeks, 1),
        "top_risks": top_risks,
        "per_unit_top": per_unit_top,
    }


# ============================================
# 專區共通強化：當事者特徵剖析（泛用，跨主題）
# ============================================
@router.get("/profile")
async def get_topic_profile(
    topic: str = Query(..., description="主題代碼：elderly/pedestrian/evehicle/dui/heavy"),
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """當事者特徵剖析（泛用）。

    依 topic 篩選查詢期間內的事故，於 Python 端統計年齡層/性別/車種/事故類型/
    保護裝備/駕照狀態/班別/熱門路線等分佈，供各專區（高齡、行人、微電車、酒駕、
    大型車）共用同一套剖析卡片。
    """
    try:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return {"error": "日期格式錯誤"}

    topic_condition = crash_topic_filter(topic)
    if topic_condition is None:
        return {"error": "未知主題"}

    from collections import Counter

    crashes = db.query(Crash).filter(
        topic_condition,
        Crash.occurred_date >= sd,
        Crash.occurred_date <= ed,
    ).all()

    total = len(crashes)

    # 年齡層：固定順序，0 也列出
    AGE_ORDER = ["<18", "18-24", "25-44", "45-64", "65+", "未知"]
    age_counter = Counter((c.driver_age_group or "未知") for c in crashes)
    age_groups = [{"name": k, "count": age_counter.get(k, 0)} for k in AGE_ORDER]

    # 性別：固定三項（男/女/未知，NULL 併入未知）
    gender_counter = Counter((c.driver_gender or "未知") for c in crashes)
    gender = [
        {"name": k, "count": gender_counter.get(k, 0)}
        for k in ["男", "女", "未知"]
    ]

    def top_n(values, n=8):
        """依出現次數由高到低排列（NULL/空值不計）"""
        filtered = [v for v in values if v]
        return [{"name": k, "count": v} for k, v in Counter(filtered).most_common(n)]

    party_types = top_n([c.party_type for c in crashes], 8)
    crash_types = top_n([c.crash_type for c in crashes], 8)
    protective_gear = top_n([c.protective_gear for c in crashes], None)
    license_status = top_n([c.license_status for c in crashes], None)

    # 班別：12 班全列，含 0
    shift_counter = Counter(c.shift_id for c in crashes)
    by_shift = [{"shift": f"{i:02d}", "count": shift_counter.get(f"{i:02d}", 0)} for i in range(1, 13)]

    # 熱門路線：top5，route_name 非空
    top_routes = top_n([c.route_name for c in crashes], 5)

    return {
        "topic": topic,
        "period": {"start_date": start_date, "end_date": end_date},
        "total": total,
        "groups": {
            "age_groups": age_groups,
            "gender": gender,
            "party_types": party_types,
            "crash_types": crash_types,
            "protective_gear": protective_gear,
            "license_status": license_status,
            "by_shift": by_shift,
            "top_routes": top_routes,
        },
    }


# ============================================
# 專區共通強化：青少年微電車校園時段熱區
# ============================================
@router.get("/school-zone-hotspots")
async def get_school_zone_hotspots(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """青少年微電車校園時段熱區。

    篩選期間內「青少年（<18歲）+ 微電車/慢車」事故，分別統計上學時段（06-08時，
    shift_id="04"）與放學時段（16-18時，shift_id="09"）的地點熱區，
    供校園周邊巡查排點參考；另附非上下學時段件數作對照。
    """
    try:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return {"error": "日期格式錯誤"}

    from collections import Counter

    MORNING_SHIFT = "04"   # 06:00-08:00 上學時段
    AFTERNOON_SHIFT = "09"  # 16:00-18:00 放學時段

    crashes = db.query(Crash).filter(
        Crash.evehicle_type.isnot(None),
        Crash.is_youth == True,
        Crash.occurred_date >= sd,
        Crash.occurred_date <= ed,
    ).all()

    youth_total = len(crashes)

    def build_period(items):
        """給定該時段的事故清單，統計 total 與 location_desc 眾數 top5（排除未知地點）"""
        total = len(items)
        location_counter = Counter(
            c.location_desc for c in items if c.location_desc and c.location_desc != "未知地點"
        )
        hotspots = []
        for location, count in location_counter.most_common(5):
            district_counter = Counter(
                c.district for c in items if c.location_desc == location and c.district
            )
            district_mode = district_counter.most_common(1)[0][0] if district_counter else None
            hotspots.append({"location": location, "count": count, "district": district_mode})
        return {"total": total, "hotspots": hotspots}

    morning_items = [c for c in crashes if c.shift_id == MORNING_SHIFT]
    afternoon_items = [c for c in crashes if c.shift_id == AFTERNOON_SHIFT]
    other_items = [c for c in crashes if c.shift_id not in (MORNING_SHIFT, AFTERNOON_SHIFT)]

    morning = build_period(morning_items)
    morning["label"] = "上學時段 06-08時"
    afternoon = build_period(afternoon_items)
    afternoon["label"] = "放學時段 16-18時"

    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "morning": morning,
        "afternoon": afternoon,
        "other_total": len(other_items),
        "youth_total": youth_total,
    }
