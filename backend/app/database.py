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
        "evehicle_type": "VARCHAR(50)",
        "is_youth": "BOOLEAN DEFAULT 0",
        "is_underage_14": "BOOLEAN DEFAULT 0",
        # 酒駕新邏輯（事故表 ground truth）
        "drinking_code": "VARCHAR(2)",
        "party_subtype_code": "VARCHAR(10)",
        "is_dui_crash_party": "BOOLEAN DEFAULT 0",
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
