"""共用：判定一筆舉發是否為「毒品駕駛」案件。

背景
====

道路交通管理處罰條例 §35 同時規範酒駕與毒駕：
- §35 第1項第1款：酒精濃度超標        → 法條代碼 3501 01 xxxx
- §35 第1項第2款：吸食毒品、迷幻藥等   → 法條代碼 3501 02 xxxx
- §35 第4項：拒絕接受測試之檢定        → 法條代碼 3504 0? xxxx
              (3504 01 = 酒測拒檢、3504 02 = 毒品拒檢)

因此「酒駕」與「毒駕」在法條代碼上是可精確區分的：
代碼第 5-6 位 = '01' → 酒精；'02' → 毒品。

資料現況（2026-05-05 實測）
==========================
- 毒駕舉發 12 件（全部有 GPS 座標），時間範圍 2025-09 ~ 2026-05
- topic_dui = True 共 257 件，其中 12 件其實是毒品（被誤計入酒駕）
  → 純酒精應為 245 件

事故側資料限制
==============
EIS 事故調查表「飲酒情形代碼」(32.) 只記錄酒精，**沒有毒品專屬欄位**。
Crash.cause 僅有「患病或服用藥物(疲勞)駕駛」這類籠統描述（混合合法藥物+疲勞），
無法精確識別毒駕。

因此毒駕分析**只做取締（Ticket）側**，事故側資料受限，UI 需明確標示。

判定方式
========
毒駕識別（任一成立）：
A. violation_code 開頭 '350102' → §35 I-2 吸食毒品
B. violation_code 開頭 '350402' → §35 IV 毒品拒檢
C. violation_name 含「吸食毒品」 → 保險信號（涵蓋 §35 肇事致傷亡含毒品的條款）

修改影響範圍
============
- backend/app/api/enforcement.py /drug（新增）
- backend/app/api/recommendations.py /drug/hotspots、/drug/peak-times（新增）
- backend/app/api/recommendations.py /map/points（加 is_drug 標記）
- 酒駕查詢一律加 AND NOT drug_drive_filter() 以排除毒駕污染
"""
from sqlalchemy import or_, and_, not_

from app.models.core import Ticket


# violation_name 中代表肇事/傷亡的關鍵字（與 dui_crash 共用概念）
DRUG_CRASH_NAME_KEYWORDS = [
    '肇事',
    '致人',
    '重傷',
    '致死',
    '致傷',
    '死亡',
]


def drug_drive_filter():
    """SQL expression: True 表示「毒品駕駛」案件。

    用法條代碼精確識別（不依賴 topic_dui，因毒品法條本身即毒駕）：
    - 350102 = §35 I-2 吸食毒品
    - 350402 = §35 IV 毒品拒檢
    - violation_name 含「吸食毒品」（保險，涵蓋肇事致傷亡含毒品條款）

    範例:
        db.query(Ticket).filter(drug_drive_filter())
    """
    return or_(
        Ticket.violation_code.like('350102%'),
        Ticket.violation_code.like('350402%'),
        Ticket.violation_name.like('%吸食毒品%'),
    )


def drug_crash_filter():
    """SQL expression: True 表示「毒駕肇事」案件。

    必須與 drug_drive_filter() 同時使用：
        db.query(Ticket).filter(drug_drive_filter(), drug_crash_filter())

    判定：violation_name 含肇事/致人/重傷等加重情節關鍵字。
    （毒駕在事故側無 ground truth，只能靠舉發單條款描述判斷是否肇事）
    """
    keyword_clauses = [Ticket.violation_name.like(f'%{kw}%')
                       for kw in DRUG_CRASH_NAME_KEYWORDS]
    return or_(*keyword_clauses)


def not_drug_filter():
    """SQL expression: True 表示「非毒駕」。

    用於酒駕查詢排除毒駕污染：
        db.query(Ticket).filter(
            Ticket.topic_dui == True,
            not_drug_filter(),   # 排除 §35 I-2 / IV 毒品案件
        )
    """
    return not_(drug_drive_filter())
