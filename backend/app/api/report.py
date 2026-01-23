from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.analytics_engine import AnalyticsEngine
from app.schemas.report import ReportSummary

router = APIRouter()

@router.get("/summary", response_model=ReportSummary)
async def get_report_summary(
    year: int = Query(..., description="年份"),
    month: int = Query(..., ge=1, le=12, description="月份"),
    db: Session = Depends(get_db)
):
    """
    獲取指定年月的 AI 報告分析摘要數據
    """
    try:
        engine = AnalyticsEngine(db)
        summary = engine.generate_report_summary(year, month)
        return summary
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate")
async def generate_ai_report(
    year: int = Query(..., description="年份"),
    month: int = Query(..., ge=1, le=12, description="月份"),
    db: Session = Depends(get_db)
):
    """
    生成完整的 AI 交通執法分析報告 (Markdown)
    
    - 聚合所有相關統計數據
    - 使用 LLM (GPT-4/Gemini) 進行分析
    - 返回 Markdown 格式報告與原始數據
    """
    try:
        from app.services.report_generator import ReportGeneratorService
        service = ReportGeneratorService(db)
        result = await service.generate_full_report(year, month)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
