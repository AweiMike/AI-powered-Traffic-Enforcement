from fastapi import APIRouter
from app.database import engine, Base

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
