from app.schemas.report import ReportSummary

class ReportPrompts:

    SERVER_SYSTEM_PROMPT = """你是臺灣警政單位的資深交通執法分析專員，專責協助地方分局檢視月度執法成效並提出下期改進建議。

## 角色與受眾
- 你的讀者是分局長、交通組組長、派出所主管
- 他們每月花 5-10 分鐘讀報告，需要「立即可行動」的結論

## 🔴 零容忍鐵則（違反將被視為嚴重缺陷）

### 1. 數字 100% 準確，禁止編造
- 所有數字（件數、百分比、派出所名稱、路段）**必須**從 JSON 資料中直接引用
- 嚴禁出現 JSON 中沒有的數字
- 若某指標為 0，必須寫 0，不可寫「無資料」；若指標為 2，必須寫 2，不可寫 0
- **每寫一個數字，先在 JSON 中 Ctrl-F 確認存在**

### 2. 繁體中文，不得使用簡體或英文

### 3. 資料涵蓋範圍必須明示（若為 partial period）
- 若資料為部分期間（is_partial=true），報告第一段**必須**寫明：「本期資料僅涵蓋 YYYY-MM-DD ~ YYYY-MM-DD（共 X 天）」
- 去年同期已對齊相同天數，此點需向讀者說明比較為公平對齊
- **未寫明資料涵蓋 = 報告無效**

### 4. 具體 > 抽象，避免空話
- ❌「建議加強執法」
- ✅「建議新化派出所每週二/四 17:00-19:00 在中正路加強攔停，針對未依規定讓車」

### 5. 3E 落地建議
- 每個問題對應 Engineering（工程）/ Enforcement（執法）/ Education（教育）至少一項具體動作

### 5.5 A1 死亡事故 → 工程檢討**必要重點**（警政實務鐵則）
- 若本期有 A1 死亡事故：工程建議章節**必須逐一檢討每個 A1 事故發生地點**
- 每個 A1 地點至少提出一項具體工程改善方向（號誌、標線、照明、速限、路側障礙、視距）
- 若無 A1：工程建議依其他熱點或 A2 重傷地點規劃即可

### 6. 專業但不裝逼
- 用：A1/A2/A3 事故、逕舉/攔舉、派出所轄區、3E 政策
- 禁用：威嚇理論、哈頓矩陣、M1/M2/M3、犯罪學視角等學術黑話

## 數字呈現格式（強制）
- 一律使用 `本期 XX 件（去年同期 XX 件，+XX.X%）` 格式
- A1/A2/A3 分開呈現時標記語意（A1=死亡、A2=受傷、A3=財損）
- 變化百分比語意門檻：
  - |pct| ≥ 20% 稱「顯著」
  - 10%~20% 稱「明顯」
  - <10% 稱「微幅」

## 🚫 禁止的錯誤比較方式

### 絕對禁止：直接把事故件數跟取締件數做大小比較
- ❌「事故 20 件 > 取締 39 件」（數學錯誤，20 本來就小於 39）
- ❌「事故件數高於取締件數」（會邏輯矛盾）

### 正確的警訊判斷方式：使用「取締/事故比率」（enforcement_ratio）
- 每個管區的 ratio 會在「關鍵數字預覽」中給出
- 比率越高 = 執法投入相對事故規模越積極
- 比率越低 = 執法相對事故不成比例（需關注）

### 正確的警訊描述句型範例
- ✅「新化派出所（含那拔）事故 20 件為 4 管區最多，取締比率 1.95（每 1 件事故對應 1.95 件取締）低於唪口 3.88，**相對事故規模執法投入偏少**，需關注」
- ✅「左鎮分駐所（含岡林）取締比率僅 1.33，為 4 管區最低，執法力道薄弱」
- ✅「唪口派出所（含知義）取締比率 3.88 最高，執法積極有效」
"""

    @staticmethod
    def _format_unit_stats(data: ReportSummary) -> str:
        """格式化 4 管區 unit_stats，含取締比率說明"""
        if not data.unit_stats:
            return "- （無派出所資料）"

        lines = []
        # 找最高/最低 ratio 作為比較錨點
        valid_ratios = [(u.unit, u.enforcement_ratio) for u in data.unit_stats if u.enforcement_ratio is not None]
        max_ratio_unit, max_ratio = max(valid_ratios, key=lambda x: x[1], default=(None, None))
        min_ratio_unit, min_ratio = min(valid_ratios, key=lambda x: x[1], default=(None, None))

        for u in data.unit_stats:
            ratio_text = f"{u.enforcement_ratio}" if u.enforcement_ratio is not None else "N/A（事故為 0）"
            line = f"- **{u.unit}**：事故 {u.crashes} 件、取締 {u.tickets} 件、取締/事故比率 = {ratio_text}"
            if u.enforcement_ratio is not None:
                if u.enforcement_ratio == max_ratio and max_ratio is not None:
                    line += " ✅ 4 管區最高（執法相對積極）"
                elif u.enforcement_ratio == min_ratio and min_ratio is not None and min_ratio < max_ratio:
                    line += " ⚠️ 4 管區最低（執法相對事故規模不足）"
            lines.append(line)

        lines.append("")
        lines.append("**解讀規則**：取締/事故比率 = 每 1 件事故對應幾件取締。比率越高代表執法投入相對事故規模越積極。")
        lines.append("**禁止**：切勿直接把「事故件數」和「取締件數」做大小比較（如「事故 20 > 取締 39」是數學錯誤）。")
        return "\n".join(lines)

    @staticmethod
    def _format_a1_locations(data: ReportSummary) -> str:
        """格式化 A1 地點清單給 prompt 用"""
        if not data.a1_locations:
            return "- （本期無 A1 死亡事故，工程建議依其他熱點或 A2 重傷地點規劃即可）"
        lines = []
        for loc in data.a1_locations:
            lines.append(f"- {loc.district} {loc.location}（{loc.count} 件死亡事故）— **必須在工程建議章節具體檢討**")
        return "\n".join(lines)

    @staticmethod
    def get_analysis_prompt(data: ReportSummary) -> str:
        """
        生成綜合分析報告的 Prompt
        Wave 9：強化 anti-hallucination — 預抽取關鍵數字 + 核對 checklist
        """
        data_json = data.model_dump_json(indent=2)

        # ============================================
        # 預抽取關鍵數字（降低 LLM 從 JSON 中撈錯風險）
        # ============================================
        ov = data.overall_stats
        tp = data.topics
        sv = data.severity

        def fmt(s) -> str:
            return f"{s.current} 件（去年同期 {s.last_year} 件，{s.change_pct:+.1f}%）"

        key_numbers = f"""
## 📌 關鍵數字預覽（請逐字引用以下數值，禁止修改）

### 總體指標
- 事故總數：{fmt(ov["accidents"])}
- 違規總數：{fmt(ov["tickets"])}
- A1+A2 傷亡事故：{fmt(ov["injuries"])}
- A1 死亡事故：{fmt(ov["deaths"])}

### 嚴重度細分（本期）
- A1 死亡：{sv.get("A1", 0)} 件
- A2 受傷：{sv.get("A2", 0)} 件
- A3 財損：{sv.get("A3", 0)} 件

### 主題分類（四大執法主題）
- 酒駕取締：{fmt(tp["dui"])}
- 闖紅燈取締：{fmt(tp["red_light"])}
- 危險駕駛取締：{fmt(tp["dangerous"])}
- 超速取締：{fmt(tp["speeding"])}
- 其中「重度超速」（40+ km/h）：{data.speeding_heavy_count} 件{'（重點警訊）' if data.speeding_heavy_count > 0 else ''}

### 專區指標（本期）
- 高齡者事故：{data.elderly_crashes} 件
- 高齡者違規：{data.elderly_tickets} 件
- 青少年事故：{data.youth_crashes} 件
- 大型車涉事事故：{data.heavy_vehicle_crashes} 件
- **行人事故：{data.pedestrian_crashes} 件**（高齡行人 {data.pedestrian_elderly_crashes} 件｜死亡 {data.pedestrian_deaths} 人｜受傷 {data.pedestrian_injuries} 人）
  {'⚠ 高齡行人佔比高，需納入教育宣導重點' if data.pedestrian_crashes > 0 and data.pedestrian_elderly_crashes / max(data.pedestrian_crashes, 1) >= 0.4 else ''}

### 🏢 派出所 4 管區表現（必須全部列出，含取締比率）
{ReportPrompts._format_unit_stats(data)}

### 🔴 A1 死亡事故地點（工程建議章節必須逐一檢討）
{ReportPrompts._format_a1_locations(data)}

### AI 自動偵測重點（請在報告中正面回應這些警訊）
{chr(10).join(f"- {c}" for c in data.focus_causes) if data.focus_causes else "- （無自動偵測警訊）"}
"""

        # ============================================
        # Partial 期間強制警示
        # ============================================
        partial_warning = ""
        if data.period.is_partial and data.period.comparison_note:
            partial_warning = f"""
## 🚨 資料涵蓋警示（最高優先級）

{data.period.comparison_note}

**第一段開頭必須寫明如下格式的文字（或等效語意）：**
> 本期資料涵蓋 {data.period.start_date} ~ {data.period.actual_end_date}（共 {data.period.days_covered} 天），去年同期已對齊為相同 {data.period.days_covered} 天進行公平比較。

**違反此要求的報告將被視為嚴重缺陷。** 讀者是決策者，若未明示資料不完整，會以為執法量能真的大幅下降而誤判政策方向。
"""

        return f"""
請根據以下新化分局統計資料，撰寫一份月度交通執法分析報告。
{partial_warning}
{key_numbers}

## 完整資料（JSON — 你可從中取得熱點、派出所、班別等更細節資料）
```json
{data_json}
```

## 報告結構（務必按此順序輸出 Markdown）

### 一、月度成效速覽
- 用 3-6 個 bullet 點出本月最重要的變化（總事故、總違規、A1 死亡、酒駕、特定派出所突出表現等）
- 每個 bullet 用「指標 + 數字 + 去年同期比較」格式
- **若行人事故 ≥ 3 件 或高齡行人占比 ≥ 40%** → 速覽必須加一個 bullet 提及
- **若有重度超速（40+ km/h）案件** → 速覽必須加一個 bullet 提及
- 最後用一句話下總結（例：「事故下降但酒駕仍上升，需針對性加強夜間取締」）

### 二、熱點分析
- **事故熱點 Top 3**：地點、件數、可能成因推論（從鄰近 severity/派出所/時段交叉分析）
- **違規熱點 Top 3**：地點、件數
- **重疊檢視**：事故熱點是否有在違規熱點清單內？若無，代表「執法未達事故源頭」，需調整

### 三、主題分析（四項）
分別針對 **酒駕 / 闖紅燈 / 危險駕駛 / 超速** 四項：
- 本期件數與變化
- 若明顯變化（±20% 以上），簡述可能原因與對應建議
- 超速若有「重度超速（40+ km/h）」案件，必須單獨指出並建議相對應執法（設置移動式測速點等）

### 四、派出所表現（新化分局 4 管區 — **必須全部列出**）
- 新化分局實際業務以 4 管區檢討：新化派出所（含那拔）、唪口派出所（含知義）、山上分駐所、左鎮分駐所（含岡林）
- **必須把上方「關鍵數字預覽」的 unit_stats 所有管區都列出**（通常剛好 4 個），不可省略任何一個
- 依事故+違規總件數降序排列
- 若某管區事故增加但取締減少 → 標記為「警訊」並建議關注
- 即使某管區件數很低，仍需列出（這是完整呈現全轄區狀況的實務要求）

**🚫 格式強制要求：必須用 bullet list（`-` 起頭），絕對禁止 Markdown table（`|` 分隔）**
- ❌ 禁止：`| 派出所 | 事故 | 取締 | 比率 |`
- ✅ 正確範例格式：
  ```
  - **新化派出所（含那拔）**：事故 262 件、取締 1157 件、取締/事故比率 4.42
    ⚠ 事故件數為 4 管區最多，取締比率最低，執法相對事故規模不足
  - **唪口派出所（含知義）**：事故 231 件、取締 1488 件、取締/事故比率 6.44
    執法力道中等
  ```
  每個管區用 1-2 行 bullet 表達（主資料一行 + 可選警訊/備註一行）。
  禁止用 table 語法的原因：前端 Markdown 渲染器對 table 支援不穩定，容易擠成一行。

### 五、下月執法建議（最重要章節）
分為 3 段：

**執法 (Enforcement) 建議**
- 具體時段、地點、取締項目（例：「山上分駐所轄區週末 20:00-02:00 加強酒測」）
- 建議用「Top 2 急迫 + Top 3 常態」分層

**工程 (Engineering) 建議**
- 🔴 **A1 死亡事故地點必列**：若本期有 A1 案件，**每個 A1 地點都必須單獨列出具體工程改善方向**（此為警政實務必要檢討項）
  - 範例：「新化區中山路（1 件 A1 死亡）— 建議工程單位評估增設左轉專用時相、加強路口照明、標線清晰度」
- 其他事故熱點：若該路段反覆發生事故，列出評估項目（號誌、標線、照明、速限）
- 若本期完全無 A1 且其他熱點無明顯工程議題，可寫「本月無急需工程改善項目」

**教育宣導 (Education) 建議**
- 針對高齡者 / 青少年微電車 / 酒駕熱點區域建議社區宣導重點
- **若有行人事故且高齡占比 ≥ 40%** → 必須加入「高齡行人安全」的具體社區宣導建議（亮色衣物、路口停看聽、遵守號誌）
- 具體列出 1-2 個可執行動作

## 格式要求（嚴格）
- **純 Markdown 語法**，勿包 ```markdown 標籤
- **絕對禁止 HTML 標籤**（如 `<h1>`, `<h2>`, `<div>`, `<br>`, `<strong>`）
  - ❌ `<h2>四、派出所表現</h2>`
  - ✅ `## 四、派出所表現`
  - 所有章節標題都必須用 `##` 或 `###`（視層級）
- 各章節統一用 `##` 起標，子項目用 `###` 或 bullet（`-`）
- 粗體用 `**文字**`（不要 `<strong>`）
- **🚫 禁止使用 Markdown table（`|` 分隔）** — 表格語法渲染不穩定會擠成一行
  - ❌ 禁止：`| 派出所 | 事故 | 取締 |`
  - ✅ 改用 bullet list：`- **新化派出所**：事故 262、取締 1157`
- 數字使用半形阿拉伯數字，無需特別標記
- 全文控制在 800-1500 字，以決策者能 5 分鐘讀完為目標
- 避免前言「以下是報告」、後語「以上為分析」，直接從第一章節開始

## 🔍 自我核對 checklist（寫完後內部檢核，但不需寫進報告）
在完成報告前，自行確認以下項目：
1. ☐ 第一段有寫「本期資料涵蓋 YYYY-MM-DD ~ YYYY-MM-DD（共 X 天）」？（若 is_partial=true 則必須）
2. ☐ 所有出現的件數、百分比、派出所名、路段名是否都能在上方「關鍵數字預覽」或 JSON 中找到？
3. ☐ 酒駕、闖紅燈、危險駕駛三項數字是否與「關鍵數字預覽」完全一致？
4. ☐ 有沒有使用學術黑話（M1/M2/哈頓矩陣/威嚇理論）？如有請移除。
5. ☐ 每個下月建議是否具體到時段/地點/取締項目？
6. ☐ 是否正面回應了「AI 自動偵測重點」中列出的警訊？
7. ☐ **A1 死亡事故地點是否都在工程建議章節單獨列出並給具體改善方向？**（若本期有 A1）
8. ☐ 派出所表現章節是否**完整列出全部 4 管區**（新化/唪口/山上/左鎮）？少寫任何一個都算違反。
9. ☐ 是否使用「取締/事故比率」作警訊判斷，**而非**「事故件數 vs 取締件數」直接大小比較？
   - ❌「事故 20 件 > 取締 39 件」（數學錯誤）
   - ✅「事故 20 件最多，但取締比率 1.95 低於唪口 3.88，執法相對事故規模不足」
10. ☐ 是否全程**未使用 Markdown table**（`|` 分隔）？派出所表現必須用 bullet list 格式。

若任一項未達成，請重寫該段。

請開始撰寫報告（直接從第一章節標題「## 一、月度成效速覽」開始，不要有任何前言）：
"""
