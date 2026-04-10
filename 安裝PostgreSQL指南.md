# PostgreSQL 安裝指南

> 🎯 目的：安裝 PostgreSQL 以啟用完整版系統
> ⏱️ 預計時間：15-20 分鐘

---

## 步驟 1：下載 PostgreSQL

### 下載地址
https://www.postgresql.org/download/windows/

### 推薦版本
- **PostgreSQL 14.x** 或更新版本
- 包含 **Stack Builder**（用於安裝 PostGIS）

### 下載方式
1. 點擊「Download the installer」
2. 選擇最新的 14.x 版本
3. 選擇 Windows x86-64

---

## 步驟 2：安裝 PostgreSQL

### 安裝選項

1. **Installation Directory**（安裝目錄）
   ```
   預設：C:\Program Files\PostgreSQL\14
   建議：使用預設值
   ```

2. **Select Components**（選擇組件）
   - ✅ **PostgreSQL Server**（必選）
   - ✅ **pgAdmin 4**（管理工具，建議安裝）
   - ✅ **Stack Builder**（必選，用於安裝 PostGIS）
   - ✅ **Command Line Tools**（必選）

3. **Data Directory**（資料目錄）
   ```
   預設：C:\Program Files\PostgreSQL\14\data
   建議：使用預設值
   ```

4. **Password**（超級用戶密碼）
   ```
   ⚠️ 重要：請記住此密碼！

   建議密碼：postgres
   （或使用您自己的密碼，但需記住）
   ```

5. **Port**（端口）
   ```
   預設：5432
   建議：使用預設值（除非此端口已被佔用）
   ```

6. **Advanced Options - Locale**（語系）
   ```
   建議：Chinese (Traditional), Taiwan 或 Default locale
   ```

7. **完成安裝**
   - 點擊「Next」完成安裝
   - ✅ **勾選「Launch Stack Builder」**（重要！）

---

## 步驟 3：安裝 PostGIS（地理空間擴展）

### 使用 Stack Builder

1. **Stack Builder 啟動後**：
   - 選擇「PostgreSQL 14 on port 5432」
   - 點擊「Next」

2. **選擇 PostGIS**：
   - 展開「Spatial Extensions」
   - ✅ 勾選「PostGIS x.x Bundle for PostgreSQL 14」
   - 點擊「Next」

3. **下載與安裝**：
   - 點擊「Next」開始下載
   - 下載完成後會自動安裝
   - 輸入 PostgreSQL 密碼（步驟 2 設定的密碼）

4. **PostGIS 安裝選項**：
   - ✅ 勾選「Create spatial database」（可選）
   - 使用預設設定
   - 完成安裝

---

## 步驟 4：驗證安裝

### 方法 1：使用 pgAdmin 4

1. 開啟 pgAdmin 4
2. 輸入主密碼（第一次使用需設定）
3. 展開「Servers」→「PostgreSQL 14」
4. 輸入密碼連接
5. 如果能看到「Databases」，表示安裝成功

### 方法 2：使用命令列

開啟命令提示字元（cmd）：

```cmd
# 測試 PostgreSQL 是否在 PATH 中
psql --version

# 預期輸出：psql (PostgreSQL) 14.x
```

如果顯示「'psql' 不是內部或外部命令」：

#### 添加 PostgreSQL 到 PATH

1. **開啟環境變數設定**：
   - 右鍵「本機」→「內容」
   - 點擊「進階系統設定」
   - 點擊「環境變數」

2. **編輯 PATH**：
   - 在「系統變數」中找到「Path」
   - 點擊「編輯」
   - 點擊「新增」
   - 輸入：`C:\Program Files\PostgreSQL\14\bin`
   - 點擊「確定」

3. **重新開啟命令提示字元**測試

---

## 步驟 5：創建系統資料庫

### 方法 1：使用 pgAdmin 4（圖形界面）

1. 開啟 pgAdmin 4
2. 連接到 PostgreSQL 14
3. 右鍵「Databases」→「Create」→「Database」
4. 輸入資料庫名稱：`traffic_enforcement`
5. 點擊「Save」
6. 右鍵新創建的資料庫 → 「Query Tool」
7. 輸入並執行：
   ```sql
   CREATE EXTENSION postgis;
   ```
