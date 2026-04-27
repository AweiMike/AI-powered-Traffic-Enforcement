# 酒駕風險預測模組 設計文件

| 項目 | 內容 |
|---|---|
| 文件版本 | v1.0 |
| 撰寫日期 | 2026-04-27 |
| 所屬專案 | 精準執法儀表板系統 |
| 模組範疇 | 僅酒駕事故風險時空預測（派出所評比已由既有「酒駕成效專區」涵蓋，不在此模組） |
| 預期使用者 | 僅本機作者（同事透過 `build_update.py --exclude prediction` 取得不含此模組的版本） |

---

## 1. 目標與動機

### 1.1 業務目標
針對轄區酒駕事故與取締資料，建立一個能輸出「未來 7 天 × 派出所 × 12 班別」風險指數的預測模型，作為勤務排班與精準執法決策的科學依據。

### 1.2 設計原則
1. **Recall 優先於 Precision** — 寧可誤報攔多，不能讓真實酒駕案件漏網（Recall ≥ 80% 為過關線）。
2. **本機運算、不嫁接外部 LLM API** — 模型訓練與推論皆在本機完成，避免個資外洩與 API 費用。
3. **解釋性必備** — 每筆高風險預測必附 SHAP top-5 特徵，支援長官質詢與信任建立。
4. **部署隔離** — 此模組僅本機可見，同事的更新檔不含本模組任何檔案、UI、資料表。
5. **不破壞既有架構** — 沿用 SQLite + FastAPI + React + Tailwind，沿用 Wave 6 配色與字體規範。

### 1.3 不做的事（YAGNI）
- 不做派出所評比（既有酒駕成效專區已涵蓋）
- 不做即時氣象（每日批次足夠）
- 不做 GPU 訓練（i5-13500 CPU 已綽綽有餘）
- 不做 LSTM / Transformer（資料量級不適合，解釋性差）
- 不做雲端部署
- 不串接實際勤務派班系統（先做 UI，串接留後續迭代）

---

## 2. 架構總覽

### 2.1 資料流

```
SQLite traffic_enforcement.db
├── Crash (suspected_alcohol)
└── Ticket (topic_dui)
        │
        ├─ ext_weather (CWA 氣象，5 年回溯)
        └─ ext_calendar (節慶/農曆/發薪/週五，2021-2030)
        │
        ▼
特徵工程 build_features.py
        │
        ▼
XGBoost 雙模型訓練 (Classifier + Poisson Regressor)
        │
        ▼
backend/models/dui_hotspot_*.pkl
        │
        ▼
前端首頁 mount → 觸發 BackgroundTask
        │
        ▼
daily_predict_dui.py → dui_predictions 表
        │
        ▼
FastAPI /topics/dui/predict/* 端點
        │
        ▼
DuiPredictionPage（KPI / Top-N / 熱圖 / SHAP）
```

### 2.2 整合點

| 既有功能 | 整合方式 |
|---|---|
| 側欄 navigation | 「專區」分組下「酒駕成效」之後新增「🎯 酒駕風險預測」項，受 `VITE_ENABLE_PREDICTION` 控制 |
| `STATION_GROUPS` (Wave 11) | 預測資料的 `group_name` 直接重用 |
| `enforcement_subtype` | 取締資料來源欄位，不變更 |
| `start.bat` | 不修改（觸發改前端首頁） |
| `build_update.py` | 新增 `--exclude prediction` 參數，預設給同事用 |
| AI 報告 | v1.0 不整合，留 P1 後續迭代 |

---

## 3. 資料庫 Schema

### 3.1 新增資料表（3 張）

**ext_weather**（行政區 × 班別 × 日 粒度，5 年）
```sql
CREATE TABLE ext_weather (
  id INTEGER PRIMARY KEY,
  date DATE NOT NULL,
  district VARCHAR(50) NOT NULL,
  shift_id VARCHAR(2) NOT NULL,
  rainfall_mm FLOAT,
  temperature_c FLOAT,
  humidity_pct FLOAT,
  wind_speed_ms FLOAT,
  weather_code VARCHAR(20),
  is_typhoon BOOLEAN DEFAULT 0,
  data_source VARCHAR(20) DEFAULT 'CWA',
  fetched_at DATETIME,
  UNIQUE(date, district, shift_id)
);
CREATE INDEX idx_weather_date_district ON ext_weather(date, district);
```

