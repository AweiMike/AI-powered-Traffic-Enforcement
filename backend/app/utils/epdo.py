"""
EPDO（Equivalent Property Damage Only，財損當量）計算共用模組

=== 標準公式（機關交通組拍板，鐵則）===
單案 EPDO = 30日死亡人數 × 9.5 + 調整受傷人數 × 3.5 + 1

    30日死亡人數 = death_count（24hr 內死亡）+ late_death_count（2-30日死亡）
    調整受傷人數 = max(0, injury_count − late_death_count)
        → late_death_count 的人原本已計入 injury_count（受傷後於 2-30 日內死亡），
          若不扣除，同一人會同時被計入「死亡」與「受傷」兩個權重，重複計權。
    + 1 = 案件基底（PDO 當量，任何一件通報案件至少計 1 分）

注意：本模組計算的是「名為 epdo」的統計指標（Top10 排名、勤務建議、
AI 報告等）。Crash.severity_weight 欄位（A1=5/A2=3/A3=1）是另一套視覺化
權重體系（區域分析地圖點位、hotspots 內部 severity_score 等），維持不動、
不在本模組處理範圍內。
"""
from sqlalchemy import func, case

# 權重係數（道安標準，人數口徑）
EPDO_DEATH_WEIGHT = 9.5
EPDO_INJURY_WEIGHT = 3.5


def crash_epdo(c) -> float:
    """單案 EPDO（Python 端）。

    c：Crash ORM 物件、SQLAlchemy Row，或任何具備同名屬性
       （death_count / late_death_count / injury_count）的物件；
       亦支援同名 key 的 dict（如 hotspots.py 聚類用的 row dict）。
    三個欄位皆可能為 NULL，一律以 0 防禦。
    """
    if isinstance(c, dict):
        get = c.get
    else:
        get = lambda k, default=0: getattr(c, k, default)

    death = (get("death_count", 0) or 0)
    late_death = (get("late_death_count", 0) or 0)
    injury = (get("injury_count", 0) or 0)

    thirty_day_deaths = death + late_death
    adjusted_injuries = max(0, injury - late_death)

    return thirty_day_deaths * EPDO_DEATH_WEIGHT + adjusted_injuries * EPDO_INJURY_WEIGHT + 1


def epdo_sum(crashes) -> float:
    """多案 EPDO 加總（Python 端），round 1 位小數。"""
    total = sum(crash_epdo(c) for c in crashes)
    return round(total, 1)


def epdo_sql_sum():
    """SQLAlchemy 聚合表達式（SUM 版），供 SQL group query 用。

    回傳可再 .label(...) 的表達式，語意與 crash_epdo() 完全對應：
        SUM(30日死亡人數) * 9.5 + SUM(調整受傷人數) * 3.5 + COUNT(*) * 1

    SQLite 無 GREATEST()，受傷調整（max(0, injury-late)）改用 CASE WHEN 實作；
    NULL 防禦一律用 func.coalesce()。
    """
    from app.models.core import Crash

    death = func.coalesce(Crash.death_count, 0)
    late_death = func.coalesce(Crash.late_death_count, 0)
    injury = func.coalesce(Crash.injury_count, 0)

    thirty_day_deaths_sum = func.sum(death + late_death)
    adjusted_injury = case((injury > late_death, injury - late_death), else_=0)
    adjusted_injury_sum = func.sum(adjusted_injury)
    base_sum = func.count()  # 每案 +1（PDO 當量基底）

    return (
        thirty_day_deaths_sum * EPDO_DEATH_WEIGHT
        + adjusted_injury_sum * EPDO_INJURY_WEIGHT
        + base_sum
    )
