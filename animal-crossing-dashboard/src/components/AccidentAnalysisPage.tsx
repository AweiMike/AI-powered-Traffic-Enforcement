/**
 * 事故分析頁面 - 獨立的事故熱點與趨勢分析
 * 參考「歸仁分局114年12月份順安專案執法與事故關聯性分析」樣式
 */
import React, { useState, useMemo } from 'react';
import { useAccidentHotspots, useAccidentPeakTimes, useCrossAnalysis } from '../hooks/useAPI';
import { AccidentHotspot, ShiftData } from '../api/client';
import DateRangePicker, { type DateRange, getCompareRange } from './DateRangePicker';

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
// AccidentViolationMap removed — 地圖視覺化頁面已完整呈現點位分布

// 時段分析圖表
const ShiftChart: React.FC<{ shifts: ShiftData[]; peakShifts: string[] }> = ({ shifts, peakShifts }) => {
    const maxValue = Math.max(...shifts.map(s => Math.max(s.accidents, s.violations))) || 1;

    return (
        <div className="space-y-2">
            {shifts.map((shift) => {
                const isPeak = peakShifts.includes(shift.shift_id);
                const accidentWidth = (shift.accidents / maxValue) * 100;
                const violationWidth = (shift.violations / maxValue) * 100;

                return (
                    <div key={shift.shift_id} className={`p-2 rounded-lg ${isPeak ? 'bg-red-50 border border-red-200' : 'bg-gray-50'}`}>
                        <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium text-nook-text">
                                {shift.time_range}
                                {isPeak && <span className="ml-2 text-red-500">🔥 建議加強</span>}
                            </span>
                            <div className="flex gap-4 text-xs">
                                <span className="text-red-500">事故 {shift.accidents}</span>
                                <span className="text-blue-500">違規 {shift.violations}</span>
                            </div>
                        </div>
                        <div className="flex gap-1 h-3">
                            <div className="bg-red-400 rounded-sm transition-all" style={{ width: `${accidentWidth}%` }} />
                            <div className="bg-blue-400 rounded-sm transition-all" style={{ width: `${violationWidth}%` }} />
                        </div>
                    </div>
                );
            })}
        </div>
    );
};

