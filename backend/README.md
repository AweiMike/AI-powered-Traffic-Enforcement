# 精準執法儀表板系統 - 後端 API

> 🔒 **個資保護等級：高（完全去識別化）**

## 系統定位

**統計分析 + 精準執法建議工具**

- ✅ 統計去年同期比較
- ✅ 分析違規態勢率
- ✅ 精準打擊酒駕
- ✅ 高齡者事故防治
- ✅ Top 5 點位推薦
- ❌ 不包含個案查詢（已有內建系統）

---

## 技術堆疊

- **框架**：FastAPI 0.104+
- **資料庫**：PostgreSQL 14+ with PostGIS
- **ORM**：SQLAlchemy 2.0+
- **Python**：3.10+

---

## 快速開始

### 1. 環境設定

```bash
# 創建虛擬環境
cd backend
python -m venv venv

# 啟動虛擬環境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt
```

### 2. 資料庫設定

```bash
# 創建 PostgreSQL 資料庫
psql -U postgres
CREATE DATABASE traffic_enforcement;
\q

# 配置環境變數
cp .env.example .env
# 編輯 .env，設定資料庫連線資訊
```

### 3. 初始化資料庫

```bash
# 執行初始化腳本
python backend/scripts/init_database.py

# 預期輸出：
# ✅ PostgreSQL 連線成功
# ✅ PostGIS 擴展已啟用
# ✅ 所有資料表創建完成（12 個表）
# ✅ 班別資料初始化完成（12 筆）
# ✅ 違規條款資料初始化完成（7 筆示例）
```

### 4. 匯入資料

```bash
# 匯入 Excel 資料（完全去識別化）
python backend/scripts/import_data.py

# 參數說明：
# --crash-file: 交通事故 Excel 檔案路徑
# --ticket-file: 舉發案件 Excel 檔案路徑
# --cluster-radius: 點位聚合半徑（預設 100 公尺）

# 範例：
python backend/scripts/import_data.py \
  --crash-file "data/交通事故案件清冊_已處理.xlsx" \
  --ticket-file "data/舉發案件綜合查詢_已處理.xlsx"
```

### 5. 啟動伺服器

```bash
# 開發模式（自動重載）
python backend/app/main.py

# 或使用 uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 訪問 API 文件
http://localhost:8000/docs
```

---

## API 端點

### 系統資訊

- `GET /` - 系統資訊（含個資保護說明）
- `GET /health` - 健康檢查

### 主題管理 (`/api/v1/topics`)

- `GET /api/v1/topics` - 取得所有主題
- `GET /api/v1/topics/{topic_code}` - 取得主題詳細資訊
- `GET /api/v1/topics/{topic_code}/stats` - 主題統計（支援班別過濾）
- `GET /api/v1/topics/{topic_code}/trends` - 主題趨勢（去年同期比較）

### 統計分析 (`/api/v1/stats`)

- `GET /api/v1/stats/overview` - 總覽統計
- `GET /api/v1/stats/monthly?year=2025&month=1` - 月度統計（含同期比較）
- `GET /api/v1/stats/elderly` - 高齡者統計
- `GET /api/v1/stats/shifts` - 班別分析（12班制）

### 推薦系統 (`/api/v1/recommendations`)

- `GET /api/v1/recommendations/top5` - Top 5 推薦點位
  - 參數：`topic_code`, `shift_id`, `days`
  - 返回：VPI/CRI/Score 及推薦點位
- `GET /api/v1/recommendations/heatmap` - 熱力圖資料
- `GET /api/v1/recommendations/briefing-card` - 班前勤務建議卡

---

## 主題代碼

系統支援三大主題：

| 代碼 | 名稱 | Emoji | VPI 權重 | Score 配置 |
|------|------|-------|---------|-----------|
| `DUI` | 酒駕精準打擊 | 🍺 | 10.0 | 0.7×VPI + 0.3×CRI |
| `RED_LIGHT` | 闖紅燈防制 | 🚦 | 2.0 | 0.6×VPI + 0.4×CRI |
| `DANGEROUS_DRIVING` | 危險駕駛防制 | ⚡ | 1.5 | 0.5×VPI + 0.5×CRI |

---

## 班別系統（12班制）

