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
            'site_id': district,
            'site_name': district,
            'district': district,
            'latitude': coords[0],
            'longitude': coords[1],
            'ticket_count': ticket_count,
            'crash_count': crash_count,
            'vpi': round(vpi, 2),
            'cri': round(cri, 2),
            'score': round(score, 2),
            'rank': 0
        })
    
    recommendations.sort(key=lambda x: x['score'], reverse=True)
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
    
    top_districts = db.query(
        Ticket.district,
        func.count(Ticket.id).label('count')
    ).filter(and_(*conditions)).group_by(Ticket.district).order_by(desc('count')).limit(3).all()
    
    total_violations = db.query(func.count(Ticket.id)).filter(and_(*conditions)).scalar() or 0
    
    shift_names = {
        "01": "00:00-02:00", "02": "02:00-04:00", "03": "04:00-06:00",
        "04": "06:00-08:00", "05": "08:00-10:00", "06": "10:00-12:00",
        "07": "12:00-14:00", "08": "14:00-16:00", "09": "16:00-18:00",
        "10": "18:00-20:00", "11": "20:00-22:00", "12": "22:00-24:00"
    }
    
    topic_names = {
        "DUI": "酒駕",
        "RED_LIGHT": "闖紅燈",
        "DANGEROUS_DRIVING": "危險駕駛"
    }
    
    return {
        "date": target_date.isoformat(),
        "shift_id": shift_id,
        "shift_time": shift_names.get(shift_id, shift_id),
        "topic_code": topic_code,
        "topic_name": topic_names.get(topic_code, topic_code),
        "top_locations": [
            {"rank": i+1, "district": d, "count": c} 
            for i, (d, c) in enumerate(top_districts)
        ],
        "total_violations": total_violations,
        "recommendation": f"建議在{top_districts[0][0] if top_districts else '熱點區域'}加強{topic_names.get(topic_code, '')}取締"
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
    db: Session = Depends(get_db)
):
    """事故熱點分析"""
    end_date = get_data_end_date(db)
    start_date = end_date - timedelta(days=days)
    
    crash_stats = db.query(
        Crash.district,
        func.count(Crash.id).label('total'),
        func.sum(case((Crash.severity == 'A1', 1), else_=0)).label('a1_count'),
        func.sum(case((Crash.severity == 'A2', 1), else_=0)).label('a2_count'),
        func.sum(case((Crash.severity == 'A3', 1), else_=0)).label('a3_count'),
        func.sum(Crash.severity_weight).label('severity_score')
    ).filter(
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date,
        Crash.district.isnot(None)
    ).group_by(Crash.district).order_by(desc('severity_score')).all()
    
    hotspots = []
    a1_total = a2_total = a3_total = 0
    
    for district, total, a1, a2, a3, severity_score in crash_stats:
        if not district:
            continue
        
        a1 = a1 or 0
        a2 = a2 or 0
        a3 = a3 or 0
        a1_total += a1
        a2_total += a2
        a3_total += a3
        
        violation_stats = db.query(
            func.count(Ticket.id).label('total_violations'),
            func.sum(case((Ticket.topic_dui == True, 1), else_=0)).label('dui'),
            func.sum(case((Ticket.topic_red_light == True, 1), else_=0)).label('red_light'),
            func.sum(case((Ticket.topic_dangerous == True, 1), else_=0)).label('dangerous')
        ).filter(
            Ticket.violation_date >= start_date,
            Ticket.violation_date <= end_date,
            Ticket.district == district
        ).first()
        
        violation_counts = {
            'DUI': violation_stats.dui or 0,
            'RED_LIGHT': violation_stats.red_light or 0,
            'DANGEROUS_DRIVING': violation_stats.dangerous or 0
        }
        priority_topic = max(violation_counts, key=violation_counts.get) if any(violation_counts.values()) else None
        
        coords = DISTRICT_COORDINATES.get(district, DEFAULT_COORDS)
        enforcement_focus = "需要更多數據分析"
        if priority_topic:
            enforcement_focus = f"建議加強{TOPIC_NAMES.get(priority_topic, '')}取締"
        
        hotspots.append({
            'district': district,
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
                'red_light': violation_stats.red_light or 0,
                'dangerous_driving': violation_stats.dangerous or 0
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
            'a3_total': a3_total
        }
    }


@router.get("/accidents/peak-times/{district}")
async def get_accident_peak_times(
    district: str,
    days: int = Query(30, ge=1, le=365, description="統計天數"),
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
    
    crash_by_shift = db.query(
        Crash.shift_id,
        func.count(Crash.id).label('count')
    ).filter(
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date,
        Crash.district == district
    ).group_by(Crash.shift_id).all()
    
    violation_by_shift = db.query(
        Ticket.shift_id,
        func.count(Ticket.id).label('count')
    ).filter(
        Ticket.violation_date >= start_date,
        Ticket.violation_date <= end_date,
        Ticket.district == district
    ).group_by(Ticket.shift_id).all()
    
    crash_dict = {s.shift_id: s.count for s in crash_by_shift}
    violation_dict = {s.shift_id: s.count for s in violation_by_shift}
    
    shifts = []
    for shift_id in sorted(shift_names.keys()):
        accidents = crash_dict.get(shift_id, 0)
        violations = violation_dict.get(shift_id, 0)
        shifts.append({
            'shift_id': shift_id,
            'time_range': shift_names[shift_id],
            'accidents': accidents,
            'violations': violations
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
        crash_conditions.append(Crash.district == district)
    
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
        ticket_conditions.append(Ticket.district == district)
    
    ticket_stats = db.query(
        Ticket.district,
        Ticket.shift_id,
        func.count(Ticket.id).label('violations')
    ).filter(and_(*ticket_conditions)).group_by(Ticket.district, Ticket.shift_id).all()
    
    ticket_dict = {(t.district, t.shift_id): t.violations for t in ticket_stats}
    
    cross_analysis = []
    for c in crash_stats:
        violations = ticket_dict.get((c.district, c.shift_id), 0)
        gap = c.accidents - (violations * 0.1) if violations else c.accidents
        
        priority = 'LOW'
        if gap > 5:
            priority = 'HIGH'
        elif gap > 2:
            priority = 'MEDIUM'
        
        cross_analysis.append({
            'district': c.district,
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
