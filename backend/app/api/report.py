from fastapi import APIRouter, Depends, Query, HTTPException, Header
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import get_db

router = APIRouter()

@router.post("/generate")
async def generate_ai_report(
    # 模式 A：完整月份（向後相容）
    year: Optional[int] = Query(None, description="年份（與 month 搭配；若提供 start_date/end_date 則忽略）"),
    month: Optional[int] = Query(None, ge=1, le=12, description="月份"),
    # 模式 B：自訂區間（Wave 13 新增）
    start_date: Optional[str] = Query(None, description="自訂起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="自訂結束日期 YYYY-MM-DD"),
    # LLM 設定（Header 傳入，避免 Key 進 query log）
    x_llm_api_key: Optional[str] = Header(None, alias="X-LLM-API-KEY", description="使用者自訂 API Key"),
    x_llm_provider: Optional[str] = Header("openai", alias="X-LLM-PROVIDER", description="LLM 供應商"),
    x_llm_model: Optional[str] = Header(None, alias="X-LLM-MODEL", description="LLM 模型名稱"),
    db: Session = Depends(get_db),
):
    """
    生成完整的 AI 交通執法分析報告（Markdown）

    支援兩種期間模式（二擇一）：
    1. **完整月份**：傳入 year + month
    2. **自訂區間**：傳入 start_date + end_date（YYYY-MM-DD）
       適用情境：長官指定特定週期、活動期間、跨月分析

    - 自動聚合所有相關統計數據
    - 呼叫 LLM 進行分析（OpenAI / Anthropic / Gemini / Ollama / Mock）
    - 返回 Markdown 格式報告 + 原始數據
    - API Key 僅於 Header 傳遞，不儲存
    """
    # 解析日期參數
    start_dt = None
    end_dt = None
    if start_date and end_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
            if start_dt > end_dt:
                raise HTTPException(status_code=400, detail="start_date 不可晚於 end_date")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"日期格式錯誤（需 YYYY-MM-DD）：{e}")
    elif not (year and month):
        raise HTTPException(status_code=400, detail="必須提供 year+month 或 start_date+end_date")

    try:
        from app.services.report_generator import ReportGeneratorService
        service = ReportGeneratorService(db)
        result = await service.generate_full_report(
            year=year,
            month=month,
            start_date_param=start_dt,
            end_date_param=end_dt,
            api_key=x_llm_api_key,
            provider=x_llm_provider,
            model_name=x_llm_model,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
