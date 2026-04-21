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
        # 預設值（config 讀取）— 僅作為 fallback
        self.provider = settings.PRIMARY_LLM_PROVIDER.lower()
        self.model = settings.LLM_MODEL_NAME
        # 檢查是否有 API Key，若無則強制使用 Mock
        if self.provider == "openai" and not settings.OPENAI_API_KEY:
            self.provider = "mock"
        elif self.provider == "gemini" and not settings.GEMINI_API_KEY:
            self.provider = "mock"
        elif self.provider == "anthropic" and not settings.CLAUDE_API_KEY:
            self.provider = "mock"

        # 追蹤「上一次呼叫實際使用」的 provider/model（給 UI footer 顯示）
        self.last_provider = self.provider
        self.last_model = self.model

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

        # Mock 模式：前端可透過 provider="mock" 或傳 api_key="mock-mode" 顯式觸發
        if active_provider == "mock" or api_key == "mock-mode":
            self.last_provider = "mock"
            self.last_model = active_model or "mock"
            return self._mock_response(system_prompt, user_prompt)

        # 如果有動態 Key，則強制使用該 Provider
        current_api_key = api_key if api_key else (
            settings.OPENAI_API_KEY if active_provider == "openai" else
            settings.GEMINI_API_KEY if active_provider == "gemini" else
            settings.CLAUDE_API_KEY if active_provider == "anthropic" else
            None
        )

        # 若無 Key 且非 Ollama（Ollama 不需要 key），則自動降級為 Mock
        if active_provider != "ollama" and not current_api_key:
            active_provider = "mock"

        if active_provider == "mock":
            self.last_provider = "mock"
            self.last_model = active_model or "mock"
            return self._mock_response(system_prompt, user_prompt)

        # 追蹤本次實際使用的 provider/model（給後端 response footer 顯示）
        self.last_provider = active_provider
        self.last_model = active_model
        
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
        """
        OpenAI Chat Completions API。

        支援家族：
        - GPT-5 系列（reasoning）：gpt-5, gpt-5-mini, gpt-5-nano
        - GPT-4.x 系列（chat）：gpt-4.1, gpt-4o, gpt-4-turbo, gpt-4o-mini
        - o-series reasoning：o1, o1-mini, o3, o3-mini, o4-mini
        """
        # Reasoning 模型不支援 system message 與 temperature 參數
        is_reasoning = (
            model.startswith("o1")
            or model.startswith("o3")
            or model.startswith("o4")
            or model.startswith("gpt-5")  # GPT-5 系列也是 reasoning model
        )

        timeout = aiohttp.ClientTimeout(total=180)  # 給 reasoning 模型更多時間
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                if is_reasoning:
                    # o1/o3 系列：合併 system + user 為單一 user message
                    payload = {
                        "model": model,
                        "messages": [
                            {"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}
                        ],
                    }
                else:
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
                        raise Exception(self._parse_openai_error(resp.status, error_text, model))
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
        except asyncio.TimeoutError:
            raise Exception(f"OpenAI 回應超時（180 秒）。{model} 可能正在高負載中，請稍後再試或改用其他模型。")
        except aiohttp.ClientConnectorError:
            raise Exception("無法連線到 OpenAI API。請檢查網路連線與防火牆設定。")
        except Exception as e:
            if "OpenAI" in str(e) or "API" in str(e):
                raise  # 已是格式化的錯誤
            raise Exception(f"OpenAI 呼叫失敗：{str(e)}")

    async def _call_gemini(self, system_prompt: str, user_prompt: str, temperature: float, api_key: str, model: str) -> str:
        """
        Google Gemini API（REST 直呼，不依賴 SDK）。
        支援 gemini-2.5-pro/flash/flash-lite, gemini-2.0-flash 等。
        """
        timeout = aiohttp.ClientTimeout(total=180)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                payload = {
                    "systemInstruction": {
                        "parts": [{"text": system_prompt}]
                    },
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": user_prompt}]
                        }
                    ],
                    "generationConfig": {
                        "temperature": temperature,
                        # 拉高到 16384 避免長報告被截斷
                        # Gemini 2.5 Pro 支援 65535, Flash 系列支援 65535, 16384 是保守值
                        "maxOutputTokens": 16384,
                    },
                    # 關閉過度保守的 safety 設定（分析警務資料可能觸發 "violence" 類別）
                    "safetySettings": [
                        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
                    ]
                }
                async with session.post(url, json=payload, headers={"Content-Type": "application/json"}) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(self._parse_gemini_error(resp.status, error_text, model))
                    data = await resp.json()

                    # 取得 candidate + finishReason 診斷
                    candidates = data.get("candidates", [])
                    if not candidates:
                        # 整個 response 沒有 candidates — 通常是 prompt 觸發 input safety filter
                        prompt_feedback = data.get("promptFeedback", {})
                        block_reason = prompt_feedback.get("blockReason", "UNKNOWN")
                        raise Exception(f"Gemini 未回傳任何內容（blockReason={block_reason}）。可能 prompt 觸發輸入過濾。")

                    candidate = candidates[0]
                    finish_reason = candidate.get("finishReason", "UNKNOWN")
                    parts = candidate.get("content", {}).get("parts", [])

                    # 合併所有 text parts（Gemini 有時會分段回應）
                    text = "".join(p.get("text", "") for p in parts if "text" in p)

                    if not text.strip():
                        # 無文字內容
                        if finish_reason == "SAFETY":
                            raise Exception("Gemini 因安全過濾拒絕回應。請改用其他模型或稍後再試。")
                        if finish_reason == "RECITATION":
                            raise Exception("Gemini 因引用限制拒絕回應。")
                        raise Exception(f"Gemini 回傳空內容（finishReason={finish_reason}）。請重試或切換模型。")

                    # 若非正常結束，附加警示但仍回傳（讓使用者看到部分內容比完全失敗好）
                    if finish_reason == "MAX_TOKENS":
                        text += "\n\n> ⚠️ **注意**：本段回應因長度限制被截斷。建議換用 Gemini 2.5 Pro（更高 token 上限）或請使用者縮短報告需求。"
                    elif finish_reason == "SAFETY":
                        text += "\n\n> ⚠️ **注意**：部分內容被安全過濾器移除。"

                    return text
        except asyncio.TimeoutError:
            raise Exception(f"Gemini 回應超時（180 秒）。{model} 可能正在高負載中，請稍後再試。")
        except aiohttp.ClientConnectorError:
            raise Exception("無法連線到 Gemini API。請檢查網路連線或 VPN（台灣需要能連到 googleapis.com）。")
        except Exception as e:
            if "Gemini" in str(e):
                raise
            raise Exception(f"Gemini 呼叫失敗：{str(e)}")

    async def _call_anthropic(self, system_prompt: str, user_prompt: str, temperature: float, api_key: str, model: str) -> str:
        """Anthropic Claude Messages API。"""
        timeout = aiohttp.ClientTimeout(total=180)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
                payload = {
                    "model": model,
                    "max_tokens": 8192,  # 長報告需要（Claude 支援到 8192 或更高視模型）
                    "temperature": temperature,
                    "system": system_prompt,
                    "messages": [
                        {"role": "user", "content": user_prompt}
                    ]
                }
                async with session.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(self._parse_anthropic_error(resp.status, error_text, model))
                    data = await resp.json()
                    return data["content"][0]["text"]
        except asyncio.TimeoutError:
            raise Exception(f"Anthropic 回應超時（180 秒）。")
        except aiohttp.ClientConnectorError:
            raise Exception("無法連線到 Anthropic API。請檢查網路連線。")
        except Exception as e:
            if "Anthropic" in str(e):
                raise
            raise Exception(f"Anthropic 呼叫失敗：{str(e)}")

    # ============================================
    # 錯誤訊息格式化（讓使用者看得懂）
    # ============================================
    def _parse_openai_error(self, status: int, text: str, model: str) -> str:
        if status == 401:
            return "OpenAI API Key 無效。請檢查 Key 是否正確、是否已啟用帳戶。"
        if status == 403:
            return f"OpenAI 無權呼叫 {model}。請檢查此 Key 是否有該模型的存取權。"
        if status == 404:
            return f"OpenAI 查無此模型：{model}。可能已下架或名稱有誤。"
        if status == 429:
            return "OpenAI 觸發速率限制或額度已用完。請稍後再試或檢查帳單。"
        if status == 500 or status == 503:
            return "OpenAI 伺服器暫時異常。請稍後再試。"
        return f"OpenAI API 錯誤（HTTP {status}）：{text[:200]}"

    def _parse_gemini_error(self, status: int, text: str, model: str) -> str:
        if status == 400:
            if "API_KEY_INVALID" in text or "API key not valid" in text:
                return "Gemini API Key 無效。請至 Google AI Studio 重新取得 Key。"
            return f"Gemini 請求格式錯誤：{text[:200]}"
        if status == 403:
            return f"Gemini 無權呼叫 {model}。可能需要升級方案或此 Key 未啟用該模型。"
        if status == 404:
            return (
                f"Gemini 查無此模型：{model}。可能已下架或名稱有誤。"
                f"目前可用 model：gemini-2.5-pro / gemini-2.5-flash / gemini-2.5-flash-lite / gemini-2.0-flash。"
                f"（Gemini 1.5 系列已於 2025 年下架）"
            )
        if status == 429:
            # 嘗試從回應解析 retry 時間
            retry_hint = ""
            import re as _re
            m = _re.search(r'"retryDelay":\s*"(\d+)s"', text)
            if m:
                retry_hint = f"（官方建議等待 {m.group(1)} 秒後重試）"

            # 依模型提示可切換方案
            if "pro" in model.lower():
                suggestion = (
                    "建議：① 切換至 gemini-2.5-flash（RPM 限制從 2 → 10 寬鬆 5 倍）"
                    "② 或 gemini-2.5-flash-lite（RPM 15、RPD 1000）"
                    "③ 或改用 🧪 Mock 模式先測試資料流。"
                )
            elif "flash-lite" in model.lower():
                suggestion = "flash-lite 已是限制最寬的免費模型，請稍後再試或升級付費方案。"
            else:
                suggestion = "可改用 gemini-2.5-flash-lite（RPM 15）或升級付費方案。"

            return (
                f"Gemini 觸發速率限制 {retry_hint}。\n"
                f"免費 tier 限制（參考）：pro=2 RPM/50 RPD；flash=10 RPM/250 RPD；flash-lite=15 RPM/1000 RPD。\n"
                f"{suggestion}"
            )
        if status >= 500:
            return "Gemini 伺服器暫時異常。請稍後再試。"
        return f"Gemini API 錯誤（HTTP {status}）：{text[:200]}"

    def _parse_anthropic_error(self, status: int, text: str, model: str) -> str:
        if status == 401:
            return "Anthropic API Key 無效。"
        if status == 404:
            return f"Anthropic 查無此模型：{model}。"
        if status == 429:
            return "Anthropic 觸發速率限制。請稍後再試。"
        if status >= 500:
            return "Anthropic 伺服器暫時異常。"
        return f"Anthropic API 錯誤（HTTP {status}）：{text[:200]}"

    def _mock_response(self, system_prompt: str, user_prompt: str) -> str:
        """
        Mock 回應：從 user_prompt 內嵌的 JSON 解析出真實統計資料，
        按照 Phase 3 的新 prompt 結構組裝模板化 Markdown。
        用途：驗證資料撈取、prompt 組裝、前端版型，不花 API 費用。
        """
        import re
        import json as _json

        # 嘗試解析 prompt 中的 JSON 資料區
        try:
            match = re.search(r"```json\s*(\{.*?\})\s*```", user_prompt, re.DOTALL)
            if not match:
                return "# Mock 模式錯誤\n\n無法從 prompt 解析 JSON 資料。請確認 prompt 結構。"
            data = _json.loads(match.group(1))
        except Exception as e:
            return f"# Mock 模式解析錯誤\n\n{str(e)}"

        return self._render_mock_report(data)

    def _render_mock_report(self, d: dict) -> str:
        """根據實際 ReportSummary 資料組裝一份模板化報告"""
        period = d.get("period", {})
        year = period.get("year", "?")
        month = period.get("month", "?")
        is_partial = period.get("is_partial", False)
        actual_end = period.get("actual_end_date")
        days_covered = period.get("days_covered", 30)

        overall = d.get("overall_stats", {})
        topics = d.get("topics", {})
        subtypes = d.get("enforcement_subtypes", {})
        severity = d.get("severity", {})
        units = d.get("unit_stats", [])
        shifts = d.get("shift_stats", [])
        a_hot = d.get("accident_hotspots", [])
        v_hot = d.get("violation_hotspots", [])
        focus_districts = d.get("focus_districts", [])
        focus_causes = d.get("focus_causes", [])

        def fmt_stat(key: str, label: str) -> str:
            s = overall.get(key, {})
            if not s:
                return f"- {label}：資料缺失"
            return f"- {label}：本期 {s.get('current', 0)} 件（去年同期 {s.get('last_year', 0)} 件，{s.get('change_pct', 0):+.1f}%）"

        def fmt_topic(key: str, label: str) -> str:
            s = topics.get(key, {})
            if not s:
                return f"- {label}：資料缺失"
            return f"- {label}：本期 {s.get('current', 0)} 件（去年 {s.get('last_year', 0)} 件，{s.get('change_pct', 0):+.1f}%）"

        # === 組裝報告 ===
        lines = []

        # 開頭：資料涵蓋說明（若本期不完整）
        if is_partial:
            lines.append(f"> **⚠ 資料涵蓋說明**：本期資料僅涵蓋 {period.get('start_date')} ~ {actual_end}（共 {days_covered} 天）。")
            lines.append(f"> 去年同期已自動對齊為相同天數比較，避免「半個月 vs 完整月」的假象落差。")
            lines.append("")

        # 一、速覽
        lines.append("## 一、月度成效速覽")
        if is_partial:
            lines.append(f"（資料截至 {actual_end}，共 {days_covered} 天）")
        lines.append(fmt_stat("tickets", "總違規"))
        lines.append(fmt_stat("accidents", "總事故"))
        lines.append(f"- A1 死亡事故：{severity.get('A1', 0)} 件｜A2 受傷：{severity.get('A2', 0)} 件｜A3 財損：{severity.get('A3', 0)} 件")
        if focus_causes:
            lines.append(f"- ⚠ 本期重點：{'、'.join(focus_causes[:3])}")
        if focus_districts:
            lines.append(f"- ⚠ 事故增加較明顯區域：{'、'.join(focus_districts)}")
        lines.append("")
        lines.append(f"**總結**：本月為 {year} 年 {month} 月分析報告（Mock 模式樣板）。正式 AI 會根據上述數據寫出更精緻的執行面結論。")
        lines.append("")

        # 二、熱點
        lines.append("## 二、熱點分析")
        lines.append("### 事故熱點 Top 3")
        if a_hot:
            for i, h in enumerate(a_hot[:3], 1):
                lines.append(f"{i}. **{h.get('district', '未知')} {h.get('location', '未知')}** — {h.get('count', 0)} 件")
        else:
            lines.append("- 本期無事故熱點資料")
        lines.append("")
        lines.append("### 違規熱點 Top 3")
        if v_hot:
            for i, h in enumerate(v_hot[:3], 1):
                lines.append(f"{i}. **{h.get('district', '未知')} {h.get('location', '未知')}** — {h.get('count', 0)} 件")
        else:
            lines.append("- 本期無違規熱點資料")
        lines.append("")
        # 重疊檢視
        a_locs = {h.get("location") for h in a_hot[:3] if h.get("location")}
        v_locs = {h.get("location") for h in v_hot[:3] if h.get("location")}
        overlap = a_locs & v_locs
        if overlap:
            lines.append(f"**重疊檢視**：事故與違規熱點都涵蓋 {'、'.join(overlap)}，顯示執法資源已投放於核心問題路段。")
        else:
            lines.append("**重疊檢視**：事故熱點未在違規熱點清單內，可能代表「執法未達事故源頭」，建議下月調整取締位置。")
        lines.append("")

        # 三、主題分析
        lines.append("## 三、主題分析")
        lines.append(fmt_topic("dui", "酒駕"))
        lines.append(fmt_topic("red_light", "闖紅燈"))
        lines.append(fmt_topic("dangerous", "危險駕駛"))
        lines.append("")

        # 四、派出所表現
        lines.append("## 四、派出所表現")
        if units:
            lines.append("依事故+違規總件數排序，本期 Top 3：")
            for u in units[:3]:
                lines.append(
                    f"- **{u.get('unit', '未知')}**：事故 {u.get('crashes', 0)} 件、違規 {u.get('tickets', 0)} 件"
                )
        else:
            lines.append("- 本期無派出所統計資料")
        lines.append("")

        # 五、下月建議
        lines.append("## 五、下月執法建議")
        lines.append("")
        lines.append("### 執法（Enforcement）")
        # 根據 subtypes 變化給建議
        top_subtype = max(subtypes.items(), key=lambda x: x[1], default=(None, 0)) if subtypes else (None, 0)
        if top_subtype[0] and top_subtype[1] > 0:
            lines.append(f"- 本月主力舉發類型為「{top_subtype[0]}」（{top_subtype[1]} 件），建議延續")
        if a_hot:
            top = a_hot[0]
            lines.append(f"- 事故最嚴重路段 **{top.get('district')} {top.get('location')}** 建議加強見警率與取締密度")
        lines.append("")
        lines.append("### 工程（Engineering）")
        if a_hot and len(a_hot) >= 2:
            lines.append(f"- 建議道路管理單位評估 {a_hot[0].get('location')} 與 {a_hot[1].get('location')} 的號誌、標線、照明是否需改善")
        else:
            lines.append("- 本月無急需工程改善項目")
        lines.append("")
        lines.append("### 教育宣導（Education）")
        elderly_c = d.get("elderly_crashes", 0)
        youth_c = d.get("youth_crashes", 0)
        heavy_c = d.get("heavy_vehicle_crashes", 0)
        if elderly_c > 0:
            lines.append(f"- 高齡者事故 {elderly_c} 件，建議社區宣導晨昏外出著亮色衣物、強化兩段式左轉觀念")
        if youth_c > 0:
            lines.append(f"- 青少年事故 {youth_c} 件，建議協調學校加強微電車/電輔車安全宣導")
        if heavy_c > 0:
            lines.append(f"- 大型車涉事 {heavy_c} 件，建議貨運業者入校園/公司宣導視線死角")
        lines.append("")
        lines.append("---")
        lines.append(f"*本報告由 **Mock 模式** 生成（新化分局 {year}/{month} 資料樣板）。切換為真實 AI 模型後，內容將由 LLM 重新分析並提供更具判斷力的建議。*")

        return "\n".join(lines)
