# -*- coding: utf-8 -*-
"""
資料匯入 API
提供前端上傳 Excel 檔案的介面
"""

import os
import re
import tempfile
from datetime import datetime
from typing import Dict, Optional, Tuple

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import Crash, Ticket, Topic

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
        import random
        offset_lat = random.uniform(-0.003, 0.003)
        offset_lng = random.uniform(-0.003, 0.003)
        return lat + offset_lat, lng + offset_lng
    
    # 部分匹配
    for name, coords in DISTRICT_COORDINATES.items():
        if name in clean_district or clean_district in name:
            lat, lng = coords
            import random
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
    """去識別化地址，返回: (行政區, 去識別化地點描述)"""
    if pd.isna(address) or not address:
        return ("未知", "未知地點")

    address = str(address).strip()

    # 提取行政區
    district_match = re.search(r"([\u4e00-\u9fa5]{2,3}區)", address)
    district = district_match.group(1) if district_match else "未知"

    # 移除門牌號碼
    clean_address = re.sub(r"\d+[-之]?\d*號[前後旁]?", "", address)
    clean_address = re.sub(r"[\u4e00-\u9fa5]{2,4}里", "", clean_address)
    clean_address = re.sub(r"臺南市|台南市", "", clean_address)
    clean_address = re.sub(r"[\u4e00-\u9fa5]{2,3}區", "", clean_address)

    # 提取路/街名
    road_match = re.search(r"([\u4e00-\u9fa5]+[路街道巷])", clean_address)
    if road_match:
        location_desc = road_match.group(1)
    else:
        location_desc = clean_address.strip() or "未知地點"

    # 處理路口格式
    if "/" in address or "、" in address:
        parts = re.split(r"[/、]", address)
        roads = []
        for part in parts:
            road_match = re.search(r"([\u4e00-\u9fa5]+[路街道])", part)
            if road_match:
                roads.append(road_match.group(1))
        if len(roads) >= 2:
            location_desc = f"{roads[0]}與{roads[1]}路口"

    return (district, location_desc[:100])


def classify_age(age) -> Tuple[str, bool]:
    """將年齡轉換為年齡組，返回: (年齡組, 是否高齡者)"""
    if pd.isna(age) or age is None:
        return ("未知", False)

    try:
        age = int(float(age))
    except (ValueError, TypeError):
        return ("未知", False)

    if age < 18:
        return ("<18", False)
    elif age < 25:
        return ("18-24", False)
    elif age < 45:
        return ("25-44", False)
    elif age < 65:
        return ("45-64", False)
    else:
        return ("65+", True)


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
# API 路由
# ============================================


