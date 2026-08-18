"""
核心資料模型 - 僅保留統計必要欄位，移除所有個資
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Date,
    Boolean,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


# ============================================
# 交通事故核心表（去識別化）
# ============================================
class Crash(Base):
    """
    交通事故案件（去識別化）
    僅保留統計分析必要欄位
    """

    __tablename__ = "core_crash"

    id = Column(Integer, primary_key=True, index=True)

    # === 唯一識別（用於去重，不含個資） ===
    case_id = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="案件編號（如：11401ACC91A0005）",
    )

    # === 匯入批次追蹤 ===
    import_batch_id = Column(String(50), index=True, comment="匯入批次ID")

    # === 時間資訊（必要） ===
    occurred_date = Column(Date, nullable=False, index=True, comment="發生日期")
    occurred_time = Column(DateTime, nullable=False, index=True, comment="發生時間")
    shift_id = Column(String(2), nullable=False, index=True, comment="班別 01-12")

    # === 地點資訊（去識別化） ===
    district = Column(String(50), index=True, comment="行政區（如：新化區）")
    location_desc = Column(String(200), comment="地點描述（路口/路段，不含門牌號）")
    latitude = Column(Float, comment="緯度（用於聚合分析）")
    longitude = Column(Float, comment="經度（用於聚合分析）")
    site_id = Column(Integer, ForeignKey("dim_site.id"), comment="聚合點位ID")

    # === 事故資訊（統計用） ===
    severity = Column(String(2), nullable=False, index=True, comment="A1/A2/A3")
    severity_weight = Column(Integer, nullable=False, comment="嚴重度權重 5/3/1")

    # === 統計用欄位 ===
    year = Column(Integer, nullable=False, index=True, comment="年份")
    month = Column(Integer, nullable=False, index=True, comment="月份")
    day_of_week = Column(Integer, comment="星期幾 0-6")
    is_holiday = Column(Boolean, default=False, comment="是否假日")
    weather = Column(String(50), index=True, comment="天候")
    light = Column(String(50), index=True, comment="光線")

    # === 主題相關（可能無法判定） ===
    suspected_alcohol = Column(
        Boolean, default=False, index=True,
        comment="疑似酒駕（與 is_dui_crash_party 同步維護，沿用舊查詢用）"
    )
    # 飲酒情形代碼（EIS 32. 欄位）4-8 表示有飲酒，其他無或未填
    drinking_code = Column(
        String(2), index=True,
        comment="飲酒情形代碼（駕駛者）：04-08=有飲酒；02=無；01/未填=未調查"
    )
    # 當事者區分子類別代碼（EIS 26. 欄位）H 開頭=行人，B/C 開頭=機車/汽車等
    party_subtype_code = Column(
        String(10), index=True,
        comment="當事者區分子類別代碼（駕駛者）：H開頭=行人、B/C/F=車輛、A=其他"
    )
    # 案件層級 rollup：該案件是否有非行人當事者飲酒
    is_dui_crash_party = Column(
        Boolean, default=False, index=True,
        comment="案件層級判定：任一非行人當事者飲酒情形∈4-8 即為 True（事故表ground truth）"
    )
    cause = Column(String(200), index=True, comment="肇事主要原因")
    party_type = Column(String(50), index=True, comment="當事人車種（如：自用小客車、機車、行人）")

    # === 駕駛人特徵（統計用，去識別化） ===
    driver_age_group = Column(
        String(20), index=True, comment="駕駛年齡組：<18/18-24/25-44/45-64/65+/未知"
    )
    is_elderly = Column(
        Boolean, default=False, index=True, comment="是否為高齡者（65歲以上）"
    )
    driver_gender = Column(String(10), index=True, comment="性別：男/女/未知")

    # === EIS 擴充欄位 ===
    precinct = Column(String(100), index=True, comment="處理分局（如：新化分局）")
    sub_unit = Column(String(100), index=True, comment="所轄單位名稱（如：新化派出所）")
    death_count = Column(Integer, default=0, comment="24小時內死亡人數")
    injury_count = Column(Integer, default=0, comment="受傷人數")
    late_death_count = Column(
        Integer, default=0,
        comment="2-30日內死亡人數（案件分類仍為 A2，僅註記用；死亡統計採24hr口徑不含此數)",
    )

    # === 道路工程分析欄位（Phase 1 擴充，來源=全選條件 EIS 匯出）===
    speed_limit = Column(Integer, index=True, comment="速限 km/h（7.速限-第1當事者）")
    crash_type = Column(String(50), index=True, comment="事故類型及型態（側撞/追撞/路口交岔撞…）")
    road_type = Column(String(50), index=True, comment="道路型態（直路/四岔路/三岔路…）")
    signal_type = Column(String(50), index=True, comment="號誌種類（12-1.）")
    road_lighting = Column(String(50), index=True, comment="道路照明設備（有照明未開啟或故障/有照明且開啟/無照明）")
    route_name = Column(String(50), index=True, comment="公路路線（台20線等，2-2. 國道/省道/縣道/鄉道）")
    route_km = Column(Float, comment="路線公里處（公里+公尺合成，線性分析用）")

    # === 當事者深化欄位（代表駕駛列，與 driver_* 同語意）===
    license_status = Column(String(30), index=True, comment="駕照狀態（有適當之駕照/無照-已達考照年齡…）")
    protective_gear = Column(String(30), comment="保護裝備（安全帽/安全帶使用情形）")
    is_hit_and_run = Column(Boolean, default=False, index=True, comment="是否肇事逃逸（35. 任一當事者=是）")
    delivery_platform = Column(String(50), comment="共享經濟或外送平台（37. 任一當事者非空）")

    # === 路口衝突方向引擎欄位（Wave 28，來源=全選條件 EIS 匯出）===
    side_impact_direction = Column(String(50), comment="側撞時行車方向（EIS 11207新增，衝突型態：對向直行、左轉 等）")
    conflict_action_pair = Column(String(80), comment="順位1×順位2當事者行動狀態配對（如：向前直行中×左轉彎）")
    signal_action = Column(String(20), comment="號誌動作（無號誌/正常/閃光/不正常，12-2欄）")

    # === 事故處理時效／道路恢復效率欄位（Wave 30-1）＋ 停讓標誌（Wave 30-2）===
    response_minutes = Column(Float, comment="發生→到場反應時間（分鐘，0-720 夾制外為 NULL）")
    clearance_minutes = Column(Float, comment="到場→排除處理時長（分鐘，0-1440 夾制外為 NULL；道路恢復效率）")
    has_yield_sign = Column(String(4), comment="有無停讓標誌（Y/N，EIS 11207新增，112年7月後始有值）")

    # === 慢車/微電車分析欄位 ===
    evehicle_type = Column(
        String(50), index=True,
        comment="慢車類型：微型電動二輪車/電動輔助自行車/一般自行車/其他"
    )
    is_youth = Column(
        Boolean, default=False, index=True, comment="是否為青少年（<18歲）"
    )
    is_underage_14 = Column(
        Boolean, default=False, index=True, comment="未滿14歲騎乘微電車"
    )

    # === 行人涉入精確口徑欄位（Wave 31-A，來源=EIS 26.當事者區分(類別) 子類別文字欄）===
    involves_pedestrian = Column(Boolean, default=False, index=True, comment="涉及行人（任一當事者子類含行人/輔助代步器材；口徑精確化 Wave 31）")
    ped_death_count = Column(Integer, default=0, comment="行人當事者 24hr 內死亡數")
    ped_late_death_count = Column(Integer, default=0, comment="行人當事者 2-30 日內死亡數")
    ped_injury_count = Column(Integer, default=0, comment="行人當事者受傷數")

    # === 高齡涉入精確口徑（由 core_crash_party 重算，非代表當事者）===
    # ⚠️ is_elderly 語意自此改為「任一當事者 ≥65 歲」（道安會報口徑）。
    #    舊的代表當事者判定會漏掉被撞的高齡者，實測低估 54%。
    elderly_party_count = Column(Integer, default=0, comment="高齡當事者人數（件≠人，勿相加）")
    elderly_death_count = Column(Integer, default=0, comment="高齡當事者 24hr 內死亡數")
    elderly_late_death_count = Column(Integer, default=0, comment="高齡當事者 2-30 日內死亡數")
    elderly_injury_count = Column(Integer, default=0, comment="高齡當事者受傷數")
    elderly_primary_count = Column(Integer, default=0, comment="高齡當事者為第一當事者之人數")
    elderly_no_fault_count = Column(Integer, default=0, comment="高齡當事者無肇事責任之人數")

    # === 系統欄位 ===
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # === 關聯 ===
    # site = relationship("Site", back_populates="crashes")  # Disabled - not needed for import

    def __repr__(self):
        return f"<Crash(id={self.id}, date={self.occurred_date}, severity={self.severity})>"


# ============================================
# 事故當事者層資料表（去識別化）
# ============================================
class CrashParty(Base):
    """
    事故當事者（每案 1~N 列；EIS 原始即為 per-當事者 row，全史約 12,854 列）

    ⚠️ 為何需要此表：core_crash 是「案件層 rollup」，年齡/車種等欄位取自
    **代表當事者**。當高齡者是被撞的一方時，代表當事者是對造駕駛，
    高齡者就從統計中消失——實測 is_elderly 低估 54%（555 vs 真實 1,211）；
    青少年僅低估 15%（多為自己事故的駕駛），低估幅度的差異本身即為佐證。

    有了本表，「涉及某族群」可用 EXISTS 精確判定，不必再為每個主題新增
    一組 rollup 欄位；並解鎖責任歸屬、年齡分層、對造分析等案件層做不到的維度。

    ⚠️ 個資紅線：EIS 的 16.當事者姓名／18.當事者身分證字號／電話／住址／車牌
    一律不得寫入本表。
    """

    __tablename__ = "core_crash_party"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(50), index=True, nullable=False, comment="對應 core_crash.case_id")
    party_order = Column(Integer, index=True, comment="當事者順位（1=第一當事者，責任歸屬代理變數）")

    # === 人口屬性 ===
    age = Column(Integer, comment="事故發生時年齡")
    age_band = Column(String(10), index=True, comment="5 歲組（65-69/70-74/…/85+）；未滿 65 者粗分組")
    gender = Column(String(10), comment="17.當事者屬(性)別")
    is_elderly = Column(Boolean, default=False, index=True, comment="本人 ≥65 歲")
    is_youth = Column(Boolean, default=False, index=True, comment="本人 12-17 歲")

    # === 當事者屬性 ===
    party_subtype = Column(String(60), comment="26.當事者區分(類別) 子類別原文")
    role = Column(String(10), index=True, comment="駕駛／乘客／行人（由子類別判定）")
    vehicle_group = Column(String(20), index=True, comment="機車／小客車／貨車／慢速載具／其他")
    license_status = Column(String(30), comment="30.駕照狀態")
    protective_gear = Column(String(30), comment="24.保護裝備")

    # === 傷亡（本人，非案件總數）===
    injury = Column(String(20), comment="22.受傷程度原文")
    is_death_24h = Column(Boolean, default=False, comment="24 小時內死亡")
    is_death_late = Column(Boolean, default=False, comment="2-30 日內死亡")
    is_injured = Column(Boolean, default=False, comment="受傷（不含死亡）")

    # === 責任歸屬 ===
    cause = Column(String(120), comment="34.初步分析研判子類別-個別")
    is_primary = Column(Boolean, default=False, index=True, comment="順位=1（主要責任代理變數）")
    no_fault = Column(
        Boolean, default=False, index=True,
        comment="個別肇因＝尚未發現肇事因素（無肇事責任）"
    )

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_crash_party_case_order", "case_id", "party_order"),
        Index("ix_crash_party_elderly", "is_elderly", "case_id"),
    )

    def __repr__(self):
        return f"<CrashParty(case={self.case_id}, order={self.party_order}, age={self.age})>"


# ============================================
# 事故摘要文本標籤（特殊致因挖掘）
# ============================================
class CrashTextTag(Base):
    """
    事故摘要文本標籤

    ⚠️ **只存標籤，不存原文。** 現場處理摘要含車牌、姓名、地址等個資，
    原文永遠留在原始 EIS 檔案，本表僅落地「案件 → 標籤 → 命中關鍵詞」。

    存在理由：結構化「肇因」欄位有系統性盲區——摘要標籤標出「動物竄出」85 件，結構化肇因欄
    **僅 4 件（4.7%）被正確歸類**，45 件掛「恍神、緊張、心不在焉分心駕駛」。
    肇因欄有此選項，問題是嚴重低登錄而非完全缺漏。
    此類特殊致因（動物、農機、油漬、視線遮蔽）平時只能靠人工翻閱挖掘。

    規則定義見 app/utils/text_tags.py。規則引擎為主力（零成本、可稽核、結果穩定）。
    """

    __tablename__ = "core_crash_text_tag"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(50), index=True, nullable=False, comment="對應 core_crash.case_id")
    tag = Column(String(20), index=True, comment="標籤，如 動物竄出／農機具／油漬路滑")
    keyword = Column(String(20), comment="命中之關鍵詞（供人工回查原文用，非原文片段）")
    source = Column(String(12), default="rule", comment="來源：rule（規則引擎）／llm（消歧，暫未啟用）")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_text_tag_case_tag", "case_id", "tag", unique=True),
    )

    def __repr__(self):
        return f"<CrashTextTag(case={self.case_id}, tag={self.tag})>"


# ============================================
# 舉發案件核心表（去識別化）
# ============================================
class Ticket(Base):
    """
    舉發案件（去識別化）
    僅保留統計分析必要欄位，移除車號、駕駛人資料
    """

    __tablename__ = "core_ticket"

    id = Column(Integer, primary_key=True, index=True)

    # === 唯一識別（用於去重，不含個資） ===
    ticket_number = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="舉發單號（如：SZ2792192）",
    )

    # === 匯入批次追蹤 ===
    import_batch_id = Column(String(50), index=True, comment="匯入批次ID")

    # === 時間資訊（必要） ===
    violation_date = Column(Date, nullable=False, index=True, comment="違規日期")
    violation_time = Column(DateTime, nullable=False, index=True, comment="違規時間")
    shift_id = Column(String(2), nullable=False, index=True, comment="班別 01-12")

    # === 地點資訊（去識別化） ===
    district = Column(String(50), index=True, comment="行政區")
    location_desc = Column(String(200), comment="地點描述（不含門牌號）")
    latitude = Column(Float, comment="緯度")
    longitude = Column(Float, comment="經度")
    site_id = Column(Integer, ForeignKey("dim_site.id"), comment="聚合點位ID")

    # === 違規資訊（核心） ===
    violation_code = Column(
        String(50), nullable=False, index=True, comment="違規條款代碼"
    )
    violation_name = Column(String(200), comment="違規條款名稱")

    # === 主題標籤（自動識別） ===
    topic_dui = Column(Boolean, default=False, index=True, comment="酒駕主題")
    topic_red_light = Column(Boolean, default=False, index=True, comment="闖紅燈主題")
    topic_dangerous = Column(Boolean, default=False, index=True, comment="危險駕駛主題")

    # === 權重與評分 ===
    ticket_weight = Column(Integer, default=3, comment="違規權重 1-5")
    severity_level = Column(String(20), comment="LOW/MEDIUM/HIGH/CRITICAL")

    # === 統計用欄位 ===
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)
    day_of_week = Column(Integer, comment="星期幾 0-6")
    is_holiday = Column(Boolean, default=False)

    # === 舉發方式（統計用） ===
    enforcement_type = Column(String(20), index=True, comment="舉發類型：攔停舉發/逕行舉發")
    enforcement_subtype = Column(String(50), comment="舉發子類型：攔舉-一般/逕舉_一般/逕舉_民眾檢舉等")

    # === 舉發單位（統計用） ===
    unit_code = Column(String(50), index=True, comment="舉發單位代碼（如：新化分局）")

    # === 駕駛人特徵（統計用，去識別化） ===
    driver_age = Column(Integer, index=True, comment="駕駛人年齡（原始值）")
    driver_age_group = Column(
        String(20), index=True, comment="駕駛年齡組：<18/18-24/25-44/45-64/65+/未知"
    )
    is_elderly = Column(
        Boolean, default=False, index=True, comment="是否為高齡者（65歲以上）"
    )
    vehicle_type = Column(String(50), index=True, comment="車種（如：汽車、機車）")
    driver_gender = Column(String(10), index=True, comment="性別：男/女/未知")

    # === 慢車/微電車分析欄位 ===
    evehicle_type = Column(
        String(50), index=True,
        comment="慢車類型：微型電動二輪車/電動輔助自行車/一般自行車/其他"
    )
    evehicle_violation = Column(
        String(50), index=True,
        comment="慢車違規態樣：未掛牌/未戴安全帽/雙載/改裝/無照駕駛"
    )
    is_youth = Column(
        Boolean, default=False, index=True, comment="是否為青少年（<18歲）"
    )

    # === 系統欄位 ===
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # === 關聯 ===
    # 注意：Site 類定義在 dimension.py 中

    def __repr__(self):
        return f"<Ticket(id={self.id}, code={self.violation_code}, date={self.violation_date})>"


# ============================================
# 點位指標表（聚合統計） - 已移至 aggregate.py
# Site 類已移至 dimension.py
# ============================================


# ============================================
# 主題定義表
# ============================================
class Topic(Base):
    """
    主題定義表
    """

    __tablename__ = "dim_topic"

    topic_code = Column(
        String(50), primary_key=True, comment="DUI/RED_LIGHT/DANGEROUS_DRIVING"
    )
    topic_name = Column(String(100), nullable=False, comment="中文名稱")
    priority = Column(Integer, nullable=False, comment="優先級 1-5")
    icon_emoji = Column(String(10), comment="🍺🚦⚡")
    color_hex = Column(String(7), comment="#E89A9A")
    description = Column(Text, comment="說明")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Topic(code={self.topic_code}, name={self.topic_name})>"


# ============================================
# 違規條款對照表
# ============================================
class ViolationTypeMap(Base):
    """
    違規條款對照表
    用於自動識別主題
    """

    __tablename__ = "dim_violation_type_map"

    id = Column(Integer, primary_key=True, index=True)

    # === 條款資訊 ===
    source_code = Column(
        String(50), nullable=False, unique=True, index=True, comment="原始條款代碼"
    )
    source_name = Column(Text, comment="原始條款名稱")

    # === 主題映射 ===
    topic_code = Column(
        String(50), ForeignKey("dim_topic.topic_code"), comment="對應主題"
    )
    sub_category = Column(String(100), comment="子分類")

    # === 權重設定 ===
    weight = Column(Integer, default=3, nullable=False, comment="權重 1-5")
    severity_level = Column(String(20), comment="LOW/MEDIUM/HIGH/CRITICAL")

    # === 備註 ===
    notes = Column(Text, comment="備註說明")

    # === 系統欄位 ===
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ViolationTypeMap(code={self.source_code}, topic={self.topic_code})>"


# ============================================
# 統計匯總表 - 已移至 aggregate.py
# MonthlyStats, DailyStats, ShiftStats 等聚合表都在 aggregate.py
# ============================================


# ============================================
# 道路改善措施登記表（Phase 3-A3：成效追蹤用）
# ============================================
class Improvement(Base):
    """道路改善措施登記（成效追蹤 before-after 分析用）"""

    __tablename__ = "core_improvement"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False, comment="措施名稱（如：中山路口增設閃光號誌）")
    measure_type = Column(
        String(50), nullable=False, index=True,
        comment="對策類型：照明改善/號誌增設/標線標誌/實體工程/測速科技執法/其他"
    )
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_m = Column(Integer, default=200, comment="成效評估半徑（公尺）")
    implemented_date = Column(Date, nullable=False, index=True, comment="完工/實施日")
    description = Column(String(300), comment="補充說明（選填）")
    source = Column(String(50), comment="來源：會勘/道安會報/自行改善（選填）")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Improvement(id={self.id}, title={self.title}, date={self.implemented_date})>"


# ============================================
# 系統操作稽核軌跡（Phase 3 C5：機關課責）
# ============================================
class AuditLog(Base):
    """系統操作稽核軌跡（機關課責）"""

    __tablename__ = "core_audit_log"

    id = Column(Integer, primary_key=True, index=True)
    ts = Column(DateTime, default=datetime.utcnow, index=True)
    action = Column(
        String(100), nullable=False, index=True,
        comment="動作：METHOD /path 或 login_success/login_failed",
    )
    detail = Column(String(300), comment="補充（如登入帳號、檔名）")
    status_code = Column(Integer, comment="HTTP 狀態碼")
    actor = Column(String(50), default="admin", comment="admin=已驗證寫入 / anonymous=未驗證")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, ts={self.ts})>"