| 班別 ID | 時間範圍 | 時段 |
|---------|---------|------|
| 01 | 00:00-02:00 | 深夜 |
| 02 | 02:00-04:00 | 深夜 |
| 03 | 04:00-06:00 | 清晨 |
| 04 | 06:00-08:00 | 清晨 |
| 05 | 08:00-10:00 | 上午 |
| 06 | 10:00-12:00 | 上午 |
| 07 | 12:00-14:00 | 下午 |
| 08 | 14:00-16:00 | 下午 |
| 09 | 16:00-18:00 | 傍晚 |
| 10 | 18:00-20:00 | 傍晚 |
| 11 | 20:00-22:00 | 夜間 |
| 12 | 22:00-00:00 | 夜間 |

---

## 指標計算

### VPI (Violation Pressure Index)

```
VPI = 違規案件數 × 主題權重

主題權重：
- DUI: 10.0（最高優先）
- RED_LIGHT: 2.0
- DANGEROUS_DRIVING: 1.5
```

### CRI (Crash Risk Index)

```
CRI = 事故案件數 × 平均嚴重度

嚴重度權重：
- A1（死亡）: 5
- A2（受傷）: 3
- A3（財損）: 1
```

### Score (綜合評分)

```
Score = α × VPI + β × CRI

權重配置：
- DUI: 0.7 × VPI + 0.3 × CRI（著重違規）
- RED_LIGHT: 0.6 × VPI + 0.4 × CRI
- DANGEROUS_DRIVING: 0.5 × VPI + 0.5 × CRI（均衡）
```

---

## 資料庫結構

### 核心事實表（完全去識別化）

#### `core_crash` - 交通事故
- ❌ 無個資：無姓名、身分證、車號、聯絡方式
- ✅ 保留：日期時間、班別、行政區、路口/路段（無門牌號）、嚴重度、年齡組、性別

#### `core_ticket` - 舉發案件
- ❌ 無個資：無舉發單號、車號、駕駛人姓名、身分證
- ✅ 保留：日期時間、班別、行政區、路口/路段、違規條款、年齡組、性別

### 維度表（無個資）

- `dim_site` - 執法點位（聚合點位）
- `dim_unit` - 舉發單位
- `dim_shift` - 班別（12班制）
- `dim_violation_code` - 違規條款

### 聚合統計表（無個資）

- `agg_site_metrics` - 點位指標（VPI/CRI/Score）
- `agg_daily_stats` - 每日統計
- `agg_monthly_stats` - 每月統計
- `agg_shift_stats` - 班別統計

---

## 個資保護措施

### 完全移除的個資

- ❌ 案件編號 / 舉發單號
- ❌ 姓名
- ❌ 身分證字號
- ❌ 車號
- ❌ 聯絡方式（電話、地址）
- ❌ 承辦人資訊
- ❌ 繳款資訊

### 去識別化處理

#### 地址
- **原始**：台南市新化區中正路123號前
- **去識別化**：行政區：新化區 / 地點：中正路（近中山路路口）

#### 年齡
- **原始**：67歲
- **去識別化**：年齡組：65+ / 是否高齡者：是

### 保留統計必要欄位

- ✅ 日期時間、班別
- ✅ 行政區、路口/路段（無門牌號）
- ✅ 違規條款、事故嚴重度
- ✅ 年齡組（<18/18-24/25-44/45-64/65+）
- ✅ 性別（男/女/未知）

詳細說明請參閱：[個資保護說明.md](../個資保護說明.md)

---

## API 使用範例

### 取得 Top 5 推薦點位

```bash
# 酒駕主題，班別11（20:00-22:00），近30天
curl "http://localhost:8000/api/v1/recommendations/top5?topic_code=DUI&shift_id=11&days=30"

# 回應範例：
{
  "topic_code": "DUI",
  "shift_id": "11",
  "period": {
    "start_date": "2024-12-14",
    "end_date": "2025-01-13",
    "days": 30
  },
  "recommendations": [
    {
      "rank": 1,
      "site_id": 123,
      "site_name": "中正路與中山路路口",
      "district": "新化區",
      "location_desc": "中正路與中山路交叉口附近",
      "coordinates": {
        "latitude": 23.0386,
        "longitude": 120.3109
      },
      "metrics": {
        "vpi": 150.5,
        "cri": 12.3,
        "score": 109.04
      },
      "statistics": {
        "tickets": 15,
        "crashes": 4,
        "violation_days": 8,
        "avg_tickets_per_day": 0.5
      }
    }
    // ... Top 2-5
  ],
  "note": "推薦點位僅基於統計分析，無任何個資"
}
```

