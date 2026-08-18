/**
 * 高齡者防治頁面 - 專注於高齡者事故分析與防治
 */
import React, { useState, useEffect, useMemo } from 'react';
import { useAccidentHotspots, useAccidentPeakTimes } from '../hooks/useAPI';
import { AccidentHotspot, ShiftData, apiClient } from '../api/client';
import DateRangePicker, { type DateRange, getCompareRange } from './DateRangePicker';
import ProfileCard from './ProfileCard';
import TrendCardSkeleton from './TrendCardSkeleton';

// recharts 依賴較重，動態載入讓它獨立成 chunk，不灌進主 bundle
const TrendCard = React.lazy(() => import('./TrendCard'));
const SignalCheckCard = React.lazy(() => import('./SignalCheckCard'));

// 同期比較標籤
const YoYBadge: React.FC<{ current: number; previous: number }> = ({ current, previous }) => {
    if (previous === 0 && current === 0) return <span className="text-xs text-gray-400">去年 0</span>;
    const diff = current - previous;
    const color = diff > 0 ? 'text-red-600' : diff < 0 ? 'text-green-600' : 'text-gray-500';
    const arrow = diff > 0 ? '▲' : diff < 0 ? '▼' : '—';
    return (
        <span className={`text-xs ${color}`}>
            去年 {previous} {arrow}{Math.abs(diff) > 0 ? Math.abs(diff) : ''}
        </span>
    );
};

// 時段分析圖表 (簡化版，專注事故)
const ShiftChart: React.FC<{ shifts: ShiftData[]; peakShifts: string[] }> = ({ shifts, peakShifts }) => {
    const maxValue = Math.max(...shifts.map(s => s.accidents)) || 1;

    return (
        <div className="space-y-2">
            {shifts.map((shift) => {
                const isPeak = peakShifts.includes(shift.shift_id);
                const accidentWidth = (shift.accidents / maxValue) * 100;
                // 晨間與傍晚特別標註
                const isExerciseTime = ['03', '04', '09', '10'].includes(shift.shift_id); // 04-08, 16-20

                return (
                    <div key={shift.shift_id} className={`p-2 rounded-lg ${isPeak ? 'bg-orange-50 border border-orange-200' : 'bg-gray-50'}`}>
                        <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium text-nook-text">
                                {shift.time_range}
                                {isExerciseTime && <span className="ml-2 text-green-600">🏃 晨昏活動</span>}
                            </span>
                            <span className="text-xs font-bold text-orange-600">事故 {shift.accidents}</span>
                        </div>
                        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div
                                className={`h-full rounded-full transition-all ${isPeak ? 'bg-orange-500' : 'bg-gray-400'}`}
                                style={{ width: `${accidentWidth}%` }}
                            />
                        </div>
                    </div>
                );
            })}
        </div>
    );
};

