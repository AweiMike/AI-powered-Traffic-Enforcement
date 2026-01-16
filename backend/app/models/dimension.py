"""
維度表模型（無個資）
"""
from sqlalchemy import Column, Integer, String, Float

from app.database import Base


class Site(Base):
    """
    執法點位維度表（聚合點位，無個資）

    說明：
    - 將相近的違規/事故地點聚合成執法點位
    - 僅保留路口/路段名稱，無門牌號
    - 用於 Top 5 推薦及地圖展示
    """
    __tablename__ = "dim_site"

    id = Column(Integer, primary_key=True)

    # 點位名稱（無個資）
    site_name = Column(String(200), nullable=False, index=True)
    # 例如："中正路與中山路路口"、"中正路（近公園）"

    # 行政區
    district = Column(String(50), index=True)
    # 例如："新化區"

    # 地點描述（無門牌號）
    location_desc = Column(String(500))
    # 例如："中正路與中山路交叉口附近，靠近新化區公所"

    # 座標（聚合中心點）
    latitude = Column(Float)
    longitude = Column(Float)

    # 聚合半徑（公尺）
    cluster_radius = Column(Integer, default=100)
    # 預設100公尺內的案件聚合到此點位

    # 點位類型
    site_type = Column(String(50))
    # 例如："路口"、"路段"、"商圈"、"學區"

    # 備註
    notes = Column(String(500))

    def __repr__(self):
        return f"<Site(id={self.id}, name='{self.site_name}', district='{self.district}')>"


class Unit(Base):
    """
    單位維度表（無個資）

    說明：
    - 舉發單位資訊
    - 用於統計各單位執法成效
    """
    __tablename__ = "dim_unit"

    id = Column(Integer, primary_key=True)

    # 單位代碼
    unit_code = Column(String(50), nullable=False, unique=True, index=True)
    # 例如："A01"、"B02"

    # 單位名稱
    unit_name = Column(String(200), nullable=False)
    # 例如："新化分駐所"、"交通組"

    # 單位類型
    unit_type = Column(String(50))
    # 例如："分駐所"、"派出所"、"交通組"

    # 轄區
    district = Column(String(50), index=True)

    # 是否啟用
    is_active = Column(Integer, default=1)

    def __repr__(self):
        return f"<Unit(code='{self.unit_code}', name='{self.unit_name}')>"


class Shift(Base):
    """
    班別維度表（12班制）

    說明：
    - 定義12個班別的時間範圍
    - 用於班別分析與勤務建議
    """
    __tablename__ = "dim_shift"

    id = Column(Integer, primary_key=True)

    # 班別代碼 (01-12)
    shift_id = Column(String(2), nullable=False, unique=True, index=True)

    # 班別編號 (1-12)
    shift_number = Column(Integer, nullable=False)

    # 開始時間（24小時制）
    start_hour = Column(Integer, nullable=False)

    # 結束時間（24小時制）
    end_hour = Column(Integer, nullable=False)

    # 時間範圍描述
    time_range = Column(String(50))
    # 例如："00:00-02:00"

    # 時段特性
    period_name = Column(String(50))
    # 例如："深夜"、"清晨"、"上午"、"下午"、"傍晚"、"夜間"

    # 備註
    notes = Column(String(200))

    def __repr__(self):
        return f"<Shift(id='{self.shift_id}', range='{self.time_range}')>"


class ViolationCode(Base):
    """
    違規條款維度表

    說明：
    - 違規條款代碼與名稱對照
    - 用於違規分類與主題識別
    """
    __tablename__ = "dim_violation_code"

    id = Column(Integer, primary_key=True)

    # 違規條款代碼
    violation_code = Column(String(50), nullable=False, unique=True, index=True)
    # 例如："3501011010"

    # 違規條款名稱
    violation_name = Column(String(200), nullable=False)
    # 例如："酒後駕車，吐氣所含酒精濃度達每公升0.25毫克以上"

    # 法條
    law_article = Column(String(100))
    # 例如："道路交通管理處罰條例第35條第1項第1款"

    # 主題標籤
    topic_dui = Column(Integer, default=0, index=True)
    topic_red_light = Column(Integer, default=0, index=True)
    topic_dangerous = Column(Integer, default=0, index=True)

    # 罰鍰金額（統計用）
    fine_min = Column(Integer)
    fine_max = Column(Integer)

    # 是否記點
    demerit_points = Column(Integer, default=0)

    # 是否吊扣/吊銷
    suspension_type = Column(String(50))
    # "吊扣"、"吊銷"、null

    def __repr__(self):
        return f"<ViolationCode(code='{self.violation_code}', name='{self.violation_name[:20]}...')>"


# 初始化班別資料的函數
def init_shift_data(db):
    """
    初始化12班別資料

    僅在首次建立資料庫時執行
    """
    shifts_data = [
        {"shift_id": "01", "shift_number": 1, "start_hour": 0, "end_hour": 2, "time_range": "00:00-02:00", "period_name": "深夜"},
        {"shift_id": "02", "shift_number": 2, "start_hour": 2, "end_hour": 4, "time_range": "02:00-04:00", "period_name": "深夜"},
        {"shift_id": "03", "shift_number": 3, "start_hour": 4, "end_hour": 6, "time_range": "04:00-06:00", "period_name": "清晨"},
        {"shift_id": "04", "shift_number": 4, "start_hour": 6, "end_hour": 8, "time_range": "06:00-08:00", "period_name": "清晨"},
        {"shift_id": "05", "shift_number": 5, "start_hour": 8, "end_hour": 10, "time_range": "08:00-10:00", "period_name": "上午"},
        {"shift_id": "06", "shift_number": 6, "start_hour": 10, "end_hour": 12, "time_range": "10:00-12:00", "period_name": "上午"},
        {"shift_id": "07", "shift_number": 7, "start_hour": 12, "end_hour": 14, "time_range": "12:00-14:00", "period_name": "下午"},
        {"shift_id": "08", "shift_number": 8, "start_hour": 14, "end_hour": 16, "time_range": "14:00-16:00", "period_name": "下午"},
        {"shift_id": "09", "shift_number": 9, "start_hour": 16, "end_hour": 18, "time_range": "16:00-18:00", "period_name": "傍晚"},
        {"shift_id": "10", "shift_number": 10, "start_hour": 18, "end_hour": 20, "time_range": "18:00-20:00", "period_name": "傍晚"},
        {"shift_id": "11", "shift_number": 11, "start_hour": 20, "end_hour": 22, "time_range": "20:00-22:00", "period_name": "夜間"},
        {"shift_id": "12", "shift_number": 12, "start_hour": 22, "end_hour": 24, "time_range": "22:00-00:00", "period_name": "夜間"},
    ]

    # 檢查是否已有資料
    existing_count = db.query(Shift).count()
    if existing_count > 0:
        print(f"⚠️  班別資料已存在 ({existing_count} 筆)，跳過初始化")
        return

    # 批次新增
    for shift_data in shifts_data:
        shift = Shift(**shift_data)
        db.add(shift)

    db.commit()
    print(f"✅ 班別資料初始化完成 (12 筆)")
