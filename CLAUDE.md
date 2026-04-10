# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## AI 助理設定

- **回應語言**：繁體中文（所有解說、註解、commit message 皆使用繁體中文）
- **程式碼註解**：繁體中文
- **Git Commit**：繁體中文

## 專案概述

**系統名稱**：精準執法儀表板系統
**用途**：交通事故及舉發違規分析，用於精準執法決策支援（非車流量分析）
**使用單位**：臺南市警察局新化分局
**UI 風格**：Animal Crossing（動物森友會）主題
**GitHub**：https://github.com/AweiMike/AI-powered-Traffic-Enforcement.git

## 技術架構

### 後端
- **框架**：FastAPI
- **語言**：Python 3.10+
- **資料庫**：SQLite（單一檔案 `backend/data/traffic_enforcement.db`）
- **ORM**：SQLAlchemy 2.0+
- **Production Port**：80（可攜式部署）/ 8000（開發模式）

### 前端
- **框架**：React 18 + TypeScript
- **打包工具**：Vite
- **樣式**：Tailwind CSS（自定義 nook-* 色彩）
- **圖示**：Lucide React
- **地圖**：React Leaflet + Leaflet
- **開發 Port**：5173

### 生產模式
Vite build 輸出到 `backend/static/`，FastAPI 同時 serve SPA + API（單一 port 80）。

## 核心概念

### 12 班別制度
時間分為 12 個班別，每班 2 小時：
- 班別 01-02：深夜（00:00-04:00）
- 班別 03-04：清晨（04:00-08:00）
- 班別 05-06：上午（08:00-12:00）
- 班別 07-08：下午（12:00-16:00）
- 班別 09-10：傍晚（16:00-20:00）
- 班別 11-12：夜間（20:00-00:00）

### 三大主題
1. **酒駕 (DUI)** — 最高優先級
2. **闘紅燈 (RED_LIGHT)** — 路口號誌執法
3. **危險駕駛 (DANGEROUS_DRIVING)** — 測速及危險行為

### 關鍵指標
- **VPI** (Violation Pressure Index)：違規壓力指數 = 違規數 × 主題權重
- **CRI** (Crash Risk Index)：事故風險指數 = 事故數 × 平均嚴重度
- **Score**：綜合評分 = α × VPI + β × CRI

### 事故嚴重度
- **A1**：死亡事故（權重 5）
- **A2**：受傷事故（權重 3）
- **A3**：財損事故（權重 1）

### 年齡分組
- <18 / 18-24 / 25-44 / 45-64 / 65+ / 未知
- `is_elderly`：65 歲以上
- `is_youth`：未滿 18 歲

### 資料隱私
系統完全去識別化：
- 無姓名、身分證、車牌
- 無精確地址（僅路段/路口）
- 僅年齡組（非精確年齡）
- 僅統計分析，無個案查詢

## 目錄結構

```
精準執法儀表板系統/
├── backend/                        # 後端 FastAPI
│   ├── app/
│   │   ├── main.py                # 主程式入口（含 SPA 靜態檔 serve）
│   │   ├── config.py              # 設定（SQLite 連線）
│   │   ├── database.py            # 資料庫連線
│   │   ├── api/                   # API 路由
│   │   │   ├── stats.py           # 統計 + data-info API
│   │   │   ├── topics.py          # 主題 API
│   │   │   ├── recommendations.py # 推薦 + 熱點 + 地圖 API
│   │   │   ├── hotspots.py        # 事故/違規熱點（GPS 聚類）
│   │   │   ├── enforcement.py     # 執法成效（酒駕/大型車）
│   │   │   ├── evehicle.py        # 青少年微電車分析
│   │   │   ├── imports.py         # 資料匯入 API（含批次）
│   │   │   ├── report.py          # AI 報告生成
│   │   │   └── admin.py           # 系統管理（重置 DB）
│   │   └── models/                # SQLAlchemy 模型
│   │       ├── core.py            # Crash, Ticket, Topic
│   │       ├── dimension.py       # Site, Unit, Shift
│   │       └── aggregate.py       # SiteMetrics, DailyStats
│   ├── scripts/
│   │   └── import_data.py         # CLI 匯入工具（--crash / --ticket）
│   ├── data/                      # SQLite DB（gitignore）
│   ├── static/                    # Vite build 輸出（gitignore）
│   └── requirements.txt
│
├── animal-crossing-dashboard/      # 前端 React
│   ├── src/
│   │   ├── App.tsx                # 主應用（路由 + 側欄 + DataInfo）
│   │   ├── api/client.ts          # API 客戶端
│   │   ├── hooks/useAPI.ts        # React Hooks
│   │   └── components/
│   │       ├── AccidentAnalysisPage.tsx    # 事故熱點分析
│   │       ├── PerformanceComparisonPage.tsx # 綜合執法成效
│   │       ├── DuiPerformancePage.tsx      # 酒駕防制成效
│   │       ├── HeavyVehiclePerformancePage.tsx # 大型車防制
│   │       ├── EVehicleAnalysisPage.tsx    # 青少年微電車專區
│   │       ├── ElderlyPreventionPage.tsx   # 高齡者防治
│   │       ├── MapViewPage.tsx             # 全螢幕地圖
│   │       ├── AIReportPage.tsx            # AI 分析報告
│   │       ├── DataImportPage.tsx          # 資料匯入頁面
│   │       ├── DateRangePicker.tsx         # 日期範圍選擇器
│   │       ├── HotspotRankingCard.tsx      # 熱點排名卡片
│   │       ├── StatCard.tsx / Top5Card.tsx / BriefingCard.tsx
│   │       ├── ShiftSelector.tsx / TopicSelector.tsx
│   │       └── MonthlyComparison.tsx / HotspotMap.tsx
│   └── package.json
│
├── build_portable.py              # 可攜式部署打包工具
├── start.bat                      # 唯一啟動入口
├── CLAUDE.md                      # 本檔案
└── .gitignore
```

