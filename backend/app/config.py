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
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost",
        "http://localhost:80",
        "http://10.128.44.65",
        "http://10.128.44.65:80",
        "http://10.128.44.65:5173",
        "http://10.128.44.65:8080",
    ]

    # 安全
    # SECRET_KEY 用於登入 token 簽章；正式環境請在 backend/.env 覆寫成自己的隨機值
    # （例：SECRET_KEY=<執行 python -c "import secrets;print(secrets.token_hex(32))" 產生>）
    SECRET_KEY: str = "xinhua-dashboard-2026-e7c1a9f4b3d8265f0a1c4e7b9d2f6083"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # 儀表板登入帳密（由後端驗證，不再硬編碼於前端；可在 backend/.env 覆寫）
    DASHBOARD_USERNAME: str = "xinhua"
    DASHBOARD_PASSWORD: str = "xinhua3736"

    # 除錯模式（True 會開啟 /docs 與 SQL echo；正式部署保持 False）
    DEBUG: bool = False

    # 地理編碼 API (選用)
    GOOGLE_MAPS_API_KEY: str = ""
    MOI_ADDRESS_API_KEY: str = ""

    # LLM 模型設定
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    CLAUDE_API_KEY: str = ""
    PRIMARY_LLM_PROVIDER: str = "openai" # openai, gemini, anthropic
    LLM_MODEL_NAME: str = "gpt-4-turbo" # or gemini-pro, claude-3-opus

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