// 事故熱點卡片
const HotspotCard: React.FC<{ hotspot: AccidentHotspot; rank: number; onSelect: () => void; selected: boolean }> =
    ({ hotspot, rank, onSelect, selected }) => {
        return (
            <div
                onClick={onSelect}
                className={`bg-white/80 rounded-2xl p-4 nook-shadow cursor-pointer transition-all hover:shadow-lg ${selected ? 'ring-2 ring-nook-leaf' : ''}`}
            >
                <div className="flex items-center gap-3 mb-3">
                    <span className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${rank === 1 ? 'bg-red-500 text-white' :
                        rank === 2 ? 'bg-orange-500 text-white' :
                            'bg-yellow-500 text-white'
                        }`}>
                        {rank}
                    </span>
                    <h4 className="font-bold text-nook-text">{hotspot.district}</h4>
                </div>

                <div className="grid grid-cols-4 gap-2 text-center text-xs mb-3">
                    <div className="bg-gray-50 rounded-lg p-2">
                        <p className="font-bold text-lg text-nook-text">{hotspot.accidents.total}</p>
                        <p className="text-nook-text/60">事故</p>
                    </div>
                    <div className="bg-red-50 rounded-lg p-2">
                        <p className="font-bold text-lg text-red-600">{hotspot.accidents.a1_count}</p>
                        <p className="text-red-500">A1</p>
                    </div>
                    <div className="bg-orange-50 rounded-lg p-2">
                        <p className="font-bold text-lg text-orange-600">{hotspot.accidents.a2_count}</p>
                        <p className="text-orange-500">A2</p>
                    </div>
                    <div className="bg-yellow-50 rounded-lg p-2">
                        <p className="font-bold text-lg text-yellow-600">{hotspot.accidents.a3_count}</p>
                        <p className="text-yellow-500">A3</p>
                    </div>
                </div>

                <div className="bg-nook-leaf/10 rounded-lg p-2 text-xs text-nook-leaf-dark">
                    💡 {hotspot.recommendation.enforcement_focus}
                </div>
            </div>
        );
    };

// 主頁面組件
const AccidentAnalysisPage: React.FC = () => {
    const [selectedDistrict, setSelectedDistrict] = useState<string | null>(null);
    const [dateRange, setDateRange] = useState<DateRange>(() => {
        const now = new Date();
        const start = new Date(now.getFullYear(), 0, 1);
        const fmt = (d: Date) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
        return { startDate: fmt(start), endDate: fmt(now) };
    });
    const [activeTab, setActiveTab] = useState<'list' | 'dui'>('list');

    // 去年同期
    const prevRange = useMemo(() => getCompareRange(dateRange), [dateRange]);

    const { data: hotspots, loading: hotspotsLoading } = useAccidentHotspots(365, false, dateRange.startDate, dateRange.endDate);
    const { data: prevHotspots } = useAccidentHotspots(365, false, prevRange.startDate, prevRange.endDate);
    const { data: peakTimes, loading: peakLoading } = useAccidentPeakTimes(selectedDistrict || '__SKIP__', 365, false, dateRange.startDate, dateRange.endDate);
    const { data: crossAnalysis, loading: crossLoading } = useCrossAnalysis(selectedDistrict || undefined, 365, dateRange.startDate, dateRange.endDate);

    const tabs = [
        { id: 'list' as const, label: '📊 詳細分析', desc: '時段與缺口' },
        { id: 'dui' as const, label: '🍺 酒駕分析', desc: '酒駕肇事熱點' },
    ];

    return (
        <div className="p-8">
            {/* 標題與篩選器 */}
            <div className="mb-6 flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-nook-text mb-2">🎯 執法缺口分析</h2>
                    <p className="text-nook-text/60">事故熱點、時段分析與精準執法建議</p>
                </div>
                <div className="bg-white/80 rounded-2xl px-4 py-2 nook-shadow">
                    <DateRangePicker value={dateRange} onChange={setDateRange} showCompare={true} />
                </div>
            </div>

            {/* 總覽統計 */}
            {hotspots && (
                <div className="grid grid-cols-5 gap-4 mb-6">
                    <div className="bg-white/80 rounded-2xl p-4 nook-shadow text-center">
                        <p className="text-3xl font-bold text-nook-text">{hotspots.summary.total_accidents}</p>
                        <p className="text-sm text-nook-text/60">事故總數</p>
                        {prevHotspots && <YoYBadge current={hotspots.summary.total_accidents} previous={prevHotspots.summary.total_accidents} />}
                    </div>
                    <div className="bg-red-50 rounded-2xl p-4 text-center border-l-4 border-red-500">
                        <p className="text-3xl font-bold text-red-600">{hotspots.summary.a1_total}</p>
                        <p className="text-sm text-red-500">A1 死亡</p>
                        {prevHotspots && <YoYBadge current={hotspots.summary.a1_total} previous={prevHotspots.summary.a1_total} />}
                    </div>
                    <div className="bg-orange-50 rounded-2xl p-4 text-center border-l-4 border-orange-500">
                        <p className="text-3xl font-bold text-orange-600">{hotspots.summary.a2_total}</p>
                        <p className="text-sm text-orange-500">A2 受傷</p>
                        {prevHotspots && <YoYBadge current={hotspots.summary.a2_total} previous={prevHotspots.summary.a2_total} />}
                    </div>
                    <div className="bg-yellow-50 rounded-2xl p-4 text-center border-l-4 border-yellow-500">
                        <p className="text-3xl font-bold text-yellow-600">{hotspots.summary.a3_total}</p>
                        <p className="text-sm text-yellow-500">A3 財損</p>
                        {prevHotspots && <YoYBadge current={hotspots.summary.a3_total} previous={prevHotspots.summary.a3_total} />}
                    </div>
                    <div className="bg-blue-50 rounded-2xl p-4 text-center border-l-4 border-blue-500">
                        <p className="text-3xl font-bold text-blue-600">{hotspots.total_districts}</p>
                        <p className="text-sm text-blue-500">涵蓋區域</p>
                    </div>
                </div>
            )}

            {/* 分頁切換 */}
            <div className="flex gap-2 mb-6">
                {tabs.map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`px-6 py-3 rounded-2xl font-medium transition-all ${activeTab === tab.id ? 'bg-nook-leaf text-white shadow-lg' : 'bg-white/60 text-nook-text hover:bg-nook-leaf/10'
                            }`}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* 詳細分析分頁 */}
            {activeTab === 'list' && (
                <div className="grid grid-cols-3 gap-6">
                    {/* 左欄：事故熱點排名 */}
                    <div className="space-y-4">
                        <div className="bg-nook-orange/10 rounded-2xl p-4">
                            <h4 className="font-bold text-nook-text mb-1">📊 區域事故排名</h4>
                            <p className="text-xs text-nook-text/70">點擊區域查看詳細時段分析</p>
                        </div>
                        {hotspotsLoading ? (
                            <div className="bg-white/80 rounded-2xl p-8 text-center">
                                <p className="text-nook-text/60">載入中...</p>
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {hotspots?.hotspots.map((hotspot, idx) => (
                                    <HotspotCard
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
                    <div className="space-y-4">
                        <div className="bg-nook-sky/10 rounded-2xl p-4">
                            <h4 className="font-bold text-nook-text mb-1">⏰ 時段分析</h4>
                            <p className="text-xs text-nook-text/70">
                                {selectedDistrict ? `${selectedDistrict} 的 12 班別事故與違規分布` : '請先選擇區域'}
                            </p>
                        </div>
                        {selectedDistrict && peakTimes ? (
                            <div className="bg-white/80 rounded-2xl p-4 nook-shadow">
                                <div className="flex justify-between items-center mb-4">
                                    <h5 className="font-bold text-nook-text">{peakTimes.district}</h5>
                                    <div className="flex gap-2 text-xs">
                                        <span className="flex items-center gap-1">
                                            <span className="w-3 h-3 bg-red-400 rounded-sm"></span> 事故
                                        </span>
                                        <span className="flex items-center gap-1">
                                            <span className="w-3 h-3 bg-blue-400 rounded-sm"></span> 違規
                                        </span>
                                    </div>
                                </div>
                                <ShiftChart shifts={peakTimes.shifts} peakShifts={peakTimes.recommendations.priority_shifts} />
                                <div className="mt-4 p-3 bg-red-50 rounded-lg">
                                    <p className="text-sm font-medium text-red-700">
                                        🚨 {peakTimes.recommendations.enforcement_suggestion}
                                    </p>
                                </div>
                            </div>
                        ) : (
                            <div className="bg-white/80 rounded-2xl p-8 text-center">
                                <p className="text-nook-text/40">👈 請先從左側選擇一個區域</p>
                            </div>
                        )}
                    </div>

                    {/* 右欄：執法缺口分析 */}
                    <div className="space-y-4">
                        <div className="bg-red-50 border border-red-200 rounded-2xl p-4">
                            <h4 className="font-bold text-red-700 mb-1">🔍 執法缺口分析</h4>
                            <p className="text-xs text-red-600/70">事故多但取締少的時段</p>
                        </div>
                        {crossAnalysis ? (
                            <>
                                <div className="grid grid-cols-3 gap-2 text-center">
                                    <div className="bg-red-50 rounded-xl p-3 border border-red-200">
                                        <p className="text-xl font-bold text-red-600">{crossAnalysis.summary.high_priority_count}</p>
                                        <p className="text-xs text-red-500">高優先</p>
                                    </div>
                                    <div className="bg-orange-50 rounded-xl p-3">
                                        <p className="text-xl font-bold text-orange-600">{crossAnalysis.summary.medium_priority_count}</p>
                                        <p className="text-xs text-orange-500">中優先</p>
                                    </div>
                                    <div className="bg-green-50 rounded-xl p-3">
                                        <p className="text-xl font-bold text-green-600">{crossAnalysis.summary.low_priority_count}</p>
                                        <p className="text-xs text-green-500">低優先</p>
                                    </div>
                                </div>
                                <div className="bg-white/80 rounded-2xl p-4 nook-shadow">
                                    <h5 className="font-bold text-nook-text mb-3">🚨 建議優先執法時段</h5>
                                    <div className="space-y-2 max-h-64 overflow-y-auto">
                                        {crossAnalysis.recommendations.high_priority_targets.slice(0, 5).map((item, idx) => (
                                            <div key={idx} className="bg-red-50 rounded-lg p-3 border border-red-100">
                                                <div className="flex justify-between items-center">
                                                    <span className="font-medium text-nook-text">{item.district}</span>
                                                    <span className="text-xs bg-red-200 text-red-700 px-2 py-1 rounded-full">{item.time_range}</span>
                                                </div>
                                                <div className="flex gap-4 mt-2 text-xs">
                                                    <span className="text-red-600">事故 {item.accidents}</span>
                                                    <span className="text-blue-600">違規 {item.violations}</span>
                                                    <span className="text-orange-600 font-bold">缺口 {item.enforcement_gap}</span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </>
                        ) : (
                            <div className="bg-white/80 rounded-2xl p-8 text-center">
                                <p className="text-nook-text/60">載入中...</p>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* 酒駕分析分頁 */}
            {activeTab === 'dui' && (
                <div className="space-y-6">
                    {/* 酒駕統計概要 - 肇事為主，績效為輔 */}
                    <div className="grid grid-cols-5 gap-4">
                        {/* 核心：酒駕肇事 */}
                        <div className="bg-red-50 rounded-2xl p-4 nook-shadow text-center border-l-4 border-red-600">
                            <p className="text-3xl font-bold text-red-700">
                                {hotspots?.summary?.dui_crash_total || 0}
                            </p>
                            <p className="text-sm text-red-600 font-medium">🚨 酒駕肇事</p>
                            <p className="text-xs text-red-400">（核心：降低事故）</p>
                        </div>
                        {/* A1 死亡 */}
                        <div className="bg-orange-50 rounded-2xl p-4 nook-shadow text-center border-l-4 border-orange-500">
                            <p className="text-3xl font-bold text-orange-600">
                                {hotspots?.summary?.a1_total || 0}
                            </p>
                            <p className="text-sm text-orange-500">A1 死亡事故</p>
                        </div>
                        {/* 輔助：酒駕無肇事 */}
                        <div className="bg-amber-50 rounded-2xl p-4 nook-shadow text-center border-l-4 border-amber-400">
                            <p className="text-3xl font-bold text-amber-600">
                                {(hotspots?.summary?.total_dui_violations || 0) - (hotspots?.summary?.dui_crash_total || 0)}
                            </p>
                            <p className="text-sm text-amber-500">📋 酒駕無肇事</p>
                            <p className="text-xs text-amber-400">（輔助：執法績效）</p>
                        </div>
                        {/* 告發總數 */}
                        <div className="bg-gray-50 rounded-2xl p-4 nook-shadow text-center border-l-4 border-gray-400">
                            <p className="text-3xl font-bold text-gray-600">
                                {hotspots?.summary?.total_dui_violations || 0}
                            </p>
                            <p className="text-sm text-gray-500">酒駕告發總數</p>
                        </div>
                        {/* 統計區間 */}
                        <div className="bg-blue-50 rounded-2xl p-4 nook-shadow text-center border-l-4 border-blue-500">
                            <p className="text-sm font-bold text-blue-600">{dateRange.startDate}</p>
                            <p className="text-sm font-bold text-blue-600">~ {dateRange.endDate}</p>
                            <p className="text-sm text-blue-500">統計區間</p>
                        </div>
                    </div>

                    <div className="grid grid-cols-3 gap-6">
                        {/* 左欄：酒駕高發區域排名 */}
                        <div className="space-y-4">
                            <div className="bg-amber-100 rounded-2xl p-4">
                                <h4 className="font-bold text-amber-800 mb-1">🍺 酒駕高發區域</h4>
                                <p className="text-xs text-amber-600">依酒駕告發數量排序</p>
                            </div>
                            <div className="space-y-3 max-h-96 overflow-y-auto">
                                {hotspots?.hotspots
                                    .filter(h => (h.violations?.dui || 0) > 0)
                                    .sort((a, b) => (b.violations?.dui || 0) - (a.violations?.dui || 0))
                                    .slice(0, 10)
                                    .map((hotspot, idx) => (
                                        <div
                                            key={hotspot.district}
                                            onClick={() => setSelectedDistrict(hotspot.district)}
                                            className={`bg-white/80 rounded-2xl p-4 nook-shadow cursor-pointer transition-all hover:shadow-lg ${selectedDistrict === hotspot.district ? 'ring-2 ring-amber-500' : ''
                                                }`}
                                        >
                                            <div className="flex items-center gap-3 mb-2">
                                                <span className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${idx === 0 ? 'bg-amber-500 text-white' :
                                                    idx === 1 ? 'bg-amber-400 text-white' :
                                                        'bg-amber-300 text-amber-800'
                                                    }`}>
                                                    {idx + 1}
                                                </span>
                                                <h4 className="font-bold text-nook-text">{hotspot.district}</h4>
                                            </div>
                                            <div className="grid grid-cols-3 gap-2 text-center text-xs">
                                                <div className="bg-amber-50 rounded-lg p-2">
                                                    <p className="font-bold text-lg text-amber-700">{hotspot.violations?.dui || 0}</p>
                                                    <p className="text-amber-600">酒駕</p>
                                                </div>
                                                <div className="bg-red-50 rounded-lg p-2">
                                                    <p className="font-bold text-lg text-red-600">{hotspot.accidents?.total || 0}</p>
                                                    <p className="text-red-500">事故</p>
                                                </div>
                                                <div className="bg-gray-50 rounded-lg p-2">
                                                    <p className="font-bold text-lg text-gray-700">{hotspot.accidents?.a1_count || 0}</p>
                                                    <p className="text-gray-500">A1</p>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                {(!hotspots || hotspots.hotspots.filter(h => (h.violations?.dui || 0) > 0).length === 0) && (
                                    <div className="bg-white/80 rounded-2xl p-8 text-center">
                                        <p className="text-nook-text/60">暫無酒駕數據</p>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* 中欄：時段分析 */}
                        <div className="space-y-4">
                            <div className="bg-purple-100 rounded-2xl p-4">
                                <h4 className="font-bold text-purple-800 mb-1">⏰ 酒駕高發時段</h4>
                                <p className="text-xs text-purple-600">
                                    {selectedDistrict ? `${selectedDistrict} 的時段分布` : '請選擇區域查看'}
                                </p>
                            </div>
                            {selectedDistrict && peakTimes ? (
                                <div className="bg-white/80 rounded-2xl p-4 nook-shadow">
                                    <h5 className="font-bold text-nook-text mb-4">{peakTimes.district} 酒駕告發時段分布</h5>
                                    <div className="space-y-2">
                                        {peakTimes.shifts
                                            // 只顯示有酒駕告發的時段，或如果該時段是建議時段也顯示
                                            .filter(s => (s.dui_citations || 0) > 0 || ['10', '11', '12', '01', '02'].includes(s.shift_id))
                                            .sort((a, b) => parseInt(a.shift_id) < 5 ? parseInt(a.shift_id) + 24 : parseInt(a.shift_id) - (parseInt(b.shift_id) < 5 ? parseInt(b.shift_id) + 24 : parseInt(b.shift_id)))
                                            .map((shift) => {
                                                const duiCount = shift.dui_citations || 0;
                                                const maxV = Math.max(...peakTimes.shifts.map(s => s.dui_citations || 0)) || 1;
                                                const width = (duiCount / maxV) * 100;
                                                const isNight = ['10', '11', '12', '01', '02', '03'].includes(shift.shift_id);
                                                const isRecommended = ['11', '12', '01', '02'].includes(shift.shift_id); // 20-04 建議時段

                                                return (
                                                    <div key={shift.shift_id} className={`p-2 rounded-lg ${isRecommended ? 'bg-red-50 border border-red-200' : 'bg-gray-50'}`}>
                                                        <div className="flex justify-between items-center mb-1">
                                                            <span className="text-xs font-medium text-nook-text flex items-center">
                                                                {shift.time_range}
                                                                {isNight && <span className="ml-2 text-purple-500">🌙</span>}
                                                                {isRecommended && <span className="ml-2 text-xs bg-red-100 text-red-600 px-1 rounded">重點時段</span>}
                                                            </span>
                                                            <span className={`text-xs font-bold ${duiCount > 0 ? 'text-red-600' : 'text-gray-400'}`}>
                                                                {duiCount} 件
                                                            </span>
                                                        </div>
                                                        <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                                                            <div
                                                                className={`h-full rounded-full transition-all ${duiCount > 0 ? 'bg-gradient-to-r from-red-400 to-red-600' : 'bg-transparent'}`}
                                                                style={{ width: `${width}%` }}
                                                            />
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                    </div>
                                    <div className="mt-4 p-3 bg-red-50 rounded-lg border border-red-200 text-xs">
                                        <p className="font-bold text-red-800 mb-1">📊 分析洞察</p>
                                        <ul className="list-disc pl-4 space-y-1 text-red-700/80">
                                            <li><span className="bg-red-100 px-1 rounded text-red-600">重點時段</span> 為建議加強攔檢時間 (20:00-04:00)。</li>
                                            <li>柱狀圖顯示實際「酒駕告發」數量。</li>
                                            <li>若重點時段告發數低，可能有執法缺口。</li>
                                        </ul>
                                    </div>
                                </div>
                            ) : (
                                <div className="bg-white/80 rounded-2xl p-8 text-center">
                                    <p className="text-nook-text/40">👈 請從左側選擇一個區域</p>
                                </div>
                            )}
                        </div>

                        {/* 右欄：酒駕執法建議 */}
                        <div className="space-y-4">
                            <div className="bg-red-100 rounded-2xl p-4">
                                <h4 className="font-bold text-red-800 mb-1">🚨 酒駕防治建議</h4>
                                <p className="text-xs text-red-600">重點取締時段與地點</p>
                            </div>
                            <div className="bg-white/80 rounded-2xl p-4 nook-shadow">
                                <h5 className="font-bold text-nook-text mb-3">📍 建議攔檢點位</h5>
                                <div className="space-y-2">
                                    {hotspots?.hotspots
                                        .filter(h => (h.violations?.dui || 0) > 0)
                                        .sort((a, b) => (b.violations?.dui || 0) - (a.violations?.dui || 0))
                                        .slice(0, 5)
                                        .map((h, idx) => (
                                            <div key={h.district} className="flex items-center justify-between p-2 bg-amber-50 rounded-lg">
                                                <div className="flex items-center gap-2">
                                                    <span className="w-6 h-6 bg-amber-500 text-white rounded-full flex items-center justify-center text-xs font-bold">
                                                        {idx + 1}
                                                    </span>
                                                    <span className="font-medium">{h.district}</span>
                                                </div>
                                                <span className="text-amber-700 font-bold">{h.violations?.dui || 0} 件</span>
                                            </div>
                                        ))}
                                </div>
                            </div>
                            <div className="bg-amber-50 border border-amber-300 rounded-2xl p-4">
                                <h5 className="font-bold text-amber-800 mb-2">⏰ 建議取締時段</h5>
                                <div className="grid grid-cols-2 gap-2 text-sm">
                                    <div className="bg-white rounded-lg p-2 text-center">
                                        <p className="text-purple-600 font-bold">20:00-24:00</p>
                                        <p className="text-xs text-gray-500">夜間聚餐後</p>
                                    </div>
                                    <div className="bg-white rounded-lg p-2 text-center">
                                        <p className="text-purple-600 font-bold">00:00-04:00</p>
                                        <p className="text-xs text-gray-500">深夜返家</p>
                                    </div>
                                </div>
                            </div>
                            <div className="bg-nook-leaf/10 rounded-2xl p-4">
                                <p className="text-sm text-nook-leaf-dark">
                                    💡 <strong>執法策略：</strong>結合A1死亡事故熱點，於夜間時段重點攔檢，可有效遏止酒駕肇事
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default AccidentAnalysisPage;
