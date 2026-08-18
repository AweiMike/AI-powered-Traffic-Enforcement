# -*- coding: utf-8 -*-
"""
事故摘要文本標籤規則引擎（特殊致因挖掘）

⚠️ 設計原則（不可違反）：
    **只存標籤，不存原文。** 現場處理摘要含車牌、姓名、地址等個資，
    原文永遠留在原始 EIS 檔，資料庫只落地「案件 → 標籤」與命中的關鍵詞。

為什麼需要：結構化的「肇因」欄位有系統性盲區。實測全史 5,989 案，摘要標籤標出「動物竄出」85 件，但結構化肇因欄
**僅 4 件（4.7%）被正確歸類**——45 件掛「恍神、緊張、心不在焉分心駕駛」、
11 件掛「未注意車前狀態」、9 件掛「尚未發現肇事因素」。
肇因欄有此選項，問題是**嚴重低登錄**而非完全缺漏。
此類特殊致因（動物、農機、油漬、視線遮蔽）平時只能靠人工翻閱挖掘。

架構：規則引擎為主力（零成本、可稽核、結果穩定），
      小模型僅在未來做消歧（例如「犬」是動物竄出還是載運犬隻）——目前不啟用。
"""
from typing import Dict, List, Tuple

# 標籤定義：(標籤, 必要關鍵詞群, 排除詞)
# 必要關鍵詞群為 OR；排除詞命中則不標記（降低誤報）
TAG_RULES: List[Tuple[str, Tuple[str, ...], Tuple[str, ...]]] = [
    ("動物竄出",
     ("犬只", "犬隻", "狗", "貓", "動物", "蛇", "禽", "牛隻", "野狗", "野貓", "竄出"),
     ("動物醫院", "寵物店", "載運")),
    ("自摔自倒",
     ("自摔", "自行倒地", "自行跌倒", "失控倒地", "打滑倒地", "人車倒地", "自撞"),
     ()),
    ("閃避不及",
     ("閃避不及", "煞車不及", "來不及閃避", "閃避"),
     ()),
    ("逆向行駛",
     ("逆向", "反向行駛", "逆道"),
     ()),
    ("油漬路滑",
     ("油漬", "路滑", "積水", "溢流", "灑落", "泥濘"),
     ()),
    ("農機具",
     ("農用", "耕耘機", "農機", "曳引機", "鐵牛", "搬運車"),
     ()),
    ("視線遮蔽",
     ("視線不良", "視線遮蔽", "遮蔽", "死角", "雜草", "招牌", "違停遮蔽"),
     ()),
    ("路面坑洞",
     ("坑洞", "路面不平", "凹陷", "人孔", "施工"),
     ()),
]


def extract_tags(summary: str) -> List[Dict[str, str]]:
    """
    從單筆摘要抽取標籤。

    回傳 [{"tag": 標籤, "keyword": 命中詞}]；未命中回空列。
    ⚠️ 回傳值刻意不含原文片段——避免個資隨標籤外流。
    """
    if not summary:
        return []
    text = summary.strip()
    if not text:
        return []

    hits: List[Dict[str, str]] = []
    for tag, keys, excludes in TAG_RULES:
        if any(x in text for x in excludes):
            continue
        kw = next((k for k in keys if k in text), None)
        if kw:
            hits.append({"tag": tag, "keyword": kw})
    return hits


def tag_stats(rows: List[Tuple[str, str]]) -> Dict[str, int]:
    """批次統計：rows = [(case_id, summary), ...] → {標籤: 案件數}"""
    counter: Dict[str, int] = {}
    for _cid, summary in rows:
        for h in extract_tags(summary):
            counter[h["tag"]] = counter.get(h["tag"], 0) + 1
    return dict(sorted(counter.items(), key=lambda x: -x[1]))
