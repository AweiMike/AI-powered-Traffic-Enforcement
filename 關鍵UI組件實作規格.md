# 關鍵 UI 組件實作規格

> 📅 文件日期：2026-01-13
> 🎨 設計風格：Animal Crossing（動森風格）
> 🛠️ 技術棧：React.js / Vue.js + Tailwind CSS + Framer Motion
> 📄 相關文件：[動森風格_完整CSS主題包.css](動森風格_完整CSS主題包.css)

---

## 📦 組件總覽

本規格書涵蓋 **10 個核心 UI 組件**：

1. 主題切換器 (TopicSelector)
2. Top 5 推薦卡 (RecommendationCard)
3. 12 班別選擇器 (ShiftSelector)
4. 地圖標記組件 (MapMarker)
5. 載入動畫 (LoadingSpinner)
6. 統計儀表板 (StatsDashboard)
7. 篩選器面板 (FilterPanel)
8. 班前報表卡 (BriefingCard)
9. 熱力圖圖層控制器 (HeatmapControl)
10. 缺口警示卡 (GapAlertCard)

---

## 1. 主題切換器 (TopicSelector)

### 📋 功能說明

允許用戶在三大主題（酒駕/闖紅燈/危險駕駛）之間切換。

### 🎨 視覺設計

```
┌──────────────────────────────────────────────────────┐
│  請選擇執法主題：                                      │
├──────────────────────────────────────────────────────┤
│                                                      │
│   🍺                🚦                ⚡            │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐      │
│  │ 酒駕取締  │     │ 闖紅燈    │     │ 危險駕駛  │      │
│  │  26筆    │     │  478筆   │     │ 1,134筆 │      │
│  │  ⭐⭐⭐   │     │  ⭐⭐     │     │  ⭐⭐    │      │
│  └─────────┘     └─────────┘     └─────────┘      │
│   [已選取]         [選擇]          [選擇]           │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 🔧 組件 Props

```typescript
interface TopicSelectorProps {
  topics: Topic[];          // 主題列表
  selectedTopic: string;    // 當前選中的主題代碼
  onTopicChange: (topicCode: string) => void;  // 主題切換回調
  showCounts?: boolean;     // 是否顯示案件數
  showPriority?: boolean;   // 是否顯示優先級星星
}

interface Topic {
  code: string;             // 'DUI' | 'RED_LIGHT' | 'DANGEROUS_DRIVING'
  name: string;             // 中文名稱
  icon: string;             // Emoji 圖標
  count: number;            // 案件數
  priority: number;         // 優先級 1-5
  color: string;            // 主題色彩 (CSS變數名)
}
```

### 💻 React 實作範例

```jsx
import React, { useState } from 'react';
import { motion } from 'framer-motion';

const TopicSelector = ({ topics, selectedTopic, onTopicChange }) => {
  return (
    <div className="ac-topic-selector">
      {topics.map((topic) => (
        <motion.div
          key={topic.code}
          className={`ac-topic-card ${
            selectedTopic === topic.code ? 'active' : ''
          } topic-${topic.code.toLowerCase().replace('_', '-')}`}
          onClick={() => onTopicChange(topic.code)}
          whileHover={{ scale: 1.05, y: -8 }}
          whileTap={{ scale: 0.95 }}
          transition={{ type: 'spring', stiffness: 300 }}
        >
          <span className="ac-topic-icon">{topic.icon}</span>
          <div className="ac-topic-name">{topic.name}</div>
          <div className="ac-topic-count">{topic.count} 筆</div>
          <div className="ac-topic-priority">
            {'⭐'.repeat(topic.priority)}
          </div>
          {selectedTopic === topic.code && (
            <motion.div
              className="ac-topic-selected-indicator"
              layoutId="topic-indicator"
              style={{
                position: 'absolute',
                bottom: '8px',
                left: '50%',
                transform: 'translateX(-50%)',
                fontSize: '12px',
                color: 'var(--ac-primary)',
                fontWeight: 'bold',
              }}
            >
              [已選取]
            </motion.div>
          )}
        </motion.div>
      ))}
    </div>
  );
};

