"""共用：判定一筆酒駕舉發是否為「酒駕肇事」案件。

背景與資料品質
================

派出所同仁在登錄違規時對 enforcement_subtype 的標註存在系統性偏差：

1. 部分酒駕肇事案件被勾選為「攔舉-一般」而非「攔舉-肇事」
   （資料庫實測顯示，含「致人」關鍵字的案件中有 12 件 subtype 為「攔舉-一般」）
2. 微型電動二輪車、腳踏車等慢車類肇事被歸到「攔舉-慢行攤」
3. 事故表 (Crash) 的 A1/A2/A3 嚴重度欄位也被避免填寫（與績效考核相關）

因此單純查 enforcement_subtype = '攔舉-肇事' 會低估真實酒駕肇事數約 44%。

判定方式
========

UNION 兩個獨立信號，任一成立即視為「酒駕肇事」：

A. enforcement_subtype = '攔舉-肇事'  （明確標註）
B. violation_name 含「肇事/致人/重傷/致死/致傷/死亡」等加重情節關鍵字
   （法條描述肇事致傷亡時會出現這些字樣）

實測結果（DUI 案件 226 件中）
- 僅 A：25 件（同仁主動標註但條款未強調肇事）
- 僅 B：12 件（同仁迴避標註但條款本身已揭露肇事，最大宗黑數）
- A ∩ B： 2 件（兩條件都符合）
- A ∪ B：39 件 ← 比現用方法多抓 44%

修改影響範圍
============

凡是計算「酒駕肇事數」「酒駕肇事率」「執法缺口判定」的查詢都應改用此 filter：
- backend/app/api/enforcement.py /dui
- backend/app/api/recommendations.py /accidents/hotspots
- backend/app/api/recommendations.py /accidents/peak-times
- 未來若做酒駕風險預測模組亦同
"""
from sqlalchemy import or_

from app.models.core import Ticket


# violation_name 中代表肇事/傷亡的關鍵字（任一出現即視為肇事案件）
DUI_CRASH_NAME_KEYWORDS = [
    '肇事',  # 條款明文「肇事」
    '致人',  # 「致人受傷」「致人死亡」「致人重傷」
    '重傷',  # 「致重傷」
    '致死',
    '致傷',
    '死亡',
]


def dui_crash_filter():
    """SQL expression: True 表示「酒駕肇事」案件。

    必須與 Ticket.topic_dui == True 同時使用（此 filter 不檢查是否為酒駕，
    僅判斷「在已是酒駕的前提下，是否為肇事」）。

    範例:
        db.query(Ticket).filter(
            Ticket.topic_dui == True,
            dui_crash_filter(),
        )
    """
    keyword_clauses = [Ticket.violation_name.like(f'%{kw}%')
                       for kw in DUI_CRASH_NAME_KEYWORDS]
    return or_(
        Ticket.enforcement_subtype == '攔舉-肇事',
        *keyword_clauses,
    )


def dui_refusal_filter():
    """SQL expression: True 表示「拒檢/拒測」案件。

    含 2 種樣態（道交§35 第 4 項衍生條款）：
    - 拒絕接受酒精濃度測試之檢定（已停車但拒絕吹氣）
    - 行經酒測檢定處不依指示停車接受稽查（直接逃逸）

    包含汽機車與慢車（微電車/腳踏車）的拒檢案件。

    Why:
    用戶 2026-04-28 指出：酒駕罰則越來越重，預期駕駛逃避酒測案件會增加，
    應獨立追蹤。實測 226 件 DUI 中有 13 件拒檢（5.7%）。

    這類案件特殊性：
    - 駕駛規避酒測（很可能本身就是酒駕）
    - 罰鍰跟拒測同等嚴厲（18 萬 + 吊照 3 年）
    - 是執法成效的「反指標」（規避成功的潛在酒駕）

    必須與 topic_dui == True 同時使用。
    """
    return or_(
        Ticket.violation_name.like('%拒絕%'),
        Ticket.violation_name.like('%不依指示停車接受稽查%'),
    )
