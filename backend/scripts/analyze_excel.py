# -*- coding: utf-8 -*-
"""分析 Excel 檔案結構"""

import pandas as pd
import os
import json


def analyze_file(filepath, name):
    """分析單一 Excel 檔案"""
    result = {"name": name, "path": filepath}

    if not os.path.exists(filepath):
        result["error"] = "File not found"
        return result

    try:
        df = pd.read_excel(filepath)
        result["rows"] = len(df)
        result["columns"] = list(df.columns)

        # 取前 3 筆範例資料
        sample = df.head(3).to_dict(orient="records")
        result["sample"] = sample

        # 分析資料類型
        dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
        result["dtypes"] = dtypes

    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(base_path)

    files = [
        (os.path.join(project_root, "交通事故案件清冊_已處理.xlsx"), "交通事故案件"),
        (os.path.join(project_root, "舉發案件綜合查詢.xlsx"), "舉發案件"),
    ]

    results = []
    for filepath, name in files:
        result = analyze_file(filepath, name)
        results.append(result)

    # 輸出為 JSON
    output_path = os.path.join(base_path, "data", "excel_analysis.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    print(f"Analysis saved to: {output_path}")

    # 簡要輸出
    for r in results:
        print(f"\n=== {r['name']} ===")
        if "error" in r:
            print(f"Error: {r['error']}")
        else:
            print(f"Rows: {r['rows']}")
            print(f"Columns ({len(r['columns'])}): {r['columns']}")


if __name__ == "__main__":
    main()