export default TopicSelector;
```

### 🎯 互動效果

- **懸停 (Hover)**：卡片上浮 8px，陰影加深
- **點擊 (Click)**：縮放到 95%，產生按壓感
- **選中狀態**：邊框高亮、背景填滿主題淺色
- **動畫**：使用 Framer Motion 的 `layoutId` 實現流暢指示器移動

### ✅ 驗收標準

- [ ] 三張卡片並排顯示（桌面版）
- [ ] 選中卡片邊框顏色正確對應主題色
- [ ] 切換動畫流暢（0.3秒過渡）
- [ ] 響應式：平板兩列、手機單列
- [ ] 無障礙：支持鍵盤導航 (Tab + Enter)

---

## 2. Top 5 推薦卡 (RecommendationCard)

### 📋 功能說明

顯示基於 Score 排序的前 5 名推薦執法點位。

### 🎨 視覺設計

```
┌────────────────────────────────────────────────┐
│ 🏆 第 1 名  ⭐⭐⭐      [詳情 →]                │
├────────────────────────────────────────────────┤
│                                                │
│  📍 臺南市新化區中正路 × 中山路 路口             │
│                                                │
│  ┌────────┬────────┬────────┬────────┐        │
│  │ 🎯分數  │ 🚨CRI  │ 📊VPI  │ 🍺酒駕  │        │
│  │  89    │  12    │  94    │  15筆  │        │
│  │ ▲+12   │ ▲+3    │ ▲+18   │ 近30日 │        │
│  └────────┴────────┴────────┴────────┘        │
│                                                │
│  💡 建議：夜間（21-03時）加強酒測攔檢            │
│  ⏰ 高發班別：班別11, 12, 01                    │
│  📈 趨勢：近30日上升 15%                        │
│                                                │
└────────────────────────────────────────────────┘
```

### 🔧 組件 Props

```typescript
interface RecommendationCardProps {
  rank: number;              // 排名 1-5
  site: RecommendationSite;  // 點位資訊
  topic: string;             // 當前主題
  onDetailClick?: () => void; // 點擊詳情按鈕回調
}

interface RecommendationSite {
  siteId: string;
  siteName: string;          // 地點名稱
  address: string;           // 完整地址
  score: number;             // 綜合評分
  cri: number;               // 事故風險指數
  vpi: number;               // 違規壓力指數
  topicCount: number;        // 該主題案件數
  scoreTrend: number;        // 分數趨勢 (+12)
  suggestion: string;        // 執法建議
  highRiskShifts: string[];  // 高發班別 ['11', '12', '01']
  trendPercentage: number;   // 趨勢百分比 (15)
}
```

### 💻 React 實作範例

```jsx
import React from 'react';
import { motion } from 'framer-motion';

