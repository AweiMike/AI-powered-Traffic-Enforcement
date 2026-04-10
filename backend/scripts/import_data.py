# -*- coding: utf-8 -*-
"""
精準執法資料匯入工具 v2.0

功能：
1. 去重（根據案件編號/舉發單號，避免重複匯入）
2. 去識別化（移除門牌號、車號、姓名等個資）
3. 自動分類（三大主題：酒駕、闘紅燈、危險駕駛）
4. 時間處理（民國年轉西元、計算班別）
5. 批次追蹤（記錄每次匯入）

使用方式：
    python import_data.py --crash "事故.xlsx" --ticket "舉發.xlsx"
    python import_data.py --init  # 僅初始化資料庫
"""

import os
import sys
import re
import argparse
from datetime import datetime
from typing import Optional, Tuple, Dict

import pandas as pd
from sqlalchemy.orm import Session

# 添加專案路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base
from app.models.core import Crash, Ticket, Topic


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
    支援格式：
    - 114/01/08 09:30:00
    - 114-01-08 09:30:00
    - 114/01/08
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
    去識別化地址
    返回: (行政區, 去識別化地點描述)
    """
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
# 匯入函數
# ============================================


def import_crashes(filepath: str, db: Session, batch_id: str) -> Dict:
    """匯入交通事故資料（支援去重）"""
    print(f"\n{'=' * 60}")
    print(f"[IMPORT] 匯入事故資料: {os.path.basename(filepath)}")
    print(f"{'=' * 60}")

    df = pd.read_excel(filepath)
    print(f"   讀取 {len(df)} 筆資料")

    stats = {"total": len(df), "new": 0, "skipped": 0, "errors": 0}

    for idx, row in df.iterrows():
        try:
            case_id = str(row.get("案件編號", "")).strip()
            if not case_id:
                stats["errors"] += 1
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

            if stats["new"] % 100 == 0:
                db.commit()
                print(f"   已匯入 {stats['new']} 筆...")

        except Exception as e:
            stats["errors"] += 1
            if stats["errors"] <= 5:
                print(f"   [WARN] 第 {idx + 1} 筆錯誤: {e}")

    db.commit()
    print(
        f"\n   ✅ 完成: 新增 {stats['new']}, 略過(重複) {stats['skipped']}, 錯誤 {stats['errors']}"
    )

    return stats


def import_tickets(filepath: str, db: Session, batch_id: str) -> Dict:
    """匯入舉發案件資料（支援去重）"""
    print(f"\n{'=' * 60}")
    print(f"[IMPORT] 匯入舉發資料: {os.path.basename(filepath)}")
    print(f"{'=' * 60}")

    df = pd.read_excel(filepath)
    print(f"   讀取 {len(df)} 筆資料")

    stats = {"total": len(df), "new": 0, "skipped": 0, "errors": 0}
    topic_counts = {"dui": 0, "red_light": 0, "dangerous": 0}

    for idx, row in df.iterrows():
        try:
            ticket_number = str(row.get("舉發單號", "")).strip()
            if not ticket_number:
                stats["errors"] += 1
                continue

            # 去重檢查
            existing = (
                db.query(Ticket).filter(Ticket.ticket_number == ticket_number).first()
            )
            if existing:
                stats["skipped"] += 1
                continue

            # 解析時間
            time_str = row.get("違規時間(出)") or row.get("建檔時間")
            violation_dt = parse_roc_datetime(time_str)
            if not violation_dt:
                stats["errors"] += 1
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

            if stats["new"] % 100 == 0:
                db.commit()
                print(f"   已匯入 {stats['new']} 筆...")

        except Exception as e:
            stats["errors"] += 1
            if stats["errors"] <= 5:
                print(f"   [WARN] 第 {idx + 1} 筆錯誤: {e}")

    db.commit()
    print(
        f"\n   ✅ 完成: 新增 {stats['new']}, 略過(重複) {stats['skipped']}, 錯誤 {stats['errors']}"
    )
    print(
        f"   📊 主題: 🍺酒駕 {topic_counts['dui']} | 🚦闘紅燈 {topic_counts['red_light']} | ⚡危駕 {topic_counts['dangerous']}"
    )

    return stats


def init_topics(db: Session):
    """初始化主題定義"""
    topics = [
        Topic(
            topic_code="DUI",
            topic_name="酒駕精準打擊",
            priority=1,
            icon_emoji="🍺",
            color_hex="#E89A9A",
            description="酒後駕車防制",
        ),
        Topic(
            topic_code="RED_LIGHT",
            topic_name="闘紅燈防制",
            priority=2,
            icon_emoji="🚦",
            color_hex="#FFB74D",
            description="路口號誌違規",
        ),
        Topic(
            topic_code="DANGEROUS_DRIVING",
            topic_name="危險駕駛防制",
            priority=3,
            icon_emoji="⚡",
            color_hex="#64B5F6",
            description="超速與危險駕駛",
        ),
    ]

    for topic in topics:
        existing = db.query(Topic).filter(Topic.topic_code == topic.topic_code).first()
        if not existing:
            db.add(topic)

    db.commit()
    print("[OK] 主題定義初始化完成")


# ============================================
# 主程式
# ============================================


def main():
    parser = argparse.ArgumentParser(description="精準執法資料匯入工具 v2.0")
    parser.add_argument("--crash", type=str, help="事故 Excel 檔案路徑")
    parser.add_argument("--ticket", type=str, help="舉發 Excel 檔案路徑")
    parser.add_argument("--init", action="store_true", help="初始化資料庫")

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("精準執法系統 - 資料匯入工具 v2.0")
    print("=" * 60)

    # 確保資料目錄存在
    db_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
    )
    os.makedirs(db_dir, exist_ok=True)

    # 創建表格
    if args.init or args.crash or args.ticket:
        print("[CHECK] 檢查資料庫結構...")
        Base.metadata.create_all(bind=engine)
        print("[OK] 資料表就緒")

    db = SessionLocal()

    try:
        init_topics(db)

        batch_id = f"IMPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"\n[BATCH] 匯入批次: {batch_id}")

        if args.crash:
            if os.path.exists(args.crash):
                import_crashes(args.crash, db, batch_id)
            else:
                print(f"[ERROR] 找不到檔案: {args.crash}")

        if args.ticket:
            if os.path.exists(args.ticket):
                import_tickets(args.ticket, db, batch_id)
            else:
                print(f"[ERROR] 找不到檔案: {args.ticket}")

        # 顯示統計
        print("\n" + "=" * 60)
        print("[STATS] 資料庫統計")
        print("=" * 60)

        crash_count = db.query(Crash).count()
        ticket_count = db.query(Ticket).count()
        dui_count = db.query(Ticket).filter(Ticket.topic_dui == True).count()
        red_count = db.query(Ticket).filter(Ticket.topic_red_light == True).count()
        danger_count = db.query(Ticket).filter(Ticket.topic_dangerous == True).count()
        elderly_count = db.query(Ticket).filter(Ticket.is_elderly == True).count()

        print(f"   事故總數: {crash_count}")
        print(f"   舉發總數: {ticket_count}")
        print(f"     - 酒駕: {dui_count}")
        print(f"     - 闘紅燈: {red_count}")
        print(f"     - 危險駕駛: {danger_count}")
        print(f"     - 高齡者: {elderly_count}")

        # 年份範圍
        if ticket_count > 0:
            min_year = db.query(Ticket.year).order_by(Ticket.year.asc()).first()[0]
            max_year = db.query(Ticket.year).order_by(Ticket.year.desc()).first()[0]
            print(f"   資料年份: {min_year} ~ {max_year}")

    finally:
        db.close()

    print("\n[OK] 完成！")


if __name__ == "__main__":
    main()
