import json
from enum import Enum
from typing import Optional, Dict, Any
import aiohttp
import asyncio
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

    async def generate_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, api_key: Optional[str] = None, provider: Optional[str] = None, model_name: Optional[str] = None) -> str:
        """
        生成文字內容
        - api_key: 動態傳入的 API Key (不儲存)
        - provider: 指定的供應商 (openai, etc.)
        - model_name: 指定的模型名稱 (gpt-4o, claude-3-5-sonnet, etc.)
        """
        # 決定使用哪個 Provider
        active_provider = provider.lower() if provider else self.provider
        
        # 決定使用哪個 Model
        active_model = model_name if model_name else self.model
        
        # 如果有動態 Key，則強制使用該 Provider (除非是 Mock)
        current_api_key = api_key if api_key else (
            settings.OPENAI_API_KEY if active_provider == "openai" else 
            settings.GEMINI_API_KEY if active_provider == "gemini" else 
            settings.CLAUDE_API_KEY
        )

        # 若無 Key 且非 Mock，則自動降級為 Mock
        if active_provider != "mock" and not current_api_key:
            active_provider = "mock"

        if active_provider == "mock":
            return self._mock_response(system_prompt, user_prompt)
        
        if active_provider == "openai":
            return await self._call_openai(system_prompt, user_prompt, temperature, current_api_key, active_model)
        elif active_provider == "gemini":
            return await self._call_gemini(system_prompt, user_prompt, temperature, current_api_key, active_model)
        elif active_provider == "anthropic":
            return await self._call_anthropic(system_prompt, user_prompt, temperature, current_api_key, active_model)
        elif active_provider == "ollama":
            return await self._call_ollama(system_prompt, user_prompt, temperature, active_model)
        
        return "Unsupported provider"

    async def _call_ollama(self, system_prompt: str, user_prompt: str, temperature: float, model: str) -> str:
        timeout = aiohttp.ClientTimeout(total=300) # Ollama local runs might be slow
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": temperature
                    }
                }
                # Assume Ollama is running on localhost default port
                async with session.post("http://localhost:11434/api/chat", json=payload) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"Ollama API Error: {error_text}")
                    data = await resp.json()
                    return data["message"]["content"]
        except aiohttp.ClientConnectorError:
             raise Exception("无法連接到本地 Ollama 服務。請確認 Ollama 是否已啟動 (http://localhost:11434)。")
        except asyncio.TimeoutError:
            raise Exception("Ollama 生成超時。本地模型可能需要較長時間，請耐心等待或切換較小的模型。")
        except Exception as e:
            raise Exception(f"Ollama Error: {str(e)}")

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

    async def _call_openai(self, system_prompt: str, user_prompt: str, temperature: float, api_key: str, model: str) -> str:
        # 設定較長的超時時間 (120秒)
        timeout = aiohttp.ClientTimeout(total=120)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
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
        except asyncio.TimeoutError:
            raise Exception("Request timed out. The model took too long to respond.")
        except Exception as e:
            raise Exception(f"Connection Error: {str(e)}")

    async def _call_gemini(self, system_prompt: str, user_prompt: str, temperature: float, api_key: str, model: str) -> str:
        # 這裡僅為示意，需要根據 google-generativeai 官方 SDK 或 REST API 實作
        return "Gemini integration not fully implemented yet."

    async def _call_anthropic(self, system_prompt: str, user_prompt: str, temperature: float, api_key: str, model: str) -> str:
        timeout = aiohttp.ClientTimeout(total=120)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
                payload = {
                    "model": model,
                    "max_tokens": 4000,
                    "temperature": temperature,
                    "system": system_prompt,
                    "messages": [
                        {"role": "user", "content": user_prompt}
                    ]
                }
                async with session.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"Anthropic API Error: {error_text}")
                    data = await resp.json()
                    return data["content"][0]["text"]
        except asyncio.TimeoutError:
            raise Exception("Request timed out. The model took too long to respond.")

    def _mock_response(self, system_prompt: str, user_prompt: str) -> str:
        """
        開發用 Mock 回應 (Markdown 格式)
        """
        if "分析" in user_prompt or "報告" in user_prompt:
            return """
# 交通執法成效與事故防制分析報告
分析期間：2026年1月

## 1. 成效摘要 (Summary)
*   **事故顯著下降**：本月 A1/A2 事故共 **86件**，較去年同期（153件）大幅下降 **43.8%**，顯示近期防制策略已見成效。
*   **違規取締策略調整**：總體違規取締雖減少 71.2%，但事故率同步下降，可能意味著執法更具**精準性**，而非僅追求數量。
*   **總結**：「精準打擊見效，事故防制成果斐然，宜持續鎖定高風險熱點。」

## 2. 事故與執法關聯分析 (M1 威嚇理論視角)
*   **執法紅利浮現**：數據顯示，儘管罰單總量減少，但針對特定熱點的精準執法與能見度提升，成功產生了威嚇效果。
*   **受傷人數下降**：A1+A2 受傷人數減少 37.5%，反映出事故嚴重度獲得有效控制。

## 3. 熱點與時空分析 (M2 熱點理論視角)
### 事故熱點 (Top 3)
1.  **新化區 中山路** (主要熱點)
2.  山上區 縣道178線
3.  山上區 市道178甲線

### 違規熱點 (Top 3)
1.  新化區 中山路
2.  山上區 市區道路
3.  新化區 中正路

**重疊分析**：
*   **新化區中山路**既是事故榜首，也是違規取締榜首，顯示執法資源已準確投放於核心問題路段。

## 4. 改進建議 (M3/M4 綜合視角)
*   **執法策略 (Enforcement)**：
    *   持續在**新化區中山路**維持高見警率。
    *   針對 **山上區** 的對向車禍（常見於縣道），建議加強「跨越雙黃線」與「超速」取締。
*   **工程建議**：
    *   檢視縣道178線的標線清晰度與夜間照明。
*   **教育宣導**：
    *   針對高齡者（本月數據未特別惡化，但仍需關注）進行社區宣導，強調晨昏外出穿著亮色衣物。

---
*本報告由 AI 自動生成 (Mock Mode)，僅供測試參考。*
"""
        return "這是 Mock LLM 的回應。請設定 API Key 以啟用真實 AI 功能。"
