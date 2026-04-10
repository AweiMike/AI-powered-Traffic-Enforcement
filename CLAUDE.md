# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## AI 助理設定

- **回應語言**：繁體中文（所有解說、註解、commit message 皆使用繁體中文）
- **程式碼註解**：繁體中文
- **Git Commit**：繁體中文

## 專案概述

**系統名稱**：精準執法儀表板系統
**版本**：1.0.0-SQLite
**用途**：事故及舉發違規分析，用於精準執法（非車流量分析）
**UI 風格**：Animal Crossing（動物森友會）主題

## 技術架構

### 後端
- **框架**：FastAPI
- **語言**：Python 3.10+
- **資料庫**：SQLite（無需安裝 PostgreSQL）
- **ORM**：SQLAlchemy 2.0+
- **Port**：8000

### 前端
- **框架**：React 18 + TypeScript
- **打包工具**：Vite
- **樣式**：Tailwind CSS
- **圖示**：Lucide React
- **Port**：5173

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
1. 🍺 **酒駕 (DUI)** - 最高優先級，權重最高
2. 🚦 **闘紅燈 (RED_LIGHT)** - 路口號誌執法
3. ⚡ **危險駕駛 (DANGEROUS_DRIVING)** - 測速及危險行為

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
- `is_elderly`：65歲以上標記為高齡者

### 資料隱私
系統完全去識別化：
- ❌ 無姓名、身分證、車牌
- ❌ 無精確地址（門牌號）
- ❌ 無精確年齡（僅年齡組）
- ✅ 僅統計分析，無個案查詢

## 目錄結構

```
精準執法儀表板系統/
├── backend/                    # 後端 FastAPI
│   ├── app/
│   │   ├── main.py            # 主程式入口
│   │   ├── main_simple.py     # 簡化版（模擬數據）
│   │   ├── config.py          # 設定（SQLite 連線）
│   │   ├── database.py        # 資料庫連線
│   │   ├── api/               # API 路由
│   │   │   ├── topics.py      # 主題 API
│   │   │   ├── stats.py       # 統計 API
│   │   │   ├── recommendations.py  # 推薦 API
│   │   │   └── imports.py     # 資料匯入 API
│   │   └── models/            # 資料模型
│   │       ├── core.py        # 核心表（Crash, Ticket）
│   │       ├── dimension.py   # 維度表（Site, Shift, Unit）
│   │       └── aggregate.py   # 聚合表（SiteMetrics, MonthlyStats）
│   ├── scripts/
│   │   └── init_sqlite.py     # SQLite 初始化腳本
│   ├── data/
│   │   └── traffic_enforcement.db  # SQLite 資料庫檔案
│   └── requirements-sqlite.txt     # SQLite 版本依賴
│
├── animal-crossing-dashboard/  # 前端 React
│   ├── src/
│   │   ├── App.tsx            # 主應用程式
│   │   ├── api/client.ts      # API 客戶端
│   │   ├── hooks/useAPI.ts    # React Hooks
│   │   └── components/        # UI 組件
│   │       ├── StatCard.tsx
│   │       ├── Top5Card.tsx
│   │       ├── BriefingCard.tsx
│   │       ├── ShiftSelector.tsx
│   │       ├── TopicSelector.tsx
│   │       └── MonthlyComparison.tsx
│   └── package.json
│
├── 啟動系統.bat               # 主選單
├── 初始化資料庫.bat           # 初始化 SQLite
├── 安裝依賴.bat               # 安裝所有依賴
├── 啟動系統-簡化版.bat        # 模擬數據測試
└── CLAUDE.md                  # 本檔案
```

## API 端點

### 系統
- `GET /` - 系統資訊
- `GET /health` - 健康檢查（返回 database 類型）

### 統計 `/api/v1/stats`
- `GET /overview?days=30` - 總覽統計
- `GET /monthly/{year}/{month}` - 月度統計
- `GET /shift/{shift_id}` - 班別統計

### 主題 `/api/v1/topics`
- `GET /` - 所有主題
- `GET /{topic_code}/stats` - 主題統計

### 推薦 `/api/v1/recommendations`
- `GET /top5?shift_id=&topic=` - Top 5 推薦點位
- `GET /briefing-card?shift_id=` - 班前勤務建議卡

