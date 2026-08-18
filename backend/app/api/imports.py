# -*- coding: utf-8 -*-
"""
資料匯入 API
提供前端上傳 Excel 檔案的介面
"""

import os
import random
import re
import tempfile
from datetime import datetime
from typing import Dict, Optional, Tuple

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import Crash, CrashParty, Ticket, Topic
from app.utils.data_health import run_batch_health_checks
from app.utils.units import normalize_unit_name

router = APIRouter()


# ============================================
# 違規條款主題分類規則
# ============================================
TOPIC_RULES = {
    "DUI": {
        "prefixes": ["3501", "3503", "3504", "7302", "7303"],
        "keywords": ["酒精", "酒駕", "酒測", "吸食毒品"],
    },
    "RED_LIGHT": {
        "prefixes": ["5301", "5302"],
        "keywords": ["闘紅燈", "紅燈越線", "紅燈右轉", "紅燈左轉", "紅燈迴轉"],
        "codes": ["6002030060", "6002030110"],
    },
    "DANGEROUS_DRIVING": {
        "prefixes": ["4000", "4301", "4304"],
        "keywords": ["超速", "危險駕駛", "逼車", "肇事逃逸"],
        "codes": ["6201", "6203", "6204", "4501030010", "4501030020"],
    },
}


# ============================================
# 區域中心座標對照表（用於無精確座標時的備援）
# ============================================
DISTRICT_COORDINATES = {
    "新化區": (23.0386, 120.3108),
    "山上區": (23.0975, 120.3547),
    "左鎮區": (23.0578, 120.4014),
    "玉井區": (23.1239, 120.4614),
    "楠西區": (23.1814, 120.4853),
    "南化區": (23.1417, 120.4731),
    "善化區": (23.1322, 120.2967),
    "大內區": (23.1203, 120.3508),
    "仁德區": (22.9722, 120.2331),
    "歸仁區": (22.9667, 120.2933),
    "關廟區": (22.9617, 120.3278),
    "龍崎區": (22.9622, 120.3847),
    "永康區": (23.0264, 120.2567),
    "東區": (22.9833, 120.2167),
    "南區": (22.9500, 120.1833),
    "北區": (23.0000, 120.2000),
    "中西區": (22.9917, 120.1917),
    "安南區": (23.0500, 120.1667),
    "安平區": (22.9917, 120.1667),
    "新營區": (23.3103, 120.3167),
    "鹽水區": (23.3203, 120.2661),
    "白河區": (23.3517, 120.4156),
    "柳營區": (23.2778, 120.3114),
    "後壁區": (23.3664, 120.3583),
    "東山區": (23.3258, 120.4036),
    "麻豆區": (23.1817, 120.2483),
    "下營區": (23.2347, 120.2647),
    "六甲區": (23.2314, 120.3472),
    "官田區": (23.1944, 120.3139),
    "佳里區": (23.1650, 120.1772),
    "學甲區": (23.2328, 120.1803),
    "西港區": (23.1222, 120.2028),
    "七股區": (23.1450, 120.1267),
    "將軍區": (23.1997, 120.1092),
    "北門區": (23.2672, 120.1261),
    "新市區": (23.0794, 120.2911),
    "安定區": (23.1014, 120.2353),
}


def get_district_coordinates(district: str) -> tuple:
    """根據區域名稱獲取中心座標"""
    if not district:
        return None, None
    
    # 移除「臺南市」「市」前綴
    clean_district = district.replace("臺南市", "").replace("台南市", "")
    if clean_district.startswith("市"):
        clean_district = clean_district[1:]
    
    # 直接查找
    if clean_district in DISTRICT_COORDINATES:
        lat, lng = DISTRICT_COORDINATES[clean_district]
        # 添加微小隨機偏移避免完全重疊（約 100-500 公尺）
        offset_lat = random.uniform(-0.003, 0.003)
        offset_lng = random.uniform(-0.003, 0.003)
        return lat + offset_lat, lng + offset_lng

    # 部分匹配
    for name, coords in DISTRICT_COORDINATES.items():
        if name in clean_district or clean_district in name:
            lat, lng = coords
            offset_lat = random.uniform(-0.003, 0.003)
            offset_lng = random.uniform(-0.003, 0.003)
            return lat + offset_lat, lng + offset_lng
    
    return None, None


# ============================================
# 工具函數
# ============================================


def parse_roc_datetime(roc_str) -> Optional[datetime]:
    """
    解析民國年日期時間
    支援格式：114/01/08 09:30:00, 114-01-08 09:30:00, 114/01/08
    """
    if pd.isna(roc_str) or not roc_str:
        return None

    roc_str = str(roc_str).strip()

    patterns = [
        (r"(\d{2,3})[/-](\d{1,2})[/-](\d{1,2})\s+(\d{1,2}):(\d{2}):(\d{2})", True),
        (r"(\d{2,3})[/-](\d{1,2})[/-](\d{1,2})\s+(\d{1,2}):(\d{2})", True),
        (r"(\d{2,3})[/-](\d{1,2})[/-](\d{1,2})", False),
    ]

    for pattern, has_time in patterns:
        match = re.match(pattern, roc_str)
        if match:
            groups = match.groups()
            roc_year = int(groups[0])
            month = int(groups[1])
            day = int(groups[2])
            year = roc_year + 1911

            if has_time:
                hour = int(groups[3])
                minute = int(groups[4])
                second = int(groups[5]) if len(groups) > 5 else 0
                return datetime(year, month, day, hour, minute, second)
            else:
                return datetime(year, month, day, 0, 0, 0)

    return None


