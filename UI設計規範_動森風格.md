# 精準執法儀表板系統 - 動森風格 UI/UX 設計規範

> 🌿 設計理念：將嚴肅的執法數據，用溫暖療癒的動森風格呈現，提升使用體驗與可讀性

---

## 🎨 一、色彩系統（Color Palette）

### 主色調 - 柔和米綠系
```
Primary Colors:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌿 主綠色 (Main Green)
  #9ECE9A    ███████  柔和草綠 - 主要按鈕、強調色
  #B8DDB5    ███████  淺草綠 - 卡片背景、次要區塊
  #D4EBD0    ███████  極淺綠 - 頁面背景

🍃 輔助綠色 (Accent Green)
  #7AB878    ███████  深草綠 - hover狀態、選中項目
  #E8F5E5    ███████  奶油綠 - 輸入框背景

🏝️ 中性色 (Neutral)
  #F9F6F0    ███████  米白色 - 卡片主背景
  #F0EBE3    ███████  米黃色 - 邊框、分隔線
  #8B7E74    ███████  溫暖灰 - 副文字
  #5D5347    ███████  深棕灰 - 主文字
```

### 功能色 - 動森自然系
```
Semantic Colors:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ 警示色 (Warning)
  #F4B860    ███████  溫暖橘黃 - 警告、待處理
  #FFD89C    ███████  淺橘黃 - 警告背景

🚨 危險色 (Danger)
  #E89A9A    ███████  柔和粉紅 - 高風險、A1事故
  #F5D6D6    ███████  淺粉紅 - 危險背景

✅ 成功色 (Success)
  #9ECE9A    ███████  草綠色 - 完成、正常
  #D4EBD0    ███████  淺綠 - 成功背景

ℹ️ 資訊色 (Info)
  #8DCEDC    ███████  柔和天藍 - 提示、資訊
  #D1EDF4    ███████  淺天藍 - 資訊背景
```

### 數據視覺化色彩
```
Chart Colors (12班別專用配色):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

班別01 (00-02) 🌙  #6B8E9E  深夜藍綠
班別02 (02-04) 🌙  #7A9DAD  深夜淺藍
班別03 (04-06) 🌅  #B8A0D4  破曉紫
班別04 (06-08) 🌅  #F4C4A0  晨曦橘
班別05 (08-10) ☀️  #FFD89C  早晨金黃
班別06 (10-12) ☀️  #9ECE9A  午前草綠
班別07 (12-14) ☀️  #7AB878  正午深綠
班別08 (14-16) ☀️  #8DCEDC  午後天藍
班別09 (16-18) 🌆  #F4B860  傍晚橙
班別10 (18-20) 🌆  #E89A9A  黃昏粉
班別11 (20-22) 🌙  #9B8FAF  夜晚紫
班別12 (22-24) 🌙  #7B8B9E  深夜灰藍
```

---

## 🎭 二、字體系統（Typography）

### 主要字體
```
Primary Font:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

中文: Noto Sans TC (思源黑體)
      - 圓潤、易讀、現代感
      - Weight: 400 (Regular), 500 (Medium), 700 (Bold)

英數: Quicksand
      - 圓潤幾何字型，符合動森風格
      - Weight: 400, 500, 700

備用: system-ui, -apple-system, 'Microsoft JhengHei'
```

### 字階系統
```
Font Scale:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

H1: 32px / 500  主標題 (頁面標題)
H2: 24px / 500  次標題 (區塊標題)
H3: 20px / 500  小標題 (卡片標題)
H4: 18px / 500  次小標題

Body-L:  16px / 400  內文大 (主要資訊)
Body-M:  14px / 400  內文中 (一般內容)
Body-S:  12px / 400  內文小 (輔助資訊)

Label:   14px / 500  標籤文字
Caption: 12px / 400  說明文字 (次要訊息)
Number:  18px / 700  數字強調

行高: 1.6em (舒適閱讀)
字間距: 0.02em
```

