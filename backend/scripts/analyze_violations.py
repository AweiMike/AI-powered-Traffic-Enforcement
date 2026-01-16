# -*- coding: utf-8 -*-
"""分析違規條款分類"""

import pandas as pd
import json
import os


def main():
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(base_path)

    df = pd.read_excel(os.path.join(project_root, "舉發案件綜合查詢.xlsx"))

    # 分析違規條款1
    violations = df["違規條款1"].dropna().value_counts()

    result = {
        "total_records": len(df),
        "unique_violations": len(violations),
        "top_violations": violations.head(50).to_dict(),
        "all_violations": violations.to_dict(),
    }

    output_path = os.path.join(base_path, "data", "violations_analysis.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Total records: {len(df)}")
    print(f"Unique violation types: {len(violations)}")
    print("\nTop 20 violations:")
    for v, count in violations.head(20).items():
        print(f"  [{count:4d}] {v}")


if __name__ == "__main__":
    main()