def calculate_shift(dt: datetime) -> str:
    """根據時間計算班別 (01-12)，每班 2 小時"""
    if dt is None:
        return "01"
    shift = (dt.hour // 2) + 1
    return f"{shift:02d}"


def deidentify_address(address) -> Tuple[str, str]:
    """
    解析地址，返回: (行政區, 完整地點描述)
    注意：已移除去識別化，保留完整地址
    """
    if pd.isna(address) or not address:
        return ("未知", "未知地點")

    address = str(address).strip()

    # 提取行政區
    district_match = re.search(r"([\u4e00-\u9fa5]{2,3}區)", address)
    district = district_match.group(1) if district_match else "未知"

    # 保留完整地址（不再去識別化）
    location_desc = address.replace("臺南市", "").replace("台南市", "").strip()
    
    return (district, location_desc[:200] if location_desc else "未知地點")


def classify_age(age) -> Tuple[str, bool, bool]:
    """將年齡轉換為年齡組，返回: (年齡組, 是否高齡者, 是否青少年)"""
    if pd.isna(age) or age is None:
        return ("未知", False, False)

    try:
        age = int(float(age))
    except (ValueError, TypeError):
        return ("未知", False, False)

    # EIS 以 -1 表示「年齡未知」（如肇逃未查獲、物/動物當事者），
    # 不可落入 <14 判斷，否則未知年齡會被灌入青少年統計
    if age < 0:
        return ("未知", False, False)

    if age < 14:
        return ("<18", False, True)  # 未滿14歲，青少年
    elif age < 18:
        return ("<18", False, True)  # 青少年
    elif age < 25:
        return ("18-24", False, False)
    elif age < 45:
        return ("25-44", False, False)
    elif age < 65:
        return ("45-64", False, False)
    else:
        return ("65+", True, False)


# ================================================================
# 事故當事者層（core_crash_party）
# ================================================================
# ⚠️ 設計說明：core_crash 為案件層 rollup，年齡等欄位取自「代表當事者」。
#    高齡者被撞時代表當事者是對造駕駛，高齡者即從統計消失（實測低估 54%）。
#    本組 helper 將 EIS 的 per-當事者 row 完整落地，使族群判定改為 EXISTS。
#    ⚠️ 個資紅線：姓名／身分證／電話／住址／車牌一律不落地。

_ELDERLY_BAND_EDGES = ((70, "65-69"), (75, "70-74"), (80, "75-79"), (85, "80-84"))

_VEHICLE_GROUP_RULES = (
    ("機車", ("普通重型", "普通輕型", "大型重型")),
    ("慢速載具", ("腳踏自行車", "微型電動二輪", "電動輔助自行車", "農耕", "個人行動運具")),
)


def _party_age_band(age: Optional[int]) -> Optional[str]:
    """年齡分組：65 歲以上採 5 歲組（高齡分析需要），未滿 65 沿用粗分組"""
    if age is None or age < 0:
        return None
    if age < 18:
        return "<18"
    if age < 65:
        return "18-64"
    for edge, label in _ELDERLY_BAND_EDGES:
        if age < edge:
            return label
    return "85+"


def _party_role(subtype: str, big_type: str) -> str:
    """駕駛／乘客／行人。⚠️ 行人必須用子類別判定，大類別「人」含乘客（Wave 31 教訓）"""
    if "行人" in subtype or "輔助代步器材" in subtype:
        return "行人"
    if "乘客" in subtype or "乘客" in big_type:
        return "乘客"
    return "駕駛"


def _party_vehicle_group(subtype: str) -> str:
    """車種歸群（與分析報告口徑一致）"""
    sub = subtype or ""
    for group, keys in _VEHICLE_GROUP_RULES:
        if any(k in sub for k in keys):
            return group
    if "貨" in sub:
        return "貨車"
    if "自用" in sub:
        return "小客車"
    return "其他"


def collect_crash_parties(df) -> Dict[str, list]:
    """
    從 EIS DataFrame 收集當事者層資料。

    回傳 {case_id: [party_dict, ...]}；同一 (case_id, 順位) 只保留第一次出現
    （跨半年檔重疊時由呼叫端以 case 為單位覆寫，仍保持冪等）。
    """
    parties: Dict[str, list] = {}
    if df is None or len(df) == 0:
        return parties

    for _, row in df.iterrows():
        case_id = None
        for col_name in ["總編號(案件編號)", "總編號（案件編號）", "案件編號", "總編號"]:
            if col_name in row.index and pd.notna(row.get(col_name)):
                val = str(row.get(col_name)).strip()
                if val:
                    case_id = val
                    break
        if not case_id:
            continue

        order_raw = _safe_eis_str(row, "當事者順位").strip()
        order_norm = order_raw.lstrip("0") or order_raw
        try:
            party_order = int(float(order_norm))
        except (ValueError, TypeError):
            party_order = None

        bucket = parties.setdefault(case_id, [])
        if any(p["party_order"] == party_order for p in bucket if party_order is not None):
            continue  # 同案同順位重複列（跨檔重疊）

        age_raw = _safe_eis_str(row, "當事者事故發生時年齡")
        try:
            age = int(float(age_raw))
        except (ValueError, TypeError):
            age = None
        if age is not None and age < 0:      # EIS 以 -1 表示年齡未知
            age = None
        _, is_elderly, is_youth = classify_age(age)

        subtype = _safe_eis_str(row, "26.當事者區分(類別)")
        big_type = _safe_eis_str(row, "26.當事者區分(大類別)")
        injury = _safe_eis_str(row, "22.受傷程度")
        cause = _safe_eis_str(row, "34.初步分析研判子類別-個別")

        bucket.append({
            "case_id": case_id[:50],
            "party_order": party_order,
            "age": age,
            "age_band": _party_age_band(age),
            "gender": (_safe_eis_str(row, "17.當事者屬(性)別") or None),
            "is_elderly": bool(is_elderly),
            "is_youth": bool(is_youth),
            "party_subtype": (subtype[:60] or None),
            "role": _party_role(subtype, big_type),
            "vehicle_group": _party_vehicle_group(subtype),
            "license_status": (_safe_eis_str(row, "30.駕照狀態") or None),
            "protective_gear": (_safe_eis_str(row, "24.保護裝備") or None),
            "injury": (injury[:20] or None),
            "is_death_24h": injury == "24小時內死亡",
            "is_death_late": injury == "2-30日內死亡",
            "is_injured": injury == "受傷",
            "cause": (cause[:120] or None),
            "is_primary": party_order == 1,
            "no_fault": cause == "尚未發現肇事因素",
        })

    return parties


def persist_crash_parties(db, parties_by_case: Dict[str, list]) -> int:
    """以 case_id 為單位 delete-then-insert（冪等；重跑不會累加）"""
    if not parties_by_case:
        return 0
    written = 0
    case_ids = list(parties_by_case.keys())
    for i in range(0, len(case_ids), 500):        # 分批避免 SQLite 參數上限
        chunk = case_ids[i:i + 500]
        db.query(CrashParty).filter(CrashParty.case_id.in_(chunk)).delete(
            synchronize_session=False
        )
        for cid in chunk:
            for p in parties_by_case[cid]:
                db.add(CrashParty(**p))
                written += 1
        db.flush()
    return written


def recompute_party_rollups(db, case_ids: Optional[list] = None) -> Dict[str, int]:
    """
    以 core_crash_party 為唯一真實來源，重算 core_crash 的族群旗標與人數欄位。

    ⚠️ 兩族群的口徑刻意不同，因為防制標的不同：

    - **is_elderly＝任一當事者 ≥65 歲**（道安會報口徑）。高齡者被撞亦為防制標的
      （實測 32.8% 為非主責、唯一死亡案即屬此類），故不限角色。
      舊的代表當事者判定漏掉被撞的高齡者，低估 54%。
    - **is_youth＝任一「青少年駕駛」**（不含乘客/行人）。青少年專區之目的為
      騎乘者的執法與宣導；若比照高齡採「任一當事者」，會灌入 127 件僅有
      兒童乘客（含 107 名 0-11 歲）的案件而扭曲該專區。限定駕駛後為 273 件
      （舊 256 件，真實低估僅 +17）。
      需要「青少年以任何身分涉入」時，直接查 core_crash_party。
    """
    where = ""
    params: Dict[str, object] = {}
    if case_ids:
        marks = ",".join(f":c{i}" for i in range(len(case_ids)))
        where = f" WHERE case_id IN ({marks})"
        params = {f"c{i}": c for i, c in enumerate(case_ids)}

    sql = f"""
    UPDATE core_crash SET
      is_elderly = COALESCE((SELECT MAX(p.is_elderly) FROM core_crash_party p
                             WHERE p.case_id = core_crash.case_id), 0),
      is_youth   = COALESCE((SELECT MAX(p.is_youth)   FROM core_crash_party p
                             WHERE p.case_id = core_crash.case_id
                               AND p.role = '駕駛'), 0),
      elderly_party_count = COALESCE((SELECT COUNT(*) FROM core_crash_party p
                             WHERE p.case_id = core_crash.case_id AND p.is_elderly = 1), 0),
      elderly_death_count = COALESCE((SELECT COUNT(*) FROM core_crash_party p
                             WHERE p.case_id = core_crash.case_id AND p.is_elderly = 1
                               AND p.is_death_24h = 1), 0),
      elderly_late_death_count = COALESCE((SELECT COUNT(*) FROM core_crash_party p
                             WHERE p.case_id = core_crash.case_id AND p.is_elderly = 1
                               AND p.is_death_late = 1), 0),
      elderly_injury_count = COALESCE((SELECT COUNT(*) FROM core_crash_party p
                             WHERE p.case_id = core_crash.case_id AND p.is_elderly = 1
                               AND p.is_injured = 1), 0),
      elderly_primary_count = COALESCE((SELECT COUNT(*) FROM core_crash_party p
                             WHERE p.case_id = core_crash.case_id AND p.is_elderly = 1
                               AND p.is_primary = 1), 0),
      elderly_no_fault_count = COALESCE((SELECT COUNT(*) FROM core_crash_party p
                             WHERE p.case_id = core_crash.case_id AND p.is_elderly = 1
                               AND p.no_fault = 1), 0)
    {where}
    """
    from sqlalchemy import text as _sql_text
    db.execute(_sql_text(sql), params)
    db.commit()

    total = db.query(func.count(CrashParty.id)).scalar() or 0
    eld = db.query(func.count(Crash.id)).filter(Crash.is_elderly.is_(True)).scalar() or 0
    return {"party_rows": total, "elderly_cases": eld}


def classify_evehicle(vehicle_type: str) -> Tuple[Optional[str], bool]:
    """
    識別慢車/電動車類型
    返回: (evehicle_type, is_evehicle)
    
    車種對照：
    - 微型電動二輪車
    - 電動輔助自行車
    - 電動自行車
    - 自行車/腳踏車
    """
    if pd.isna(vehicle_type) or not vehicle_type:
        return (None, False)
    
    vt = str(vehicle_type).strip()
    
    # 微型電動二輪車識別
    if any(k in vt for k in ["微型電動二輪", "微電動二輪", "微電車", "電動二輪車"]):
        return ("微型電動二輪車", True)
    
    # 電動輔助自行車識別
    if any(k in vt for k in ["電動輔助自行車", "電輔自行車", "電輔車", "電助車"]):
        return ("電動輔助自行車", True)
    
    # 電動自行車（較舊的分類，可能是微電車或電輔車）
    if any(k in vt for k in ["電動自行車", "電動腳踏車"]):
        return ("電動輔助自行車", True)  # 預設歸類為電輔車
    
    # 一般自行車
    if any(k in vt for k in ["自行車", "腳踏車", "單車"]):
        return ("一般自行車", True)
    
    return (None, False)


def classify_violation_topic(code: str, name: str) -> Dict[str, bool]:
    """根據違規條款分類主題"""
    result = {"dui": False, "red_light": False, "dangerous": False}

    if pd.isna(code):
        return result

    code = str(code).strip()
    name = str(name) if not pd.isna(name) else ""

    # 檢查 DUI
    for prefix in TOPIC_RULES["DUI"]["prefixes"]:
        if code.startswith(prefix):
            result["dui"] = True
            break
    for keyword in TOPIC_RULES["DUI"]["keywords"]:
        if keyword in name:
            result["dui"] = True
            break

    # 檢查闘紅燈
    for prefix in TOPIC_RULES["RED_LIGHT"]["prefixes"]:
        if code.startswith(prefix):
            result["red_light"] = True
            break
    for specific_code in TOPIC_RULES["RED_LIGHT"].get("codes", []):
        if code.startswith(specific_code):
            result["red_light"] = True
            break
    for keyword in TOPIC_RULES["RED_LIGHT"]["keywords"]:
        if keyword in name:
            result["red_light"] = True
            break

    # 檢查危險駕駛
    for prefix in TOPIC_RULES["DANGEROUS_DRIVING"]["prefixes"]:
        if code.startswith(prefix):
            result["dangerous"] = True
            break
    for specific_code in TOPIC_RULES["DANGEROUS_DRIVING"].get("codes", []):
        if code.startswith(specific_code):
            result["dangerous"] = True
            break
    for keyword in TOPIC_RULES["DANGEROUS_DRIVING"]["keywords"]:
        if keyword in name:
            result["dangerous"] = True
            break

    return result


def get_severity_weight(severity: str) -> int:
    """取得事故嚴重度權重"""
    return {"A1": 5, "A2": 3, "A3": 1}.get(severity, 1)


# ============================================
# EIS 格式支援函數（警政署公總EIS匯出格式）
# ============================================


def detect_crash_format(columns: list) -> str:
    """
    自動偵測 Excel 是 EIS 格式還是分局舊格式。
    EIS 特徵欄位：GPS緯度、1.發生時間、總編號(案件編號)、處理單位名稱分局層
    """
    eis_markers = [
        "GPS緯度", "GPS經度", "總編號(案件編號)",
        "1.發生時間", "處理單位名稱分局層",
        "3-1.24小時內死亡人數", "2-1.發生地址_路街",
    ]
    match_count = sum(1 for m in eis_markers if m in columns)
    return "EIS" if match_count >= 2 else "LEGACY"


def parse_eis_datetime(date_val, time_val) -> Optional[datetime]:
    """
    解析 EIS 格式日期時間。
    date_val: YYYYMMDD 整數/字串（如 20240108）
    time_val: HHMMSS 整數（如 93000 → 09:30:00）
    """
    if pd.isna(date_val):
        return None
    try:
        date_str = str(int(float(date_val))).zfill(8)
        year = int(date_str[:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])

        hour, minute, second = 0, 0, 0
        if not pd.isna(time_val):
            time_int = int(float(time_val))
            hour = time_int // 10000
            minute = (time_int % 10000) // 100
            second = time_int % 100

        return datetime(year, month, day, hour, minute, second)
    except (ValueError, TypeError):
        return None


def _safe_eis_str(row, col_name: str) -> str:
    """安全取得 EIS 欄位的字串值，缺失或無效時回傳空字串"""
    if col_name not in row.index:
        return ""
    val = row.get(col_name)
    if pd.isna(val):
        return ""
    s = str(val).strip()
    return "" if s in ("nan", "None", "") else s


def build_eis_location(row) -> str:
    """
    從 EIS 多欄位地址組合成 location_desc。
    格式：路街+段 / 交叉路口+段（或公路路線）
    """
    road = _safe_eis_str(row, "2-1.發生地址_路街")
    segment = _safe_eis_str(row, "2-1.發生地址_段")
    cross = _safe_eis_str(row, "2-1.發生交叉路口_路街口")
    if not cross:
        cross = _safe_eis_str(row, "2-1.發生地址_交叉路口_路街口")
    cross_seg = _safe_eis_str(row, "2-1.發生交叉路口_段")
    highway = _safe_eis_str(row, "2-2.發生-路線-公路(國道/省道/縣道/鄉道)")
    # 全選條件匯出的欄名無「2-1.」前綴（發生地址_其他），兩種都認
    other = _safe_eis_str(row, "2-1.發生地址_其他") or _safe_eis_str(row, "發生地址_其他")

    parts = []
    if road:
        parts.append(road + segment)
    if cross:
        parts.append(cross + cross_seg)
    if highway and not road:
        parts.append(highway)
    if other and not parts:
        parts.append(other)

    if not parts:
        return "未知地點"
    if len(parts) >= 2:
        return f"{parts[0]} / {parts[1]}"
    return parts[0]


def extract_eis_district(row) -> str:
    """從 EIS 資料取得行政區名稱"""
    # 優先使用明確的行政區欄位
    for col in ["2-1.發生市區鄉鎮", "市區鄉鎮"]:
        val = _safe_eis_str(row, col)
        if val:
            clean = val.replace("臺南市", "").replace("台南市", "").strip()
            if clean:
                return clean

    # 備援：從處理單位名稱分局層推導
    precinct = _safe_eis_str(row, "處理單位名稱分局層")
    if precinct:
        precinct_clean = precinct.replace("臺南市政府警察局", "").strip()
        # 分局名稱與行政區的簡易對應
        precinct_to_district = {
            "新化分局": "新化區", "歸仁分局": "歸仁區", "善化分局": "善化區",
            "永康分局": "永康區", "白河分局": "白河區", "新營分局": "新營區",
            "麻豆分局": "麻豆區", "佳里分局": "佳里區", "學甲分局": "學甲區",
            "玉井分局": "玉井區",
            "第一分局": "東區", "第二分局": "中西區", "第三分局": "安南區",
            "第四分局": "安平區", "第五分局": "北區", "第六分局": "南區",
        }
        if precinct_clean in precinct_to_district:
            return precinct_to_district[precinct_clean]

    return "未知"


def clean_precinct_name(raw) -> Optional[str]:
    """清除分局全稱前綴，只保留如『新化分局』；並正規化罕見異體字。"""
    if pd.isna(raw) or not raw:
        return None
    name = str(raw).replace("臺南市政府警察局", "").strip()
    # 那拔派出所異體字正規化：EIS 事故表用罕見字 U+26C61（𦰡，BMP 外字元），違規表用正常「那」。
    # 直接 str.replace 對不上（編碼/正規化差異），改用逐字元重建：
    # 凡是 BMP 外的罕見字（ord > 0xFFFF）一律換成「那」，這樣「𦰡拔」→「那拔」。
    if any(ord(ch) > 0xFFFF for ch in name):
        name = "".join("那" if ord(ch) > 0xFFFF else ch for ch in name)
    return name or None


def extract_sub_unit(row) -> Optional[str]:
    """轄區派出所（sub_unit）統一取值 + 正規化。

    欄名相容（EIS 不同匯出模式對同一資料用不同欄名）：
    - 所轄單位名稱       —— 部分欄位匯出（手動加選欄位）
    - 管轄單位名稱       —— 全選條件匯出（欄名不同，內容同為轄區派出所）
    - 處理單位名稱派出所 —— 備援（實際處理單位，多為交通分隊）

    值正規化：全選條件檔的值是全稱「臺南市政府警察局新化分局𦰡拔派出所」，
    需剝除警察局 + 分局前綴成短名「那拔派出所」，才與既有 DB 的 sub_unit 值一致
    （否則派出所統計會因同所異名而分裂成兩組）。
    值本身就是「新化分局」（未特定所）時保留原名。

    正規化邏輯統一委由 app.utils.units.normalize_unit_name 處理（全站共用，
    與 core_ticket.unit_code 的正規化口徑一致）。
    """
    val = (
        _safe_eis_str(row, "所轄單位名稱")
        or _safe_eis_str(row, "管轄單位名稱")
        or _safe_eis_str(row, "處理單位名稱派出所")
    )
    if not val:
        return None
    name = normalize_unit_name(val)
    return name[:100] if name else None


def has_subunit_column(df) -> bool:
    """檔案是否帶有轄區派出所欄位（兩種匯出模式的欄名皆認得）"""
    return any(
        ("所轄單位名稱" in str(c)) or ("管轄單位名稱" in str(c))
        for c in df.columns
    )


def _row_official_severity(row) -> Optional[str]:
    """取出該列的官方「事故類別」值（A1/A2/A3），無官方值回傳 None。"""
    for col in ("事故類別", "交通事故類別"):
        v = _safe_eis_str(row, col)
        if v:
            v = (v.upper().replace("Ａ", "A")
                 .replace("１", "1").replace("２", "2").replace("３", "3"))
            if v in ("A1", "A2", "A3"):
                return v
    return None


def backfill_official_severity(existing, row, stats) -> None:
    """重複匯入時，以較新匯出檔的「官方事故類別」回補既有案件的 severity 與死傷。

    背景：EIS 同一案件在不同時間匯出，severity/傷亡會隨調查成熟而更新
    （傷亡人數回填、A2/A3 改判）。若舊檔先匯入、新檔後到，案件會因去重被略過，
    導致官方判定永遠進不了 DB（實證：6/1-6/7 A2 官方 26 件，先舊後新只剩 24）。

    僅當該列真的帶官方「事故類別」值（A1/A2/A3）時才覆寫——
    死傷推導出的 severity 不覆寫官方值；死傷人數也僅在官方檔且欄位存在時同步。
    """
    new_sev = _row_official_severity(row)
    if not new_sev:
        return
    if new_sev != existing.severity:
        existing.severity = new_sev
        existing.severity_weight = get_severity_weight(new_sev)
        stats["updated"] = stats.get("updated", 0) + 1
    if ("3-1.24小時內死亡人數" in row.index) or ("死亡" in row.index):
        nd = get_eis_int(row, "3-1.24小時內死亡人數", "死亡")
        if nd != (existing.death_count or 0):
            existing.death_count = nd
    if ("3-2.受傷人數" in row.index) or ("受傷" in row.index):
        ni = get_eis_int(row, "3-2.受傷人數", "受傷")
        if ni != (existing.injury_count or 0):
            existing.injury_count = ni
    # 2-30日內死亡人數回補：僅註記用，不動 severity 分類與24hr口徑死亡統計；
    # 欄位存在才覆寫（舊部分欄位檔無此欄，避免誤把既有值蓋成 0）
    if "3-2.2-30日內死亡人數" in row.index:
        nld = get_eis_int(row, "3-2.2-30日內死亡人數")
        if nld != (existing.late_death_count or 0):
            existing.late_death_count = nld


def backfill_road_fields(existing, row, rollup) -> None:
    """回補道路工程欄位：既有案件欄位為空、且新檔（全選條件匯出）有值時補上。

    與 backfill_official_severity 同場景：舊檔先匯入建案、全選檔後到被去重略過，
    新欄位（速限/事故型態/照明/路線/駕照…）若不回補會永遠是 NULL。
    只補空值、不覆寫既有值。
    """
    rf = extract_road_engineering_fields(row)
    for k, v in rf.items():
        if v is not None and getattr(existing, k, None) is None:
            setattr(existing, k, v)
    # 天候：主解析路徑欄位，但回補場景相同（舊檔無「4.天候」→ NULL，
    # 全選檔後到需補值）。2026-07-06 品質面板抓到此遺漏（天候率 1.2%）後補上。
    if existing.weather is None:
        w = _safe_eis_str(row, "天候") or _safe_eis_str(row, "4.天候")
        if w:
            existing.weather = w
    if rollup:
        if existing.license_status is None and rollup.get("driver_license_status"):
            existing.license_status = rollup["driver_license_status"]
        if existing.protective_gear is None and rollup.get("driver_protective_gear"):
            existing.protective_gear = rollup["driver_protective_gear"]
        if not existing.is_hit_and_run and rollup.get("any_hit_and_run"):
            existing.is_hit_and_run = True
        if existing.delivery_platform is None and rollup.get("delivery_platform"):
            existing.delivery_platform = rollup["delivery_platform"]
        # 路口衝突方向引擎（Wave 28）：順位1×順位2 行動狀態配對回補
        if existing.conflict_action_pair is None and rollup.get("conflict_action_pair"):
            existing.conflict_action_pair = rollup["conflict_action_pair"]
        # 行人涉入精確口徑（Wave 31-A）：舊檔先建案時可能沒有「26.當事者區分(類別)」
        # 子類別文字欄，新檔（全選條件匯出）帶了才回補；False→True 時四欄一併原子寫入，
        # 避免只補旗標卻漏補死傷數（與其他 Wave 28/30 欄位同一套「只補空/False」語意）。
        if not existing.involves_pedestrian and rollup.get("involves_pedestrian"):
            existing.involves_pedestrian = True
            existing.ped_death_count = rollup.get("ped_death_count", 0)
            existing.ped_late_death_count = rollup.get("ped_late_death_count", 0)
            existing.ped_injury_count = rollup.get("ped_injury_count", 0)


def _parse_eis_dt(dstr: str, tstr: str) -> Optional[datetime]:
    """將 EIS 日期字串(YYYYMMDD) + 時間字串(HHMMSS) 解析為 datetime。

    輸入為 _safe_eis_str() 已取出的字串（可能帶小數尾巴如 "20240108.0"；
    時間可能不足 6 位如 "93000"，需 zfill 補齊）。缺日期或格式錯誤回傳 None；
    時間缺值視為 00:00:00。供 Wave 30-1 到場反應/排除時長計算用。
    """
    if not dstr:
        return None
    try:
        date_str = str(int(float(dstr))).zfill(8)
        year = int(date_str[:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])

        hour, minute, second = 0, 0, 0
        if tstr:
            time_str = str(int(float(tstr))).zfill(6)
            hour = int(time_str[0:2])
            minute = int(time_str[2:4])
            second = int(time_str[4:6])

        return datetime(year, month, day, hour, minute, second)
    except (ValueError, TypeError):
        return None


def extract_road_engineering_fields(row) -> dict:
    """案件級道路工程欄位（Phase 1 擴充；全選條件匯出才有值，欄位缺時皆為 None）。

    對應 Crash model 的 speed_limit / crash_type / road_type / signal_type /
    road_lighting / route_name / route_km / side_impact_direction /
    signal_action / response_minutes / clearance_minutes / has_yield_sign
    十二欄。這些為 EIS 案件級屬性（同案各當事者列相同），取當前列即可。
    side_impact_direction / signal_action 為 Wave 28 路口衝突方向引擎新增欄位；
    response_minutes / clearance_minutes / has_yield_sign 為 Wave 30-1（事故
    處理時效／道路恢復效率）與 Wave 30-2（停讓標誌）新增欄位。
    """
    speed_limit = None
    sl = _safe_eis_str(row, "7.速限(第1當事者)")
    if sl:
        try:
            v = int(float(sl))
            if 0 < v <= 130:
                speed_limit = v
        except (ValueError, TypeError):
            pass

    route_km = None
    km = (_safe_eis_str(row, "2-2.發生-路線-公里處 (國道/省道/縣道/鄉道)")
          or _safe_eis_str(row, "2-2.發生-路線-公里處(國道/省道/縣道/鄉道)"))
    m = _safe_eis_str(row, "2-2.發生-路線-公尺處(國道/省道/縣道/鄉道)")
    if km:
        try:
            route_km = float(km) + (float(m) / 1000.0 if m else 0.0)
        except (ValueError, TypeError):
            pass

    route = _safe_eis_str(row, "2-2.發生-路線-公路(國道/省道/縣道/鄉道)")
    lighting = (_safe_eis_str(row, "5.道路照明設備(11207新增)")
                or _safe_eis_str(row, "5.道路照明設備"))

    # 事故處理時效（Wave 30-1：道路恢復效率框架）
    # 發生→到場＝response_minutes（反應時間，0-720分鐘內夾制）；
    # 到場→排除＝clearance_minutes（排除清空時長＝道路恢復效率，0-1440分鐘內夾制）。
    # 逾夾制範圍視為資料異常，回 None 而非寫入離群值。
    occ = _parse_eis_dt(_safe_eis_str(row, "發生日期"), _safe_eis_str(row, "1.發生時間"))
    arr = _parse_eis_dt(_safe_eis_str(row, "到場處理日期"), _safe_eis_str(row, "到場處理時間"))
    end = _parse_eis_dt(_safe_eis_str(row, "結束(事故排除)日期"), _safe_eis_str(row, "結束(事故排除)時間"))

    response_minutes = None
    if occ and arr:
        diff = (arr - occ).total_seconds() / 60.0
        if 0 <= diff <= 720:
            response_minutes = round(diff, 1)

    clearance_minutes = None
    if arr and end:
        diff = (end - arr).total_seconds() / 60.0
        if 0 <= diff <= 1440:
            clearance_minutes = round(diff, 1)

    return {
        "speed_limit": speed_limit,
        "crash_type": (_safe_eis_str(row, "15.事故類型及型態") or None),
        "road_type": (_safe_eis_str(row, "8.道路型態") or None),
        "signal_type": (_safe_eis_str(row, "12-1.號誌-號誌種類") or None),
        "road_lighting": lighting or None,
        "route_name": route if route and route != "無" else None,
        "route_km": route_km,
        # 路口衝突方向引擎（Wave 28）：案件級欄位，取當前列即可
        "side_impact_direction": (_safe_eis_str(row, "側撞時行車方向名稱(11207新增)")[:50] or None),
        "signal_action": (_safe_eis_str(row, "12-2.號誌-號誌動作")[:20] or None),
        # 事故處理時效／停讓標誌（Wave 30-1、30-2）
        "response_minutes": response_minutes,
        "clearance_minutes": clearance_minutes,
        "has_yield_sign": (_safe_eis_str(row, "有無停讓標誌(11207新增)")[:4] or None),
    }


def derive_eis_severity(row) -> str:
    """
    從 EIS 資料推導事故嚴重度。
    優先：事故類別欄位（A1/A2/A3）
    備援：死亡人數 > 0 → A1，受傷人數 > 0 → A2，否則 A3
    """
    # 嘗試讀取明確的事故類別欄位
    for col in ["事故類別", "交通事故類別"]:
        val = _safe_eis_str(row, col)
        if val:
            # 全形轉半形
            v = val.upper().replace("Ａ", "A").replace("１", "1").replace("２", "2").replace("３", "3")
            if v in ("A1", "A2", "A3"):
                return v
            if "死亡" in v:
                return "A1"
            if "受傷" in v:
                return "A2"

    # 從死傷人數推導
    for death_col in ["3-1.24小時內死亡人數", "死亡"]:
        val = _safe_eis_str(row, death_col)
        if val:
            try:
                if int(float(val)) > 0:
                    return "A1"
            except (ValueError, TypeError):
                pass

    for injury_col in ["3-2.受傷人數", "受傷"]:
        val = _safe_eis_str(row, injury_col)
        if val:
            try:
                if int(float(val)) > 0:
                    return "A2"
            except (ValueError, TypeError):
                pass

    return "A3"


def get_eis_int(row, primary_col: str, fallback_col: str = None) -> int:
    """從 EIS 欄位取得整數值，支援備援欄位"""
    for col in [primary_col, fallback_col]:
        if col and col in row.index and pd.notna(row.get(col)):
            try:
                return int(float(row.get(col)))
            except (ValueError, TypeError):
                pass
    return 0


def validate_taiwan_coords(lat, lon) -> bool:
    """驗證座標是否在台灣範圍內（粗略）"""
    if pd.isna(lat) or pd.isna(lon):
        return False
    try:
        lat_f, lon_f = float(lat), float(lon)
        return 21.5 <= lat_f <= 26.5 and 119.0 <= lon_f <= 122.5
    except (ValueError, TypeError):
        return False


# ============================================
# TXT 檔案讀取
# ============================================


def _read_eis_txt(file_path: str) -> pd.DataFrame:
    """
    讀取 EIS 匯出的 @ 分隔 TXT 檔案。
    自動偵測並跳過 metadata header（標題列含 '總編號' 或 'GPS'）。
    """
    # 先用 UTF-8 嘗試，失敗則用 cp950 (Big5 變體)
    for encoding in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            with open(file_path, "r", encoding=encoding) as f:
                lines = f.readlines()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        raise HTTPException(status_code=400, detail="TXT 檔案編碼無法辨識（嘗試 UTF-8/CP950/Big5）")

    # 找出標題列（含 '總編號' 或 'GPS' 的那一行）
    header_idx = None
    for i, line in enumerate(lines[:20]):
        if "總編號" in line or "GPS" in line or "案件編號" in line:
            header_idx = i
            break

    if header_idx is None:
        raise HTTPException(status_code=400, detail="TXT 檔案中找不到欄位標題列（需含 '總編號' 或 'GPS'）")

    # 解析標題
    header_line = lines[header_idx].strip()
    columns = [c.strip() for c in header_line.split("@")]

    # 去重欄位名：EIS 匯出偶爾有重複欄位（如「受傷」出現兩次），
    # 會導致 row.get(col) 回傳 Series 而非單值，後續 if value 判斷時
    # 觸發「The truth value of a Series is ambiguous」。重複者加 _2/_3 後綴，
    # 保留第一個原名（後續解析都用原名取值，確保取到單一欄）。
    seen_cols: dict[str, int] = {}
    deduped_columns = []
    for c in columns:
        if c in seen_cols:
            seen_cols[c] += 1
            deduped_columns.append(f"{c}_{seen_cols[c]}")
        else:
            seen_cols[c] = 1
            deduped_columns.append(c)
    columns = deduped_columns

    # 解析資料列
    data_rows = []
    for line in lines[header_idx + 1:]:
        line = line.strip()
        if not line:
            continue
        fields = [f.strip() for f in line.split("@")]
        # 確保欄位數一致（不足補空、多餘截斷）
        if len(fields) < len(columns):
            fields.extend([""] * (len(columns) - len(fields)))
        elif len(fields) > len(columns):
            fields = fields[:len(columns)]
        data_rows.append(fields)

    if not data_rows:
        raise HTTPException(status_code=400, detail="TXT 檔案中沒有資料列")

    df = pd.DataFrame(data_rows, columns=columns)
    # 將空字串轉為 NaN，方便後續 pd.isna 判斷
    df.replace("", pd.NA, inplace=True)
    return df


# ============================================
# API 路由
# ============================================


@router.post("/crash")
async def import_crash_file(
    file: UploadFile = File(..., description="交通事故 Excel 檔案"),
    db: Session = Depends(get_db),
):
    """
    匯入交通事故資料

    - 支援 .xlsx, .xls, .txt 格式
    - TXT 格式：@ 分隔，自動跳過前幾行 metadata header
    - 自動去重（依案件編號）
    - 自動去識別化
    """
    ALLOWED_EXTENSIONS = (".xlsx", ".xls", ".txt")

    # 驗證檔案類型
    if not file.filename.endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail="僅支援 Excel (.xlsx, .xls) 或 TXT (.txt) 檔案格式",
        )

    is_txt = file.filename.endswith(".txt")

    # 儲存暫存檔
    try:
        suffix = ".txt" if is_txt else ".xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"檔案儲存失敗: {str(e)}")

    try:
        if is_txt:
            # === TXT 格式：@ 分隔，前幾行為 metadata ===
            df = _read_eis_txt(tmp_path)
        else:
            # === Excel 格式 ===
            # 讀取 Excel - 先不指定標題列以偵測結構
            df_raw = pd.read_excel(tmp_path, header=None)

            # 自動偵測標題列：尋找包含「案件編號」或「發生時間」或「總編號」的列
            header_row = 0
            for i in range(min(10, len(df_raw))):
                row_values = [str(v).strip() for v in df_raw.iloc[i] if pd.notna(v)]
                row_text = " ".join(row_values)
                if any(kw in row_text for kw in ["案件編號", "發生時間", "事故編號", "總編號", "GPS緯度"]):
                    header_row = i
                    break

            # 重新讀取，使用正確的標題列
            df = pd.read_excel(tmp_path, header=header_row)

        # 清理欄位名稱（移除空白和換行，但保留括號以辨識 EIS 欄位）
        df.columns = [str(c).strip().replace("\n", "") for c in df.columns]

        # 自動偵測資料格式
        data_format = detect_crash_format(list(df.columns))

        # 檢查 EIS 檔是否含「所轄單位名稱」欄位（缺則事故會 fallback 成交通分隊，派出所統計失準）
        has_subunit_col = data_format == "EIS" and has_subunit_column(df)
        # 檢查是否含「事故類別」欄位（缺則 A1/A2/A3 只能靠死傷人數推導，可能失準）
        has_severity_col = data_format == "EIS" and any(
            ("事故類別" in str(c)) or ("交通事故類別" in str(c)) for c in df.columns
        )

        batch_id = f"WEB_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        stats = {"total": len(df), "new": 0, "skipped": 0, "errors": 0}
        coords_stats = {"with_gps": 0, "fallback": 0}
        error_messages = []
        seen_case_ids: set = set()

        # ==============================================================
        # Pre-pass：以 case_id 為單位 rollup 飲酒情形
        # ==============================================================
        # EIS 是 per-當事者 row，多筆共用 case_id。原 import 邏輯只保留第一 row，
        # 會丟失「行人 + 肇事駕駛飲酒」這類情境的駕駛資訊。
        #
        # 規則：
        #   - 飲酒情形代碼 ∈ {04,05,06,07,08} 視為「有飲酒」
        #   - 當事者區分子類別代碼 H 開頭視為「行人」（飲酒行人不算酒駕肇事）
        #   - is_dui_crash_party = (任一非行人當事者有飲酒)
        # 駕駛者欄位（drinking_code, party_subtype_code）的選擇優先序：
        #   1) 非行人 + 有飲酒（首選，肇事駕駛）
        #   2) 非行人 + 任意飲酒值（次選）
        #   3) 第一筆 row（行人為主案件 fallback）
        case_rollup: dict[str, dict] = {}
        if data_format == "EIS":
            DRINKING_CODES = {"04", "05", "06", "07", "08", "4", "5", "6", "7", "8"}
            # 補強信號：如果 飲酒情形代碼 漏填，但肇因 = '酒醉駕駛'(53) 或文字含關鍵字
            ALCOHOL_CAUSE_CODES = {"53"}
            ALCOHOL_KEYWORDS = ["酒醉", "酒後", "飲酒", "醉駕"]

            for _, row in df.iterrows():
                # 取案件編號
                rid = None
                for col_name in ["總編號(案件編號)", "總編號（案件編號）", "案件編號", "總編號"]:
                    if col_name in row.index and pd.notna(row.get(col_name)):
                        val = str(row.get(col_name)).strip()
                        if val:
                            rid = val
                            break
                if not rid:
                    continue

                subtype = _safe_eis_str(row, "26.當事者區分(類別)子類別代碼(車種)") or ""
                drinking = _safe_eis_str(row, "32.飲酒情形代碼") or ""
                cause_code = _safe_eis_str(row, "34.初步分析研判-個別代碼") or ""
                cause_text = _safe_eis_str(row, "34.初步分析研判子類別-主要") or ""
                # 標準化（02 vs 2）
                subtype = subtype.strip()
                drinking = drinking.strip().lstrip("0") or drinking.strip()
                cause_code = cause_code.strip().lstrip("0") or cause_code.strip()

                is_pedestrian = subtype.startswith("H")
                # 主信號：飲酒情形 4-8
                is_drinking_primary = drinking in DRINKING_CODES or drinking in {"4", "5", "6", "7", "8"}
                # 補強信號：肇因代碼 53 或文字含「酒醉/酒後/飲酒/醉駕」
                is_drinking_secondary = (
                    cause_code in ALCOHOL_CAUSE_CODES
                    or any(kw in cause_text for kw in ALCOHOL_KEYWORDS)
                )
                is_drinking = is_drinking_primary or is_drinking_secondary

                bucket = case_rollup.setdefault(rid, {
                    "has_drinking_party": False,
                    "driver_subtype_code": None,
                    "driver_drinking_code": None,
                    "driver_license_status": None,
                    "driver_protective_gear": None,
                    "any_hit_and_run": False,
                    "delivery_platform": None,
                    # 路口衝突方向引擎（Wave 28）：順位1×順位2 當事者行動狀態配對
                    "_conflict_act1": None,
                    "_conflict_act2": None,
                    "conflict_action_pair": None,
                    "_picked_priority": 0,  # 內部用：1=肇事駕駛飲酒, 2=非行人, 3=fallback
                    # 行人涉入精確口徑（Wave 31-A）
                    "involves_pedestrian": False,
                    "ped_death_count": 0,
                    "ped_late_death_count": 0,
                    "ped_injury_count": 0,
                })

                # 旗標：只要有任何非行人飲酒就標記
                if not is_pedestrian and is_drinking:
                    bucket["has_drinking_party"] = True

                # 行人涉入精確口徑（Wave 31-A）：任一當事者「26.當事者區分(類別)」
                # 子類別文字含「行人」或「輔助代步器材」（電動代步車使用者道交視同行人）。
                # ⚠️ 不可用大類別「人」判定，該大類含乘客，乘客不是行人。
                party_sub_type = _safe_eis_str(row, "26.當事者區分(類別)")
                if "行人" in party_sub_type or "輔助代步器材" in party_sub_type:
                    bucket["involves_pedestrian"] = True
                    ped_injury = _safe_eis_str(row, "22.受傷程度")
                    if ped_injury == "24小時內死亡":
                        bucket["ped_death_count"] += 1
                    elif ped_injury == "2-30日內死亡":
                        bucket["ped_late_death_count"] += 1
                    elif ped_injury == "受傷":
                        bucket["ped_injury_count"] += 1

                # 案件級聚合：任一當事者肇逃=是；外送平台取第一個有效值
                if _safe_eis_str(row, "35.肇事逃逸(是否肇逃)") == "是":
                    bucket["any_hit_and_run"] = True
                if not bucket["delivery_platform"]:
                    _dp = _safe_eis_str(row, "37.共享經濟或外送平台")
                    # 值域含「其他(非共享經濟與外送平台)」「非駕駛人」等雜訊，僅收真外送/共享
                    if _dp and ("外送" in _dp or "共享" in _dp) and "非共享" not in _dp:
                        bucket["delivery_platform"] = _dp[:50]

                # 路口衝突方向引擎（Wave 28）：順位1×順位2 當事者行動狀態配對
                # 「當事者順位」值可能有前導零（"01"），lstrip("0") 正規化比對
                _pos_raw = _safe_eis_str(row, "當事者順位").strip()
                _pos = _pos_raw.lstrip("0") or _pos_raw
                _action_status = _safe_eis_str(row, "29.當事者行動狀態類別名稱") or None
                if _pos == "1" and bucket["_conflict_act1"] is None and _action_status:
                    bucket["_conflict_act1"] = _action_status
                elif _pos == "2" and bucket["_conflict_act2"] is None and _action_status:
                    bucket["_conflict_act2"] = _action_status
                if bucket["_conflict_act1"] and bucket["_conflict_act2"]:
                    bucket["conflict_action_pair"] = (
                        f"{bucket['_conflict_act1']}×{bucket['_conflict_act2']}"[:80]
                    )

                # 駕駛代表 row 選擇（priority 越高越佳，3>2>1）
                priority = 3 if (not is_pedestrian and is_drinking) else (2 if not is_pedestrian else 1)
                if priority > bucket["_picked_priority"]:
                    bucket["_picked_priority"] = priority
                    bucket["driver_subtype_code"] = subtype[:10] if subtype else None
                    # 駕駛代碼優先取真實飲酒值；若僅靠補強信號才被標記，drinking 為空字串時不寫入
                    bucket["driver_drinking_code"] = drinking[:2] if drinking else None
                    bucket["driver_license_status"] = (_safe_eis_str(row, "30.駕照狀態") or None)
                    bucket["driver_protective_gear"] = (_safe_eis_str(row, "24.保護裝備") or None)

        for idx, row in df.iterrows():
            try:
                # ============================
                # 案件編號（兩種格式通用）
                # ============================
                case_id = None
                # EIS 優先使用 總編號(案件編號)
                id_candidates = (
                    ["總編號(案件編號)", "總編號（案件編號）", "案件編號", "總編號", "案號", "CaseID"]
                    if data_format == "EIS"
                    else ["案件編號", "案號", "事故編號", "編號", "案件序號", "序號", "CaseID", "case_id"]
                )
                for col_name in id_candidates:
                    if col_name in row.index and pd.notna(row.get(col_name)):
                        val = str(row.get(col_name)).strip()
                        if val and any(c.isdigit() for c in val):
                            case_id = val
                            break

                if not case_id:
                    non_empty_count = sum(1 for v in row if pd.notna(v) and str(v).strip())
                    if non_empty_count < 3:
                        continue  # 靜默跳過空白列
                    stats["errors"] += 1
                    error_messages.append(f"第 {idx + 2} 列：缺少案件編號")
                    continue

                # 去重檢查（in-memory + DB）
                if case_id in seen_case_ids:
                    stats["skipped"] += 1
                    continue
                existing = db.query(Crash).filter(Crash.case_id == case_id).first()
                if existing:
                    seen_case_ids.add(case_id)
                    # 回補新加入的酒駕欄位（drinking_code / party_subtype_code / is_dui_crash_party）
                    # 若舊資料尚未填寫，從 case_rollup 取得最新值補上
                    if data_format == "EIS":
                        rollup = case_rollup.get(case_id, {})
                        new_is_dui = bool(rollup.get("has_drinking_party", False))
                        new_drinking = rollup.get("driver_drinking_code")
                        new_subtype = rollup.get("driver_subtype_code")
                        # 只在尚未標記為 True 或欄位空時才更新（保守覆寫）
                        changed = False
                        if not existing.is_dui_crash_party and new_is_dui:
                            existing.is_dui_crash_party = True
                            existing.suspected_alcohol = True
                            changed = True
                        if not existing.drinking_code and new_drinking:
                            existing.drinking_code = new_drinking
                            changed = True
                        if not existing.party_subtype_code and new_subtype:
                            existing.party_subtype_code = new_subtype
                            changed = True
                        if changed:
                            stats["updated"] = stats.get("updated", 0) + 1
                        # 官方 severity / 死傷回補（較新匯出檔為準）
                        backfill_official_severity(existing, row, stats)
                        backfill_road_fields(existing, row, rollup)
                    stats["skipped"] += 1
                    continue

                # ============================
                # EIS 格式處理路徑
                # ============================
                if data_format == "EIS":
                    # --- 日期時間 ---
                    time_col = "1.發生時間" if "1.發生時間" in row.index else "發生時間"
                    occurred_dt = parse_eis_datetime(
                        row.get("發生日期"),
                        row.get(time_col),
                    )
                    if not occurred_dt:
                        # EIS 備援：嘗試民國格式
                        occurred_dt = parse_roc_datetime(row.get("發生日期"))
                    if not occurred_dt:
                        stats["errors"] += 1
                        error_messages.append(f"第 {idx + 2} 列：EIS 發生日期/時間解析失敗")
                        continue

                    # --- GPS 座標 ---
                    eis_lat = pd.to_numeric(row.get("GPS緯度"), errors="coerce")
                    eis_lon = pd.to_numeric(row.get("GPS經度"), errors="coerce")
                    if validate_taiwan_coords(eis_lat, eis_lon):
                        latitude, longitude = float(eis_lat), float(eis_lon)
                        coords_stats["with_gps"] += 1
                    else:
                        # 備援：區域中心座標
                        district_temp = extract_eis_district(row)
                        latitude, longitude = get_district_coordinates(district_temp)
                        coords_stats["fallback"] += 1

                    # --- 行政區 ---
                    district = extract_eis_district(row)

                    # --- 地點描述 ---
                    location_desc = build_eis_location(row)[:200]

                    # --- 嚴重度 ---
                    severity = derive_eis_severity(row)

                    # --- 死傷人數 ---
                    death_count = get_eis_int(row, "3-1.24小時內死亡人數", "死亡")
                    injury_count = get_eis_int(row, "3-2.受傷人數", "受傷")
                    # 2-30日內死亡人數（僅註記用，不影響 severity 分類與24hr口徑死亡統計；無 fallback 欄名，舊部分欄位檔無此欄）
                    late_death_count = get_eis_int(row, "3-2.2-30日內死亡人數")

                    # --- 分局 / 所轄單位 / 派出所 ---
                    # 轄區派出所統一由 extract_sub_unit 處理：
                    # 所轄單位名稱(部分欄位匯出) → 管轄單位名稱(全選條件匯出) → 處理單位名稱派出所(備援)
                    precinct = clean_precinct_name(row.get("處理單位名稱分局層"))
                    sub_unit = extract_sub_unit(row)

                    # --- 肇因 ---
                    cause = (
                        _safe_eis_str(row, "34.初步分析研判子類別-主要")
                        or _safe_eis_str(row, "34.初步分析研判-個別")
                        or _safe_eis_str(row, "34.初步分析研判-個別代碼")
                        or _safe_eis_str(row, "肇事主要原因")
                        or None
                    )

                    # --- 天候/光線 ---
                    weather = _safe_eis_str(row, "天候") or _safe_eis_str(row, "4.天候") or None
                    light = _safe_eis_str(row, "光線") or None

                    # --- 酒駕（新邏輯：用 32. 飲酒情形代碼 + 排除行人）---
                    # 從 case_rollup 取得本案件層級的 ground truth（pre-pass 算好）
                    rollup = case_rollup.get(case_id, {})
                    is_dui_crash_party = bool(rollup.get("has_drinking_party", False))
                    drinking_code = rollup.get("driver_drinking_code")
                    party_subtype_code = rollup.get("driver_subtype_code")
                    # suspected_alcohol 與新欄位同步維護（沿用舊查詢）
                    suspected_alcohol = is_dui_crash_party

                    # 道路工程分析欄位（Phase 1：案件級 + 代表駕駛級）
                    road_fields = extract_road_engineering_fields(row)
                    license_status = rollup.get("driver_license_status")
                    protective_gear = rollup.get("driver_protective_gear")
                    is_hit_and_run = bool(rollup.get("any_hit_and_run", False))
                    delivery_platform = rollup.get("delivery_platform")
                    conflict_action_pair = rollup.get("conflict_action_pair")
                    # 行人涉入精確口徑（Wave 31-A）
                    involves_pedestrian = bool(rollup.get("involves_pedestrian", False))
                    ped_death_count = rollup.get("ped_death_count", 0)
                    ped_late_death_count = rollup.get("ped_late_death_count", 0)
                    ped_injury_count = rollup.get("ped_injury_count", 0)

                    # 舊邏輯 fallback（若資料未含新欄位，例如歷史檔）
                    if not is_dui_crash_party and (drinking_code is None and party_subtype_code is None):
                        alcohol_val = _safe_eis_str(row, "酒測值") or _safe_eis_str(row, "飲酒情形")
                        if alcohol_val:
                            if "飲酒" in alcohol_val or "酒後" in alcohol_val:
                                suspected_alcohol = True
                                is_dui_crash_party = True
                            else:
                                try:
                                    if float(alcohol_val) > 0:
                                        suspected_alcohol = True
                                        is_dui_crash_party = True
                                except (ValueError, TypeError):
                                    pass

                # ============================
                # 分局舊格式處理路徑（LEGACY）
                # ============================
                else:
                    # --- 日期時間（民國格式） ---
                    occurred_dt = None
                    for time_col in ["發生時間", "事故時間", "發生日期時間", "日期時間", "時間", "發生日期"]:
                        if time_col in row.index and pd.notna(row.get(time_col)):
                            occurred_dt = parse_roc_datetime(row.get(time_col))
                            if occurred_dt:
                                break
                    if not occurred_dt:
                        stats["errors"] += 1
                        error_messages.append(f"第 {idx + 2} 列：發生時間格式錯誤或缺失")
                        continue

                    # --- 地址 ---
                    location_val = None
                    for loc_col in ["發生地點", "事故地點", "地點", "地址", "發生地址", "事故位置"]:
                        if loc_col in row.index and pd.notna(row.get(loc_col)):
                            location_val = row.get(loc_col)
                            break
                    district, location_desc = deidentify_address(location_val)

                    # --- 嚴重度 ---
                    severity = "A3"
                    for sev_col in ["交通事故類別", "事故類別", "類別", "嚴重程度", "事故等級"]:
                        if sev_col in row.index and pd.notna(row.get(sev_col)):
                            severity = str(row.get(sev_col)).strip().upper()
                            break
                    if severity not in ["A1", "A2", "A3"]:
                        severity = "A3"

                    # --- 座標（統一驗證 + 單次 fallback 呼叫）---
                    legacy_lat = pd.to_numeric(row.get("緯度"), errors="coerce")
                    legacy_lon = pd.to_numeric(row.get("經度"), errors="coerce")
                    if validate_taiwan_coords(legacy_lat, legacy_lon):
                        latitude, longitude = float(legacy_lat), float(legacy_lon)
                    else:
                        latitude, longitude = get_district_coordinates(district)

                    # --- LEGACY 獨有欄位預設值 ---
                    death_count = 0
                    injury_count = 0
                    late_death_count = 0  # LEGACY 無此欄，2-30日死亡註記僅 EIS 全選條件檔才有
                    precinct = None
                    sub_unit = None
                    cause = str(row.get("肇事主要原因") or row.get("肇事原因") or "").strip() or None
                    weather = str(row.get("天候") or "").strip() or None
                    light = str(row.get("光線") or "").strip() or None

                    # --- 酒駕 ---
                    suspected_alcohol = False
                    alcohol_val = row.get("酒測值") or row.get("飲酒情形")
                    if alcohol_val:
                        val_str = str(alcohol_val)
                        if "飲酒" in val_str or "酒後" in val_str:
                            suspected_alcohol = True
                        else:
                            try:
                                if float(val_str) > 0:
                                    suspected_alcohol = True
                            except (ValueError, TypeError):
                                pass

                    # LEGACY 沒有結構化代碼，只能 fallback 用 suspected_alcohol 同步新欄位
                    drinking_code = None
                    party_subtype_code = None
                    is_dui_crash_party = suspected_alcohol
                    # LEGACY 無道路工程欄位
                    road_fields = {}
                    license_status = None
                    protective_gear = None
                    is_hit_and_run = False
                    delivery_platform = None
                    conflict_action_pair = None
                    # LEGACY 無 26.當事者區分(類別) 子類別文字欄，行人精確口徑無法判定
                    involves_pedestrian = False
                    ped_death_count = 0
                    ped_late_death_count = 0
                    ped_injury_count = 0

                # ============================
                # 共用欄位（兩種格式皆走此路徑）
                # ============================

                # 年齡資訊（支援 EIS 欄位名稱）
                age_val = (
                    _safe_eis_str(row, "當事者事故發生時年齡")
                    or _safe_eis_str(row, "25.當事者事故發生時年齡")
                    or _safe_eis_str(row, "當事人年齡")
                    or _safe_eis_str(row, "年齡")
                ) or None
                birth_date_val = (
                    _safe_eis_str(row, "當事者出生日期")
                    or _safe_eis_str(row, "出生年月日")
                    or _safe_eis_str(row, "出生日期")
                ) or None

                is_elderly = False
                is_youth = False
                driver_age_group = "未知"

                if age_val:
                    driver_age_group, is_elderly, is_youth = classify_age(age_val)
                elif birth_date_val:
                    # EIS 出生日期可能是 YYYYMMDD 整數或民國格式
                    birth_dt = parse_eis_datetime(birth_date_val, 0) or parse_roc_datetime(birth_date_val)
                    if birth_dt and occurred_dt:
                        age = occurred_dt.year - birth_dt.year - (
                            (occurred_dt.month, occurred_dt.day) < (birth_dt.month, birth_dt.day)
                        )
                        driver_age_group, is_elderly, is_youth = classify_age(age)

                # 車種與慢車分類
                # EIS TXT 格式使用 26.當事者區分(大類別) + 26.當事者區分(類別)
                party_type_raw = (
                    _safe_eis_str(row, "當事人車種")
                    or _safe_eis_str(row, "車種")
                    or _safe_eis_str(row, "26.當事者區分(類別)")
                    or _safe_eis_str(row, "26.當事者區分(大類別)")
                )
                party_type = party_type_raw or None
                evehicle_type, _ = classify_evehicle(party_type)

                # 未滿14歲騎乘微電車判斷
                is_underage_14_riding = False
                if evehicle_type == "微型電動二輪車" and driver_age_group == "<18":
                    try:
                        raw_age = row.get("當事人年齡") or row.get("年齡")
                        if raw_age and int(float(raw_age)) < 14:
                            is_underage_14_riding = True
                    except (ValueError, TypeError):
                        pass

                driver_gender = (
                    _safe_eis_str(row, "17.當事者屬(性)別")
                    or _safe_eis_str(row, "當事者屬(性)別")
                    or _safe_eis_str(row, "當事者性別")
                    or _safe_eis_str(row, "當事人性別")
                    or _safe_eis_str(row, "性別")
                ) or None
                # 全選條件檔的屬(性)別含非人值（無或物(動物、堆置物)、肇事逃逸尚未查獲），
                # 僅認得男/女，其餘視為未知，避免污染性別統計
                if driver_gender:
                    if "男" in driver_gender:
                        driver_gender = "男"
                    elif "女" in driver_gender:
                        driver_gender = "女"
                    else:
                        driver_gender = None

                # ============================
                # 寫入資料庫
                # ============================
                crash = Crash(
                    case_id=case_id,
                    import_batch_id=batch_id,
                    occurred_date=occurred_dt.date(),
                    occurred_time=occurred_dt,
                    shift_id=calculate_shift(occurred_dt),
                    district=district,
                    location_desc=location_desc,
                    latitude=latitude,
                    longitude=longitude,
                    severity=severity,
                    severity_weight=get_severity_weight(severity),
                    year=occurred_dt.year,
                    month=occurred_dt.month,
                    day_of_week=occurred_dt.weekday(),
                    driver_age_group=driver_age_group,
                    is_elderly=is_elderly,
                    driver_gender=driver_gender,
                    weather=weather,
                    light=light,
                    party_type=party_type,
                    cause=cause,
                    suspected_alcohol=suspected_alcohol,
                    # 新邏輯：飲酒情形代碼 + 行人排除（EIS 才有；LEGACY 為 None）
                    drinking_code=drinking_code,
                    party_subtype_code=party_subtype_code,
                    is_dui_crash_party=is_dui_crash_party,
                    # EIS 擴充欄位
                    precinct=precinct,
                    sub_unit=sub_unit,
                    death_count=death_count,
                    injury_count=injury_count,
                    late_death_count=late_death_count,
                    # 慢車/微電車欄位
                    evehicle_type=evehicle_type,
                    is_youth=is_youth,
                    is_underage_14=is_underage_14_riding,
                    # 道路工程分析欄位（Phase 1）
                    license_status=license_status,
                    protective_gear=protective_gear,
                    is_hit_and_run=is_hit_and_run,
                    delivery_platform=delivery_platform,
                    # 路口衝突方向引擎（Wave 28）
                    conflict_action_pair=conflict_action_pair,
                    # 行人涉入精確口徑（Wave 31-A）
                    involves_pedestrian=involves_pedestrian,
                    ped_death_count=ped_death_count,
                    ped_late_death_count=ped_late_death_count,
                    ped_injury_count=ped_injury_count,
                    **road_fields,
                )

                db.add(crash)
                seen_case_ids.add(case_id)
                stats["new"] += 1

                # 每 100 筆提交一次
                if stats["new"] % 100 == 0:
                    db.commit()

            except Exception as e:
                db.rollback()
                stats["errors"] += 1
                if len(error_messages) < 10:
                    error_messages.append(f"第 {idx + 2} 列：{str(e)}")

        db.commit()

        # 事故當事者層落地（Wave 32）：以 case 為單位 delete-then-insert，
        # 再由當事者層重算 is_elderly / is_youth 與高齡人數欄位。
        if data_format == "EIS":
            _parties = collect_crash_parties(df)
            if _parties:
                persist_crash_parties(db, _parties)
                db.commit()
                recompute_party_rollups(db, list(_parties.keys()))

        # 取得統計
        total_crashes = db.query(Crash).count()
        severity_stats = {
            "A1": db.query(Crash).filter(Crash.severity == "A1").count(),
            "A2": db.query(Crash).filter(Crash.severity == "A2").count(),
            "A3": db.query(Crash).filter(Crash.severity == "A3").count(),
        }

        # 缺「所轄單位名稱」欄位警示（事故會 fallback 成交通分隊，派出所統計失準）
        subunit_warning = None
        if data_format == "EIS" and not has_subunit_col:
            subunit_warning = (
                "⚠️ 此檔缺「所轄單位名稱」欄位，事故將歸入處理單位（多為交通分隊），"
                "派出所層級統計會失準。建議回 EIS 重新匯出並勾選「所轄單位名稱」欄位後重匯入。"
            )
        # 缺「事故類別」欄位警示（A1/A2/A3 只能靠死傷人數推導，可能失準）
        severity_warning = None
        if data_format == "EIS" and not has_severity_col:
            severity_warning = (
                "⚠️ 此檔缺「事故類別」欄位，A1/A2/A3 嚴重度改用死傷人數推導，"
                "若受傷人數欄位未填完整會誤判（A2↔A3）。建議匯出時勾選「事故類別」欄位。"
            )

        # 匯入後自動資料健檢（防污染防線）：失敗不影響匯入結果本身
        try:
            health_warnings = run_batch_health_checks(db, batch_id)
        except Exception:
            health_warnings = ["健檢執行失敗（不影響匯入結果）"]

        return {
            "success": True,
            "message": (
                f"匯入完成（{data_format} 格式）："
                f"新增 {stats['new']} 筆，略過 {stats['skipped']} 筆（重複），"
                f"錯誤 {stats['errors']} 筆"
                + (f"｜{subunit_warning}" if subunit_warning else "")
                + (f"｜{severity_warning}" if severity_warning else "")
            ),
            "batch_id": batch_id,
            "data_format": data_format,
            "stats": stats,
            "subunit_warning": subunit_warning,
            "severity_warning": severity_warning,
            "coordinates": coords_stats if data_format == "EIS" else None,
            "errors": error_messages[:10] if error_messages else [],
            "health_warnings": health_warnings,
            "database": {
                "total_crashes": total_crashes,
                "severity": severity_stats,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"匯入失敗: {str(e)}")

    finally:
        # 清理暫存檔
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/crash/batch")
async def import_crash_batch(db: Session = Depends(get_db)):
    """
    批次匯入事故調查表資料夾中所有 TXT 檔案。

    自動讀取專案根目錄下的「事故調查表資料」資料夾，
    依序匯入所有 .txt 檔案。
    """
    import glob as glob_mod
    import traceback

    # 資料夾路徑：專案根目錄（backend 的上一層）下的「事故調查表資料」
    # __file__ = backend/app/api/imports.py → 往上 3 層 = backend/ → 再上 1 層 = 專案根目錄
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    project_root = os.path.dirname(backend_dir)
    data_dir = os.path.join(project_root, "事故調查表資料")

    if not os.path.isdir(data_dir):
        raise HTTPException(
            status_code=404,
            detail=f"找不到事故調查表資料夾: {data_dir}",
        )

    txt_files = sorted(glob_mod.glob(os.path.join(data_dir, "*.txt")))
    if not txt_files:
        raise HTTPException(status_code=404, detail="資料夾中沒有 .txt 檔案")

    try:
        return _do_batch_import(txt_files, db)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"批次匯入失敗: {str(e)}")


