/**
 * DuiPerformancePage - 酒後駕車防制成效
 * 各派出所取締件數（含主動/肇事/民檢/其他細分）+ A1/A2/A3 事故數 + 去年同期比較
 */

import React, { useState, useEffect } from 'react';
import { Wine, TrendingUp, TrendingDown, Minus, AlertTriangle, Shield, Trophy } from 'lucide-react';
import DateRangePicker, { type DateRange } from './DateRangePicker';
import { apiClient } from '../api/client';

function defaultRange(): DateRange {
  const now = new Date();
  const start = new Date(now.getFullYear(), 0, 1);
  const fmt = (d: Date) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  return { startDate: fmt(start), endDate: fmt(now) };
}

function DiffBadge({ value }: { value: number }) {
  if (value > 0) return <span className="inline-flex items-center gap-0.5 text-red-600 text-xs font-bold"><TrendingUp className="w-3 h-3"/>+{value}</span>;
  if (value < 0) return <span className="inline-flex items-center gap-0.5 text-green-600 text-xs font-bold"><TrendingDown className="w-3 h-3"/>{value}</span>;
  return <span className="inline-flex items-center gap-0.5 text-gray-400 text-xs"><Minus className="w-3 h-3"/>0</span>;
}

interface TicketBreakdown {
  proactive: number;
  crash_derived: number;
  citizen: number;
  other: number;
}

/** 取締件數細分小字：主動/肇事/民檢/其他
 *  - 主動 (攔舉-一般)：值得鼓勵的主動出擊
 *  - 肇事 (攔舉-肇事 + violation_name 關鍵字 UNION)：含肇事的酒駕舉發
 *  - 民檢 (逕舉_民眾檢舉)：民眾通報
 *
 *  prevBreakdown 提供時，肇事項目額外顯示 vs 去年同期的增減
 *  （肇事增加=紅色警示、減少=綠色，與一般取締邏輯相反）
 */
function TicketBreakdownLine({
  breakdown, prevBreakdown, align = 'right'
}: {
  breakdown?: TicketBreakdown;
  prevBreakdown?: TicketBreakdown;
  align?: 'right' | 'left';
}) {
  if (!breakdown) return null;
  const items = [
    { label: '主動', value: breakdown.proactive, color: 'text-green-700' },
    { label: '肇事', value: breakdown.crash_derived, color: 'text-red-500', isCrash: true },
    { label: '民檢', value: breakdown.citizen, color: 'text-gray-500' },
    { label: '其他', value: breakdown.other, color: 'text-gray-400' },
  ];
  const crashDiff = prevBreakdown
    ? breakdown.crash_derived - prevBreakdown.crash_derived
    : null;
  return (
    <div className={`mt-0.5 text-[10px] flex flex-wrap items-center gap-x-1.5 gap-y-0.5 ${align === 'right' ? 'justify-end' : ''}`}>
      {items.map((it) => (
        <span key={it.label} className={it.color}>
          {it.label}<span className="ml-0.5 font-semibold tabular-nums">{it.value}</span>
          {it.isCrash && crashDiff !== null && crashDiff !== 0 && (
            <span className={`ml-0.5 font-bold tabular-nums ${crashDiff > 0 ? 'text-red-700' : 'text-emerald-700'}`}>
              {crashDiff > 0 ? `↑+${crashDiff}` : `↓${crashDiff}`}
            </span>
          )}
          {it.isCrash && crashDiff === 0 && (
            <span className="ml-0.5 text-gray-400">±0</span>
          )}
        </span>
      ))}
    </div>
  );
}

