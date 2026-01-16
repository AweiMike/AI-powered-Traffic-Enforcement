"""
資料庫初始化腳本

功能：
1. 創建所有資料表
2. 初始化基礎資料（班別、違規條款等）
3. 驗證資料庫連線

使用方式：
  python backend/scripts/init_database.py
"""
import sys
from pathlib import Path

# 加入專案根目錄到 Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "backend"))

from sqlalchemy import text
from app.database import engine, SessionLocal, Base
from app.config import settings
from app.models import *  # 導入所有模型
from app.models.dimension import init_shift_data


def check_database_connection():
    """檢查資料庫連線"""
    print("\n" + "=" * 60)
    print("🔌 檢查資料庫連線...")
    print("=" * 60)

    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.scalar()
            print(f"✅ PostgreSQL 連線成功")
            print(f"   版本：{version}")
            return True
    except Exception as e:
        print(f"❌ 資料庫連線失敗：{e}")
        print(f"\n請檢查：")
        print(f"  1. PostgreSQL 是否已啟動")
        print(f"  2. 資料庫 '{settings.DATABASE_NAME}' 是否已創建")
        print(f"  3. 連線設定是否正確：{settings.DATABASE_URL}")
        return False


def check_postgis_extension():
    """檢查並啟用 PostGIS 擴展"""
    print("\n" + "=" * 60)
    print("🗺️  檢查 PostGIS 擴展...")
    print("=" * 60)

    try:
        with engine.connect() as conn:
            # 檢查 PostGIS 是否已安裝
            result = conn.execute(text(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis');"
            ))
            exists = result.scalar()

            if not exists:
                print("⚠️  PostGIS 未安裝，嘗試安裝...")
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                conn.commit()
                print("✅ PostGIS 擴展已啟用")
            else:
                print("✅ PostGIS 擴展已存在")

            # 檢查版本
            result = conn.execute(text("SELECT PostGIS_version();"))
            version = result.scalar()
            print(f"   版本：{version}")
            return True
    except Exception as e:
        print(f"❌ PostGIS 檢查失敗：{e}")
        print(f"\n請手動安裝 PostGIS：")
        print(f"  1. 安裝 PostgreSQL PostGIS 擴展")
        print(f"  2. 在資料庫中執行：CREATE EXTENSION postgis;")
        return False


def create_all_tables():
    """創建所有資料表"""
    print("\n" + "=" * 60)
    print("📊 創建資料表...")
    print("=" * 60)

    try:
        Base.metadata.create_all(bind=engine)
        print("✅ 所有資料表創建完成")

        # 列出已創建的表
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        print(f"\n已創建的資料表（共 {len(tables)} 個）：")
        for table in sorted(tables):
            print(f"  - {table}")

        return True
    except Exception as e:
        print(f"❌ 資料表創建失敗：{e}")
        return False


def init_basic_data():
    """初始化基礎資料"""
    print("\n" + "=" * 60)
    print("🌱 初始化基礎資料...")
    print("=" * 60)

    db = SessionLocal()

    try:
        # 初始化12班別資料
        print("\n📅 初始化班別資料（12班制）...")
        init_shift_data(db)

        # 初始化常見違規條款（示例）
        print("\n📜 初始化違規條款資料...")
        init_violation_codes(db)

        print("\n✅ 基礎資料初始化完成")
        return True
    except Exception as e:
        print(f"❌ 基礎資料初始化失敗：{e}")
        db.rollback()
        return False
    finally:
        db.close()


