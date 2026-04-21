from sqlalchemy.orm import Session
from app.services.analytics_engine import AnalyticsEngine
from app.services.llm_service import LLMService
from app.services.prompts import ReportPrompts
from app.schemas.report import ReportSummary
import json
import re


def sanitize_markdown(content: str) -> str:
    """
    清理 LLM 可能回傳的非標準 Markdown 格式問題。
    即使 prompt 寫明禁用，部分模型（如 Gemini Flash）仍偶爾會：
    - 使用 HTML heading tags (<h1>...<h6>)
    - 使用 <strong>, <br>, <p> 等 HTML 標籤
    - 包 ```markdown ... ``` 外層 code fence
    此 sanitizer 是防線最後一關，確保前端 ReactMarkdown 能一致渲染。
    """
    if not content:
        return content

    # 移除外層 ```markdown 包裝（有些模型會自作主張加）
    content = re.sub(r"^```(?:markdown|md)?\s*\n", "", content.strip())
    content = re.sub(r"\n```\s*$", "", content)

    # HTML heading tags → Markdown heading
    for level in range(1, 7):
        tag_open = f"<h{level}>"
        tag_close = f"</h{level}>"
        md_prefix = "#" * level + " "
        # 匹配 <h2>text</h2> 單行形式
        pattern = re.compile(rf"<h{level}>\s*(.*?)\s*</h{level}>", re.IGNORECASE)
        content = pattern.sub(lambda m: md_prefix + m.group(1), content)

    # 常見 HTML inline 標籤 → Markdown
    content = re.sub(r"<strong>(.*?)</strong>", r"**\1**", content, flags=re.IGNORECASE | re.DOTALL)
    content = re.sub(r"<b>(.*?)</b>", r"**\1**", content, flags=re.IGNORECASE | re.DOTALL)
    content = re.sub(r"<em>(.*?)</em>", r"*\1*", content, flags=re.IGNORECASE | re.DOTALL)
    content = re.sub(r"<br\s*/?>", "\n", content, flags=re.IGNORECASE)
    # <p> 包起來的段落 → 純文字 + 換行
    content = re.sub(r"<p>(.*?)</p>", r"\1\n", content, flags=re.IGNORECASE | re.DOTALL)

    return content.strip()


class ReportGeneratorService:
    def __init__(self, db: Session):
        self.analytics = AnalyticsEngine(db)
        self.llm = LLMService()

    async def generate_full_report(
        self,
        year: int = None,
        month: int = None,
        start_date_param=None,
        end_date_param=None,
        api_key: str = None,
        provider: str = None,
        model_name: str = None,
    ) -> dict:
        """
        生成完整的 AI 分析報告

        參數模式（二擇一）：
        - year + month：完整月份
        - start_date_param + end_date_param：自訂區間
        """
        # 1. 獲取數據
        data: ReportSummary = self.analytics.generate_report_summary(
            year=year,
            month=month,
            start_date_param=start_date_param,
            end_date_param=end_date_param,
        )
        
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

        # 3.5 Sanitize — 清理 HTML tag / 外層 code fence（防線最後一關）
        report_content = sanitize_markdown(report_content)

        # 4. 回傳結果
        # 我們回傳結構化數據，將原始數據與 AI 報告分開，方便前端展示
        return {
            "period": {
                "year": year,
                "month": month
            },
            "raw_data": data, # 包含給 LLM 看的所有原始統計數據
            "ai_analysis": {
                "provider": self.llm.last_provider,  # 本次實際使用的 provider（不是 config 預設）
                "model": self.llm.last_model,        # 本次實際使用的 model
                "content": report_content # Markdown 格式的報告內文
            }
        }
