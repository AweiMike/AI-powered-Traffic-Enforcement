/**
 * 微型電動二輪車與電動輔助自行車分析頁面
 * 專注於青少年事故防制與精準執法
 */
import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import DateRangePicker, { type DateRange } from './DateRangePicker';

// 定義類型
interface EVehicleOverview {
    period_days: number;
    crashes: {
        total: number;
        micro_evehicle: number;
        eassist_bike: number;
        youth_count: number;
        youth_ratio: number;
        underage_14: number;
        severity: {
            a1: number;
            a2: number;
            a3: number;
        };
    };
    tickets: {
        total: number;
        youth_count: number;
        youth_ratio: number;
        violation_types: Array<{ type: string; count: number }>;
    };
    highlight: {
        youth_warning: boolean;
        underage_alert: boolean;
    };
}

interface YouthHotspot {
    district: string;
    total: number;
    crash_count?: number;
    ticket_count?: number;
    a1_count: number;
    a2_count: number;
    a3_count: number;
    weighted_score: number;
}

interface YearlyTrend {
    years_compared: number;
    current_year: number;
    current_month: number;
    yearly_totals: Record<number, { total: number; youth: number }>;
    monthly_trend: Array<{
        month: number;
        month_name: string;
        [key: string]: number | string;
    }>;
    yoy_comparison: {
        current_month: number;
        this_year: number;
        last_year: number;
        change: number;
        change_percent: number;
        trend: string;
    };
}

interface TimeDistribution {
    shift_id: string;
    time_range: string;
    total: number;
    youth_count: number;
    is_school_time: boolean;
}

interface ViolationType {
    violation_type: string;
    total: number;
    youth_count: number;
    youth_ratio: number;
}

interface AgeDistribution {
    age_group: string;
    crash_count: number;
    ticket_count: number;
    is_youth: boolean;
}

interface YouthAgeBreakdown {
    period_days: number;
    under_14: {
        ages: Array<{ age: number; count: number; label: string }>;
        total: number;
        warning: string;
    };
    age_14_to_17: {
        ages: Array<{ age: number; count: number; label: string }>;
        total: number;
    };
    youth_total: number;
    youth_total_from_group?: number;
    data_available: boolean;
}

// 統計卡片元件
const StatCard: React.FC<{
    title: string;
    value: number | string;
    subtitle?: string;
    color: string;
    emoji: string;
    alert?: boolean;
}> = ({ title, value, subtitle, color, emoji, alert }) => (
    <div className={`bg-white/80 rounded-2xl p-4 nook-shadow text-center border-b-4 ${color} ${alert ? 'ring-2 ring-red-400 animate-pulse' : ''}`}>
        <div className="text-3xl mb-1">{emoji}</div>
        <p className="text-3xl font-bold text-nook-text">{value}</p>
        <p className="text-sm text-nook-text/60">{title}</p>
        {subtitle && <p className="text-xs text-nook-text/40 mt-1">{subtitle}</p>}
    </div>
);

