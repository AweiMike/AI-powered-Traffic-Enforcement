from datetime import date, datetime, timedelta
import calendar
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case, desc
from app.models.core import Crash, Ticket
from app.schemas.report import (
    ReportSummary, ReportPeriod, StatComparison, 
    MonthlyTrend, HotspotItem
)

class AnalyticsEngine:
    def __init__(self, db: Session):
        self.db = db

    def generate_report_summary(self, year: int, month: int) -> ReportSummary:
        """
        生成指定年月的報告摘要數據
        """
        # 1. 決定日期範圍
        _, last_day = calendar.monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)
        
        # 去年同期
        last_year = year - 1
        last_start_date = date(last_year, month, 1)
        _, last_yr_last_day = calendar.monthrange(last_year, month)
        last_end_date = date(last_year, month, last_yr_last_day)

        # 2. 總體指標 (Overall Stats)
        overall_stats = self._get_overall_stats(year, month, last_year)

        # 3. 趨勢數據 (Trends) - 過去 6 個月
        trends = self._get_monthly_trends(year, month, months=6)

        # 4. 熱點分析 (Hotspots) - 前 5 名
        accident_hotspots = self._get_accident_hotspots(start_date, end_date, top_n=5)
        violation_hotspots = self._get_violation_hotspots(start_date, end_date, top_n=5)

        # 5. 重點關注項目 (待實作，先留空)
        focus_districts = [] 
        focus_causes = []

        return ReportSummary(
            period=ReportPeriod(
                year=year,
                month=month,
                start_date=start_date,
                end_date=end_date
            ),
            overall_stats=overall_stats,
            trends=trends,
            accident_hotspots=accident_hotspots,
            violation_hotspots=violation_hotspots,
            focus_districts=focus_districts,
            focus_causes=focus_causes
        )

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
