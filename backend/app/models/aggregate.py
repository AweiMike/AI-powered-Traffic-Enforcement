"""
聚合統計表模型（預先計算，提升查詢效能）
"""
from sqlalchemy import Column, Integer, String, Float, Date, Index
from app.database import Base


class SiteMetrics(Base):
    """
    點位聚合指標表（無個資，僅統計）

    說明：
    - 預先計算各點位的 VPI/CRI/Score
    - 定期更新（每日或每週）
    - 用於快速查詢 Top 5 推薦
    """
    __tablename__ = "agg_site_metrics"

    id = Column(Integer, primary_key=True)

    # 點位 ID
    site_id = Column(Integer, nullable=False, index=True)

    # 主題代碼
    topic_code = Column(String(50), nullable=False, index=True)
    # "DUI", "RED_LIGHT", "DANGEROUS_DRIVING"

    # 班別（選填）
    shift_id = Column(String(2), index=True)
    # null 表示全時段

    # 統計期間
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    period_days = Column(Integer, nullable=False)

    # 違規統計
    ticket_count = Column(Integer, default=0)
    violation_days = Column(Integer, default=0)  # 有違規的天數

    # 事故統計
    crash_count = Column(Integer, default=0)
    crash_a1_count = Column(Integer, default=0)
    crash_a2_count = Column(Integer, default=0)
    crash_a3_count = Column(Integer, default=0)
    severity_sum = Column(Integer, default=0)  # 嚴重度加總

    # 高齡者統計
    elderly_ticket_count = Column(Integer, default=0)
    elderly_crash_count = Column(Integer, default=0)

    # 計算指標
    vpi = Column(Float, default=0.0, index=True)  # Violation Pressure Index
    cri = Column(Float, default=0.0, index=True)  # Crash Risk Index
    score = Column(Float, default=0.0, index=True)  # 綜合評分

    # 更新時間
    updated_at = Column(Date, nullable=False, index=True)

    # 複合索引
    __table_args__ = (
        Index('idx_site_topic_shift', 'site_id', 'topic_code', 'shift_id'),
        Index('idx_topic_score', 'topic_code', 'score'),
    )

    def __repr__(self):
        return f"<SiteMetrics(site_id={self.site_id}, topic='{self.topic_code}', score={self.score:.2f})>"


class DailyStats(Base):
    """
    每日統計表（無個資，僅統計）

    說明：
    - 每日違規/事故統計
    - 用於趨勢分析與同期比較
    """
    __tablename__ = "agg_daily_stats"

    id = Column(Integer, primary_key=True)

    # 日期
    stat_date = Column(Date, nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)
    day_of_week = Column(Integer)  # 0=Monday, 6=Sunday
    is_holiday = Column(Integer, default=0)

    # 班別
    shift_id = Column(String(2), index=True)

    # 行政區（選填）
    district = Column(String(50), index=True)

    # 違規統計
    total_tickets = Column(Integer, default=0)
    dui_tickets = Column(Integer, default=0)
    red_light_tickets = Column(Integer, default=0)
    dangerous_tickets = Column(Integer, default=0)

    # 事故統計
    total_crashes = Column(Integer, default=0)
    crash_a1 = Column(Integer, default=0)
    crash_a2 = Column(Integer, default=0)
    crash_a3 = Column(Integer, default=0)

    # 高齡者統計
    elderly_tickets = Column(Integer, default=0)
    elderly_crashes = Column(Integer, default=0)

    # 性別統計
    male_tickets = Column(Integer, default=0)
    female_tickets = Column(Integer, default=0)
    unknown_gender_tickets = Column(Integer, default=0)

    # 更新時間
    updated_at = Column(Date, nullable=False)

    # 複合索引
    __table_args__ = (
        Index('idx_date_shift', 'stat_date', 'shift_id'),
        Index('idx_year_month', 'year', 'month'),
    )

    def __repr__(self):
        return f"<DailyStats(date={self.stat_date}, tickets={self.total_tickets}, crashes={self.total_crashes})>"


class MonthlyStats(Base):
    """
    每月統計表（無個資，僅統計）

    說明：
    - 每月聚合統計
    - 用於年度比較與長期趨勢分析
    """
    __tablename__ = "agg_monthly_stats"

    id = Column(Integer, primary_key=True)

    # 年月
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)

    # 行政區（選填）
    district = Column(String(50), index=True)

    # 違規統計
    total_tickets = Column(Integer, default=0)
    dui_tickets = Column(Integer, default=0)
    red_light_tickets = Column(Integer, default=0)
    dangerous_tickets = Column(Integer, default=0)

    # 事故統計
    total_crashes = Column(Integer, default=0)
    crash_a1 = Column(Integer, default=0)
    crash_a2 = Column(Integer, default=0)
    crash_a3 = Column(Integer, default=0)

    # 高齡者統計
    elderly_tickets = Column(Integer, default=0)
    elderly_crashes = Column(Integer, default=0)

    # 去年同期統計（用於快速比較）
    last_year_tickets = Column(Integer, default=0)
    last_year_crashes = Column(Integer, default=0)

    # 變化率
    ticket_change_rate = Column(Float)
    crash_change_rate = Column(Float)

    # 更新時間
    updated_at = Column(Date, nullable=False)

    # 複合索引
    __table_args__ = (
        Index('idx_year_month_unique', 'year', 'month', 'district', unique=True),
    )

    def __repr__(self):
        return f"<MonthlyStats(year={self.year}, month={self.month}, tickets={self.total_tickets})>"