def _get_imported_filenames(db, model, pattern_prefix="BATCH_") -> set:
    """查詢已匯入過的檔案名稱（從 import_batch_id 解析）"""
    batch_ids = (
        db.query(model.import_batch_id)
        .filter(model.import_batch_id.like(f"{pattern_prefix}%"))
        .distinct()
        .all()
    )
    names = set()
    for (bid,) in batch_ids:
        # batch_id 格式: BATCH_YYYYMMDD_HHMMSS_filename.ext
        parts = bid.split("_", 3)
        if len(parts) >= 4:
            names.add(parts[3])
    return names


def _do_batch_import(txt_files: list, db):
    """批次匯入的實際邏輯（同步函數，避免 async 問題）"""
    total_stats = {"files": 0, "total": 0, "new": 0, "skipped": 0, "errors": 0, "files_skipped": 0, "updated": 0}
    coords_total = {"with_gps": 0, "fallback": 0}
    all_errors = []
    skipped_files = []
    files_missing_subunit = []  # 缺「所轄單位名稱」欄位的檔（事故會 fallback 成交通分隊）
    files_missing_severity = []  # 缺「事故類別」欄位的檔（A1/A2/A3 靠死傷推導）
    seen_case_ids: set = set()
    batch_ids_this_run = []  # 本次匯入產生的所有 batch_id（各檔各自時間戳，健檢需收集全部）

    # 取得已匯入過的檔案名稱
    imported_files = _get_imported_filenames(db, Crash)

    # 檢查是否有舊版 sub_unit（= 交通分隊，代表尚未套用「所轄單位名稱」欄位）
    # 若有，允許已匯入的檔案重新進入流程以回補 sub_unit 欄位
    needs_backfill_subunit = db.query(func.count(Crash.id)).filter(
        Crash.sub_unit.like('%交通分隊%')
    ).scalar() > 0
    # 路口衝突方向引擎（Wave 28）回補哨兵：signal_action 全史 87% 案件應有值，
    # 若全庫皆為 NULL 代表尚未跑過回補，允許已匯入檔案重新進入流程補值；
    # 回補後 signal_action 必非零，冪等不再重跑。
    conflict_backfill_needed = (
        db.query(func.count(Crash.id)).scalar() > 0
        and db.query(func.count(Crash.id)).filter(Crash.signal_action.isnot(None)).scalar() == 0
    )
    # 事故處理時效／道路恢復效率（Wave 30-1）回補哨兵：clearance_minutes 全庫皆為
    # NULL 代表尚未跑過回補，允許已匯入檔案重新進入流程補值；
    # 回補後 clearance_minutes 必非零，冪等不再重跑。
    clearance_backfill_needed = (
        db.query(func.count(Crash.id)).scalar() > 0
        and db.query(func.count(Crash.id)).filter(Crash.clearance_minutes.isnot(None)).scalar() == 0
    )
    # 行人涉入精確口徑（Wave 31-A）回補哨兵：全庫皆無 involves_pedestrian=True 但已有資料，
    # 代表尚未跑過回補，允許已匯入檔案重新進入流程補值；回補後必有部分案件為 True，冪等不再重跑。
    pedestrian_backfill_needed = (
        db.query(func.count(Crash.id)).scalar() > 0
        and db.query(func.count(Crash.id)).filter(Crash.involves_pedestrian == True).scalar() == 0
    )
    # 事故當事者層（Wave 32）回補哨兵：core_crash_party 全空但已有事故資料，
    # 代表尚未落地當事者層，允許已匯入檔案重新進入流程補值；回補後非零，冪等不再重跑。
    party_backfill_needed = (
        db.query(func.count(Crash.id)).scalar() > 0
        and db.query(func.count(CrashParty.id)).scalar() == 0
    )
    needs_backfill = (
        needs_backfill_subunit or conflict_backfill_needed or clearance_backfill_needed
        or pedestrian_backfill_needed or party_backfill_needed
    )

    for txt_path in txt_files:
        fname = os.path.basename(txt_path)

        # 跳過已匯入的檔案（除非需要回補轄區派出所）
        if fname in imported_files and not needs_backfill:
            total_stats["files_skipped"] += 1
            skipped_files.append(fname)
            continue

        try:
            df = _read_eis_txt(txt_path)
            df.columns = [str(c).strip().replace("\n", "") for c in df.columns]
            data_format = detect_crash_format(list(df.columns))

            batch_id = f"BATCH_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{fname}"
            batch_ids_this_run.append(batch_id)
            stats = {"total": len(df), "new": 0, "skipped": 0, "errors": 0, "updated": 0}
            coords_stats = {"with_gps": 0, "fallback": 0}

            # 缺「所轄單位名稱」欄位偵測
            if data_format == "EIS" and not has_subunit_column(df):
                files_missing_subunit.append(fname)
            # 缺「事故類別」欄位偵測
            if data_format == "EIS" and not any(
                ("事故類別" in str(c)) or ("交通事故類別" in str(c)) for c in df.columns
            ):
                files_missing_severity.append(fname)

            # Pre-pass：以 case_id 為單位 rollup 飲酒情形（同 web import 邏輯）
            case_rollup: dict[str, dict] = {}
            if data_format == "EIS":
                _DRINKING_CODES = {"04", "05", "06", "07", "08", "4", "5", "6", "7", "8"}
                _ALCOHOL_CAUSE_CODES = {"53"}
                _ALCOHOL_KEYWORDS = ["酒醉", "酒後", "飲酒", "醉駕"]
                for _, _row in df.iterrows():
                    _rid = None
                    for _c in ["總編號(案件編號)", "總編號（案件編號）", "案件編號", "總編號"]:
                        if _c in _row.index and pd.notna(_row.get(_c)):
                            _v = str(_row.get(_c)).strip()
                            if _v:
                                _rid = _v
                                break
                    if not _rid:
                        continue
                    _subtype = (_safe_eis_str(_row, "26.當事者區分(類別)子類別代碼(車種)") or "").strip()
                    _drinking = (_safe_eis_str(_row, "32.飲酒情形代碼") or "").strip()
                    _cause_code = (_safe_eis_str(_row, "34.初步分析研判-個別代碼") or "").strip().lstrip("0")
                    _cause_text = _safe_eis_str(_row, "34.初步分析研判子類別-主要") or ""
                    _is_pedestrian = _subtype.startswith("H")
                    _is_drinking_primary = _drinking in _DRINKING_CODES
                    _is_drinking_secondary = (
                        _cause_code in _ALCOHOL_CAUSE_CODES
                        or any(kw in _cause_text for kw in _ALCOHOL_KEYWORDS)
                    )
                    _is_drinking = _is_drinking_primary or _is_drinking_secondary
                    _bucket = case_rollup.setdefault(_rid, {
                        "has_drinking_party": False,
                        "driver_subtype_code": None,
                        "driver_drinking_code": None,
                        "driver_license_status": None,
                        "driver_protective_gear": None,
                        "any_hit_and_run": False,
                        "delivery_platform": None,
                        # 路口衝突方向引擎（Wave 28）：順位1×順位2 當事者行動狀態配對
                        "_conflict_act1": None,
                        "_conflict_act2": None,
                        "conflict_action_pair": None,
                        "_picked_priority": 0,
                        # 行人涉入精確口徑（Wave 31-A）
                        "involves_pedestrian": False,
                        "ped_death_count": 0,
                        "ped_late_death_count": 0,
                        "ped_injury_count": 0,
                    })
                    if not _is_pedestrian and _is_drinking:
                        _bucket["has_drinking_party"] = True
                    # 行人涉入精確口徑（Wave 31-A）：任一當事者「26.當事者區分(類別)」
                    # 子類別文字含「行人」或「輔助代步器材」（電動代步車使用者道交視同行人）。
                    # ⚠️ 不可用大類別「人」判定，該大類含乘客，乘客不是行人。
                    _party_sub_type = _safe_eis_str(_row, "26.當事者區分(類別)")
                    if "行人" in _party_sub_type or "輔助代步器材" in _party_sub_type:
                        _bucket["involves_pedestrian"] = True
                        _ped_injury = _safe_eis_str(_row, "22.受傷程度")
                        if _ped_injury == "24小時內死亡":
                            _bucket["ped_death_count"] += 1
                        elif _ped_injury == "2-30日內死亡":
                            _bucket["ped_late_death_count"] += 1
                        elif _ped_injury == "受傷":
                            _bucket["ped_injury_count"] += 1
                    # 案件級聚合：任一當事者肇逃=是；外送平台取第一個有效值
                    if _safe_eis_str(_row, "35.肇事逃逸(是否肇逃)") == "是":
                        _bucket["any_hit_and_run"] = True
                    if not _bucket["delivery_platform"]:
                        _dp = _safe_eis_str(_row, "37.共享經濟或外送平台")
                        # 僅收真外送/共享（排除「其他(非共享經濟與外送平台)」「非駕駛人」雜訊）
                        if _dp and ("外送" in _dp or "共享" in _dp) and "非共享" not in _dp:
                            _bucket["delivery_platform"] = _dp[:50]
                    # 路口衝突方向引擎（Wave 28）：順位1×順位2 當事者行動狀態配對
                    _pos_raw = _safe_eis_str(_row, "當事者順位").strip()
                    _pos = _pos_raw.lstrip("0") or _pos_raw
                    _action_status = _safe_eis_str(_row, "29.當事者行動狀態類別名稱") or None
                    if _pos == "1" and _bucket["_conflict_act1"] is None and _action_status:
                        _bucket["_conflict_act1"] = _action_status
                    elif _pos == "2" and _bucket["_conflict_act2"] is None and _action_status:
                        _bucket["_conflict_act2"] = _action_status
                    if _bucket["_conflict_act1"] and _bucket["_conflict_act2"]:
                        _bucket["conflict_action_pair"] = (
                            f"{_bucket['_conflict_act1']}×{_bucket['_conflict_act2']}"[:80]
                        )
                    _priority = 3 if (not _is_pedestrian and _is_drinking) else (2 if not _is_pedestrian else 1)
                    if _priority > _bucket["_picked_priority"]:
                        _bucket["_picked_priority"] = _priority
                        _bucket["driver_subtype_code"] = _subtype[:10] if _subtype else None
                        _bucket["driver_drinking_code"] = _drinking[:2] if _drinking else None
                        _bucket["driver_license_status"] = (_safe_eis_str(_row, "30.駕照狀態") or None)
                        _bucket["driver_protective_gear"] = (_safe_eis_str(_row, "24.保護裝備") or None)

            for idx, row in df.iterrows():
                try:
                    # 案件編號
                    case_id = None
                    id_candidates = (
                        ["總編號(案件編號)", "總編號（案件編號）", "案件編號", "總編號"]
                        if data_format == "EIS"
                        else ["案件編號", "案號", "事故編號"]
                    )
                    for col_name in id_candidates:
                        if col_name in row.index and pd.notna(row.get(col_name)):
                            val = str(row.get(col_name)).strip()
                            if val and any(c.isdigit() for c in val):
                                case_id = val
                                break

                    if not case_id:
                        non_empty_count = sum(1 for v in row if pd.notna(v) and str(v).strip())
                        if non_empty_count < 3:
                            continue
                        stats["errors"] += 1
                        continue

                    # 去重：先查 in-memory set（同批次多當事人），再查 DB（先前批次）
                    if case_id in seen_case_ids:
                        # 同批次重複（同案多當事者列 / 跨檔同案）：
                        # 較新匯出檔帶官方事故類別或工程欄位時，回補先寫入的案件
                        if data_format == "EIS":
                            dup = db.query(Crash).filter(Crash.case_id == case_id).first()
                            if dup is not None:
                                backfill_official_severity(dup, row, stats)
                                backfill_road_fields(dup, row, case_rollup.get(case_id, {}))
                        stats["skipped"] += 1
                        continue
                    existing = db.query(Crash).filter(Crash.case_id == case_id).first()
                    if existing:
                        seen_case_ids.add(case_id)
                        # 回補轄區派出所：若既有 sub_unit 含「交通分隊」且新檔帶了所轄單位，更新之
                        if needs_backfill and existing.sub_unit and "交通分隊" in existing.sub_unit:
                            # 僅用真正的轄區欄位回補（不含處理單位備援，避免用交通分隊覆寫）
                            new_sub_val = (
                                _safe_eis_str(row, "所轄單位名稱")
                                or _safe_eis_str(row, "管轄單位名稱")
                            )
                            if new_sub_val:
                                new_sub = clean_precinct_name(new_sub_val)
                                if new_sub and "分局" in new_sub:
                                    suffix = new_sub.split("分局", 1)[1].strip()
                                    if suffix:
                                        new_sub = suffix
                                if new_sub and new_sub != existing.sub_unit:
                                    existing.sub_unit = new_sub[:100]
                                    stats["updated"] += 1
                        # 回補新加入的酒駕欄位
                        if data_format == "EIS":
                            rollup = case_rollup.get(case_id, {})
                            new_is_dui = bool(rollup.get("has_drinking_party", False))
                            new_drinking = rollup.get("driver_drinking_code")
                            new_subtype = rollup.get("driver_subtype_code")
                            if not existing.is_dui_crash_party and new_is_dui:
                                existing.is_dui_crash_party = True
                                existing.suspected_alcohol = True
                                stats["updated"] += 1
                            if not existing.drinking_code and new_drinking:
                                existing.drinking_code = new_drinking
                            if not existing.party_subtype_code and new_subtype:
                                existing.party_subtype_code = new_subtype
                            # 官方 severity / 死傷回補（較新匯出檔為準）
                            backfill_official_severity(existing, row, stats)
                            backfill_road_fields(existing, row, rollup)
                        stats["skipped"] += 1
                        continue

                    # EIS 處理
                    if data_format == "EIS":
                        time_col = "1.發生時間" if "1.發生時間" in row.index else "發生時間"
                        occurred_dt = parse_eis_datetime(row.get("發生日期"), row.get(time_col))
                        if not occurred_dt:
                            occurred_dt = parse_roc_datetime(row.get("發生日期"))
                        if not occurred_dt:
                            stats["errors"] += 1
                            continue

                        eis_lat = pd.to_numeric(row.get("GPS緯度"), errors="coerce")
                        eis_lon = pd.to_numeric(row.get("GPS經度"), errors="coerce")
                        if validate_taiwan_coords(eis_lat, eis_lon):
                            latitude, longitude = float(eis_lat), float(eis_lon)
                            coords_stats["with_gps"] += 1
                        else:
                            district_temp = extract_eis_district(row)
                            latitude, longitude = get_district_coordinates(district_temp)
                            coords_stats["fallback"] += 1

                        district = extract_eis_district(row)
                        location_desc = build_eis_location(row)[:200]
                        severity = derive_eis_severity(row)
                        death_count = get_eis_int(row, "3-1.24小時內死亡人數", "死亡")
                        injury_count = get_eis_int(row, "3-2.受傷人數", "受傷")
                        # 2-30日內死亡人數（僅註記用，不影響 severity 分類與24hr口徑死亡統計；無 fallback 欄名）
                        late_death_count = get_eis_int(row, "3-2.2-30日內死亡人數")
                        precinct = clean_precinct_name(row.get("處理單位名稱分局層"))
                        # 轄區派出所統一由 extract_sub_unit 處理（含全選條件「管轄單位名稱」欄名）
                        sub_unit = extract_sub_unit(row)
                        cause = (
                            _safe_eis_str(row, "34.初步分析研判子類別-主要")
                            or _safe_eis_str(row, "34.初步分析研判-個別")
                            or _safe_eis_str(row, "34.初步分析研判-個別代碼")
                            or None
                        )
                        weather = _safe_eis_str(row, "天候") or _safe_eis_str(row, "4.天候") or None
                        light = _safe_eis_str(row, "光線") or None
                        # 新邏輯：飲酒情形代碼（從 case_rollup 取）
                        rollup = case_rollup.get(case_id, {})
                        is_dui_crash_party = bool(rollup.get("has_drinking_party", False))
                        drinking_code = rollup.get("driver_drinking_code")
                        party_subtype_code = rollup.get("driver_subtype_code")
                        suspected_alcohol = is_dui_crash_party
                        # 道路工程分析欄位（Phase 1：案件級 + 代表駕駛級）
                        road_fields = extract_road_engineering_fields(row)
                        license_status = rollup.get("driver_license_status")
                        protective_gear = rollup.get("driver_protective_gear")
                        is_hit_and_run = bool(rollup.get("any_hit_and_run", False))
                        delivery_platform = rollup.get("delivery_platform")
                        conflict_action_pair = rollup.get("conflict_action_pair")
                        # 行人涉入精確口徑（Wave 31-A）
                        involves_pedestrian = bool(rollup.get("involves_pedestrian", False))
                        ped_death_count = rollup.get("ped_death_count", 0)
                        ped_late_death_count = rollup.get("ped_late_death_count", 0)
                        ped_injury_count = rollup.get("ped_injury_count", 0)

                        # 舊邏輯 fallback
                        if not is_dui_crash_party and (drinking_code is None and party_subtype_code is None):
                            alcohol_val = _safe_eis_str(row, "酒測值") or _safe_eis_str(row, "飲酒情形")
                            if alcohol_val:
                                if "飲酒" in alcohol_val or "酒後" in alcohol_val:
                                    suspected_alcohol = True
                                    is_dui_crash_party = True
                                else:
                                    try:
                                        if float(alcohol_val) > 0:
                                            suspected_alcohol = True
                                            is_dui_crash_party = True
                                    except (ValueError, TypeError):
                                        pass
                    else:
                        # LEGACY 路徑（TXT 通常不會走到這裡）
                        stats["errors"] += 1
                        continue

                    # 共用欄位 — 年齡（支援 EIS 欄位名稱）
                    age_val = (
                        _safe_eis_str(row, "當事者事故發生時年齡")
                        or _safe_eis_str(row, "25.當事者事故發生時年齡")
                        or _safe_eis_str(row, "當事人年齡")
                        or _safe_eis_str(row, "年齡")
                    ) or None
                    birth_date_val = (
                        _safe_eis_str(row, "當事者出生日期")
                        or _safe_eis_str(row, "出生年月日")
                        or _safe_eis_str(row, "出生日期")
                    ) or None

                    is_elderly = False
                    is_youth = False
                    driver_age_group = "未知"
                    if age_val:
                        driver_age_group, is_elderly, is_youth = classify_age(age_val)
                    elif birth_date_val:
                        birth_dt = parse_eis_datetime(birth_date_val, 0) or parse_roc_datetime(birth_date_val)
                        if birth_dt and occurred_dt:
                            age = occurred_dt.year - birth_dt.year - (
                                (occurred_dt.month, occurred_dt.day) < (birth_dt.month, birth_dt.day)
                            )
                            driver_age_group, is_elderly, is_youth = classify_age(age)

                    party_type_raw = (
                        _safe_eis_str(row, "當事人車種")
                        or _safe_eis_str(row, "車種")
                        or _safe_eis_str(row, "26.當事者區分(類別)")
                        or _safe_eis_str(row, "26.當事者區分(大類別)")
                    )
                    party_type = party_type_raw or None
                    evehicle_type, _ = classify_evehicle(party_type)

                    is_underage_14_riding = False
                    if evehicle_type == "微型電動二輪車" and driver_age_group == "<18":
                        try:
                            raw_age = age_val or _safe_eis_str(row, "當事人年齡") or _safe_eis_str(row, "年齡")
                            if raw_age and int(float(raw_age)) < 14:
                                is_underage_14_riding = True
                        except (ValueError, TypeError):
                            pass

                    driver_gender = (
                        _safe_eis_str(row, "17.當事者屬(性)別")
                        or _safe_eis_str(row, "當事者屬(性)別")
                        or _safe_eis_str(row, "當事者性別")
                        or _safe_eis_str(row, "當事人性別")
                        or _safe_eis_str(row, "性別")
                    ) or None
                    # 全選條件檔的屬(性)別含非人值（無或物(動物、堆置物)、肇事逃逸尚未查獲），
                    # 僅認得男/女，其餘視為未知，避免污染性別統計
                    if driver_gender:
                        if "男" in driver_gender:
                            driver_gender = "男"
                        elif "女" in driver_gender:
                            driver_gender = "女"
                        else:
                            driver_gender = None

                    crash = Crash(
                        case_id=case_id,
                        import_batch_id=batch_id,
                        occurred_date=occurred_dt.date(),
                        occurred_time=occurred_dt,
                        shift_id=calculate_shift(occurred_dt),
                        district=district,
                        location_desc=location_desc,
                        latitude=latitude,
                        longitude=longitude,
                        severity=severity,
                        severity_weight=get_severity_weight(severity),
                        year=occurred_dt.year,
                        month=occurred_dt.month,
                        day_of_week=occurred_dt.weekday(),
                        driver_age_group=driver_age_group,
                        is_elderly=is_elderly,
                        driver_gender=driver_gender,
                        weather=weather,
                        light=light,
                        party_type=party_type,
                        cause=cause,
                        suspected_alcohol=suspected_alcohol,
                        drinking_code=drinking_code,
                        party_subtype_code=party_subtype_code,
                        is_dui_crash_party=is_dui_crash_party,
                        precinct=precinct,
                        sub_unit=sub_unit,
                        death_count=death_count,
                        injury_count=injury_count,
                        late_death_count=late_death_count,
                        evehicle_type=evehicle_type,
                        is_youth=is_youth,
                        is_underage_14=is_underage_14_riding,
                        # 道路工程分析欄位（Phase 1）
                        license_status=license_status,
                        protective_gear=protective_gear,
                        is_hit_and_run=is_hit_and_run,
                        delivery_platform=delivery_platform,
                        # 路口衝突方向引擎（Wave 28）
                        conflict_action_pair=conflict_action_pair,
                        # 行人涉入精確口徑（Wave 31-A）
                        involves_pedestrian=involves_pedestrian,
                        ped_death_count=ped_death_count,
                        ped_late_death_count=ped_late_death_count,
                        ped_injury_count=ped_injury_count,
                        **road_fields,
                    )
                    db.add(crash)
                    seen_case_ids.add(case_id)
                    stats["new"] += 1

                    if stats["new"] % 100 == 0:
                        db.commit()

                except Exception as e:
                    db.rollback()
                    stats["errors"] += 1
                    if len(all_errors) < 20:
                        all_errors.append(f"[{fname}] 第 {idx + 2} 列: {str(e)}")

            db.commit()

            # 事故當事者層落地（Wave 32）：以 case 為單位 delete-then-insert，
            # 再由當事者層重算 is_elderly / is_youth 與高齡人數欄位。
            if data_format == "EIS":
                _parties = collect_crash_parties(df)
                if _parties:
                    persist_crash_parties(db, _parties)
                    db.commit()
                    recompute_party_rollups(db, list(_parties.keys()))

            total_stats["files"] += 1
            total_stats["total"] += stats["total"]
            total_stats["new"] += stats["new"]
            total_stats["skipped"] += stats["skipped"]
            total_stats["errors"] += stats["errors"]
            total_stats["updated"] = total_stats.get("updated", 0) + stats.get("updated", 0)
            coords_total["with_gps"] += coords_stats["with_gps"]
            coords_total["fallback"] += coords_stats["fallback"]

        except Exception as e:
            all_errors.append(f"[{fname}] 檔案讀取失敗: {str(e)}")

    # 統計
    total_crashes = db.query(Crash).count()
    severity_stats = {
        "A1": db.query(Crash).filter(Crash.severity == "A1").count(),
        "A2": db.query(Crash).filter(Crash.severity == "A2").count(),
        "A3": db.query(Crash).filter(Crash.severity == "A3").count(),
    }

    msg_parts = []
    if total_stats["files"] > 0:
        msg_parts.append(f"匯入 {total_stats['files']} 個檔案，新增 {total_stats['new']} 筆")
    if total_stats.get("updated", 0) > 0:
        msg_parts.append(f"回補轄區派出所 {total_stats['updated']} 筆")
    if total_stats["files_skipped"] > 0:
        msg_parts.append(f"跳過 {total_stats['files_skipped']} 個已匯入檔案")
    if total_stats["skipped"] > 0:
        msg_parts.append(f"略過 {total_stats['skipped']} 筆重複")
    if total_stats["errors"] > 0:
        msg_parts.append(f"錯誤 {total_stats['errors']} 筆")
    if not msg_parts:
        msg_parts.append("所有檔案皆已匯入，無新資料")

    subunit_warning = None
    if files_missing_subunit:
        subunit_warning = (
            f"⚠️ 以下 {len(files_missing_subunit)} 個檔缺「所轄單位名稱」欄位，"
            f"事故將歸入交通分隊、派出所統計失準，建議重新匯出勾選該欄位："
            + "、".join(files_missing_subunit)
        )
    severity_warning = None
    if files_missing_severity:
        severity_warning = (
            f"⚠️ 以下 {len(files_missing_severity)} 個檔缺「事故類別」欄位，"
            f"A1/A2/A3 改用死傷人數推導，受傷欄未填完整會誤判，建議匯出時勾選「事故類別」："
            + "、".join(files_missing_severity)
        )

    # 匯入後自動資料健檢（防污染防線）：對本次匯入產生的全部 batch_id 一起檢查
    try:
        health_warnings = run_batch_health_checks(db, batch_ids_this_run)
    except Exception:
        health_warnings = ["健檢執行失敗（不影響匯入結果）"]

    return {
        "success": True,
        "message": "批次匯入完成：" + "，".join(msg_parts)
                   + (f"｜{subunit_warning}" if subunit_warning else "")
                   + (f"｜{severity_warning}" if severity_warning else ""),
        "data_format": "EIS",
        "stats": total_stats,
        "subunit_warning": subunit_warning,
        "severity_warning": severity_warning,
        "coordinates": coords_total,
        "skipped_files": skipped_files,
        "errors": all_errors[:20] if all_errors else [],
        "health_warnings": health_warnings,
        "database": {
            "total_crashes": total_crashes,
            "severity": severity_stats,
        },
    }


