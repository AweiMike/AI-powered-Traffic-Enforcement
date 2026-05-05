"""手動標記酒駕事故黑數案件（人為疏失資料補強）

當 EIS 飲酒情形代碼（32.）+ 肇因（34.）都被同仁忘記填寫時，
系統無法從結構化資料偵測酒駕。此腳本維護人工覆核確認為酒駕的
case_id 清單，補強自動偵測。

使用方式
========

執行：
    cd backend
    python scripts/backfill_manual_dui.py

新增案件：
    1. 在下方 MANUAL_DUI_CRASH_CASES 列表加入新項目
    2. 重新執行此腳本（會跳過已標記的案件，僅處理新項目）

原則
====

- 只有「人工清冊已確認」且「EIS 結構化資料完全空白」的案件才該加入
- 加入時要記錄 verified_by 來源，方便日後追溯
- is_dui_crash_party 一旦設為 True，後續再匯入 EIS 不會被覆蓋（保守覆寫邏輯）
"""
import sys
from pathlib import Path

# 加入 backend 到 sys.path 讓 app.* 可以 import
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.disable(logging.WARNING)


# ============================================================
# 人工覆核清單：以下 case_id 已由人工確認為酒駕肇事，補強自動偵測
# 排序：時間倒序（新的加在最上面）
# ============================================================
MANUAL_DUI_CRASH_CASES = [
    # === 待補充 ===
    # 2026-04-26 大智路145巷 (清冊註記人為「林清勇」，A2，肇因「酒醉(後)駕駛」)
    # 起初推測 case_id = 11504ACC91B3116（DB 內當日大智路唯一案件），但用戶
    # 確認該編號不對應林清勇，故暫時撤回。等正確 case_id 確認後再加入。
    #
    # 範例格式：
    # {
    #     "case_id": "...",
    #     "occurred": "YYYY-MM-DD HH:MM",
    #     "location": "...",
    #     "severity": "A1/A2/A3",
    #     "note": "為何要人工覆核（描述 EIS 缺漏狀況）",
    #     "verified_by": "覆核來源（清冊檔名 / 部門 / 日期）",
    # },
]


def main():
    from app.database import get_db
    from app.models.core import Crash

    db = next(get_db())

    updated, already_marked, not_found = 0, 0, []

    print("=" * 60)
    print("酒駕肇事黑數人工覆核 - 回補腳本")
    print("=" * 60)
    print(f"清單共 {len(MANUAL_DUI_CRASH_CASES)} 件")
    print()

    for entry in MANUAL_DUI_CRASH_CASES:
        case_id = entry["case_id"]
        crash = db.query(Crash).filter(Crash.case_id == case_id).first()

        if not crash:
            not_found.append(entry)
            print(f"  [!] {case_id} 在 DB 找不到（可能尚未匯入該批次資料）")
            continue

        if crash.is_dui_crash_party:
            already_marked += 1
            print(f"  [✓] {case_id} 已標記為酒駕肇事，略過")
            continue

        crash.is_dui_crash_party = True
        crash.suspected_alcohol = True  # 同步舊欄位
        updated += 1
        print(f"  [+] {case_id} 標記為酒駕肇事")
        print(f"       時間: {entry['occurred']}  地點: {entry['location']}")
        print(f"       來源: {entry['verified_by']}")

    db.commit()

    print()
    print("=" * 60)
    print(f"完成：新標 {updated} 件、跳過已標 {already_marked} 件、找不到 {len(not_found)} 件")
    print("=" * 60)

    if not_found:
        print()
        print("⚠ 以下案件在 DB 找不到（可能該期間 EIS 尚未匯入）：")
        for entry in not_found:
            print(f"  - {entry['case_id']} ({entry['occurred']})")
        print()
        print("處置：先匯入該期間 EIS 後，重新執行此腳本即可。")
        sys.exit(1)


if __name__ == "__main__":
    main()