**ext_calendar**（2021-01-01 ~ 2030-12-31，一次性生成）
```sql
CREATE TABLE ext_calendar (
  date DATE PRIMARY KEY,
  is_holiday BOOLEAN DEFAULT 0,
  is_holiday_eve BOOLEAN DEFAULT 0,
  lunar_day INTEGER,
  is_payday BOOLEAN DEFAULT 0,
  is_friday BOOLEAN DEFAULT 0,
  festival_name VARCHAR(50),
  is_election_eve BOOLEAN DEFAULT 0
);
```

**dui_predictions**（每日預測結果快照，>30 天舊紀錄自動清除）
```sql
CREATE TABLE dui_predictions (
  id INTEGER PRIMARY KEY,
  predict_for_date DATE NOT NULL,
  sub_unit VARCHAR(100) NOT NULL,
  shift_id VARCHAR(2) NOT NULL,
  group_name VARCHAR(100),
  risk_score FLOAT NOT NULL,
  risk_level VARCHAR(10),  -- HIGH/MEDIUM/LOW
  risk_rank INTEGER,
  predicted_count FLOAT,
  shap_top_features TEXT,  -- JSON
  model_version VARCHAR(20),
  generated_at DATETIME,
  UNIQUE(predict_for_date, sub_unit, shift_id)
);
CREATE INDEX idx_pred_date_unit ON dui_predictions(predict_for_date, sub_unit);
```

**system_locks**（防重入，已存在則重用）
```sql
CREATE TABLE IF NOT EXISTS system_locks (
  name VARCHAR(50) PRIMARY KEY,
  locked_at DATETIME,
  released_at DATETIME
);
```

### 3.2 資料遷移
- 同事的版本：以上 4 張表**不建立**（migration 腳本檢查 `VITE_ENABLE_PREDICTION` env，不存在則跳過）
- 本機版本：透過 `backend/scripts/init_prediction_schema.py` 一次性建立

---

## 4. 特徵工程

### 4.1 樣本構造
對 (sub_unit ∈ 8 種) × (shift_id ∈ 12 班) × (date ∈ 5 年) 笛卡兒積展開，每筆為一個訓練樣本，最終資料量約 **17.5 萬列**。

### 4.2 22 個特徵

| 類別 | 特徵 | 型別 | 來源 |
|---|---|---|---|
| 時間 | shift_id | categorical | Crash |
| 時間 | day_of_week | int 0-6 | derive |
| 時間 | month | int 1-12 | derive |
| 時間 | is_holiday | bool | ext_calendar |
| 時間 | is_holiday_eve | bool | ext_calendar |
| 空間 | sub_unit | one-hot 8 | Crash |
| 空間 | district | one-hot | Crash |
| 空間 | group_name | one-hot 4 | STATION_GROUPS map |
| 歷史 | rolling_7d_dui_crash | int | 過去 7 天同 sub_unit 酒駕事故數 |
| 歷史 | rolling_30d_dui_crash | int | 同上 30 天 |
| 歷史 | rolling_90d_dui_crash | int | 同上 90 天 |
| 歷史 | rolling_7d_dui_ticket | int | 過去 7 天同 sub_unit 酒駕取締數 |
| 歷史 | rolling_30d_dui_ticket | int | 同上 30 天 |
| 歷史 | rolling_90d_dui_ticket | int | 同上 90 天 |
| 環境 | rainfall_mm | float | ext_weather |
| 環境 | temperature_c | float | ext_weather |
| 環境 | weather_code | categorical | ext_weather |
| 環境 | is_typhoon | bool | ext_weather |
| 環境 | light | categorical（白天/夜間） | Crash 或 shift_id 推導 |
| 事件 | is_payday | bool | ext_calendar |
| 事件 | is_friday | bool | ext_calendar |
| 事件 | festival_flag | categorical | ext_calendar |

### 4.3 標籤
- **主標籤（Classifier）**：該樣本是否發生 ≥1 件酒駕事故（`Crash.suspected_alcohol = TRUE` 且時空對齊） → Binary 0/1
- **副標籤（Regressor）**：該樣本酒駕事故件數 → 整數 ≥ 0

### 4.4 切分（時間導向，不可隨機）
```
最早 ─── 70% train ───│── 15% val ──│── 15% test ──│ 最新
                       ↑切點 1        ↑切點 2
```
5 年資料 ≈ 訓練 42 個月、驗證 9 個月、測試 9 個月。

---

## 5. 模型架構

### 5.1 雙模型策略