const RecommendationCard = ({ rank, site, topic, onDetailClick }) => {
  const getRankIcon = (rank) => {
    const icons = ['🏆', '🥈', '🥉', '4️⃣', '5️⃣'];
    return icons[rank - 1] || '';
  };

  const getTrendColor = (trend) => {
    return trend > 0 ? 'var(--ac-danger)' : 'var(--ac-success)';
  };

  const getTrendIcon = (trend) => {
    return trend > 0 ? '▲' : '▼';
  };

  return (
    <motion.div
      className={`ac-recommendation-card topic-${topic.toLowerCase().replace('_', '-')}`}
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: rank * 0.1 }}
      whileHover={{ x: 4 }}
    >
      {/* 卡片頭部 */}
      <div className="ac-rec-header">
        <div className="ac-rec-rank">
          <span className="ac-rec-rank-icon">{getRankIcon(rank)}</span>
          <span>第 {rank} 名</span>
          <span className="ac-rec-priority">{'⭐'.repeat(Math.ceil(site.score / 20))}</span>
        </div>
        {onDetailClick && (
          <button className="ac-btn ac-btn-sm ac-btn-secondary" onClick={onDetailClick}>
            詳情 →
          </button>
        )}
      </div>

      {/* 地點資訊 */}
      <div className="ac-rec-location">
        📍 {site.siteName}
      </div>

      {/* 指標網格 */}
      <div className="ac-rec-metrics">
        <div className="ac-metric-item">
          <div className="ac-metric-label">🎯 分數</div>
          <div className="ac-metric-value">{site.score}</div>
          <div
            className="ac-metric-trend"
            style={{ color: getTrendColor(site.scoreTrend) }}
          >
            {getTrendIcon(site.scoreTrend)}+{Math.abs(site.scoreTrend)}
          </div>
        </div>

        <div className="ac-metric-item">
          <div className="ac-metric-label">🚨 CRI</div>
          <div className="ac-metric-value">{site.cri}</div>
        </div>

        <div className="ac-metric-item">
          <div className="ac-metric-label">📊 VPI</div>
          <div className="ac-metric-value">{site.vpi}</div>
        </div>

        <div className="ac-metric-item">
          <div className="ac-metric-label">
            {topic === 'DUI' ? '🍺' : topic === 'RED_LIGHT' ? '🚦' : '⚡'} 案件
          </div>
          <div className="ac-metric-value">{site.topicCount}筆</div>
          <div className="ac-metric-trend" style={{ fontSize: '10px' }}>
            近30日
          </div>
        </div>
      </div>

      {/* 執法建議 */}
      <div className="ac-rec-suggestion">
        <div className="ac-rec-suggestion-title">💡 建議</div>
        <div>{site.suggestion}</div>
        <div style={{ marginTop: '8px', fontSize: '14px' }}>
          ⏰ 高發班別：{site.highRiskShifts.join(', ')}
        </div>
        <div style={{ marginTop: '4px', fontSize: '14px' }}>
          📈 趨勢：近30日{site.trendPercentage > 0 ? '上升' : '下降'} {Math.abs(site.trendPercentage)}%
        </div>
      </div>
    </motion.div>
  );
};

export default RecommendationCard;
```

### 🎯 互動效果

- **進入動畫**：從左淡入，延遲時間 = 排名 × 0.1s
- **懸停**：向右移動 4px
- **詳情按鈕**：點擊後展開更多資訊或跳轉

### ✅ 驗收標準

- [ ] 排名圖標正確顯示（🏆🥈🥉4️⃣5️⃣）
- [ ] 左側彩條顏色對應主題色
- [ ] 趨勢箭頭正確（上升▲紅色、下降▼綠色）
- [ ] 建議內容清晰可讀
- [ ] 4 個指標網格正確顯示

---

## 3. 12 班別選擇器 (ShiftSelector)

### 📋 功能說明

允許用戶選擇一個或多個班別進行資料篩選。

### 🎨 視覺設計

```
┌─────────────────────────────────────────┐
│  請選擇班別：                            │
├─────────────────────────────────────────┤
│                                         │
│  🌙 🌙 🌅 🌅 ☀️ ☀️                     │
│  01 02 03 04 05 06                      │
│  [✓][  ][  ][  ][  ][  ]                │
│                                         │
│  ☀️ ☀️ 🌆 🌆 🌙 🌙                     │
│  07 08 09 10 11 12                      │
│  [  ][  ][  ][  ][✓][✓]                │
│                                         │
└─────────────────────────────────────────┘
```

### 🔧 組件 Props

```typescript
interface ShiftSelectorProps {
  selectedShifts: string[];       // 已選班別 ['01', '11', '12']
  onShiftChange: (shifts: string[]) => void;
  multiSelect?: boolean;          // 是否支持多選
  showTimeRange?: boolean;        // 是否顯示時間範圍
}