def init_violation_codes(db):
    """初始化違規條款資料（示例）"""
    from app.models.dimension import ViolationCode

    # 檢查是否已有資料
    existing_count = db.query(ViolationCode).count()
    if existing_count > 0:
        print(f"⚠️  違規條款資料已存在 ({existing_count} 筆)，跳過初始化")
        return

    # 示例違規條款（實際使用時應從完整清單匯入）
    sample_codes = [
        {
            "violation_code": "3501011010",
            "violation_name": "酒後駕車，吐氣所含酒精濃度達每公升0.25毫克以上",
            "law_article": "道路交通管理處罰條例第35條第1項第1款",
            "topic_dui": 1,
            "fine_min": 15000,
            "fine_max": 90000,
            "demerit_points": 0,
            "suspension_type": "吊扣"
        },
        {
            "violation_code": "3504021000",
            "violation_name": "酒後駕車肇事致人死亡",
            "law_article": "道路交通管理處罰條例第35條第4項",
            "topic_dui": 1,
            "fine_min": 90000,
            "fine_max": 90000,
            "demerit_points": 0,
            "suspension_type": "吊銷"
        },
        {
            "violation_code": "53010A1011",
            "violation_name": "闖紅燈（機車）",
            "law_article": "道路交通管理處罰條例第53條第1項",
            "topic_red_light": 1,
            "fine_min": 1800,
            "fine_max": 5400,
            "demerit_points": 0
        },
        {
            "violation_code": "5301011000",
            "violation_name": "不依號誌指示行駛（汽車）",
            "law_article": "道路交通管理處罰條例第53條第1項",
            "topic_red_light": 1,
            "fine_min": 1800,
            "fine_max": 5400,
            "demerit_points": 0
        },
        {
            "violation_code": "40001A1051",
            "violation_name": "超速（機車）20-40 km/h",
            "law_article": "道路交通管理處罰條例第40條",
            "topic_dangerous": 1,
            "fine_min": 1600,
            "fine_max": 2400,
            "demerit_points": 1
        },
        {
            "violation_code": "4000151000",
            "violation_name": "超速（汽車）逾40 km/h",
            "law_article": "道路交通管理處罰條例第40條",
            "topic_dangerous": 1,
            "fine_min": 4000,
            "fine_max": 6000,
            "demerit_points": 2
        },
        {
            "violation_code": "4301011000",
            "violation_name": "危險駕駛",
            "law_article": "道路交通管理處罰條例第43條第1項第1款",
            "topic_dangerous": 1,
            "fine_min": 6000,
            "fine_max": 24000,
            "demerit_points": 3
        }
    ]

    # 批次新增
    for code_data in sample_codes:
        code = ViolationCode(**code_data)
        db.add(code)

    db.commit()
    print(f"✅ 違規條款資料初始化完成 ({len(sample_codes)} 筆示例資料)")
    print("   ⚠️  提醒：請使用完整的違規條款清單更新資料庫")


def verify_initialization():
    """驗證初始化結果"""
    print("\n" + "=" * 60)
    print("✅ 驗證初始化結果...")
    print("=" * 60)

    db = SessionLocal()

    try:
        from app.models.dimension import Shift, ViolationCode

        # 檢查班別資料
        shift_count = db.query(Shift).count()
        print(f"\n✅ 班別資料：{shift_count} 筆")

        if shift_count > 0:
            shifts = db.query(Shift).order_by(Shift.shift_number).all()
            for shift in shifts:
                print(f"   - 班別 {shift.shift_id}: {shift.time_range} ({shift.period_name})")

        # 檢查違規條款資料
        code_count = db.query(ViolationCode).count()
        print(f"\n✅ 違規條款資料：{code_count} 筆")

        if code_count > 0:
            dui_codes = db.query(ViolationCode).filter(ViolationCode.topic_dui == 1).count()
            red_light_codes = db.query(ViolationCode).filter(ViolationCode.topic_red_light == 1).count()
            dangerous_codes = db.query(ViolationCode).filter(ViolationCode.topic_dangerous == 1).count()

            print(f"   - 酒駕相關：{dui_codes} 筆")
            print(f"   - 闖紅燈相關：{red_light_codes} 筆")
            print(f"   - 危險駕駛相關：{dangerous_codes} 筆")

        return True
    except Exception as e:
        print(f"❌ 驗證失敗：{e}")
        return False
    finally:
        db.close()


def main():
    """主程式"""
    print("\n" + "=" * 60)
    print("🚀 精準執法儀表板系統 - 資料庫初始化")
    print("=" * 60)
    print(f"\n專案：{settings.PROJECT_NAME}")
    print(f"版本：{settings.VERSION}")
    print(f"資料庫：{settings.DATABASE_NAME}")
    print(f"個資保護：完全去識別化")

    # 執行初始化步驟
    steps = [
        ("檢查資料庫連線", check_database_connection),
        ("檢查 PostGIS 擴展", check_postgis_extension),
        ("創建資料表", create_all_tables),
        ("初始化基礎資料", init_basic_data),
        ("驗證初始化結果", verify_initialization),
    ]

    success = True
    for step_name, step_func in steps:
        if not step_func():
            print(f"\n❌ 步驟失敗：{step_name}")
            success = False
            break

    # 總結
    print("\n" + "=" * 60)
    if success:
        print("✅ 資料庫初始化完成！")
        print("=" * 60)
        print("\n下一步：")
        print("  1. 使用 import_data.py 匯入 Excel 資料")
        print("  2. 啟動 FastAPI 伺服器：python backend/app/main.py")
        print("  3. 訪問 API 文件：http://localhost:8000/docs")
    else:
        print("❌ 資料庫初始化失敗")
        print("=" * 60)
        print("\n請檢查上述錯誤訊息並修正問題")

    print()


if __name__ == "__main__":
    main()
