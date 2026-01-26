import pandas as pd

# 模擬 imports.py 的邏輯
df_raw = pd.read_excel(r'D:\Programming\精準執法儀表板系統\交通事故案件清冊1120101-1150120.xls', header=None)

# 自動偵測標題列
header_row = 0
for i in range(min(10, len(df_raw))):
    row_values = [str(v).strip() for v in df_raw.iloc[i] if pd.notna(v)]
    row_text = ' '.join(row_values)
    if '案件編號' in row_text or '發生時間' in row_text or '事故編號' in row_text:
        header_row = i
        print(f"找到標題列: 第 {i+1} 列 (索引 {i})")
        break

# 重新讀取
df = pd.read_excel(r'D:\Programming\精準執法儀表板系統\交通事故案件清冊1120101-1150120.xls', header=header_row)

# 清理欄位名稱
df.columns = [str(c).strip().replace('\n', '').replace(' ', '') for c in df.columns]

print("\n=== 清理後的欄位名稱 ===")
for i, col in enumerate(df.columns):
    print(f"  欄{i}: '{col}'")

print(f"\n總資料列數: {len(df)}")

print("\n=== 第一筆資料 ===")
first_row = df.iloc[0]
for col in ['案件編號', '發生時間', '發生地點', '交通事故類別']:
    if col in df.columns:
        print(f"  {col}: {first_row[col]}")
    else:
        print(f"  {col}: [欄位不存在]")