---

## 📦 三、卡片設計（Card System）

### 主要卡片樣式
```css
動森風格卡片規範:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

基礎卡片:
  background: #F9F6F0 (米白色)
  border: 3px solid #F0EBE3 (米黃邊框)
  border-radius: 20px (圓潤角度)
  padding: 24px
  box-shadow:
    0 4px 12px rgba(139, 126, 116, 0.08),  /* 柔和陰影 */
    0 2px 4px rgba(139, 126, 116, 0.04)    /* 層次感 */

懸停效果 (Hover):
  transform: translateY(-4px)
  box-shadow:
    0 8px 20px rgba(139, 126, 116, 0.12),
    0 4px 8px rgba(139, 126, 116, 0.06)
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1)

選中狀態 (Active):
  border: 3px solid #9ECE9A (草綠邊框)
  box-shadow: 0 0 0 4px rgba(158, 206, 154, 0.2) (外發光)
```

### 卡片類型
```
類型配色:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌿 推薦點位卡 (Top 5)
   • 背景: #F9F6F0
   • 左側彩條: #9ECE9A (4px寬)
   • 標題: #5D5347 / 18px / 500
   • 數字: #7AB878 / 24px / 700

⚠️ 高風險卡
   • 背景: #FFF9F0
   • 左側彩條: #E89A9A
   • 圖示: 🚨 柔和紅色

✅ 已覆蓋卡
   • 背景: #F0F9F0
   • 左側彩條: #9ECE9A
   • 圖示: ✓ 草綠色

📊 統計卡
   • 背景: 漸層 #F9F6F0 → #E8F5E5
   • 圖表用圓潤線條
   • 數字大而醒目
```

---

## 🎮 四、互動元件（Interactive Components）

### 按鈕設計
```css
動森風格按鈕:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

主要按鈕 (Primary):
  background: #9ECE9A
  color: #FFFFFF
  border: 2px solid #7AB878
  border-radius: 12px
  padding: 12px 24px
  font-size: 14px
  font-weight: 500
  box-shadow: 0 2px 8px rgba(122, 184, 120, 0.2)

  hover:
    background: #7AB878
    transform: scale(1.02)

  active:
    transform: scale(0.98)

次要按鈕 (Secondary):
  background: #FFFFFF
  color: #5D5347
  border: 2px solid #F0EBE3

副按鈕 (Ghost):
  background: transparent
  color: #8B7E74
  border: 2px dashed #F0EBE3
```

### 輸入框
```css
Input Fields:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

文字輸入:
  background: #E8F5E5
  border: 2px solid #D4EBD0
  border-radius: 12px
  padding: 12px 16px
  color: #5D5347

  focus:
    border-color: #9ECE9A
    box-shadow: 0 0 0 4px rgba(158, 206, 154, 0.15)
    outline: none

下拉選單 (Dropdown):
  • 圓潤箭頭圖示
  • 選項間距寬鬆 (padding: 12px)
  • hover 背景: #E8F5E5
```

### 切換器與選擇器
```css
Toggle / Switch:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

班別選擇器 (12班):
  • 圓形按鈕陣列
  • 直徑: 48px
  • 未選中: #F9F6F0 邊框 #F0EBE3
  • 選中: 對應班別色彩 + 白色文字
  • 圖示: 🌙☀️🌅🌆 時段符號

主題切換 (酒駕/行人):
  • 圓潤膠囊按鈕
  • 寬度: 120px × 2
  • 滑動動畫: cubic-bezier(0.4, 0, 0.2, 1)
  • 酒駕: 🍺 icon
  • 行人: 🚶 icon
```

---

## 🗺️ 五、地圖設計（Map Styling）