interface Shift {
  id: string;                     // '01' ~ '12'
  icon: string;                   // 🌙🌅☀️🌆
  timeRange: [number, number];    // [0, 2] 表示 00:00-02:00
  label: string;                  // '深夜' | '清晨' | ...
}
```

### 💻 React 實作範例

```jsx
import React from 'react';
import { motion } from 'framer-motion';

const shifts = [
  { id: '01', icon: '🌙', timeRange: [0, 2], label: '深夜' },
  { id: '02', icon: '🌙', timeRange: [2, 4], label: '深夜' },
  { id: '03', icon: '🌅', timeRange: [4, 6], label: '清晨' },
  { id: '04', icon: '🌅', timeRange: [6, 8], label: '清晨' },
  { id: '05', icon: '☀️', timeRange: [8, 10], label: '上午' },
  { id: '06', icon: '☀️', timeRange: [10, 12], label: '上午' },
  { id: '07', icon: '☀️', timeRange: [12, 14], label: '中午' },
  { id: '08', icon: '☀️', timeRange: [14, 16], label: '下午' },
  { id: '09', icon: '🌆', timeRange: [16, 18], label: '傍晚' },
  { id: '10', icon: '🌆', timeRange: [18, 20], label: '傍晚' },
  { id: '11', icon: '🌙', timeRange: [20, 22], label: '夜間' },
  { id: '12', icon: '🌙', timeRange: [22, 24], label: '夜間' },
];

const ShiftSelector = ({ selectedShifts, onShiftChange, multiSelect = true }) => {
  const handleShiftClick = (shiftId) => {
    if (multiSelect) {
      const newSelection = selectedShifts.includes(shiftId)
        ? selectedShifts.filter((id) => id !== shiftId)
        : [...selectedShifts, shiftId];
      onShiftChange(newSelection);
    } else {
      onShiftChange([shiftId]);
    }
  };

  return (
    <div className="ac-shift-selector">
      {shifts.map((shift) => {
        const isSelected = selectedShifts.includes(shift.id);
        return (
          <motion.div
            key={shift.id}
            className={`ac-shift-item ${isSelected ? 'active' : ''}`}
            data-shift={shift.id}
            onClick={() => handleShiftClick(shift.id)}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
          >
            <span className="ac-shift-icon">{shift.icon}</span>
            <span className="ac-shift-number">{shift.id}</span>
            <span className="ac-shift-time">
              {String(shift.timeRange[0]).padStart(2, '0')}:00-
              {String(shift.timeRange[1]).padStart(2, '0')}:00
            </span>
            {isSelected && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                style={{
                  position: 'absolute',
                  top: '4px',
                  right: '4px',
                  color: 'var(--ac-primary)',
                  fontSize: '16px',
                }}
              >
                ✓
              </motion.div>
            )}
          </motion.div>
        );
      })}
    </div>
  );
};

export default ShiftSelector;
```

### 🎯 互動效果

- **懸停**：放大到 110%
- **點擊**：縮小到 90% 再恢復
- **選中**：顯示綠色勾選標記，背景填滿淺綠色
- **動畫**：勾選標記從 0 放大到 1（0.2s）

### ✅ 驗收標準

- [ ] 12 個班別格子正確排列（6×2）
- [ ] 選中狀態清晰可辨
- [ ] 支持多選/單選模式切換
- [ ] 時間範圍正確顯示
- [ ] 響應式：手機 3×4 排列

---

## 4. 地圖標記組件 (MapMarker)

### 📋 功能說明

在地圖上標記舉發案件、交通事故、推薦點位。

### 🎨 視覺設計

```
舉發標記：
  🍺 (粉紅背景)
  🚦 (橘黃背景)
  ⚡ (天藍背景)

事故標記：
  🚨 (紅色背景 + 脈動動畫)

推薦標記：
  ⭐ (綠色背景 + 脈動動畫 + 較大尺寸)
