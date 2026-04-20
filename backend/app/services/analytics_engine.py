from datetime import date, datetime, timedelta
import calendar
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case, desc, or_
from app.models.core import Crash, Ticket
from app.schemas.report import (
    ReportSummary, ReportPeriod, StatComparison,
    MonthlyTrend, HotspotItem, UnitStat, ShiftStat
)

# 大型車車種關鍵字（與 enforcement.py 保持一致）
HEAVY_VEHICLE_KEYWORDS = ["大貨車", "大客車", "曳引車", "拖車", "遊覽"]


class AnalyticsEngine:
    def __init__(self, db: Session):
        self.db = db

    def generate_report_summary(self, year: int, month: int) -> ReportSummary:
        """
        生成指定年月的報告摘要數據（Wave 7：擴充資料集 + Wave 8：對稱比較）
        """
        # 1. 決定完整月份的日期範圍
        _, last_day = calendar.monthrange(year, month)
        full_start_date = date(year, month, 1)
        full_end_date = date(year, month, last_day)

        # 2. 偵測資料實際涵蓋範圍（避免拿「半個月資料」與「完整 30 天去年同期」比較 → 假象下降）
        data_end = self._get_actual_data_end(full_start_date, full_end_date)
        is_partial = data_end < full_end_date
        # 本期實際使用的結束日期
        start_date = full_start_date
        end_date = data_end if is_partial else full_end_date
        days_covered = (end_date - start_date).days + 1

        # 3. 去年同期調整：若本期是部分資料，去年同期也裁切到相同天數
        last_year = year - 1
        last_start_date = date(last_year, month, 1)
        last_end_date = date(last_year, month, min(days_covered, calendar.monthrange(last_year, month)[1]))

        comparison_note = None
        if is_partial:
            comparison_note = (
                f"⚠ 本期資料僅涵蓋 {start_date} ~ {end_date}（共 {days_covered} 天），"
                f"月份尚未結束或資料尚未匯入到月底。"
                f"為了公平比較，去年同期已自動對齊為 {last_start_date} ~ {last_end_date}（同樣 {days_covered} 天）。"
                f"請在報告中明確提及「本期資料截至 X 日」避免誤導讀者。"
            )

        # 2. 總體指標（含對稱比較）
        overall_stats = self._get_overall_stats_range(start_date, end_date, last_start_date, last_end_date)

        # 3. 主題分類（酒駕/紅燈/危駕，含對稱比較）
        topics = self._get_topic_stats_range(start_date, end_date, last_start_date, last_end_date)

        # 4. 舉發子類型（8 種）
        enforcement_subtypes = self._get_enforcement_subtypes(start_date, end_date)

        # 5. 嚴重度細分（改為 range 版避免資料跨月問題）
        severity = self._get_severity_breakdown_range(start_date, end_date)

        # 6. 派出所統計（Top 5 by 事故+違規總數）
        unit_stats = self._get_unit_stats(start_date, end_date, top_n=5)

        # 7. 班別分析（含 0 值，完整 12 班）
        shift_stats = self._get_shift_stats(start_date, end_date)

        # 8. 專區指標（range 版）
        elderly_crashes = self._count_crash_range(start_date, end_date, Crash.is_elderly == True)
        elderly_tickets = self._count_ticket_range(start_date, end_date, Ticket.is_elderly == True)
        youth_crashes = self._count_crash_range(start_date, end_date, Crash.is_youth == True)
        heavy_vehicle_crashes = self._count_heavy_vehicle_crashes(start_date, end_date)

        # 9. 趨勢
        trends = self._get_monthly_trends(year, month, months=6)

        # 10. 熱點（過濾未知地點）
        accident_hotspots = self._get_accident_hotspots(start_date, end_date, top_n=5)
        violation_hotspots = self._get_violation_hotspots(start_date, end_date, top_n=5)

        # 11. 自動偵測重點關注
        focus_districts = self._detect_focus_districts(start_date, end_date, last_start_date, last_end_date)
        focus_causes = self._detect_focus_causes(topics, severity)

        return ReportSummary(
            period=ReportPeriod(
                year=year, month=month,
                start_date=start_date, end_date=end_date,
                is_partial=is_partial,
                actual_end_date=data_end if is_partial else None,
                days_covered=days_covered,
                comparison_note=comparison_note,
            ),
            overall_stats=overall_stats,
            topics=topics,
            enforcement_subtypes=enforcement_subtypes,
            severity=severity,
            unit_stats=unit_stats,
            shift_stats=shift_stats,
            elderly_crashes=elderly_crashes,
            elderly_tickets=elderly_tickets,
            youth_crashes=youth_crashes,
            heavy_vehicle_crashes=heavy_vehicle_crashes,
            trends=trends,
            accident_hotspots=accident_hotspots,
            violation_hotspots=violation_hotspots,
            focus_districts=focus_districts,
            focus_causes=focus_causes,
        )

    def _get_actual_data_end(self, start_date: date, end_date: date) -> date:
        """
        取得指定區間內「兩種資料都完整涵蓋」的最後一天（Crash 與 Ticket 取較早者）。

        為何用 MIN 而非 MAX：
        - 若 crash 到 4/15、ticket 到 4/9，使用 MAX=4/15 會讓 4/10~15 沒 ticket 資料
          → tickets 在這幾天算 0，造成跟去年同期對比時 tickets 被低估
        - 用 MIN=4/9 確保此區間內兩種資料都有完整紀錄 → 比較最公平
        """
        max_crash = self.db.query(func.max(Crash.occurred_date)).filter(
            Crash.occurred_date >= start_date, Crash.occurred_date <= end_date
        ).scalar()
        max_ticket = self.db.query(func.max(Ticket.violation_date)).filter(
            Ticket.violation_date >= start_date, Ticket.violation_date <= end_date
        ).scalar()
        dates = [d for d in [max_crash, max_ticket] if d is not None]
        if not dates:
            return end_date  # 本期完全沒資料，至少不縮小
        return min(dates)

    # ========================================
    # Helper queries（新增）
    # ========================================

    # ========================================
    # Range-based 計數（Wave 8：對稱比較）
    # ========================================

    def _count_crash_range(self, start: date, end: date, extra_filter=None) -> int:
        q = self.db.query(func.count(Crash.id)).filter(
            Crash.occurred_date >= start, Crash.occurred_date <= end
        )
        if extra_filter is not None:
            q = q.filter(extra_filter)
        return q.scalar() or 0

    def _count_ticket_range(self, start: date, end: date, extra_filter=None) -> int:
        q = self.db.query(func.count(Ticket.id)).filter(
            Ticket.violation_date >= start, Ticket.violation_date <= end
        )
        if extra_filter is not None:
            q = q.filter(extra_filter)
        return q.scalar() or 0

    def _get_overall_stats_range(self, start: date, end: date, last_start: date, last_end: date) -> dict:
        """總體指標（事故/違規/A1+A2/A1）以 date range 做對稱比較"""
        def calc(curr: int, last: int) -> dict:
            change = curr - last
            pct = round((change / last * 100), 1) if last > 0 else 0
            return {"current": curr, "last_year": last, "change": change, "change_pct": pct}

        return {
            "accidents": StatComparison(**calc(
                self._count_crash_range(start, end),
                self._count_crash_range(last_start, last_end),
            )),
            "tickets": StatComparison(**calc(
                self._count_ticket_range(start, end),
                self._count_ticket_range(last_start, last_end),
            )),
            "injuries": StatComparison(**calc(
                self._count_crash_range(start, end, Crash.severity.in_(['A1', 'A2'])),
                self._count_crash_range(last_start, last_end, Crash.severity.in_(['A1', 'A2'])),
            )),
            "deaths": StatComparison(**calc(
                self._count_crash_range(start, end, Crash.severity == 'A1'),
                self._count_crash_range(last_start, last_end, Crash.severity == 'A1'),
            )),
        }

    def _get_topic_stats_range(self, start: date, end: date, last_start: date, last_end: date) -> dict:
        """酒駕 / 闖紅燈 / 危駕 的對稱比較"""
        def calc(curr: int, last: int) -> dict:
            change = curr - last
            pct = round((change / last * 100), 1) if last > 0 else 0
            return {"current": curr, "last_year": last, "change": change, "change_pct": pct}

        return {
            "dui": StatComparison(**calc(
                self._count_ticket_range(start, end, Ticket.topic_dui == True),
                self._count_ticket_range(last_start, last_end, Ticket.topic_dui == True),
            )),
            "red_light": StatComparison(**calc(
                self._count_ticket_range(start, end, Ticket.topic_red_light == True),
                self._count_ticket_range(last_start, last_end, Ticket.topic_red_light == True),
            )),
            "dangerous": StatComparison(**calc(
                self._count_ticket_range(start, end, Ticket.topic_dangerous == True),
                self._count_ticket_range(last_start, last_end, Ticket.topic_dangerous == True),
            )),
        }

    def _get_severity_breakdown_range(self, start: date, end: date) -> dict:
        """A1/A2/A3 事故數（range 版）"""
        return {
            sev: self._count_crash_range(start, end, Crash.severity == sev)
            for sev in ["A1", "A2", "A3"]
        }

    def _get_enforcement_subtypes(self, start_date: date, end_date: date) -> dict:
        """舉發子類型 8 種精確比對"""
        subtypes = [
            "攔舉-一般", "攔舉-肇事", "攔舉-慢行攤",
            "逕舉_一般", "逕舉_民眾檢舉", "逕舉_標示單", "逕舉_拖吊", "逕舉_微電車",
        ]
        result = {}
        for st in subtypes:
            count = (
                self.db.query(func.count(Ticket.id))
                .filter(
                    Ticket.violation_date >= start_date,
                    Ticket.violation_date <= end_date,
                    Ticket.enforcement_subtype == st,
                )
                .scalar() or 0
            )
            result[st] = count
        return result

    def _get_severity_breakdown(self, year: int, month: int) -> dict:
        """A1/A2/A3 事故數"""
        result = {}
        for sev in ["A1", "A2", "A3"]:
            result[sev] = self._count_filtered(Crash, year, month, Crash.severity == sev)
        return result

    def _get_unit_stats(self, start_date: date, end_date: date, top_n: int) -> list:
        """各派出所/單位的事故 + 違規（依總和排序）"""
        # 撈所有有紀錄的單位
        crash_units = dict(
            self.db.query(Crash.sub_unit, func.count(Crash.id))
            .filter(
                Crash.occurred_date >= start_date,
                Crash.occurred_date <= end_date,
                Crash.sub_unit.isnot(None),
            )
            .group_by(Crash.sub_unit)
            .all()
        )
        ticket_units = dict(
            self.db.query(Ticket.unit_code, func.count(Ticket.id))
            .filter(
                Ticket.violation_date >= start_date,
                Ticket.violation_date <= end_date,
                Ticket.unit_code.isnot(None),
            )
            .group_by(Ticket.unit_code)
            .all()
        )
        all_units = set(crash_units.keys()) | set(ticket_units.keys())

        def short_name(unit: str) -> str:
            """移除共同前綴 新化分局，只保留派出所名"""
            return unit.replace("新化分局", "") if unit else unit

        items = [
            UnitStat(
                unit=short_name(u),
                crashes=crash_units.get(u, 0),
                tickets=ticket_units.get(u, 0),
            )
            for u in all_units
        ]
        items.sort(key=lambda x: x.crashes + x.tickets, reverse=True)
        return items[:top_n]

    def _get_shift_stats(self, start_date: date, end_date: date) -> list:
        """
        12 班制統計（全列 0 值也呈現）。
        為何保留 0 值：讓 LLM 看到「某班完全沒事故/違規」也是重要資訊
        （可能代表該時段人力已足、或該時段巡邏空窗）。
        """
        result = []
        for shift_num in range(1, 13):
            sid = f"{shift_num:02d}"
            accidents = self._count_crash_range(start_date, end_date, Crash.shift_id == sid)
            tickets = self._count_ticket_range(start_date, end_date, Ticket.shift_id == sid)
            result.append(ShiftStat(shift_id=sid, accidents=accidents, tickets=tickets))
        return result

    def _count_heavy_vehicle_crashes(self, start_date: date, end_date: date) -> int:
        """大型車涉事的事故數（關鍵字比對 party_type）"""
        filters = [Crash.party_type.like(f"%{kw}%") for kw in HEAVY_VEHICLE_KEYWORDS]
        return (
            self.db.query(func.count(Crash.id))
            .filter(
                Crash.occurred_date >= start_date,
                Crash.occurred_date <= end_date,
                or_(*filters),
            )
            .scalar() or 0
        )

    def _detect_focus_districts(self, start_date, end_date, last_start, last_end) -> list:
        """
        找出事故變化最劇烈的前 3 個行政區（不限增加方向）。
        - 增加 → 需關注（可能是新熱點）
        - 大幅減少 → 也值得注意（改善原因 / 資料缺失？）
        只過濾變化絕對值 ≤ 1 的微幅變化（避免噪音）。
        """
        curr = dict(
            self.db.query(Crash.district, func.count(Crash.id))
            .filter(Crash.occurred_date >= start_date, Crash.occurred_date <= end_date, Crash.district.isnot(None))
            .group_by(Crash.district)
            .all()
        )
        last = dict(
            self.db.query(Crash.district, func.count(Crash.id))
            .filter(Crash.occurred_date >= last_start, Crash.occurred_date <= last_end, Crash.district.isnot(None))
            .group_by(Crash.district)
            .all()
        )

        result = []
        for d in set(curr.keys()) | set(last.keys()):
            c = curr.get(d, 0)
            l = last.get(d, 0)
            change = c - l
            if abs(change) <= 1:
                continue  # 忽略微幅變化
            # 組合有方向性的標籤
            direction = "+" if change > 0 else ""
            result.append((d, change, f"{d}（事故 {c} 件，去年 {l} 件，{direction}{change} 件）"))

        # 依變化絕對值降序
        result.sort(key=lambda x: abs(x[1]), reverse=True)
        return [label for _, _, label in result[:3]]

    def _detect_focus_causes(self, topics: dict, severity: dict) -> list:
        """根據 topics/severity 的變化自動挑出重點關注項"""
        focus = []
        for topic, stat in topics.items():
            if stat.change_pct >= 20 and stat.current > 10:
                display = {"dui": "酒駕", "red_light": "闖紅燈", "dangerous": "危險駕駛"}[topic]
                focus.append(f"{display}顯著增加（{stat.change_pct:+.0f}%）")
            elif stat.change_pct <= -20 and stat.last_year > 10:
                display = {"dui": "酒駕", "red_light": "闖紅燈", "dangerous": "危險駕駛"}[topic]
                focus.append(f"{display}顯著下降（{stat.change_pct:+.0f}%）")

        # A1 死亡事故是特別關注項
        if severity.get("A1", 0) > 0:
            focus.append(f"本月有 {severity['A1']} 件 A1 死亡事故")

        return focus[:5]

    def _get_overall_stats(self, year: int, month: int, last_year: int) -> dict:
        """計算當月與去年同期的總體指標"""
        
        # 定義指標查詢輔助函數
        def get_count(model, yr, m, additional_filter=None):
            q = self.db.query(func.count(model.id)).filter(
                and_(model.year == yr, model.month == m)
            )
            if additional_filter is not None:
                q = q.filter(additional_filter)
            return q.scalar() or 0

        # 事故統計
        curr_crashes = get_count(Crash, year, month)
        last_crashes = get_count(Crash, last_year, month)
        
        # 違規統計
        curr_tickets = get_count(Ticket, year, month)
        last_tickets = get_count(Ticket, last_year, month)
        
        # 受傷/死亡 (A1/A2)
        curr_injuries = get_count(Crash, year, month, Crash.severity.in_(['A1', 'A2']))
        last_injuries = get_count(Crash, last_year, month, Crash.severity.in_(['A1', 'A2']))
        
        # 計算變化率
        def calc_change(curr, last):
            change = curr - last
            pct = round((change / last * 100), 1) if last > 0 else 0
            return {"current": curr, "last_year": last, "change": change, "change_pct": pct}

        return {
            "accidents": StatComparison(**calc_change(curr_crashes, last_crashes)),
            "tickets": StatComparison(**calc_change(curr_tickets, last_tickets)),
            "injuries": StatComparison(**calc_change(curr_injuries, last_injuries)),
            # 暫無死亡欄位，暫用 A1 代替
            "deaths": StatComparison(**calc_change(
                get_count(Crash, year, month, Crash.severity == 'A1'), 
                get_count(Crash, last_year, month, Crash.severity == 'A1')
            ))
        }

    def _get_monthly_trends(self, year: int, month: int, months: int) -> list:
        """獲取過去 N 個月的趨勢"""
        trends = []
        # 計算起始月份
        curr_date = date(year, month, 1)
        
        for i in range(months-1, -1, -1):
            target_date = curr_date - timedelta(days=i*30) # 粗略計算，主要取年月
            y, m = target_date.year, target_date.month
            
            # 修正日期計算誤差，直接用 relativedelta 會更好，但這裡手動處理
            # 簡單回推：從當前月份往前推 i 個月
            temp_y, temp_m = year, month - i
            while temp_m <= 0:
                temp_m += 12
                temp_y -= 1
            
            y, m = temp_y, temp_m
            
            accidents = self.db.query(func.count(Crash.id)).filter(
                and_(Crash.year == y, Crash.month == m)
            ).scalar() or 0
            
            tickets = self.db.query(func.count(Ticket.id)).filter(
                and_(Ticket.year == y, Ticket.month == m)
            ).scalar() or 0
            
            trends.append(MonthlyTrend(
                month=f"{y}-{m:02d}",
                accidents=accidents,
                tickets=tickets
            ))
        return trends

    def _clean_district(self, district: str) -> str:
        if district and district.startswith('市'):
            return district[1:]
        return district or "未知區"

    def _clean_location(self, location: str, district: str) -> str:
        if not location:
            return "未知地點"
        cleaned_dist = self._clean_district(district)
        if cleaned_dist and len(cleaned_dist) >= 2:
            prefix = cleaned_dist[0]
            common_road_chars = ['中', '大', '正', '民', '建', '信', '光', '和', '竹', '北', '南', '東', '西']
            if location.startswith(prefix) and len(location) > 1:
                if location[1] in common_road_chars:
                    return location[1:]
        return location

    # 無意義地點字樣（過濾掉避免熱點排名包含）
    _UNKNOWN_LOCATION_TOKENS = ["未知", "不詳", "其他", ""]

    def _is_meaningful_location(self, loc: str | None) -> bool:
        if not loc or not loc.strip():
            return False
        stripped = loc.strip()
        return not any(tok in stripped for tok in self._UNKNOWN_LOCATION_TOKENS if tok)

    def _get_accident_hotspots(self, start_date: date, end_date: date, top_n: int) -> list:
        """事故熱點（過濾未知/空白地點，僅 A1/A2）"""
        # 多撈幾筆後再過濾（避免過濾後數量不足 top_n）
        query = self.db.query(
            Crash.district,
            Crash.location_desc,
            func.count(Crash.id).label('total')
        ).filter(
            and_(
                Crash.occurred_date >= start_date,
                Crash.occurred_date <= end_date,
                Crash.location_desc.isnot(None),
                Crash.location_desc != "",
                Crash.severity.in_(['A1', 'A2'])
            )
        ).group_by(
            Crash.district, Crash.location_desc
        ).order_by(desc('total')).limit(top_n * 3)

        results = query.all()

        hotspots = []
        for row in results:
            if not self._is_meaningful_location(row.location_desc):
                continue
            hotspots.append(HotspotItem(
                rank=len(hotspots) + 1,
                location=self._clean_location(row.location_desc, row.district),
                district=self._clean_district(row.district),
                count=row.total,
                trend_pct=None,
                major_cause="A1+A2",
            ))
            if len(hotspots) >= top_n:
                break
        return hotspots

    def _get_violation_hotspots(self, start_date: date, end_date: date, top_n: int) -> list:
        """違規熱點（過濾未知/空白地點）"""
        query = self.db.query(
            Ticket.district,
            Ticket.location_desc,
            func.count(Ticket.id).label('count')
        ).filter(
            and_(
                Ticket.violation_date >= start_date,
                Ticket.violation_date <= end_date,
                Ticket.location_desc.isnot(None),
                Ticket.location_desc != "",
            )
        ).group_by(
            Ticket.district, Ticket.location_desc
        ).order_by(desc('count')).limit(top_n * 3)

        results = query.all()

        hotspots = []
        for row in results:
            if not self._is_meaningful_location(row.location_desc):
                continue
            hotspots.append(HotspotItem(
                rank=len(hotspots) + 1,
                location=self._clean_location(row.location_desc, row.district),
                district=self._clean_district(row.district),
                count=row.count,
                major_cause="全部違規",
            ))
            if len(hotspots) >= top_n:
                break
        return hotspots