## 前端頁面與路由

App.tsx 使用 sidebar 導覽，view state 切換頁面：

| view ID | 頁面 | 說明 |
|---------|------|------|
| `dashboard` | 總覽 | StatCard 統計卡片 |
| `accidents` | AccidentAnalysisPage | 事故熱點（GPS 100m 聚類排名） |
| `map` | MapViewPage | 全螢幕地圖（唯讀可用） |
| `elderly` | ElderlyPreventionPage | 高齡者事故分析 |
| `evehicle` | EVehicleAnalysisPage | 青少年微電車專區 |
| `dui` | DuiPerformancePage | 酒駕防制成效 |
| `heavy-vehicle` | HeavyVehiclePerformancePage | 大型車防制 |
| `monthly` | PerformanceComparisonPage | 綜合執法成效（含 CSV 匯出） |
| `ai-report` | AIReportPage | AI 報告（admin only） |
| `import` | DataImportPage | 資料匯入（admin only） |

### 唯讀模式
URL hash `#view` 啟用唯讀模式，隱藏 admin 功能（匯入、AI 報告）。
管理員登入：xinhua / xinhua3736

### DateRangePicker
共用元件，支援預設（本週/本月/本季/本年/30天/90天/180天）和自定日期範圍。

### Sidebar DataInfo
App.tsx 側欄底部顯示資料涵蓋日期範圍、筆數、最後上傳時間。

## API 端點

### 系統
- `GET /` — 系統資訊
- `GET /health` — 健康檢查

### 統計 `/api/v1/stats`
- `GET /overview` — 總覽統計
- `GET /monthly` — 月度統計
- `GET /elderly` — 高齡者統計
- `GET /shifts` — 班別統計
- `GET /violations` — 違規分類
- `GET /data-info` — 資料涵蓋範圍（日期、筆數、最後上傳時間）

### 主題 `/api/v1/topics`
- `GET /` — 所有主題
- `GET /{topic_code}/stats` — 主題統計
- `GET /{topic_code}/trends` — 主題趨勢

### 推薦 `/api/v1/recommendations`
- `GET /top5` — Top 5 推薦點位
- `GET /heatmap` — 熱力圖資料
- `GET /briefing-card` — 班前勤務建議卡
- `GET /accidents/hotspots` — 事故熱點
- `GET /accidents/peak-times/{district}` — 分區尖峰時段
- `GET /cross-analysis` — 時段/行政區交叉分析
- `GET /analysis/elderly-vehicle-types` — 高齡者車種
- `GET /analysis/dui-environment` — 酒駕環境因素
- `GET /map/points` — 地圖資料點
- `GET /map/heatmap-data` — 地圖熱力圖
- `PUT /map/crash/{crash_id}/coordinates` — 更新事故座標
- `PUT /map/crashes/coordinates/batch` — 批次更新座標

### 熱點 `/api/v1/hotspots`
- `GET /accident-hotspots` — 事故熱點排名（GPS 100m 聚類）
- `GET /ticket-hotspots` — 違規熱點排名
- `GET /hotspot-overlap` — 事故＋違規重疊分析
- `GET /a1-accident-list` — A1 死亡事故清單

### 執法成效 `/api/v1/enforcement`
- `GET /dui` — 酒駕防制成效
- `GET /heavy-vehicle` — 大型車防制成效

### 微電車 `/api/v1/evehicle`
- `GET /overview` — 微電車總覽
- `GET /youth-hotspots` — 青少年熱點
- `GET /time-analysis` — 時段分析
- `GET /violation-types` — 違規類型
- `GET /age-distribution` — 年齡分佈
- `GET /youth-age-breakdown` — 青少年年齡細分
- `GET /yearly-trend` — 年度趨勢

### 資料匯入 `/api/v1/import`
- `POST /crash` — 匯入事故檔案（.xlsx/.xls/.txt）
- `POST /crash/batch` — 批次匯入事故資料夾
- `POST /ticket` — 匯入舉發檔案（.xlsx/.xls）
- `POST /ticket/batch` — 批次匯入舉發資料夾
- `GET /status` — 資料庫統計狀態

### 管理 `/api/v1/admin`
- `POST /reset-database` — 重置資料庫