const DuiPerformancePage: React.FC = () => {
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const result = await apiClient.getDuiPerformance(range.startDate, range.endDate);
        setData(result);
      } catch (e) {
        console.error('Failed to fetch DUI performance', e);
      }
      setLoading(false);
    };
    fetchData();
  }, [range]);

  return (
    <div className="p-8">
      {/* 頁面標題 */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-nook-text flex items-center gap-2">
          <Wine className="w-6 h-6 text-sky-700" />
          酒後駕車防制成效
        </h2>
        <p className="text-nook-text/60 mt-1">各派出所取締件數與事故數統計，含去年同期比較</p>
      </div>

      {/* 日期區間選擇 */}
      <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-4 nook-shadow mb-6">
        <DateRangePicker value={range} onChange={setRange} />
      </div>

      {/* 摘要卡片 */}
      {data && (
        <div className="grid grid-cols-5 gap-4 mb-6">
          <SummaryCard
            title="取締件數"
            current={data.total.tickets}
            prev={data.total.tickets_prev}
            icon={<Shield className="w-5 h-5 text-sky-700" />}
            color="purple"
            breakdown={data.total.tickets_breakdown}
            prevBreakdown={data.total.tickets_prev_breakdown}
          />
          <SummaryCard
            title="去年同期取締"
            current={data.total.tickets_prev}
            icon={<Shield className="w-5 h-5 text-gray-500" />}
            color="gray"
            breakdown={data.total.tickets_prev_breakdown}
          />
          <SummaryCard
            title="A1 酒駕事故"
            current={data.total.a1_crashes}
            prev={data.total.a1_crashes_prev}
            icon={<AlertTriangle className="w-5 h-5 text-red-600" />}
            color="red"
            invertDiff
          />
          <SummaryCard
            title="A2 酒駕事故"
            current={data.total.a2_crashes}
            prev={data.total.a2_crashes_prev}
            icon={<AlertTriangle className="w-5 h-5 text-orange-600" />}
            color="orange"
            invertDiff
          />
          <SummaryCard
            title="A3 酒駕事故"
            current={data.total.a3_crashes}
            prev={data.total.a3_crashes_prev}
            icon={<AlertTriangle className="w-5 h-5 text-amber-600" />}
            color="amber"
            invertDiff
          />
        </div>
      )}

      {/* 各派出所明細表 */}
      <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden">
        <div className="p-4 border-b border-nook-cream/50">
          <h3 className="font-bold text-nook-text">各單位績效明細</h3>
        </div>
        {loading ? (
          <div className="p-12 text-center text-nook-text/40">載入中...</div>
        ) : data?.rows?.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-sky-50 text-nook-text/80">
                  <th className="px-4 py-3 text-left font-medium">單位</th>
                  <th className="px-4 py-3 text-right font-medium">取締件數</th>
                  <th className="px-4 py-3 text-right font-medium">去年同期</th>
                  <th className="px-4 py-3 text-right font-medium">增減</th>
                  <th className="px-4 py-3 text-right font-medium">A1 事故</th>
                  <th className="px-4 py-3 text-right font-medium">A1 去年</th>
                  <th className="px-4 py-3 text-right font-medium">A2 事故</th>
                  <th className="px-4 py-3 text-right font-medium">A2 去年</th>
                  <th className="px-4 py-3 text-right font-medium">A3 事故</th>
                  <th className="px-4 py-3 text-right font-medium">A3 去年</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row: any, i: number) => (
                  <tr key={row.unit} className={i % 2 === 0 ? 'bg-white' : 'bg-sky-50/30'}>
                    <td className="px-4 py-2.5 font-medium text-nook-text">{row.unit}</td>
                    <td className="px-4 py-2.5 text-right">
                      <div className="font-bold text-sky-800">{row.tickets}</div>
                      <TicketBreakdownLine
                        breakdown={row.tickets_breakdown}
                        prevBreakdown={row.tickets_prev_breakdown}
                      />
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <div className="text-nook-text/60">{row.tickets_prev}</div>
                      <TicketBreakdownLine breakdown={row.tickets_prev_breakdown} />
                    </td>
                    <td className="px-4 py-2.5 text-right"><DiffBadge value={row.tickets_diff} /></td>
                    <td className="px-4 py-2.5 text-right font-bold text-red-600">{row.a1_crashes}</td>
                    <td className="px-4 py-2.5 text-right text-nook-text/60">{row.a1_crashes_prev}</td>
                    <td className="px-4 py-2.5 text-right font-bold text-orange-600">{row.a2_crashes}</td>
                    <td className="px-4 py-2.5 text-right text-nook-text/60">{row.a2_crashes_prev}</td>
                    <td className="px-4 py-2.5 text-right font-bold text-amber-600">{row.a3_crashes}</td>
                    <td className="px-4 py-2.5 text-right text-nook-text/60">{row.a3_crashes_prev}</td>
                  </tr>
                ))}
                {/* 合計列 */}
                <tr className="bg-sky-100 font-bold border-t-2 border-sky-300">
                  <td className="px-4 py-3 text-nook-text">合計</td>
                  <td className="px-4 py-3 text-right">
                    <div className="text-sky-800">{data.total.tickets}</div>
                    <TicketBreakdownLine
                      breakdown={data.total.tickets_breakdown}
                      prevBreakdown={data.total.tickets_prev_breakdown}
                    />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="text-nook-text/60">{data.total.tickets_prev}</div>
                    <TicketBreakdownLine breakdown={data.total.tickets_prev_breakdown} />
                  </td>
                  <td className="px-4 py-3 text-right"><DiffBadge value={data.total.tickets_diff} /></td>
                  <td className="px-4 py-3 text-right text-red-600">{data.total.a1_crashes}</td>
                  <td className="px-4 py-3 text-right text-nook-text/60">{data.total.a1_crashes_prev}</td>
                  <td className="px-4 py-3 text-right text-orange-600">{data.total.a2_crashes}</td>
                  <td className="px-4 py-3 text-right text-nook-text/60">{data.total.a2_crashes_prev}</td>
                  <td className="px-4 py-3 text-right text-amber-600">{data.total.a3_crashes}</td>
                  <td className="px-4 py-3 text-right text-nook-text/60">{data.total.a3_crashes_prev}</td>
                </tr>
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-12 text-center text-nook-text/40">尚無資料</div>
        )}
      </div>

      {/* 管區績效排名（扣除肇事舉發）*/}
      {data?.unit_group_ranking && data.unit_group_ranking.length > 0 && (
        <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden mt-6">
          <div className="p-4 border-b border-nook-cream/50 flex items-center gap-2">
            <Trophy className="w-5 h-5 text-yellow-600" />
            <h3 className="font-bold text-nook-text">管區績效排名（扣除肇事舉發）</h3>
            <span className="text-xs text-nook-text/50 ml-2">
              · 主動取締 = 總取締 − 肇事舉發；數字越高代表派出所主動出擊（路檢、酒測站）越積極
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-yellow-50 text-nook-text/80">
                  <th className="px-4 py-3 text-center font-medium w-16">排名</th>
                  <th className="px-4 py-3 text-left font-medium">管區（含合併所）</th>
                  <th className="px-4 py-3 text-right font-medium">主動取締</th>
                  <th className="px-4 py-3 text-right font-medium">總取締</th>
                  <th className="px-4 py-3 text-right font-medium">肇事舉發</th>
                  <th className="px-4 py-3 text-right font-medium">酒駕肇事率</th>
                  <th className="px-4 py-3 text-center font-medium">執法缺口</th>
                  <th className="px-4 py-3 text-right font-medium">A1/A2/A3</th>
                </tr>
              </thead>
              <tbody>
                {data.unit_group_ranking.map((g: any, i: number) => (
                  <tr key={g.group} className={i % 2 === 0 ? 'bg-white' : 'bg-yellow-50/30'}>
                    <td className="px-4 py-2.5 text-center">
                      <RankBadge rank={g.rank} total={data.unit_group_ranking.length} />
                    </td>
                    <td className="px-4 py-2.5 font-medium text-nook-text">{g.group}</td>
                    <td className="px-4 py-2.5 text-right">
                      <span className="text-lg font-bold text-green-700 tabular-nums">{g.tickets_excl_crash}</span>
                    </td>
                    <td className="px-4 py-2.5 text-right text-sky-800 tabular-nums">{g.tickets_total}</td>
                    <td className="px-4 py-2.5 text-right text-red-500 tabular-nums">{g.tickets_crash_derived}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">
                      <CrashRate rate={g.dui_crash_rate} />
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <GapBadge gap={g.enforcement_gap} />
                    </td>
                    <td className="px-4 py-2.5 text-right text-xs text-nook-text/50 tabular-nums">
                      <span className="text-red-600">{g.a1_crashes}</span>
                      <span className="mx-0.5">/</span>
                      <span className="text-orange-600">{g.a2_crashes}</span>
                      <span className="mx-0.5">/</span>
                      <span className="text-amber-600">{g.a3_crashes}</span>
                      <span className="ml-1 text-nook-text/30" title="事故表 A1/A2/A3 可能因避免填寫而低估">⚠</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-3 text-xs text-nook-text/60 border-t border-nook-cream/30 space-y-1">
            <div>📊 <strong>酒駕肇事率</strong> = 攔舉-肇事 ÷ 總酒駕取締。資料來源是<u>舉發單</u>（強制填寫），比事故表 A1/A2/A3 可靠（事故表常被避免填寫嚴重度）。</div>
            <div>⚠️ <strong>執法缺口</strong>：肇事率 ≥ 30% 且主動率 &lt; 50% → 「有缺口」（事先沒攔到，事故才補開）；主動率 ≥ 70% 且肇事率 &lt; 15% → 「無缺口」（路檢有效）。取締 &lt; 5 件視為樣本不足。</div>
            <div className="text-nook-text/40">排名僅看「主動取締」件數；事故並列時依事故少者為優先。</div>
          </div>
        </div>
      )}

      {/* 同期比較說明 */}
      {data && (
        <div className="mt-4 text-xs text-nook-text/40 flex items-center gap-2">
          <span>查詢期間：{data.period.start_date} ~ {data.period.end_date}</span>
          <span>|</span>
          <span>去年同期：{data.compare_period.start_date} ~ {data.compare_period.end_date}</span>
        </div>
      )}
    </div>
  );
};

/** 酒駕肇事率：彩色文字，>=30% 紅、15-30% 黃、<15% 綠 */
function CrashRate({ rate }: { rate: number }) {
  const pct = (rate * 100).toFixed(1);
  let cls = 'text-gray-500';
  if (rate >= 0.30) cls = 'text-red-600 font-semibold';
  else if (rate >= 0.15) cls = 'text-orange-500 font-semibold';
  else if (rate > 0) cls = 'text-green-700 font-semibold';
  return <span className={cls}>{pct}%</span>;
}

/** 執法缺口徽章 */
function GapBadge({ gap }: { gap: 'HIGH' | 'LOW' | 'NEUTRAL' | 'INSUFFICIENT_DATA' }) {
  if (gap === 'HIGH') {
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-xs font-semibold">⚠ 有缺口</span>;
  }
  if (gap === 'LOW') {
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-100 text-green-700 text-xs font-semibold">✅ 無缺口</span>;
  }
  if (gap === 'INSUFFICIENT_DATA') {
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 text-xs">樣本不足</span>;
  }
  return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-yellow-50 text-yellow-700 text-xs">中性</span>;
}

/** 排名徽章：第 1 名金、第 2 銀、第 3 銅、最後一名警示 */
function RankBadge({ rank, total }: { rank: number; total: number }) {
  if (rank === 1) {
    return <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-yellow-400 text-yellow-900 font-bold text-sm shadow-sm">🥇</span>;
  }
  if (rank === 2) {
    return <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-gray-300 text-gray-800 font-bold text-sm shadow-sm">🥈</span>;
  }
  if (rank === 3) {
    return <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-orange-300 text-orange-900 font-bold text-sm shadow-sm">🥉</span>;
  }
  if (rank === total) {
    return <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-red-100 text-red-700 font-bold text-sm">{rank}</span>;
  }
  return <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-gray-100 text-gray-700 font-bold text-sm">{rank}</span>;
}

/** 摘要卡片 */
function SummaryCard({ title, current, prev, icon, color, invertDiff, breakdown, prevBreakdown }: {
  title: string;
  current: number;
  prev?: number;
  icon: React.ReactNode;
  color: string;
  invertDiff?: boolean;
  breakdown?: TicketBreakdown;
  prevBreakdown?: TicketBreakdown;
}) {
  const diff = prev !== undefined ? current - prev : undefined;
  const colorMap: Record<string, string> = {
    purple: 'from-sky-50 to-sky-100/50 border-sky-200',
    red: 'from-red-50 to-red-100/50 border-red-200',
    orange: 'from-orange-50 to-orange-100/50 border-orange-200',
    amber: 'from-amber-50 to-amber-100/50 border-amber-200',
    gray: 'from-gray-50 to-gray-100/50 border-gray-200',
  };
  return (
    <div className={`bg-gradient-to-br ${colorMap[color] || colorMap.gray} border rounded-2xl p-4`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-nook-text/70">{title}</span>
        {icon}
      </div>
      <div className="text-2xl font-bold text-nook-text">{current}</div>
      {breakdown && <TicketBreakdownLine breakdown={breakdown} prevBreakdown={prevBreakdown} align="left" />}
      {diff !== undefined && (
        <div className="mt-1">
          {invertDiff ? (
            // 事故：減少是好的
            diff > 0
              ? <span className="text-xs text-red-600">較去年增加 {diff}</span>
              : diff < 0
              ? <span className="text-xs text-green-600">較去年減少 {Math.abs(diff)}</span>
              : <span className="text-xs text-gray-500">與去年持平</span>
          ) : (
            // 取締：增加是好的
            diff > 0
              ? <span className="text-xs text-green-600">較去年增加 {diff}</span>
              : diff < 0
              ? <span className="text-xs text-red-600">較去年減少 {Math.abs(diff)}</span>
              : <span className="text-xs text-gray-500">與去年持平</span>
          )}
        </div>
      )}
    </div>
  );
}

export default DuiPerformancePage;
