"""
資料庫連線設定
"""
from sqlalchemy import create_engine
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
    print("✅ 資料庫表格創建完成")
