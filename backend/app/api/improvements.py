"""
道路改善成效追蹤 API（Phase 3-A3）

提供道路改善措施的登記 CRUD，以及 before-after 成效評估。
成效評估方法論：
- 以「日均事故率」比較改善前後（而非總數），因 after 期間可能因資料未滿期而較短。
- 半徑內事故篩選採 bounding box 預過濾 + Haversine 精算（沿用 recommendations.py 的 site-dossier 模式）。
- 扣除「全轄區同期」事故率變化（baseline），緩解迴歸均值（regression-to-the-mean）
  與大環境趨勢（如整體車流、宣導成效）對單一點位判讀造成的干擾。
"""
import math
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import Improvement, Crash

router = APIRouter()


# ============================================
# 請求體 Schema
# ============================================
class ImprovementCreate(BaseModel):
    """新增道路改善措施登記的請求體"""

    title: str
    measure_type: str
    latitude: float
    longitude: float
    radius_m: Optional[int] = 200
    implemented_date: str  # YYYY-MM-DD
    description: Optional[str] = None
    source: Optional[str] = None


# ============================================
# 共用工具函式（沿用 recommendations.py 的 site-dossier 模式）
# ============================================
def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine 公式計算兩點間距離（公尺），供半徑精算過濾用"""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _crashes_in_radius(db: Session, lat: float, lng: float, radius_m: int, start_date, end_date) -> list:
    """bounding box 預過濾 + Haversine 精算，取得半徑內、日期區間內（含頭尾）的事故清單"""
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
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date,
    ).all()

    return [c for c in candidates if _haversine_m(lat, lng, c.latitude, c.longitude) <= radius_m]


def _period_stats(crashes: list) -> dict:
    """彙整某期間事故清單的 total/epdo/deaths/injuries"""
    return {
        "total": len(crashes),
        "epdo": sum(c.severity_weight or 0 for c in crashes),
        "deaths": sum(c.death_count or 0 for c in crashes),
        "injuries": sum(c.injury_count or 0 for c in crashes),
    }


def _pct_change(before_rate: float, after_rate: float) -> Optional[float]:
    """日均率變化百分比（以未四捨五入的原始日均率計算，僅結果取 1 位小數）；
    before_rate=0 時無法計算變化率，回傳 None。"""
    if before_rate == 0:
        return None
    return round((after_rate - before_rate) / before_rate * 100, 1)


# ============================================
# CRUD 端點
# ============================================
@router.post("/")
async def create_improvement(body: ImprovementCreate, db: Session = Depends(get_db)):
    """新增道路改善措施登記"""
    if not body.title or not body.title.strip():
        raise HTTPException(status_code=400, detail="title 不可為空")
    if not body.measure_type or not body.measure_type.strip():
        raise HTTPException(status_code=400, detail="measure_type 不可為空")
    if not (21.5 <= body.latitude <= 25.5):
        raise HTTPException(status_code=400, detail="latitude 超出台灣範圍（21.5~25.5）")
    if not (119 <= body.longitude <= 122.5):
        raise HTTPException(status_code=400, detail="longitude 超出台灣範圍（119~122.5）")

    try:
        impl_date = datetime.strptime(body.implemented_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="implemented_date 格式錯誤，需為 YYYY-MM-DD")

    # radius_m 夾在 50~1000 之間（非拒絕，直接夾住）
    radius_m = max(50, min(1000, body.radius_m or 200))

    row = Improvement(
        title=body.title,
        measure_type=body.measure_type,
        latitude=body.latitude,
        longitude=body.longitude,
        radius_m=radius_m,
        implemented_date=impl_date,
        description=body.description,
        source=body.source,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {"success": True, "id": row.id}


@router.get("/")
async def list_improvements(db: Session = Depends(get_db)):
    """道路改善措施登記清單，依實施日期降冪排列"""
    rows = db.query(Improvement).order_by(Improvement.implemented_date.desc()).all()
    items = [
        {
            "id": r.id,
            "title": r.title,
            "measure_type": r.measure_type,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "radius_m": r.radius_m,
            "implemented_date": r.implemented_date.isoformat(),
            "description": r.description,
            "source": r.source,
        }
        for r in rows
    ]
    return {"items": items}


@router.delete("/{improvement_id}")
async def delete_improvement(improvement_id: int, db: Session = Depends(get_db)):
    """刪除道路改善措施登記"""
    row = db.query(Improvement).filter(Improvement.id == improvement_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="找不到該筆改善措施登記")

    db.delete(row)
    db.commit()
    return {"success": True}


# ============================================
# 成效評估（批次，核心功能）
# ============================================
@router.get("/evaluations")
async def get_evaluations(
    days: int = Query(365, ge=1, description="before/after 各自的基準天數"),
    db: Session = Depends(get_db),
):
    """
    批次計算所有道路改善登記點位的 before-after 成效評估。

    - before 期間：[實施日 - days, 實施日 - 1]
    - after 期間：[實施日, 實施日 + after_days - 1]，after_days 依資料庫最新事故日期自動縮短
      （資料不足 days 天時，after_days = min(days, 資料末日 - 實施日 + 1)）
    - 若 after_days <= 0（措施剛實施、尚無 after 資料），該筆回傳 status: "no_after_data"
    - net_pct 為扣除「全轄區同期」日均率變化後的淨效果，用以緩解迴歸均值與大環境趨勢干擾
    """
    data_end = db.query(func.max(Crash.occurred_date)).scalar()
    if data_end is None:
        return {"days": days, "data_end": None, "items": []}

    rows = db.query(Improvement).order_by(Improvement.implemented_date.desc()).all()

    items = []
    for r in rows:
        impl = r.implemented_date
        before_start = impl - timedelta(days=days)
        before_end = impl - timedelta(days=1)

        after_days = min(days, (data_end - impl).days + 1)
        if after_days <= 0:
            items.append({
                "id": r.id,
                "title": r.title,
                "measure_type": r.measure_type,
                "implemented_date": impl.isoformat(),
                "radius_m": r.radius_m,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "status": "no_after_data",
            })
            continue

        after_end = impl + timedelta(days=after_days - 1)

        # === 點位（半徑內）統計 ===
        before_crashes = _crashes_in_radius(db, r.latitude, r.longitude, r.radius_m, before_start, before_end)
        after_crashes = _crashes_in_radius(db, r.latitude, r.longitude, r.radius_m, impl, after_end)

        before_stats = _period_stats(before_crashes)
        after_stats = _period_stats(after_crashes)

        before_rate_raw = before_stats["total"] / days
        after_rate_raw = after_stats["total"] / after_days
        pct_change = _pct_change(before_rate_raw, after_rate_raw)

        before_epdo_rate_raw = before_stats["epdo"] / days
        after_epdo_rate_raw = after_stats["epdo"] / after_days
        epdo_pct_change = _pct_change(before_epdo_rate_raw, after_epdo_rate_raw)

        # === 全轄區同期控制（baseline，緩解迴歸均值與大環境趨勢）===
        baseline_before_total = db.query(func.count(Crash.id)).filter(
            Crash.occurred_date >= before_start, Crash.occurred_date <= before_end
        ).scalar() or 0
        baseline_after_total = db.query(func.count(Crash.id)).filter(
            Crash.occurred_date >= impl, Crash.occurred_date <= after_end
        ).scalar() or 0

        baseline_before_rate_raw = baseline_before_total / days
        baseline_after_rate_raw = baseline_after_total / after_days
        baseline_pct = _pct_change(baseline_before_rate_raw, baseline_after_rate_raw)

        net_pct = (
            round(pct_change - baseline_pct, 1)
            if pct_change is not None and baseline_pct is not None
            else None
        )

        preliminary = after_days < 90

        # === verdict 判讀（繁中一句話）===
        if net_pct is None:
            verdict = "資料不足，尚無法評估"
        elif net_pct <= -30:
            verdict = f"顯著改善：扣除全區趨勢後事故率下降 {abs(net_pct):.0f}%"
        elif net_pct <= -10:
            verdict = f"初步改善：淨下降 {abs(net_pct):.0f}%"
            if preliminary:
                verdict = f"（初期）{verdict}"
        elif net_pct < 10:
            verdict = "無明顯變化，建議持續觀察"
        else:
            verdict = f"事故率不降反升（淨 +{net_pct:.0f}%），建議回會勘檢視措施有效性"

        items.append({
            "id": r.id,
            "title": r.title,
            "measure_type": r.measure_type,
            "implemented_date": impl.isoformat(),
            "radius_m": r.radius_m,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "before": {
                **before_stats,
                "days": days,
                "daily_rate": round(before_rate_raw, 4),
            },
            "after": {
                **after_stats,
                "days": after_days,
                "daily_rate": round(after_rate_raw, 4),
            },
            "pct_change": pct_change,
            "baseline_pct": baseline_pct,
            "net_pct": net_pct,
            "epdo_pct_change": epdo_pct_change,
            "preliminary": preliminary,
            "verdict": verdict,
        })

    return {"days": days, "data_end": data_end.isoformat(), "items": items}