```python
classifier = XGBClassifier(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.05,
    scale_pos_weight=auto,    # 自動處理類別不平衡（正樣本約 1%）
    eval_metric='aucpr',
    early_stopping_rounds=30,
)

regressor = XGBRegressor(
    objective='count:poisson',  # 件數標籤右偏，Poisson 為教科書答案
    n_estimators=200,
    max_depth=5,
)

# 最終 risk_score
# normalize: 用訓練集的 P95 做 min-max 截斷縮放至 [0,1]，避免極端離群值拉高分數
risk_score = 0.7 * classifier.predict_proba + 0.3 * normalize(regressor.predict)
```

### 5.2 類別不平衡處理
- `scale_pos_weight = neg / pos`（XGBoost 內建）
- 評估**禁用 Accuracy**，改用 PR-AUC + Recall@K
- **不使用 SMOTE**（時序資料合成樣本破壞時間結構）

### 5.3 Recall-first 門檻調整
- 預設分類門檻 0.5 → **降到 0.25**
- 上線前以驗證集調出「Recall ≥ 80% 之最低 Precision 點」對應的門檻
- 此門檻寫入模型 metadata，推論時使用

### 5.4 風險等級映射
| risk_score 區間 | risk_level | UI 顯示 |
|---|---|---|
| ≥ 0.70 | HIGH | 🔴 必排勤 |
| 0.40 - 0.69 | MEDIUM | 🟡 補強 |
| < 0.40 | LOW | 🟢 例行 |

---

## 6. 訓練 Pipeline

### 6.1 檔案結構
```
backend/app/ml/
├── __init__.py
├── feature_engineering.py
├── train.py
├── evaluate.py
├── predict.py
└── shap_explainer.py

backend/models/
├── dui_hotspot_classifier_v{ts}.pkl
├── dui_hotspot_regressor_v{ts}.pkl
├── feature_columns_v{ts}.json
└── eval_reports/
    └── eval_v{ts}.json

backend/scripts/
├── init_prediction_schema.py
├── fetch_cwa_history.py
├── build_calendar.py
├── daily_predict_dui.py
└── retrain_dui_model.py
```

### 6.2 訓練步驟
1. Feature build → cache 為 parquet
2. Time split 70/15/15
3. Classifier + Regressor 並行訓練（early stopping on val）
4. 評估：PR-AUC、Recall（主）、Precision、Top-K Recall、MAE（迴歸）
5. 持久化：模型 + feature_columns + eval_report 寫入 `backend/models/`

### 6.3 重訓練觸發
- **手動**：UI 顯示「🟡 模型可重訓」徽章 → 點擊呼叫 `/admin/predict/dui/retrain`
- **觸發條件**：累積新事故/取締資料 ≥ 30 天
- **不自動**：避免 3-4 分鐘訓練阻塞使用

---

## 7. API 端點

| 端點 | 方法 | 用途 |
|---|---|---|
| `/topics/dui/predict/status` | GET | 首頁觸發用，回傳 fresh/refreshing/triggered |
| `/topics/dui/predict/hotspot` | GET | 未來 N 天 Top-K 高風險（params: `days`, `top`） |
| `/topics/dui/predict/by_unit/{sub_unit}` | GET | 特定派出所未來各班風險 |
| `/topics/dui/predict/explain/{prediction_id}` | GET | 單筆 SHAP 解釋 |
| `/admin/predict/dui/retrain` | POST | 觸發重訓（API Key） |

### 7.1 hotspot 回應範例
```json
{
  "model_version": "v20260427",
  "predict_window": ["2026-04-28", "2026-05-04"],
  "items": [
    {
      "date": "2026-05-02",
      "shift_id": "11",
      "shift_label": "20:00-22:00",
      "duty_order": 7,
      "duty_label": "第7班",
      "sub_unit": "新化派出所",
      "group_name": "新化派出所（含那拔）",
      "risk_score": 0.87,
      "risk_level": "HIGH",
      "predicted_count": 1.4,
      "rank": 1,
      "top_factors": [
        {"feature": "rolling_30d_dui_crash", "value": 4, "shap": 0.31},
        {"feature": "is_friday", "value": true, "shap": 0.22},
        {"feature": "is_holiday_eve", "value": true, "shap": 0.18}
      ]
    }
  ]
}
```

---

## 8. 前端 UI