### 動森風格地圖
```javascript
Mapbox/Leaflet 自訂樣式:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

底圖配色:
  • 水域: #8DCEDC (柔和天藍)
  • 草地/公園: #D4EBD0 (淺草綠)
  • 道路: #F9F6F0 (米白)
  • 建築: #F0EBE3 (米黃)
  • 文字: #8B7E74 (溫暖灰)

標記樣式:
  • 事故點 (Crash): 🔴 柔和紅色圓點，外圈光暈
  • 舉發點 (Ticket): 🔵 柔和藍色圓點
  • 推薦點位 (Top 5): ⭐ 星星標記，脈動動畫

  點位大小:
    - 小: 8px (一般)
    - 中: 12px (重要)
    - 大: 16px (Top推薦)

  透明度: 0.7 (避免過於擁擠)

熱力圖:
  • 色階: #D4EBD0 → #9ECE9A → #F4B860 → #E89A9A
  • 圓潤模糊效果
  • 透明度: 0.6
```

### Popup 卡片
```css
地圖彈出卡:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  background: #FFFFFF
  border-radius: 16px
  border: 3px solid #9ECE9A
  padding: 16px
  min-width: 280px
  box-shadow: 0 8px 24px rgba(93, 83, 71, 0.15)

  標題區:
    • Icon + 點位名稱
    • 字體: 16px / 500
    • 顏色: #5D5347

  內容區:
    • CRI/VPI 數值：大字號、顏色區分
    • 事故/舉發數：帶圖示
    • 建議行動：高亮背景

  底部:
    • "查看詳情" 按鈕 (圓潤小按鈕)
```

---

## 📊 六、圖表設計（Charts）

### 動森風格圖表規範
```javascript
Chart.js / ECharts 配置:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

通用設定:
  • 字體: Quicksand
  • 網格線: #F0EBE3，虛線
  • 背景: 透明或 #F9F6F0
  • 圓潤線條: lineTension: 0.4

長條圖 (Bar Chart):
  • 圓角: borderRadius: 8
  • 間距: barPercentage: 0.7
  • 顏色: 12班別配色
  • 邊框: 2px solid (深一階的顏色)

圓餅圖 (Pie Chart):
  • 內圈留白 (Doughnut): cutout: 60%
  • 間距: spacing: 4
  • 懸停: 放大效果
  • 標籤: 帶圖示 + 百分比

折線圖 (Line Chart):
  • 線寬: 3px
  • 圓點: 半徑 6px，白色邊框
  • 漸層填充:
      top: rgba(158, 206, 154, 0.3)
      bottom: rgba(158, 206, 154, 0)
  • 平滑曲線: tension: 0.4
```

### 數據展示
```css
數字強調樣式:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

大數字:
  font-size: 36px
  font-weight: 700
  color: #7AB878
  font-family: Quicksand

  趨勢箭頭:
    • 上升 ↗️ #E89A9A
    • 下降 ↘️ #9ECE9A
    • 持平 → #8B7E74

百分比:
  • 圓形進度環 (Circular Progress)
  • 粗細: 8px
  • 背景: #F0EBE3
  • 前景: #9ECE9A
  • 中心數字: 24px / 700
```

---

## 🎪 七、頁面佈局（Layout）

### 整體結構
```
動森風格頁面佈局:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────┐
│  🌿 Header (固定頂部，高度: 72px)                      │
│  • Logo + 系統名稱 (左)                                │
│  • 快速篩選器 (中)                                     │
│  • 使用者選單 (右)                                     │
│  • 背景: 半透明白 rgba(249, 246, 240, 0.95)           │
│  • 毛玻璃效果: backdrop-filter: blur(12px)            │
└─────────────────────────────────────────────────────┘

┌───────────┬─────────────────────────────────────────┐
│           │                                         │
│  🎯 側邊   │  📊 主內容區                             │
│  導覽      │                                         │
│  (220px)  │  • 最大寬度: 1400px                      │
│           │  • 間距: 24px                            │
│  • 圖示+   │  • 卡片網格: 4欄 / 3欄 / 2欄 (響應式)     │
│    文字    │                                         │
│  • 選中:   │  ┌─────────┬─────────┬─────────┐        │
│    草綠背  │  │  卡片1   │  卡片2   │  卡片3   │        │
│    景圓角  │  │         │         │         │        │
│           │  └─────────┴─────────┴─────────┘        │
│           │                                         │
│           │  • 捲動平滑: scroll-behavior: smooth    │
│           │  • 無限捲動或分頁                         │
└───────────┴─────────────────────────────────────────┘

頁面背景:
  • 基底: #F9F6F0
  • 紋理: SVG 樹葉圖案 (極淡，不干擾閱讀)
  • 漸層: 頂部 #E8F5E5 → 底部 #F9F6F0
```

