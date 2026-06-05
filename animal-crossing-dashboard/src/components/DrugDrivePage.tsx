/**
 * DrugDrivePage - 毒品駕駛防制分析（取締側）
 * 資料來源：Ticket 法條代碼 §35 I-2 吸食毒品 / §35 IV 毒品拒檢
 * ⚠️ 事故側受限：EIS 事故調查表無毒品專屬欄位，故僅做取締分析
 */

import React, { useState, useEffect } from 'react';
import { Pill, TrendingUp, TrendingDown, Minus, AlertTriangle, MapPin, Clock, Trophy } from 'lucide-react';
import DateRangePicker, { type DateRange } from './DateRangePicker';
import { apiClient } from '../api/client';

function defaultRange(): DateRange {
  const now = new Date();
  const start = new Date(now.getFullYear(), 0, 1);
  const fmt = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return { startDate: fmt(start), endDate: fmt(now) };
}

/** 增減箭頭：取締增加=綠(好)、減少=紅(壞)；肇事相反 */
function DiffArrow({ diff, invert = false }: { diff: number; invert?: boolean }) {
  if (diff === 0) return <span className="text-[10px] text-gray-400 ml-0.5">±0</span>;
  const isBad = invert ? diff > 0 : diff < 0;
  const color = isBad ? 'text-red-600' : 'text-teal-600';
  const sign = diff > 0 ? `↑+${diff}` : `↓${diff}`;
  return <span className={`text-[11px] font-bold ${color} ml-0.5 tabular-nums`}>{sign}</span>;
}