## 資料匯入

### 資料來源格式

| 類型 | 來源 | 格式 | 匯入方式 |
|------|------|------|----------|
| 事故（EIS） | 警政署 EIS 事故調查表匯出 | TXT（@ 分隔） | 放入「事故調查表資料/」→ 批次匯入 |
| 事故（分局） | 交通事故案件清冊 | .xls | 單檔上傳 |
| 舉發 | 舉發案件綜合查詢 | .xlsx | 單檔上傳或放入「舉發案件綜合查詢/」→ 批次匯入 |

### CLI 匯入（import_data.py）
```bash
cd backend
python scripts/import_data.py --crash "事故.xls" --ticket "舉發.xlsx"
python scripts/import_data.py --init  # 僅初始化資料庫
```

### 網頁匯入（DataImportPage）
- 單檔上傳：拖放或選擇檔案
- 批次匯入：一鍵匯入對應資料夾中所有檔案
- 批次事故：讀取「事故調查表資料/」中的 .txt 檔
- 批次舉發：讀取「舉發案件綜合查詢/」中的 .xlsx 檔

### 匯入處理流程
1. 自動偵測格式（EIS / LEGACY）
2. 去重（案件編號 / 舉發單號）
3. 去識別化（移除個資）
4. 時間轉換（民國年 → 西元）
5. 班別計算（12 班制）
6. 主題分類（酒駕/闘紅燈/危險駕駛）
7. GPS 座標驗證 + 區域中心備援
8. 慢車/微電車分類
9. 批次追蹤（import_batch_id）

## 事故熱點排名（GPS 聚類）

`backend/app/api/hotspots.py` 使用 GPS 座標聚類（100m 半徑）取代文字分組：
- `cluster_crashes_by_gps()` — 以第一筆 GPS 為 seed，將 100m 內的事故歸為同一群
- `_pick_best_location()` — 從群中選擇最佳地名（優先路口格式）
- 基線比較使用 200m matching distance
- 排名依事故數排序

## 資料庫模型

### 核心表
```python
class Crash(Base):  # core_crash
    case_id, import_batch_id
    occurred_date, occurred_time, shift_id
    district, location_desc, latitude, longitude
    severity (A1/A2/A3), severity_weight (5/3/1)
    driver_age_group, is_elderly, is_youth, driver_gender
    party_type, evehicle_type, is_underage_14
    cause, weather, light, suspected_alcohol
    precinct, sub_unit, death_count, injury_count
    year, month, day_of_week

class Ticket(Base):  # core_ticket
    ticket_number, import_batch_id
    violation_date, violation_time, shift_id
    district, location_desc, latitude, longitude
    violation_code, violation_name
    topic_dui, topic_red_light, topic_dangerous
    driver_age, driver_age_group, is_elderly, is_youth
    driver_gender, vehicle_type
    evehicle_type, evehicle_violation
    unit_code, year, month, day_of_week

class Topic(Base):  # dim_topic
    topic_code (DUI/RED_LIGHT/DANGEROUS_DRIVING)
    topic_name, priority, icon_emoji, color_hex
```

### 維度表
```python
class Site(Base):   # dim_site — 執法點位
class Unit(Base):   # dim_unit — 執法單位（派出所）
class Shift(Base):  # dim_shift — 班別定義 (01-12)
```

## 部署

### 開發模式
```bash
# 後端
cd backend && python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# 前端
cd animal-crossing-dashboard && npm install && npm run dev
```

### 生產模式（可攜式部署）
使用 `build_portable.py` 打包，產出 `deploy/精準執法儀表板/`：
- 內嵌 Python 3.12.7 Embeddable（免安裝）
- `啟動儀表板.bat` — 啟動 uvicorn port 80 + 自動開瀏覽器
- `匯入資料.bat` — 資料匯入工具

```bash
# 打包步驟
cd animal-crossing-dashboard && npx vite build --outDir ../backend/static
cd .. && python build_portable.py
```

### 啟動入口
`start.bat` 是唯一啟動腳本入口（勿新增其他 .bat）。

## 注意事項

1. **資料隱私**：系統設計為完全去識別化，不儲存任何個資
2. **敏感檔案**：.xls/.xlsx/.csv/.db 均在 .gitignore 中，禁止 commit
3. **SQLite 限制**：適合中小規模資料（<50 萬筆）
4. **定期備份**：SQLite 為單一檔案，直接複製 `backend/data/traffic_enforcement.db`

## 常用命令

```bash
# 啟動後端（開發模式）
cd backend && venv\Scripts\activate && python -m uvicorn app.main:app --reload --port 8000

# 啟動前端
cd animal-crossing-dashboard && npm run dev

# 前端 build（生產）
cd animal-crossing-dashboard && npx vite build --outDir ../backend/static

# 匯入資料（CLI）
cd backend && venv\Scripts\activate
python scripts/import_data.py --crash "事故.xls" --ticket "舉發.xlsx"

# 打包可攜式部署
python build_portable.py
```

---

*最後更新：2026-04-10*