### 響應式設計
```
Responsive Breakpoints:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Desktop (≥1280px):
  • 側邊欄: 220px
  • 內容: 4欄網格
  • 卡片間距: 24px

Tablet (768px - 1279px):
  • 側邊欄: 收合成圖示 (64px)
  • 內容: 2-3欄網格
  • 卡片間距: 16px

Mobile (< 768px):
  • 側邊欄: 底部導覽 (Bottom Nav)
  • 內容: 1欄堆疊
  • 卡片間距: 12px
  • 字體縮放: 0.9x
```

---

## ✨ 八、動畫與互動（Animation）

### 微動畫
```css
動森風格動畫:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

載入動畫:
  • 三片葉子旋轉 🍃🍃🍃
  • 顏色: #9ECE9A, #B8DDB5, #D4EBD0
  • 速度: 1.2s ease-in-out

卡片進入:
  • fade-in + slide-up
  • 延遲: stagger 0.1s
  • 持續: 0.6s

數字滾動:
  • CountUp.js
  • 持續: 1s
  • Easing: ease-out

按鈕點擊:
  • 漣漪效果 (Ripple)
  • 顏色: rgba(158, 206, 154, 0.4)
  • 擴散: 0.6s

通知提示:
  • Toast 從右上角滑入
  • 圓潤邊角 + 柔和陰影
  • 自動消失: 3s
  • Icon 彈跳動畫
```

### 過場效果
```javascript
頁面切換:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • 淡入淡出 (Fade)
  • 配合葉子飄落動畫 (可選)
  • 持續時間: 0.3s
  • Timing: cubic-bezier(0.4, 0, 0.2, 1)

Loading Skeleton:
  • 圓潤形狀
  • 漸層閃爍: #F0EBE3 → #E8F5E5
  • 動畫: shimmer 1.5s infinite
```

---

## 🎨 九、圖示系統（Iconography）

### 圖示風格
```
Icon Style Guide:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

基本規範:
  • 線條粗細: 2px (圓潤端點)
  • 尺寸: 16px / 20px / 24px
  • 顏色: #8B7E74 (預設), #9ECE9A (啟用)
  • 風格: 圓潤、友善、清晰

推薦圖示庫:
  • Lucide Icons (主要)
  • Feather Icons (輔助)
  • 自訂 SVG (特殊需求)

功能圖示映射:
  🌙 深夜班別 (00-06)
  🌅 清晨班別 (06-09)
  ☀️ 白天班別 (09-18)
  🌆 傍晚班別 (18-21)
  🌙 夜間班別 (21-24)

  🍺 酒駕主題（DUI）
  🚦 闖紅燈主題（RED_LIGHT）
  ⚡ 危險駕駛主題（DANGEROUS_DRIVING）
  🚗 車輛
  🚨 高風險/事故
  ✅ 已覆蓋
  📍 地點
  📊 統計
  📄 報表
  ⚙️ 設定
```

---

## 📱 十、特殊組件設計

