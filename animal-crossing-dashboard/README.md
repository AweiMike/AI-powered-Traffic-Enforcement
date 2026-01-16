# 精準執法儀表板系統 - 前端

> 🌿 動森風格的交通執法數據可視化儀表板

## 特色

- ✅ 動物森友會主題設計
- ✅ 連接 FastAPI 後端 API
- ✅ 完整的個資保護（無個資顯示）
- ✅ Top 5 推薦點位可視化
- ✅ 班前勤務建議卡生成
- ✅ 月度同期比較圖表
- ✅ 12班制班別選擇器

## 技術堆疊

- **框架**: React 18 + TypeScript
- **構建工具**: Vite
- **樣式**: Tailwind CSS
- **圖標**: Lucide React
- **狀態管理**: React Hooks

## 快速開始

### 1. 安裝依賴

```bash
cd animal-crossing-dashboard
npm install
```

### 2. 配置環境變數

```bash
cp .env.example .env
```

編輯 `.env` 設定後端 API 地址：
```env
VITE_API_BASE_URL=http://localhost:8000
```

### 3. 啟動開發伺服器

```bash
npm run dev
```

前端將運行在 `http://localhost:3000`

### 4. 構建生產版本

```bash
npm run build
```

構建產物將輸出到 `dist/` 目錄

## 專案結構

```
animal-crossing-dashboard/
├── src/
│   ├── api/
│   │   └── client.ts          # API 客戶端
│   ├── hooks/
│   │   └── useAPI.ts           # React Hooks
│   ├── components/
│   │   ├── StatCard.tsx        # 統計卡片
│   │   ├── Top5Card.tsx        # Top 5 推薦卡片
│   │   ├── BriefingCard.tsx    # 班前勤務建議卡
│   │   ├── ShiftSelector.tsx   # 班別選擇器
│   │   ├── TopicSelector.tsx   # 主題選擇器
│   │   └── MonthlyComparison.tsx # 月度比較
│   ├── App.tsx                 # 主應用程式
│   ├── main.tsx                # 入口文件
│   └── index.css               # 全局樣式
├── public/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```

## 核心組件

### API Client (`src/api/client.ts`)

提供完整的後端 API 封裝：

```typescript
import { apiClient } from '@/api/client';

// 取得總覽統計
const overview = await apiClient.getOverview(30);

// 取得 Top 5 推薦
const top5 = await apiClient.getTop5('DUI', '11', 30);

// 取得班前勤務建議卡
const briefing = await apiClient.getBriefingCard('DUI', '11');
```

### React Hooks (`src/hooks/useAPI.ts`)

提供便捷的 React Hooks：

```typescript
import { useOverview, useTop5, useBriefingCard } from '@/hooks/useAPI';

// 在組件中使用
const { data, loading, error, refetch } = useOverview(30);
```

### 組件

#### StatCard - 統計卡片
顯示關鍵指標，支持趨勢顯示

#### Top5Card - Top 5 推薦卡片
顯示推薦執法點位的 VPI/CRI/Score

#### BriefingCard - 班前勤務建議卡
生成完整的勤務建議，包含 Top 5 推薦點位

#### ShiftSelector - 班別選擇器
12班制選擇器，支持全時段選項

#### TopicSelector - 主題選擇器
三大主題選擇：酒駕、闖紅燈、危險駕駛

#### MonthlyComparison - 月度比較
顯示當月與去年同期的統計比較

## 主題配置

動森風格色彩配置（`tailwind.config.js`）：

```js
colors: {
  'nook-cream': '#FDF6E3',
  'nook-leaf': '#7ABB6A',
  'nook-sky': '#87CEEB',
  'nook-bell': '#FFD700',
  'nook-text': '#5D4037',
  'nook-red': '#E57373',
  'nook-orange': '#FFB74D',
}
```

## API 使用範例

### 取得總覽統計

```typescript
const { data, loading, error } = useOverview(30);

if (loading) return <div>載入中...</div>;
if (error) return <div>錯誤: {error.message}</div>;

return (
  <div>
    <p>違規案件: {data.tickets.total}</p>
    <p>交通事故: {data.crashes.total}</p>
  </div>
);
```

### 取得 Top 5 推薦

```typescript
const [topic, setTopic] = useState<TopicCode>('DUI');
const [shift, setShift] = useState<string>('11');

const { data: top5 } = useTop5(topic, shift, 30);

return (
  <Top5List
    recommendations={top5?.recommendations || []}
    topicEmoji="🍺"
    topicColor="bg-nook-red"
  />
);
```

### 取得班前勤務建議卡

```typescript
const { data: briefing } = useBriefingCard('DUI', '11');

return <BriefingCard data={briefing} />;
```

## 開發指南

### 添加新組件

1. 在 `src/components/` 創建組件文件
2. 使用 TypeScript 定義 Props 介面
3. 使用 Tailwind CSS 動森風格類名
4. 確保響應式設計

### 添加新 API 端點

1. 在 `src/api/client.ts` 添加新方法
2. 在 `src/hooks/useAPI.ts` 添加對應 Hook
3. 更新 TypeScript 型別定義

### 樣式規範

- 使用 Tailwind CSS 類名
- 遵循動森風格配色
- 圓角統一使用 `rounded-2xl` 或 `rounded-3xl`
- 陰影使用 `nook-shadow` 類

## 個資保護

本系統前端完全不顯示任何個資：

- ✅ 僅顯示統計聚合數據
- ✅ 地址僅顯示行政區和路口（無門牌號）
- ✅ 年齡以分組顯示（<18/18-24/25-44/45-64/65+）
- ✅ 無任何姓名、身分證、車號等個資

每個 API 回應都包含 `note` 欄位說明資料已完全去識別化。

## 瀏覽器支持

- Chrome/Edge (最新版本)
- Firefox (最新版本)
- Safari (最新版本)

## 疑難排解

### API 連線失敗

檢查：
1. 後端伺服器是否已啟動 (`http://localhost:8000`)
2. `.env` 文件中的 API 地址是否正確
3. CORS 設定是否正確

### 樣式未生效

確認：
1. Tailwind CSS 已正確安裝
2. `tailwind.config.js` 配置正確
3. `index.css` 正確導入 Tailwind

## 授權

本系統為台南市警察局新化分局內部使用工具。

---

🌿 Made with Animal Crossing Style
