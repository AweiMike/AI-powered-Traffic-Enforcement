"""趨勢分析引擎 (Trend Engine)

純資料分析層（以 pandas 計算），不依賴資料庫或特定主題。
給定一段時間序列的計數，產出進階趨勢指標：

- 移動平均 (moving average)        — 平滑短期雜訊，看中期走勢
- 環比 (period-on-period, MoM)     — 最新一期相對前一期的增減幅度
- Z-score 異常偵測 (anomaly)       — 最新一期是否偏離歷史常態
- 專業判讀文字 (interpretation)    — 將上述指標轉成可讀的執法建議語句

設計為跨主題可重用（酒駕 / 毒駕 / 超速 / 事故熱點 …）。
首次套用於 enforcement.py /dui/trend（酒駕週趨勢）。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Optional

import pandas as pd


def _safe_pct(cur: float, prev: float) -> Optional[float]:
    """環比百分比；前期為 0 時無法計算，回傳 None。"""
    if prev == 0:
        return None
    return round((cur - prev) / prev * 100, 1)


def _interpret(*, window: int, latest: float, ma_latest: float,
               mom_pct: Optional[float], z: float, is_anomaly: bool,
               direction: str, metric_name: str, higher_is_worse: bool) -> str:
    """將指標組成一段專業判讀文字（描述句 + 判讀建議句）。"""
    mom_txt = "—" if mom_pct is None else f"{mom_pct:+.1f}%"
    desc = (f"近 {window} 週移動平均 {ma_latest:.1f} {metric_name}，"
            f"最新週 {int(latest)} {metric_name}（環比 {mom_txt}）。")

    if is_anomaly:
        if z > 0:
            verdict = "惡化" if higher_is_worse else "升溫"
            judge = (f"最新週高於歷史均值 {abs(z):.1f} 個標準差，"
                     f"屬統計顯著{verdict}，建議優先投入勤務能量、強化攔檢。")
        else:
            verdict = "改善" if higher_is_worse else "降溫"
            judge = (f"最新週低於歷史均值 {abs(z):.1f} 個標準差，"
                     f"屬統計顯著{verdict}；惟須留意是否為勤務或通報落差所致。")
    else:
        if direction == "up":
            judge = "呈緩升走勢，仍在常態波動範圍內，建議持續觀察。"
        elif direction == "down":
            judge = "呈緩降走勢，仍在常態波動範圍內，建議維持既有勤務強度。"
        else:
            judge = "數值平穩，無顯著波動。"
    return desc + judge


def compute_trend(
    labels: list[str],
    values: list[float],
    *,
    window: int = 4,
    z_threshold: float = 2.0,
    metric_name: str = "件",
    higher_is_worse: bool = False,
) -> dict:
    """計算時間序列的趨勢指標。

    Args:
        labels: 每一期的標籤（如週起日 "6/9"），長度需與 values 相同。
        values: 每一期的計數。
        window: 移動平均視窗（期數），預設 4。
        z_threshold: 異常偵測門檻（標準差倍數），預設 2.0。
        metric_name: 計數單位名稱（判讀文字用），如 "件"。
        higher_is_worse: 數值越高是否代表越糟（影響判讀用詞）。
            酒駕「肇事」序列傳 True；「主動取締 / 總取締」序列傳 False。

    Returns:
        dict：points / 移動平均 / 環比 / 均值 / 標準差 / z-score /
              是否異常 / 走勢方向 / 判讀文字。
    """
    n = len(values)
    if n == 0:
        return {
            "points": [], "window": window, "latest": 0, "ma_latest": 0.0,
            "mom_abs": None, "mom_pct": None, "mean": 0.0, "std": 0.0,
            "zscore": 0.0, "is_anomaly": False, "direction": "flat",
            "interpretation": "尚無資料。",
        }

    s = pd.Series(values, dtype="float64")
    ma = s.rolling(window=window, min_periods=1).mean().round(1)

    points = [
        {"label": labels[i], "value": int(values[i]), "ma": float(ma.iloc[i])}
        for i in range(n)
    ]

    latest = float(values[-1])
    prev = float(values[-2]) if n >= 2 else None
    mom_abs = int(latest - prev) if prev is not None else None
    mom_pct = _safe_pct(latest, prev) if prev is not None else None

    # 異常基準：排除最新一期，避免最新值稀釋歷史均值 / 標準差
    hist = s.iloc[:-1] if n >= 2 else s
    mean = float(hist.mean()) if len(hist) else 0.0
    std = float(hist.std(ddof=0)) if len(hist) > 1 else 0.0
    z = round((latest - mean) / std, 2) if std > 0 else 0.0
    is_anomaly = abs(z) >= z_threshold

    if latest > mean:
        direction = "up"
    elif latest < mean:
        direction = "down"
    else:
        direction = "flat"

    interpretation = _interpret(
        window=window, latest=latest, ma_latest=float(ma.iloc[-1]),
        mom_pct=mom_pct, z=z, is_anomaly=is_anomaly,
        direction=direction, metric_name=metric_name,
        higher_is_worse=higher_is_worse,
    )

    return {
        "points": points,
        "window": window,
        "latest": int(latest),
        "ma_latest": float(ma.iloc[-1]),
        "mom_abs": mom_abs,
        "mom_pct": mom_pct,
        "mean": round(mean, 1),
        "std": round(std, 2),
        "zscore": z,
        "is_anomaly": is_anomaly,
        "direction": direction,
        "interpretation": interpretation,
    }


def _week_start(d: date) -> date:
    """回傳該日期所屬週的週一。"""
    return d - timedelta(days=d.weekday())


#: 去年同期疊圖採 52 週（364 天）位移而非日曆年位移，
#: 目的是保持「星期對齊」（週一還是週一），週分桶才能正確逐週比對。
#: 代價是每年略漂移 1-2 天（365/366 天 vs 364 天），對週趨勢視覺化可接受。
YOY_WEEK_OFFSET = timedelta(weeks=52)


def weekly_trend(
    daily: Iterable[tuple],
    start: date,
    end: date,
    *,
    daily_prev: Optional[Iterable[tuple]] = None,
    window: int = 4,
    z_threshold: float = 2.0,
    metric_name: str = "件",
    higher_is_worse: bool = False,
) -> dict:
    """將每日計數依「週」彙總並計算趨勢（各執法主題趨勢端點共用）。

    Args:
        daily: 可迭代的 (date, total, secondary) tuple。
            total = 該日總取締；secondary = 子集合（如肇事舉發）。
            primary = total - secondary（如主動取締）。無子集的主題 secondary 傳 0。
        start, end: 查詢區間（含），用來產生連續週序（補零）。
        daily_prev: 選填，去年同期（52 週前）的每日計數，格式同 daily
            （僅需 total，secondary 不使用）。提供時每週會多一個 prev_total 欄位
            供前端疊圖比較；省略則不含此欄位。

    Returns:
        {"weeks": [...], "trend": {...}}。weeks 每筆含 week_start/label/total/primary/secondary
        （若提供 daily_prev 則另含 prev_total）。
        會剔除尾端「未完整」的週（空週或進行中的當週），避免最新週 0 件 / 環比 -100%
        / 假性「改善」等誤導。
    """
    daily = list(daily)
    buckets: dict = {}
    for d, total, secondary in daily:
        ws = _week_start(d)
        b = buckets.setdefault(ws, {"total": 0, "secondary": 0})
        b["total"] += total
        b["secondary"] += secondary

    weeks = []
    cur = _week_start(start)
    last = _week_start(end)
    while cur <= last:
        b = buckets.get(cur, {"total": 0, "secondary": 0})
        total = b["total"]
        secondary = b["secondary"]
        weeks.append({
            "week_start": cur.isoformat(),
            "label": f"{cur.month}/{cur.day}",
            "total": total,
            "secondary": secondary,
            "primary": max(0, total - secondary),
        })
        cur += timedelta(days=7)

    # 剔除「未完整」的尾端週：以最後一筆有資料的日期 data_end 為準，
    # 凡 week_end(該週週日) > data_end 的尾端週都移除——涵蓋「尚未發生/未匯入的空週」
    # 與「進行中的當週（資料只到一半）」，避免最新週因不完整而出現
    # 0 件 / 環比 -100% / 假性「改善」等誤導性數值。至少保留 1 週。
    data_end = max((d for d, _t, _s in daily), default=None)
    if data_end is not None:
        while len(weeks) > 1:
            w_start = date.fromisoformat(weeks[-1]["week_start"])
            if w_start + timedelta(days=6) > data_end:
                weeks.pop()
            else:
                break

    if daily_prev is not None:
        prev_buckets: dict = {}
        for d, total, _secondary in daily_prev:
            ws = _week_start(d)
            prev_buckets[ws] = prev_buckets.get(ws, 0) + total
        for w in weeks:
            prev_ws = date.fromisoformat(w["week_start"]) - YOY_WEEK_OFFSET
            w["prev_total"] = prev_buckets.get(prev_ws, 0)

    labels = [w["label"] for w in weeks]
    totals = [w["total"] for w in weeks]
    trend = compute_trend(
        labels, totals,
        window=window, z_threshold=z_threshold,
        metric_name=metric_name, higher_is_worse=higher_is_worse,
    )
    return {"weeks": weeks, "trend": trend}
