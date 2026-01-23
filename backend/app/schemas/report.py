from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import date

class StatComparison(BaseModel):
    current: int
    last_year: int
    change: int
    change_pct: float

class MonthlyTrend(BaseModel):
    month: str
    accidents: int
    tickets: int

class HotspotItem(BaseModel):
    rank: int
    location: str
    district: str
    count: int
    trend_pct: Optional[float] = None
    major_cause: Optional[str] = None # For accidents (e.g. "A1", "A2") or violations (e.g. "DUI")

class ReportPeriod(BaseModel):
    year: int
    month: int
    start_date: date
    end_date: date

class ReportSummary(BaseModel):
    """
    彙整給 AI 進行分析的所有統計數據結構
    """
    period: ReportPeriod
    
    # 總體指標
    overall_stats: Dict[str, StatComparison] # keys: "accidents", "tickets", "injuries", "deaths"
    
    # 趨勢數據 (過去 6-12 個月)
    trends: List[MonthlyTrend]
    
    # 熱點分析
    accident_hotspots: List[HotspotItem]
    violation_hotspots: List[HotspotItem]
    
    # 重點關注 (AI 提示用)
    focus_districts: List[str] # 事故增加最多的區域
    focus_causes: List[str] # 增加最多的違規/事故類型
