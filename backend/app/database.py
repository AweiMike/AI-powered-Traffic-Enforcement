"""
資料庫連線設定
"""
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# 建立資料庫引擎
# SQLite 特別配置
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False}  # SQLite 需要此參數
    )
else:
    # PostgreSQL 配置
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )

# Session 工廠
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 類別
Base = declarative_base()


def get_db():
    """
    資料庫依賴注入
    用於 FastAPI 路由
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    初始化資料庫
    創建所有表格
    """
    # 導入所有模型以確保它們被註冊
    from app.models import core, dimension, aggregate

    Base.metadata.create_all(bind=engine)

    # EIS 欄位自動遷移：若既有資料庫缺少新欄位則自動補上
    _migrate_eis_columns()

    # 單位名稱正規化遷移：core_ticket.unit_code / core_crash.sub_unit 統一為短名
    _canonicalize_unit_names()

    print("[OK] Database tables ready")


def _migrate_eis_columns():
    """檢查並補上 EIS 整合所需的新欄位（不刪資料）"""
    inspector = inspect(engine)

    # core_crash 表需要的新欄位（EIS 整合 + 慢車分析 + 酒駕飲酒情形代碼）
    _ensure_columns(inspector, "core_crash", {
        "precinct": "VARCHAR(100)",
        "sub_unit": "VARCHAR(100)",
        "death_count": "INTEGER DEFAULT 0",
        "injury_count": "INTEGER DEFAULT 0",
        "late_death_count": "INTEGER DEFAULT 0",
        "evehicle_type": "VARCHAR(50)",
        "is_youth": "BOOLEAN DEFAULT 0",
        "is_underage_14": "BOOLEAN DEFAULT 0",
        # 酒駕新邏輯（事故表 ground truth）
        "drinking_code": "VARCHAR(2)",
        "party_subtype_code": "VARCHAR(10)",
        "is_dui_crash_party": "BOOLEAN DEFAULT 0",
        # 道路工程分析欄位（Phase 1，全選條件匯出）
        "speed_limit": "INTEGER",
        "crash_type": "VARCHAR(50)",
        "road_type": "VARCHAR(50)",
        "signal_type": "VARCHAR(50)",
        "road_lighting": "VARCHAR(50)",
        "route_name": "VARCHAR(50)",
        "route_km": "FLOAT",
        "license_status": "VARCHAR(30)",
        "protective_gear": "VARCHAR(30)",
        "is_hit_and_run": "BOOLEAN DEFAULT 0",
        "delivery_platform": "VARCHAR(50)",
        # 路口衝突方向引擎欄位（Wave 28）
        "side_impact_direction": "VARCHAR(50)",
        "conflict_action_pair": "VARCHAR(80)",
        "signal_action": "VARCHAR(20)",
        # 事故處理時效／道路恢復效率（Wave 30-1）＋ 停讓標誌（Wave 30-2）
        "response_minutes": "FLOAT",
        "clearance_minutes": "FLOAT",
        "has_yield_sign": "VARCHAR(4)",
    })

    # core_ticket 表可能缺少的欄位
    _ensure_columns(inspector, "core_ticket", {
        "evehicle_type": "VARCHAR(50)",
        "evehicle_violation": "VARCHAR(50)",
        "is_youth": "BOOLEAN DEFAULT 0",
        "enforcement_type": "VARCHAR(20)",
        "enforcement_subtype": "VARCHAR(50)",
    })


def _ensure_columns(inspector, table_name: str, columns: dict):
    """若表格存在但缺少指定欄位，執行 ALTER TABLE ADD COLUMN"""
    if table_name not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns(table_name)}
    with engine.connect() as conn:
        for col_name, col_type in columns.items():
            if col_name not in existing:
                conn.execute(text(
                    f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
                ))
                print(f"  [+] {table_name}.{col_name} ({col_type}) added")
        conn.commit()


def _canonicalize_unit_names():
    """單位名稱正規化遷移：core_ticket.unit_code / core_crash.sub_unit 統一為短名。

    背景：core_ticket.unit_code 舊資料帶分局前綴（如「新化分局唪口派出所」），
    core_crash.sub_unit 已是短名（「唪口派出所」）。酒駕/大型車成效頁「各單位
    績效明細」用 set(ticket鍵 ∪ crash鍵) 精確合併，字串不同就把同一派出所拆成
    兩列。統一為短名（全站 canonical 慣例）後該頁會自動癒合，不需改合併邏輯。

    冪等：值已是短名時 UPDATE 條件不會命中，第二次執行更新數為 0。
    表格或欄位不存在（全新 DB、尚未跑過 _migrate_eis_columns 等情境）安全跳過。
    失敗只印警告，絕不讓資料庫初始化/啟動失敗。
    """
    from app.utils.units import normalize_unit_name

    targets = [
        ("core_ticket", "unit_code", 50),
        ("core_crash", "sub_unit", 100),
    ]

    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        summary_parts = []

        with engine.connect() as conn:
            for table_name, col_name, max_len in targets:
                if table_name not in existing_tables:
                    continue
                existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
                if col_name not in existing_cols:
                    continue

                rows = conn.execute(text(
                    f"SELECT DISTINCT {col_name} FROM {table_name} WHERE {col_name} IS NOT NULL"
                )).fetchall()

                changed_values = 0
                changed_rows = 0
                for (old_value,) in rows:
                    new_value = normalize_unit_name(old_value)
                    if new_value is not None:
                        new_value = new_value[:max_len]
                    if new_value == old_value:
                        continue
                    result = conn.execute(
                        text(f"UPDATE {table_name} SET {col_name} = :new_value WHERE {col_name} = :old_value"),
                        {"new_value": new_value, "old_value": old_value},
                    )
                    changed_values += 1
                    changed_rows += result.rowcount or 0

                conn.commit()
                summary_parts.append(f"{table_name} 更新 {changed_values} 種值/{changed_rows} 筆")

        if summary_parts:
            print("[migrate] 單位名稱正規化: " + ", ".join(summary_parts))
        else:
            print("[migrate] 單位名稱正規化: 略過（表格/欄位不存在）")
    except Exception as e:
        print(f"[migrate][WARN] 單位名稱正規化失敗，已略過（不影響啟動）: {e}")
