from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app.models.core import Crash, Ticket, AuditLog

router = APIRouter()

@router.post("/reset-database")
async def reset_database():
    """重置資料庫：刪除所有資料表並重新建立"""
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        return {"status": "success", "message": "資料庫已重置"}
    except Exception as e:
        # SQLite 鎖定問題可能導致此處失敗
        return {"status": "error", "message": str(e)}


@router.get("/data-quality")
async def get_data_quality(db: Session = Depends(get_db)):
    """資料品質總覽（Phase 1 C4）：像數據公司一樣把資料品質當產品管理。

    回傳事故/舉發兩側的涵蓋範圍、關鍵欄位完整率、
    以及 Phase 1 道路工程欄位的入庫率——匯入後一眼看出資料健康度。
    """
    def rate(count: int, total: int) -> float:
        return round(count * 100 / total, 1) if total else 0.0

    crash_total = db.query(func.count(Crash.id)).scalar() or 0
    ticket_total = db.query(func.count(Ticket.id)).scalar() or 0

    crash_range = db.query(func.min(Crash.occurred_date), func.max(Crash.occurred_date)).first()
    ticket_range = db.query(func.min(Ticket.violation_date), func.max(Ticket.violation_date)).first()

    def crash_nonnull(col) -> int:
        return db.query(func.count(Crash.id)).filter(col.isnot(None)).scalar() or 0

    gps_n = db.query(func.count(Crash.id)).filter(
        Crash.latitude.isnot(None), Crash.longitude.isnot(None)).scalar() or 0
    loc_unknown = db.query(func.count(Crash.id)).filter(Crash.location_desc == "未知地點").scalar() or 0
    age_unknown = db.query(func.count(Crash.id)).filter(Crash.driver_age_group == "未知").scalar() or 0

    severity_dist = dict(db.query(Crash.severity, func.count(Crash.id)).group_by(Crash.severity).all())
    by_year = [
        {"year": y, "crashes": c}
        for y, c in db.query(Crash.year, func.count(Crash.id)).group_by(Crash.year).order_by(Crash.year)
    ]

    # Phase 1 道路工程欄位入庫率（全選條件匯出才有值；低=該期間檔案非全選版）
    phase1_cols = {
        "speed_limit": Crash.speed_limit,
        "crash_type": Crash.crash_type,
        "road_type": Crash.road_type,
        "road_lighting": Crash.road_lighting,
        "signal_type": Crash.signal_type,
        "route_name": Crash.route_name,
        "license_status": Crash.license_status,
        "protective_gear": Crash.protective_gear,
    }
    phase1 = {name: {"count": crash_nonnull(col), "rate": rate(crash_nonnull(col), crash_total)}
              for name, col in phase1_cols.items()}

    return {
        "crash": {
            "total": crash_total,
            "date_range": [d.isoformat() if d else None for d in crash_range],
            "severity": severity_dist,
            "by_year": by_year,
            "gps_rate": rate(gps_n, crash_total),
            "sub_unit_rate": rate(crash_nonnull(Crash.sub_unit), crash_total),
            "weather_rate": rate(crash_nonnull(Crash.weather), crash_total),
            "location_unknown_rate": rate(loc_unknown, crash_total),
            "age_unknown_rate": rate(age_unknown, crash_total),
            "gender_rate": rate(crash_nonnull(Crash.driver_gender), crash_total),
        },
        "ticket": {
            "total": ticket_total,
            "date_range": [d.isoformat() if d else None for d in ticket_range],
        },
        # 兩側資料涵蓋落差：舉發側最新日期落後事故側 → 提醒補匯出舉發檔
        "coverage_gap_days": (
            (crash_range[1] - ticket_range[1]).days
            if crash_range[1] and ticket_range[1] else None
        ),
        "phase1_road_fields": phase1,
    }


@router.get("/audit-log")
async def get_audit_log(
    limit: int = Query(default=50, description="回傳筆數（夾在 1-200 之間）"),
    db: Session = Depends(get_db),
):
    """稽核軌跡查詢（Phase 3 C5）：依時間降冪回傳最近的系統操作紀錄。

    涵蓋兩類寫入來源：
    - main.py write_protect_middleware：非 GET 的 /api/v1/* 請求
    - auth.py login：login_success / login_failed
    """
    limit = max(1, min(limit, 200))

    rows = (
        db.query(AuditLog)
        .order_by(AuditLog.ts.desc())
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "ts": row.ts.isoformat() if row.ts else None,
                "action": row.action,
                "detail": row.detail,
                "status_code": row.status_code,
                "actor": row.actor,
            }
            for row in rows
        ]
    }
