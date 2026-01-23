# 🚀 AI 報告生成系統 & 熱點分析 - 實施計畫

**建立日期：** 2026-01-23
**版本：** 1.0
**狀態：** 規劃中

---

## 📋 專案概述

建立一套「結構化數據 + AI 智慧分析」的報告生成系統，結合交通事故防制理論（嚇阻、熱點、Haddon、Safe System），自動產出可呈報的分析報告。

---

## 🎯 核心功能

### Phase 1: 熱點分析引擎 (1-2 天)
- [ ] **Top N 事故熱點 API** - 前 5/10 大事故路口/路段
- [ ] **重疊率計算** - 事故熱點 vs 違規熱點
- [ ] **趨勢比較** - 本期 vs 去年同期/前月

### Phase 2: 報告摘要 JSON 結構 (1-2 天)
- [ ] **ReportSummary 資料結構** - 完整的 JSON Schema
- [ ] **報告摘要 API** - `/api/report/summary`
- [ ] **自動計算引擎** - 從原始數據計算所有指標

### Phase 3: AI 報告生成 (2-3 天)
- [ ] **理論模組 Prompts** - M1~M4 固定模組
- [ ] **多模型整合** - OpenAI / Gemini / Claude
- [ ] **審稿檢核** - 程式規則 + LLM 審稿
- [ ] **報告輸出** - Markdown / HTML / PDF

### Phase 4: 前端整合 (1-2 天)
- [ ] **報告生成頁面** - 新增專屬頁面
- [ ] **熱點地圖標示** - Top N 視覺化
- [ ] **導出功能** - Word/PDF/HTML

---

## 📊 資料結構設計

### 1. Report Summary JSON (MVP)

```json
{
  "meta": {
    "generated_at": "2026-01-23T10:00:00+08:00",
    "period": {
      "start": "2026-01-01",
      "end": "2026-01-31",
      "label": "2026年1月"
    },
    "baseline": {
      "type": "去年同期",
      "period": {
        "start": "2025-01-01",
        "end": "2025-01-31"
      }
    },
    "scope": "臺南市新化分局轄區"
  },
  
  "accident": {
    "summary": {
      "a1_count": 2,
      "a2_count": 84,
      "a3_count": 156,
      "total": 242,
      "a1_ratio": 0.83,
      "trend_vs_baseline_pct": -15.2
    },
    "top_hotspots": [
      {
        "rank": 1,
        "site_id": "HS001",
        "name": "中山路 x 中正路口",
        "district": "新化區",
        "a1_count": 1,
        "a2_count": 5,
        "total": 6,
        "trend_pct": 20.0,
        "coordinates": [23.0383, 120.3108]
      }
    ],
    "by_timeband": [
      { "shift": "01", "time_range": "00:00-02:00", "a1": 0, "a2": 3, "total": 8 }
    ],
    "by_type": {
      "intersection": { "count": 120, "pct": 49.6 },
      "road_segment": { "count": 122, "pct": 50.4 }
    },
    "by_cause": [
      { "cause": "未注意車前狀況", "count": 45, "pct": 18.6 },
      { "cause": "未依規定讓車", "count": 38, "pct": 15.7 }
    ],
    "by_party_type": [
      { "party_type": "機車", "count": 156, "pct": 64.5 },
      { "party_type": "自小客", "count": 52, "pct": 21.5 }
    ]
  },
  
  "enforcement": {
    "dui": {
      "count": 15,
      "trend_vs_baseline_pct": -25.0,
      "density_per_shift": 1.25,
      "top_hotspots": [
        { "rank": 1, "site_id": "HS002", "name": "中華路段", "count": 5 }
      ]
    },
    "red_light": {
      "count": 120,
      "trend_vs_baseline_pct": 10.5,
      "density_per_shift": 10.0,
      "top_hotspots": []
    },
    "dangerous_driving": {
      "count": 85,
      "trend_vs_baseline_pct": -5.2,
      "density_per_shift": 7.08,
      "top_hotspots": []
    },
    "total_tickets": 450
  },
  
  "overlap_and_spillover": {
    "accident_vs_dui_overlap_rate": 45.0,
    "accident_vs_redlight_overlap_rate": 62.0,
    "accident_vs_dangerous_overlap_rate": 58.0,
    "spillover_analysis": {
      "core_hotspot_change_pct": -12.0,
      "buffer_zone_change_pct": 5.0,
      "interpretation": "核心熱點下降，周邊緩衝區微幅上升，疑似位移效應"
    }
  },
  
  "elderly": {
    "accident_count": 28,
    "accident_pct": 11.6,
    "ticket_count": 42,
    "trend_vs_baseline_pct": 8.5
  }
}
```

---

## 🤖 AI 理論模組設計

### M1: 嚇阻理論 (Deterrence Theory)

**核心邏輯：** 執法密度 → 違規變化 → 事故變化

