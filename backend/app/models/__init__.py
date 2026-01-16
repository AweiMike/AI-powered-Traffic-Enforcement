"""
資料庫模型匯出

說明：
- core: 核心事實表（違規、事故）- 完全去識別化
- dimension: 維度表（點位、單位、班別等）- 無個資
- aggregate: 聚合統計表（預先計算）- 無個資
"""

# 核心事實表（完全去識別化）
from app.models.core import Crash, Ticket

# 維度表（無個資）
from app.models.dimension import Site, Unit, Shift, ViolationCode

# 聚合統計表（無個資）
from app.models.aggregate import (
    SiteMetrics,
    DailyStats,
    MonthlyStats,
    ShiftStats
)

__all__ = [
    # Core tables
    "Crash",
    "Ticket",

    # Dimension tables
    "Site",
    "Unit",
    "Shift",
    "ViolationCode",

    # Aggregate tables
    "SiteMetrics",
    "DailyStats",
    "MonthlyStats",
    "ShiftStats",
]
