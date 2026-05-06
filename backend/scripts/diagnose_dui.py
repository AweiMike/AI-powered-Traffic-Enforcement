"""酒駕資料一致性診斷

當「肇事舉發」數字異常少時，跑這支腳本診斷：
  cd backend
  python scripts/diagnose_dui.py

會輸出：
  1. DB 中酒駕相關欄位填寫率
  2. 飲酒情形代碼分佈（檢查匯入時是否有抓到該欄位）
  3. is_dui_crash_party 與 drinking_code 是否一致
  4. 程式碼版本確認（是否包含 backfill 邏輯）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.disable(logging.WARNING)

# Windows console encoding fix
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main():
    from sqlalchemy import func, or_, and_
    from app.database import get_db
    from app.models.core import Crash

    db = next(get_db())

    print("=" * 70)
    print("酒駕資料一致性診斷")
    print("=" * 70)

    # 1. 整體統計
    total = db.query(Crash).count()
    has_drinking = db.query(Crash).filter(
        Crash.drinking_code.isnot(None), Crash.drinking_code != ''
    ).count()
    has_subtype = db.query(Crash).filter(
        Crash.party_subtype_code.isnot(None), Crash.party_subtype_code != ''
    ).count()
    flagged = db.query(Crash).filter(Crash.is_dui_crash_party == True).count()
    suspected = db.query(Crash).filter(Crash.suspected_alcohol == True).count()

    print(f"\n[1] 整體統計")
    print(f"   Crash 總筆數:                {total}")
    print(f"   is_dui_crash_party = True:   {flagged}")
    print(f"   suspected_alcohol = True:    {suspected} (應 ~ is_dui_crash_party)")
    print(f"   drinking_code 有值:          {has_drinking}  ({has_drinking*100//max(total,1)}%)")
    print(f"   party_subtype_code 有值:     {has_subtype}  ({has_subtype*100//max(total,1)}%)")

    if has_drinking == 0:
        print()
        print(f"   ⚠️  drinking_code 全部空白 → EIS 匯入時沒抓到「32. 飲酒情形代碼」欄位")
        print(f"      可能原因：")
        print(f"      (a) 匯入的 EIS 檔沒有勾選「26. 當事者區分(類別)子類別代碼(車種)」")
        print(f"          與「32. 飲酒情形代碼」這兩欄")
        print(f"      (b) 匯入版本是舊版（沒有 case-level rollup 邏輯）")
        return

    # 2. 飲酒情形代碼分佈
    print(f"\n[2] 飲酒情形代碼分佈")
    rows = db.query(Crash.drinking_code, func.count(Crash.id)).group_by(
        Crash.drinking_code
    ).order_by(func.count(Crash.id).desc()).limit(15).all()
    for code, cnt in rows:
        flag = " ← 有飲酒" if code in {"04", "05", "06", "07", "08", "4", "5", "6", "7", "8"} else ""
        print(f"   '{code}': {cnt}{flag}")

    # 3. drinking 4-8 但 is_dui_crash_party=False（應為 True 卻沒標記）
    drinking_codes_set = ['04', '05', '06', '07', '08', '4', '5', '6', '7', '8']
    should_be_true = db.query(Crash).filter(
        Crash.drinking_code.in_(drinking_codes_set),
        ~Crash.party_subtype_code.like('H%') if has_subtype else True,
        Crash.is_dui_crash_party != True,
    ).count()
    print(f"\n[3] 應為 True 但未標記:        {should_be_true} 件")
    if should_be_true > 0:
        print(f"   ⚠️  這些案件 drinking_code 是 4-8 但 is_dui_crash_party 仍 False")
        print(f"   原因：匯入時 backfill 邏輯沒跑到（可能用了舊版 imports.py）")
        print(f"   解法：執行下列指令手動回補")
        print(f"          python scripts/backfill_dui_from_drinking.py")

    # 4. 程式碼版本確認
    print(f"\n[4] 程式碼版本確認")
    imports_path = Path(__file__).resolve().parents[1] / "app" / "api" / "imports.py"
    text = imports_path.read_text(encoding="utf-8")
    has_rollup = "case_rollup" in text
    has_backfill = "回補新加入的酒駕欄位" in text or "回補新欄位" in text
    has_secondary = "ALCOHOL_CAUSE_CODES" in text or "ALCOHOL_KEYWORDS" in text
    print(f"   case_rollup 預掃描邏輯:     {'✓' if has_rollup else '✗ 缺少'}")
    print(f"   既有 case 回補新欄位:       {'✓' if has_backfill else '✗ 缺少'}")
    print(f"   肇因/關鍵字補強信號:        {'✓' if has_secondary else '✗ 缺少'}")
    if not (has_rollup and has_backfill and has_secondary):
        print()
        print(f"   ⚠️  程式碼版本不夠新，請更新到最新版的 backend")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
