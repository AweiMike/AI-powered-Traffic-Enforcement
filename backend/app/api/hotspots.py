"""
熱點分析 API - 事故與違規熱點排名、重疊率計算
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, case
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

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

@router.get("/accident-hotspots", response_model=HotspotResponse)
async def get_accident_hotspots(
    year: Optional[int] = Query(default=None, description="年份 (若指定則忽略 days)"),
    month: Optional[int] = Query(default=None, ge=1, le=12, description="月份 (需配合 year)"),
    days: int = Query(default=30, description="分析期間天數 (若未指定 year/month)"),
    top_n: int = Query(default=10, ge=1, le=50, description="返回前 N 名"),
    severity: Optional[str] = Query(default=None, description="嚴重度篩選: A1, A2, A1+A2"),
    compare_baseline: bool = Query(default=True, description="是否比較去年同期"),
    db: Session = Depends(get_db)
):
    """
    取得事故熱點排名
    
    - 依地點聚合事故數量
    - 支援嚴重度篩選
    - 可比較去年同期趨勢
    - 支援年月篩選
    """
    # 決定日期範圍
    if year and month:
        # 使用指定年月
        import calendar
        _, last_day = calendar.monthrange(year, month)
        start_date = datetime(year, month, 1).date()
        end_date = datetime(year, month, last_day).date()
    else:
        # 使用 days 參數
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
    
    # 基礎查詢 - 使用正確的 case() 語法
    query = db.query(
        Crash.district,
        Crash.location_desc,
        func.sum(case((Crash.severity == 'A1', 1), else_=0)).label('a1_count'),
        func.sum(case((Crash.severity == 'A2', 1), else_=0)).label('a2_count'),
        func.sum(case((Crash.severity == 'A3', 1), else_=0)).label('a3_count'),
        func.count(Crash.id).label('total'),
        func.avg(Crash.latitude).label('avg_lat'),
        func.avg(Crash.longitude).label('avg_lng')
    ).filter(
        and_(
            Crash.occurred_date >= start_date,
            Crash.occurred_date <= end_date,
            Crash.location_desc.isnot(None),
            Crash.location_desc != ''
        )
    )
    
    # 嚴重度篩選
    if severity == 'A1':
        query = query.filter(Crash.severity == 'A1')
    elif severity == 'A2':
        query = query.filter(Crash.severity == 'A2')
    elif severity == 'A1+A2':
        query = query.filter(Crash.severity.in_(['A1', 'A2']))
    
    # 聚合與排序
    results = query.group_by(
        Crash.district, Crash.location_desc
    ).order_by(
        desc('total')
    ).limit(top_n).all()
    
    # 計算去年同期數據（用於趨勢比較）
    baseline_data = {}
    if compare_baseline:
        baseline_start = start_date.replace(year=start_date.year - 1)
        baseline_end = end_date.replace(year=end_date.year - 1)
        
        baseline_query = db.query(
            Crash.district,
            Crash.location_desc,
            func.count(Crash.id).label('total')
        ).filter(
            and_(
                Crash.occurred_date >= baseline_start,
                Crash.occurred_date <= baseline_end,
                Crash.location_desc.isnot(None)
            )
        ).group_by(Crash.district, Crash.location_desc).all()
        
        for row in baseline_query:
            key = f"{row.district}|{row.location_desc}"
            baseline_data[key] = row.total
    
    # 組裝結果 - 組合區域+地點顯示完整位置
    hotspots = []
    for i, row in enumerate(results, 1):
        key = f"{row.district}|{row.location_desc}"
        baseline_count = baseline_data.get(key, 0)
        
        trend_pct = None
        if compare_baseline and baseline_count > 0:
            trend_pct = round((row.total - baseline_count) / baseline_count * 100, 1)
        
        # 組合完整地點名稱：區域 + 路段
        full_location = row.location_desc or "未知地點"
        if row.district and row.location_desc and row.district not in row.location_desc:
            full_location = f"{row.district} {row.location_desc}"
        
        hotspots.append(HotspotItem(
            rank=i,
            location=full_location,
            district=row.district or "未知區",
            a1_count=row.a1_count or 0,
            a2_count=row.a2_count or 0,
            a3_count=row.a3_count or 0,
            total=row.total,
            trend_pct=trend_pct,
            latitude=row.avg_lat,
            longitude=row.avg_lng
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
            "start": (start_date.replace(year=start_date.year - 1)).isoformat(),
            "end": (end_date.replace(year=end_date.year - 1)).isoformat(),
            "type": "去年同期"
        } if compare_baseline else None,
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
    top_n: int = Query(default=10, ge=1, le=50, description="返回前 N 名"),
    topic: Optional[str] = Query(default=None, description="主題篩選: DUI, RED_LIGHT, DANGEROUS"),
    db: Session = Depends(get_db)
):
    """
    取得違規熱點排名
    
    - 依地點聚合違規數量
    - 支援主題篩選（酒駕/闘紅燈/危駕）
    - 支援年月篩選
    """
    # 決定日期範圍
    if year and month:
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
        # 組合完整地點名稱
        full_location = row.location_desc or "未知地點"
        if row.district and row.location_desc and row.district not in row.location_desc:
            full_location = f"{row.district} {row.location_desc}"
            
        hotspots.append(TicketHotspotItem(
            rank=i,
            location=full_location,
            district=row.district or "未知區",
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
