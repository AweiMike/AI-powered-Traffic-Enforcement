"""
配置設定
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # 專案資訊
    PROJECT_NAME: str = "精準執法儀表板系統"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    # 資料庫 - SQLite（無需安裝 PostgreSQL）
    DATABASE_URL: str = "sqlite:///./data/traffic_enforcement.db"
    # 注意：如果需要讓其他電腦連接，請使用絕對路徑
    # 例如：DATABASE_URL: str = "sqlite:///D:/Programming/精準執法儀表板系統/backend/data/traffic_enforcement.db"

    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # 安全
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # 除錯模式
    DEBUG: bool = True

    # 地理編碼 API (選用)
    GOOGLE_MAPS_API_KEY: str = ""
    MOI_ADDRESS_API_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