```

### 🔧 組件 Props

```typescript
interface MapMarkerProps {
  type: 'ticket' | 'crash' | 'recommended';
  topic?: 'DUI' | 'RED_LIGHT' | 'DANGEROUS_DRIVING';
  position: [number, number];    // [lat, lng]
  data: MarkerData;
  onClick?: (data: MarkerData) => void;
}

interface MarkerData {
  id: string;
  name: string;
  count?: number;
  severity?: 'A1' | 'A2' | 'A3';
  score?: number;
}
```

### 💻 Mapbox GL JS 實作範例

```javascript
import mapboxgl from 'mapbox-gl';

// 創建自定義標記元素
const createMarkerElement = (type, topic, data) => {
  const el = document.createElement('div');
  el.className = `ac-map-marker ac-marker-${type}`;

  if (type === 'ticket') {
    el.classList.add(`ac-marker-${topic.toLowerCase().replace('_', '-')}`);
    el.innerHTML = topic === 'DUI' ? '🍺' : topic === 'RED_LIGHT' ? '🚦' : '⚡';
  } else if (type === 'crash') {
    el.classList.add('ac-marker-crash');
    el.innerHTML = '🚨';
  } else if (type === 'recommended') {
    el.classList.add('ac-marker-recommended');
    el.innerHTML = '⭐';
  }

  // 添加脈動動畫 (僅事故和推薦點位)
  if (type === 'crash' || type === 'recommended') {
    el.style.animation = 'pulse 2s infinite';
  }

  return el;
};

// 添加標記到地圖
const addMarkerToMap = (map, markerProps) => {
  const { type, topic, position, data, onClick } = markerProps;
  const el = createMarkerElement(type, topic, data);

  const marker = new mapboxgl.Marker({ element: el })
    .setLngLat([position[1], position[0]])  // [lng, lat]
    .addTo(map);

  // 添加彈出框
  const popup = new mapboxgl.Popup({ offset: 25 }).setHTML(`
    <div style="padding: 8px;">
      <strong>${data.name}</strong><br>
      ${data.count ? `案件數: ${data.count}` : ''}
      ${data.score ? `分數: ${data.score}` : ''}
    </div>
  `);

  marker.setPopup(popup);

  // 點擊事件
  if (onClick) {
    el.addEventListener('click', () => onClick(data));
  }

  return marker;
};
```

### ✅ 驗收標準

- [ ] 標記顏色正確對應主題
- [ ] 事故標記有脈動動畫
- [ ] 推薦標記尺寸較大且有脈動
- [ ] 懸停時標記放大 120%
- [ ] 點擊顯示彈出框

---

## 5. 載入動畫 (LoadingSpinner)

### 📋 功能說明

在資料載入時顯示療癒的葉子旋轉動畫。

### 🎨 視覺設計

```
┌──────────────────────┐
│                      │
│        🌿           │
│    (旋轉動畫)         │
│                      │
│   資料載入中...       │
│                      │
└──────────────────────┘
```

### 💻 React 實作範例

```jsx
import React from 'react';
import { motion } from 'framer-motion';

const LoadingSpinner = ({ text = '資料載入中...' }) => {
  return (
    <div className="ac-loading">
      <motion.div
        className="ac-loading-leaf"
        animate={{
          rotate: [0, 180, 360],
          scale: [1, 1.2, 1],
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: 'easeInOut',
        }}
      >
        🌿
      </motion.div>
      <div className="ac-loading-text">{text}</div>
    </div>
  );
};

export default LoadingSpinner;
```

### ✅ 驗收標準

- [ ] 葉子平滑旋轉 360 度
- [ ] 旋轉時有放大效果（1 → 1.2 → 1）
- [ ] 動畫循環流暢
- [ ] 文字清晰可讀

---

## 6. 統計儀表板 (StatsDashboard)

### 📋 功能說明

顯示本月重大違規概況統計。

### 🎨 視覺設計

```
┌─────────────────────────────────────────────────────┐
│  📊 重大違規概況（本月）                              │
├─────────────────────────────────────────────────────┤
│                                                     │
│   🍺 酒駕     🚦 闖紅燈    ⚡ 危險駕駛    📈 總計   │
│   26 筆       478 筆      1,134 筆     1,638 筆  │
│   ▲ +3       ▼ -12        ▲ +45       ▲ +36     │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 💻 React 實作範例

