import json
from enum import Enum
from typing import Optional, Dict, Any
import aiohttp
from app.config import settings

class LLMProvider(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    MOCK = "mock"

class LLMService:
    def __init__(self):
        self.provider = settings.PRIMARY_LLM_PROVIDER.lower()
        self.model = settings.LLM_MODEL_NAME
        # 檢查是否有 API Key，若無則強制使用 Mock
        if self.provider == "openai" and not settings.OPENAI_API_KEY:
            self.provider = "mock"
        elif self.provider == "gemini" and not settings.GEMINI_API_KEY:
            self.provider = "mock"
        elif self.provider == "anthropic" and not settings.CLAUDE_API_KEY:
            self.provider = "mock"

    async def generate_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        """
        生成文字內容
        """
        if self.provider == "mock":
            return self._mock_response(system_prompt, user_prompt)
        
        if self.provider == "openai":
            return await self._call_openai(system_prompt, user_prompt, temperature)
        elif self.provider == "gemini":
            return await self._call_gemini(system_prompt, user_prompt, temperature)
        elif self.provider == "anthropic":
            return await self._call_anthropic(system_prompt, user_prompt, temperature)
        
        return "Unsupported provider"

    async def generate_json(self, system_prompt: str, user_prompt: str, output_schema: Optional[Dict] = None) -> Dict:
        """
        生成結構化 JSON 數據
        """
        # 在 Prompt 中強調 JSON 輸出
        json_instruction = "\n\n請以純 JSON 格式輸出回應，不要包含 Markdown 格式標記（如 ```json）。"
        response_text = await self.generate_text(system_prompt, user_prompt + json_instruction, temperature=0.1)
        
        try:
            # 清理可能的 Markdown 標記
            cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            # 如果解析失敗，返回原始文本包裝在 error 中
             # (實際生產環境應該有重試機制)
            return {"error": "Failed to parse JSON", "raw_content": response_text}

    async def _call_openai(self, system_prompt: str, user_prompt: str, temperature: float) -> str:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature
            }
            async with session.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"OpenAI API Error: {error_text}")
                data = await resp.json()
                return data["choices"][0]["message"]["content"]

    async def _call_gemini(self, system_prompt: str, user_prompt: str, temperature: float) -> str:
        # 這裡僅為示意，需要根據 google-generativeai 官方 SDK 或 REST API 實作
        return "Gemini integration not fully implemented yet."

    async def _call_anthropic(self, system_prompt: str, user_prompt: str, temperature: float) -> str:
        # 這裡僅為示意
        return "Claude integration not fully implemented yet."

    def _mock_response(self, system_prompt: str, user_prompt: str) -> str:
        """
        開發用 Mock 回應
        """
        if "分析" in user_prompt or "報告" in user_prompt:
            return """
            {
                "title": "精準執法成效分析報告",
                "summary": "本月事故總數較去年同期顯著下降，顯示執法策略有效。",
                "sections": [
                    {
                        "title": "事故趨勢分析",
                        "content": "本月A1/A2類事故呈現下降趨勢，主要集中在..."
                    },
                    {
                        "title": "熱點分析",
                        "content": "新化區中山路仍為主要事故熱點，建議加強..."
                    }
                ]
            }
            """
        return "這是 Mock LLM 的回應。請設定 API Key 以啟用真實 AI 功能。"
