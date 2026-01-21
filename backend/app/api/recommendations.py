"""
推薦系統 API - Top 5 精準執法建議
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, case
from typing import Optional, List
from datetime import datetime, timedelta

from app.database import get_db
from app.models.core import Ticket, Crash
from app.models.dimension import Site

router = APIRouter()


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
    db: Session = Depends(get_db)
):
    """事故熱點分析"""
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
        func.sum(case((Crash.suspected_alcohol == True, 1), else_=0)).label('dui_crashes')
    ).filter(
        *filters
    ).group_by(Crash.district).order_by(desc('severity_score')).all()
    
    hotspots = []
    a1_total = a2_total = a3_total = dui_crash_total = 0
    
    for district, total, a1, a2, a3, severity_score, dui_crashes in crash_stats:
        if not district:
            continue
        
        # 標準化區域名稱
        normalized_district = normalize_district(district)
        district_variants = get_district_variants(district)
        
        a1 = a1 or 0
        a2 = a2 or 0
        a3 = a3 or 0
        dui_crashes = dui_crashes or 0
        a1_total += a1
        a2_total += a2
        a3_total += a3
        dui_crash_total += dui_crashes
        
        violation_stats = db.query(
            func.count(Ticket.id).label('total_violations'),
            func.sum(case((Ticket.topic_dui == True, 1), else_=0)).label('dui'),
            func.sum(case((Ticket.topic_red_light == True, 1), else_=0)).label('red_light'),
            func.sum(case((Ticket.topic_dangerous == True, 1), else_=0)).label('dangerous')
        ).filter(
            Ticket.violation_date >= start_date,
            Ticket.violation_date <= end_date,
            Ticket.district.in_(district_variants)  # 匹配兩種格式
        ).first()
        
        violation_counts = {
            'DUI': violation_stats.dui or 0,
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
                'severity_score': severity_score or 0
            },
            'violations': {
                'total': violation_stats.total_violations or 0,
                'dui': violation_stats.dui or 0,
                'dui_no_crash': (violation_stats.dui or 0) - dui_crashes,  # 酒駕無肇事
                'red_light': violation_stats.red_light or 0,
                'dangerous_driving': violation_stats.dangerous or 0
            },
            'dui_stats': {
                'total_dui': violation_stats.dui or 0,
                'dui_with_crash': dui_crashes,  # 酒駕有肇事
                'dui_no_crash': max(0, (violation_stats.dui or 0) - dui_crashes)  # 酒駕無肇事告發
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
            'dui_crash_total': dui_crash_total,
            'total_dui_violations': sum(h['violations']['dui'] for h in hotspots)
        }
    }


@router.get("/accidents/peak-times/{district}")
async def get_accident_peak_times(
    district: str,
    days: int = Query(30, ge=1, le=365, description="統計天數"),
    is_elderly: Optional[bool] = Query(False, description="是否僅統計高齡者事故"),
    db: Session = Depends(get_db)
):
    """特定區域的時段分布分析"""
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
        Ticket.topic_dui == True
    ).group_by(Ticket.shift_id).all()
    
    crash_dict = {s.shift_id: s.count for s in crash_by_shift}
    violation_dict = {s.shift_id: s.count for s in violation_by_shift}
    dui_dict = {s.shift_id: s.count for s in dui_by_shift}
    
    shifts = []
    for shift_id in sorted(shift_names.keys()):
        accidents = crash_dict.get(shift_id, 0)
        violations = violation_dict.get(shift_id, 0)
        dui_citations = dui_dict.get(shift_id, 0)
        shifts.append({
            'shift_id': shift_id,
            'time_range': shift_names[shift_id],
            'accidents': accidents,
            'violations': violations,
            'dui_citations': dui_citations
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
    db: Session = Depends(get_db)
):
    """事故與違規交叉分析"""
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
    db: Session = Depends(get_db)
):
    """
    高齡者車種分析
    分析高齡者事故中的車種分佈（機車、行人、自小客等）
    """
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
        Crash.suspected_alcohol == True,
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date,
        Crash.weather.isnot(None)
    ).group_by(Crash.weather).order_by(desc('count')).all()
    
    # 光線分佈
    light_stats = db.query(
        Crash.light,
        func.count(Crash.id).label('count')
    ).filter(
        Crash.suspected_alcohol == True,
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date,
        Crash.light.isnot(None)
    ).group_by(Crash.light).order_by(desc('count')).all()
    
    # 總計
    total_dui = db.query(func.count(Crash.id)).filter(
        Crash.suspected_alcohol == True,
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


@router.get("/map/points")
async def get_map_points(
    days: int = Query(default=90, description="分析期間天數"),
    point_type: str = Query(default="all", description="資料類型: all, crash, ticket"),
    severity: str = Query(default=None, description="嚴重度篩選: A1, A2, A3"),
    topic: str = Query(default=None, description="主題篩選: DUI, RED_LIGHT, DANGEROUS_DRIVING"),
    db: Session = Depends(get_db)
):
    """
    取得地圖點位資料
    返回帶有真實座標的事故/違規資料供地圖顯示
    """
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
            Crash.shift_id,
            Crash.is_elderly,
            Crash.suspected_alcohol,
            Crash.party_type
        ).filter(
            Crash.occurred_date >= start_date,
            Crash.occurred_date <= end_date
        )
        
        if severity:
            crash_query = crash_query.filter(Crash.severity == severity)
        
        crashes = crash_query.all()
        result['summary']['total_crashes'] = len(crashes)
        
        for c in crashes:
            if c.latitude and c.longitude:
                result['crash_points'].append({
                    'id': c.id,
                    'lat': c.latitude,
                    'lng': c.longitude,
                    'district': c.district,
                    'location': c.location_desc,
                    'severity': c.severity,
                    'date': c.occurred_date.isoformat() if c.occurred_date else None,
                    'shift': c.shift_id,
                    'is_elderly': c.is_elderly,
                    'is_dui': c.suspected_alcohol,
                    'vehicle_type': c.party_type
                })
        result['summary']['crashes_with_coords'] = len(result['crash_points'])
    
    # 取得違規點位
    if point_type in ['all', 'ticket']:
        ticket_query = db.query(
            Ticket.id,
            Ticket.latitude,
            Ticket.longitude,
            Ticket.district,
            Ticket.location_desc,
            Ticket.topic_dui,
            Ticket.topic_red_light,
            Ticket.topic_dangerous,
            Ticket.violation_date,
            Ticket.shift_id,
            Ticket.is_elderly,
            Ticket.vehicle_type
        ).filter(
            Ticket.violation_date >= start_date,
            Ticket.violation_date <= end_date
        )
        
        if topic:
            if topic == 'DUI':
                ticket_query = ticket_query.filter(Ticket.topic_dui == True)
            elif topic == 'RED_LIGHT':
                ticket_query = ticket_query.filter(Ticket.topic_red_light == True)
            elif topic == 'DANGEROUS_DRIVING':
                ticket_query = ticket_query.filter(Ticket.topic_dangerous == True)
        
        tickets = ticket_query.all()
        result['summary']['total_tickets'] = len(tickets)
        
        for t in tickets:
            if t.latitude and t.longitude:
                # 判斷主題
                topic_name = None
                if t.topic_dui:
                    topic_name = 'DUI'
                elif t.topic_red_light:
                    topic_name = 'RED_LIGHT'
                elif t.topic_dangerous:
                    topic_name = 'DANGEROUS_DRIVING'
                
                result['ticket_points'].append({
                    'id': t.id,
                    'lat': t.latitude,
                    'lng': t.longitude,
                    'district': t.district,
                    'location': t.location_desc,
                    'topic': topic_name,
                    'date': t.violation_date.isoformat() if t.violation_date else None,
                    'shift': t.shift_id,
                    'is_elderly': t.is_elderly,
                    'vehicle_type': t.vehicle_type
                })
        result['summary']['tickets_with_coords'] = len(result['ticket_points'])
    
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


