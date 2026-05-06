"""從既有的 drinking_code 與 party_subtype_code 重新計算 is_dui_crash_party

當匯入時 backfill 邏輯失效（例如同事 build 版本太舊），這支腳本可以
直接從 DB 中已寫入的 drinking_code / party_subtype_code / cause 等欄位
重算 is_dui_crash_party 旗標。

使用方式:
    cd backend
    python scripts/backfill_dui_from_drinking.py

判定邏輯（與 imports.py case_rollup 一致）：
- 飲酒情形代碼 ∈ {04,05,06,07,08} → 視為飲酒
- 當事者區分子類別代碼 H 開頭 → 視為行人，不算
- 補強信號：cause 含「酒醉/酒後/飲酒/醉駕」
- 必須非行人 + 有飲酒信號 → is_dui_crash_party = True
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.disable(logging.WARNING)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DRINKING_CODES = {"04", "05", "06", "07", "08", "4", "5", "6", "7", "8"}
ALCOHOL_KEYWORDS = ["酒醉", "酒後", "飲酒", "醉駕"]


def main():
    from app.database import get_db
    from app.models.core import Crash

    db = next(get_db())

    candidates = db.query(Crash).filter(Crash.is_dui_crash_party != True).all()

    print(f"檢查 {len(candidates)} 件未標記為酒駕的事故...")

    updated = 0
    for c in candidates:
        # 主信號：飲酒情形代碼
        drinking = (c.drinking_code or "").strip()
        is_drinking_primary = drinking in DRINKING_CODES

        # 補強信號：肇因文字含關鍵字
        cause_text = c.cause or ""
        is_drinking_secondary = any(kw in cause_text for kw in ALCOHOL_KEYWORDS)

        if not (is_drinking_primary or is_drinking_secondary):
            continue

        # 排除行人（party_subtype_code 以 H 開頭）
        subtype = (c.party_subtype_code or "").strip()
        if subtype.startswith("H"):
            continue

        # 標記為酒駕
        c.is_dui_crash_party = True
        c.suspected_alcohol = True
        updated += 1

    db.commit()

    print(f"完成：共回補 {updated} 件")

    # 驗證
    total_flagged = db.query(Crash).filter(Crash.is_dui_crash_party == True).count()
    print(f"目前 is_dui_crash_party = True 共 {total_flagged} 件")


if __name__ == "__main__":
    main()
