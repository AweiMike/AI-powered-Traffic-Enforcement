from sqlalchemy.orm import Session
from app.services.analytics_engine import AnalyticsEngine
from app.services.llm_service import LLMService
from app.services.prompts import ReportPrompts
from app.schemas.report import ReportSummary
import json

class ReportGeneratorService:
    def __init__(self, db: Session):
        self.analytics = AnalyticsEngine(db)
        self.llm = LLMService()

    async def generate_full_report(self, year: int, month: int, api_key: str = None, provider: str = None, model_name: str = None) -> dict:
        """
        生成完整的 AI 分析報告
        """
        # 1. 獲取數據
        data: ReportSummary = self.analytics.generate_report_summary(year, month)
        
        # 2. 準備 Prompt
        system_prompt = ReportPrompts.SERVER_SYSTEM_PROMPT
        user_prompt = ReportPrompts.get_analysis_prompt(data)
        
        # 3. 呼叫 LLM
        # 這裡我們預期 LLM 返回 Markdown 格式的報告
        report_content = await self.llm.generate_text(
            system_prompt, 
            user_prompt,
            api_key=api_key,
            provider=provider,
            model_name=model_name
        )
        
        # 4. 回傳結果
        # 我們回傳結構化數據，將原始數據與 AI 報告分開，方便前端展示
        return {
            "period": {
                "year": year,
                "month": month
            },
            "raw_data": data, # 包含給 LLM 看的所有原始統計數據
            "ai_analysis": {
                "provider": self.llm.provider,
                "model": self.llm.model,
                "content": report_content # Markdown 格式的報告內文
            }
        }
