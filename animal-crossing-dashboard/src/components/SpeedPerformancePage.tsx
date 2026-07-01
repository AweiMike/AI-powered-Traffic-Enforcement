/**
 * SpeedPerformancePage - 速度管理（超速違規）專區
 * 超速取締件數、嚴重度分級、速限分布、派出所排名、熱點
 */

import React, { useState, useEffect } from 'react';
import { Gauge, TrendingUp, TrendingDown, Minus, AlertTriangle, Zap, MapPin } from 'lucide-react';
import DateRangePicker, { type DateRange } from './DateRangePicker';
import { apiClient } from '../api/client';
import TrendCardSkeleton from './TrendCardSkeleton';

// recharts 依賴較重，動態載入讓它獨立成 chunk，不灌進主 bundle
const TrendCard = React.lazy(() => import('./TrendCard'));

function defaultRange(): DateRange {
    const now = new Date();
    const start = new Date(now.getFullYear(), 0, 1);
    const fmt = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    return { startDate: fmt(start), endDate: fmt(now) };
}

function DiffBadge({ value }: { value: number }) {
    if (value > 0) return <span className="inline-flex items-center gap-0.5 text-red-600 text-xs font-bold tabular-nums"><TrendingUp className="w-3 h-3" />+{value}</span>;
    if (value < 0) return <span className="inline-flex items-center gap-0.5 text-green-600 text-xs font-bold tabular-nums"><TrendingDown className="w-3 h-3" />{value}</span>;
    return <span className="inline-flex items-center gap-0.5 text-gray-400 text-xs"><Minus className="w-3 h-3" />0</span>;
}

function PctBadge({ value }: { value: number | null }) {
    if (value === null || value === undefined) return <span className="text-slate-400 text-xs">—</span>;
    if (value > 0) return <span className="text-red-600 text-xs font-bold tabular-nums">+{value.toFixed(1)}%</span>;
    if (value < 0) return <span className="text-green-600 text-xs font-bold tabular-nums">{value.toFixed(1)}%</span>;
    return <span className="text-slate-400 text-xs">0%</span>;
}

/** 短派出所名 */
function shortUnit(name: string): string {
    return name ? name.replace('新化分局', '') : name;
}