```jsx
const StatsDashboard = ({ stats }) => {
  return (
    <div className="ac-card">
      <div className="ac-card-header">
        <h3 className="ac-card-title">📊 重大違規概況（本月）</h3>
      </div>
      <div className="ac-card-body">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
          {stats.map((stat) => (
            <div key={stat.code} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '32px' }}>{stat.icon}</div>
              <div style={{ fontSize: '14px', color: 'var(--ac-text-secondary)' }}>
                {stat.name}
              </div>
              <div style={{ fontSize: '24px', fontWeight: 'bold', margin: '8px 0' }}>
                {stat.count} 筆
              </div>
              <div style={{ fontSize: '14px', color: stat.trend > 0 ? 'var(--ac-danger)' : 'var(--ac-success)' }}>
                {stat.trend > 0 ? '▲' : '▼'} {Math.abs(stat.trend)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
```

---

## 7. 篩選器面板 (FilterPanel)

### 🎨 視覺設計

```
┌────────────┐
│  🎯 篩選    │
│            │
│  📅 時間    │
│  □ 近7日    │
│  ☑ 近30日   │
│  □ 近90日   │
│            │
│  🌙 班別    │
│  □ 深夜     │
│  ☑ 夜間     │
│            │
│  📍 行政區   │
│  ☑ 新化區   │
│  □ 永康區   │
│            │
│  [套用]    │
└────────────┘
```

### 💻 React 實作範例

```jsx
const FilterPanel = ({ filters, onFiltersChange }) => {
  const handleChange = (key, value) => {
    onFiltersChange({ ...filters, [key]: value });
  };

  return (
    <div className="ac-card" style={{ width: '240px' }}>
      <div className="ac-card-header">
        <h4 className="ac-card-title">🎯 篩選</h4>
      </div>
      <div className="ac-card-body">
        {/* 時間篩選 */}
        <div className="mb-md">
          <div style={{ fontWeight: 'bold', marginBottom: '8px' }}>📅 時間</div>
          {['7', '30', '90'].map((days) => (
            <label key={days} style={{ display: 'block', marginBottom: '4px' }}>
              <input
                type="radio"
                name="days"
                className="ac-radio"
                checked={filters.days === days}
                onChange={() => handleChange('days', days)}
              />
              {' '}近{days}日
            </label>
          ))}
        </div>

        {/* 班別篩選 */}
        <div className="mb-md">
          <div style={{ fontWeight: 'bold', marginBottom: '8px' }}>🌙 班別</div>
          {['深夜', '清晨', '白天', '傍晚', '夜間'].map((period) => (
            <label key={period} style={{ display: 'block', marginBottom: '4px' }}>
              <input type="checkbox" className="ac-checkbox" />
              {' '}{period}
            </label>
          ))}
        </div>

        {/* 行政區篩選 */}
        <div className="mb-md">
          <div style={{ fontWeight: 'bold', marginBottom: '8px' }}>📍 行政區</div>
          {['新化區', '永康區', '安南區'].map((district) => (
            <label key={district} style={{ display: 'block', marginBottom: '4px' }}>
              <input type="checkbox" className="ac-checkbox" />
              {' '}{district}
            </label>
          ))}
        </div>

        <button className="ac-btn ac-btn-primary w-full">🔍 套用篩選</button>
      </div>
    </div>
  );
};
```

---

## 8. 班前報表卡 (BriefingCard)

顯示班前勤務建議卡的數位版本。

### 💻 React 實作範例

