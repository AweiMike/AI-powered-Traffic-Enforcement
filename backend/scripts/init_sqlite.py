"""
SQLite 資料庫初始化腳本
用於創建資料庫表格並匯入初始資料
"""
import sys
from pathlib import Path

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database import engine, SessionLocal, Base, init_db
from app.models.core import Topic, ViolationTypeMap
from app.models.dimension import init_shift_data
from datetime import datetime


def init_topics(db):
    """初始化主題資料"""
    topics_data = [
        {
            "topic_code": "DUI",
            "topic_name": "酒駕精準打擊",
            "priority": 1,
            "icon_emoji": "🍺",
            "color_hex": "#E89A9A",
            "description": "針對酒後駕車進行精準執法與預防",
        },
        {
            "topic_code": "RED_LIGHT",
            "topic_name": "闖紅燈防制",
            "priority": 2,
            "icon_emoji": "🚦",
            "color_hex": "#F4A460",
            "description": "重點路口號誌執法，減少闖紅燈違規",
        },
        {
            "topic_code": "DANGEROUS_DRIVING",
            "topic_name": "危險駕駛防制",
            "priority": 3,
            "icon_emoji": "⚡",
            "color_hex": "#87CEEB",
            "description": "測速及危險駕駛行為取締",
        },
    ]

    # 檢查是否已有資料
    existing_count = db.query(Topic).count()
    if existing_count > 0:
        print(f"[WARN]  主題資料已存在 ({existing_count} 筆)，跳過初始化")
        return

    # 批次新增
    for topic_data in topics_data:
        topic = Topic(**topic_data)
        db.add(topic)

    db.commit()
    print(f"[OK] 主題資料初始化完成 (3 筆)")


def init_violation_type_map(db):
    """初始化違規條款對照表（範例資料）"""
    violation_maps = [
        # 酒駕相關
        {
            "source_code": "35-1-1",
            "source_name": "酒後駕車，吐氣所含酒精濃度達每公升0.25毫克以上",
            "topic_code": "DUI",
            "weight": 5,
            "severity_level": "CRITICAL",
        },
        {
            "source_code": "35-1-2",
            "source_name": "拒絕接受酒精濃度測試檢定",
            "topic_code": "DUI",
            "weight": 5,
            "severity_level": "CRITICAL",
        },
        # 闖紅燈相關
        {
            "source_code": "53-1",
            "source_name": "闖紅燈",
            "topic_code": "RED_LIGHT",
            "weight": 4,
            "severity_level": "HIGH",
        },
        {
            "source_code": "53-2",
            "source_name": "不依號誌指示行駛",
            "topic_code": "RED_LIGHT",
            "weight": 3,
            "severity_level": "MEDIUM",
        },
        # 危險駕駛相關
        {
            "source_code": "40",
            "source_name": "超速行駛",
            "topic_code": "DANGEROUS_DRIVING",
            "weight": 3,
            "severity_level": "MEDIUM",
        },
        {
            "source_code": "43-1",
            "source_name": "蛇行、危險駕駛",
            "topic_code": "DANGEROUS_DRIVING",
            "weight": 5,
            "severity_level": "CRITICAL",
        },
    ]

    # 檢查是否已有資料
    existing_count = db.query(ViolationTypeMap).count()
    if existing_count > 0:
        print(f"[WARN]  違規條款對照資料已存在 ({existing_count} 筆)，跳過初始化")
        return

    # 批次新增
    for violation_map in violation_maps:
        vm = ViolationTypeMap(**violation_map)
        db.add(vm)

    db.commit()
    print(f"[OK] 違規條款對照資料初始化完成 ({len(violation_maps)} 筆)")


def main():
    """主程式"""
    print("=" * 60)
    print("精準執法儀表板系統 - SQLite 資料庫初始化")
    print("=" * 60)
    print()

    # 1. 創建資料目錄
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    print(f"[OK] 資料目錄已創建：{data_dir}")

    # 2. 創建所有表格
    print("\n正在創建資料庫表格...")
    init_db()

    # 3. 初始化基礎資料
    print("\n正在初始化基礎資料...")
    db = SessionLocal()
    try:
        # 初始化班別資料
        init_shift_data(db)

        # 初始化主題資料
        init_topics(db)

        # 初始化違規條款對照
        init_violation_type_map(db)

        print("\n" + "=" * 60)
        print("[OK] 資料庫初始化完成！")
        print("=" * 60)
        print()
        print("[INFO] 資料庫位置：")
        db_path = data_dir / "traffic_enforcement.db"
        print(f"   {db_path}")
        print()
        print("[INFO] 下一步：")
        print("   1. 使用匯入腳本將您的資料匯入資料庫")
        print("   2. 或者先啟動系統測試介面（會顯示空資料）")
        print()
        print("[START] 啟動系統：")
        print("   執行 啟動系統.bat 或")
        print("   cd backend && python app/main.py")
        print()

    except Exception as e:
        print(f"\n[ERROR] 初始化失敗：{e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
