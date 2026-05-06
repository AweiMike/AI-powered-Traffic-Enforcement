"""直接從 EIS 檔（事故調查表資料匯出 .txt）回補酒駕欄位

當 import 流程是舊版、不會回補既有 case_id 的新欄位時，這支腳本
直接讀 EIS .txt 檔、case-level rollup、UPDATE DB，繞過 import 邏輯。

使用方式
========

1. 把 EIS .txt 檔放在 backend/事故調查表資料/ 資料夾
   （支援多個檔案，會全部處理）

2. 執行：
       cd backend
       python scripts/backfill_dui_from_eis.py

3. 觀察輸出：每個 case_id 是否被更新

判定邏輯（與 imports.py case_rollup 一致）
==========================================

對每個 case_id，掃描所有當事者 row：
- 飲酒情形代碼 ∈ {04,05,06,07,08} → 視為飲酒
- 當事者區分子類別代碼 H 開頭 → 行人，排除
- 任何非行人當事者飲酒 → is_dui_crash_party = True

不管 DB 中該 case_id 是否已標記，一律重算（idempotent）。
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


def _parse_eis_files(eis_dir: Path) -> dict:
    """掃描所有 EIS .txt 檔，回傳 {case_id: rollup} dict"""
    case_rollup: dict[str, dict] = {}

    txt_files = sorted(eis_dir.glob("*.txt"))
    if not txt_files:
        print(f"⚠ 找不到 EIS 檔：{eis_dir}")
        return case_rollup

    print(f"掃描 {len(txt_files)} 個 EIS 檔...")

    for txt in txt_files:
        try:
            content = txt.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = txt.read_text(encoding="big5")
            except Exception as e:
                print(f"  ✗ {txt.name}: 編碼錯誤 ({e})")
                continue

        lines = content.splitlines()
        if not lines:
            continue

        # 找 header (含 「總編號」 或 「案件編號」 的那一行)
        header_idx = -1
        for i, line in enumerate(lines):
            if "總編號" in line and "@" in line:
                header_idx = i
                break
        if header_idx == -1:
            print(f"  ✗ {txt.name}: 找不到 header")
            continue

        headers = lines[header_idx].split("@")
        # 找關鍵欄位 index
        try:
            idx_case_id = next(i for i, h in enumerate(headers) if "總編號" in h or h.strip() == "案件編號")
        except StopIteration:
            print(f"  ✗ {txt.name}: 找不到 案件編號 欄位")
            continue

        idx_subtype = next((i for i, h in enumerate(headers) if "子類別代碼" in h or "26.當事者區分(類別)子類別代碼" in h), -1)
        idx_drinking = next((i for i, h in enumerate(headers) if "飲酒情形代碼" in h or "32.飲酒情形" in h), -1)
        idx_cause_code = next((i for i, h in enumerate(headers) if "34.初步分析研判-個別代碼" in h), -1)
        idx_cause_text = next((i for i, h in enumerate(headers) if "34.初步分析研判子類別-主要" in h), -1)

        if idx_drinking == -1 and idx_subtype == -1:
            print(f"  ✗ {txt.name}: 沒有 飲酒情形 + 子類別代碼 兩欄，無法判定")
            continue

        rows_in_file = 0
        for line in lines[header_idx + 1:]:
            parts = line.split("@")
            if len(parts) <= max(idx_case_id, idx_subtype, idx_drinking):
                continue

            case_id = parts[idx_case_id].strip()
            if not case_id:
                continue

            subtype = parts[idx_subtype].strip() if idx_subtype != -1 else ""
            drinking = parts[idx_drinking].strip().lstrip("0") if idx_drinking != -1 else ""
            if not drinking and idx_drinking != -1:
                drinking = parts[idx_drinking].strip()
            cause_code = parts[idx_cause_code].strip().lstrip("0") if idx_cause_code != -1 else ""
            cause_text = parts[idx_cause_text].strip() if idx_cause_text != -1 else ""

            is_pedestrian = subtype.startswith("H")
            is_drinking_primary = drinking in DRINKING_CODES
            is_drinking_secondary = (
                cause_code == "53"
                or any(kw in cause_text for kw in ALCOHOL_KEYWORDS)
            )
            is_drinking = is_drinking_primary or is_drinking_secondary

            bucket = case_rollup.setdefault(case_id, {
                "has_drinking_party": False,
                "driver_subtype_code": None,
                "driver_drinking_code": None,
                "_picked_priority": 0,
            })

            if not is_pedestrian and is_drinking:
                bucket["has_drinking_party"] = True

            priority = 3 if (not is_pedestrian and is_drinking) else (2 if not is_pedestrian else 1)
            if priority > bucket["_picked_priority"]:
                bucket["_picked_priority"] = priority
                bucket["driver_subtype_code"] = subtype[:10] if subtype else None
                bucket["driver_drinking_code"] = drinking[:2] if drinking else None
            rows_in_file += 1

        print(f"  ✓ {txt.name}: 處理 {rows_in_file} rows")

    return case_rollup


def main():
    from app.database import get_db
    from app.models.core import Crash

    # EIS 檔路徑：backend/事故調查表資料/
    eis_dir = Path(__file__).resolve().parents[2] / "事故調查表資料"
    if not eis_dir.exists():
        # 也試試 backend/scripts/../事故調查表資料/
        eis_dir = Path(__file__).resolve().parents[1].parent / "事故調查表資料"
    if not eis_dir.exists():
        print(f"❌ 找不到 EIS 資料夾：{eis_dir}")
        print(f"   請把 EIS .txt 檔放在 [專案根目錄]/事故調查表資料/")
        return

    case_rollup = _parse_eis_files(eis_dir)
    print()
    print(f"從 EIS 檔抓到 {len(case_rollup)} 個 case_id")

    flagged_in_eis = sum(1 for v in case_rollup.values() if v["has_drinking_party"])
    print(f"其中飲酒非行人案件: {flagged_in_eis} 件")

    if flagged_in_eis == 0:
        print()
        print("⚠ EIS 檔中沒有任何飲酒（4-8）的非行人案件")
        print("   可能 EIS 匯出時沒勾選 32. 飲酒情形代碼 欄位")
        return

    # 套用到 DB
    db = next(get_db())
    updated, not_in_db, already_marked = 0, 0, 0

    print()
    print("套用到 DB...")
    for cid, info in case_rollup.items():
        crash = db.query(Crash).filter(Crash.case_id == cid).first()
        if not crash:
            if info["has_drinking_party"]:
                not_in_db += 1
            continue

        changed = False

        # 寫入 drinking_code 與 party_subtype_code（不論是否有飲酒）
        if info.get("driver_drinking_code") and not crash.drinking_code:
            crash.drinking_code = info["driver_drinking_code"]
            changed = True
        if info.get("driver_subtype_code") and not crash.party_subtype_code:
            crash.party_subtype_code = info["driver_subtype_code"]
            changed = True

        # 標記酒駕
        if info["has_drinking_party"]:
            if crash.is_dui_crash_party:
                already_marked += 1
            else:
                crash.is_dui_crash_party = True
                crash.suspected_alcohol = True
                updated += 1
                changed = True

    db.commit()

    total_flagged = db.query(Crash).filter(Crash.is_dui_crash_party == True).count()
    print()
    print("=" * 60)
    print(f"完成：")
    print(f"  新標記為酒駕:  {updated} 件")
    print(f"  已標過略過:    {already_marked} 件")
    print(f"  EIS 有但 DB 找不到 case_id:  {not_in_db} 件")
    print(f"  目前 DB is_dui_crash_party = True 共 {total_flagged} 件")
    print("=" * 60)


if __name__ == "__main__":
    main()