// 高齡者熱點卡片
const ElderlyHotspotCard: React.FC<{ hotspot: AccidentHotspot; rank: number; onSelect: () => void; selected: boolean }> =
    ({ hotspot, rank, onSelect, selected }) => {
        return (
            <div
                onClick={onSelect}
                className={`bg-white/80 rounded-2xl p-4 nook-shadow cursor-pointer transition-all hover:shadow-lg ${selected ? 'ring-2 ring-orange-400' : ''}`}
            >
                <div className="flex items-center gap-3 mb-3">
                    <span className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${rank === 1 ? 'bg-orange-500 text-white' :
                        rank === 2 ? 'bg-orange-400 text-white' :
                            'bg-orange-300 text-white'
                        }`}>
                        {rank}
                    </span>
                    <h4 className="font-bold text-nook-text">{hotspot.district}</h4>
                </div>

                <div className="grid grid-cols-5 gap-2 text-center text-xs mb-3">
                    <div className="bg-orange-50 rounded-lg p-2">
                        <p className="font-bold text-lg text-orange-700">{hotspot.accidents.total}</p>
                        <p className="text-orange-600">事故</p>
                    </div>
                    <div className="bg-red-50 rounded-lg p-2">
                        <p className="font-bold text-lg text-red-600">{hotspot.accidents.a1_count}</p>
                        <p className="text-red-500">A1</p>
                    </div>
                    <div className="bg-yellow-50 rounded-lg p-2">
                        <p className="font-bold text-lg text-yellow-600">{hotspot.accidents.a2_count}</p>
                        <p className="text-yellow-500">A2</p>
                    </div>
                    <div className="bg-gray-100 rounded-lg p-2">
                        <p className="font-bold text-lg text-gray-800">{hotspot.accidents.death_count ?? 0}</p>
                        <p className="text-gray-600">死亡</p>
                    </div>
                    <div className="bg-orange-100 rounded-lg p-2">
                        <p className="font-bold text-lg text-orange-600">{hotspot.accidents.injury_count ?? 0}</p>
                        <p className="text-orange-500">受傷</p>
                    </div>
                </div>
            </div>
        );
    };

const ElderlyPreventionPage: React.FC = () => {
    const [selectedDistrict, setSelectedDistrict] = useState<string | null>(null);
    const [dateRange, setDateRange] = useState<DateRange>(() => {
        const now = new Date();
        const start = new Date(now.getFullYear(), 0, 1);
        const fmt = (d: Date) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
        return { startDate: fmt(start), endDate: fmt(now) };
    });
    const [vehicleData, setVehicleData] = useState<any>(null);
    // 執法落差倍數（對象錯位）：該族群占事故比重 ÷ 占舉發比重
    const [gapRatio, setGapRatio] = useState<any>(null);

    // 去年同期日期
    const prevRange = useMemo(() => getCompareRange(dateRange), [dateRange]);

    // isElderly = true 強制篩選高齡者數據
    const { data: hotspots, loading: hotspotsLoading } = useAccidentHotspots(365, true, dateRange.startDate, dateRange.endDate);
    const { data: prevHotspots } = useAccidentHotspots(365, true, prevRange.startDate, prevRange.endDate);
    const { data: peakTimes, loading: peakLoading } = useAccidentPeakTimes(selectedDistrict || '__SKIP__', 365, true, dateRange.startDate, dateRange.endDate);

    // 載入車種分析數據
    useEffect(() => {
        const fetchVehicleData = async () => {
            try {
                const data = await apiClient.getElderlyVehicleAnalysis(365, dateRange.startDate, dateRange.endDate);
                setVehicleData(data);
            } catch (e) {
                console.error('Failed to load vehicle analysis:', e);
            }
        };
        fetchVehicleData();

        let alive = true;
        apiClient
            .getEnforcementGapRatio('elderly', dateRange.startDate, dateRange.endDate, true)
            .then((d) => { if (alive) setGapRatio(d?.supported ? d : null); })
            .catch(() => { if (alive) setGapRatio(null); });
        return () => { alive = false; };
    }, [dateRange]);

    return (
        <div className="p-8 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-nook-text mb-2">👵 高齡者事故防制專區</h2>
                    <p className="text-nook-text/60">針對 65 歲以上長者事故分析與防治建議</p>
                    <p className="text-xs text-accent mt-1.5 bg-accent-soft/50 inline-block px-2.5 py-1 rounded-lg">
                        口徑：<b>任一當事者年滿 65 歲</b>即計入（道安會報口徑）。
                        舊版僅以「代表當事者」判定，會漏掉高齡者<b>被撞</b>的案件而低估 54%。
                    </p>
                </div>
                <DateRangePicker value={dateRange} onChange={setDateRange} showCompare={true} />
            </div>

            {/* 總覽數據 */}
            {hotspots && (
                <div className="grid grid-cols-6 gap-4">
                    <div className="bg-white/80 rounded-2xl p-4 nook-shadow text-center border-b-4 border-orange-500">
                        <p className="text-4xl font-bold text-nook-text">{hotspots.summary.total_accidents}</p>
                        <p className="text-sm text-nook-text/60">高齡事故總數</p>
                        {prevHotspots && <YoYBadge current={hotspots.summary.total_accidents} previous={prevHotspots.summary.total_accidents} />}
                    </div>
                    <div className="bg-red-50 rounded-2xl p-4 nook-shadow text-center border-b-4 border-red-500">
                        <p className="text-4xl font-bold text-red-600">{hotspots.summary.a1_total}</p>
                        <p className="text-sm text-red-500">A1 事故件數</p>
                        {prevHotspots && <YoYBadge current={hotspots.summary.a1_total} previous={prevHotspots.summary.a1_total} />}
                    </div>
                    <div className="bg-yellow-50 rounded-2xl p-4 nook-shadow text-center border-b-4 border-yellow-500">
                        <p className="text-4xl font-bold text-yellow-600">{hotspots.summary.a2_total}</p>
                        <p className="text-sm text-yellow-500">A2 事故件數</p>
                        {prevHotspots && <YoYBadge current={hotspots.summary.a2_total} previous={prevHotspots.summary.a2_total} />}
                    </div>
                    <div className="bg-gray-50 rounded-2xl p-4 nook-shadow text-center border-b-4 border-gray-800">
                        <p className="text-4xl font-bold text-gray-800">{hotspots.summary.death_total ?? 0}</p>
                        <p className="text-sm text-gray-600">死亡人數</p>
                        {prevHotspots && <YoYBadge current={hotspots.summary.death_total ?? 0} previous={prevHotspots.summary.death_total ?? 0} />}
                    </div>
                    <div className="bg-orange-50 rounded-2xl p-4 nook-shadow text-center border-b-4 border-orange-400">
                        <p className="text-4xl font-bold text-orange-600">{hotspots.summary.injury_total ?? 0}</p>
                        <p className="text-sm text-orange-500">受傷人數</p>
                        {prevHotspots && <YoYBadge current={hotspots.summary.injury_total ?? 0} previous={prevHotspots.summary.injury_total ?? 0} />}
                    </div>
                    <div className="bg-blue-50 rounded-2xl p-4 nook-shadow text-center border-b-4 border-blue-500">
                        <p className="text-4xl font-bold text-blue-600">{hotspots.hotspots.length}</p>
                        <p className="text-sm text-blue-500">發生區域數</p>
                    </div>
                </div>
            )}

            {/* 訊號／雜訊判讀：先確認變化是真是假，再往下看趨勢與熱點 */}
            <React.Suspense fallback={<div className="bg-white/80 rounded-2xl p-6 nook-shadow h-40 animate-pulse" />}>
                <SignalCheckCard range={dateRange} topic="elderly" />
            </React.Suspense>

            {/* 執法落差倍數（對象錯位）—— 與 Wave 29 執法錯位引擎（空間錯位）互補 */}
            {gapRatio && (
                <div className="bg-white/80 rounded-2xl p-5 nook-shadow flex items-center gap-6 flex-wrap">
                    <div className="flex items-baseline gap-2">
                        <span className="text-3xl font-bold text-nook-text tabular-nums tracking-tight">
                            {gapRatio.gap_ratio}
                        </span>
                        <span className="text-sm font-semibold text-nook-text/70">倍執法落差</span>
                    </div>
                    <div className="text-xs text-nook-text/60 leading-relaxed">
                        高齡者占傷亡事故 <b className="text-nook-text">{gapRatio.crash.share_pct}%</b>
                        （{gapRatio.crash.topic}／{gapRatio.crash.total} 件），
                        占舉發僅 <b className="text-nook-text">{gapRatio.ticket.share_pct}%</b>
                        （{gapRatio.ticket.topic}／{gapRatio.ticket.total} 件）
                        {typeof gapRatio.ticket.post_crash_pct === 'number' && (
                            <>；其中 <b className="text-nook-text">{gapRatio.ticket.post_crash_pct}%</b> 為肇事後補單</>
                        )}
                    </div>
                    <div className="text-xs px-3 py-1.5 rounded-full bg-amber-100 text-amber-800 font-semibold">
                        {gapRatio.verdict}
                    </div>
                    <p className="text-[11px] text-nook-text/40 basis-full leading-relaxed">
                        ⚠️ 倍數高不等於應多開單：高齡者有相當比例為非肇責方（被撞），
                        此類案件之防制對象應為其他用路人。請併看下方責任結構。
                    </p>
                </div>
            )}

            {/* 高齡者傷亡事故週趨勢與專業判讀：A1+A2 傷亡事故為主訊號，A3 財損僅供參考 */}
            <React.Suspense fallback={<TrendCardSkeleton title="高齡者傷亡事故週趨勢" />}>
                <TrendCard
                    range={dateRange}
                    title="高齡者傷亡事故週趨勢"
                    fetcher={(s, e) => apiClient.getTopicAccidentTrend(s, e, 'elderly')}
                    primaryName="A2 受傷"
                    secondaryName="A1 死亡"
                    tertiaryName="A3 財損（參考）"
                    primaryColor="#D97706"
                    secondaryColor="#DC2626"
                />
            </React.Suspense>

            {/* 高齡者事故特徵剖析 */}
            <ProfileCard topic="elderly" title="高齡者事故特徵剖析" range={dateRange} />

            <div className="grid grid-cols-12 gap-6">
                {/* 左欄：高齡事故熱區 */}
                <div className="col-span-4 space-y-4">
                    <div className="bg-slate-100 rounded-2xl p-4 border-l-4 border-warning">
                        <h4 className="font-bold text-slate-800 mb-1">📍 高齡事故熱區</h4>
                        <p className="text-xs text-slate-600">依長者事故數量排序</p>
                    </div>
                    {hotspotsLoading ? (
                        <div className="text-center py-10 text-gray-400">載入中...</div>
                    ) : (
                        <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
                            {hotspots?.hotspots.map((hotspot, idx) => (
                                <ElderlyHotspotCard
                                    key={hotspot.district}
                                    hotspot={hotspot}
                                    rank={idx + 1}
                                    onSelect={() => setSelectedDistrict(hotspot.district)}
                                    selected={selectedDistrict === hotspot.district}
                                />
                            ))}
                        </div>
                    )}
                </div>

                {/* 中欄：時段分析 */}
                <div className="col-span-5 space-y-4">
                    <div className="bg-slate-100 rounded-2xl p-4 border-l-4 border-accent">
                        <h4 className="font-bold text-slate-800 mb-1">⏰ 事故時段分析</h4>
                        <p className="text-xs text-slate-600">
                            {selectedDistrict ? `${selectedDistrict} 高齡事故分布` : '請選擇區域查看'}
                        </p>
                    </div>
                    {selectedDistrict && peakTimes ? (
                        <div className="bg-white/80 rounded-2xl p-6 nook-shadow">
                            <h5 className="font-bold text-nook-text mb-4 text-lg">{peakTimes.district}</h5>
                            <ShiftChart shifts={peakTimes.shifts} peakShifts={peakTimes.recommendations.priority_shifts} />
                            <div className="mt-6 p-4 bg-orange-50 rounded-xl border border-orange-200">
                                <h6 className="font-bold text-orange-800 mb-2">💡 防治重點</h6>
                                <p className="text-sm text-orange-700 mb-2">
                                    長者事故常發生於<strong>晨間運動 (04-06)</strong> 或 <strong>傍晚買菜 (16-18)</strong> 時段。
                                </p>
                                <p className="text-sm text-gray-600">
                                    建議加強{peakTimes.recommendations.priority_shifts.length > 0 ? '事故高峰時段' : '晨昏時段'}的護老勤務與宣導。
                                </p>
                            </div>
                        </div>
                    ) : (
                        <div className="bg-white/80 rounded-2xl p-12 text-center h-64 flex items-center justify-center">
                            <p className="text-nook-text/40 text-lg">👈 請點選左側熱點區域</p>
                        </div>
                    )}
                </div>

                {/* 右欄：車種分析 + 宣導建議 */}
                <div className="col-span-3 space-y-4">
                    {/* 車種分析 */}
                    <div className="bg-purple-100 rounded-2xl p-4">
                        <h4 className="font-bold text-purple-800 mb-1">🚗 車種分析</h4>
                        <p className="text-xs text-purple-600">高齡者涉及事故車種分佈</p>
                    </div>

                    {vehicleData && vehicleData.vehicle_breakdown && vehicleData.vehicle_breakdown.length > 0 ? (
                        <div className="bg-white/80 rounded-2xl p-4 nook-shadow">
                            <div className="space-y-2">
                                {vehicleData.vehicle_breakdown.slice(0, 5).map((v: any, idx: number) => (
                                    <div key={idx} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                                        <div className="flex items-center gap-2">
                                            <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${idx === 0 ? 'bg-purple-500 text-white' : 'bg-purple-200 text-purple-700'
                                                }`}>{idx + 1}</span>
                                            <span className="text-sm font-medium text-nook-text">{v.vehicle_type}</span>
                                        </div>
                                        <div className="text-right">
                                            <span className="text-lg font-bold text-purple-600">{v.count}</span>
                                            <span className="text-xs text-gray-500 ml-1">({v.percentage}%)</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            {vehicleData.insights && (
                                <div className="mt-3 p-3 bg-purple-50 rounded-lg border border-purple-200">
                                    <p className="text-xs text-purple-700">
                                        💡 {vehicleData.insights.recommendation}
                                    </p>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="bg-white/80 rounded-2xl p-4 nook-shadow text-center text-gray-400">
                            暫無車種資料
                        </div>
                    )}

                    {/* 宣導建議 */}
                    <div className="bg-slate-100 rounded-2xl p-4 border-l-4 border-accent">
                        <h4 className="font-bold text-slate-800 mb-1">📢 防治宣導建議</h4>
                        <p className="text-xs text-slate-600">針對長者特性之策略</p>
                    </div>

                    <div className="bg-white rounded-2xl p-4 nook-shadow space-y-2.5">
                        <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 flex gap-3">
                            <span className="text-xl shrink-0">🦺</span>
                            <div className="min-w-0">
                                <h5 className="font-semibold text-slate-800 mb-0.5 text-sm">亮衣與反光配件</h5>
                                <p className="text-xs text-slate-500">晨昏外出時應穿著鮮豔衣物。</p>
                            </div>
                        </div>

                        <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 flex gap-3">
                            <span className="text-xl shrink-0">🛵</span>
                            <div className="min-w-0">
                                <h5 className="font-semibold text-slate-800 mb-0.5 text-sm">兩段式左轉</h5>
                                <p className="text-xs text-slate-500">騎乘機車應落實兩段式左轉。</p>
                            </div>
                        </div>

                        <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 flex gap-3">
                            <span className="text-xl shrink-0">🚌</span>
                            <div className="min-w-0">
                                <h5 className="font-semibold text-slate-800 mb-0.5 text-sm">大型車視線死角</h5>
                                <p className="text-xs text-slate-500">遠離大型車輛視線死角範圍。</p>
                            </div>
                        </div>
                    </div>

                    <div className="bg-accent-soft rounded-2xl p-4 text-center">
                        <p className="text-sm text-accent-hover font-medium">✨ 「長者平安，全家心安」</p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ElderlyPreventionPage;