const DrugDrivePage: React.FC = () => {
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const result = await apiClient.getDrugPerformance(range.startDate, range.endDate);
        setData(result);
      } catch (e) {
        console.error('Failed to fetch drug performance', e);
      }
      setLoading(false);
    };
    fetchData();
  }, [range]);

  const total = data?.total;
  const maxDistrict = Math.max(1, ...(data?.by_district || []).map((d: any) => d.tickets));
  const maxShift = Math.max(1, ...(data?.by_shift || []).map((s: any) => s.tickets));

  return (
    <div className="p-8">
      {/* 標題 */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-nook-text flex items-center gap-2">
          <Pill className="w-6 h-6 text-teal-600" />
          毒品駕駛防制分析
        </h2>
        <p className="text-nook-text/60 mt-1">§35 吸食毒品 / 毒品拒檢取締分析、時段與區域精準執法建議</p>
      </div>

      {/* 資料限制說明 */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800 mb-6">
        ⚠️ <strong>事故側資料受限</strong>：EIS 事故調查表無毒品專屬欄位（飲酒情形代碼僅記錄酒精），
        故本專區僅涵蓋<strong>取締（舉發）資料</strong>。毒駕已從酒駕統計中拆分，兩者互不重複計算。
      </div>

      {/* 日期區間 */}
      <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-4 nook-shadow mb-6">
        <DateRangePicker value={range} onChange={setRange} />
      </div>

      {loading ? (
        <div className="p-12 text-center text-nook-text/40">載入中...</div>
      ) : !data ? (
        <div className="p-12 text-center text-nook-text/40">尚無資料</div>
      ) : (
        <>
          {/* KPI 卡片 */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-gradient-to-br from-teal-50 to-teal-100/50 border border-teal-200 rounded-2xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-nook-text/70">毒駕取締</span>
                <Pill className="w-5 h-5 text-teal-600" />
              </div>
              <div className="text-2xl font-bold text-nook-text flex items-baseline gap-2">
                <span>{total.tickets}</span>
                <DiffArrow diff={total.tickets_diff} invert={false} />
              </div>
              <p className="text-[10px] text-teal-400/80 mt-1">§35 I-2 吸食毒品 + IV 毒品拒檢</p>
            </div>

            <div className="bg-gradient-to-br from-red-50 to-red-100/50 border border-red-200 rounded-2xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-nook-text/70">毒駕肇事</span>
                <AlertTriangle className="w-5 h-5 text-red-600" />
              </div>
              <div className="text-2xl font-bold text-nook-text flex items-baseline gap-2">
                <span>{total.crash}</span>
                <DiffArrow diff={total.crash_diff} invert={true} />
              </div>
              <p className="text-[10px] text-red-400/80 mt-1">舉發單含肇事關鍵字</p>
            </div>

            <div className="bg-gradient-to-br from-gray-50 to-gray-100/50 border border-gray-200 rounded-2xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-nook-text/70">去年同期取締</span>
                <Pill className="w-5 h-5 text-gray-500" />
              </div>
              <div className="text-2xl font-bold text-nook-text">{total.tickets_prev}</div>
              <p className="text-[10px] text-gray-400 mt-1">{data.compare_period.start_date} ~ {data.compare_period.end_date}</p>
            </div>
          </div>

          {/* 管區排名 */}
          {data.unit_group_ranking?.length > 0 && (
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden mb-6">
              <div className="p-4 border-b border-nook-cream/50 flex items-center gap-2">
                <Trophy className="w-5 h-5 text-yellow-600" />
                <h3 className="font-bold text-nook-text">管區毒駕取締排名</h3>
                <span className="text-xs text-nook-text/50 ml-2">依取締件數排序（含合併所）</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-teal-50 text-nook-text/80">
                      <th className="px-4 py-3 text-center font-medium w-16">排名</th>
                      <th className="px-4 py-3 text-left font-medium">管區</th>
                      <th className="px-4 py-3 text-right font-medium">取締件數</th>
                      <th className="px-4 py-3 text-right font-medium">含肇事</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.unit_group_ranking.map((g: any, i: number) => (
                      <tr key={g.group} className={i % 2 === 0 ? 'bg-white' : 'bg-teal-50/30'}>
                        <td className="px-4 py-2.5 text-center">
                          <RankBadge rank={g.rank} />
                        </td>
                        <td className="px-4 py-2.5 font-medium text-nook-text">{g.group}</td>
                        <td className="px-4 py-2.5 text-right font-bold text-teal-700 tabular-nums">{g.tickets}</td>
                        <td className="px-4 py-2.5 text-right text-red-600 tabular-nums">{g.crash}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-6">
            {/* 區域分析 */}
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden">
              <div className="p-4 border-b border-nook-cream/50 flex items-center gap-2">
                <MapPin className="w-5 h-5 text-teal-600" />
                <h3 className="font-bold text-nook-text">毒駕高發區域</h3>
                <span className="text-xs text-nook-text/50 ml-2">建議攔檢地點</span>
              </div>
              <div className="p-4 space-y-2">
                {data.by_district?.length > 0 ? data.by_district.map((d: any) => (
                  <div key={d.district} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="font-medium text-nook-text">{d.district}</span>
                      <span className="tabular-nums">
                        <span className="font-bold text-teal-700">{d.tickets}</span>
                        {d.crash > 0 && <span className="text-red-600 ml-1">（肇事 {d.crash}）</span>}
                      </span>
                    </div>
                    <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-teal-400 to-teal-600 rounded-full"
                        style={{ width: `${(d.tickets / maxDistrict) * 100}%` }} />
                    </div>
                  </div>
                )) : <p className="text-nook-text/40 text-center py-6 text-sm">尚無資料</p>}
              </div>
            </div>

            {/* 時段分析 */}
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden">
              <div className="p-4 border-b border-nook-cream/50 flex items-center gap-2">
                <Clock className="w-5 h-5 text-teal-600" />
                <h3 className="font-bold text-nook-text">毒駕高發時段</h3>
                <span className="text-xs text-nook-text/50 ml-2">建議攔檢時間（派出所勤務班）</span>
              </div>
              <div className="p-4 space-y-2">
                {data.by_shift?.length > 0 ? data.by_shift.map((s: any) => (
                  <div key={s.shift_id} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="font-medium text-nook-text">
                        第{s.duty_order}班 <span className="text-nook-text/50">{s.time_range}</span>
                      </span>
                      <span className="tabular-nums">
                        <span className="font-bold text-teal-700">{s.tickets}</span>
                        {s.crash > 0 && <span className="text-red-600 ml-1">（肇事 {s.crash}）</span>}
                      </span>
                    </div>
                    <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-teal-400 to-teal-600 rounded-full"
                        style={{ width: `${(s.tickets / maxShift) * 100}%` }} />
                    </div>
                  </div>
                )) : <p className="text-nook-text/40 text-center py-6 text-sm">尚無資料</p>}
              </div>
            </div>
          </div>

          {/* 各派出所明細 */}
          {data.rows?.length > 0 && (
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden mt-6">
              <div className="p-4 border-b border-nook-cream/50">
                <h3 className="font-bold text-nook-text">各單位毒駕取締明細</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-teal-50 text-nook-text/80">
                      <th className="px-4 py-3 text-left font-medium">單位</th>
                      <th className="px-4 py-3 text-right font-medium">取締件數</th>
                      <th className="px-4 py-3 text-right font-medium">去年同期</th>
                      <th className="px-4 py-3 text-right font-medium">增減</th>
                      <th className="px-4 py-3 text-right font-medium">含肇事</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.rows.map((row: any, i: number) => (
                      <tr key={row.unit} className={i % 2 === 0 ? 'bg-white' : 'bg-teal-50/30'}>
                        <td className="px-4 py-2.5 font-medium text-nook-text">{row.unit}</td>
                        <td className="px-4 py-2.5 text-right font-bold text-teal-700 tabular-nums">{row.tickets}</td>
                        <td className="px-4 py-2.5 text-right text-nook-text/60 tabular-nums">{row.tickets_prev}</td>
                        <td className="px-4 py-2.5 text-right"><DiffBadge value={row.tickets_diff} /></td>
                        <td className="px-4 py-2.5 text-right text-red-600 tabular-nums">{row.crash}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 統計區間 */}
          <div className="mt-4 text-xs text-nook-text/40">
            查詢期間：{data.period.start_date} ~ {data.period.end_date}
            <span className="mx-2">|</span>
            去年同期：{data.compare_period.start_date} ~ {data.compare_period.end_date}
          </div>
        </>
      )}
    </div>
  );
};

function DiffBadge({ value }: { value: number }) {
  if (value > 0) return <span className="inline-flex items-center gap-0.5 text-red-600 text-xs font-bold"><TrendingUp className="w-3 h-3" />+{value}</span>;
  if (value < 0) return <span className="inline-flex items-center gap-0.5 text-green-600 text-xs font-bold"><TrendingDown className="w-3 h-3" />{value}</span>;
  return <span className="inline-flex items-center gap-0.5 text-gray-400 text-xs"><Minus className="w-3 h-3" />0</span>;
}

function RankBadge({ rank }: { rank: number }) {
  if (rank === 1) return <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-yellow-400 text-yellow-900 font-bold text-sm shadow-sm">🥇</span>;
  if (rank === 2) return <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-gray-300 text-gray-800 font-bold text-sm shadow-sm">🥈</span>;
  if (rank === 3) return <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-orange-300 text-orange-900 font-bold text-sm shadow-sm">🥉</span>;
  return <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-gray-100 text-gray-700 font-bold text-sm">{rank}</span>;
}

export default DrugDrivePage;