def _import_ticket_df(df: pd.DataFrame, batch_id: str, db, error_messages: list = None):
    """匯入舉發案件 DataFrame 的共用邏輯（單檔/批次皆用此函數）"""
    if error_messages is None:
        error_messages = []
    stats = {"total": len(df), "new": 0, "skipped": 0, "errors": 0}
    topic_counts = {"dui": 0, "red_light": 0, "dangerous": 0}
    seen_ids: set = set()

    for idx, row in df.iterrows():
        try:
            ticket_number = str(row.get("舉發單號", "")).strip()
            if not ticket_number or ticket_number == "nan":
                stats["errors"] += 1
                if len(error_messages) < 10:
                    error_messages.append(f"第 {idx + 2} 列：缺少舉發單號")
                continue

            # 去重（in-memory + DB）
            if ticket_number in seen_ids:
                stats["skipped"] += 1
                continue
            existing = (
                db.query(Ticket)
                .filter(Ticket.ticket_number == ticket_number)
                .first()
            )
            if existing:
                # 回補缺少的舉發類型/子類型欄位
                updated = False
                if not existing.enforcement_type:
                    raw_et = row.get("舉發類型")
                    if raw_et is not None and not pd.isna(raw_et):
                        et = str(raw_et).strip()
                        if et:
                            existing.enforcement_type = et[:20]
                            updated = True
                if not existing.enforcement_subtype:
                    raw_est = row.get("舉發子類型")
                    if raw_est is not None and not pd.isna(raw_est):
                        est = str(raw_est).strip()
                        if est:
                            existing.enforcement_subtype = est[:50]
                            updated = True
                if updated:
                    stats["updated"] = stats.get("updated", 0) + 1
                seen_ids.add(ticket_number)
                stats["skipped"] += 1
                continue

            # 解析時間
            time_str = row.get("違規時間(出)") or row.get("建檔時間")
            violation_dt = parse_roc_datetime(time_str)
            if not violation_dt:
                stats["errors"] += 1
                if len(error_messages) < 10:
                    error_messages.append(f"第 {idx + 2} 列：違規時間格式錯誤")
                continue

            # 地址
            location1 = (
                str(row.get("違規地點一", ""))
                if not pd.isna(row.get("違規地點一"))
                else ""
            )
            location2 = (
                str(row.get("違規地點備註", ""))
                if not pd.isna(row.get("違規地點備註"))
                else ""
            )
            full_location = f"{location1} {location2}".strip()
            district, location_desc = deidentify_address(full_location)

            # 違規條款
            violation_full = (
                str(row.get("違規條款1", ""))
                if not pd.isna(row.get("違規條款1"))
                else ""
            )
            parts = violation_full.split(" ", 1)
            violation_code = parts[0] if parts else ""
            violation_name = parts[1] if len(parts) > 1 else ""

            # 主題分類
            topics = classify_violation_topic(violation_code, violation_name)
            if topics["dui"]:
                topic_counts["dui"] += 1
            if topics["red_light"]:
                topic_counts["red_light"] += 1
            if topics["dangerous"]:
                topic_counts["dangerous"] += 1

            # 年齡處理
            age_group, is_elderly, is_youth = classify_age(row.get("違規人年齡"))
            driver_age = None
            is_underage_14 = False
            try:
                raw_age = row.get("違規人年齡")
                if raw_age and not pd.isna(raw_age):
                    driver_age = int(float(raw_age))
                    if driver_age < 14:
                        is_underage_14 = True
            except (ValueError, TypeError):
                pass

            driver_gender = str(row.get("違規人性別") or row.get("性別") or "").strip() or None

            # 車種與慢車分類
            vehicle_type = str(row.get("車種") or "").strip() or None
            evehicle_type, is_evehicle = classify_evehicle(vehicle_type)

            # 違規態樣分類（針對慢車）
            evehicle_violation = None
            violation_text = violation_name.lower() if violation_name else ""
            if is_evehicle:
                if "未領用牌照" in violation_text or "未掛牌" in violation_text or "未懸掛" in violation_text:
                    evehicle_violation = "未掛牌"
                elif "未戴安全帽" in violation_text or "安全帽" in violation_text:
                    evehicle_violation = "未戴安全帽"
                elif "附載" in violation_text or "雙載" in violation_text or "載人" in violation_text:
                    evehicle_violation = "雙載"
                elif "改裝" in violation_text or "拆除" in violation_text:
                    evehicle_violation = "改裝"
                elif "無照" in violation_text or "未領駕照" in violation_text:
                    evehicle_violation = "無照駕駛"
                elif is_underage_14 and evehicle_type == "微型電動二輪車":
                    evehicle_violation = "未滿14歲騎乘"

            # 舉發類型
            enforcement_type = str(row.get("舉發類型", "")).strip() if not pd.isna(row.get("舉發類型")) else None
            enforcement_subtype = str(row.get("舉發子類型", "")).strip() if not pd.isna(row.get("舉發子類型")) else None

            # 舉發單位（正規化為短名，剝除分局前綴，與 core_crash.sub_unit 口徑一致，
            # 避免「各單位績效明細」因同一派出所字串不同而被拆成兩列）
            unit_code_norm = (
                normalize_unit_name(str(row.get("舉發單位", "")))
                if not pd.isna(row.get("舉發單位"))
                else None
            )

            ticket = Ticket(
                ticket_number=ticket_number,
                import_batch_id=batch_id,
                violation_date=violation_dt.date(),
                violation_time=violation_dt,
                shift_id=calculate_shift(violation_dt),
                district=district,
                location_desc=location_desc,
                latitude=row.get("緯度") if not pd.isna(row.get("緯度")) else None,
                longitude=row.get("經度") if not pd.isna(row.get("經度")) else None,
                violation_code=violation_code,
                violation_name=violation_name[:200] if violation_name else None,
                topic_dui=topics["dui"],
                topic_red_light=topics["red_light"],
                topic_dangerous=topics["dangerous"],
                year=violation_dt.year,
                month=violation_dt.month,
                day_of_week=violation_dt.weekday(),
                enforcement_type=enforcement_type[:20] if enforcement_type else None,
                enforcement_subtype=enforcement_subtype[:50] if enforcement_subtype else None,
                unit_code=unit_code_norm[:50] if unit_code_norm else None,
                driver_age=driver_age,
                driver_age_group=age_group,
                is_elderly=is_elderly,
                vehicle_type=vehicle_type,
                driver_gender=driver_gender,
                evehicle_type=evehicle_type,
                evehicle_violation=evehicle_violation,
                is_youth=is_youth,
            )

            db.add(ticket)
            seen_ids.add(ticket_number)
            stats["new"] += 1

            if stats["new"] % 100 == 0:
                db.commit()

        except Exception as e:
            db.rollback()
            stats["errors"] += 1
            if len(error_messages) < 10:
                error_messages.append(f"第 {idx + 2} 列：{str(e)}")

    db.commit()
    return stats, topic_counts, error_messages


