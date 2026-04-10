"""
熱點分析 API - 事故與違規熱點排名、重疊率計算
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, case
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from math import radians, cos, sqrt

from app.database import get_db
from app.models.core import Crash, Ticket


router = APIRouter()


# ============================================
# Pydantic 模型
# ============================================

class HotspotItem(BaseModel):
    """單一熱點項目"""
    rank: int
    location: str
    district: str
    a1_count: int
    a2_count: int
    a3_count: int
    total: int
    trend_pct: Optional[float] = None  # 與基準期比較
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class HotspotResponse(BaseModel):
    """熱點分析回應"""
    period: dict
    baseline: Optional[dict] = None
    hotspots: List[HotspotItem]
    total_in_period: int


# ============================================
# GPS 聚類工具（100m 半徑）
# ============================================

# 台灣緯度 ~23°N 下的公尺換算
_DEG_LAT_TO_M = 111_320.0  # 1度緯度 ≈ 111,320m
_COS_23 = cos(radians(23.0))
_DEG_LNG_TO_M = 111_320.0 * _COS_23  # 1度經度 ≈ 102,470m

CLUSTER_RADIUS_M = 100  # 聚類半徑(公尺)


def _distance_m(lat1, lng1, lat2, lng2):
    """兩點間近似距離（公尺），適用於台灣小範圍"""
    dlat = (lat1 - lat2) * _DEG_LAT_TO_M
    dlng = (lng1 - lng2) * _DEG_LNG_TO_M
    return sqrt(dlat * dlat + dlng * dlng)


def _clean_district(district: str) -> str:
    """清理區域名稱，移除「市」前綴"""
    if district and district.startswith('市'):
        return district[1:]
    return district or "未知區"


def _pick_best_location(location_counts: dict) -> str:
    """
    從一組 location_desc -> count 中挑出最佳代表名稱。
    優先選含「/」的交叉路口描述（但其票數需 >= 最多單一名稱的 30%），
    否則選票數最多的名稱。
    """
    if not location_counts:
        return "未知地點"
    top_name = max(location_counts, key=location_counts.get)
    top_count = location_counts[top_name]
    # 找交叉路口中票數最多的
    intersections = {k: v for k, v in location_counts.items() if '/' in k}
    if intersections:
        best_inter = max(intersections, key=intersections.get)
        # 交叉路口票數夠多才優先選（至少佔最多單一名稱的 30%）
        if intersections[best_inter] >= top_count * 0.3:
            return best_inter
    return top_name


def cluster_crashes_by_gps(rows, radius_m=CLUSTER_RADIUS_M):
    """
    將事故記錄依 GPS 座標聚類。

    rows: list of dicts with keys: lat, lng, district, location_desc, severity
    returns: list of cluster dicts sorted by total desc
    """
    clusters = []  # each: {lat, lng, district, locations: {desc: count}, a1, a2, a3, total, ids: set}

    for row in rows:
        lat, lng = row['lat'], row['lng']
        if lat is None or lng is None:
            continue

        matched = None
        min_dist = radius_m + 1
        for c in clusters:
            d = _distance_m(lat, lng, c['lat'], c['lng'])
            if d < min_dist:
                min_dist = d
                matched = c

        if matched and min_dist <= radius_m:
            # 更新 cluster 中心為加權平均
            n = matched['total']
            matched['lat'] = (matched['lat'] * n + lat) / (n + 1)
            matched['lng'] = (matched['lng'] * n + lng) / (n + 1)
            matched['total'] += 1
            sev = row.get('severity', '')
            if sev == 'A1':
                matched['a1'] += 1
            elif sev == 'A2':
                matched['a2'] += 1
            else:
                matched['a3'] += 1
            loc = row.get('location_desc', '')
            matched['locations'][loc] = matched['locations'].get(loc, 0) + 1
            # district 取最常見
            matched['districts'][row['district']] = matched['districts'].get(row['district'], 0) + 1
        else:
            sev = row.get('severity', '')
            clusters.append({
                'lat': lat,
                'lng': lng,
                'districts': {row['district']: 1},
                'locations': {row.get('location_desc', ''): 1},
                'a1': 1 if sev == 'A1' else 0,
                'a2': 1 if sev == 'A2' else 0,
                'a3': 1 if sev != 'A1' and sev != 'A2' else 0,
                'total': 1,
            })

    # Sort by total descending
    clusters.sort(key=lambda c: c['total'], reverse=True)
    return clusters


class TicketHotspotItem(BaseModel):
    """違規熱點項目"""
    rank: int
    location: str
    district: str
    count: int
    topic: Optional[str] = None
    trend_pct: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


# ============================================
# 事故熱點 API
# ============================================

def _fetch_crash_rows(db, start_dt, end_dt, severity=None):
    """查詢指定日期範圍內的事故記錄，回傳 list of dicts"""
    query = db.query(
        Crash.latitude, Crash.longitude, Crash.district,
        Crash.location_desc, Crash.severity
    ).filter(
        and_(
            Crash.occurred_date >= start_dt,
            Crash.occurred_date <= end_dt,
            Crash.latitude.isnot(None),
            Crash.longitude.isnot(None),
        )
    )
    if severity == 'A1':
        query = query.filter(Crash.severity == 'A1')
    elif severity == 'A2':
        query = query.filter(Crash.severity == 'A2')
    elif severity == 'A1+A2':
        query = query.filter(Crash.severity.in_(['A1', 'A2']))

    return [
        {'lat': r.latitude, 'lng': r.longitude,
         'district': r.district or '', 'location_desc': r.location_desc or '',
         'severity': r.severity or ''}
        for r in query.all()
    ]


@router.get("/accident-hotspots", response_model=HotspotResponse)
async def get_accident_hotspots(
    year: Optional[int] = Query(default=None, description="年份 (若指定則忽略 days)"),
    month: Optional[int] = Query(default=None, ge=1, le=12, description="月份 (需配合 year)"),
    days: int = Query(default=30, description="分析期間天數 (若未指定 year/month)"),
    start_date: Optional[str] = Query(default=None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="結束日期 YYYY-MM-DD"),
    top_n: int = Query(default=10, ge=1, le=50, description="返回前 N 名"),
    severity: Optional[str] = Query(default=None, description="嚴重度篩選: A1, A2, A1+A2"),
    compare_baseline: bool = Query(default=True, description="是否比較去年同期"),
    db: Session = Depends(get_db)
):
    """
    取得事故熱點排名（GPS 100m 半徑聚類）

    - 以 GPS 座標方圓 100m 聚類，將地理位置相近的事故歸為同一熱點
    - 自動從聚類內的 location_desc 挑選最具代表性的路口名稱
    - 支援嚴重度篩選、去年同期趨勢比較
    """
    # 決定日期範圍 (優先 start_date/end_date > year/month > days)
    if start_date and end_date:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    elif year and month:
        import calendar
        _, last_day = calendar.monthrange(year, month)
        start_date = datetime(year, month, 1).date()
        end_date = datetime(year, month, last_day).date()
    else:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

    # 取得所有個別事故記錄並做 GPS 聚類
    rows = _fetch_crash_rows(db, start_date, end_date, severity)
    clusters = cluster_crashes_by_gps(rows)

    # 去年同期聚類（用於趨勢比較）
    baseline_clusters = []
    baseline_start = None
    baseline_end = None
    if compare_baseline:
        baseline_start = start_date.replace(year=start_date.year - 1)
        baseline_end = end_date.replace(year=end_date.year - 1)
        baseline_rows = _fetch_crash_rows(db, baseline_start, baseline_end, severity)
        baseline_clusters = cluster_crashes_by_gps(baseline_rows)

    # 組裝結果
    hotspots = []
    for i, c in enumerate(clusters[:top_n], 1):
        district = max(c['districts'], key=c['districts'].get)
        location = _pick_best_location(c['locations'])

        # 與去年同期比較：找 baseline 中距離最近的 cluster
        trend_pct = None
        if compare_baseline and baseline_clusters:
            best_bl = None
            best_dist = CLUSTER_RADIUS_M * 2  # 容許 200m 匹配
            for bl in baseline_clusters:
                d = _distance_m(c['lat'], c['lng'], bl['lat'], bl['lng'])
                if d < best_dist:
                    best_dist = d
                    best_bl = bl
            if best_bl and best_bl['total'] > 0:
                trend_pct = round((c['total'] - best_bl['total']) / best_bl['total'] * 100, 1)

        hotspots.append(HotspotItem(
            rank=i,
            location=_clean_district(location) if not location else location,
            district=_clean_district(district),
            a1_count=c['a1'],
            a2_count=c['a2'],
            a3_count=c['a3'],
            total=c['total'],
            trend_pct=trend_pct,
            latitude=round(c['lat'], 6),
            longitude=round(c['lng'], 6),
        ))

    # 總數
    total_in_period = db.query(func.count(Crash.id)).filter(
        and_(
            Crash.occurred_date >= start_date,
            Crash.occurred_date <= end_date
        )
    ).scalar() or 0

    return HotspotResponse(
        period={
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": days if not (year and month) else None,
            "year": year,
            "month": month
        },
        baseline={
            "start": baseline_start.isoformat(),
            "end": baseline_end.isoformat(),
            "type": "去年同期"
        } if compare_baseline and baseline_start else None,
        hotspots=hotspots,
        total_in_period=total_in_period
    )


# ============================================
# 違規熱點 API
# ============================================

@router.get("/ticket-hotspots")
async def get_ticket_hotspots(
    year: Optional[int] = Query(default=None, description="年份 (若指定則忽略 days)"),
    month: Optional[int] = Query(default=None, ge=1, le=12, description="月份 (需配合 year)"),
    days: int = Query(default=30, description="分析期間天數 (若未指定 year/month)"),
    start_date: Optional[str] = Query(default=None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="結束日期 YYYY-MM-DD"),
    top_n: int = Query(default=10, ge=1, le=50, description="返回前 N 名"),
    topic: Optional[str] = Query(default=None, description="主題篩選: DUI, RED_LIGHT, DANGEROUS"),
    db: Session = Depends(get_db)
):
    """
    取得違規熱點排名

    - 依地點聚合違規數量
    - 支援主題篩選（酒駕/闘紅燈/危駕）
    - 支援年月篩選或自訂日期區間
    """
    # 決定日期範圍 (優先 start_date/end_date > year/month > days)
    if start_date and end_date:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    elif year and month:
        import calendar
        _, last_day = calendar.monthrange(year, month)
        start_date = datetime(year, month, 1).date()
        end_date = datetime(year, month, last_day).date()
    else:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
    
    query = db.query(
        Ticket.district,
        Ticket.location_desc,
        func.count(Ticket.id).label('count'),
        func.avg(Ticket.latitude).label('avg_lat'),
        func.avg(Ticket.longitude).label('avg_lng')
    ).filter(
        and_(
            Ticket.violation_date >= start_date,
            Ticket.violation_date <= end_date,
            Ticket.location_desc.isnot(None),
            Ticket.location_desc != ''
        )
    )
    
    # 主題篩選
    topic_label = "全部"
    if topic == 'DUI':
        query = query.filter(Ticket.topic_dui == True)
        topic_label = "酒駕"
    elif topic == 'RED_LIGHT':
        query = query.filter(Ticket.topic_red_light == True)
        topic_label = "闘紅燈"
    elif topic == 'DANGEROUS':
        query = query.filter(Ticket.topic_dangerous == True)
        topic_label = "危險駕駛"
    
    results = query.group_by(
        Ticket.district, Ticket.location_desc
    ).order_by(
        desc('count')
    ).limit(top_n).all()

    hotspots = []
    for i, row in enumerate(results, 1):
        hotspots.append(TicketHotspotItem(
            rank=i,
            location=row.location_desc or "未知地點",
            district=_clean_district(row.district),
            count=row.count,
            topic=topic_label,
            latitude=row.avg_lat,
            longitude=row.avg_lng
        ))
    
    return {
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": days
        },
        "topic": topic_label,
        "hotspots": [h.dict() for h in hotspots]
    }


# ============================================
# 熱點重疊率分析 API
# ============================================

@router.get("/hotspot-overlap")
async def get_hotspot_overlap(
    days: int = Query(default=30, description="分析期間天數"),
    top_n: int = Query(default=10, description="取前 N 名熱點計算重疊"),
    db: Session = Depends(get_db)
):
    """
    計算事故熱點與各違規類別熱點的重疊率
    
    重疊率 = (事故熱點中同時是違規熱點的數量) / (事故熱點總數) * 100
    """
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    # 取得事故熱點 (Top N 地點)
    accident_hotspots = db.query(
        Crash.district,
        Crash.location_desc
    ).filter(
        and_(
            Crash.occurred_date >= start_date,
            Crash.occurred_date <= end_date,
            Crash.location_desc.isnot(None)
        )
    ).group_by(
        Crash.district, Crash.location_desc
    ).order_by(
        desc(func.count(Crash.id))
    ).limit(top_n).all()
    
    accident_locations = set(f"{r.district}|{r.location_desc}" for r in accident_hotspots)
    
    def get_ticket_hotspot_locations(topic_filter=None):
        """取得違規熱點位置集合"""
        q = db.query(
            Ticket.district,
            Ticket.location_desc
        ).filter(
            and_(
                Ticket.violation_date >= start_date,
                Ticket.violation_date <= end_date,
                Ticket.location_desc.isnot(None)
            )
        )
        
        if topic_filter == 'DUI':
            q = q.filter(Ticket.topic_dui == True)
        elif topic_filter == 'RED_LIGHT':
            q = q.filter(Ticket.topic_red_light == True)
        elif topic_filter == 'DANGEROUS':
            q = q.filter(Ticket.topic_dangerous == True)
        
        results = q.group_by(
            Ticket.district, Ticket.location_desc
        ).order_by(
            desc(func.count(Ticket.id))
        ).limit(top_n).all()
        
        return set(f"{r.district}|{r.location_desc}" for r in results)
    
    # 計算各主題重疊率
    dui_locations = get_ticket_hotspot_locations('DUI')
    red_light_locations = get_ticket_hotspot_locations('RED_LIGHT')
    dangerous_locations = get_ticket_hotspot_locations('DANGEROUS')
    all_ticket_locations = get_ticket_hotspot_locations(None)
    
    def calc_overlap(set_a, set_b):
        if len(set_a) == 0:
            return 0
        overlap = len(set_a.intersection(set_b))
        return round(overlap / len(set_a) * 100, 1)
    
    return {
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": days
        },
        "top_n": top_n,
        "accident_hotspot_count": len(accident_locations),
        "overlap_rates": {
            "accident_vs_all_tickets": calc_overlap(accident_locations, all_ticket_locations),
            "accident_vs_dui": calc_overlap(accident_locations, dui_locations),
            "accident_vs_red_light": calc_overlap(accident_locations, red_light_locations),
            "accident_vs_dangerous": calc_overlap(accident_locations, dangerous_locations)
        },
        "interpretation": generate_overlap_interpretation(
            calc_overlap(accident_locations, all_ticket_locations),
            calc_overlap(accident_locations, dui_locations)
        )
    }


def generate_overlap_interpretation(all_overlap: float, dui_overlap: float) -> str:
    """根據重疊率生成簡單解讀"""
    if all_overlap >= 70:
        return "事故與違規熱點高度重疊，執法地點與事故熱點對齊良好"
    elif all_overlap >= 40:
        return "事故與違規熱點中度重疊，建議檢視未覆蓋的事故熱點"
    else:
        return "事故與違規熱點重疊率偏低，建議重新評估執法熱點部署"


# ============================================
# A1 事故明細清單
# ============================================

@router.get("/a1-accident-list")
async def get_a1_accident_list(
    start_date: Optional[str] = Query(default=None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="結束日期 YYYY-MM-DD"),
    days: int = Query(default=365, description="分析期間天數 (若未指定日期區間)"),
    db: Session = Depends(get_db)
):
    """
    取得 A1 死亡事故明細清單（去識別化）

    回傳每筆 A1 事故的日期、地點、肇因等資訊，供分析使用
    """
    # 決定日期範圍
    if start_date and end_date:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
    else:
        ed = datetime.now().date()
        sd = ed - timedelta(days=days)

    results = db.query(Crash).filter(
        and_(
            Crash.severity == "A1",
            Crash.occurred_date >= sd,
            Crash.occurred_date <= ed,
        )
    ).order_by(Crash.occurred_date.desc()).all()

    items = []
    for r in results:
        district = r.district or "未知區"
        if district.startswith("市"):
            district = district[1:]

        items.append({
            "date": str(r.occurred_date),
            "time": r.occurred_time.strftime("%H:%M") if r.occurred_time else None,
            "district": district,
            "location": r.location_desc or "未知地點",
            "cause": r.cause or "未記載",
            "party_type": r.party_type or "未記載",
            "death_count": r.death_count or 0,
            "injury_count": r.injury_count or 0,
            "is_elderly": r.is_elderly or False,
            "precinct": r.precinct or "",
            "latitude": r.latitude,
            "longitude": r.longitude,
        })

    return {
        "period": {"start": str(sd), "end": str(ed)},
        "total": len(items),
        "items": items,
    }