### Top 5 推薦卡片
```
動森風格推薦卡 (重點設計):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────────────────────────┐
│ 🏆 第 1 名  ⭐⭐⭐              [詳情 →] │
├────────────────────────────────────────┤
│                                        │
│  📍 臺南市新化區中山路 × 信義路 路口      │
│                                        │
│  ┌──────────┬──────────┬──────────┐   │
│  │ 🎯 分數   │ 🚨 CRI   │ 📊 VPI   │   │
│  │   89     │   45     │   67     │   │
│  │ ▲ +12    │ ▲ +8     │ ▲ +15    │   │
│  └──────────┴──────────┴──────────┘   │
│                                        │
│  💡 建議: 酒駕取締、路口違規             │
│                                        │
│  📈 近30日: ━━━━━━━━━━━━━━━━━━━▲       │
│            (迷你折線圖)                │
└────────────────────────────────────────┘

樣式:
  • 漸層邊框 (第1名金色，第2名銀色，第3名銅色)
  • 左上角排名徽章
  • 數字大而醒目
  • 趨勢箭頭帶顏色
  • 微光效果 (shimmer) on hover
```

### 班別選擇器
```
12班圓形選擇器:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  🌙  🌙  🌅  🌅  ☀️  ☀️
  01  02  03  04  05  06

  ☀️  ☀️  🌆  🌆  🌙  🌙
  07  08  09  10  11  12

互動:
  • 點擊選中: 填滿對應班別顏色 + 縮放動畫
  • 多選模式: 勾選圖示 ✓
  • Tooltip: "第X班 (HH:00-HH:00)"
```

### 覆蓋率儀表板
```
圓形進度環 (Coverage):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

      ╭─────────╮
    ╱             ╲
   │    ╭───╮      │
   │   │ 85% │     │   ← 大字號百分比
   │    ╰───╯      │
    ╲    已覆蓋     ╱   ← 小字說明
      ╰─────────╯

  • 環粗: 12px
  • 顏色: #9ECE9A (已覆蓋), #F0EBE3 (未覆蓋)
  • 動畫: 填充從 0% → 實際%
  • 持續: 1.5s ease-out
```

---

## 🎬 十一、實作建議

### 技術棧推薦
```
Frontend Stack:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

框架: React.js 或 Vue.js
UI 庫:
  • Tailwind CSS (基礎)
  • Headless UI (無樣式組件)
  • Framer Motion (動畫)

圖表:
  • Chart.js + chartjs-plugin-datalabels
  • 或 ECharts (功能更強)

地圖:
  • Mapbox GL JS (可自訂樣式)
  • 或 Leaflet + 自訂 tiles

字體載入:
  @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;700&display=swap');
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap');
```

### CSS 變數設定
```css
/* 動森風格 CSS Variables */
:root {
  /* Colors */
  --ac-primary: #9ECE9A;
  --ac-primary-light: #B8DDB5;
  --ac-primary-dark: #7AB878;

  --ac-bg-main: #F9F6F0;
  --ac-bg-card: #FFFFFF;
  --ac-bg-secondary: #E8F5E5;

  --ac-text-primary: #5D5347;
  --ac-text-secondary: #8B7E74;

  --ac-border: #F0EBE3;

  --ac-warning: #F4B860;
  --ac-danger: #E89A9A;
  --ac-success: #9ECE9A;
  --ac-info: #8DCEDC;

  /* Spacing */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;

  /* Border Radius */
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 20px;
  --radius-full: 9999px;

  /* Typography */
  --font-primary: 'Noto Sans TC', sans-serif;
  --font-accent: 'Quicksand', sans-serif;

  /* Shadows */
  --shadow-sm: 0 2px 4px rgba(139, 126, 116, 0.04);
  --shadow-md: 0 4px 12px rgba(139, 126, 116, 0.08);
  --shadow-lg: 0 8px 24px rgba(139, 126, 116, 0.12);

  /* Transitions */
  --transition-base: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
```

---

## 📐 十二、設計稿輸出規範

