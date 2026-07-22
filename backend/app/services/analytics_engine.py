from datetime import date, datetime, timedelta
import calendar
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case, desc, or_
from app.models.core import Crash, Ticket, Improvement
from app.schemas.report import (
    ReportSummary, ReportPeriod, StatComparison,
    MonthlyTrend, HotspotItem, UnitStat, ShiftStat
)
from app.utils.epdo import epdo_sql_sum

# 大型車車種關鍵字（與 enforcement.py 保持一致）
HEAVY_VEHICLE_KEYWORDS = ["大貨車", "大客車", "曳引車", "拖車", "遊覽"]


class AnalyticsEngine:
    def __init__(self, db: Session):
        self.db = db

    def generate_report_summary(
        self,
        year: int = None,
        month: int = None,
        start_date_param: date = None,
        end_date_param: date = None,
    ) -> ReportSummary:
        """
        生成報告摘要數據（Wave 13：支援自訂日期區間）

        參數模式（二擇一）：
        - year + month：完整月份分析（沿用舊邏輯，支援 partial period 自動偵測）
        - start_date_param + end_date_param：自訂任意日期區間（給長官想要特定週/季度/活動期間用）

        若提供 start/end 則優先採用，year/month 僅作為 metadata 顯示用。
        """
        # === 模式判斷：是否為自訂區間 ===
        custom_range = start_date_param is not None and end_date_param is not None

        if custom_range:
            # 自訂區間：直接使用
            start_date = start_date_param
            end_date = end_date_param
            days_covered = (end_date - start_date).days + 1

            # 去年同期：完全對齊（同樣的 起始月日 ~ 結束月日，年份 -1）
            last_start_date = start_date.replace(year=start_date.year - 1)
            try:
                last_end_date = end_date.replace(year=end_date.year - 1)
            except ValueError:
                # 處理 2/29 邊界
                last_end_date = end_date.replace(year=end_date.year - 1, day=28)

            # 自訂區間沒有「完整月」概念，is_partial 改用「資料是否涵蓋到 end_date」判斷
            data_end = self._get_actual_data_end(start_date, end_date)
            is_partial = data_end < end_date
            if is_partial:
                end_date = data_end
                days_covered = (end_date - start_date).days + 1
                # 去年同期也對應裁切
                try:
                    last_end_date = end_date.replace(year=end_date.year - 1)
                except ValueError:
                    last_end_date = end_date.replace(year=end_date.year - 1, day=28)

            # 顯示用 year/month（取 start_date 的年月）
            year = start_date.year
            month = start_date.month

            comparison_note = None
            if is_partial:
                comparison_note = (
                    f"⚠ 自訂區間 {start_date_param} ~ {end_date_param}，但實際資料僅涵蓋 {start_date} ~ {end_date}（共 {days_covered} 天）。"
                    f"為了公平比較，去年同期已自動對齊為 {last_start_date} ~ {last_end_date}（同樣 {days_covered} 天）。"
                    f"請在報告中明確標明資料涵蓋範圍。"
                )
            else:
                comparison_note = (
                    f"📅 自訂區間 {start_date} ~ {end_date}（共 {days_covered} 天），"
                    f"與去年同期 {last_start_date} ~ {last_end_date} 對齊比較。"
                )

        else:
            # === 完整月份模式（原有邏輯）===
            if year is None or month is None:
                raise ValueError("必須提供 year+month 或 start_date+end_date")

            _, last_day = calendar.monthrange(year, month)
            full_start_date = date(year, month, 1)
            full_end_date = date(year, month, last_day)

            data_end = self._get_actual_data_end(full_start_date, full_end_date)
            is_partial = data_end < full_end_date
            start_date = full_start_date
            end_date = data_end if is_partial else full_end_date
            days_covered = (end_date - start_date).days + 1

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

        # 6. 派出所統計（列出所有真實派出所/分駐所，排除交通分隊/交通組/警備隊等統籌單位）
        unit_stats = self._get_unit_stats(start_date, end_date, top_n=None)

        # 7. 班別分析（含 0 值，完整 12 班）
        shift_stats = self._get_shift_stats(start_date, end_date)

        # 8. 專區指標（range 版）
        elderly_crashes = self._count_crash_range(start_date, end_date, Crash.is_elderly == True)
        elderly_tickets = self._count_ticket_range(start_date, end_date, Ticket.is_elderly == True)
        youth_crashes = self._count_crash_range(start_date, end_date, Crash.is_youth == True)
        heavy_vehicle_crashes = self._count_heavy_vehicle_crashes(start_date, end_date)

        # 8.1 行人事故專區
        pedestrian_crashes = self._count_pedestrian_crashes(start_date, end_date)
        pedestrian_elderly_crashes = self._count_pedestrian_crashes(start_date, end_date, Crash.is_elderly == True)
        pedestrian_deaths, pedestrian_injuries = self._sum_pedestrian_casualties(start_date, end_date)

        # 8.1.1 2-30日內死亡人數加總（僅註記用，不動 severity 分類與24hr口徑死亡統計）
        late_deaths = self._sum_late_deaths(start_date, end_date)

        # 8.2 重度超速（40+ km/h）件數
        speeding_heavy_count = self._count_heavy_speeding(start_date, end_date)

        # 9. 趨勢
        trends = self._get_monthly_trends(year, month, months=6)

        # 10. 熱點（過濾未知地點）
        accident_hotspots = self._get_accident_hotspots(start_date, end_date, top_n=5)
        violation_hotspots = self._get_violation_hotspots(start_date, end_date, top_n=5)

        # 10.5 A1 死亡地點（工程改善必要重點）
        a1_locations = self._get_a1_locations(start_date, end_date)

        # 11. 自動偵測重點關注（Wave 8.1：補上整體指標）
        focus_districts = self._detect_focus_districts(start_date, end_date, last_start_date, last_end_date)
        focus_causes = self._detect_focus_causes(topics, severity, overall_stats)

        # 12. Phase 1-3 新資料維度織入（Phase 3-C3：道安會報月報升級）
        #     照明故障／無照／逃逸／風險路線／改善措施成效
        lighting_issues = self._get_lighting_issues(start_date, end_date)
        unlicensed_count = self._get_unlicensed_count(start_date, end_date)
        hit_and_run_count = self._get_hit_and_run_count(start_date, end_date)
        top_route_segments = self._get_top_route_segments(start_date, end_date)
        improvement_effects = self._get_improvement_effects()

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
            pedestrian_crashes=pedestrian_crashes,
            pedestrian_elderly_crashes=pedestrian_elderly_crashes,
            pedestrian_deaths=pedestrian_deaths,
            pedestrian_injuries=pedestrian_injuries,
            late_deaths=late_deaths,
            speeding_heavy_count=speeding_heavy_count,
            trends=trends,
            accident_hotspots=accident_hotspots,
            violation_hotspots=violation_hotspots,
            a1_locations=a1_locations,
            focus_districts=focus_districts,
            focus_causes=focus_causes,
            lighting_issues=lighting_issues,
            unlicensed_count=unlicensed_count,
            hit_and_run_count=hit_and_run_count,
            top_route_segments=top_route_segments,
            improvement_effects=improvement_effects,
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
        """酒駕 / 闖紅燈 / 危駕 / 超速 的對稱比較"""
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
            # 超速：violation_name LIKE '%超速%'（無 topic flag，用字串比對）
            "speeding": StatComparison(**calc(
                self._count_ticket_range(start, end, Ticket.violation_name.like('%超速%')),
                self._count_ticket_range(last_start, last_end, Ticket.violation_name.like('%超速%')),
            )),
        }

    def _count_heavy_speeding(self, start: date, end: date) -> int:
        """計算本期重度超速（40+ km/h）件數。
        從 violation_name 中解析「超速 X 公里」，X >= 41 視為重度。
        """
        import re
        pattern = re.compile(r"超速\s*(\d+)\s*公里")
        rows = self.db.query(Ticket.violation_name).filter(
            Ticket.violation_date >= start,
            Ticket.violation_date <= end,
            Ticket.violation_name.like('%超速%'),
        ).all()
        count = 0
        for (name,) in rows:
            if not name:
                continue
            m = pattern.search(name)
            if m and int(m.group(1)) >= 41:
                count += 1
        return count

    def _count_pedestrian_crashes(self, start: date, end: date, extra_filter=None) -> int:
        """行人涉入事故件數（Wave 31-A：involves_pedestrian 精確口徑，取代舊版
        party_type LIKE/等於 判定——舊版誤把「全案當事者皆人類」當行人事故，
        漏掉「行人被車撞、代表當事者是駕駛」的案件）"""
        q = self.db.query(func.count(Crash.id)).filter(
            Crash.occurred_date >= start,
            Crash.occurred_date <= end,
            Crash.involves_pedestrian == True,
        )
        if extra_filter is not None:
            q = q.filter(extra_filter)
        return q.scalar() or 0

    def _sum_pedestrian_casualties(self, start: date, end: date) -> tuple[int, int]:
        """回傳 (死亡人數, 受傷人數) — 僅行人當事者本身傷亡。

        Wave 31-A：改用 ped_death_count/ped_injury_count（行人當事者本身傷亡），
        取代舊版 Crash.death_count/injury_count（案件總死傷，若同案有非行人
        當事者死傷會高估行人死傷數）。ped_late_death_count（2-30日內死亡）
        比照全站口徑不併入死亡數，僅供未來如需展示時取用。
        """
        rows = self.db.query(Crash.ped_death_count, Crash.ped_injury_count).filter(
            Crash.occurred_date >= start,
            Crash.occurred_date <= end,
            Crash.involves_pedestrian == True,
        ).all()
        deaths = sum(r.ped_death_count or 0 for r in rows)
        injuries = sum(r.ped_injury_count or 0 for r in rows)
        return deaths, injuries

    def _sum_late_deaths(self, start: date, end: date) -> int:
        """2-30日內死亡人數加總（僅註記用；不影響 severity 分類，死亡統計仍採24hr口徑不含此數）"""
        return self.db.query(func.coalesce(func.sum(Crash.late_death_count), 0)).filter(
            Crash.occurred_date >= start,
            Crash.occurred_date <= end,
        ).scalar() or 0

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

    # ========================================
    # 派出所實際業務分組（新化分局 4 管區）
    # ========================================
    # 每個管區由一個主要派出所 + 0~1 個副派出所組成
    # 使用 substring 比對，支援資料庫中各種變體（含前綴「新化分局」等）
    # 注意 𦰡拔 / 那拔 兩種寫法都可能出現
    STATION_GROUPS = [
        {
            "display": "新化派出所（含那拔）",
            "members": ["新化派出所", "那拔派出所", "𦰡拔派出所"],
        },
        {
            "display": "唪口派出所（含知義）",
            "members": ["唪口派出所", "知義派出所"],
        },
        {
            "display": "山上分駐所",
            "members": ["山上分駐所"],
        },
        {
            "display": "左鎮分駐所",
            "members": ["左鎮分駐所", "岡林派出所"],
        },
    ]

    def _classify_unit_to_group(self, unit: str) -> str | None:
        """
        將 DB 中的 sub_unit / unit_code 歸類到 4 個業務管區之一。
        若為統籌單位（交通分隊/交通組/警備隊等）或未知，回傳 None。
        """
        if not unit:
            return None
        for group in self.STATION_GROUPS:
            for member in group["members"]:
                if member in unit:
                    return group["display"]
        return None

    def _get_unit_stats(self, start_date: date, end_date: date, top_n: int | None = None) -> list:
        """
        派出所業務管區統計（新化分局實際檢討結構）：
          1. 新化派出所（含那拔）
          2. 唪口派出所（含知義）
          3. 山上分駐所
          4. 左鎮分駐所（含岡林）

        排除：交通分隊、交通組、警備隊等統籌單位
        （它們不是地理轄區，混入會誤導派出所比較）

        回傳順序：依「事故+違規」總和降序。
        top_n=None 時列出全部 4 個管區。
        """
        # 撈所有單位的 crash / ticket 計數
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

        # 聚合到 4 個管區
        group_crashes: dict[str, int] = {g["display"]: 0 for g in self.STATION_GROUPS}
        group_tickets: dict[str, int] = {g["display"]: 0 for g in self.STATION_GROUPS}

        for unit, count in crash_units.items():
            group = self._classify_unit_to_group(unit)
            if group:
                group_crashes[group] += count

        for unit, count in ticket_units.items():
            group = self._classify_unit_to_group(unit)
            if group:
                group_tickets[group] += count

        # 組裝 UnitStat list（含 enforcement_ratio）
        items = []
        for group in self.STATION_GROUPS:
            c = group_crashes[group["display"]]
            t = group_tickets[group["display"]]
            # 取締比率：每 1 件事故對應幾件取締（衡量執法投入相對事故規模）
            ratio = round(t / c, 2) if c > 0 else None
            items.append(UnitStat(
                unit=group["display"],
                crashes=c,
                tickets=t,
                enforcement_ratio=ratio,
            ))
        items.sort(key=lambda x: x.crashes + x.tickets, reverse=True)

        if top_n is None:
            return items
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

    def _detect_focus_causes(self, topics: dict, severity: dict, overall: dict | None = None) -> list:
        """
        自動挑出 AI 應優先關注的重點項（給 prompt 當 focus hint）
        優先級（由高到低）：
          1. A1 死亡事故 — 任何一件都需關注
          2. 整體事故變化（±10% 以上）— 最關鍵的管理指標
          3. 整體傷亡變化（±15% 以上）— 人命關天
          4. 整體違規取締變化（±20% 以上）— 反映執法力度
          5. 主題分類變化（±20% 以上）— DUI / 紅燈 / 危駕
        """
        focus = []

        # 1. A1 死亡 — 最高優先
        a1 = severity.get("A1", 0) if severity else 0
        if a1 > 0:
            focus.append(f"🔴 本期有 {a1} 件 A1 死亡事故，需專案檢討")

        # 2-4. 整體指標（新增 — overall 若存在則檢查）
        if overall:
            def describe(label: str, stat: StatComparison | dict, inc_threshold: int, dec_threshold: int) -> str | None:
                pct = stat.change_pct if hasattr(stat, "change_pct") else stat.get("change_pct", 0)
                curr = stat.current if hasattr(stat, "current") else stat.get("current", 0)
                last = stat.last_year if hasattr(stat, "last_year") else stat.get("last_year", 0)
                if pct >= inc_threshold and curr > 0:
                    return f"⚠ {label}上升（{pct:+.1f}%，{last}→{curr}）"
                if pct <= -inc_threshold and last > 0:
                    # 對違規取締「大幅下降」視為警訊（執法萎縮）
                    if label == "違規取締總量":
                        return f"⚠ {label}大幅下降（{pct:+.1f}%，{last}→{curr}）— 執法力度可能萎縮"
                    return f"✓ {label}下降（{pct:+.1f}%，{last}→{curr}）"
                return None

            for key, label, inc, dec in [
                ("accidents", "事故總量", 10, 10),
                ("injuries", "傷亡人數", 15, 15),
                ("tickets", "違規取締總量", 20, 20),
            ]:
                stat = overall.get(key)
                if stat:
                    msg = describe(label, stat, inc, dec)
                    if msg:
                        focus.append(msg)

        # 5. 主題變化（含超速）
        topic_labels = {
            "dui": "酒駕", "red_light": "闖紅燈",
            "dangerous": "危險駕駛", "speeding": "超速取締"
        }
        for topic, stat in topics.items():
            if topic not in topic_labels:
                continue
            display = topic_labels[topic]
            if stat.change_pct >= 20 and stat.current > 10:
                focus.append(f"{display}顯著增加（{stat.change_pct:+.0f}%）")
            elif stat.change_pct <= -20 and stat.last_year > 10:
                focus.append(f"{display}顯著下降（{stat.change_pct:+.0f}%）")

        return focus[:6]  # 上限 6 項避免資訊過載

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

    def _get_a1_locations(self, start_date: date, end_date: date) -> list:
        """
        取得本期所有 A1 死亡事故地點（不限 top_n）。

        警政實務規則：A1 案件屬「工程檢討必要重點」，
        AI 報告必須在工程建議章節逐一檢討每個 A1 地點。

        若本期無 A1 事故，回傳空 list。
        """
        query = self.db.query(
            Crash.district,
            Crash.location_desc,
            func.count(Crash.id).label('count'),
        ).filter(
            Crash.occurred_date >= start_date,
            Crash.occurred_date <= end_date,
            Crash.severity == 'A1',
            Crash.location_desc.isnot(None),
            Crash.location_desc != "",
        ).group_by(
            Crash.district, Crash.location_desc,
        ).order_by(desc('count'))

        results = query.all()
        items = []
        for row in results:
            if not self._is_meaningful_location(row.location_desc):
                continue
            items.append(HotspotItem(
                rank=len(items) + 1,
                location=self._clean_location(row.location_desc, row.district),
                district=self._clean_district(row.district),
                count=row.count,
                major_cause="A1",
            ))
        return items

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

    # ========================================
    # Phase 1-3 新資料維度織入（Phase 3-C3：道安會報月報升級）
    # 照明故障／無照駕駛／肇事逃逸／風險路線／改善措施成效
    # ========================================

    # 夜間班別集合（與 recommendations.py 的 NIGHT_SHIFTS 保持一致，22:00~06:00）
    _NIGHT_SHIFTS = {"10", "11", "12", "01", "02", "03"}

    def _get_lighting_issues(self, start: date, end: date) -> dict:
        """
        夜間照明故障事故統計（Phase 1 新增 road_lighting 欄位）。
        total：期間內道路照明「有照明未開啟或故障」件數
        night：其中發生於夜間班別（見 _NIGHT_SHIFTS）的件數
        """
        total = self._count_crash_range(start, end, Crash.road_lighting == "有照明未開啟或故障")
        night = self._count_crash_range(
            start, end,
            and_(Crash.road_lighting == "有照明未開啟或故障", Crash.shift_id.in_(self._NIGHT_SHIFTS)),
        )
        return {"total": total, "night": night}

    def _get_unlicensed_count(self, start: date, end: date) -> int:
        """無照駕駛事故件數（license_status 含「無照」，Phase 1 新增欄位）"""
        return self._count_crash_range(start, end, Crash.license_status.like('%無照%'))

    def _get_hit_and_run_count(self, start: date, end: date) -> int:
        """肇事逃逸事故件數（Phase 1 新增 is_hit_and_run 欄位）"""
        return self._count_crash_range(start, end, Crash.is_hit_and_run == True)

    def _get_top_route_segments(self, start: date, end: date) -> list:
        """
        風險路線 Top 3（Phase 1 新增 route_name / route_km 維度）。
        依 EPDO（台灣道安標準公式，人數口徑，見 app/utils/epdo.py）降冪排序，
        與 recommendations.py /corridor-analysis 路線排名（模式 A）採同一評比邏輯，
        方便跨功能對照。
        """
        rows = (
            self.db.query(
                Crash.route_name,
                func.count(Crash.id).label("total"),
                epdo_sql_sum().label("epdo"),
            )
            .filter(
                Crash.occurred_date >= start,
                Crash.occurred_date <= end,
                Crash.route_name.isnot(None),
                Crash.route_name != "",
            )
            .group_by(Crash.route_name)
            .order_by(desc("epdo"))
            .limit(3)
            .all()
        )
        return [
            {"route": r.route_name, "total": r.total, "epdo": round(r.epdo or 0, 1)}
            for r in rows
        ]

    def _get_improvement_effects(self) -> list:
        """
        改善措施成效（Phase 3-A3 成效評估織入 AI 報告，Phase 3-C3 新增）。
        沿用 improvements.py 端點抽取出的共用函式 evaluate_improvement()，
        避免同一套 before/after 評估邏輯維護兩份。
        取有 net_pct（可判讀）者，依實施日期降冪排序後取前 3 筆；
        無改善措施登記或全部尚無法判讀時回傳 []。
        """
        rows = self.db.query(Improvement).order_by(Improvement.implemented_date.desc()).all()
        if not rows:
            return []

        # 延遲匯入：避免 services 層與 api 層在模組載入時互相牽動
        from app.api.improvements import evaluate_improvement

        effects = []
        for imp in rows:
            evaluation = evaluate_improvement(self.db, imp, 365)
            if evaluation.get("net_pct") is not None:
                effects.append({
                    "title": evaluation["title"],
                    "implemented_date": evaluation["implemented_date"],
                    "net_pct": evaluation["net_pct"],
                    "verdict": evaluation["verdict"],
                    "preliminary": evaluation["preliminary"],
                })
            if len(effects) >= 3:
                break
        return effects