### 8.1 新頁面 `DuiPredictionPage.tsx`
四個區段：
1. **模型評估摘要 KPI** — Recall / Precision / PR-AUC / 模型狀態
2. **未來 7 天 Top-N 表格** — 日期/勤務班別/派出所/風險/SHAP 主因/詳情按鈕
3. **風險時段熱圖** — 派出所 × 12 班 × 7 天矩陣，色階 HIGH/MEDIUM/LOW
4. **SHAP 全域特徵重要度** — 折疊面板

### 8.1.1 勤務班別顯示規則
**儲存層**（`shift_id`）沿用既有公式 `(hour // 2) + 1`，不可變動。
**UI 顯示層**對齊派出所勤務序號：

| duty_order | shift_id | 時段 |
|---|---|---|
| 第1班 | 05 | 08:00-10:00 |
| 第2班 | 06 | 10:00-12:00 |
| 第3班 | 07 | 12:00-14:00 |
| 第4班 | 08 | 14:00-16:00 |
| 第5班 | 09 | 16:00-18:00 |
| 第6班 | 10 | 18:00-20:00 |
| 第7班 | 11 | 20:00-22:00 |
| 第8班 | 12 | 22:00-00:00 |
| 第9班 | 01 | 00:00-02:00 |
| 第10班 | 02 | 02:00-04:00 |
| 第11班 | 03 | 04:00-06:00 |
| 第12班 | 04 | 06:00-08:00 |

API 回傳同時提供 `shift_id` / `shift_label` / `duty_order` / `duty_label` 四個欄位。
表格與熱圖橫軸**按 duty_order 升序排列**（第1班在最左），符合警員直覺。
此映射統一寫在 `backend/app/utils/shift_mapping.py`，前後端共用同一份來源。

### 8.2 詳情側邊抽屜
點 Top-N 表「查看詳情」開啟：
- SHAP waterfall plot（後端產生 PNG）
- 該組合過去 90 天歷史 mini chart
- 「採納為勤務點」按鈕（v1 僅 log，不串實際派班）

### 8.3 觸發機制（前端首頁 mount）
```
DashboardView mount
  └─ GET /topics/dui/predict/status
       ├─ fresh    → 不顯示
       ├─ refreshing/triggered → Header toast「🔄 預測資料更新中...」
       │   └─ 每 3 秒輪詢，完成後 toast 變綠 → 3 秒後消失
       └─ error    → 灰色提示「預測暫不可用」
```

### 8.4 視覺規範
- 沿用 Wave 6 Option B 深藍 B2B 風格
- HIGH=`danger` 紅 / MEDIUM=`warning` 琥珀 / LOW=`success` 綠
- 數字 `tabular-nums tracking-tight`
- 不加裝飾背景

### 8.5 側欄整合
```tsx
{
  label: "🎯 酒駕風險預測",
  icon: TrendingUp,
  visible: import.meta.env.VITE_ENABLE_PREDICTION === 'true',
}
```

---

## 9. 部署隔離

### 9.1 雙重防線
1. **編譯時排除**：`build_update.py --exclude prediction` 排除以下檔案：
   - `backend/app/ml/**`
   - `backend/scripts/daily_predict_dui.py`
   - `backend/scripts/retrain_dui_model.py`
   - `backend/scripts/init_prediction_schema.py`
   - `backend/scripts/fetch_cwa_history.py`
   - `backend/scripts/build_calendar.py`
   - `backend/app/api/prediction.py`（或從 `main.py` router include 條件式排除）
   - `animal-crossing-dashboard/src/components/DuiPredictionPage.tsx`
   - `backend/app/services/dui_predictor_svc.py`
   - `backend/app/schemas/prediction.py`
   - `requirements_ml.txt`
2. **執行時 feature flag**：`VITE_ENABLE_PREDICTION=false` 隱藏側欄項目，防漏排檔案被誤觸發。

### 9.2 你的本機建構
```bash
# 全功能（含預測）— 你自己用
python build_update.py

# 同事版（無預測）
python build_update.py --exclude prediction
```

### 9.3 個資與安全
- `.pkl`、`backend/models/`、`dui_predictions` 加進 `.gitignore`
- CWA API 金鑰存 `.env`（已 gitignored）
- 個資原則沿用既有：`.xls/.xlsx/.csv/.db` 排除規則不變

---

## 10. 環境準備

### 10.1 ML 專用 venv
```bash
py -3.12 -m venv D:\Programming\精準執法儀表板系統\.venv-ml
.venv-ml\Scripts\pip install -r requirements_ml.txt
```

### 10.2 `requirements_ml.txt`
```
xgboost>=2.1.0,<3.0
scikit-learn>=1.5.0,<2.0
shap>=0.46.0
pandas>=2.0
joblib>=1.4
holidays>=0.50
lunardate>=0.2.2
requests
pyarrow  # parquet cache
```

