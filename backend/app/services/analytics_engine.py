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
        生成指定年月的報告摘要數據（Wave 7：擴充資料集）
        """
        # 1. 決定日期範圍
        _, last_day = calendar.monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)

        last_year = year - 1
        _, last_yr_last_day = calendar.monthrange(last_year, month)
        last_start_date = date(last_year, month, 1)
        last_end_date = date(last_year, month, last_yr_last_day)

        # 2. 總體指標
        overall_stats = self._get_overall_stats(year, month, last_year)

        # 3. 主題分類（酒駕/紅燈/危駕）
        topics = self._get_topic_stats(year, month, last_year)

        # 4. 舉發子類型（8 種）
        enforcement_subtypes = self._get_enforcement_subtypes(start_date, end_date)

        # 5. 嚴重度細分
        severity = self._get_severity_breakdown(year, month)

        # 6. 派出所統計（Top 5 by 事故+違規總數）
        unit_stats = self._get_unit_stats(start_date, end_date, top_n=5)

        # 7. 班別分析
        shift_stats = self._get_shift_stats(start_date, end_date)

        # 8. 專區指標
        elderly_crashes = self._count_filtered(Crash, year, month, Crash.is_elderly == True)
        elderly_tickets = self._count_filtered(Ticket, year, month, Ticket.is_elderly == True)
        youth_crashes = self._count_filtered(Crash, year, month, Crash.is_youth == True)
        heavy_vehicle_crashes = self._count_heavy_vehicle_crashes(start_date, end_date)

        # 9. 趨勢
        trends = self._get_monthly_trends(year, month, months=6)

        # 10. 熱點
        accident_hotspots = self._get_accident_hotspots(start_date, end_date, top_n=5)
        violation_hotspots = self._get_violation_hotspots(start_date, end_date, top_n=5)

        # 11. 自動偵測重點關注
        focus_districts = self._detect_focus_districts(start_date, end_date, last_start_date, last_end_date)
        focus_causes = self._detect_focus_causes(topics, severity)

        return ReportSummary(
            period=ReportPeriod(year=year, month=month, start_date=start_date, end_date=end_date),
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

    # ========================================
    # Helper queries（新增）
    # ========================================

    def _count_filtered(self, model, year: int, month: int, extra_filter) -> int:
        """通用：特定模型 + 年月 + 額外條件的計數"""
        return (
            self.db.query(func.count(model.id))
            .filter(and_(model.year == year, model.month == month))
            .filter(extra_filter)
            .scalar() or 0
        )

    def _get_topic_stats(self, year: int, month: int, last_year: int) -> dict:
        """酒駕 / 闖紅燈 / 危駕 分類含去年同期比較"""
        def calc(curr: int, last: int) -> dict:
            change = curr - last
            pct = round((change / last * 100), 1) if last > 0 else 0
            return {"current": curr, "last_year": last, "change": change, "change_pct": pct}

        def topic_count(yr: int, m: int, filter_expr) -> int:
            return (
                self.db.query(func.count(Ticket.id))
                .filter(and_(Ticket.year == yr, Ticket.month == m))
                .filter(filter_expr)
                .scalar() or 0
            )

        return {
            "dui": StatComparison(**calc(
                topic_count(year, month, Ticket.topic_dui == True),
                topic_count(last_year, month, Ticket.topic_dui == True),
            )),
            "red_light": StatComparison(**calc(
                topic_count(year, month, Ticket.topic_red_light == True),
                topic_count(last_year, month, Ticket.topic_red_light == True),
            )),
            "dangerous": StatComparison(**calc(
                topic_count(year, month, Ticket.topic_dangerous == True),
                topic_count(last_year, month, Ticket.topic_dangerous == True),
            )),
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
        """12 班制統計"""
        result = []
        for shift_num in range(1, 13):
            sid = f"{shift_num:02d}"
            accidents = (
                self.db.query(func.count(Crash.id))
                .filter(
                    Crash.occurred_date >= start_date,
                    Crash.occurred_date <= end_date,
                    Crash.shift_id == sid,
                )
                .scalar() or 0
            )
            tickets = (
                self.db.query(func.count(Ticket.id))
                .filter(
                    Ticket.violation_date >= start_date,
                    Ticket.violation_date <= end_date,
                    Ticket.shift_id == sid,
                )
                .scalar() or 0
            )
            if accidents or tickets:
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
        """找出事故增加最多的前 3 個行政區"""
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
        diffs = [(d, curr.get(d, 0) - last.get(d, 0)) for d in set(curr.keys()) | set(last.keys())]
        diffs.sort(key=lambda x: x[1], reverse=True)
        # 只回傳增加（change > 0）的前 3 個
        return [d for d, change in diffs[:3] if change > 0]

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

    def _get_accident_hotspots(self, start_date: date, end_date: date, top_n: int) -> list:
        # 使用與 API 相同的邏輯
        query = self.db.query(
            Crash.district,
            Crash.location_desc,
            func.count(Crash.id).label('total')
        ).filter(
            and_(
                Crash.occurred_date >= start_date,
                Crash.occurred_date <= end_date,
                Crash.location_desc.isnot(None),
                Crash.severity.in_(['A1', 'A2']) # 僅針對 A1/A2 熱點
            )
        ).group_by(
            Crash.district, Crash.location_desc
        ).order_by(
            desc('total')
        ).limit(top_n)
        
        results = query.all()
        
        # 簡單計算去年同期變化 (Optional optimization: if slow, can remove)
        # 這裡簡化為不計算趨勢以加快速度，或者之後再加
        
        hotspots = []
        for i, row in enumerate(results, 1):
            hotspots.append(HotspotItem(
                rank=i,
                location=self._clean_location(row.location_desc, row.district),
                district=self._clean_district(row.district),
                count=row.total,
                trend_pct=None, # 若需要趨勢需額外查詢
                major_cause="A1+A2"
            ))
        return hotspots

    def _get_violation_hotspots(self, start_date: date, end_date: date, top_n: int) -> list:
        query = self.db.query(
            Ticket.district,
            Ticket.location_desc,
            func.count(Ticket.id).label('count')
        ).filter(
            and_(
                Ticket.violation_date >= start_date,
                Ticket.violation_date <= end_date,
                Ticket.location_desc.isnot(None),
                # Ticket.topic_dui == True # 預設取酒駕熱點？還是全部？
                # 報告中可能需要最嚴重的違規熱點，這裡先取整體的
            )
        ).group_by(
            Ticket.district, Ticket.location_desc
        ).order_by(
            desc('count')
        ).limit(top_n)
        
        results = query.all()
        
        hotspots = []
        for i, row in enumerate(results, 1):
            hotspots.append(HotspotItem(
                rank=i,
                location=self._clean_location(row.location_desc, row.district),
                district=self._clean_district(row.district),
                count=row.count,
                major_cause="全部違規"
            ))
        return hotspots
