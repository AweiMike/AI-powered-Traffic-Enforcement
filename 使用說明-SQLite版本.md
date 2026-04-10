# 精準執法儀表板系統 - SQLite 版本使用說明

## 🎉 好消息！

系統已改為使用 **SQLite 資料庫**，無需安裝 PostgreSQL！

### ✅ SQLite 的優勢

1. **無需安裝資料庫軟體** - 不需要系統權限
2. **單一檔案** - 整個資料庫就是一個 `.db` 檔案
3. **輕量快速** - 適合中小規模資料
4. **完全離線** - 不需要網路連線
5. **易於備份** - 直接複製檔案即可

## 📋 系統架構

```
這台電腦（主機）：
├── 後端 API (Port 8000)
├── 前端介面 (Port 5173)
└── SQLite 資料庫檔案 (backend/data/traffic_enforcement.db)

其他電腦（客戶端）：
└── 透過瀏覽器訪問 http://[主機IP]:5173
```

## 🚀 快速開始

### 步驟 1：初始化資料庫

執行以下任一方式：

**方式A：使用快捷腳本**
```batch
雙擊執行：初始化資料庫.bat
```

**方式B：使用主選單**
```batch
1. 雙擊執行：啟動系統.bat
2. 選擇選項 [4] 初始化資料庫
```

### 步驟 2：啟動系統

**方式A：快速啟動完整版**
```batch
雙擊執行：啟動系統.bat
選擇 [1] 啟動完整系統
```

**方式B：使用簡化版測試**
```batch
雙擊執行：啟動系統-簡化版.bat
```

### 步驟 3：訪問系統

- 🌐 **前端介面**：http://localhost:5173
- 📡 **後端 API**：http://localhost:8000
- 📚 **API 文件**：http://localhost:8000/docs

## 🗄️ 資料庫位置

```
D:\Programming\精準執法儀表板系統\backend\data\traffic_enforcement.db
```

### 備份資料庫

只需複製這個檔案即可完整備份！

```batch
copy backend\data\traffic_enforcement.db backup\traffic_enforcement_備份_20250114.db
```

## 🌐 讓其他電腦連接此系統

### 1. 查詢本機 IP 位址

```batch
# 開啟命令提示字元，執行：
ipconfig

# 找到「IPv4 位址」，例如：192.168.1.100
```

### 2. 設定防火牆（重要！）

**允許 Port 8000（後端API）**
```batch
# 以管理員身分執行命令提示字元
netsh advfirewall firewall add rule name="精準執法系統-API" dir=in action=allow protocol=TCP localport=8000
```

**允許 Port 5173（前端介面）**
```batch
netsh advfirewall firewall add rule name="精準執法系統-前端" dir=in action=allow protocol=TCP localport=5173
```

### 3. 修改後端配置（允許遠端連接）

編輯 `backend/app/config.py`：

```python
# CORS - 添加允許的來源
ALLOWED_ORIGINS: List[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.1.100:5173",  # 添加主機 IP
    "http://192.168.1.*:5173",     # 允許整個區網（可選）
]
```

### 4. 其他電腦連接方式

**方式A：直接訪問前端（推薦）**
```
在瀏覽器輸入：http://192.168.1.100:5173
```

**方式B：只訪問 API**
```
API 端點：http://192.168.1.100:8000/api/v1
API 文件：http://192.168.1.100:8000/docs
```

## 📊 匯入資料

### 準備 Excel 檔案

1. **交通事故資料** (crashes.xlsx)
   - 必要欄位：發生日期、發生時間、地點、嚴重度

2. **舉發案件資料** (tickets.xlsx)
   - 必要欄位：違規日期、違規時間、地點、違規條款

### 執行匯入

```batch
1. 雙擊執行：啟動系統.bat
2. 選擇 [5] 匯入資料
3. 依提示輸入檔案路徑
```

或直接執行：
```batch
cd backend
venv\Scripts\activate.bat
python scripts\import_data.py --crash-file "路徑\crashes.xlsx" --ticket-file "路徑\tickets.xlsx"
```

## 🔧 進階設定

### 更改資料庫位置

編輯 `backend/app/config.py`：

```python
# 改為絕對路徑，方便其他電腦訪問
DATABASE_URL: str = "sqlite:///D:/Data/traffic_enforcement.db"
```

### 設定資料保留期限

編輯 `backend/app/config.py`：

```python
# 只保留最近 365 天的資料
DATA_RETENTION_DAYS: int = 365
```

## 🛠️ 常見問題

### Q1: 資料庫檔案在哪裡？
**A:** `backend/data/traffic_enforcement.db`

### Q2: 如何備份資料？
**A:** 直接複製 `traffic_enforcement.db` 檔案

### Q3: 其他電腦無法連線？
**A:** 檢查：
1. 主機電腦的防火牆設定
2. 確認主機 IP 位址正確
3. 確認系統正在運行 (前端+後端都要啟動)

### Q4: 資料庫損壞怎麼辦？
**A:**
1. 從備份還原
2. 或重新執行 `初始化資料庫.bat` 創建新的空資料庫
3. 重新匯入資料

### Q5: 可以同時多人使用嗎？
**A:** 可以！SQLite 支援多人同時讀取，但同時寫入會有限制。對於此系統（主要是查詢統計），完全沒問題。

### Q6: 資料量限制？
**A:** SQLite 理論上可支援到 281 TB，對於一般執法資料（幾萬到幾十萬筆）完全足夠。

### Q7: 效能如何？
**A:** 對於中小規模資料（10萬筆以內），SQLite 效能優異。如果未來資料量超過 50 萬筆，再考慮升級到 PostgreSQL。

## 📌 重要提醒

### ⚠️ 保持主機運行

- 這台電腦就是資料庫主機
- 關機後其他電腦將無法連線
- 建議設定為「永不休眠」

### 🔒 資料安全

- 定期備份 `traffic_enforcement.db` 檔案
- 建議每日或每週自動備份
- 可使用排程任務自動複製檔案

### 🚀 效能優化

如果系統變慢：
1. 定期清理舊資料
2. 執行資料庫真空清理：
   ```sql
   VACUUM;
   ```
3. 考慮升級到 PostgreSQL

## 📞 技術支援

如遇到問題，請檢查：
1. 後端命令視窗的錯誤訊息
2. 前端瀏覽器的 Console (F12)
3. 資料庫檔案是否存在且未損壞

---

**系統版本**：1.0.0-SQLite
**最後更新**：2025-01-14
**資料庫類型**：SQLite 3