### Figma / Sketch 檔案結構
```
設計稿組織:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 精準執法儀表板_動森風格.fig
  ├─ 🎨 Design System
  │   ├─ Colors (色彩系統)
  │   ├─ Typography (字體)
  │   ├─ Components (組件庫)
  │   └─ Icons (圖示集)
  │
  ├─ 📱 Pages
  │   ├─ 01_班別決策看板
  │   ├─ 02_地圖疊圖頁
  │   ├─ 03_覆蓋率分析頁
  │   └─ 04_報表匯出頁
  │
  ├─ 🧩 Components
  │   ├─ Cards (各式卡片)
  │   ├─ Buttons (按鈕變體)
  │   ├─ Inputs (輸入元件)
  │   └─ Charts (圖表樣式)
  │
  └─ 📐 Grid & Layout
      └─ Responsive (響應式網格)
```

### 切圖輸出
```
Assets Export:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SVG:
  • 所有圖示
  • Logo
  • 插圖元素

PNG (@2x, @3x):
  • 點陣圖示 (如需要)
  • 截圖範例

命名規範:
  • icon-[name]-[size].svg
  • img-[description]-@2x.png
```

---

## 🎯 十三、使用者體驗建議

### 親和性設計
```
Accessibility (動森風格也要無障礙):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

色彩對比:
  • 確保文字與背景對比度 ≥ 4.5:1 (WCAG AA)
  • 重要資訊對比度 ≥ 7:1 (WCAG AAA)

鍵盤導覽:
  • Tab 順序合理
  • Focus 狀態清晰 (草綠外框 + 陰影)
  • 快捷鍵提示 (Tooltip)

語意化 HTML:
  • 使用 <nav>, <main>, <section>
  • ARIA labels 完整
  • alt 文字描述清楚

字體大小:
  • 最小 12px，避免過小
  • 支援瀏覽器縮放 (em/rem 單位)
```

### 載入體驗
```
Loading States:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

首次載入:
  • 葉子旋轉動畫 🍃
  • 進度條 (草綠色)
  • 提示文字: "準備中..."

資料載入:
  • Skeleton Screen (圓潤形狀)
  • 局部載入 (不阻塞整頁)
  • 載入完成淡入

錯誤處理:
  • 友善錯誤訊息
  • 動森風格插圖 (迷路的狸克?)
  • 重試按鈕醒目
```

---

## 📝 十四、設計檢查清單

開發前確認:
```
✅ 色彩系統已定義 (CSS Variables)
✅ 字體已載入 (Google Fonts)
✅ 組件庫已建立 (Storybook 可選)
✅ 圖示集已準備 (SVG Sprite 或 Icon Font)
✅ 響應式斷點已設定
✅ 動畫效果已測試 (流暢度)
✅ 無障礙檢查通過 (Lighthouse)
✅ 跨瀏覽器測試 (Chrome, Safari, Firefox)
```

---

## 🎁 附錄：參考資源

### 靈感來源
- Animal Crossing: New Horizons (遊戲 UI)
- Notion (卡片設計)
- Dribbble 搜尋 "pastel dashboard"

### 推薦工具
- **Coolors.co** - 色彩搭配生成
- **Figma** - 設計稿製作
- **Framer Motion** - React 動畫庫
- **Lordicon** - 動畫圖示庫

---

**設計理念總結:**
> "讓執法數據也能療癒人心，用動森的溫暖包裹嚴肅的分析工作。"

**核心原則:**
1. 🌿 **柔和色彩** - 避免刺眼，長時間使用不疲勞
2. 🎮 **圓潤形狀** - 卡片、按鈕、圖表都要圓滑
3. ✨ **微動畫** - 適度的動態回饋，提升愉悅感
4. 📊 **清晰資訊** - 療癒不等於難讀，數據要一目了然
5. 🎨 **一致性** - 嚴格遵守設計系統，保持整體和諧

---

*Last Updated: 2026-01-13*
*Version: 1.0*