class ShiftStats(Base):
    """
    班別統計表（無個資，僅統計）

    說明：
    - 各班別聚合統計
    - 用於班別分析與勤務規劃
    """
    __tablename__ = "agg_shift_stats"

    id = Column(Integer, primary_key=True)

    # 統計期間
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # 班別
    shift_id = Column(String(2), nullable=False, index=True)

    # 主題（選填）
    topic_code = Column(String(50), index=True)

    # 行政區（選填）
    district = Column(String(50), index=True)

    # 違規統計
    total_tickets = Column(Integer, default=0)

    # 事故統計
    total_crashes = Column(Integer, default=0)
    crash_a1 = Column(Integer, default=0)
    crash_a2 = Column(Integer, default=0)
    crash_a3 = Column(Integer, default=0)

    # 高齡者統計
    elderly_tickets = Column(Integer, default=0)
    elderly_crashes = Column(Integer, default=0)

    # 平均每日數量
    avg_tickets_per_day = Column(Float)
    avg_crashes_per_day = Column(Float)

    # 更新時間
    updated_at = Column(Date, nullable=False)

    # 複合索引
    __table_args__ = (
        Index('idx_shift_topic', 'shift_id', 'topic_code'),
    )

    def __repr__(self):
        return f"<ShiftStats(shift_id='{self.shift_id}', tickets={self.total_tickets}, crashes={self.total_crashes})>"


# 聚合計算函數（示例）
def calculate_site_metrics(db, site_id: int, topic_code: str, shift_id: str = None, days: int = 30):
    """
    計算特定點位的 VPI/CRI/Score

    參數：
    - db: 資料庫 session
    - site_id: 點位 ID
    - topic_code: 主題代碼
    - shift_id: 班別（選填）
    - days: 統計天數

    返回：
    - SiteMetrics 物件
    """
    from datetime import datetime, timedelta
    from sqlalchemy import and_, func
    from app.models.core import Ticket, Crash

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    # 查詢違規統計
    ticket_conditions = [
        Ticket.violation_date >= start_date,
        Ticket.violation_date <= end_date,
        Ticket.site_id == site_id
    ]

    # 主題條件
    if topic_code == "DUI":
        ticket_conditions.append(Ticket.topic_dui == True)
    elif topic_code == "RED_LIGHT":
        ticket_conditions.append(Ticket.topic_red_light == True)
    elif topic_code == "DANGEROUS_DRIVING":
        ticket_conditions.append(Ticket.topic_dangerous == True)

    # 班別條件
    if shift_id:
        ticket_conditions.append(Ticket.shift_id == shift_id)

    ticket_count = db.query(func.count(Ticket.id)).filter(and_(*ticket_conditions)).scalar() or 0

    # 計算有違規的天數
    violation_days = db.query(
        func.count(func.distinct(Ticket.violation_date))
    ).filter(and_(*ticket_conditions)).scalar() or 0

    # 高齡者違規
    elderly_tickets = db.query(func.count(Ticket.id)).filter(
        and_(*ticket_conditions),
        Ticket.is_elderly == True
    ).scalar() or 0

    # 查詢事故統計
    crash_conditions = [
        Crash.occurred_date >= start_date,
        Crash.occurred_date <= end_date,
        Crash.site_id == site_id
    ]

    if shift_id:
        crash_conditions.append(Crash.shift_id == shift_id)

    crash_stats = db.query(
        func.count(Crash.id).label('count'),
        func.sum(Crash.severity_weight).label('severity_sum'),
        func.sum(func.case((Crash.severity == 'A1', 1), else_=0)).label('a1'),
        func.sum(func.case((Crash.severity == 'A2', 1), else_=0)).label('a2'),
        func.sum(func.case((Crash.severity == 'A3', 1), else_=0)).label('a3')
    ).filter(and_(*crash_conditions)).first()

    crash_count = crash_stats.count or 0
    severity_sum = crash_stats.severity_sum or 0
    crash_a1 = crash_stats.a1 or 0
    crash_a2 = crash_stats.a2 or 0
    crash_a3 = crash_stats.a3 or 0

    # 高齡者事故
    elderly_crashes = db.query(func.count(Crash.id)).filter(
        and_(*crash_conditions),
        Crash.is_elderly == True
    ).scalar() or 0

    # 計算指標
    # VPI = 違規數 × 主題權重
    vpi_weights = {"DUI": 10.0, "RED_LIGHT": 2.0, "DANGEROUS_DRIVING": 1.5}
    vpi = ticket_count * vpi_weights.get(topic_code, 1.0)

    # CRI = 事故數 × 平均嚴重度
    cri = 0.0
    if crash_count > 0:
        avg_severity = severity_sum / crash_count
        cri = crash_count * avg_severity

    # Score = α × VPI + β × CRI
    score_weights = {
        "DUI": (0.7, 0.3),
        "RED_LIGHT": (0.6, 0.4),
        "DANGEROUS_DRIVING": (0.5, 0.5)
    }
    alpha, beta = score_weights.get(topic_code, (0.5, 0.5))
    score = alpha * vpi + beta * cri

    # 創建或更新 SiteMetrics
    metrics = SiteMetrics(
        site_id=site_id,
        topic_code=topic_code,
        shift_id=shift_id,
        period_start=start_date,
        period_end=end_date,
        period_days=days,
        ticket_count=ticket_count,
        violation_days=violation_days,
        crash_count=crash_count,
        crash_a1_count=crash_a1,
        crash_a2_count=crash_a2,
        crash_a3_count=crash_a3,
        severity_sum=severity_sum,
        elderly_ticket_count=elderly_tickets,
        elderly_crash_count=elderly_crashes,
        vpi=vpi,
        cri=cri,
        score=score,
        updated_at=datetime.now().date()
    )

    return metrics
