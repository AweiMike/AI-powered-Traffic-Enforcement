"""登入驗證 API

設計（內網儀表板的務實安全模型）：
- 帳密由後端驗證（config/.env），不再硬編碼於前端 bundle
- 登入成功回傳 HMAC token（SECRET_KEY 簽章，無狀態、無需資料庫）
- main.py 的寫入保護 middleware 以 verify_token 驗證非 GET 請求
- GET（唯讀統計，資料已去識別化）不強制 token，保留 #view 免登入模式
"""
import hashlib
import hmac

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings

router = APIRouter()


def make_token(username: str) -> str:
    """以 SECRET_KEY 對使用者名稱簽章產生 token（deterministic、無過期）"""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        f"dashboard-auth:{username}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_token(token: str) -> bool:
    """驗證 token 是否為合法簽章（constant-time 比較防 timing attack）"""
    if not token:
        return False
    expected = make_token(settings.DASHBOARD_USERNAME)
    return hmac.compare_digest(token, expected)


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(req: LoginRequest):
    """帳密驗證；成功回傳 X-Auth-Token 用的 token"""
    if (
        hmac.compare_digest(req.username, settings.DASHBOARD_USERNAME)
        and hmac.compare_digest(req.password, settings.DASHBOARD_PASSWORD)
    ):
        return {"success": True, "token": make_token(req.username)}
    raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
