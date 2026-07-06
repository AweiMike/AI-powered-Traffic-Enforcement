/**
 * PedestrianAnalysisPage - 行人事故發生率專區
 * 行人事故件數 + 佔比 + 死傷人數 + 高齡行人占比 + 肇因分類 + 熱點
 */

import React, { useState, useEffect } from 'react';
import { PersonStanding, TrendingUp, TrendingDown, Minus, AlertTriangle, Users, MapPin } from 'lucide-react';
import DateRangePicker, { type DateRange } from './DateRangePicker';
import { apiClient } from '../api/client';
import TrendCardSkeleton from './TrendCardSkeleton';
import ProfileCard from './ProfileCard';

// recharts 依賴較重，動態載入讓它獨立成 chunk，不灌進主 bundle
const TrendCard = React.lazy(() => import('./TrendCard'));

function defaultRange(): DateRange {
    // 行人事故資料稀少，預設本年度讓使用者看到足夠資料
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

const PedestrianAnalysisPage: React.FC = () => {
    const [range, setRange] = useState<DateRange>(defaultRange);
    const [data, setData] = useState<any>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            try {
                const result = await apiClient.getPedestrianAnalysis(range.startDate, range.endDate);
                setData(result);
            } catch (e) {
                console.error('Failed to fetch pedestrian analysis', e);
            }
            setLoading(false);
        };
        fetchData();
    }, [range]);

    const curr = data?.current;
    const prev = data?.previous;

    return (
        <div className="p-8">
            {/* 標題 */}
            <div className="mb-6">
                <h2 className="text-2xl font-bold text-nook-text flex items-center gap-2">
                    <PersonStanding className="w-6 h-6 text-sky-700" />
                    行人事故發生率
                </h2>
                <p className="text-nook-text/60 mt-1">行人事故件數、占比、死傷與高齡行人特別關注</p>
            </div>

            {/* 日期區間 */}
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-4 nook-shadow mb-6">
                <DateRangePicker value={range} onChange={setRange} />
                <p className="text-[11px] text-slate-500 mt-2">
                    💡 行人事故資料稀少，建議選擇較長期間（半年以上）較具統計意義
                </p>
            </div>

            {loading && <div className="text-center text-slate-400 py-8">載入中...</div>}

            {!loading && data && (
                <>
                    {/* 摘要卡片 */}
                    <div className="grid grid-cols-4 gap-4 mb-6">
                        <div className="bg-gradient-to-br from-sky-50 to-sky-100/50 border border-sky-200 rounded-2xl p-4">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm text-slate-600">行人事故件數</span>
                                <PersonStanding className="w-5 h-5 text-sky-700" />
                            </div>
                            <div className="text-2xl font-bold text-slate-900 tabular-nums">{curr.total}</div>
                            <div className="mt-1 flex items-center gap-2 text-xs">
                                <span className="text-slate-500">去年 {prev.total}</span>
                                <DiffBadge value={curr.total - prev.total} />
                            </div>
                        </div>

                        <div className="bg-gradient-to-br from-purple-50 to-purple-100/50 border border-purple-200 rounded-2xl p-4">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm text-slate-600">占總事故比</span>
                                <AlertTriangle className="w-5 h-5 text-purple-600" />
                            </div>
                            <div className="text-2xl font-bold text-purple-700 tabular-nums">{curr.pct_of_all}%</div>
                            <div className="mt-1 flex items-center gap-2 text-xs">
                                <span className="text-slate-500">去年 {prev.pct_of_all}% · 全事故 {curr.all_crashes}</span>
                            </div>
                        </div>

                        <div className="bg-gradient-to-br from-red-50 to-red-100/50 border border-red-200 rounded-2xl p-4">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm text-slate-600">死傷人數</span>
                                <AlertTriangle className="w-5 h-5 text-red-600" />
                            </div>
                            <div className="text-2xl font-bold text-red-600 tabular-nums">{curr.deaths + curr.injuries}</div>
                            <div className="mt-1 flex items-center gap-2 text-xs">
                                <span className="text-red-700">💀 {curr.deaths} 死</span>
                                <span className="text-orange-700">🏥 {curr.injuries} 傷</span>
                            </div>
                        </div>

                        <div className="bg-gradient-to-br from-amber-50 to-amber-100/50 border border-amber-300 rounded-2xl p-4">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm text-slate-600">⚠ 高齡行人</span>
                                <Users className="w-5 h-5 text-amber-700" />
                            </div>
                            <div className="text-2xl font-bold text-amber-700 tabular-nums">{curr.elderly}</div>
                            <div className="mt-1 flex items-center gap-2 text-xs">
                                <span className="text-slate-600 font-semibold">占行人 {curr.elderly_pct}%</span>
                            </div>
                        </div>
                    </div>

                    {/* 行人傷亡事故週趨勢與專業判讀：A1+A2 傷亡事故為主訊號，A3 財損僅供參考 */}
                    <React.Suspense fallback={<TrendCardSkeleton title="行人傷亡事故週趨勢" />}>
                        <TrendCard
                            range={range}
                            title="行人傷亡事故週趨勢"
                            fetcher={(s, e) => apiClient.getTopicAccidentTrend(s, e, 'pedestrian')}
                            primaryName="A2 受傷"
                            secondaryName="A1 死亡"
                            tertiaryName="A3 財損（參考）"
                            primaryColor="#D97706"
                            secondaryColor="#DC2626"
                        />
                    </React.Suspense>

                    {/* 行人事故特徵剖析 */}
                    <ProfileCard topic="pedestrian" title="行人事故特徵剖析" range={range} />

                    {/* 警訊 banner（若高齡占比 >= 40% 特別提醒）*/}
                    {curr.elderly_pct >= 40 && curr.total > 0 && (
                        <div className="mb-6 bg-amber-50 border-l-4 border-amber-500 rounded-r-xl p-4">
                            <div className="flex items-start gap-3">
                                <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                                <div className="text-sm text-amber-900">
                                    <p className="font-bold mb-1">⚠ 高齡行人特別警訊</p>
                                    <p>本期行人事故中，<strong className="text-amber-800">{curr.elderly_pct}%（{curr.elderly}/{curr.total} 件）</strong>涉及高齡者。高齡行人是交通安全重點保護對象，應優先規劃社區宣導與路口工程改善。</p>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* 嚴重度 + 肇因 */}
                    <div className="grid grid-cols-2 gap-4 mb-6">
                        <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-5 nook-shadow">
                            <h3 className="font-bold text-slate-800 mb-3">嚴重度分布</h3>
                            <div className="space-y-3">
                                {[
                                    { label: 'A1 死亡', count: curr.a1, color: 'bg-red-500', textColor: 'text-red-700' },
                                    { label: 'A2 受傷', count: curr.a2, color: 'bg-orange-400', textColor: 'text-orange-700' },
                                    { label: 'A3 財損', count: curr.a3, color: 'bg-yellow-400', textColor: 'text-yellow-700' },
                                ].map(tier => {
                                    const pct = curr.total > 0 ? (tier.count / curr.total * 100) : 0;
                                    return (
                                        <div key={tier.label}>
                                            <div className="flex justify-between text-sm mb-1">
                                                <span className={tier.textColor}>{tier.label}</span>
                                                <span className="font-bold tabular-nums">
                                                    {tier.count} 件（{pct.toFixed(1)}%）
                                                </span>
                                            </div>
                                            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                                <div className={`h-full ${tier.color} rounded-full`} style={{ width: `${pct}%` }} />
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        {/* 肇因分類 */}
                        <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-5 nook-shadow">
                            <h3 className="font-bold text-slate-800 mb-3">肇因分類</h3>
                            <div className="space-y-2.5 text-sm">
                                <div className="flex justify-between items-center py-2 border-b border-slate-100">
                                    <div>
                                        <p className="font-semibold text-slate-800">🚗 駕駛違規</p>
                                        <p className="text-xs text-slate-500">未禮讓行人、車輛未暫停讓行人等</p>
                                    </div>
                                    <span className="font-bold text-red-600 tabular-nums">{curr.fault_breakdown.driver_fault}</span>
                                </div>
                                <div className="flex justify-between items-center py-2 border-b border-slate-100">
                                    <div>
                                        <p className="font-semibold text-slate-800">🚶 行人違規</p>
                                        <p className="text-xs text-slate-500">穿越道路未注意、未依標誌穿越等</p>
                                    </div>
                                    <span className="font-bold text-orange-600 tabular-nums">{curr.fault_breakdown.pedestrian_fault}</span>
                                </div>
                                <div className="flex justify-between items-center py-2">
                                    <div>
                                        <p className="font-semibold text-slate-800">❓ 其他/未分類</p>
                                        <p className="text-xs text-slate-500">其他事故原因或無明確歸屬</p>
                                    </div>
                                    <span className="font-bold text-slate-500 tabular-nums">{curr.fault_breakdown.other}</span>
                                </div>
                            </div>
                            <p className="text-[11px] text-slate-400 mt-3">
                                註：肇因依 Crash.cause 欄位關鍵字推論，非 100% 精確。
                            </p>
                        </div>
                    </div>

                    {/* 熱點 */}
                    <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-5 nook-shadow">
                        <h3 className="font-bold text-slate-800 mb-3 flex items-center gap-2">
                            <MapPin className="w-4 h-4" />
                            行人事故熱點 Top 5（工程改善建議參考）
                        </h3>
                        {data.hotspots.length === 0 ? (
                            <p className="text-slate-400 text-sm py-4">本期無行人事故資料</p>
                        ) : (
                            <div className="space-y-2">
                                {data.hotspots.map((h: any) => (
                                    <div key={h.rank} className="flex items-center gap-3 py-2.5 px-3 bg-slate-50 rounded-lg">
                                        <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                                            h.rank === 1 ? 'bg-red-100 text-red-700' :
                                            h.rank === 2 ? 'bg-orange-100 text-orange-700' :
                                            h.rank === 3 ? 'bg-yellow-100 text-yellow-700' :
                                            'bg-slate-200 text-slate-600'
                                        }`}>
                                            {h.rank}
                                        </span>
                                        <div className="flex-1 min-w-0">
                                            <p className="font-semibold text-slate-800 truncate" title={h.location}>{h.location}</p>
                                            <p className="text-xs text-slate-500">{h.district}</p>
                                        </div>
                                        <div className="flex items-center gap-3 text-xs">
                                            <span className="text-slate-600 tabular-nums">{h.count} 件</span>
                                            {h.elderly_count > 0 && (
                                                <span className="text-amber-700 font-semibold tabular-nums" title="高齡行人">
                                                    高齡 {h.elderly_count}
                                                </span>
                                            )}
                                            {h.deaths > 0 && (
                                                <span className="text-red-700 font-bold tabular-nums">💀 {h.deaths}</span>
                                            )}
                                            {h.injuries > 0 && (
                                                <span className="text-orange-700 tabular-nums">🏥 {h.injuries}</span>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                        <p className="text-[11px] text-slate-400 mt-3">
                            💡 出現在此清單的地點，建議會同交通工程單位評估斑馬線、號誌、照明、行人庇護島等改善措施。
                        </p>
                    </div>
                </>
            )}
        </div>
    );
};

export default PedestrianAnalysisPage;
