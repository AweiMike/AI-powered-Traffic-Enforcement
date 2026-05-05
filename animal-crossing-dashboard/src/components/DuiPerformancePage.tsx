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

/** 增減顯示：上方主動取締、下方肇事，分別與去年同期比較
 *  主動 invert=false（增加=綠=好）；肇事 invert=true（增加=紅=壞）
 *  肇事採 Crash 側 ground truth（若有提供 crashOverride）
 */
function ProactiveVsCrashDiff({
  breakdown, prevBreakdown,
  crashOverride, crashPrevOverride,
  totalOverride, totalPrevOverride,
}: {
  breakdown?: TicketBreakdown;
  prevBreakdown?: TicketBreakdown;
  crashOverride?: number;
  crashPrevOverride?: number;
  totalOverride?: number;
  totalPrevOverride?: number;
}) {
  if (!breakdown || !prevBreakdown) return <span className="text-gray-400 text-xs">—</span>;
  const crashCur = crashOverride ?? breakdown.crash_derived;
  const crashPrev = crashPrevOverride ?? prevBreakdown.crash_derived;
  const totalCur = totalOverride ?? (breakdown.proactive + breakdown.crash_derived + (breakdown.refusal ?? 0) + breakdown.citizen + breakdown.other);
  const totalPrev = totalPrevOverride ?? (prevBreakdown.proactive + prevBreakdown.crash_derived + (prevBreakdown.refusal ?? 0) + prevBreakdown.citizen + prevBreakdown.other);
  // 主動 = 取締總數 − 肇事舉發 − 民檢
  const proactiveCur = Math.max(0, totalCur - crashCur - breakdown.citizen);
  const proactivePrev = Math.max(0, totalPrev - crashPrev - prevBreakdown.citizen);
  const proactiveDiff = proactiveCur - proactivePrev;
  const crashDiff = crashCur - crashPrev;

  return (
    <div className="inline-flex flex-col items-end gap-0.5 text-[11px]">
      <span className="flex items-center gap-1">
        <span className="text-green-700/80 font-medium">主動</span>
        <DiffArrow diff={proactiveDiff} invert={false} />
      </span>
      <span className="flex items-center gap-1">
        <span className="text-red-500/80 font-medium">肇事</span>
        <DiffArrow diff={crashDiff} invert={true} />
      </span>
    </div>
  );
}

interface TicketBreakdown {
  proactive: number;
  crash_derived: number;
  /** 拒檢/拒測案件（§35-IV：拒絕酒測 或 不依指示停車接受稽查） */
  refusal: number;
  citizen: number;
  /** 慢車（攔舉-慢行攤 + 其他逕舉子類） */
  other: number;
}

/** 取締件數細分小字：主動/肇事/民檢/慢車
 *  - 主動 (攔舉-一般)：值得鼓勵的主動出擊
 *  - 肇事 (攔舉-肇事 + violation_name 關鍵字 UNION)：含肇事的酒駕舉發
 *  - 民檢 (逕舉_民眾檢舉)：民眾通報
 *  - 慢車 (攔舉-慢行攤 + 其他逕舉)：微電車/腳踏車類酒駕
 *
 *  每項在 prevBreakdown 提供時都會顯示 vs 去年同期的增減箭頭。
 *  語意：肇事 增加=壞(紅) / 減少=好(綠)；其餘取締量 增加=好(綠) / 減少=壞(紅)
 */
function DiffArrow({ diff, invert = false, size = 'xs' }: {
  diff: number;
  invert?: boolean;  // true 表示「增加=壞」（如肇事）
  size?: 'xs' | 'sm';
}) {
  const cls = size === 'sm' ? 'text-sm font-bold' : 'text-[10px] font-bold';
  if (diff === 0) return <span className={`${cls} text-gray-400 ml-0.5`}>±0</span>;
  const isBad = invert ? diff > 0 : diff < 0;
  const color = isBad ? 'text-red-700' : 'text-emerald-700';
  const sign = diff > 0 ? `↑+${diff}` : `↓${diff}`;
  return <span className={`${cls} ${color} ml-0.5 tabular-nums`}>{sign}</span>;
}