def _get_ticket_db_stats(db):
    """取得舉發案件的資料庫統計"""
    return {
        "total_tickets": db.query(Ticket).count(),
        "topics": {
            "dui": db.query(Ticket).filter(Ticket.topic_dui == True).count(),
            "red_light": db.query(Ticket).filter(Ticket.topic_red_light == True).count(),
            "dangerous": db.query(Ticket).filter(Ticket.topic_dangerous == True).count(),
        },
        "elderly": db.query(Ticket).filter(Ticket.is_elderly == True).count(),
    }


@router.post("/crash/upload-batch")
async def import_crash_upload_batch(
    files: list[UploadFile] = File(..., description="多個事故檔案（.xlsx/.xls/.txt）"),
    db: Session = Depends(get_db),
):
    """
    透過瀏覽器上傳多個事故檔案進行批次匯入。
    支援同時上傳多個 .xlsx / .xls / .txt 檔案。
    """
    import traceback

    ALLOWED_EXTENSIONS = (".xlsx", ".xls", ".txt")

    total_stats = {"files": 0, "total": 0, "new": 0, "skipped": 0, "errors": 0, "files_skipped": 0, "updated": 0}
    coords_total = {"with_gps": 0, "fallback": 0}
    all_errors = []
    files_missing_subunit = []  # 缺「所轄單位名稱」欄位的檔
    files_missing_severity = []  # 缺「事故類別」欄位的檔
    seen_case_ids: set = set()
    batch_ids_this_run = []  # 本次上傳產生的所有 batch_id（各檔各自時間戳，健檢需收集全部）

    # 檢查是否需要回補 sub_unit（舊版匯入時未讀「所轄單位名稱」）
    needs_backfill_subunit = db.query(func.count(Crash.id)).filter(
        Crash.sub_unit.like('%交通分隊%')
    ).scalar() > 0
    # 路口衝突方向引擎（Wave 28）回補哨兵：signal_action 全史 87% 案件應有值，
    # 若全庫皆為 NULL 代表尚未跑過回補，允許已匯入檔案重新進入流程補值；
    # 回補後 signal_action 必非零，冪等不再重跑。
    conflict_backfill_needed = (
        db.query(func.count(Crash.id)).scalar() > 0
        and db.query(func.count(Crash.id)).filter(Crash.signal_action.isnot(None)).scalar() == 0
    )
    # 事故處理時效／道路恢復效率（Wave 30-1）回補哨兵：clearance_minutes 全庫皆為
    # NULL 代表尚未跑過回補，允許已匯入檔案重新進入流程補值；
    # 回補後 clearance_minutes 必非零，冪等不再重跑。
    clearance_backfill_needed = (
        db.query(func.count(Crash.id)).scalar() > 0
        and db.query(func.count(Crash.id)).filter(Crash.clearance_minutes.isnot(None)).scalar() == 0
    )
    # 行人涉入精確口徑（Wave 31-A）回補哨兵：全庫皆無 involves_pedestrian=True 但已有資料，
    # 代表尚未跑過回補，允許已匯入檔案重新進入流程補值；回補後必有部分案件為 True，冪等不再重跑。
    pedestrian_backfill_needed = (
        db.query(func.count(Crash.id)).scalar() > 0
        and db.query(func.count(Crash.id)).filter(Crash.involves_pedestrian == True).scalar() == 0
    )
    # 事故當事者層（Wave 32）回補哨兵：core_crash_party 全空但已有事故資料，
    # 代表尚未落地當事者層，允許已匯入檔案重新進入流程補值；回補後非零，冪等不再重跑。
    party_backfill_needed = (
        db.query(func.count(Crash.id)).scalar() > 0
        and db.query(func.count(CrashParty.id)).scalar() == 0
    )
    needs_backfill = (
        needs_backfill_subunit or conflict_backfill_needed or clearance_backfill_needed
        or pedestrian_backfill_needed or party_backfill_needed
    )

    for file in files:
        if not file.filename or not file.filename.endswith(ALLOWED_EXTENSIONS):
            all_errors.append(f"[{file.filename}] 不支援的檔案格式")
            continue

        is_txt = file.filename.endswith(".txt")

        try:
            suffix = ".txt" if is_txt else ".xlsx"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = tmp.name
        except Exception as e:
            all_errors.append(f"[{file.filename}] 檔案儲存失敗: {str(e)}")
            continue

        try:
            if is_txt:
                df = _read_eis_txt(tmp_path)
            else:
                df_raw = pd.read_excel(tmp_path, header=None)
                header_row = 0
                for i in range(min(10, len(df_raw))):
                    row_values = [str(v).strip() for v in df_raw.iloc[i] if pd.notna(v)]
                    row_text = " ".join(row_values)
                    if any(kw in row_text for kw in ["案件編號", "發生時間", "事故編號", "總編號", "GPS緯度"]):
                        header_row = i
                        break
                df = pd.read_excel(tmp_path, header=header_row)

            df.columns = [str(c).strip().replace("\n", "") for c in df.columns]
            data_format = detect_crash_format(list(df.columns))
            batch_id = f"UPLOAD_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
            batch_ids_this_run.append(batch_id)

            # 缺「所轄單位名稱」欄位偵測
            if data_format == "EIS" and not has_subunit_column(df):
                files_missing_subunit.append(file.filename)
            # 缺「事故類別」欄位偵測
            if data_format == "EIS" and not any(
                ("事故類別" in str(c)) or ("交通事故類別" in str(c)) for c in df.columns
            ):
                files_missing_severity.append(file.filename)

            stats = {"total": len(df), "new": 0, "skipped": 0, "errors": 0, "updated": 0}
            coords_stats = {"with_gps": 0, "fallback": 0}

            # Pre-pass：以 case_id 為單位 rollup 飲酒情形（同 web/batch import）
            case_rollup: dict[str, dict] = {}
            if data_format == "EIS":
                _DRINKING_CODES = {"04", "05", "06", "07", "08", "4", "5", "6", "7", "8"}
                _ALCOHOL_CAUSE_CODES = {"53"}
                _ALCOHOL_KEYWORDS = ["酒醉", "酒後", "飲酒", "醉駕"]
                for _, _row in df.iterrows():
                    _rid = None
                    for _c in ["總編號(案件編號)", "總編號（案件編號）", "案件編號", "總編號"]:
                        if _c in _row.index and pd.notna(_row.get(_c)):
                            _v = str(_row.get(_c)).strip()
                            if _v:
                                _rid = _v
                                break
                    if not _rid:
                        continue
                    _subtype = (_safe_eis_str(_row, "26.當事者區分(類別)子類別代碼(車種)") or "").strip()
                    _drinking = (_safe_eis_str(_row, "32.飲酒情形代碼") or "").strip()
                    _cause_code = (_safe_eis_str(_row, "34.初步分析研判-個別代碼") or "").strip().lstrip("0")
                    _cause_text = _safe_eis_str(_row, "34.初步分析研判子類別-主要") or ""
                    _is_pedestrian = _subtype.startswith("H")
                    _is_drinking_primary = _drinking in _DRINKING_CODES
                    _is_drinking_secondary = (
                        _cause_code in _ALCOHOL_CAUSE_CODES
                        or any(kw in _cause_text for kw in _ALCOHOL_KEYWORDS)
                    )
                    _is_drinking = _is_drinking_primary or _is_drinking_secondary
                    _bucket = case_rollup.setdefault(_rid, {
                        "has_drinking_party": False,
                        "driver_subtype_code": None,
                        "driver_drinking_code": None,
                        "driver_license_status": None,
                        "driver_protective_gear": None,
                        "any_hit_and_run": False,
                        "delivery_platform": None,
                        # 路口衝突方向引擎（Wave 28）：順位1×順位2 當事者行動狀態配對
                        "_conflict_act1": None,
                        "_conflict_act2": None,
                        "conflict_action_pair": None,
                        "_picked_priority": 0,
                        # 行人涉入精確口徑（Wave 31-A）
                        "involves_pedestrian": False,
                        "ped_death_count": 0,
                        "ped_late_death_count": 0,
                        "ped_injury_count": 0,
                    })
                    if not _is_pedestrian and _is_drinking:
                        _bucket["has_drinking_party"] = True
                    # 行人涉入精確口徑（Wave 31-A）：任一當事者「26.當事者區分(類別)」
                    # 子類別文字含「行人」或「輔助代步器材」（電動代步車使用者道交視同行人）。
                    # ⚠️ 不可用大類別「人」判定，該大類含乘客，乘客不是行人。
                    _party_sub_type = _safe_eis_str(_row, "26.當事者區分(類別)")
                    if "行人" in _party_sub_type or "輔助代步器材" in _party_sub_type:
                        _bucket["involves_pedestrian"] = True
                        _ped_injury = _safe_eis_str(_row, "22.受傷程度")
                        if _ped_injury == "24小時內死亡":
                            _bucket["ped_death_count"] += 1
                        elif _ped_injury == "2-30日內死亡":
                            _bucket["ped_late_death_count"] += 1
                        elif _ped_injury == "受傷":
                            _bucket["ped_injury_count"] += 1
                    # 案件級聚合：任一當事者肇逃=是；外送平台取第一個有效值
                    if _safe_eis_str(_row, "35.肇事逃逸(是否肇逃)") == "是":
                        _bucket["any_hit_and_run"] = True
                    if not _bucket["delivery_platform"]:
                        _dp = _safe_eis_str(_row, "37.共享經濟或外送平台")
                        # 僅收真外送/共享（排除「其他(非共享經濟與外送平台)」「非駕駛人」雜訊）
                        if _dp and ("外送" in _dp or "共享" in _dp) and "非共享" not in _dp:
                            _bucket["delivery_platform"] = _dp[:50]
                    # 路口衝突方向引擎（Wave 28）：順位1×順位2 當事者行動狀態配對
                    _pos_raw = _safe_eis_str(_row, "當事者順位").strip()
                    _pos = _pos_raw.lstrip("0") or _pos_raw
                    _action_status = _safe_eis_str(_row, "29.當事者行動狀態類別名稱") or None
                    if _pos == "1" and _bucket["_conflict_act1"] is None and _action_status:
                        _bucket["_conflict_act1"] = _action_status
                    elif _pos == "2" and _bucket["_conflict_act2"] is None and _action_status:
                        _bucket["_conflict_act2"] = _action_status
                    if _bucket["_conflict_act1"] and _bucket["_conflict_act2"]:
                        _bucket["conflict_action_pair"] = (
                            f"{_bucket['_conflict_act1']}×{_bucket['_conflict_act2']}"[:80]
                        )
                    _priority = 3 if (not _is_pedestrian and _is_drinking) else (2 if not _is_pedestrian else 1)
                    if _priority > _bucket["_picked_priority"]:
                        _bucket["_picked_priority"] = _priority
                        _bucket["driver_subtype_code"] = _subtype[:10] if _subtype else None
                        _bucket["driver_drinking_code"] = _drinking[:2] if _drinking else None
                        _bucket["driver_license_status"] = (_safe_eis_str(_row, "30.駕照狀態") or None)
                        _bucket["driver_protective_gear"] = (_safe_eis_str(_row, "24.保護裝備") or None)

            for idx, row in df.iterrows():
                try:
                    # 案件編號
                    case_id = None
                    id_candidates = (
                        ["總編號(案件編號)", "總編號（案件編號）", "案件編號", "總編號", "案號", "CaseID"]
                        if data_format == "EIS"
                        else ["案件編號", "案號", "事故編號", "編號", "案件序號", "序號", "CaseID", "case_id"]
                    )
                    for col_name in id_candidates:
                        if col_name in row.index and pd.notna(row.get(col_name)):
                            val = str(row.get(col_name)).strip()
                            if val and any(c.isdigit() for c in val):
                                case_id = val
                                break

                    if not case_id:
                        non_empty_count = sum(1 for v in row if pd.notna(v) and str(v).strip())
                        if non_empty_count < 3:
                            continue
                        stats["errors"] += 1
                        continue

                    if case_id in seen_case_ids:
                        # 同批次重複（同案多當事者列 / 跨檔同案）：
                        # 較新匯出檔帶官方事故類別或工程欄位時，回補先寫入的案件
                        if data_format == "EIS":
                            dup = db.query(Crash).filter(Crash.case_id == case_id).first()
                            if dup is not None:
                                backfill_official_severity(dup, row, stats)
                                backfill_road_fields(dup, row, case_rollup.get(case_id, {}))
                        stats["skipped"] += 1
                        continue
                    existing = db.query(Crash).filter(Crash.case_id == case_id).first()
                    if existing:
                        seen_case_ids.add(case_id)
                        # 回補轄區派出所
                        if needs_backfill and existing.sub_unit and "交通分隊" in existing.sub_unit:
                            # 僅用真正的轄區欄位回補（不含處理單位備援，避免用交通分隊覆寫）
                            new_sub_val = (
                                _safe_eis_str(row, "所轄單位名稱")
                                or _safe_eis_str(row, "管轄單位名稱")
                            )
                            if new_sub_val:
                                new_sub = clean_precinct_name(new_sub_val)
                                if new_sub and "分局" in new_sub:
                                    suffix = new_sub.split("分局", 1)[1].strip()
                                    if suffix:
                                        new_sub = suffix
                                if new_sub and new_sub != existing.sub_unit:
                                    existing.sub_unit = new_sub[:100]
                                    stats["updated"] += 1
                        # 回補新加入的酒駕欄位
                        if data_format == "EIS":
                            rollup = case_rollup.get(case_id, {})
                            new_is_dui = bool(rollup.get("has_drinking_party", False))
                            new_drinking = rollup.get("driver_drinking_code")
                            new_subtype = rollup.get("driver_subtype_code")
                            if not existing.is_dui_crash_party and new_is_dui:
                                existing.is_dui_crash_party = True
                                existing.suspected_alcohol = True
                                stats["updated"] += 1
                            if not existing.drinking_code and new_drinking:
                                existing.drinking_code = new_drinking
                            if not existing.party_subtype_code and new_subtype:
                                existing.party_subtype_code = new_subtype
                            # 官方 severity / 死傷回補（較新匯出檔為準）
                            backfill_official_severity(existing, row, stats)
                            backfill_road_fields(existing, row, rollup)
                        stats["skipped"] += 1
                        continue

                    if data_format == "EIS":
                        time_col = "1.發生時間" if "1.發生時間" in row.index else "發生時間"
                        occurred_dt = parse_eis_datetime(row.get("發生日期"), row.get(time_col))
                        if not occurred_dt:
                            occurred_dt = parse_roc_datetime(row.get("發生日期"))
                        if not occurred_dt:
                            stats["errors"] += 1
                            continue

                        eis_lat = pd.to_numeric(row.get("GPS緯度"), errors="coerce")
                        eis_lon = pd.to_numeric(row.get("GPS經度"), errors="coerce")
                        if validate_taiwan_coords(eis_lat, eis_lon):
                            latitude, longitude = float(eis_lat), float(eis_lon)
                            coords_stats["with_gps"] += 1
                        else:
                            district_temp = extract_eis_district(row)
                            latitude, longitude = get_district_coordinates(district_temp)
                            coords_stats["fallback"] += 1

                        district = extract_eis_district(row)
                        location_desc = build_eis_location(row)[:200]
                        severity = derive_eis_severity(row)
                        death_count = get_eis_int(row, "3-1.24小時內死亡人數", "死亡")
                        injury_count = get_eis_int(row, "3-2.受傷人數", "受傷")
                        # 2-30日內死亡人數（僅註記用，不影響 severity 分類與24hr口徑死亡統計；無 fallback 欄名）
                        late_death_count = get_eis_int(row, "3-2.2-30日內死亡人數")
                        precinct = clean_precinct_name(row.get("處理單位名稱分局層"))
                        # 轄區派出所統一由 extract_sub_unit 處理（含全選條件「管轄單位名稱」欄名）
                        sub_unit = extract_sub_unit(row)
                        cause = (
                            _safe_eis_str(row, "34.初步分析研判子類別-主要")
                            or _safe_eis_str(row, "34.初步分析研判-個別")
                            or _safe_eis_str(row, "34.初步分析研判-個別代碼")
                            or _safe_eis_str(row, "肇事主要原因")
                            or None
                        )
                        weather = _safe_eis_str(row, "天候") or _safe_eis_str(row, "4.天候") or None
                        light = _safe_eis_str(row, "光線") or None

                        # 新邏輯：飲酒情形代碼（從 case_rollup 取）
                        rollup = case_rollup.get(case_id, {})
                        is_dui_crash_party = bool(rollup.get("has_drinking_party", False))
                        drinking_code = rollup.get("driver_drinking_code")
                        party_subtype_code = rollup.get("driver_subtype_code")
                        suspected_alcohol = is_dui_crash_party
                        # 道路工程分析欄位（Phase 1：案件級 + 代表駕駛級）
                        road_fields = extract_road_engineering_fields(row)
                        license_status = rollup.get("driver_license_status")
                        protective_gear = rollup.get("driver_protective_gear")
                        is_hit_and_run = bool(rollup.get("any_hit_and_run", False))
                        delivery_platform = rollup.get("delivery_platform")
                        conflict_action_pair = rollup.get("conflict_action_pair")
                        # 行人涉入精確口徑（Wave 31-A）
                        involves_pedestrian = bool(rollup.get("involves_pedestrian", False))
                        ped_death_count = rollup.get("ped_death_count", 0)
                        ped_late_death_count = rollup.get("ped_late_death_count", 0)
                        ped_injury_count = rollup.get("ped_injury_count", 0)

                        # 舊邏輯 fallback
                        if not is_dui_crash_party and (drinking_code is None and party_subtype_code is None):
                            alcohol_val = _safe_eis_str(row, "酒測值") or _safe_eis_str(row, "飲酒情形")
                            if alcohol_val:
                                if "飲酒" in alcohol_val or "酒後" in alcohol_val:
                                    suspected_alcohol = True
                                    is_dui_crash_party = True
                                else:
                                    try:
                                        if float(alcohol_val) > 0:
                                            suspected_alcohol = True
                                            is_dui_crash_party = True
                                    except (ValueError, TypeError):
                                        pass
                    else:
                        occurred_dt = None
                        for time_col in ["發生時間", "事故時間", "發生日期時間", "日期時間", "時間", "發生日期"]:
                            if time_col in row.index and pd.notna(row.get(time_col)):
                                occurred_dt = parse_roc_datetime(row.get(time_col))
                                if occurred_dt:
                                    break
                        if not occurred_dt:
                            stats["errors"] += 1
                            continue

                        location_val = None
                        for loc_col in ["發生地點", "事故地點", "地點", "地址", "發生地址", "事故位置"]:
                            if loc_col in row.index and pd.notna(row.get(loc_col)):
                                location_val = row.get(loc_col)
                                break
                        district, location_desc = deidentify_address(location_val)

                        severity = "A3"
                        for sev_col in ["交通事故類別", "事故類別", "類別", "嚴重程度", "事故等級"]:
                            if sev_col in row.index and pd.notna(row.get(sev_col)):
                                severity = str(row.get(sev_col)).strip().upper()
                                break
                        if severity not in ["A1", "A2", "A3"]:
                            severity = "A3"

                        legacy_lat = pd.to_numeric(row.get("緯度"), errors="coerce")
                        legacy_lon = pd.to_numeric(row.get("經度"), errors="coerce")
                        if validate_taiwan_coords(legacy_lat, legacy_lon):
                            latitude, longitude = float(legacy_lat), float(legacy_lon)
                        else:
                            latitude, longitude = get_district_coordinates(district)

                        death_count = 0
                        injury_count = 0
                        late_death_count = 0  # LEGACY 無此欄，2-30日死亡註記僅 EIS 全選條件檔才有
                        precinct = None
                        sub_unit = None
                        cause = str(row.get("肇事主要原因") or row.get("肇事原因") or "").strip() or None
                        weather = str(row.get("天候") or "").strip() or None
                        light = str(row.get("光線") or "").strip() or None

                        suspected_alcohol = False
                        alcohol_val = row.get("酒測值") or row.get("飲酒情形")
                        if alcohol_val:
                            val_str = str(alcohol_val)
                            if "飲酒" in val_str or "酒後" in val_str:
                                suspected_alcohol = True
                            else:
                                try:
                                    if float(val_str) > 0:
                                        suspected_alcohol = True
                                except (ValueError, TypeError):
                                    pass

                        # LEGACY 沒有結構化代碼，is_dui_crash_party 同步 suspected_alcohol
                        drinking_code = None
                        party_subtype_code = None
                        is_dui_crash_party = suspected_alcohol
                        # LEGACY 無道路工程欄位
                        road_fields = {}
                        license_status = None
                        protective_gear = None
                        is_hit_and_run = False
                        delivery_platform = None
                        conflict_action_pair = None
                        # LEGACY 無 26.當事者區分(類別) 子類別文字欄，行人精確口徑無法判定
                        involves_pedestrian = False
                        ped_death_count = 0
                        ped_late_death_count = 0
                        ped_injury_count = 0

                    # 共用欄位
                    age_val = (
                        _safe_eis_str(row, "當事者事故發生時年齡")
                        or _safe_eis_str(row, "25.當事者事故發生時年齡")
                        or _safe_eis_str(row, "當事人年齡")
                        or _safe_eis_str(row, "年齡")
                    ) or None
                    birth_date_val = (
                        _safe_eis_str(row, "當事者出生日期")
                        or _safe_eis_str(row, "出生年月日")
                        or _safe_eis_str(row, "出生日期")
                    ) or None

                    is_elderly = False
                    is_youth = False
                    driver_age_group = "未知"
                    if age_val:
                        driver_age_group, is_elderly, is_youth = classify_age(age_val)
                    elif birth_date_val:
                        birth_dt = parse_eis_datetime(birth_date_val, 0) or parse_roc_datetime(birth_date_val)
                        if birth_dt and occurred_dt:
                            age = occurred_dt.year - birth_dt.year - (
                                (occurred_dt.month, occurred_dt.day) < (birth_dt.month, birth_dt.day)
                            )
                            driver_age_group, is_elderly, is_youth = classify_age(age)

                    party_type_raw = (
                        _safe_eis_str(row, "當事人車種")
                        or _safe_eis_str(row, "車種")
                        or _safe_eis_str(row, "26.當事者區分(類別)")
                        or _safe_eis_str(row, "26.當事者區分(大類別)")
                    )
                    party_type = party_type_raw or None
                    evehicle_type, _ = classify_evehicle(party_type)

                    is_underage_14_riding = False
                    if evehicle_type == "微型電動二輪車" and driver_age_group == "<18":
                        try:
                            raw_age = age_val or _safe_eis_str(row, "當事人年齡") or _safe_eis_str(row, "年齡")
                            if raw_age and int(float(raw_age)) < 14:
                                is_underage_14_riding = True
                        except (ValueError, TypeError):
                            pass

                    driver_gender = (
                        _safe_eis_str(row, "17.當事者屬(性)別")
                        or _safe_eis_str(row, "當事者屬(性)別")
                        or _safe_eis_str(row, "當事者性別")
                        or _safe_eis_str(row, "當事人性別")
                        or _safe_eis_str(row, "性別")
                    ) or None

                    crash = Crash(
                        case_id=case_id,
                        import_batch_id=batch_id,
                        occurred_date=occurred_dt.date(),
                        occurred_time=occurred_dt,
                        shift_id=calculate_shift(occurred_dt),
                        district=district,
                        location_desc=location_desc,
                        latitude=latitude,
                        longitude=longitude,
                        severity=severity,
                        severity_weight=get_severity_weight(severity),
                        year=occurred_dt.year,
                        month=occurred_dt.month,
                        day_of_week=occurred_dt.weekday(),
                        driver_age_group=driver_age_group,
                        is_elderly=is_elderly,
                        driver_gender=driver_gender,
                        weather=weather,
                        light=light,
                        party_type=party_type,
                        cause=cause,
                        suspected_alcohol=suspected_alcohol,
                        drinking_code=drinking_code,
                        party_subtype_code=party_subtype_code,
                        is_dui_crash_party=is_dui_crash_party,
                        precinct=precinct,
                        sub_unit=sub_unit,
                        death_count=death_count,
                        injury_count=injury_count,
                        late_death_count=late_death_count,
                        evehicle_type=evehicle_type,
                        is_youth=is_youth,
                        is_underage_14=is_underage_14_riding,
                        # 道路工程分析欄位（Phase 1）
                        license_status=license_status,
                        protective_gear=protective_gear,
                        is_hit_and_run=is_hit_and_run,
                        delivery_platform=delivery_platform,
                        # 路口衝突方向引擎（Wave 28）
                        conflict_action_pair=conflict_action_pair,
                        # 行人涉入精確口徑（Wave 31-A）
                        involves_pedestrian=involves_pedestrian,
                        ped_death_count=ped_death_count,
                        ped_late_death_count=ped_late_death_count,
                        ped_injury_count=ped_injury_count,
                        **road_fields,
                    )

                    db.add(crash)
                    seen_case_ids.add(case_id)
                    stats["new"] += 1

                    if stats["new"] % 100 == 0:
                        db.commit()

                except Exception as e:
                    db.rollback()
                    stats["errors"] += 1
                    if len(all_errors) < 20:
                        all_errors.append(f"[{file.filename}] 第 {idx + 2} 列: {str(e)}")

            db.commit()

            # 事故當事者層落地（Wave 32）：以 case 為單位 delete-then-insert，
            # 再由當事者層重算 is_elderly / is_youth 與高齡人數欄位。
            if data_format == "EIS":
                _parties = collect_crash_parties(df)
                if _parties:
                    persist_crash_parties(db, _parties)
                    db.commit()
                    recompute_party_rollups(db, list(_parties.keys()))

            total_stats["files"] += 1
            total_stats["total"] += stats["total"]
            total_stats["new"] += stats["new"]
            total_stats["skipped"] += stats["skipped"]
            total_stats["errors"] += stats["errors"]
            total_stats["updated"] = total_stats.get("updated", 0) + stats.get("updated", 0)
            coords_total["with_gps"] += coords_stats["with_gps"]
            coords_total["fallback"] += coords_stats["fallback"]

        except Exception as e:
            all_errors.append(f"[{file.filename}] 檔案處理失敗: {str(e)}")

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    total_crashes = db.query(Crash).count()
    severity_stats = {
        "A1": db.query(Crash).filter(Crash.severity == "A1").count(),
        "A2": db.query(Crash).filter(Crash.severity == "A2").count(),
        "A3": db.query(Crash).filter(Crash.severity == "A3").count(),
    }

    msg_parts = []
    if total_stats["files"] > 0:
        msg_parts.append(f"匯入 {total_stats['files']} 個檔案，新增 {total_stats['new']} 筆")
    if total_stats.get("updated", 0) > 0:
        msg_parts.append(f"回補轄區派出所 {total_stats['updated']} 筆")
    if total_stats["skipped"] > 0:
        msg_parts.append(f"略過 {total_stats['skipped']} 筆重複")
    if total_stats["errors"] > 0:
        msg_parts.append(f"錯誤 {total_stats['errors']} 筆")
    if not msg_parts:
        msg_parts.append("無新資料")

    subunit_warning = None
    if files_missing_subunit:
        subunit_warning = (
            f"⚠️ 以下 {len(files_missing_subunit)} 個檔缺「所轄單位名稱」欄位，"
            f"事故將歸入交通分隊、派出所統計失準，建議重新匯出勾選該欄位："
            + "、".join(files_missing_subunit)
        )
    severity_warning = None
    if files_missing_severity:
        severity_warning = (
            f"⚠️ 以下 {len(files_missing_severity)} 個檔缺「事故類別」欄位，"
            f"A1/A2/A3 改用死傷人數推導，受傷欄未填完整會誤判，建議匯出時勾選「事故類別」："
            + "、".join(files_missing_severity)
        )

    # 匯入後自動資料健檢（防污染防線）：對本次上傳產生的全部 batch_id 一起檢查
    try:
        health_warnings = run_batch_health_checks(db, batch_ids_this_run)
    except Exception:
        health_warnings = ["健檢執行失敗（不影響匯入結果）"]

    return {
        "success": True,
        "message": "批次上傳匯入完成：" + "，".join(msg_parts)
                   + (f"｜{subunit_warning}" if subunit_warning else "")
                   + (f"｜{severity_warning}" if severity_warning else ""),
        "stats": total_stats,
        "subunit_warning": subunit_warning,
        "severity_warning": severity_warning,
        "coordinates": coords_total,
        "errors": all_errors[:20] if all_errors else [],
        "health_warnings": health_warnings,
        "database": {
            "total_crashes": total_crashes,
            "severity": severity_stats,
        },
    }


