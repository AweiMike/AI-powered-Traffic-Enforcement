/**
 * 事故分析頁面 - 獨立的事故熱點與趨勢分析
 */
import React, { useState } from 'react';
import { useAccidentHotspots, useAccidentPeakTimes, useCrossAnalysis } from '../hooks/useAPI';
import { AccidentHotspot, ShiftData } from '../api/client';

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
                            <div
                                className="bg-red-400 rounded-sm transition-all"
                                style={{ width: `${accidentWidth}%` }}
                            />
                            <div
                                className="bg-blue-400 rounded-sm transition-all"
                                style={{ width: `${violationWidth}%` }}
                            />
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
                className={`bg-white/80 rounded-2xl p-4 nook-shadow cursor-pointer transition-all hover:shadow-lg ${selected ? 'ring-2 ring-nook-leaf' : ''
                    }`}
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
    const [days, setDays] = useState<number>(30);

    const { data: hotspots, loading: hotspotsLoading } = useAccidentHotspots(days);
    // Only fetch peak times when a district is selected
    const { data: peakTimes, loading: peakLoading } = useAccidentPeakTimes(selectedDistrict || '__SKIP__', days);
    const { data: crossAnalysis, loading: crossLoading } = useCrossAnalysis(selectedDistrict || undefined, days);

    const dayOptions = [
        { value: 30, label: '近 30 天' },
        { value: 90, label: '近 90 天' },
        { value: 180, label: '近 180 天' },
        { value: 365, label: '近 1 年' },
    ];

    return (
        <div className="p-8">
            {/* 標題與篩選器 */}
            <div className="mb-6 flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-nook-text mb-2">🚧 事故分析</h2>
                    <p className="text-nook-text/60">事故熱點、時段分析與精準執法建議</p>
                </div>
                {/* 日期範圍選擇器 */}
                <div className="flex items-center gap-2 bg-white/80 rounded-2xl px-4 py-2 nook-shadow">
                    <span className="text-sm text-nook-text/60">📅 資料範圍：</span>
                    <div className="flex gap-1">
                        {dayOptions.map(opt => (
                            <button
                                key={opt.value}
                                onClick={() => setDays(opt.value)}
                                className={`px-3 py-1.5 rounded-xl text-sm font-medium transition-all ${days === opt.value
                                        ? 'bg-nook-leaf text-white'
                                        : 'bg-nook-leaf/10 text-nook-text hover:bg-nook-leaf/20'
                                    }`}
                            >
                                {opt.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* 總覽統計 */}
            {hotspots && (
                <div className="grid grid-cols-5 gap-4 mb-6">
                    <div className="bg-white/80 rounded-2xl p-4 nook-shadow text-center">
                        <p className="text-3xl font-bold text-nook-text">{hotspots.summary.total_accidents}</p>
                        <p className="text-sm text-nook-text/60">事故總數</p>
                    </div>
                    <div className="bg-red-50 rounded-2xl p-4 text-center border-l-4 border-red-500">
                        <p className="text-3xl font-bold text-red-600">{hotspots.summary.a1_total}</p>
                        <p className="text-sm text-red-500">A1 死亡</p>
                    </div>
                    <div className="bg-orange-50 rounded-2xl p-4 text-center border-l-4 border-orange-500">
                        <p className="text-3xl font-bold text-orange-600">{hotspots.summary.a2_total}</p>
                        <p className="text-sm text-orange-500">A2 受傷</p>
                    </div>
                    <div className="bg-yellow-50 rounded-2xl p-4 text-center border-l-4 border-yellow-500">
                        <p className="text-3xl font-bold text-yellow-600">{hotspots.summary.a3_total}</p>
                        <p className="text-sm text-yellow-500">A3 財損</p>
                    </div>
                    <div className="bg-blue-50 rounded-2xl p-4 text-center border-l-4 border-blue-500">
                        <p className="text-3xl font-bold text-blue-600">{hotspots.total_districts}</p>
                        <p className="text-sm text-blue-500">涵蓋區域</p>
                    </div>
                </div>
            )}

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
                            {(!hotspots || hotspots.hotspots.length === 0) && (
                                <div className="bg-white/80 rounded-2xl p-8 text-center">
                                    <p className="text-nook-text/60">暫無事故數據</p>
                                </div>
                            )}
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

                    {selectedDistrict ? (
                        peakLoading ? (
                            <div className="bg-white/80 rounded-2xl p-8 text-center">
                                <p className="text-nook-text/60">載入中...</p>
                            </div>
                        ) : peakTimes ? (
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

                                <ShiftChart
                                    shifts={peakTimes.shifts}
                                    peakShifts={peakTimes.recommendations.priority_shifts}
                                />

                                <div className="mt-4 p-3 bg-red-50 rounded-lg">
                                    <p className="text-sm font-medium text-red-700">
                                        🚨 {peakTimes.recommendations.enforcement_suggestion}
                                    </p>
                                    <p className="text-xs text-red-600/70 mt-1">
                                        {peakTimes.recommendations.rationale}
                                    </p>
                                </div>
                            </div>
                        ) : (
                            <div className="bg-white/80 rounded-2xl p-8 text-center">
                                <p className="text-nook-text/60">無時段數據</p>
                            </div>
                        )
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
                        <p className="text-xs text-red-600/70">
                            {selectedDistrict ? `${selectedDistrict} 的高風險時段` : '事故多但取締少的時段'}
                        </p>
                    </div>

                    {crossLoading ? (
                        <div className="bg-white/80 rounded-2xl p-8 text-center">
                            <p className="text-nook-text/60">載入中...</p>
                        </div>
                    ) : crossAnalysis ? (
                        <>
                            {/* 優先級統計 */}
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

                            {/* 高優先列表 */}
                            <div className="bg-white/80 rounded-2xl p-4 nook-shadow">
                                <h5 className="font-bold text-nook-text mb-3">🚨 建議優先執法時段</h5>
                                <div className="space-y-2 max-h-64 overflow-y-auto">
                                    {crossAnalysis.recommendations.high_priority_targets.length > 0 ? (
                                        crossAnalysis.recommendations.high_priority_targets.map((item, idx) => (
                                            <div key={idx} className="bg-red-50 rounded-lg p-3 border border-red-100">
                                                <div className="flex justify-between items-center">
                                                    <span className="font-medium text-nook-text">{item.district}</span>
                                                    <span className="text-xs bg-red-200 text-red-700 px-2 py-1 rounded-full">
                                                        {item.time_range}
                                                    </span>
                                                </div>
                                                <div className="flex gap-4 mt-2 text-xs">
                                                    <span className="text-red-600">事故 {item.accidents}</span>
                                                    <span className="text-blue-600">違規 {item.violations}</span>
                                                    <span className="text-orange-600 font-bold">缺口 {item.enforcement_gap}</span>
                                                </div>
                                            </div>
                                        ))
                                    ) : (
                                        <p className="text-center text-nook-text/60 py-4">無高優先執法目標</p>
                                    )}
                                </div>
                            </div>

                            {/* 建議說明 */}
                            <div className="bg-nook-leaf/10 rounded-2xl p-4">
                                <p className="text-sm text-nook-leaf-dark">
                                    💡 <strong>執法策略建議：</strong>{crossAnalysis.recommendations.suggestion}
                                </p>
                            </div>
                        </>
                    ) : (
                        <div className="bg-white/80 rounded-2xl p-8 text-center">
                            <p className="text-nook-text/60">無交叉分析數據</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default AccidentAnalysisPage;