function TicketBreakdownLine({
  breakdown, prevBreakdown, align = 'right',
  crashOverride, crashPrevOverride,
  totalOverride, totalPrevOverride,
}: {
  breakdown?: TicketBreakdown;
  prevBreakdown?: TicketBreakdown;
  align?: 'right' | 'left';
  /** 用 Crash 側 ground truth 覆寫「肇事舉發」桶（因法律規定酒駕事故必開單，兩者應相等）*/
  crashOverride?: number;
  crashPrevOverride?: number;
  /** 取締總數（用於主動桶 residual 計算） */
  totalOverride?: number;
  totalPrevOverride?: number;
}) {
  if (!breakdown) return null;

  // 「肇事舉發」採 Crash 側 ground truth（事故表飲酒情形 4-8）
  // 法律規定：酒駕事故必開單。所以 肇事舉發 = 酒駕事故 = 14（Crash 側）
  // 主動 = 取締總數 − 肇事舉發 − 民檢（residual 算法）
  const crashCount = crashOverride ?? breakdown.crash_derived;
  const crashPrev = crashPrevOverride ?? prevBreakdown?.crash_derived ?? 0;
  const refusal = breakdown.refusal ?? 0;
  const ticketsTotal = totalOverride ?? (breakdown.proactive + breakdown.crash_derived + refusal + breakdown.citizen + breakdown.other);
  const ticketsPrev = totalPrevOverride ?? (
    prevBreakdown
      ? prevBreakdown.proactive + prevBreakdown.crash_derived + (prevBreakdown.refusal ?? 0) + prevBreakdown.citizen + prevBreakdown.other
      : 0
  );

  const proactiveTotal = Math.max(0, ticketsTotal - crashCount - breakdown.citizen);
  const prevProactiveTotal = Math.max(0, ticketsPrev - crashPrev - (prevBreakdown?.citizen ?? 0));

  const mainItems: { label: string; value: number; prev: number; color: string; invert: boolean }[] = [
    { label: '主動', value: proactiveTotal, prev: prevProactiveTotal, color: 'text-green-700', invert: false },
    // 肇事舉發 = 酒駕事故（Crash 側）。法律規定酒駕事故必開單，所以兩者數字相等。
    { label: '肇事舉發', value: crashCount, prev: crashPrev, color: 'text-red-500', invert: true },
    { label: '民檢', value: breakdown.citizen, prev: prevBreakdown?.citizen ?? 0, color: 'text-gray-500', invert: false },
  ];

  // 主動內細項（不顯示箭頭，純資訊）
  const subItems: { label: string; value: number }[] = [
    { label: '一般', value: breakdown.proactive },
    { label: '拒檢', value: refusal },
    { label: '慢車', value: breakdown.other },
  ].filter(s => s.value > 0);

  const justify = align === 'right' ? 'justify-end' : '';

  return (
    <div className="mt-0.5 space-y-0.5">
      <div className={`text-[10px] flex flex-wrap items-center gap-x-1.5 gap-y-0.5 ${justify}`}>
        {mainItems.map((it) => (
          <span key={it.label} className={it.color}>
            {it.label}<span className="ml-0.5 font-semibold tabular-nums">{it.value}</span>
            {prevBreakdown && <DiffArrow diff={it.value - it.prev} invert={it.invert} />}
          </span>
        ))}
      </div>
      {/* 子細分只在沒用 Crash override 時顯示（用 Crash override 時主動桶為 residual，sub-bucket 不再對應） */}
      {subItems.length > 0 && proactiveTotal > 0 && crashOverride === undefined && (
        <div className={`text-[9px] text-nook-text/40 flex flex-wrap items-center gap-x-1 gap-y-0.5 ${justify}`}>
          <span>主動內</span>
          {subItems.map((s, i) => (
            <span key={s.label}>
              {i > 0 && <span className="mx-0.5">·</span>}
              {s.label} <span className="font-semibold tabular-nums">{s.value}</span>
            </span>
          ))}
        </div>
      )}
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
      {data && (() => {
        const a1 = data.total.a1_crashes || 0;
        const a2 = data.total.a2_crashes || 0;
        const a3 = data.total.a3_crashes || 0;
        const a1p = data.total.a1_crashes_prev || 0;
        const a2p = data.total.a2_crashes_prev || 0;
        const a3p = data.total.a3_crashes_prev || 0;
        const crashTotal = a1 + a2 + a3;
        const crashTotalPrev = a1p + a2p + a3p;
        return (
          <div className="grid grid-cols-3 gap-4 mb-6">
            <SummaryCard
              title="取締件數"
              current={data.total.tickets}
              prev={data.total.tickets_prev}
              icon={<Shield className="w-5 h-5 text-sky-700" />}
              color="purple"
              breakdown={data.total.tickets_breakdown}
              prevBreakdown={data.total.tickets_prev_breakdown}
              crashOverride={crashTotal}
              crashPrevOverride={crashTotalPrev}
              totalOverride={data.total.tickets}
              totalPrevOverride={data.total.tickets_prev}
            />
            <SummaryCard
              title="去年同期取締"
              current={data.total.tickets_prev}
              icon={<Shield className="w-5 h-5 text-gray-500" />}
              color="gray"
              breakdown={data.total.tickets_prev_breakdown}
            />
            <CrashSummaryCard
              current={crashTotal}
              prev={crashTotalPrev}
              a1={a1} a2={a2} a3={a3}
              a1p={a1p} a2p={a2p} a3p={a3p}
            />
          </div>
        );
      })()}

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
                        crashOverride={(row.a1_crashes ?? 0) + (row.a2_crashes ?? 0) + (row.a3_crashes ?? 0)}
                        crashPrevOverride={(row.a1_crashes_prev ?? 0) + (row.a2_crashes_prev ?? 0) + (row.a3_crashes_prev ?? 0)}
                        totalOverride={row.tickets}
                        totalPrevOverride={row.tickets_prev}
                      />
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <div className="text-nook-text/60">{row.tickets_prev}</div>
                      <TicketBreakdownLine breakdown={row.tickets_prev_breakdown} />
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <ProactiveVsCrashDiff
                        breakdown={row.tickets_breakdown}
                        prevBreakdown={row.tickets_prev_breakdown}
                        crashOverride={(row.a1_crashes ?? 0) + (row.a2_crashes ?? 0) + (row.a3_crashes ?? 0)}
                        crashPrevOverride={(row.a1_crashes_prev ?? 0) + (row.a2_crashes_prev ?? 0) + (row.a3_crashes_prev ?? 0)}
                        totalOverride={row.tickets}
                        totalPrevOverride={row.tickets_prev}
                      />
                    </td>
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
                      crashOverride={(data.total.a1_crashes ?? 0) + (data.total.a2_crashes ?? 0) + (data.total.a3_crashes ?? 0)}
                      crashPrevOverride={(data.total.a1_crashes_prev ?? 0) + (data.total.a2_crashes_prev ?? 0) + (data.total.a3_crashes_prev ?? 0)}
                      totalOverride={data.total.tickets}
                      totalPrevOverride={data.total.tickets_prev}
                    />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="text-nook-text/60">{data.total.tickets_prev}</div>
                    <TicketBreakdownLine breakdown={data.total.tickets_prev_breakdown} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <ProactiveVsCrashDiff
                      breakdown={data.total.tickets_breakdown}
                      prevBreakdown={data.total.tickets_prev_breakdown}
                      crashOverride={(data.total.a1_crashes ?? 0) + (data.total.a2_crashes ?? 0) + (data.total.a3_crashes ?? 0)}
                      crashPrevOverride={(data.total.a1_crashes_prev ?? 0) + (data.total.a2_crashes_prev ?? 0) + (data.total.a3_crashes_prev ?? 0)}
                      totalOverride={data.total.tickets}
                      totalPrevOverride={data.total.tickets_prev}
                    />
                  </td>
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
                  <th className="px-4 py-3 text-right font-medium">總取締</th>
                  <th className="px-4 py-3 text-right font-medium">主動取締</th>
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
                    <td className="px-4 py-2.5 text-right text-sky-800 tabular-nums font-semibold">{g.tickets_total}</td>
                    <td className="px-4 py-2.5 text-right">
                      <span className="text-lg font-bold text-green-700 tabular-nums">{g.tickets_excl_crash}</span>
                    </td>
                    <td className="px-4 py-2.5 text-right text-red-500 tabular-nums">{g.crashes_total}</td>
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

/** 酒駕事故摘要卡（Crash 側 ground truth：A1+A2+A3 = is_dui_crash_party 總計） */
function CrashSummaryCard({ current, prev, a1, a2, a3, a1p, a2p, a3p }: {
  current: number; prev: number;
  a1: number; a2: number; a3: number;
  a1p: number; a2p: number; a3p: number;
}) {
  const diff = current - prev;
  return (
    <div className="bg-gradient-to-br from-red-50 to-red-100/50 border border-red-200 rounded-2xl p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-nook-text/70">🚗 酒駕事故</span>
        <AlertTriangle className="w-5 h-5 text-red-600" />
      </div>
      <div className="text-2xl font-bold text-nook-text flex items-baseline gap-2">
        <span>{current}</span>
        <DiffArrow diff={diff} invert={true} size="sm" />
      </div>
      {/* A1/A2/A3 子細分（小字） */}
      <div className="mt-1 text-[10px] flex flex-wrap items-center gap-x-1.5">
        <span className="text-red-700 font-semibold">
          A1<span className="ml-0.5 font-bold tabular-nums">{a1}</span>
          <DiffArrow diff={a1 - a1p} invert={true} />
        </span>
        <span className="text-orange-600 font-semibold">
          A2<span className="ml-0.5 font-bold tabular-nums">{a2}</span>
          <DiffArrow diff={a2 - a2p} invert={true} />
        </span>
        <span className="text-amber-600 font-semibold">
          A3<span className="ml-0.5 font-bold tabular-nums">{a3}</span>
          <DiffArrow diff={a3 - a3p} invert={true} />
        </span>
      </div>
      <p className="text-[10px] text-red-400/80 mt-0.5">事故表 ground truth（飲酒情形 4-8）</p>
    </div>
  );
}

/** 摘要卡片 */
function SummaryCard({ title, current, prev, icon, color, invertDiff, breakdown, prevBreakdown, crashOverride, crashPrevOverride, totalOverride, totalPrevOverride }: {
  title: string;
  current: number;
  prev?: number;
  icon: React.ReactNode;
  color: string;
  invertDiff?: boolean;
  breakdown?: TicketBreakdown;
  prevBreakdown?: TicketBreakdown;
  crashOverride?: number;
  crashPrevOverride?: number;
  totalOverride?: number;
  totalPrevOverride?: number;
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
      <div className="text-2xl font-bold text-nook-text flex items-baseline gap-2">
        <span>{current}</span>
        {diff !== undefined && (
          <DiffArrow diff={diff} invert={!!invertDiff} size="sm" />
        )}
      </div>
      {breakdown && (
        <TicketBreakdownLine
          breakdown={breakdown}
          prevBreakdown={prevBreakdown}
          align="left"
          crashOverride={crashOverride}
          crashPrevOverride={crashPrevOverride}
          totalOverride={totalOverride}
          totalPrevOverride={totalPrevOverride}
        />
      )}
    </div>
  );
}

export default DuiPerformancePage;