@router.post("/ticket/upload-batch")
async def import_ticket_upload_batch(
    files: list[UploadFile] = File(..., description="多個舉發 Excel 檔案"),
    db: Session = Depends(get_db),
):
    """
    透過瀏覽器上傳多個舉發檔案進行批次匯入。
    支援同時上傳多個 .xlsx / .xls 檔案。
    """
    total_stats = {"files": 0, "total": 0, "new": 0, "skipped": 0, "errors": 0}
    total_topics = {"dui": 0, "red_light": 0, "dangerous": 0}
    all_errors = []

    for file in files:
        if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
            all_errors.append(f"[{file.filename}] 不支援的檔案格式（僅支援 .xlsx/.xls）")
            continue

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = tmp.name
        except Exception as e:
            all_errors.append(f"[{file.filename}] 檔案儲存失敗: {str(e)}")
            continue

        try:
            df = pd.read_excel(tmp_path)
            batch_id = f"UPLOAD_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
            file_errors = []
            stats, topic_counts, file_errors = _import_ticket_df(df, batch_id, db, file_errors)

            total_stats["files"] += 1
            total_stats["total"] += stats["total"]
            total_stats["new"] += stats["new"]
            total_stats["skipped"] += stats["skipped"]
            total_stats["errors"] += stats["errors"]
            total_stats["updated"] = total_stats.get("updated", 0) + stats.get("updated", 0)
            for k in total_topics:
                total_topics[k] += topic_counts[k]
            for e in file_errors:
                if len(all_errors) < 20:
                    all_errors.append(f"[{file.filename}] {e}")

        except Exception as e:
            all_errors.append(f"[{file.filename}] 檔案處理失敗: {str(e)}")

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    db_stats = _get_ticket_db_stats(db)

    msg_parts = []
    if total_stats["files"] > 0:
        msg_parts.append(f"匯入 {total_stats['files']} 個檔案，新增 {total_stats['new']} 筆")
    if total_stats.get("updated", 0) > 0:
        msg_parts.append(f"回補 {total_stats['updated']} 筆舉發子類型")
    if total_stats["skipped"] > 0:
        msg_parts.append(f"略過 {total_stats['skipped']} 筆重複")
    if total_stats["errors"] > 0:
        msg_parts.append(f"錯誤 {total_stats['errors']} 筆")
    if not msg_parts:
        msg_parts.append("無新資料")

    return {
        "success": True,
        "message": "批次上傳匯入完成：" + "，".join(msg_parts),
        "stats": total_stats,
        "topics_imported": total_topics,
        "errors": all_errors[:20] if all_errors else [],
        "database": db_stats,
    }


