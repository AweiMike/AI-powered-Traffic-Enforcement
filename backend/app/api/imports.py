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
        # 讀取 Excel
        df = pd.read_excel(tmp_path)
        batch_id = f"WEB_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        stats = {"total": len(df), "new": 0, "skipped": 0, "errors": 0}
        error_messages = []

        for idx, row in df.iterrows():
            try:
                case_id = str(row.get("案件編號", "")).strip()
                if not case_id:
                    stats["errors"] += 1
                    error_messages.append(f"第 {idx + 2} 列：缺少案件編號")
                    continue

                # 去重檢查
                existing = db.query(Crash).filter(Crash.case_id == case_id).first()
                if existing:
                    stats["skipped"] += 1
                    continue

                # 解析時間
                occurred_dt = parse_roc_datetime(row.get("發生時間"))
                if not occurred_dt:
                    stats["errors"] += 1
                    error_messages.append(f"第 {idx + 2} 列：發生時間格式錯誤")
                    continue

                # 去識別化地址
                district, location_desc = deidentify_address(row.get("發生地點"))

                # 事故類別
                severity = str(row.get("交通事故類別", "A3")).strip().upper()
                if severity not in ["A1", "A2", "A3"]:
                    severity = "A3"

                crash = Crash(
                    case_id=case_id,
                    import_batch_id=batch_id,
                    occurred_date=occurred_dt.date(),
                    occurred_time=occurred_dt,
                    shift_id=calculate_shift(occurred_dt),
                    district=district,
                    location_desc=location_desc,
                    severity=severity,
                    severity_weight=get_severity_weight(severity),
                    year=occurred_dt.year,
                    month=occurred_dt.month,
                    day_of_week=occurred_dt.weekday(),
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