8. 點擊「Execute」（F5）

### 方法 2：使用命令列

開啟命令提示字元：

```cmd
# 連接到 PostgreSQL
psql -U postgres

# 輸入密碼（步驟 2 設定的密碼）

# 創建資料庫
CREATE DATABASE traffic_enforcement;

# 切換到新資料庫
\c traffic_enforcement

# 啟用 PostGIS 擴展
CREATE EXTENSION postgis;

# 驗證 PostGIS
SELECT PostGIS_version();

# 退出
\q
```

---

## 步驟 6：配置系統環境變數

### 編輯 `.env` 文件

開啟 `D:\Programming\精準執法儀表板系統\backend\.env`

如果不存在，複製 `.env.example`：

```env
# 資料庫設定
DATABASE_URL=postgresql://postgres:你的密碼@localhost:5432/traffic_enforcement
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=你的密碼
DATABASE_NAME=traffic_enforcement

# API 設定
API_V1_PREFIX=/api/v1
DEBUG=True

# CORS 設定
ALLOWED_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
```

**⚠️ 重要**：將 `你的密碼` 替換為步驟 2 設定的 PostgreSQL 密碼

---

## 步驟 7：安裝後端依賴

開啟命令提示字元，執行：

```cmd
cd D:\Programming\精準執法儀表板系統\backend

# 啟動虛擬環境
venv\Scripts\activate

# 安裝所有依賴（現在 psycopg2-binary 應該能成功安裝）
pip install -r requirements.txt
```

---

## 步驟 8：初始化資料庫

```cmd
# 確保在 backend 目錄並已啟動虛擬環境
python scripts\init_database.py
```

**預期輸出**：
```
✅ PostgreSQL 連線成功
✅ PostGIS 擴展已啟用
✅ 所有資料表創建完成（12 個表）
✅ 班別資料初始化完成（12 筆）
✅ 違規條款資料初始化完成
```

---

## 常見問題

### Q1: 安裝時出現「port 5432 already in use」

**解決方案**：
1. 更改安裝時的端口（例如：5433）
2. 或停止佔用 5432 的程序

### Q2: psql 命令找不到

**解決方案**：
- 將 `C:\Program Files\PostgreSQL\14\bin` 添加到 PATH
- 重新啟動命令提示字元

### Q3: PostGIS 安裝失敗

**解決方案**：
1. 重新執行 Stack Builder
2. 或手動下載 PostGIS：http://postgis.net/windows_downloads/
3. 或在資料庫中手動安裝：
   ```sql
   CREATE EXTENSION postgis;
   ```

### Q4: 連接資料庫時出現「password authentication failed」

**解決方案**：
- 檢查 `.env` 中的密碼是否正確
- 使用 pgAdmin 4 測試連接
- 重置 postgres 用戶密碼：
  ```cmd
  psql -U postgres
  ALTER USER postgres WITH PASSWORD '新密碼';
  ```

---

## 驗證清單

安裝完成後，請確認：

- ✅ PostgreSQL 服務正在運行
- ✅ psql 命令可用（或 PATH 已設定）
- ✅ pgAdmin 4 可連接到資料庫
- ✅ 資料庫 `traffic_enforcement` 已創建
- ✅ PostGIS 擴展已啟用
- ✅ `.env` 文件已配置
- ✅ 後端依賴安裝成功
- ✅ 資料庫初始化成功

---

## 完成後

安裝完成後，請回到主系統並：

1. **啟動完整版後端**：
   ```cmd
   python backend\app\main.py
   ```

2. **訪問 API 文件**：
   http://localhost:8000/docs

3. **啟動前端**：
   ```cmd
   cd animal-crossing-dashboard
   npm run dev
   ```

4. **訪問系統**：
   http://localhost:5173

---

**預計完成時間**：15-20 分鐘

如有任何問題，請參考「常見問題」章節或查看系統日誌。

🌿 祝安裝順利！