@router.post("/ticket")
async def import_ticket_file(
    file: UploadFile = File(..., description="舉發案件 Excel 檔案"),
    db: Session = Depends(get_db),
):
    """
    匯入舉發案件資料

    - 支援 .xlsx, .xls 格式
    - 自動去重（依舉發單號）
    - 自動主題分類（酒駕、闘紅燈、危險駕駛）
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400, detail="僅支援 Excel 檔案格式 (.xlsx, .xls)"
        )

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"檔案儲存失敗: {str(e)}")

    try:
        df = pd.read_excel(tmp_path)
        batch_id = f"WEB_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        stats, topic_counts, error_messages = _import_ticket_df(df, batch_id, db)
        db_stats = _get_ticket_db_stats(db)

        return {
            "success": True,
            "message": f"匯入完成：新增 {stats['new']} 筆，回補 {stats.get('updated', 0)} 筆，略過 {stats['skipped']} 筆（重複），錯誤 {stats['errors']} 筆",
            "batch_id": batch_id,
            "stats": stats,
            "topics_imported": topic_counts,
            "errors": error_messages[:10] if error_messages else [],
            "database": db_stats,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"匯入失敗: {str(e)}")

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/ticket/batch")
async def import_ticket_batch(db: Session = Depends(get_db)):
    """
    批次匯入舉發案件綜合查詢資料夾中所有 Excel 檔案。

    自動讀取專案根目錄下的「舉發案件綜合查詢」資料夾。
    """
    import traceback

    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    project_root = os.path.dirname(backend_dir)
    data_dir = os.path.join(project_root, "舉發案件綜合查詢")

    if not os.path.isdir(data_dir):
        raise HTTPException(
            status_code=404,
            detail=f"找不到舉發案件資料夾: {data_dir}",
        )

    xlsx_files = sorted(
        [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.endswith((".xlsx", ".xls"))]
    )
    if not xlsx_files:
        raise HTTPException(status_code=404, detail="資料夾中沒有 Excel 檔案")

    try:
        total_stats = {"files": 0, "total": 0, "new": 0, "skipped": 0, "errors": 0, "files_skipped": 0}
        total_topics = {"dui": 0, "red_light": 0, "dangerous": 0}
        all_errors = []
        skipped_files = []

        # 取得已匯入過的檔案名稱
        imported_files = _get_imported_filenames(db, Ticket)

        # 檢查是否有需要回補的欄位（enforcement_type 為 NULL 的筆數）
        needs_backfill = db.query(func.count(Ticket.id)).filter(
            Ticket.enforcement_type.is_(None)
        ).scalar() > 0

        for fpath in xlsx_files:
            fname = os.path.basename(fpath)

            # 跳過已匯入的檔案（除非需要回補欄位）
            if fname in imported_files and not needs_backfill:
                total_stats["files_skipped"] += 1
                skipped_files.append(fname)
                continue

            try:
                df = pd.read_excel(fpath)
                batch_id = f"BATCH_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{fname}"
                file_errors = []
                stats, topic_counts, file_errors = _import_ticket_df(df, batch_id, db, file_errors)

                if fname in imported_files:
                    # 已匯入過的檔案，只計算回補數
                    total_stats["files_skipped"] += 1
                    skipped_files.append(fname)
                else:
                    total_stats["files"] += 1
                total_stats["total"] += stats["total"]
                total_stats["new"] += stats["new"]
                total_stats["skipped"] += stats["skipped"]
                total_stats["errors"] += stats["errors"]
                total_stats["updated"] = total_stats.get("updated", 0) + stats.get("updated", 0)
                for k in total_topics:
                    total_topics[k] += topic_counts[k]
                for e in file_errors:
                    if len(all_errors) < 20:
                        all_errors.append(f"[{fname}] {e}")

            except Exception as e:
                all_errors.append(f"[{fname}] 檔案讀取失敗: {str(e)}")

        db_stats = _get_ticket_db_stats(db)

        msg_parts = []
        if total_stats["files"] > 0:
            msg_parts.append(f"匯入 {total_stats['files']} 個檔案，新增 {total_stats['new']} 筆")
        if total_stats.get("updated", 0) > 0:
            msg_parts.append(f"回補 {total_stats['updated']} 筆舉發子類型")
        if total_stats["files_skipped"] > 0:
            msg_parts.append(f"跳過 {total_stats['files_skipped']} 個已匯入檔案")
        if total_stats["skipped"] > 0:
            msg_parts.append(f"略過 {total_stats['skipped']} 筆重複")
        if total_stats["errors"] > 0:
            msg_parts.append(f"錯誤 {total_stats['errors']} 筆")
        if not msg_parts:
            msg_parts.append("所有檔案皆已匯入，無新資料")

        return {
            "success": True,
            "message": "批次匯入完成：" + "，".join(msg_parts),
            "stats": total_stats,
            "topics_imported": total_topics,
            "skipped_files": skipped_files,
            "errors": all_errors[:20] if all_errors else [],
            "database": db_stats,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"批次匯入失敗: {str(e)}")


@router.get("/status")
async def get_import_status(db: Session = Depends(get_db)):
    """
    取得目前資料庫狀態
    """
    crash_count = db.query(Crash).count()
    ticket_count = db.query(Ticket).count()

    severity_stats = {
        "A1": db.query(Crash).filter(Crash.severity == "A1").count(),
        "A2": db.query(Crash).filter(Crash.severity == "A2").count(),
        "A3": db.query(Crash).filter(Crash.severity == "A3").count(),
    }

    topic_stats = {
        "dui": db.query(Ticket).filter(Ticket.topic_dui == True).count(),
        "red_light": db.query(Ticket).filter(Ticket.topic_red_light == True).count(),
        "dangerous": db.query(Ticket).filter(Ticket.topic_dangerous == True).count(),
    }

    elderly_stats = {
        "tickets": db.query(Ticket).filter(Ticket.is_elderly == True).count(),
        "crashes": db.query(Crash).filter(Crash.is_elderly == True).count(),
    }

    return {
        "crashes": {
            "total": crash_count,
            "severity": severity_stats,
        },
        "tickets": {
            "total": ticket_count,
            "topics": topic_stats,
        },
        "elderly": elderly_stats,
        "note": "所有資料皆已去識別化",
    }