// 熱點卡片元件
const HotspotCard: React.FC<{ hotspot: YouthHotspot; rank: number }> = ({ hotspot, rank }) => (
    <div className="bg-white/80 rounded-xl p-4 nook-shadow">
        <div className="flex items-center gap-3 mb-3">
            <span className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-white ${rank === 1 ? 'bg-red-500' : rank === 2 ? 'bg-orange-500' : 'bg-yellow-500'
                }`}>
                {rank}
            </span>
            <h4 className="font-bold text-nook-text">{hotspot.district}</h4>
            <span className="ml-auto text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded-full">
                權重 {hotspot.weighted_score}
            </span>
        </div>
        <div className="grid grid-cols-5 gap-2 text-center text-xs">
            <div className="bg-purple-50 rounded-lg p-2">
                <p className="font-bold text-lg text-purple-600">{hotspot.ticket_count || 0}</p>
                <p className="text-purple-500">違規</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-2">
                <p className="font-bold text-lg text-nook-text">{hotspot.crash_count || 0}</p>
                <p className="text-nook-text/60">事故</p>
            </div>
            <div className="bg-red-50 rounded-lg p-2">
                <p className="font-bold text-lg text-red-600">{hotspot.a1_count}</p>
                <p className="text-red-500">A1</p>
            </div>
            <div className="bg-orange-50 rounded-lg p-2">
                <p className="font-bold text-lg text-orange-600">{hotspot.a2_count}</p>
                <p className="text-orange-500">A2</p>
            </div>
            <div className="bg-yellow-50 rounded-lg p-2">
                <p className="font-bold text-lg text-yellow-600">{hotspot.a3_count}</p>
                <p className="text-yellow-500">A3</p>
            </div>
        </div>
    </div>
);

// 時段分析圖表
const TimeChart: React.FC<{ data: TimeDistribution[] }> = ({ data }) => {
    const maxValue = Math.max(...data.map(d => d.total)) || 1;

    return (
        <div className="space-y-2">
            {data.map((item) => (
                <div key={item.shift_id} className={`p-2 rounded-lg ${item.is_school_time ? 'bg-red-50 border border-red-200' : 'bg-gray-50'}`}>
                    <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium text-nook-text">
                            {item.time_range}
                            {item.is_school_time && <span className="ml-2 text-red-600">🎒 通學時段</span>}
                        </span>
                        <div className="text-xs">
                            <span className="font-bold text-nook-text">{item.total}</span>
                            <span className="text-nook-text/40 mx-1">/</span>
                            <span className="font-bold text-red-600">{item.youth_count} 青少年</span>
                        </div>
                    </div>
                    <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div
                            className={`h-full rounded-full transition-all ${item.is_school_time ? 'bg-red-500' : 'bg-blue-400'}`}
                            style={{ width: `${(item.total / maxValue) * 100}%` }}
                        />
                    </div>
                </div>
            ))}
        </div>
    );
};

// 主頁面元件
const EVehicleAnalysisPage: React.FC = () => {
    const [dateRange, setDateRange] = useState<DateRange>(() => {
        const now = new Date();
        const start = new Date(now.getFullYear(), 0, 1);
        const fmt = (d: Date) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
        return { startDate: fmt(start), endDate: fmt(now) };
    });
    const [activeTab, setActiveTab] = useState<'overview' | 'hotspots' | 'time' | 'violations' | 'trend'>('overview');
    const [loading, setLoading] = useState<boolean>(true);

    // 資料狀態
    const [overview, setOverview] = useState<EVehicleOverview | null>(null);
    const [hotspots, setHotspots] = useState<YouthHotspot[]>([]);
    const [timeData, setTimeData] = useState<TimeDistribution[]>([]);
    const [violations, setViolations] = useState<ViolationType[]>([]);
    const [ageData, setAgeData] = useState<AgeDistribution[]>([]);
    const [youthAgeBreakdown, setYouthAgeBreakdown] = useState<YouthAgeBreakdown | null>(null);
    const [yearlyTrend, setYearlyTrend] = useState<YearlyTrend | null>(null);

    // 載入資料
    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            try {
                // 平行請求所有資料
                const dateParams = `start_date=${dateRange.startDate}&end_date=${dateRange.endDate}`;
                const [overviewRes, hotspotsRes, timeRes, violationsRes, ageRes, youthAgeRes, trendRes] = await Promise.all([
                    fetch(`/api/v1/evehicle/overview?days=365&${dateParams}`),
                    fetch(`/api/v1/evehicle/youth-hotspots?days=365&${dateParams}`),
                    fetch(`/api/v1/evehicle/time-analysis?days=365&${dateParams}`),
                    fetch(`/api/v1/evehicle/violation-types?days=365&${dateParams}`),
                    fetch(`/api/v1/evehicle/age-distribution?days=365&${dateParams}`),
                    fetch(`/api/v1/evehicle/youth-age-breakdown?days=365&${dateParams}`),
                    fetch(`/api/v1/evehicle/yearly-trend?years=4`),
                ]);

                if (overviewRes.ok) setOverview(await overviewRes.json());
                if (hotspotsRes.ok) {
                    const data = await hotspotsRes.json();
                    setHotspots(data.hotspots || []);
                }
                if (timeRes.ok) {
                    const data = await timeRes.json();
                    setTimeData(data.time_distribution || []);
                }
                if (violationsRes.ok) {
                    const data = await violationsRes.json();
                    setViolations(data.violations || []);
                }
                if (ageRes.ok) {
                    const data = await ageRes.json();
                    setAgeData(data.distribution || []);
                }
                if (youthAgeRes.ok) {
                    const data = await youthAgeRes.json();
                    setYouthAgeBreakdown(data);
                }
                if (trendRes.ok) {
                    const data = await trendRes.json();
                    setYearlyTrend(data);
                }
            } catch (error) {
                console.error('載入資料失敗:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [dateRange]);

    const tabs = [
        { id: 'overview' as const, label: '📊 總覽', description: '事故與違規統計' },
        { id: 'hotspots' as const, label: '📍 熱點', description: '青少年事故熱區' },
        { id: 'time' as const, label: '⏰ 時段', description: '通學時段分析' },
        { id: 'violations' as const, label: '📋 違規', description: '違規態樣分布' },
        { id: 'trend' as const, label: '📈 趨勢', description: '年度同期比較' },
    ];

    return (
        <div className="p-8 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-nook-text mb-2">🛵 青少年慢車與微電車分析專區</h2>
                    <p className="text-nook-text/60">青少年微型電動二輪車、電動輔助自行車事故防制與精準執法</p>
                </div>
                <DateRangePicker value={dateRange} onChange={setDateRange} showCompare={true} />
            </div>

            {/* 警告提示 */}
            {overview?.highlight.youth_warning && (
                <div className="bg-red-100 border-2 border-red-300 rounded-2xl p-4 flex items-center gap-4">
                    <span className="text-4xl">⚠️</span>
                    <div>
                        <h4 className="font-bold text-red-800">青少年事故佔比偏高</h4>
                        <p className="text-sm text-red-600">
                            青少年（&lt;18歲）佔慢車事故 {overview.crashes.youth_ratio}%，建議加強校園周邊執法與宣導。
                        </p>
                    </div>
                </div>
            )}

            {overview?.highlight.underage_alert && (
                <div className="bg-orange-100 border-2 border-orange-300 rounded-2xl p-4 flex items-center gap-4">
                    <span className="text-4xl">🚨</span>
                    <div>
                        <h4 className="font-bold text-orange-800">未滿 14 歲騎乘微電車</h4>
                        <p className="text-sm text-orange-600">
                            發現 {overview.crashes.underage_14} 件未滿 14 歲騎乘微電車事故，依第 72-2 條可處罰監護人。
                        </p>
                    </div>
                </div>
            )}

            {/* 分頁標籤 */}
            <div className="flex gap-2">
                {tabs.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`px-6 py-3 rounded-2xl font-medium transition-all ${activeTab === tab.id
                            ? 'bg-purple-500 text-white shadow-lg'
                            : 'bg-white/60 text-nook-text hover:bg-purple-100'
                            }`}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {loading ? (
                <div className="bg-white/80 rounded-2xl p-12 text-center">
                    <div className="animate-spin w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full mx-auto mb-4"></div>
                    <p className="text-nook-text/60">載入資料中...</p>
                </div>
            ) : (
                <>
                    {/* 總覽分頁 */}
                    {activeTab === 'overview' && overview && (
                        <div className="space-y-6">
                            {/* 統計卡片 */}
                            <div className="grid grid-cols-5 gap-4">
                                <StatCard
                                    title="慢車事故總數"
                                    value={overview.crashes.total}
                                    emoji="🛵"
                                    color="border-purple-500"
                                />
                                <StatCard
                                    title="青少年事故"
                                    value={overview.crashes.youth_count}
                                    subtitle={`佔 ${overview.crashes.youth_ratio}%`}
                                    emoji="👦"
                                    color="border-red-500"
                                    alert={overview.highlight.youth_warning}
                                />
                                <StatCard
                                    title="微電車事故"
                                    value={overview.crashes.micro_evehicle}
                                    emoji="🔋"
                                    color="border-blue-500"
                                />
                                <StatCard
                                    title="電輔車事故"
                                    value={overview.crashes.eassist_bike}
                                    emoji="🚲"
                                    color="border-green-500"
                                />
                                <StatCard
                                    title="違規總數"
                                    value={overview.tickets.total}
                                    subtitle={`青少年 ${overview.tickets.youth_count} 件`}
                                    emoji="📋"
                                    color="border-orange-500"
                                />
                            </div>

                            {/* 嚴重度與年齡分布 */}
                            <div className="grid grid-cols-2 gap-6">
                                {/* 嚴重度 */}
                                <div className="bg-white/80 rounded-2xl p-6 nook-shadow">
                                    <h4 className="font-bold text-nook-text mb-4">📊 事故嚴重度分布</h4>
                                    <div className="grid grid-cols-3 gap-4">
                                        <div className="bg-red-50 rounded-xl p-4 text-center">
                                            <p className="text-3xl font-bold text-red-600">{overview.crashes.severity.a1}</p>
                                            <p className="text-sm text-red-500">A1 死亡</p>
                                        </div>
                                        <div className="bg-orange-50 rounded-xl p-4 text-center">
                                            <p className="text-3xl font-bold text-orange-600">{overview.crashes.severity.a2}</p>
                                            <p className="text-sm text-orange-500">A2 受傷</p>
                                        </div>
                                        <div className="bg-yellow-50 rounded-xl p-4 text-center">
                                            <p className="text-3xl font-bold text-yellow-600">{overview.crashes.severity.a3}</p>
                                            <p className="text-sm text-yellow-500">A3 財損</p>
                                        </div>
                                    </div>
                                </div>

                                {/* 青少年年齡分布 */}
                                <div className="bg-white/80 rounded-2xl p-6 nook-shadow">
                                    <h4 className="font-bold text-nook-text mb-4">👦 青少年違規年齡分布 (&lt;18歲)</h4>
                                    <div className="space-y-2">
                                        {/* 未滿14歲區塊 - 微電車禁止騎乘 */}
                                        <div className="bg-red-100 rounded-xl p-3 border-2 border-red-300">
                                            <div className="flex items-center justify-between mb-2">
                                                <span className="font-bold text-red-700">🚫 未滿14歲（禁止騎乘微電車）</span>
                                                <span className="text-sm font-bold text-red-600">
                                                    {youthAgeBreakdown?.under_14?.total || 0} 件
                                                </span>
                                            </div>
                                            <div className="grid grid-cols-5 gap-2">
                                                {(youthAgeBreakdown?.under_14?.ages || [{ age: 9, count: 0 }, { age: 10, count: 0 }, { age: 11, count: 0 }, { age: 12, count: 0 }, { age: 13, count: 0 }]).map(ageItem => (
                                                    <div key={ageItem.age} className="bg-white rounded-lg p-2 text-center">
                                                        <p className="text-xs text-red-600 font-medium">{ageItem.age}歲</p>
                                                        <p className={`text-lg font-bold ${ageItem.count > 0 ? 'text-red-700' : 'text-gray-300'}`}>
                                                            {ageItem.count}
                                                        </p>
                                                    </div>
                                                ))}
                                            </div>
                                            <p className="text-xs text-red-600 mt-2">⚠️ 未滿14歲騎乘微電車，依第72-2條處罰監護人</p>
                                        </div>

                                        {/* 14-17歲區塊 */}
                                        <div className="bg-orange-50 rounded-xl p-3 border border-orange-200">
                                            <div className="flex items-center justify-between mb-2">
                                                <span className="font-bold text-orange-700">⚠️ 14-17歲（可騎乘但需注意）</span>
                                                <span className="text-sm font-bold text-orange-600">
                                                    {youthAgeBreakdown?.age_14_to_17?.total || 0} 件
                                                </span>
                                            </div>
                                            <div className="grid grid-cols-4 gap-2">
                                                {(youthAgeBreakdown?.age_14_to_17?.ages || [{ age: 14, count: 0 }, { age: 15, count: 0 }, { age: 16, count: 0 }, { age: 17, count: 0 }]).map(ageItem => (
                                                    <div key={ageItem.age} className="bg-white rounded-lg p-2 text-center">
                                                        <p className="text-xs text-orange-600 font-medium">{ageItem.age}歲</p>
                                                        <p className={`text-lg font-bold ${ageItem.count > 0 ? 'text-orange-700' : 'text-gray-300'}`}>
                                                            {ageItem.count}
                                                        </p>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>

                                        {/* 青少年總計 */}
                                        <div className="bg-purple-100 rounded-xl p-3 border border-purple-300">
                                            <div className="flex items-center justify-between">
                                                <span className="font-bold text-purple-700">📊 青少年違規總計 (&lt;18歲)</span>
                                                <div className="text-sm">
                                                    <span className="font-bold text-purple-700">{youthAgeBreakdown?.youth_total || 0}</span>
                                                    <span className="text-purple-500 mx-1">件</span>
                                                </div>
                                            </div>
                                            {!youthAgeBreakdown?.data_available && (
                                                <p className="text-xs text-purple-500 mt-2">💡 重新匯入資料後即可顯示個別年齡統計</p>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* 法規重點 */}
                            <div className="bg-gradient-to-r from-purple-100 to-blue-100 rounded-2xl p-6">
                                <h4 className="font-bold text-nook-text mb-4">⚖️ 法規重點提醒</h4>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="bg-white/80 rounded-xl p-4">
                                        <h5 className="font-bold text-purple-700 mb-2">🔋 微型電動二輪車</h5>
                                        <ul className="text-sm text-nook-text/70 space-y-1">
                                            <li>✅ 強制掛牌（白底綠字）</li>
                                            <li>✅ 強制戴安全帽</li>
                                            <li>✅ 須滿 14 歲才可騎乘</li>
                                            <li>✅ 禁止改裝（拆限速器）</li>
                                        </ul>
                                    </div>
                                    <div className="bg-white/80 rounded-xl p-4">
                                        <h5 className="font-bold text-green-700 mb-2">🚲 電動輔助自行車</h5>
                                        <ul className="text-sm text-nook-text/70 space-y-1">
                                            <li>❌ 免掛牌（須有閃電標章）</li>
                                            <li>⚠️ 建議戴安全帽</li>
                                            <li>❌ 無年齡限制</li>
                                            <li>✅ 須以人力踩踏為主</li>
                                        </ul>
                                    </div>
                                </div>
                                <div className="mt-4 bg-red-100 rounded-xl p-4">
                                    <p className="text-sm text-red-700">
                                        <strong>🍺 酒駕提醒：</strong>微電車與電輔車酒駕皆視同一般酒駕處罰！
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* 熱點分頁 */}
                    {activeTab === 'hotspots' && (
                        <div className="space-y-4">
                            <div className="bg-red-100 rounded-2xl p-4">
                                <h4 className="font-bold text-red-800 mb-1">📍 青少年事故熱點排行</h4>
                                <p className="text-xs text-red-600">依青少年慢車事故數量排序，權重計算：A1×5 + A2×3 + A3×1</p>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                {hotspots.map((hotspot, idx) => (
                                    <HotspotCard key={hotspot.district} hotspot={hotspot} rank={idx + 1} />
                                ))}
                            </div>
                            {hotspots.length === 0 && (
                                <div className="bg-white/80 rounded-2xl p-12 text-center">
                                    <p className="text-nook-text/60">目前尚無青少年事故熱點資料</p>
                                </div>
                            )}
                        </div>
                    )}

                    {/* 時段分頁 */}
                    {activeTab === 'time' && (
                        <div className="grid grid-cols-2 gap-6">
                            <div className="space-y-4">
                                <div className="bg-blue-100 rounded-2xl p-4">
                                    <h4 className="font-bold text-blue-800 mb-1">⏰ 24 小時時段分布</h4>
                                    <p className="text-xs text-blue-600">標記通學時段（上學 07-08、放學 16-18）</p>
                                </div>
                                <div className="bg-white/80 rounded-2xl p-6 nook-shadow">
                                    <TimeChart data={timeData} />
                                </div>
                            </div>
                            <div className="space-y-4">
                                <div className="bg-orange-100 rounded-2xl p-4">
                                    <h4 className="font-bold text-orange-800 mb-1">🎒 通學時段重點</h4>
                                    <p className="text-xs text-orange-600">建議在通學時段加強校園周邊巡邏</p>
                                </div>
                                <div className="bg-white/80 rounded-2xl p-6 nook-shadow space-y-4">
                                    <div className="bg-red-50 rounded-xl p-4 border border-red-200">
                                        <h5 className="font-bold text-red-700 mb-2">🌅 上學時段 (06:00-10:00)</h5>
                                        <p className="text-sm text-red-600">
                                            學生趕上學，常見超速、闖紅燈、未戴安全帽等違規。
                                        </p>
                                    </div>
                                    <div className="bg-orange-50 rounded-xl p-4 border border-orange-200">
                                        <h5 className="font-bold text-orange-700 mb-2">🌆 放學時段 (16:00-18:00)</h5>
                                        <p className="text-sm text-orange-600">
                                            放學後青少年聚集，常見雙載、競速、蛇行等危險行為。
                                        </p>
                                    </div>
                                    <div className="bg-purple-50 rounded-xl p-4 border border-purple-200">
                                        <h5 className="font-bold text-purple-700 mb-2">💡 執法建議</h5>
                                        <ul className="text-sm text-purple-600 space-y-1">
                                            <li>• 通學時段於校園周邊 500m 加強巡邏</li>
                                            <li>• 優先攔查未掛牌微電車</li>
                                            <li>• 違規雙載從嚴取締</li>
                                        </ul>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* 違規分頁 */}
                    {activeTab === 'violations' && (
                        <div className="space-y-4">
                            <div className="bg-orange-100 rounded-2xl p-4">
                                <h4 className="font-bold text-orange-800 mb-1">📋 違規態樣分布</h4>
                                <p className="text-xs text-orange-600">慢車/微電車相關違規統計</p>
                            </div>
                            <div className="grid grid-cols-2 gap-6">
                                <div className="bg-white/80 rounded-2xl p-6 nook-shadow">
                                    <h5 className="font-bold text-nook-text mb-4">違規類型排行</h5>
                                    <div className="space-y-3">
                                        {violations.map((v, idx) => (
                                            <div key={v.violation_type} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                                                <div className="flex items-center gap-3">
                                                    <span className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-white ${idx === 0 ? 'bg-red-500' : idx === 1 ? 'bg-orange-500' : 'bg-yellow-500'
                                                        }`}>
                                                        {idx + 1}
                                                    </span>
                                                    <span className="font-medium text-nook-text">{v.violation_type}</span>
                                                </div>
                                                <div className="text-right">
                                                    <p className="font-bold text-nook-text">{v.total} 件</p>
                                                    <p className="text-xs text-red-500">青少年 {v.youth_count} 件 ({v.youth_ratio}%)</p>
                                                </div>
                                            </div>
                                        ))}
                                        {violations.length === 0 && (
                                            <p className="text-center text-nook-text/60 py-4">目前無違規態樣資料</p>
                                        )}
                                    </div>
                                </div>
                                <div className="space-y-4">
                                    <div className="bg-white/80 rounded-2xl p-6 nook-shadow">
                                        <h5 className="font-bold text-nook-text mb-4">⚖️ 法律依據</h5>
                                        <div className="space-y-3 text-sm">
                                            <div className="p-3 bg-red-50 rounded-lg border border-red-200">
                                                <p className="font-bold text-red-700">未掛牌</p>
                                                <p className="text-red-600">道交條例第 71-1 條，可沒入車輛</p>
                                            </div>
                                            <div className="p-3 bg-orange-50 rounded-lg border border-orange-200">
                                                <p className="font-bold text-orange-700">未滿 14 歲騎乘</p>
                                                <p className="text-orange-600">第 72-2 條，處罰監護人</p>
                                            </div>
                                            <div className="p-3 bg-yellow-50 rounded-lg border border-yellow-200">
                                                <p className="font-bold text-yellow-700">未戴安全帽</p>
                                                <p className="text-yellow-600">微電車強制規定，電輔車建議</p>
                                            </div>
                                            <div className="p-3 bg-purple-50 rounded-lg border border-purple-200">
                                                <p className="font-bold text-purple-700">違規雙載</p>
                                                <p className="text-purple-600">微電車與電輔車皆禁止載人</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* 趨勢分頁 */}
                    {activeTab === 'trend' && (
                        <div className="space-y-4">
                            <div className="bg-gradient-to-r from-indigo-100 to-purple-100 rounded-2xl p-4">
                                <h4 className="font-bold text-indigo-800 mb-1">📈 年度同期趨勢比較</h4>
                                <p className="text-xs text-indigo-600">近 4 年同月份青少年慢車違規數量比較</p>
                            </div>

                            {yearlyTrend && (
                                <>
                                    {/* 同期比較卡片 */}
                                    <div className="grid grid-cols-3 gap-4">
                                        <div className="bg-white/80 rounded-2xl p-4 nook-shadow">
                                            <p className="text-sm text-nook-text/60 mb-1">本月青少年違規</p>
                                            <p className="text-3xl font-bold text-indigo-600">{yearlyTrend.yoy_comparison.this_year}</p>
                                            <p className="text-xs text-nook-text/60">{yearlyTrend.current_year}年{yearlyTrend.current_month}月</p>
                                        </div>
                                        <div className="bg-white/80 rounded-2xl p-4 nook-shadow">
                                            <p className="text-sm text-nook-text/60 mb-1">去年同月</p>
                                            <p className="text-3xl font-bold text-gray-600">{yearlyTrend.yoy_comparison.last_year}</p>
                                            <p className="text-xs text-nook-text/60">{yearlyTrend.current_year - 1}年{yearlyTrend.current_month}月</p>
                                        </div>
                                        <div className={`rounded-2xl p-4 nook-shadow ${yearlyTrend.yoy_comparison.change > 0 ? 'bg-red-50' :
                                            yearlyTrend.yoy_comparison.change < 0 ? 'bg-green-50' : 'bg-gray-50'
                                            }`}>
                                            <p className="text-sm text-nook-text/60 mb-1">同期變化</p>
                                            <p className={`text-3xl font-bold ${yearlyTrend.yoy_comparison.change > 0 ? 'text-red-600' :
                                                yearlyTrend.yoy_comparison.change < 0 ? 'text-green-600' : 'text-gray-600'
                                                }`}>
                                                {yearlyTrend.yoy_comparison.change > 0 ? '+' : ''}{yearlyTrend.yoy_comparison.change}
                                            </p>
                                            <p className={`text-xs ${yearlyTrend.yoy_comparison.change > 0 ? 'text-red-500' :
                                                yearlyTrend.yoy_comparison.change < 0 ? 'text-green-500' : 'text-gray-500'
                                                }`}>
                                                {yearlyTrend.yoy_comparison.trend} {Math.abs(yearlyTrend.yoy_comparison.change_percent)}%
                                            </p>
                                        </div>
                                    </div>

                                    {/* 多年趨勢比較圖表 */}
                                    <div className="bg-white/80 rounded-2xl p-6 nook-shadow">
                                        <h5 className="font-bold text-nook-text mb-4">青少年違規月份趨勢比較</h5>

                                        {(() => {
                                            const years = [yearlyTrend.current_year - 3, yearlyTrend.current_year - 2, yearlyTrend.current_year - 1, yearlyTrend.current_year];
                                            const colors = ['#9ca3af', '#60a5fa', '#a78bfa', '#6366f1'];  // gray, blue, purple, indigo
                                            const months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

                                            // 找出最大值
                                            let maxVal = 1;
                                            yearlyTrend.monthly_trend.forEach(item => {
                                                years.forEach(year => {
                                                    const val = (item[`y${year}`] as number) || 0;
                                                    if (val > maxVal) maxVal = val;
                                                });
                                            });

                                            const chartWidth = 700;
                                            const chartHeight = 280;
                                            const padding = { top: 20, right: 30, bottom: 50, left: 50 };
                                            const graphWidth = chartWidth - padding.left - padding.right;
                                            const graphHeight = chartHeight - padding.top - padding.bottom;

                                            // 生成每年的折線路徑
                                            const yearLines = years.map((year, yearIdx) => {
                                                const points = months.map((month, monthIdx) => {
                                                    const item = yearlyTrend.monthly_trend.find(m => m.month === month);
                                                    const val = item ? ((item[`y${year}`] as number) || 0) : 0;
                                                    const x = padding.left + (monthIdx / (months.length - 1)) * graphWidth;
                                                    const y = padding.top + graphHeight - (val / maxVal) * graphHeight;
                                                    return { x, y, val, month };
                                                });
                                                return { year, color: colors[yearIdx], points };
                                            });

                                            return (
                                                <div className="overflow-x-auto">
                                                    <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="w-full">
                                                        {/* 背景網格 */}
                                                        {[0, 0.25, 0.5, 0.75, 1].map(ratio => (
                                                            <line
                                                                key={ratio}
                                                                x1={padding.left}
                                                                y1={padding.top + graphHeight * (1 - ratio)}
                                                                x2={padding.left + graphWidth}
                                                                y2={padding.top + graphHeight * (1 - ratio)}
                                                                stroke="#e5e7eb"
                                                                strokeWidth="1"
                                                            />
                                                        ))}

                                                        {/* 月份垂直線 */}
                                                        {months.map((month, idx) => {
                                                            const x = padding.left + (idx / (months.length - 1)) * graphWidth;
                                                            return (
                                                                <line
                                                                    key={month}
                                                                    x1={x}
                                                                    y1={padding.top}
                                                                    x2={x}
                                                                    y2={padding.top + graphHeight}
                                                                    stroke="#f3f4f6"
                                                                    strokeWidth="1"
                                                                />
                                                            );
                                                        })}

                                                        {/* 每年的折線 */}
                                                        {yearLines.map(({ year, color, points }) => (
                                                            <g key={year}>
                                                                <polyline
                                                                    points={points.map(p => `${p.x},${p.y}`).join(' ')}
                                                                    fill="none"
                                                                    stroke={color}
                                                                    strokeWidth="3"
                                                                    strokeLinejoin="round"
                                                                    strokeLinecap="round"
                                                                />
                                                                {/* 數據點 */}
                                                                {points.map((p, idx) => (
                                                                    <g key={idx}>
                                                                        <circle
                                                                            cx={p.x}
                                                                            cy={p.y}
                                                                            r={p.val > 0 ? 5 : 3}
                                                                            fill={color}
                                                                            stroke="white"
                                                                            strokeWidth="2"
                                                                            style={{ cursor: 'pointer' }}
                                                                        />
                                                                        <title>{year}年{p.month}月: {p.val}件</title>
                                                                    </g>
                                                                ))}
                                                            </g>
                                                        ))}

                                                        {/* X 軸標籤（月份） */}
                                                        {months.map((month, idx) => {
                                                            const x = padding.left + (idx / (months.length - 1)) * graphWidth;
                                                            return (
                                                                <text
                                                                    key={month}
                                                                    x={x}
                                                                    y={chartHeight - 15}
                                                                    textAnchor="middle"
                                                                    className="text-sm fill-gray-600"
                                                                    fontWeight="500"
                                                                >
                                                                    {month}月
                                                                </text>
                                                            );
                                                        })}

                                                        {/* Y 軸標籤 */}
                                                        {[0, Math.round(maxVal / 2), maxVal].map((val, idx) => (
                                                            <text
                                                                key={idx}
                                                                x={padding.left - 10}
                                                                y={padding.top + graphHeight * (1 - val / maxVal) + 4}
                                                                textAnchor="end"
                                                                className="text-xs fill-gray-500"
                                                            >
                                                                {val}
                                                            </text>
                                                        ))}
                                                    </svg>
                                                </div>
                                            );
                                        })()}

                                        {/* 年份圖例 */}
                                        <div className="flex gap-6 mt-4 justify-center text-sm">
                                            {[yearlyTrend.current_year - 3, yearlyTrend.current_year - 2, yearlyTrend.current_year - 1, yearlyTrend.current_year].map((year, idx) => {
                                                const colors = ['bg-gray-400', 'bg-blue-400', 'bg-purple-400', 'bg-indigo-500'];
                                                return (
                                                    <div key={year} className="flex items-center gap-2">
                                                        <div className={`w-4 h-1 rounded ${colors[idx]}`}></div>
                                                        <span className="text-nook-text font-medium">{year}年</span>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>

                                    {/* 年度總計 */}
                                    <div className="grid grid-cols-4 gap-4">
                                        {Object.entries(yearlyTrend.yearly_totals)
                                            .sort(([a], [b]) => Number(a) - Number(b))
                                            .map(([year, data]) => (
                                                <div key={year} className="bg-white/80 rounded-2xl p-4 nook-shadow text-center">
                                                    <p className="text-sm text-nook-text/60">{year}年</p>
                                                    <p className="text-2xl font-bold text-indigo-600">{data.youth}</p>
                                                    <p className="text-xs text-nook-text/60">青少年違規</p>
                                                    <p className="text-xs text-gray-400">總計 {data.total} 件</p>
                                                </div>
                                            ))}
                                    </div>
                                </>
                            )}

                            {!yearlyTrend && (
                                <div className="bg-white/80 rounded-2xl p-12 text-center">
                                    <p className="text-nook-text/60">載入趨勢資料中...</p>
                                </div>
                            )}
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export default EVehicleAnalysisPage;