**必須引用指標：**
- 執法密度 (`density_per_shift`)
- 違規趨勢 (`trend_vs_baseline_pct`)
- 事故趨勢 (`accident.summary.trend_vs_baseline_pct`)

**模板：**
```
根據嚇阻理論，當執法密度達到 {density} 件/班次時，違規行為應呈現下降趨勢。
本期 {topic} 違規共 {count} 件，較去年同期 {trend_direction} {trend_pct}%，
同期事故 {accident_trend_direction} {accident_trend_pct}%，
{conclusion: 符合/未完全符合} 嚇阻效應預期。
```

### M2: 熱點理論 + 位移/擴散 (Hot Spot + Displacement/Diffusion)

**核心邏輯：** 重疊率 + 核心/周邊變化

**必須引用指標：**
- 重疊率 (`overlap_rate`)
- 核心變化 (`core_hotspot_change_pct`)
- 緩衝區變化 (`buffer_zone_change_pct`)

### M3: Haddon Matrix (事故機制)

**核心邏輯：** 人/車/路 × 事前/事中/事後

**必須引用指標：**
- 事故型態分布 (`by_type`, `by_cause`)
- 當事人車種 (`by_party_type`)
- 時段分布 (`by_timeband`)

### M4: Safe System (速度能量與嚴重度)

**核心邏輯：** 事故發生率 vs 嚴重度（A1比例）

**必須引用指標：**
- A1 比例 (`a1_ratio`)
- 超速/危駕取締 (`dangerous_driving`)
- 嚴重事故趨勢

---

## 🔧 技術架構

### 後端 (FastAPI)

```
backend/app/
├── api/
│   ├── report.py          # 新增：報告生成 API
│   └── hotspots.py        # 新增：熱點分析 API
├── services/
│   ├── analytics_engine.py # 新增：指標計算引擎
│   ├── report_generator.py # 新增：AI 報告生成
│   └── ai_clients.py       # 新增：多模型整合
└── schemas/
    └── report.py           # 新增：報告 Pydantic 模型
```

### 前端 (React)

```
animal-crossing-dashboard/src/
├── components/
│   ├── ReportGeneratorPage.tsx  # 新增：報告生成頁
│   └── HotspotRankingCard.tsx   # 新增：熱點排名卡片
└── api/
    └── client.ts                # 更新：新增報告 API
```

---

## 📅 開發順序

### Day 1: 熱點分析 API
1. 建立 `/api/stats/hotspots` 端點
2. 計算 Top N 事故/違規熱點
3. 前端顯示熱點排名卡片

### Day 2: 報告摘要 JSON
1. 建立 `ReportSummary` Pydantic 模型
2. 實作 `AnalyticsEngine` 計算所有指標
3. 建立 `/api/report/summary` 端點

### Day 3: AI 報告生成
1. 建立理論模組 Prompt 模板
2. 整合 OpenAI / Gemini / Claude
3. 實作審稿檢核邏輯

### Day 4: 前端整合
1. 報告生成頁面
2. 熱點地圖標示
3. 導出功能

---

## 🔑 關鍵設計決策

### 1. 地點鍵 (Join Key)
**決定：** 使用 `(district, location_desc)` 組合作為初步 Key，未來升級為 `site_id`

**理由：**
- 目前資料已有 `district` + `location_desc`
- 避免大規模 schema 變更
- 可逐步建立 `dim_site` 對照表

### 2. 基準線 (Baseline)
**決定：** 預設「去年同期」，可選「前月」

**理由：**
- 去年同期消除季節性影響
- 與官方統計口徑一致
- 使用者可依需求切換

### 3. AI 模型分工
**決定：**
- 主模型（寫報告）：OpenAI GPT-4o 或 Claude 3.5 Sonnet
- 次模型（審稿）：Gemini 2.0 Flash

**理由：**
- GPT-4o/Claude 長文生成穩定
- Gemini Flash 成本低、結構化輸出佳

---

## ⚠️ 風險與對策

| 風險 | 對策 |
|------|------|
| AI 產生不存在的數據 | 硬性規則：每句必引用 JSON 指標 + 審稿檢核 |
| 地點資料不一致 | 建立地點正規化對照表 |
| API 成本過高 | 快取報告摘要、限制生成頻率 |
| 報告格式不符呈報規範 | 固定六段式結構、程式驗證 |

---

## ✅ 驗收標準

1. [ ] 可產出 Top 10 事故熱點排名
2. [ ] 報告摘要 JSON 包含所有必要指標
3. [ ] AI 報告每句話都引用具體數據
4. [ ] 審稿模組能偵測未引用的陳述
5. [ ] 可導出 Word/PDF 格式

---

## 📚 參考資源

- OpenAI Responses API: https://platform.openai.com/docs/api-reference/responses
- Gemini API: https://ai.google.dev/gemini-api/docs
- Anthropic Messages API: https://docs.anthropic.com/en/api/messages