```jsx
const BriefingCard = ({ briefing }) => {
  return (
    <div className="ac-card">
      <div className="ac-card-header">
        <h3 className="ac-card-title">
          {briefing.topic.icon} {briefing.topic.name} - 班前勤務建議卡
        </h3>
        <button className="ac-btn ac-btn-sm ac-btn-secondary">
          📄 匯出 PDF
        </button>
      </div>
      <div className="ac-card-body">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
          <div>
            <div style={{ fontSize: '14px', color: 'var(--ac-text-secondary)' }}>📅 日期</div>
            <div style={{ fontWeight: 'bold' }}>{briefing.date}</div>
          </div>
          <div>
            <div style={{ fontSize: '14px', color: 'var(--ac-text-secondary)' }}>⏰ 班別</div>
            <div style={{ fontWeight: 'bold' }}>第 {briefing.shift} 班</div>
          </div>
          <div>
            <div style={{ fontSize: '14px', color: 'var(--ac-text-secondary)' }}>🎯 覆蓋率</div>
            <div style={{ fontWeight: 'bold', color: 'var(--ac-success)' }}>{briefing.coverage}%</div>
          </div>
        </div>

        <h4 style={{ marginBottom: '12px' }}>🏆 Top 5 建議取締點位</h4>
        {briefing.top5.map((site, idx) => (
          <div key={site.id} style={{ marginBottom: '8px', padding: '8px', backgroundColor: 'var(--ac-bg-main)', borderRadius: '8px' }}>
            <strong>排名{idx + 1}</strong> {site.name} - 分數: {site.score}
          </div>
        ))}

        <div style={{ marginTop: '24px', padding: '16px', backgroundColor: 'var(--ac-primary-pale)', borderRadius: '12px' }}>
          <strong>💡 執法重點提示</strong>
          <ul style={{ marginTop: '8px', paddingLeft: '20px' }}>
            {briefing.tips.map((tip, idx) => (
              <li key={idx}>{tip}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};
```

---

## 9. 熱力圖圖層控制器

控制地圖上不同圖層的顯示/隱藏。

### 💻 React 實作範例

```jsx
const HeatmapControl = ({ layers, onLayersChange }) => {
  const handleToggle = (layerId) => {
    onLayersChange({
      ...layers,
      [layerId]: !layers[layerId],
    });
  };

  return (
    <div className="ac-card" style={{ position: 'absolute', top: '16px', left: '16px', zIndex: 1000, width: '200px' }}>
      <div className="ac-card-header">
        <h4 className="ac-card-title">圖層控制</h4>
      </div>
      <div className="ac-card-body">
        <label style={{ display: 'block', marginBottom: '8px' }}>
          <input
            type="checkbox"
            className="ac-checkbox"
            checked={layers.dui}
            onChange={() => handleToggle('dui')}
          />
          {' '}🍺 酒駕
        </label>
        <label style={{ display: 'block', marginBottom: '8px' }}>
          <input
            type="checkbox"
            className="ac-checkbox"
            checked={layers.crash}
            onChange={() => handleToggle('crash')}
          />
          {' '}🚨 事故
        </label>
        <label style={{ display: 'block', marginBottom: '8px' }}>
          <input
            type="checkbox"
            className="ac-checkbox"
            checked={layers.recommended}
            onChange={() => handleToggle('recommended')}
          />
          {' '}⭐ 推薦
        </label>
        <label style={{ display: 'block' }}>
          <input
            type="checkbox"
            className="ac-checkbox"
            checked={layers.heatmap}
            onChange={() => handleToggle('heatmap')}
          />
          {' '}🔥 熱力圖
        </label>
      </div>
    </div>
  );
};
```

---

## 10. 缺口警示卡 (GapAlertCard)

顯示未覆蓋的高風險點位。

### 💻 React 實作範例

