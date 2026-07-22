# -*- coding: utf-8 -*-
"""單位名稱正規化 — 全站 canonical 慣例：短名（不帶警察局/分局前綴）"""
from typing import Optional


# 組織裁併對照（2026-07 岡林派出所轄區併入左鎮分駐所）：
# normalize 末端套用，歷史資料由 startup migration 自動收斂，未來匯入即歸併
UNIT_MERGES = {
    "岡林派出所": "左鎮分駐所",
}


def normalize_unit_name(name: Optional[str]) -> Optional[str]:
    """單位名稱正規化為短名。

    規則（依序）：
    1. None/空白 → None
    2. 剝除「臺南市政府警察局」前綴
    3. BMP 外罕見字（ord > 0xFFFF）一律換成「那」——EIS 事故表的𦰡拔→那拔
    4. 含「分局」→ 取「分局」之後的部分為短名（如「新化分局唪口派出所」→「唪口派出所」）；
       但若「分局」後為空（值就是「XX分局」本身）→ 保留原名
    5. 套用組織裁併對照 UNIT_MERGES（如「岡林派出所」→「左鎮分駐所」，2026-07 岡林轄區併入左鎮）

    純字串邏輯，不處理 pandas NaN（呼叫端須自行判斷 pd.isna）。
    不做長度截斷，由呼叫端依欄位長度限制截斷。
    """
    if name is None:
        return None

    cleaned = str(name).replace("臺南市政府警察局", "").strip()
    if not cleaned:
        return None

    # 那拔派出所異體字正規化：EIS 事故表用罕見字 U+26C61（𦰡，BMP 外字元），
    # 違規表用正常「那」。直接 str.replace 對不上（編碼/正規化差異），
    # 改用逐字元重建：凡是 BMP 外的罕見字（ord > 0xFFFF）一律換成「那」。
    if any(ord(ch) > 0xFFFF for ch in cleaned):
        cleaned = "".join("那" if ord(ch) > 0xFFFF else ch for ch in cleaned)

    if "分局" in cleaned:
        suffix = cleaned.split("分局", 1)[1].strip()
        if suffix:
            cleaned = suffix
        # else：值本身就是「XX分局」（未特定所），保留原名

    # 組織裁併：岡林派出所轄區已併入左鎮分駐所（2026-07），統計上不再獨立成列
    cleaned = UNIT_MERGES.get(cleaned, cleaned)

    return cleaned or None