### 取得月度統計（含同期比較）

```bash
# 2025年1月統計
curl "http://localhost:8000/api/v1/stats/monthly?year=2025&month=1"

# 回應範例：
{
  "period": {
    "year": 2025,
    "month": 1
  },
  "current": {
    "tickets": 1234,
    "crashes": 56,
    "topics": {
      "dui": 26,
      "red_light": 478,
      "dangerous_driving": 730
    }
  },
  "last_year": {
    "year": 2024,
    "tickets": 1150,
    "crashes": 62
  },
  "comparison": {
    "tickets_change": 7.3,
    "crashes_change": -9.7,
    "tickets_trend": "上升",
    "crashes_trend": "下降"
  },
  "note": "僅統計分析，無個資"
}
```

### 取得班前勤務建議卡

```bash
# 酒駕主題，班別11，今日
curl "http://localhost:8000/api/v1/recommendations/briefing-card?topic_code=DUI&shift_id=11"

# 回應範例：
{
  "date": "2025-01-13",
  "shift": {
    "shift_id": "11",
    "shift_number": 11,
    "time_range": "20:00-22:00"
  },
  "topic": {
    "code": "DUI",
    "name": "酒駕精準打擊",
    "emoji": "🍺",
    "focus": "加強酒測攔檢"
  },
  "top5_sites": [
    // Top 5 推薦點位
  ],
  "notes": [
    "⚠️ 本建議基於近30日統計分析",
    "🎯 建議優先部署於 Top 3 點位",
    "👴 注意高齡駕駛人執法態度",
    "📊 執法後請回報實際成效"
  ],
  "privacy_note": "本建議卡無任何個資，僅統計分析資料"
}
```

---

## 開發指南

### 專案結構

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 應用程式
│   ├── config.py            # 配置設定
│   ├── database.py          # 資料庫連線
│   ├── api/                 # API 路由
│   │   ├── __init__.py
│   │   ├── topics.py        # 主題管理
│   │   ├── stats.py         # 統計分析
│   │   └── recommendations.py  # 推薦系統
│   └── models/              # 資料庫模型
│       ├── __init__.py
│       ├── core.py          # 核心事實表（去識別化）
│       ├── dimension.py     # 維度表
│       └── aggregate.py     # 聚合統計表
├── scripts/
│   ├── init_database.py     # 資料庫初始化
│   └── import_data.py       # Excel 資料匯入（去識別化）
├── requirements.txt
├── .env.example
└── README.md
```

### 添加新 API 端點

1. 在對應的路由文件中添加端點（`app/api/`）
2. 使用 `Depends(get_db)` 注入資料庫 session
3. 確保所有查詢和回應都不包含個資
4. 添加 `note` 欄位說明無個資

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db

router = APIRouter()

@router.get("/new-endpoint")
async def new_endpoint(db: Session = Depends(get_db)):
    # 實作查詢邏輯（確保無個資）
    return {
        "data": [],
        "note": "統計資料已完全去識別化"
    }
```

### 測試

```bash
# 執行測試（待實作）
pytest

# API 文件測試
# 訪問 http://localhost:8000/docs
# 使用 Swagger UI 測試各端點
```

---

## 常見問題

### Q: 如何更新違規條款資料？

A: 編輯 `scripts/init_database.py` 中的 `init_violation_codes()` 函數，或使用 SQL 直接更新 `dim_violation_code` 表。

### Q: 如何調整點位聚合半徑？

A: 在匯入資料時使用 `--cluster-radius` 參數：
```bash
python backend/scripts/import_data.py --cluster-radius 150
```

### Q: 如何定期更新聚合統計表？

A: 使用 `app/models/aggregate.py` 中的 `calculate_site_metrics()` 函數，可設定 cron job 定期執行。

### Q: 系統會儲存個資嗎？

A: **絕對不會**。本系統在資料匯入階段即完全去識別化，資料庫僅儲存統計必要欄位。詳見：[個資保護說明.md](../個資保護說明.md)

---

## 系統版本

- **版本**：v1.0.0
- **更新日期**：2026-01-13
- **個資保護等級**：高（完全去識別化）

---

## 授權與支援

本系統為台南市警察局新化分局內部使用工具。

如有問題請聯繫：系統管理員

---

🔒 **本系統設計確保無個資外洩風險**
