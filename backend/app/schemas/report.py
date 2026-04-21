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


class UnitStat(BaseModel):
    """派出所/單位的執法與事故數據"""
    unit: str
    crashes: int
    tickets: int


class ShiftStat(BaseModel):
    """班別統計（12 班制：01-12）"""
    shift_id: str
    accidents: int
    tickets: int


class ReportPeriod(BaseModel):
    year: int
    month: int
    start_date: date
    end_date: date
    # === 資料涵蓋狀態 ===
    is_partial: bool = False           # True 表示本期資料不完整（月份尚未結束或資料尚未匯入到月底）
    actual_end_date: Optional[date] = None   # 實際有資料的最後日期（若 is_partial）
    days_covered: int = 30             # 本期實際涵蓋天數
    comparison_note: Optional[str] = None  # 給 AI 看的比較說明文字


class ReportSummary(BaseModel):
    """
    彙整給 AI 進行分析的所有統計數據結構（Wave 7 擴充版）
    """
    period: ReportPeriod

    # === 總體指標 ===
    overall_stats: Dict[str, StatComparison]  # keys: "accidents", "tickets", "injuries", "deaths"

    # === 主題分類（三大執法主題）===
    topics: Dict[str, StatComparison]  # keys: "dui"（酒駕）, "red_light"（闖紅燈）, "dangerous"（危駕）

    # === 舉發子類型（8 種細分）===
    enforcement_subtypes: Dict[str, int]
    # keys: 攔舉-一般, 攔舉-肇事, 攔舉-慢行攤, 逕舉_一般, 逕舉_民眾檢舉,
    #        逕舉_標示單, 逕舉_拖吊, 逕舉_微電車

    # === 嚴重度細分 ===
    severity: Dict[str, int]  # keys: "A1", "A2", "A3"

    # === 各派出所/單位統計（Top 5）===
    unit_stats: List[UnitStat]

    # === 班別分析（12 班制）===
    shift_stats: List[ShiftStat]

    # === 專區指標 ===
    elderly_crashes: int        # 本期高齡者事故數
    elderly_tickets: int        # 本期高齡者違規數
    youth_crashes: int          # 青少年（<18）事故數
    heavy_vehicle_crashes: int  # 大型車涉事事故數

    # === 趨勢數據 ===
    trends: List[MonthlyTrend]

    # === 熱點分析 ===
    accident_hotspots: List[HotspotItem]
    violation_hotspots: List[HotspotItem]

    # === A1 死亡事故地點（工程改善必要檢討項）===
    # 警政實務規則：任何 A1 案件皆為「工程檢討必要重點」
    a1_locations: List[HotspotItem] = []

    # === AI 重點關注（自動偵測）===
    focus_districts: List[str]   # 事故增加最多的行政區
    focus_causes: List[str]      # 增加最多的違規/事故類型
