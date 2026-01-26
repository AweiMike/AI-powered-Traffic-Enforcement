from fastapi import APIRouter, Depends, Query, HTTPException, Header
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
# ... (imports)

router = APIRouter()

@router.post("/generate")
async def generate_ai_report(
    year: int = Query(..., description="年份"),
    month: int = Query(..., ge=1, le=12, description="月份"),
    x_llm_api_key: Optional[str] = Header(None, alias="X-LLM-API-KEY", description="使用者自訂 API Key"),
    x_llm_provider: Optional[str] = Header("openai", alias="X-LLM-PROVIDER", description="LLM 供應商 (openai, gemini)"),
    x_llm_model: Optional[str] = Header(None, alias="X-LLM-MODEL", description="LLM 模型名稱"),
    db: Session = Depends(get_db)
):
    """
    生成完整的 AI 交通執法分析報告 (Markdown)
    
    - 聚合所有相關統計數據
    - 使用 LLM (GPT-4/Gemini) 進行分析
    - 返回 Markdown 格式報告與原始數據
    - **API Key 安全**：優先使用 Header 傳入的 Key，不儲存於後端。
    """
    try:
        from app.services.report_generator import ReportGeneratorService
        service = ReportGeneratorService(db)
        result = await service.generate_full_report(
            year=year, 
            month=month,
            api_key=x_llm_api_key,
            provider=x_llm_provider,
            model_name=x_llm_model
        )
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
