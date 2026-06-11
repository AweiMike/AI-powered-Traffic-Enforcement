/**
 * HeavyVehiclePerformancePage - 大型車事故防制成效
 * 各派出所取締件數（含主動/肇事/民檢/其他子類細分）+ A1/A2/A3 事故數 + 去年同期比較
 */

import React, { useState, useEffect } from 'react';
import { Truck, TrendingUp, TrendingDown, Minus, AlertTriangle, Shield } from 'lucide-react';
import DateRangePicker, { type DateRange } from './DateRangePicker';
import { apiClient } from '../api/client';
import TrendCard from './TrendCard';

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

const HeavyVehiclePerformancePage: React.FC = () => {
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const result = await apiClient.getHeavyVehiclePerformance(range.startDate, range.endDate);
        setData(result);
      } catch (e) {
        console.error('Failed to fetch heavy vehicle performance', e);
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
          <Truck className="w-6 h-6 text-amber-600" />
          大型車事故防制成效
        </h2>
        <p className="text-nook-text/60 mt-1">各派出所大型車取締件數與事故數統計，含去年同期比較</p>
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
            icon={<Shield className="w-5 h-5 text-amber-600" />}
            color="amber"
            breakdown={data.total.tickets_breakdown}
          />
          <SummaryCard
            title="去年同期取締"
            current={data.total.tickets_prev}
            icon={<Shield className="w-5 h-5 text-gray-500" />}
            color="gray"
            breakdown={data.total.tickets_prev_breakdown}
          />
          <SummaryCard
            title="A1 大型車事故"
            current={data.total.a1_crashes}
            prev={data.total.a1_crashes_prev}
            icon={<AlertTriangle className="w-5 h-5 text-red-600" />}
            color="red"
            invertDiff
          />
          <SummaryCard
            title="A2 大型車事故"
            current={data.total.a2_crashes}
            prev={data.total.a2_crashes_prev}
            icon={<AlertTriangle className="w-5 h-5 text-orange-600" />}
            color="orange"
            invertDiff
          />
          <SummaryCard
            title="A3 大型車事故"
            current={data.total.a3_crashes}
            prev={data.total.a3_crashes_prev}
            icon={<AlertTriangle className="w-5 h-5 text-amber-600" />}
            color="amber"
            invertDiff
          />
        </div>
      )}

      {/* 大型車週趨勢 */}
      <TrendCard
        range={range}
        title="大型車週趨勢與專業判讀"
        fetcher={(s, e) => apiClient.getHeavyVehicleTrend(s, e)}
        primaryName="主動取締"
        secondaryName="肇事舉發"
      />

      {/* 各派出所明細表 */}
      <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden mb-6">
        <div className="p-4 border-b border-nook-cream/50">
          <h3 className="font-bold text-nook-text">各單位績效明細</h3>
        </div>
        {loading ? (
          <div className="p-12 text-center text-nook-text/40">載入中...</div>
        ) : data?.rows?.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-nook-text/80">
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
                  <tr key={row.unit} className={i % 2 === 0 ? 'bg-white' : 'bg-slate-50/30'}>
                    <td className="px-4 py-2.5 font-medium text-nook-text">{row.unit}</td>
                    <td className="px-4 py-2.5 text-right font-bold text-slate-800">{row.tickets}</td>
                    <td className="px-4 py-2.5 text-right text-nook-text/60">{row.tickets_prev}</td>
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
                <tr className="bg-slate-100 font-bold border-t-2 border-slate-300">
                  <td className="px-4 py-3 text-nook-text">合計</td>
                  <td className="px-4 py-3 text-right text-slate-800">{data.total.tickets}</td>
                  <td className="px-4 py-3 text-right text-nook-text/60">{data.total.tickets_prev}</td>
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

      {/* 法條取締細項 */}
      {data?.code_labels && (
        <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden">
          <div className="p-4 border-b border-nook-cream/50">
            <h3 className="font-bold text-nook-text">重點違規條款參考</h3>
            <p className="text-xs text-nook-text/50 mt-1">大型車精準執法應加強取締之違規態樣</p>
          </div>
          <div className="p-4">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {Object.entries(data.code_labels).map(([code, label]) => (
                <div key={code} className="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded-lg">
                  <span className="text-xs font-mono font-bold text-slate-800 bg-slate-100 px-1.5 py-0.5 rounded">{code}</span>
                  <span className="text-xs text-nook-text/70">{label as string}</span>
                </div>
              ))}
            </div>
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

function SummaryCard({ title, current, prev, icon, color, invertDiff, breakdown }: {
  title: string;
  current: number;
  prev?: number;
  icon: React.ReactNode;
  color: string;
  invertDiff?: boolean;
  breakdown?: { proactive: number; crash_derived: number; citizen: number; other: number };
}) {
  const diff = prev !== undefined ? current - prev : undefined;
  const colorMap: Record<string, string> = {
    amber: 'from-slate-50 to-slate-100/50 border-slate-200',
    red: 'from-red-50 to-red-100/50 border-red-200',
    orange: 'from-orange-50 to-orange-100/50 border-orange-200',
    gray: 'from-gray-50 to-gray-100/50 border-gray-200',
  };
  return (
    <div className={`bg-gradient-to-br ${colorMap[color] || colorMap.gray} border rounded-2xl p-4`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-nook-text/70">{title}</span>
        {icon}
      </div>
      <div className="text-2xl font-bold text-nook-text">{current}</div>
      {breakdown && (
        <div className="mt-0.5 text-[10px] flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
          <span className="text-green-700">主動<span className="ml-0.5 font-semibold tabular-nums">{breakdown.proactive}</span></span>
          <span className="text-red-500">肇事<span className="ml-0.5 font-semibold tabular-nums">{breakdown.crash_derived}</span></span>
          <span className="text-gray-500">民檢<span className="ml-0.5 font-semibold tabular-nums">{breakdown.citizen}</span></span>
          <span className="text-gray-400">其他<span className="ml-0.5 font-semibold tabular-nums">{breakdown.other}</span></span>
        </div>
      )}
      {diff !== undefined && (
        <div className="mt-1">
          {invertDiff ? (
            diff > 0
              ? <span className="text-xs text-red-600">較去年增加 {diff}</span>
              : diff < 0
              ? <span className="text-xs text-green-600">較去年減少 {Math.abs(diff)}</span>
              : <span className="text-xs text-gray-500">與去年持平</span>
          ) : (
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

export default HeavyVehiclePerformancePage;
