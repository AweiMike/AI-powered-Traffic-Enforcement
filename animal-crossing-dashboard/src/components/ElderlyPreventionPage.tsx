/**
 * 高齡者防治頁面 - 專注於高齡者事故分析與防治
 */
import React, { useState } from 'react';
import { useAccidentHotspots, useAccidentPeakTimes } from '../hooks/useAPI';
import { AccidentHotspot, ShiftData } from '../api/client';

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

                <div className="grid grid-cols-3 gap-2 text-center text-xs mb-3">
                    <div className="bg-orange-50 rounded-lg p-2">
                        <p className="font-bold text-lg text-orange-700">{hotspot.accidents.total}</p>
                        <p className="text-orange-600">高齡事故</p>
                    </div>
                    <div className="bg-red-50 rounded-lg p-2">
                        <p className="font-bold text-lg text-red-600">{hotspot.accidents.a1_count}</p>
                        <p className="text-red-500">A1 死亡</p>
                    </div>
                    <div className="bg-yellow-50 rounded-lg p-2">
                        <p className="font-bold text-lg text-yellow-600">{hotspot.accidents.a2_count}</p>
                        <p className="text-yellow-500">A2 受傷</p>
                    </div>
                </div>
            </div>
        );
    };

const ElderlyPreventionPage: React.FC = () => {
    const [selectedDistrict, setSelectedDistrict] = useState<string | null>(null);
    const [days, setDays] = useState<number>(30);
    // isElderly = true 強制篩選高齡者數據
    const { data: hotspots, loading: hotspotsLoading } = useAccidentHotspots(days, true);
    const { data: peakTimes, loading: peakLoading } = useAccidentPeakTimes(selectedDistrict || '__SKIP__', days, true);

    const dayOptions = [
        { value: 30, label: '近 30 天' },
        { value: 90, label: '近 90 天' },
        { value: 180, label: '近 180 天' },
        { value: 365, label: '近 1 年' },
    ];

    return (
        <div className="p-8 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-nook-text mb-2">👵 高齡者事故防制專區</h2>
                    <p className="text-nook-text/60">針對 65 歲以上長者事故分析與防治建議</p>
                </div>
                <div className="flex items-center gap-2 bg-white/80 rounded-2xl px-4 py-2 nook-shadow">
                    <span className="text-sm text-nook-text/60">📅 資料範圍：</span>
                    <div className="flex gap-1">
                        {dayOptions.map(opt => (
                            <button
                                key={opt.value}
                                onClick={() => setDays(opt.value)}
                                className={`px-3 py-1.5 rounded-xl text-sm font-medium transition-all ${days === opt.value ? 'bg-orange-500 text-white' : 'bg-orange-100 text-orange-800 hover:bg-orange-200'
                                    }`}
                            >
                                {opt.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* 總覽數據 */}
            {hotspots && (
                <div className="grid grid-cols-4 gap-4">
                    <div className="bg-white/80 rounded-2xl p-4 nook-shadow text-center border-b-4 border-orange-500">
                        <p className="text-4xl font-bold text-nook-text">{hotspots.summary.total_accidents}</p>
                        <p className="text-sm text-nook-text/60">高齡事故總數</p>
                    </div>
                    <div className="bg-red-50 rounded-2xl p-4 nook-shadow text-center border-b-4 border-red-500">
                        <p className="text-4xl font-bold text-red-600">{hotspots.summary.a1_total}</p>
                        <p className="text-sm text-red-500">涉及 A1 死亡</p>
                    </div>
                    <div className="bg-yellow-50 rounded-2xl p-4 nook-shadow text-center border-b-4 border-yellow-500">
                        <p className="text-4xl font-bold text-yellow-600">{hotspots.summary.a2_total}</p>
                        <p className="text-sm text-yellow-500">涉及 A2 受傷</p>
                    </div>
                    <div className="bg-blue-50 rounded-2xl p-4 nook-shadow text-center border-b-4 border-blue-500">
                        <p className="text-4xl font-bold text-blue-600">{hotspots.hotspots.length}</p>
                        <p className="text-sm text-blue-500">發生區域數</p>
                    </div>
                </div>
            )}

            <div className="grid grid-cols-12 gap-6">
                {/* 左欄：高齡事故熱區 */}
                <div className="col-span-4 space-y-4">
                    <div className="bg-orange-100 rounded-2xl p-4">
                        <h4 className="font-bold text-orange-800 mb-1">📍 高齡事故熱區</h4>
                        <p className="text-xs text-orange-600">依長者事故數量排序</p>
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
                    <div className="bg-blue-100 rounded-2xl p-4">
                        <h4 className="font-bold text-blue-800 mb-1">⏰ 事故時段分析</h4>
                        <p className="text-xs text-blue-600">
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

                {/* 右欄：宣導建議 (靜態/動態混合) */}
                <div className="col-span-3 space-y-4">
                    <div className="bg-green-100 rounded-2xl p-4">
                        <h4 className="font-bold text-green-800 mb-1">📢 防治宣導建議</h4>
                        <p className="text-xs text-green-600">針對長者特性之策略</p>
                    </div>

                    <div className="bg-white/80 rounded-2xl p-4 nook-shadow space-y-4">
                        <div className="bg-yellow-50 p-3 rounded-lg border border-yellow-200">
                            <span className="text-2xl mb-1 block">🦺</span>
                            <h5 className="font-bold text-yellow-800 mb-1">亮衣與反光配件</h5>
                            <p className="text-xs text-gray-600">晨昏外出時應穿著鮮豔衣物或配戴反光手環。</p>
                        </div>

                        <div className="bg-blue-50 p-3 rounded-lg border border-blue-200">
                            <span className="text-2xl mb-1 block">🛵</span>
                            <h5 className="font-bold text-blue-800 mb-1">兩段式左轉</h5>
                            <p className="text-xs text-gray-600">騎乘機車應落實兩段式左轉，避免直接穿越馬路。</p>
                        </div>

                        <div className="bg-red-50 p-3 rounded-lg border border-red-200">
                            <span className="text-2xl mb-1 block">🚌</span>
                            <h5 className="font-bold text-red-800 mb-1">大型車視線死角</h5>
                            <p className="text-xs text-gray-600">遠離大型車輛，避免進入內輪差與視線死角範圍。</p>
                        </div>
                    </div>

                    <div className="bg-nook-leaf/10 rounded-2xl p-4 text-center">
                        <p className="text-sm text-nook-leaf-dark font-medium">✨ 「長者平安，全家心安」</p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ElderlyPreventionPage;