### 10.3 硬體驗證（i5-13500 / 16GB / 906GB free）
- 訓練：~3-4 分鐘
- 每日批次：< 5 秒
- 模型檔：< 50MB
- 特徵 cache：< 500MB
- **無需 GPU**

---

## 11. 監控與健康檢查

| 監控項 | 機制 | UI 表現 |
|---|---|---|
| 預測新鮮度 | `dui_predictions.generated_at` | KPI 顯示更新時間，>25h 變紅 |
| 氣象新鮮度 | `ext_weather.date` 最新 | banner 警告「氣象資料過期」 |
| 模型漂移 | 每月重訓比較 Recall 差距 | eval_report 標記，差距 >5% 提示 |
| 重入鎖殘留 | `system_locks.locked_at` >10 分鐘自動視為失效 | 自動釋放 |

---

## 12. 風險清單

| 風險 | 機率 | 影響 | 緩解 |
|---|---|---|---|
| 小型派出所樣本不足（如山上分駐所） | 中 | 該所預測不準 | 用 `group_name` 4 管區層級補強 |
| CWA API 限流/停機 | 低 | 氣象特徵缺漏 | 缺值用上週同班別均值 fallback；訓練時加少量 missing 樣本 |
| `--exclude` 漏排檔案 | 中 | 同事看到不該看的 | 雙防線 + CI 檢查清單 + 部署前 dry-run 驗證 |
| 過度依賴 AI | 中 | 決策誤判 | UI 永遠顯示模型版本 + 訓練資料截止日 + 「僅供參考」字樣 |
| 過度攔查影響觀感 | 中 | 民怨 | HIGH/MEDIUM/LOW 三級供你裁量，不強制 |
| 連假後資料 gap | 低 | 預測過期 | 首頁觸發機制偵測 >3 天 gap 時補抓氣象 |
| 模型版本不相容 | 低 | 載入失敗 | 訓練/部署皆用 Python 3.12.7 + 套件版本鎖定 |

---

## 13. v1.0 完成定義 (Definition of Done)

- [ ] 5 年特徵集 + ext_weather + ext_calendar 全部入 DB
- [ ] 訓練腳本一鍵跑完，Recall ≥ 80%
- [ ] FastAPI 5 個端點（含 /status）上線並通過 manual test
- [ ] `DuiPredictionPage` 4 個區段顯示正確
- [ ] Dashboard 首頁開啟時自動偵測+背景刷新，連續 5 工作日驗證無誤
- [ ] Process lock 機制防重入驗證
- [ ] `build_update.py --exclude prediction` 對同事版驗證沒洩漏（dry-run + 實機驗證）
- [ ] `DuiPredictionPage` 加「前往執法缺口酒駕分析 →」連結卡片
- [ ] `AccidentAnalysisPage` 酒駕分析 tab 末尾加「前往酒駕風險預測 →」連結（受 `VITE_ENABLE_PREDICTION` 控制顯示）
- [ ] 撰寫 `docs/dui_prediction_user_guide.md` 給未來的你/接手人

---

## 14. 後續迭代路線

| 優先 | 項目 | 觸發條件 |
|---|---|---|
| 🟢 P0 | 本 v1.0 全部 | 本次完成 |
| 🟢 P0 | 與 `AccidentAnalysisPage` 酒駕分析 tab 雙向 deep-link（互相導引按鈕） | 本次完成（輕度整合） |
| 🟡 P1 | 「採納為勤務點」串實際勤務派班系統 | 與資訊室談 API 之後 |
| 🟡 P1 | 預測結果接進既有 AI 報告（`ReportSummary.dui_predictions`） | v1 上線穩定 1 個月後 |
| 🟡 P1 | 評估是否將「執法缺口的酒駕分析 tab」與本預測頁整併成「酒駕情報中心」 | v1 上線使用 1-2 個月後，依使用習慣再決定 |
| 🔵 P2 | 模型 A/B 測試（XGBoost vs LightGBM） | Recall 卡關 80% 才考慮 |
| 🔵 P2 | 即時氣象（每小時 vs 每日） | CWA API 配額允許 |
| ⚪ P3 | 跨分局推廣 | 你需要時 |

---

## 15. 變更紀錄

| 日期 | 版本 | 變更 |
|---|---|---|
| 2026-04-27 | v1.0 | 初版設計（brainstorming session） |
