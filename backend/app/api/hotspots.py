"""
熱點分析 API - 事故與違規熱點排名、重疊率計算
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, case
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from math import radians, cos, sqrt
import re

from app.database import get_db
from app.models.core import Crash, Ticket
from app.utils.epdo import crash_epdo
from app.utils.drug_drive import not_drug_filter
from app.api.enforcement import HEAVY_VEHICLE_KEYWORDS


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
    epdo: float = 0  # EPDO（台灣道安標準公式，人數口徑，見 app/utils/epdo.py）；Top10 排序鍵
    trend_pct: Optional[float] = None  # 與基準期比較（依 epdo 計算）
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # 路口衝突方向引擎（Wave 28）
    no_signal_pct: Optional[float] = None  # 無號誌案數 / signal_action 非空案數（分母0→None）
    top_conflict: Optional[str] = None  # 該叢集 side_impact_direction 眾數


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


def _collapse_self_pair(name: str) -> str:
    """EIS 偶有「中正路 / 中正路」同路自交寫法（同路段非路口），折疊為單路名顯示"""
    if '/' in name:
        parts = [p.strip() for p in name.split('/')]
        if len(parts) == 2 and parts[0] and parts[0] == parts[1]:
            return parts[0]
    return name


def _pick_best_location(location_counts: dict) -> str:
    """
    從一組 location_desc -> count 中挑出最佳代表名稱。
    優先選含「/」的交叉路口描述（但其票數需 >= 最多單一名稱的 30%），
    否則選票數最多的名稱。「A / A」同路自交寫法不算路口且顯示時折疊為單路名。
    """
    if not location_counts:
        return "未知地點"
    top_name = max(location_counts, key=location_counts.get)
    top_count = location_counts[top_name]
    # 找交叉路口中票數最多的（排除「A / A」同路自交假路口）
    intersections = {
        k: v for k, v in location_counts.items()
        if '/' in k and _collapse_self_pair(k) == k
    }
    if intersections:
        best_inter = max(intersections, key=intersections.get)
        # 交叉路口票數夠多才優先選（至少佔最多單一名稱的 30%）
        if intersections[best_inter] >= top_count * 0.3:
            return best_inter
    return _collapse_self_pair(top_name)


def cluster_crashes_by_gps(rows, radius_m=CLUSTER_RADIUS_M):
    """
    將事故記錄依 GPS 座標聚類。

    rows: list of dicts with keys: lat, lng, district, location_desc, severity,
          death_count, late_death_count, injury_count（供 epdo 累加用）
    returns: list of cluster dicts sorted by epdo desc（Top10 排序鍵，見 accident-hotspots）
    """
    clusters = []  # each: {lat, lng, district, locations: {desc: count}, a1, a2, a3, total, epdo, ids: set}

    for row in rows:
        lat, lng = row['lat'], row['lng']
        if lat is None or lng is None:
            continue

        # 單案 EPDO（台灣道安標準公式，人數口徑）：見 app/utils/epdo.py
        row_epdo = crash_epdo(row)

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
            matched['epdo'] += row_epdo
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
            # 路口衝突方向引擎（Wave 28）：號誌動作 / 衝突方向累計（向下相容，row 缺鍵時 get 回傳 None）
            sa = row.get('signal_action')
            if sa:
                matched['signal_action_counts'][sa] = matched['signal_action_counts'].get(sa, 0) + 1
            sid = row.get('side_impact_direction')
            if sid:
                matched['conflict_counts'][sid] = matched['conflict_counts'].get(sid, 0) + 1
        else:
            sev = row.get('severity', '')
            sa = row.get('signal_action')
            sid = row.get('side_impact_direction')
            clusters.append({
                'lat': lat,
                'lng': lng,
                'districts': {row['district']: 1},
                'locations': {row.get('location_desc', ''): 1},
                'a1': 1 if sev == 'A1' else 0,
                'a2': 1 if sev == 'A2' else 0,
                'a3': 1 if sev != 'A1' and sev != 'A2' else 0,
                'total': 1,
                'epdo': row_epdo,
                # 路口衝突方向引擎（Wave 28）：向下相容，row 無此鍵時累計為空 dict
                'signal_action_counts': {sa: 1} if sa else {},
                'conflict_counts': {sid: 1} if sid else {},
            })

    # 路口衝突方向引擎（Wave 28）：由累計分布導出每叢集摘要欄位
    # no_signal_pct：無號誌案數 / signal_action 非空案數（分母 0 → None）
    # top_conflict：side_impact_direction 眾數（無資料 → None）
    for c in clusters:
        sig_counts = c.get('signal_action_counts', {})
        sig_total = sum(sig_counts.values())
        c['no_signal_pct'] = round(sig_counts.get('無號誌', 0) / sig_total, 2) if sig_total else None
        conflict_counts = c.get('conflict_counts', {})
        c['top_conflict'] = max(conflict_counts, key=conflict_counts.get) if conflict_counts else None

    # 排序鍵改為 epdo 降冪（原為 total 降冪；財損案多但死傷少的路口不再壓過死傷路口）
    clusters.sort(key=lambda c: c['epdo'], reverse=True)
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

def _fetch_crash_rows(db, start_dt, end_dt, severity=None, dui_only: bool = False):
    """查詢指定日期範圍內的事故記錄，回傳 list of dicts。
    death_count/late_death_count/injury_count：供聚類後計算單案 EPDO 用（crash_epdo()）。
    dui_only：僅取酒駕肇事事故（Crash.is_dui_crash_party，案件層級 ground truth）。"""
    query = db.query(
        Crash.latitude, Crash.longitude, Crash.district,
        Crash.location_desc, Crash.severity,
        Crash.death_count, Crash.late_death_count, Crash.injury_count,
        Crash.signal_action, Crash.side_impact_direction,
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

    if dui_only:
        # 僅酒駕肇事熱點（精準執法理念：事故防制優先於取締績效，見本檔 accident-hotspots 說明）
        query = query.filter(Crash.is_dui_crash_party == True)

    return [
        {'lat': r.latitude, 'lng': r.longitude,
         'district': r.district or '', 'location_desc': r.location_desc or '',
         'severity': r.severity or '',
         'death_count': r.death_count, 'late_death_count': r.late_death_count,
         'injury_count': r.injury_count,
         # 路口衝突方向引擎（Wave 28）：號誌動作分流 / 主要衝突方向來源欄位
         'signal_action': r.signal_action, 'side_impact_direction': r.side_impact_direction}
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
    dui_only: bool = Query(default=False, description="僅酒駕事故（is_dui_crash_party）"),
    db: Session = Depends(get_db)
):
    """
    取得事故熱點排名（GPS 100m 半徑聚類）

    - 以 GPS 座標方圓 100m 聚類，將地理位置相近的事故歸為同一熱點
    - 自動從聚類內的 location_desc 挑選最具代表性的路口名稱
    - 排序依 EPDO（台灣道安標準公式，人數口徑，見 app/utils/epdo.py）降冪，
      而非單純件數，避免財損案多但死傷少的路口壓過死傷路口
    - 支援嚴重度篩選、去年同期趨勢比較（trend_pct 亦以 epdo 比較）
    - dui_only=True 時僅計酒駕肇事事故：精準執法理念（交通組原意）——
      取締熱點只反映警察常站的位置（自我強化偏差），肇事熱點才是真風險位置，
      執法部署應以事故防制為目的，而非取締績效
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
    rows = _fetch_crash_rows(db, start_date, end_date, severity, dui_only)
    clusters = cluster_crashes_by_gps(rows)

    # 去年同期聚類（用於趨勢比較）
    baseline_clusters = []
    baseline_start = None
    baseline_end = None
    if compare_baseline:
        baseline_start = start_date.replace(year=start_date.year - 1)
        baseline_end = end_date.replace(year=end_date.year - 1)
        baseline_rows = _fetch_crash_rows(db, baseline_start, baseline_end, severity, dui_only)
        baseline_clusters = cluster_crashes_by_gps(baseline_rows)

    # 組裝結果
    hotspots = []
    for i, c in enumerate(clusters[:top_n], 1):
        district = max(c['districts'], key=c['districts'].get)
        location = _pick_best_location(c['locations'])

        # 與去年同期比較：找 baseline 中距離最近的 cluster
        # trend_pct 改以 epdo 比較（原以 total 比較，財損案多寡會蓋掉死傷輕重的變化）
        trend_pct = None
        if compare_baseline and baseline_clusters:
            best_bl = None
            best_dist = CLUSTER_RADIUS_M * 2  # 容許 200m 匹配
            for bl in baseline_clusters:
                d = _distance_m(c['lat'], c['lng'], bl['lat'], bl['lng'])
                if d < best_dist:
                    best_dist = d
                    best_bl = bl
            if best_bl and best_bl['epdo'] > 0:
                trend_pct = round((c['epdo'] - best_bl['epdo']) / best_bl['epdo'] * 100, 1)

        hotspots.append(HotspotItem(
            rank=i,
            location=_clean_district(location) if not location else location,
            district=_clean_district(district),
            a1_count=c['a1'],
            a2_count=c['a2'],
            a3_count=c['a3'],
            total=c['total'],
            epdo=round(c['epdo'], 1),
            trend_pct=trend_pct,
            latitude=round(c['lat'], 6),
            longitude=round(c['lng'], 6),
            no_signal_pct=c.get('no_signal_pct'),
            top_conflict=c.get('top_conflict'),
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


# ============================================
# 執法錯位引擎（Wave 29）：事故熱區 vs 取締熱區雙榜對照
# ============================================
# 背景：事故 GPS 覆蓋率 100% → 走 GPS 100m 聚類；取締 GPS 覆蓋率僅約 19% → 不可聚類，
# 改走 district + location_desc 文字分組。雙榜以路名 token 交集比對（非 GPS 距離）。

TOPIC_LABELS = {"dui": "酒駕", "heavy": "大型車", "speed": "超速", "evehicle": "微電車"}

# 道路等級前綴（由長至短無關，逐一比對開頭）— _road_tokens 用於剝除路名前綴以歸一比對
_ROAD_PREFIXES = ("省道", "縣道", "區道", "鄉道", "市道")


_ADMIN_PREFIX_RE = re.compile(r"^[一-鿿]{1,3}[區里]")


def _road_tokens(name: str) -> set:
    """地點名稱 → 路名 token 集合。全形臺→台、剝行政區/村里前綴（新化區/榮和里，可連續）、
    剝「省道/縣道/區道/鄉道/市道」前綴、依「/」拆路口、去空白。
    例：「中山路 / 省道臺39線」→ {"中山路", "台39線"}；「左鎮區榮和里 臺20線23.9公里處」→ {"台20線23.9公里處"}
    （比對階段用包含判定，「台20線」可命中「台20線23.9公里處」——見 _tokens_hit）"""
    if not name:
        return set()
    tokens = set()
    normalized = name.replace("臺", "台")
    for part in normalized.split("/"):
        token = part.strip()
        # 剝行政區/村里前綴（取締側 location_desc 常帶「新化區」「左鎮區榮和里」，事故側不帶）
        while True:
            m = _ADMIN_PREFIX_RE.match(token)
            if not m:
                break
            token = token[m.end():].strip()
        for prefix in _ROAD_PREFIXES:
            if token.startswith(prefix):
                token = token[len(prefix):]
                break
        if token:
            tokens.add(token)
    return tokens


def _tokens_hit(a: set, b: set) -> set:
    """兩組路名 token 的命中集合：完全相等，或（≥3 字保護下）一方包含另一方。
    取締側常帶公里數/門牌尾綴（「台20線23.9公里處」），包含判定讓「台20線」可命中；
    ≥3 字下限避免過短 token 誤配。回傳命中的「較短代表名」集合。"""
    hits = set()
    for x in a:
        for y in b:
            if x == y:
                hits.add(x)
            elif len(x) >= 3 and x in y:
                hits.add(x)
            elif len(y) >= 3 and y in x:
                hits.add(y)
    return hits


def _topic_crash_filter(topic: str):
    """依主題回傳事故側 SQLAlchemy 篩選條件（dui/heavy/speed/evehicle）"""
    if topic == "dui":
        return Crash.is_dui_crash_party == True
    if topic == "heavy":
        return or_(*[Crash.party_type.ilike(f"%{kw}%") for kw in HEAVY_VEHICLE_KEYWORDS])
    if topic == "speed":
        return Crash.cause.like("%超速%")
    if topic == "evehicle":
        return Crash.evehicle_type.isnot(None) & (Crash.evehicle_type != "")
    return None


def _topic_ticket_filter(topic: str):
    """依主題回傳取締側 SQLAlchemy 篩選條件（dui/heavy/speed/evehicle）"""
    if topic == "dui":
        return and_(Ticket.topic_dui == True, not_drug_filter())
    if topic == "heavy":
        return or_(*[Ticket.vehicle_type.ilike(f"%{kw}%") for kw in HEAVY_VEHICLE_KEYWORDS])
    if topic == "speed":
        return Ticket.violation_name.like("%超速%")
    if topic == "evehicle":
        return Ticket.evehicle_type.isnot(None) & (Ticket.evehicle_type != "")
    return None


def _fetch_topic_crash_rows(db: Session, start_dt, end_dt, topic: str):
    """查詢指定日期範圍與主題（dui/heavy/speed/evehicle）且有 GPS 座標的事故記錄，
    回傳 list of dicts 供 cluster_crashes_by_gps 聚類使用（欄位比照 _fetch_crash_rows）。"""
    query = db.query(
        Crash.latitude, Crash.longitude, Crash.district,
        Crash.location_desc, Crash.severity,
        Crash.death_count, Crash.late_death_count, Crash.injury_count,
    ).filter(
        and_(
            Crash.occurred_date >= start_dt,
            Crash.occurred_date <= end_dt,
            Crash.latitude.isnot(None),
            Crash.longitude.isnot(None),
        ),
        _topic_crash_filter(topic),
    )
    return [
        {'lat': r.latitude, 'lng': r.longitude,
         'district': r.district or '', 'location_desc': r.location_desc or '',
         'severity': r.severity or '',
         'death_count': r.death_count, 'late_death_count': r.late_death_count,
         'injury_count': r.injury_count}
        for r in query.all()
    ]


def _match_hotspots(crash_hotspots: list, ticket_hotspots: list):
    """路名 token 交集比對事故熱區與取締熱區雙榜（純函式，無 DB 相依）。

    回傳 (matched, crash_only, ticket_only, overlap_rate)：
    - matched: [{"crash": ch, "tickets": [th, ...], "common_tokens": [...]}]
      對每個事故熱區，找出所有 token 交集非空的取締熱區
    - crash_only: 無任何配對的事故熱區（高事故低取締 → 移防目標）
    - ticket_only: 未被任何事故熱區配到的取締熱區（→ 檢討候選）
    - overlap_rate: len(matched) / len(crash_hotspots) * 100（事故榜空 → 0.0）
    """
    crash_token_sets = [_road_tokens(h["location"]) for h in crash_hotspots]
    ticket_token_sets = [_road_tokens(h["location"]) for h in ticket_hotspots]

    matched = []
    matched_ticket_idx = set()
    crash_only = []
    for ci, ch in enumerate(crash_hotspots):
        ct = crash_token_sets[ci]
        paired_tickets = []
        common_all = set()
        for ti, th in enumerate(ticket_hotspots):
            common = _tokens_hit(ct, ticket_token_sets[ti])
            if common:
                paired_tickets.append(th)
                matched_ticket_idx.add(ti)
                common_all |= common
        if paired_tickets:
            matched.append({
                "crash": ch,
                "tickets": paired_tickets,
                "common_tokens": sorted(common_all),
            })
        else:
            crash_only.append(ch)

    ticket_only = [th for ti, th in enumerate(ticket_hotspots) if ti not in matched_ticket_idx]
    overlap_rate = round(len(matched) / len(crash_hotspots) * 100, 1) if crash_hotspots else 0.0

    return matched, crash_only, ticket_only, overlap_rate


def _build_mismatch_suggestions(topic_label: str, crash_only: list, ticket_only: list, matched: list) -> list:
    """組裝移防建議（純函式，無 DB 相依）：
    crash_only 前 3 各一條 + ticket_only 前 2 合一條 + matched 第 1 名一條"""
    suggestions = []
    for h in crash_only[:3]:
        suggestions.append({
            "title": f"移入攔檢能量：{h['location']}",
            "reason": f"{topic_label}肇事熱區（{h['count']} 件/EPDO {h['epdo']}）目前不在取締熱區榜上，建議優先移設攔檢點",
        })
    if len(ticket_only) >= 2:
        t1, t2 = ticket_only[0], ticket_only[1]
        suggestions.append({
            "title": "檢討既有攔檢點配置",
            "reason": f"{t1['location']}（{t1['count']} 張）、{t2['location']}（{t2['count']} 張）取締量大但未對應肇事熱區，可評估將部分能量移往上述肇事熱區",
        })
    if matched:
        m0 = matched[0]
        ch0 = m0["crash"]
        ticket_count_sum = sum(t["count"] for t in m0["tickets"])
        suggestions.append({
            "title": f"布防正確：{ch0['location']}",
            "reason": f"肇事與取締熱區重合（{ch0['count']} 件/{ticket_count_sum} 張），維持並持續監測",
        })
    return suggestions


@router.get("/enforcement-mismatch")
async def get_enforcement_mismatch(
    topic: str = Query(..., description="dui|heavy|speed|evehicle"),
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="結束日期 YYYY-MM-DD"),
    top_n: int = Query(default=8, description="事故/取締熱區各取前 N 名"),
    db: Session = Depends(get_db),
):
    """
    執法錯位引擎（Wave 29）：四主題（酒駕/大型車/超速/微電車）事故熱區 vs 取締熱區雙榜對照。

    - 事故側 GPS 覆蓋率 100% → 走 GPS 100m 聚類（cluster_crashes_by_gps）
    - 取締側 GPS 覆蓋率僅約 19%，不可聚類 → 改走 district + location_desc 文字分組
    - 雙榜以路名 token 交集比對（_road_tokens），非 GPS 距離比對
    - crash_only：肇事熱區未見取締覆蓋（高事故低取締）→ 移防建議目標
    - ticket_only：取締熱區未對應肇事熱區 → 檢討候選
    - 精準執法理念：事故熱區反映真風險位置，取締熱區反映警力當前部署，兩者對照找出錯位
    """
    if topic not in TOPIC_LABELS:
        return {"error": f"不支援的 topic: {topic}（限 dui|heavy|speed|evehicle）"}

    try:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return {"error": "日期格式錯誤"}

    topic_label = TOPIC_LABELS[topic]

    # --- 事故熱區（GPS 聚類）---
    crash_n = db.query(func.count(Crash.id)).filter(
        Crash.occurred_date >= sd,
        Crash.occurred_date <= ed,
        _topic_crash_filter(topic),
    ).scalar() or 0

    crash_rows = _fetch_topic_crash_rows(db, sd, ed, topic)
    clusters = cluster_crashes_by_gps(crash_rows)

    crash_hotspots = []
    for i, c in enumerate(clusters[:top_n], 1):
        district = max(c['districts'], key=c['districts'].get)
        crash_hotspots.append({
            "rank": i,
            "location": _pick_best_location(c['locations']),
            "district": _clean_district(district),
            "count": c['total'],
            "epdo": round(c['epdo'], 1),
            "latitude": round(c['lat'], 6),
            "longitude": round(c['lng'], 6),
        })

    # --- 取締熱區（location_desc 文字分組；GPS 覆蓋率過低不可聚類）---
    ticket_rows = db.query(
        Ticket.district, Ticket.location_desc,
        func.count(Ticket.id).label('count'),
    ).filter(
        and_(
            Ticket.violation_date >= sd,
            Ticket.violation_date <= ed,
            Ticket.location_desc.isnot(None),
            Ticket.location_desc != "未知地點",
        ),
        _topic_ticket_filter(topic),
    ).group_by(
        Ticket.district, Ticket.location_desc,
    ).order_by(
        desc('count'),
    ).limit(top_n).all()

    ticket_hotspots = []
    for i, row in enumerate(ticket_rows, 1):
        ticket_hotspots.append({
            "rank": i,
            "location": row.location_desc or "未知地點",
            "district": _clean_district(row.district),
            "count": row.count,
        })

    # --- 路名 token 歸一比對（純函式，見 _match_hotspots）---
    matched, crash_only, ticket_only, overlap_rate = _match_hotspots(crash_hotspots, ticket_hotspots)

    # --- 樣本警語 ---
    if crash_n < 30:
        crash_sample_note = f"⚠ 事故樣本僅 {crash_n} 件，熱區分布僅供參考"
    else:
        crash_sample_note = f"事故樣本 {crash_n} 件"

    # --- 移防建議（純函式，見 _build_mismatch_suggestions）---
    suggestions = _build_mismatch_suggestions(topic_label, crash_only, ticket_only, matched)

    return {
        "topic": topic,
        "topic_label": topic_label,
        "period": {"start_date": start_date, "end_date": end_date},
        "crash_sample_note": crash_sample_note,
        "crash_hotspots": crash_hotspots,
        "ticket_hotspots": ticket_hotspots,
        "matched": matched,
        "crash_only": crash_only,
        "ticket_only": ticket_only,
        "overlap_rate": overlap_rate,
        "suggestions": suggestions,
    }