@router.post("/crash")
async def import_crash_file(
    file: UploadFile = File(..., description="交通事故 Excel 檔案"),
    db: Session = Depends(get_db),
):
    """
    匯入交通事故資料

    - 支援 .xlsx, .xls 格式
    - 自動去重（依案件編號）
    - 自動去識別化
    """
    # 驗證檔案類型
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400, detail="僅支援 Excel 檔案格式 (.xlsx, .xls)"
        )

    # 儲存暫存檔
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"檔案儲存失敗: {str(e)}")

    try:
        # 讀取 Excel - 先不指定標題列以偵測結構
        df_raw = pd.read_excel(tmp_path, header=None)
        
        # 自動偵測標題列：尋找包含「案件編號」或「發生時間」的列
        header_row = 0
        for i in range(min(10, len(df_raw))):
            row_values = [str(v).strip() for v in df_raw.iloc[i] if pd.notna(v)]
            row_text = ' '.join(row_values)
            if '案件編號' in row_text or '發生時間' in row_text or '事故編號' in row_text:
                header_row = i
                break
        
        # 重新讀取，使用正確的標題列
        df = pd.read_excel(tmp_path, header=header_row)
        
        # 清理欄位名稱（移除空白和換行）
        df.columns = [str(c).strip().replace('\n', '').replace(' ', '') for c in df.columns]
        
        batch_id = f"WEB_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        stats = {"total": len(df), "new": 0, "skipped": 0, "errors": 0}
        error_messages = []

        for idx, row in df.iterrows():
            try:
                # 支援多種案件編號欄位名稱
                case_id = None
                for col_name in ["案件編號", "案號", "事故編號", "編號", "案件序號", "序號", "CaseID", "case_id"]:
                    if col_name in row.index and pd.notna(row.get(col_name)):
                        val = str(row.get(col_name)).strip()
                        # 只接受看起來像案件編號的值（包含數字）
                        if val and any(c.isdigit() for c in val):
                            case_id = val
                            break
                
                # 如果沒有案件編號，靜默跳過（可能是空白列或標題列）
                if not case_id:
                    # 檢查整列是否大部分都是空的
                    non_empty_count = sum(1 for v in row if pd.notna(v) and str(v).strip())
                    if non_empty_count < 3:
                        # 靜默跳過空白列
                        continue
                    stats["errors"] += 1
                    error_messages.append(f"第 {idx + 2} 列：缺少案件編號")
                    continue

                # 去重檢查
                existing = db.query(Crash).filter(Crash.case_id == case_id).first()
                if existing:
                    stats["skipped"] += 1
                    continue

                # 解析時間 - 支援多種欄位名稱
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

                # 去識別化地址 - 支援多種欄位名稱
                location_val = None
                for loc_col in ["發生地點", "事故地點", "地點", "地址", "發生地址", "事故位置"]:
                    if loc_col in row.index and pd.notna(row.get(loc_col)):
                        location_val = row.get(loc_col)
                        break
                district, location_desc = deidentify_address(location_val)

                # 事故類別 - 支援多種欄位名稱
                severity = "A3"
                for sev_col in ["交通事故類別", "事故類別", "類別", "嚴重程度", "事故等級"]:
                    if sev_col in row.index and pd.notna(row.get(sev_col)):
                        severity = str(row.get(sev_col)).strip().upper()
                        break
                if severity not in ["A1", "A2", "A3"]:
                    severity = "A3"

                # 嘗試讀取年齡資訊（支援原始完整檔案）
                age_val = row.get("當事人年齡") or row.get("年齡") or row.get("Age")
                birth_date_val = row.get("出生年月日") or row.get("出生日期") or row.get("生日")
                
                is_elderly = False
                driver_age_group = "未知"
                
                # 優先使用年齡欄位
                if not pd.isna(age_val):
                    driver_age_group, is_elderly = classify_age(age_val)
                # 其次嘗試從生日計算
                elif not pd.isna(birth_date_val):
                    birth_dt = parse_roc_datetime(birth_date_val)
                    if birth_dt and occurred_dt:
                        age = occurred_dt.year - birth_dt.year - ((occurred_dt.month, occurred_dt.day) < (birth_dt.month, birth_dt.day))
                        if age >= 65:
                            is_elderly = True
                            driver_age_group = "65+"
                        elif age < 18:
                            driver_age_group = "<18"
                        elif age < 25:
                            driver_age_group = "18-24"
                        elif age < 45:
                            driver_age_group = "25-44"
                        else:
                            driver_age_group = "45-64"

                # 提取額外資訊（若有）
                party_type = str(row.get("當事人車種") or row.get("車種") or "").strip() or None
                cause = str(row.get("肇事主要原因") or row.get("肇事原因") or "").strip() or None
                driver_gender = str(row.get("當事人性別") or row.get("性別") or "").strip() or None
                weather = str(row.get("天候") or "").strip() or None
                light = str(row.get("光線") or "").strip() or None
                
                # 嘗試判斷酒駕
                alcohol_val = row.get("酒測值") or row.get("飲酒情形")
                suspected_alcohol = False
                if alcohol_val:
                    val_str = str(alcohol_val)
                    if "飲酒" in val_str or "酒後" in val_str:
                        suspected_alcohol = True
                    else:
                        try:
                            if float(val_str) > 0:
                                suspected_alcohol = True
                        except:
                            pass

                crash = Crash(
                    case_id=case_id,
                    import_batch_id=batch_id,
                    occurred_date=occurred_dt.date(),
                    occurred_time=occurred_dt,
                    shift_id=calculate_shift(occurred_dt),
                    district=district,
                    location_desc=location_desc,
                    # 座標：優先使用原始資料，否則使用區域中心座標
                    latitude=row.get("緯度") if pd.notna(row.get("緯度")) else get_district_coordinates(district)[0],
                    longitude=row.get("經度") if pd.notna(row.get("經度")) else get_district_coordinates(district)[1],
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
                )

                db.add(crash)
                stats["new"] += 1

                # 每 100 筆提交一次
                if stats["new"] % 100 == 0:
                    db.commit()

            except Exception as e:
                stats["errors"] += 1
                if len(error_messages) < 10:
                    error_messages.append(f"第 {idx + 2} 列：{str(e)}")

        db.commit()

        # 取得統計
        total_crashes = db.query(Crash).count()
        severity_stats = {
            "A1": db.query(Crash).filter(Crash.severity == "A1").count(),
            "A2": db.query(Crash).filter(Crash.severity == "A2").count(),
            "A3": db.query(Crash).filter(Crash.severity == "A3").count(),
        }

        return {
            "success": True,
            "message": f"匯入完成：新增 {stats['new']} 筆，略過 {stats['skipped']} 筆（重複），錯誤 {stats['errors']} 筆",
            "batch_id": batch_id,
            "stats": stats,
            "errors": error_messages[:10] if error_messages else [],
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
    - 自動去識別化
    """
    # 驗證檔案類型
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400, detail="僅支援 Excel 檔案格式 (.xlsx, .xls)"
        )

    # 儲存暫存檔
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"檔案儲存失敗: {str(e)}")

    try:
        # 讀取 Excel
        df = pd.read_excel(tmp_path)
        batch_id = f"WEB_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        stats = {"total": len(df), "new": 0, "skipped": 0, "errors": 0}
        topic_counts = {"dui": 0, "red_light": 0, "dangerous": 0}
        error_messages = []

        for idx, row in df.iterrows():
            try:
                ticket_number = str(row.get("舉發單號", "")).strip()
                if not ticket_number:
                    stats["errors"] += 1
                    error_messages.append(f"第 {idx + 2} 列：缺少舉發單號")
                    continue

                # 去重檢查
                existing = (
                    db.query(Ticket)
                    .filter(Ticket.ticket_number == ticket_number)
                    .first()
                )
                if existing:
                    stats["skipped"] += 1
                    continue

                # 解析時間
                time_str = row.get("違規時間(出)") or row.get("建檔時間")
                violation_dt = parse_roc_datetime(time_str)
                if not violation_dt:
                    stats["errors"] += 1
                    error_messages.append(f"第 {idx + 2} 列：違規時間格式錯誤")
                    continue

                # 去識別化地址
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
                age_group, is_elderly = classify_age(row.get("違規人年齡"))
                
                # 性別可能會在 "違規人性別" 或 "性別"
                driver_gender = str(row.get("違規人性別") or row.get("性別") or "").strip() or None

                # 車種提取
                vehicle_type = str(row.get("車種") or "").strip() or None

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
                    unit_code=str(row.get("舉發單位", ""))[:50]
                    if not pd.isna(row.get("舉發單位"))
                    else None,
                    driver_age_group=age_group,
                    is_elderly=is_elderly,
                    vehicle_type=vehicle_type,
                    driver_gender=driver_gender,
                )

                db.add(ticket)
                stats["new"] += 1

                # 每 100 筆提交一次
                if stats["new"] % 100 == 0:
                    db.commit()

            except Exception as e:
                stats["errors"] += 1
                if len(error_messages) < 10:
                    error_messages.append(f"第 {idx + 2} 列：{str(e)}")

        db.commit()

        # 取得統計
        total_tickets = db.query(Ticket).count()
        topic_stats = {
            "dui": db.query(Ticket).filter(Ticket.topic_dui == True).count(),
            "red_light": db.query(Ticket)
            .filter(Ticket.topic_red_light == True)
            .count(),
            "dangerous": db.query(Ticket)
            .filter(Ticket.topic_dangerous == True)
            .count(),
        }
        elderly_count = db.query(Ticket).filter(Ticket.is_elderly == True).count()

        return {
            "success": True,
            "message": f"匯入完成：新增 {stats['new']} 筆，略過 {stats['skipped']} 筆（重複），錯誤 {stats['errors']} 筆",
            "batch_id": batch_id,
            "stats": stats,
            "topics_imported": topic_counts,
            "errors": error_messages[:10] if error_messages else [],
            "database": {
                "total_tickets": total_tickets,
                "topics": topic_stats,
                "elderly": elderly_count,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"匯入失敗: {str(e)}")

    finally:
        # 清理暫存檔
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


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