### 資料匯入 `/api/v1/import`
- `POST /crashes` - 匯入事故資料
- `POST /tickets` - 匯入舉發資料

## 資料庫模型

### 核心表
```python
# 交通事故（去識別化）
class Crash(Base):
    __tablename__ = "core_crash"
    occurred_date, occurred_time, shift_id
    district, location_desc, latitude, longitude
    severity (A1/A2/A3), severity_weight (5/3/1)
    driver_age_group, is_elderly, driver_gender

# 舉發案件（去識別化）
class Ticket(Base):
    __tablename__ = "core_ticket"
    violation_date, violation_time, shift_id
    district, location_desc, latitude, longitude
    violation_code, violation_name
    topic_dui, topic_red_light, topic_dangerous
```

### 維度表
```python
# 執法點位
class Site(Base):
    __tablename__ = "dim_site"
    site_name, district, latitude, longitude

# 班別定義
class Shift(Base):
    __tablename__ = "dim_shift"
    shift_id (01-12), start_hour, end_hour
```

## 前端組件

### 主要頁面
- **Dashboard**：總覽統計（使用 useOverview hook）
- **Top 5 推薦**：推薦執法點位（使用 useTop5 hook）
- **班前勤務卡**：勤務建議（使用 useBriefingCard hook）
- **違規分析**：違規統計
- **高齡者防治**：高齡事故分析
- **月度比較**：同期比較（使用 useMonthlyStats hook）

### API Hooks
```typescript
// hooks/useAPI.ts
useOverview(days: number)
useTop5(shift_id?: string, topic?: string)
useMonthlyStats(year: number, month: number)
useBriefingCard(shift_id: string)
useHealthCheck()
```

## 開發歷程

### 2025-01-14：SQLite 版本改版
**原因**：公司電腦無系統權限安裝 PostgreSQL

**變更**：
1. 資料庫從 PostgreSQL 改為 SQLite
2. 移除 PostGIS 依賴，改用經緯度欄位
3. 移除「交通流量」功能（與精準執法無關）
4. 前端副標題改為「事故與違規分析」
5. 所有前端組件確保實際連接 API

**修改檔案**：
- `backend/app/config.py` - SQLite 連線設定
- `backend/app/database.py` - 移除 geoalchemy2
- `backend/app/models/core.py` - geom → latitude/longitude
- `backend/app/models/dimension.py` - 移除 PostGIS
- `backend/app/main.py` - health check 顯示 db 類型
- `animal-crossing-dashboard/src/App.tsx` - 移除車流量

**新增檔案**：
- `backend/scripts/init_sqlite.py`
- `backend/requirements-sqlite.txt`
- `初始化資料庫.bat`
- `安裝依賴.bat`
- `使用說明-SQLite版本.md`
- `網路分享設定指南.md`
- `系統改版說明.md`

## 部署說明

### 本機使用
```batch
1. 安裝依賴.bat
2. 初始化資料庫.bat
3. 啟動系統.bat → 選擇 [1]
```

### 網路分享
1. 查詢本機 IP：`ipconfig`
2. 設定防火牆：允許 Port 8000, 5173
3. 修改 CORS：`backend/app/config.py` 添加 IP
4. 其他電腦訪問：`http://主機IP:5173`

### 資料庫位置
```
backend/data/traffic_enforcement.db
```

### 備份
```batch
copy backend\data\traffic_enforcement.db backup\
```

## 注意事項

1. **資料隱私**：系統設計為完全去識別化，不儲存任何個資
2. **主機保持運行**：關機後其他電腦無法連線
3. **定期備份**：SQLite 是單一檔案，直接複製即可
4. **效能限制**：SQLite 適合中小規模資料（<50萬筆）

## 常用命令

```batch
# 啟動後端（開發模式）
cd backend
venv\Scripts\activate
python app\main.py

# 啟動前端
cd animal-crossing-dashboard
npm run dev

# 初始化資料庫
cd backend
venv\Scripts\activate
python scripts\init_sqlite.py
```

## 聯繫資訊

如有問題，請檢查：
1. 後端視窗錯誤訊息
2. 前端 Console (F12)
3. 資料庫檔案是否存在

---

*最後更新：2025-01-14*