const SpeedPerformancePage: React.FC = () => {
    const [range, setRange] = useState<DateRange>(defaultRange);
    const [data, setData] = useState<any>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            try {
                const result = await apiClient.getSpeedPerformance(range.startDate, range.endDate);
                setData(result);
            } catch (e) {
                console.error('Failed to fetch speed performance', e);
            }
            setLoading(false);
        };
        fetchData();
    }, [range]);

    const curr = data?.summary?.current;
    const prev = data?.summary?.previous;
    const crashesC = data?.crashes?.current;
    const crashesP = data?.crashes?.previous;

    // 嚴重度比例
    const sevTotal = curr ? curr.severity.light + curr.severity.medium + curr.severity.heavy + curr.severity.unknown : 0;

    return (
        <div className="p-8">
            {/* 標題 */}
            <div className="mb-6">
                <h2 className="text-2xl font-bold text-nook-text flex items-center gap-2">
                    <Gauge className="w-6 h-6 text-sky-700" />
                    速度管理（超速違規）
                </h2>
                <p className="text-nook-text/60 mt-1">超速取締件數、嚴重度分級、速限分布與熱點，含去年同期比較</p>
            </div>

            {/* 日期區間 */}
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-4 nook-shadow mb-6">
                <DateRangePicker value={range} onChange={setRange} />
            </div>

            {loading && <div className="text-center text-slate-400 py-8">載入中...</div>}

            {!loading && data && (
                <>
                    {/* 摘要卡片 */}
                    <div className="grid grid-cols-4 gap-4 mb-6">
                        <div className="bg-gradient-to-br from-sky-50 to-sky-100/50 border border-sky-200 rounded-2xl p-4">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm text-slate-600">超速取締件數</span>
                                <Gauge className="w-5 h-5 text-sky-700" />
                            </div>
                            <div className="text-2xl font-bold text-slate-900 tabular-nums">{curr.total.toLocaleString()}</div>
                            <div className="mt-1 flex items-center gap-2 text-xs">
                                <span className="text-slate-500">去年 {prev.total.toLocaleString()}</span>
                                <PctBadge value={data.summary.diff_pct} />
                            </div>
                        </div>

                        <div className="bg-gradient-to-br from-red-50 to-red-100/50 border border-red-200 rounded-2xl p-4">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm text-slate-600">重度超速 (40+ km/h)</span>
                                <AlertTriangle className="w-5 h-5 text-red-600" />
                            </div>
                            <div className="text-2xl font-bold text-red-600 tabular-nums">{curr.severity.heavy.toLocaleString()}</div>
                            <div className="mt-1 flex items-center gap-2 text-xs">
                                <span className="text-slate-500">占比 {sevTotal > 0 ? (curr.severity.heavy / sevTotal * 100).toFixed(1) : 0}%</span>
                            </div>
                        </div>

                        <div className="bg-gradient-to-br from-orange-50 to-orange-100/50 border border-orange-200 rounded-2xl p-4">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm text-slate-600">超速肇事件數</span>
                                <Zap className="w-5 h-5 text-orange-600" />
                            </div>
                            <div className="text-2xl font-bold text-orange-600 tabular-nums">{crashesC.total}</div>
                            <div className="mt-1 flex items-center gap-2 text-xs">
                                <span className="text-slate-500">A1 {crashesC.a1_crashes} · A2 {crashesC.a2_crashes}</span>
                            </div>
                        </div>

                        <div className="bg-gradient-to-br from-slate-50 to-slate-100/50 border border-slate-200 rounded-2xl p-4">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm text-slate-600">超速事故死傷</span>
                                <AlertTriangle className="w-5 h-5 text-slate-600" />
                            </div>
                            <div className="text-2xl font-bold text-slate-900 tabular-nums">
                                {crashesC.deaths + crashesC.injuries}
                            </div>
                            <div className="mt-1 flex items-center gap-2 text-xs">
                                <span className="text-red-600">💀 {crashesC.deaths}</span>
                                <span className="text-orange-600">🏥 {crashesC.injuries}</span>
                            </div>
                        </div>
                    </div>

                    {/* 超速週趨勢 */}
                    <React.Suspense fallback={<TrendCardSkeleton title="超速週趨勢與專業判讀" />}>
                        <TrendCard
                            range={range}
                            title="超速週趨勢與專業判讀"
                            fetcher={(s, e) => apiClient.getSpeedTrend(s, e)}
                            primaryName="超速取締"
                        />
                    </React.Suspense>

                    {/* 嚴重度分級 + 速限分布 */}
                    <div className="grid grid-cols-2 gap-4 mb-6">
                        {/* 嚴重度分級長條圖 */}
                        <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-5 nook-shadow">
                            <h3 className="font-bold text-slate-800 mb-3 flex items-center gap-2">
                                <Gauge className="w-4 h-4" />
                                超速嚴重度分級
                            </h3>
                            <div className="space-y-3">
                                {[
                                    { key: 'light', label: '輕度 11-20 km/h', color: 'bg-yellow-400', textColor: 'text-yellow-700' },
                                    { key: 'medium', label: '中度 21-40 km/h', color: 'bg-orange-400', textColor: 'text-orange-700' },
                                    { key: 'heavy', label: '重度 40+ km/h ⚠', color: 'bg-red-500', textColor: 'text-red-700' },
                                ].map(tier => {
                                    const count = curr.severity[tier.key] || 0;
                                    const pct = sevTotal > 0 ? (count / sevTotal * 100) : 0;
                                    return (
                                        <div key={tier.key}>
                                            <div className="flex justify-between text-sm mb-1">
                                                <span className={tier.textColor}>{tier.label}</span>
                                                <span className="font-bold tabular-nums">
                                                    {count.toLocaleString()} 件（{pct.toFixed(1)}%）
                                                </span>
                                            </div>
                                            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                                <div className={`h-full ${tier.color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                            {curr.severity.unknown > 0 && (
                                <div className="mt-3 text-[11px] text-slate-400">
                                    註：{curr.severity.unknown} 筆未能解析公里數（法條類違規）已排除計算
                                </div>
                            )}
                        </div>

                        {/* 速限分布 */}
                        <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-5 nook-shadow">
                            <h3 className="font-bold text-slate-800 mb-3">各速限路段超速件數</h3>
                            <div className="space-y-2">
                                {Object.entries(curr.by_limit || {})
                                    .sort(([, a], [, b]) => (b as number) - (a as number))
                                    .map(([limit, count]) => {
                                        const maxCount = Math.max(...Object.values(curr.by_limit || {}).map(v => v as number));
                                        const pct = maxCount > 0 ? ((count as number) / maxCount * 100) : 0;
                                        return (
                                            <div key={limit} className="flex items-center gap-2">
                                                <span className="text-xs text-slate-600 w-20 tabular-nums">限速 {limit}</span>
                                                <div className="flex-1 h-5 bg-slate-100 rounded overflow-hidden">
                                                    <div className="h-full bg-sky-500 rounded" style={{ width: `${pct}%` }} />
                                                </div>
                                                <span className="font-bold text-sm tabular-nums w-16 text-right">{(count as number).toLocaleString()}</span>
                                            </div>
                                        );
                                    })}
                            </div>
                        </div>
                    </div>

                    {/* 派出所取締排名 */}
                    <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-5 nook-shadow mb-6">
                        <h3 className="font-bold text-slate-800 mb-3">各派出所超速取締件數（含去年同期比較）</h3>
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-slate-200 text-slate-500">
                                    <th className="text-left py-2 px-2 font-medium">派出所</th>
                                    <th className="text-right py-2 px-2 font-medium">本期</th>
                                    <th className="text-right py-2 px-2 font-medium">去年</th>
                                    <th className="text-right py-2 px-2 font-medium">變化</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.unit_rows.map((row: any) => (
                                    <tr key={row.unit} className="border-b border-slate-100 hover:bg-slate-50">
                                        <td className="py-2 px-2 text-slate-700">{shortUnit(row.unit)}</td>
                                        <td className="py-2 px-2 text-right font-bold tabular-nums">{row.tickets.toLocaleString()}</td>
                                        <td className="py-2 px-2 text-right text-slate-500 tabular-nums">{row.tickets_prev.toLocaleString()}</td>
                                        <td className="py-2 px-2 text-right"><DiffBadge value={row.tickets_diff} /></td>
                                    </tr>
                                ))}
                                <tr className="bg-slate-50 font-bold">
                                    <td className="py-2 px-2">合計</td>
                                    <td className="py-2 px-2 text-right tabular-nums">{curr.total.toLocaleString()}</td>
                                    <td className="py-2 px-2 text-right text-slate-500 tabular-nums">{prev.total.toLocaleString()}</td>
                                    <td className="py-2 px-2 text-right"><DiffBadge value={curr.total - prev.total} /></td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    {/* 熱點 */}
                    <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-5 nook-shadow">
                        <h3 className="font-bold text-slate-800 mb-3 flex items-center gap-2">
                            <MapPin className="w-4 h-4" />
                            超速取締熱點 Top 5
                        </h3>
                        {data.hotspots.length === 0 ? (
                            <p className="text-slate-400 text-sm">本期無符合條件的熱點資料</p>
                        ) : (
                            <div className="space-y-2">
                                {data.hotspots.map((h: any) => (
                                    <div key={h.rank} className="flex items-center gap-3 py-2 px-3 bg-slate-50 rounded-lg">
                                        <span className="w-6 h-6 bg-sky-100 text-sky-700 rounded-full flex items-center justify-center text-xs font-bold">
                                            {h.rank}
                                        </span>
                                        <div className="flex-1 min-w-0">
                                            <p className="font-semibold text-slate-800 truncate">{h.location}</p>
                                            <p className="text-xs text-slate-500">{h.district}</p>
                                        </div>
                                        <span className="font-bold text-sky-700 tabular-nums">{h.count.toLocaleString()} 件</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </>
            )}
        </div>
    );
};

export default SpeedPerformancePage;