```jsx
const GapAlertCard = ({ gaps }) => {
  if (gaps.length === 0) {
    return (
      <div className="ac-card" style={{ borderLeft: '6px solid var(--ac-success)' }}>
        <div style={{ textAlign: 'center', padding: '24px' }}>
          <div style={{ fontSize: '48px' }}>✅</div>
          <div style={{ fontSize: '18px', fontWeight: 'bold', marginTop: '8px' }}>
            所有高風險點位均已覆蓋
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="ac-card" style={{ borderLeft: '6px solid var(--ac-warning)' }}>
      <div className="ac-card-header">
        <h4 className="ac-card-title">⚠️ 未覆蓋之高風險點位（建議補點）</h4>
      </div>
      <div className="ac-card-body">
        {gaps.map((gap) => (
          <div key={gap.id} style={{ marginBottom: '12px', padding: '12px', backgroundColor: 'var(--ac-bg-main)', borderRadius: '8px', borderLeft: '3px solid var(--ac-warning)' }}>
            <div style={{ fontWeight: 'bold' }}>📍 {gap.name}</div>
            <div style={{ fontSize: '14px', color: 'var(--ac-text-secondary)', marginTop: '4px' }}>
              分數: {gap.score} | 距離最近執法點: {gap.distance}km
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
```

---

## 📦 組件庫打包建議

### 目錄結構

```
src/
├── components/
│   ├── TopicSelector/
│   │   ├── index.jsx
│   │   ├── TopicSelector.css
│   │   └── TopicSelector.stories.js
│   ├── RecommendationCard/
│   ├── ShiftSelector/
│   ├── MapMarker/
│   ├── LoadingSpinner/
│   ├── StatsDashboard/
│   ├── FilterPanel/
│   ├── BriefingCard/
│   ├── HeatmapControl/
│   └── GapAlertCard/
├── styles/
│   └── theme.css  (動森風格_完整CSS主題包.css)
└── utils/
    ├── constants.js  (主題定義、班別定義)
    └── helpers.js
```

### 安裝依賴

```bash
npm install framer-motion mapbox-gl react-chartjs-2
```

### 全局引入主題

```jsx
// App.jsx
import './styles/theme.css';
import '@fontsource/quicksand';
import '@fontsource/noto-sans-tc';

function App() {
  return <div className="app">{/* 組件 */}</div>;
}
```

---

## ✅ 整體驗收清單

### 功能驗收
- [ ] 所有組件可正常渲染
- [ ] 主題切換正確觸發回調
- [ ] 班別選擇支持多選/單選
- [ ] 地圖標記正確顯示並可點擊
- [ ] 載入動畫流暢運行
- [ ] 篩選器正確更新資料

### 視覺驗收
- [ ] 色彩符合動森風格（柔和、療癒）
- [ ] 圓角半徑統一（卡片 20px、按鈕 8px）
- [ ] 字體正確載入（Quicksand + Noto Sans TC）
- [ ] 陰影效果適中
- [ ] 動畫流暢（0.3s 過渡）

### 響應式驗收
- [ ] 桌面版（≥1024px）：3 列主題、6×2 班別
- [ ] 平板版（640-1024px）：2 列主題、4×3 班別
- [ ] 手機版（<640px）：1 列主題、3×4 班別

### 無障礙驗收
- [ ] 所有按鈕可用鍵盤操作
- [ ] 對比度符合 WCAG AA 標準
- [ ] 螢幕閱讀器可讀

---

## 🎓 結論

本規格書提供了 **10 個核心 UI 組件** 的完整實作指南，包括：

✅ **設計稿** - ASCII 圖示清晰展示視覺效果
✅ **Props 定義** - TypeScript 型別完整
✅ **React 程式碼** - 可直接使用的實作範例
✅ **互動效果** - Framer Motion 動畫規格
✅ **驗收標準** - 明確的檢查清單

這些組件遵循動森風格的設計語言，確保整個系統具有一致且療癒的使用體驗。

---

**文件製作**：Claude Sonnet 4.5
**最後更新**：2026-01-13
**相關文件**：
- [動森風格_完整CSS主題包.css](動森風格_完整CSS主題包.css)
- [UI設計規範_動森風格.md](UI設計規範_動森風格.md)

🌿 Generated by 精準執法系統（動森版）
