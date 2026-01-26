import pandas as pd

# 讀取 Excel 檔案，不使用任何標題
df = pd.read_excel(r'D:\Programming\精準執法儀表板系統\交通事故案件清冊1120101-1150120.xls', header=None)

print("=== 檔案結構分析 ===")
print(f"總列數: {len(df)}")
print(f"總欄數: {len(df.columns)}")

print("\n=== 前 5 列內容 ===")
for i in range(min(5, len(df))):
    print(f"\n--- 第 {i+1} 列 ---")
    for j, val in enumerate(df.iloc[i]):
        if pd.notna(val) and str(val).strip():
            print(f"  欄{j}: {val}")

print("\n=== 找到實際欄位標題 ===")
# 尋找包含「編號」或「發生」字樣的列作為標題列
for i in range(min(10, len(df))):
    row_str = ' '.join([str(v) for v in df.iloc[i] if pd.notna(v)])
    if '發生' in row_str or '編號' in row_str or '事故' in row_str:
        print(f"可能的標題在第 {i+1} 列:")
        cols = [str(v) for v in df.iloc[i] if pd.notna(v) and str(v).strip()]
        for c in cols:
            print(f"  - {c}")
        break
