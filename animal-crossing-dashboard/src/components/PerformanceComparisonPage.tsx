/**
 * PerformanceComparisonPage - 成效比較頁面
 * 提供本期 vs 去年同期比較、趨勢圖表、報表導出功能
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
    Calendar, TrendingUp, TrendingDown, Minus, Download, FileText,
    ChevronLeft, ChevronRight, BarChart3, LineChart, AlertTriangle,
    CheckCircle, ArrowUpRight, ArrowDownRight
} from 'lucide-react';
import { apiClient, MonthlyStats } from '../api/client';

// ============================================
// 類型定義
// ============================================
interface TrendDataPoint {
    month: string;
    tickets: number;
    crashes: number;
    dui: number;
    red_light: number;
    dangerous: number;
}

// ============================================
// 工具函數
// ============================================
const getTrendIcon = (trend: string) => {
    switch (trend) {
        case '上升':
            return <TrendingUp className="w-5 h-5" />;
        case '下降':
            return <TrendingDown className="w-5 h-5" />;
        default:
            return <Minus className="w-5 h-5" />;
    }
};

const getTrendColor = (trend: string, isGoodWhenDown = true) => {
    const isGood = isGoodWhenDown ? trend === '下降' : trend === '上升';
    if (isGood) return 'text-nook-leaf bg-nook-leaf/10';
    if (trend === '持平') return 'text-nook-text/60 bg-nook-cream/30';
    return 'text-nook-red bg-nook-red/10';
};

// ============================================
// 月份選擇器組件
// ============================================
interface MonthSelectorProps {
    year: number;
    month: number;
    onChange: (year: number, month: number) => void;
}

const MonthSelector: React.FC<MonthSelectorProps> = ({ year, month, onChange }) => {
    const handlePrev = () => {
        if (month === 1) {
            onChange(year - 1, 12);
        } else {
            onChange(year, month - 1);
        }
    };

    const handleNext = () => {
        if (month === 12) {
            onChange(year + 1, 1);
        } else {
            onChange(year, month + 1);
        }
    };

    return (
        <div className="flex items-center gap-4 bg-white/80 backdrop-blur-sm rounded-2xl px-4 py-2 nook-shadow">
            <button
                onClick={handlePrev}
                className="p-2 hover:bg-nook-leaf/10 rounded-xl transition-colors"
            >
                <ChevronLeft className="w-5 h-5 text-nook-text" />
            </button>
            <div className="text-center min-w-[120px]">
                <span className="text-xl font-bold text-nook-text">{year} 年 {month} 月</span>
            </div>
            <button
                onClick={handleNext}
                className="p-2 hover:bg-nook-leaf/10 rounded-xl transition-colors"
            >
                <ChevronRight className="w-5 h-5 text-nook-text" />
            </button>
        </div>
    );
};

// ============================================
// 比較卡片組件
// ============================================
interface ComparisonCardProps {
    title: string;
    emoji: string;
    current: number;
    lastYear: number;
    change: number;
    trend: string;
    color: string;
}

const ComparisonCard: React.FC<ComparisonCardProps> = ({
    title, emoji, current, lastYear, change, trend, color
}) => {
    const diff = current - lastYear;
    const isImproved = trend === '下降';

    return (
        <div className={`bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow`}>
            <div className="flex items-center gap-3 mb-4">
                <div className={`w-12 h-12 ${color} rounded-2xl flex items-center justify-center text-2xl`}>
                    {emoji}
                </div>
                <div>
                    <h3 className="font-bold text-nook-text">{title}</h3>
                    <p className="text-sm text-nook-text/60">vs 去年同期</p>
                </div>
            </div>

            <div className="flex items-end justify-between mb-4">
                <div>
                    <p className="text-4xl font-bold text-nook-text">{current.toLocaleString()}</p>
                    <p className="text-sm text-nook-text/60">本期</p>
                </div>
                <div className={`flex items-center gap-2 px-4 py-2 rounded-xl ${getTrendColor(trend)}`}>
                    {isImproved ? <ArrowDownRight className="w-5 h-5" /> : diff > 0 ? <ArrowUpRight className="w-5 h-5" /> : <Minus className="w-5 h-5" />}
                    <span className="font-bold text-lg">{Math.abs(change)}%</span>
                </div>
            </div>

            <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                    <span className="text-nook-text/60">去年同期：</span>
                    <span className="font-medium text-nook-text">{lastYear.toLocaleString()}</span>
                </div>
                <div className={`flex items-center gap-1 ${diff > 0 ? 'text-nook-red' : diff < 0 ? 'text-nook-leaf' : 'text-nook-text/60'}`}>
                    {diff > 0 ? '+' : ''}{diff.toLocaleString()}
                </div>
            </div>
        </div>
    );
};

// ============================================
// 簡易趨勢圖組件
// ============================================
interface SimpleTrendChartProps {
    data: TrendDataPoint[];
    dataKey: keyof TrendDataPoint;
    color: string;
    title: string;
}

const SimpleTrendChart: React.FC<SimpleTrendChartProps> = ({ data, dataKey, color, title }) => {
    if (data.length === 0) {
        return (
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-4 nook-shadow">
                <h4 className="text-sm font-medium text-nook-text/60 mb-3">{title}</h4>
                <div className="h-24 flex items-center justify-center text-nook-text/40 text-sm">
                    暫無趨勢資料
                </div>
            </div>
        );
    }

    const values = data.map(d => d[dataKey] as number);
    const max = Math.max(...values, 1); // At least 1 to avoid division issues
    const sum = values.reduce((a, b) => a + b, 0);

    // If all values are 0, show empty state
    if (sum === 0) {
        return (
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-4 nook-shadow">
                <h4 className="text-sm font-medium text-nook-text/60 mb-3">{title}</h4>
                <div className="flex items-end gap-1 h-24">
                    {data.map((d, i) => (
                        <div key={i} className="flex-1 flex flex-col items-center gap-1">
                            <div className={`w-full ${color} rounded-t opacity-20`} style={{ height: '10%' }} />
                            <span className="text-[10px] text-nook-text/40">{d.month.slice(-2)}</span>
                        </div>
                    ))}
                </div>
                <p className="text-center text-xs text-nook-text/40 mt-2">此期間無資料</p>
            </div>
        );
    }

    return (
        <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-4 nook-shadow">
            <h4 className="text-sm font-bold text-nook-text mb-4">{title}</h4>
            <div className="flex items-end gap-2 h-32 pb-6">
                {data.map((d, i) => {
                    const value = d[dataKey] as number;
                    const height = Math.max((value / max) * 100, 4); // At least 4% height

                    // Fallback colors if custom colors fail
                    let barColor = color;
                    if (title.includes('違規')) barColor = 'bg-blue-500';
                    if (title.includes('事故')) barColor = 'bg-orange-500';

                    return (
                        <div key={i} className="flex-1 flex flex-col items-center gap-1 group relative h-full justify-end">
                            {/* Value Label */}
                            <span className={`text-xs font-bold mb-1 ${value === 0 ? 'opacity-0' : 'text-nook-text'}`}>
                                {value}
                            </span>

                            {/* Bar */}
                            <div
                                className={`w-full ${barColor} rounded-t-md transition-all duration-300 hover:opacity-80 shadow-sm`}
                                style={{ height: `${height}%`, minHeight: '4px' }}
                            />

                            {/* Month Label */}
                            <span className="text-xs font-medium text-nook-text/70 mt-1 absolute -bottom-6 w-full text-center">
                                {parseInt(d.month.split('/')[1])}月
                            </span>
                        </div>
                    );
                })}
            </div>
            <div className="flex justify-between text-xs font-medium text-nook-text/60 mt-4 px-1">
                <span>最小: {Math.min(...values)}</span>
                <span>最大: {Math.max(...values)}</span>
            </div>
        </div>
    );
};

// ============================================
// 主頁面組件
// ============================================

// ============================================
// 交叉分析趨勢圖組件 (雙軸折線圖)
// ============================================
const CrossAnalysisChart: React.FC<{ data: TrendDataPoint[] }> = ({ data }) => {
    if (data.length === 0) return null;

    const tickets = data.map(d => d.tickets);
    const crashes = data.map(d => d.crashes);

    // 計算兩個 Y 軸的範圍
    const maxTickets = Math.max(...tickets, 1) * 1.1; // 留 10% 空間
    const maxCrashes = Math.max(...crashes, 1) * 1.1;

    // SVG 尺寸與邊距
    const width = 1000;
    const height = 300;
    const padding = { top: 40, right: 60, bottom: 40, left: 60 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // 座標轉換函數
    const getX = (index: number) => padding.left + (index / (data.length - 1)) * chartWidth;
    const getY_Tickets = (val: number) => height - padding.bottom - (val / maxTickets) * chartHeight;
    const getY_Crashes = (val: number) => height - padding.bottom - (val / maxCrashes) * chartHeight;

    // 生成路徑數據
    const ticketPath = data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)},${getY_Tickets(d.tickets)}`).join(' ');
    const crashPath = data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)},${getY_Crashes(d.crashes)}`).join(' ');

    return (
        <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow mb-8">
            <h3 className="text-lg font-bold text-nook-text mb-2 flex items-center gap-2">
                <LineChart className="w-5 h-5 text-nook-leaf" />
                違規 vs 事故 交叉趨勢分析
            </h3>
            <p className="text-sm text-nook-text/60 mb-6">觀察「違規取締力度」與「交通事故發生」之關聯性</p>

            <div className="w-full overflow-x-auto">
                <div className="min-w-[600px] relative">
                    <svg viewBox={`0 0 ${width} ${height}`} className="w-full text-xs select-none">
                        {/* 網格線 */}
                        {[0, 0.25, 0.5, 0.75, 1].map((ratio, i) => {
                            const y = height - padding.bottom - chartHeight * ratio;
                            return (
                                <line
                                    key={i}
                                    x1={padding.left}
                                    y1={y}
                                    x2={width - padding.right}
                                    y2={y}
                                    stroke="#e5e7eb"
                                    strokeDasharray="4 4"
                                />
                            );
                        })}

                        {/* X 軸標籤 */}
                        {data.map((d, i) => (
                            <text
                                key={i}
                                x={getX(i)}
                                y={height - 10}
                                textAnchor="middle"
                                fill="#6b7280"
                                fontWeight="bold"
                            >
                                {d.month.split('/')[1]}月
                            </text>
                        ))}

                        {/* 左 Y 軸 (違規) */}
                        <text x={30} y={padding.top - 15} fill="#3b82f6" fontWeight="bold" fontSize="14" textAnchor="middle">違規數</text>
                        {[0, 0.5, 1].map((ratio, i) => {
                            const y = height - padding.bottom - chartHeight * ratio;
                            const val = Math.round(maxTickets * ratio);
                            return (
                                <text key={i} x={padding.left - 10} y={y + 4} textAnchor="end" fill="#3b82f6" fontWeight="bold">
                                    {val}
                                </text>
                            );
                        })}

                        {/* 右 Y 軸 (事故) */}
                        <text x={width - 30} y={padding.top - 15} fill="#f97316" fontWeight="bold" fontSize="14" textAnchor="middle">事故數</text>
                        {[0, 0.5, 1].map((ratio, i) => {
                            const y = height - padding.bottom - chartHeight * ratio;
                            const val = Math.round(maxCrashes * ratio);
                            return (
                                <text key={i} x={width - padding.right + 10} y={y + 4} textAnchor="start" fill="#f97316" fontWeight="bold">
                                    {val}
                                </text>
                            );
                        })}

                        {/* 數據線 - 違規 (藍色) */}
                        <path d={ticketPath} fill="none" stroke="#3b82f6" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" className="drop-shadow-md" />

                        {/* 數據線 - 事故 (橘色) */}
                        <path d={crashPath} fill="none" stroke="#f97316" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" className="drop-shadow-md" />

                        {/* 數據點與 Tooltip 互動區 */}
                        {data.map((d, i) => (
                            <g key={i} className="group cursor-pointer">
                                {/* 隱形觸發區 */}
                                <rect
                                    x={getX(i) - (chartWidth / (data.length - 1)) / 2}
                                    y={padding.top}
                                    width={chartWidth / (data.length - 1)}
                                    height={chartHeight}
                                    fill="transparent"
                                />
                                {/* 垂直指示線 (Hover 顯示) */}
                                <line
                                    x1={getX(i)} y1={padding.top} x2={getX(i)} y2={height - padding.bottom}
                                    stroke="#9ca3af" strokeDasharray="4 4"
                                    className="opacity-0 group-hover:opacity-100 transition-opacity"
                                />

                                {/* 違規點 */}
                                <circle cx={getX(i)} cy={getY_Tickets(d.tickets)} r="6" fill="#eff6ff" stroke="#3b82f6" strokeWidth="3" className="group-hover:r-8 transition-all" />

                                {/* 事故點 */}
                                <circle cx={getX(i)} cy={getY_Crashes(d.crashes)} r="6" fill="#fff7ed" stroke="#f97316" strokeWidth="3" className="group-hover:r-8 transition-all" />

                                {/* Tooltip */}
                                <g className="opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none transform -translate-y-2">
                                    {/* Tooltip Background */}
                                    <rect x={getX(i) - 60} y={padding.top - 10} width="120" height="70" rx="8" fill="rgba(255, 255, 255, 0.95)" stroke="#e5e7eb" strokeWidth="1" className="shadow-xl" />

                                    {/* Tooltip Content */}
                                    <text x={getX(i)} y={padding.top + 10} textAnchor="middle" fill="#374151" fontWeight="bold" fontSize="14">{d.month}</text>

                                    <circle cx={getX(i) - 30} cy={padding.top + 30} r="4" fill="#3b82f6" />
                                    <text x={getX(i) - 20} y={padding.top + 34} textAnchor="start" fill="#3b82f6" fontSize="12" fontWeight="bold">違規: {d.tickets}</text>

                                    <circle cx={getX(i) - 30} cy={padding.top + 50} r="4" fill="#f97316" />
                                    <text x={getX(i) - 20} y={padding.top + 54} textAnchor="start" fill="#f97316" fontSize="12" fontWeight="bold">事故: {d.crashes}</text>
                                </g>
                            </g>
                        ))}
                    </svg>
                </div>
            </div>

            {/* 圖例 */}
            <div className="flex justify-center gap-8 mt-4">
                <div className="flex items-center gap-2">
                    <span className="w-8 h-1 bg-blue-500 rounded-full h-1.5"></span>
                    <span className="text-sm font-bold text-nook-text">違規案件數 (左軸)</span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="w-8 h-1 bg-orange-500 rounded-full h-1.5"></span>
                    <span className="text-sm font-bold text-nook-text">交通事故數 (右軸)</span>
                </div>
            </div>
        </div>
    );
};

const PerformanceComparisonPage: React.FC = () => {
    const now = new Date();
    const [year, setYear] = useState(now.getFullYear());
    const [month, setMonth] = useState(now.getMonth() + 1);
    const [data, setData] = useState<MonthlyStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [trendData, setTrendData] = useState<TrendDataPoint[]>([]);

    // 載入月度數據
    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            setError(null);
            try {
                const result = await apiClient.getMonthlyStats(year, month);
                setData(result);
            } catch (err) {
                setError(err instanceof Error ? err.message : '載入失敗');
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [year, month]);

    // 載入趨勢數據（過去6個月）
    useEffect(() => {
        const fetchTrend = async () => {
            const promises = [];
            for (let i = 5; i >= 0; i--) {
                let m = month - i;
                let y = year;
                while (m <= 0) {
                    m += 12;
                    y -= 1;
                }
                const monthStr = `${y}/${m.toString().padStart(2, '0')}`;

                promises.push(
                    apiClient.getMonthlyStats(y, m)
                        .then(result => ({
                            month: monthStr,
                            tickets: result.current.tickets,
                            crashes: result.current.crashes,
                            dui: result.current.topics.dui,
                            red_light: result.current.topics.red_light,
                            dangerous: result.current.topics.dangerous_driving,
                        }))
                        .catch(err => {
                            console.warn(`Failed to fetch stats for ${monthStr}, using 0`, err);
                            return {
                                month: monthStr,
                                tickets: 0,
                                crashes: 0,
                                dui: 0,
                                red_light: 0,
                                dangerous: 0,
                            };
                        })
                );
            }

            const results = await Promise.all(promises);
            setTrendData(results);
        };
        fetchTrend();
    }, [year, month]);

    // 導出 CSV
    const handleExportCSV = () => {
        if (!data) return;

        const csvContent = [
            ['成效比較報表', `${year}年${month}月`],
            [],
            ['項目', '本期', '去年同期', '增減', '變化率'],
            ['違規案件', data.current.tickets, data.last_year.tickets,
                data.current.tickets - data.last_year.tickets, `${data.comparison.tickets_change}%`],
            ['交通事故', data.current.crashes, data.last_year.crashes,
                data.current.crashes - data.last_year.crashes, `${data.comparison.crashes_change}%`],
            [],
            ['主題分類', '本期', '去年同期'],
            ['酒駕', data.current.topics.dui, data.last_year.topics.dui],
            ['闖紅燈', data.current.topics.red_light, data.last_year.topics.red_light],
            ['危險駕駛', data.current.topics.dangerous_driving, data.last_year.topics.dangerous_driving],
        ].map(row => row.join(',')).join('\n');

        const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `成效比較_${year}年${month}月.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    // 導出 PDF（使用瀏覽器列印功能）
    const handlePrintReport = () => {
        window.print();
    };

    if (loading) {
        return (
            <div className="p-8">
                <div className="animate-pulse space-y-6">
                    <div className="h-12 bg-nook-cream rounded-2xl w-1/3"></div>
                    <div className="grid grid-cols-2 gap-6">
                        <div className="h-48 bg-nook-cream rounded-3xl"></div>
                        <div className="h-48 bg-nook-cream rounded-3xl"></div>
                    </div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-8">
                <div className="bg-nook-red/10 rounded-3xl p-8 text-center">
                    <AlertTriangle className="w-12 h-12 text-nook-red mx-auto mb-4" />
                    <h2 className="text-xl font-bold text-nook-red mb-2">載入失敗</h2>
                    <p className="text-nook-text/60">{error}</p>
                </div>
            </div>
        );
    }

    if (!data) return null;

    return (
        <div className="p-8 print:p-4">
            {/* 標題區 */}
            <div className="flex items-center justify-between mb-8 print:mb-4">
                <div>
                    <h2 className="text-2xl font-bold text-nook-text mb-2">📊 成效比較</h2>
                    <p className="text-nook-text/60">本期 vs 去年同期數據對比分析</p>
                </div>
                <div className="flex items-center gap-4 print:hidden">
                    <MonthSelector
                        year={year}
                        month={month}
                        onChange={(y, m) => { setYear(y); setMonth(m); }}
                    />
                    <button
                        onClick={handleExportCSV}
                        className="flex items-center gap-2 px-4 py-2 bg-nook-leaf text-white rounded-xl hover:bg-nook-leaf/90 transition-colors shadow-lg shadow-nook-leaf/30"
                    >
                        <Download className="w-4 h-4" />
                        導出 CSV
                    </button>
                    <button
                        onClick={handlePrintReport}
                        className="flex items-center gap-2 px-4 py-2 bg-white text-nook-text rounded-xl hover:bg-nook-cream transition-colors nook-shadow"
                    >
                        <FileText className="w-4 h-4" />
                        列印報表
                    </button>
                </div>
            </div>

            {/* 總覽卡片 */}
            <div className="grid grid-cols-2 gap-6 mb-8">
                <ComparisonCard
                    title="違規案件"
                    emoji="📋"
                    current={data.current.tickets}
                    lastYear={data.last_year.tickets}
                    change={data.comparison.tickets_change}
                    trend={data.comparison.tickets_trend}
                    color="bg-nook-sky/20"
                />
                <ComparisonCard
                    title="交通事故"
                    emoji="🚗"
                    current={data.current.crashes}
                    lastYear={data.last_year.crashes}
                    change={data.comparison.crashes_change}
                    trend={data.comparison.crashes_trend}
                    color="bg-nook-orange/20"
                />
            </div>

            {/* 事故嚴重度比較 */}
            {data.current.severity && (
                <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow mb-8">
                    <h3 className="text-lg font-bold text-nook-text mb-6 flex items-center gap-2">
                        <AlertTriangle className="w-5 h-5 text-nook-red" />
                        事故嚴重度比較
                    </h3>
                    <div className="grid grid-cols-2 gap-6">
                        {/* A1 死亡事故 */}
                        <div className="bg-red-50 rounded-2xl p-5 border-l-4 border-red-500">
                            <div className="flex items-center gap-3 mb-4">
                                <span className="text-3xl">💀</span>
                                <div>
                                    <span className="font-bold text-nook-text text-lg">A1 死亡事故</span>
                                    <p className="text-xs text-nook-text/50">最高嚴重等級</p>
                                </div>
                            </div>
                            <div className="flex items-end justify-between">
                                <div>
                                    <p className="text-4xl font-bold text-red-600">{data.current.severity.a1}</p>
                                    <p className="text-sm text-nook-text/60">本期</p>
                                </div>
                                <div className="text-right">
                                    <p className="text-2xl font-medium text-nook-text/60">{data.last_year.severity?.a1 || 0}</p>
                                    <p className="text-sm text-nook-text/40">去年同期</p>
                                </div>
                            </div>
                            <div className="mt-3 pt-3 border-t border-red-200">
                                <div className={`text-sm font-medium ${data.current.severity.a1 < (data.last_year.severity?.a1 || 0) ? 'text-nook-leaf' :
                                    data.current.severity.a1 > (data.last_year.severity?.a1 || 0) ? 'text-nook-red' : 'text-nook-text/60'
                                    }`}>
                                    {data.current.severity.a1 < (data.last_year.severity?.a1 || 0) ? '✓ 減少 ' :
                                        data.current.severity.a1 > (data.last_year.severity?.a1 || 0) ? '↑ 增加 ' : '持平 '}
                                    {Math.abs(data.current.severity.a1 - (data.last_year.severity?.a1 || 0))} 件
                                </div>
                            </div>
                        </div>

                        {/* A2 受傷事故 */}
                        <div className="bg-orange-50 rounded-2xl p-5 border-l-4 border-orange-500">
                            <div className="flex items-center gap-3 mb-4">
                                <span className="text-3xl">🏥</span>
                                <div>
                                    <span className="font-bold text-nook-text text-lg">A2 受傷事故</span>
                                    <p className="text-xs text-nook-text/50">需送醫救護</p>
                                </div>
                            </div>
                            <div className="flex items-end justify-between">
                                <div>
                                    <p className="text-4xl font-bold text-orange-600">{data.current.severity.a2}</p>
                                    <p className="text-sm text-nook-text/60">本期</p>
                                </div>
                                <div className="text-right">
                                    <p className="text-2xl font-medium text-nook-text/60">{data.last_year.severity?.a2 || 0}</p>
                                    <p className="text-sm text-nook-text/40">去年同期</p>
                                </div>
                            </div>
                            <div className="mt-3 pt-3 border-t border-orange-200">
                                <div className={`text-sm font-medium ${data.current.severity.a2 < (data.last_year.severity?.a2 || 0) ? 'text-nook-leaf' :
                                    data.current.severity.a2 > (data.last_year.severity?.a2 || 0) ? 'text-nook-red' : 'text-nook-text/60'
                                    }`}>
                                    {data.current.severity.a2 < (data.last_year.severity?.a2 || 0) ? '✓ 減少 ' :
                                        data.current.severity.a2 > (data.last_year.severity?.a2 || 0) ? '↑ 增加 ' : '持平 '}
                                    {Math.abs(data.current.severity.a2 - (data.last_year.severity?.a2 || 0))} 件
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* 主題分類比較 */}
            <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow mb-8">
                <h3 className="text-lg font-bold text-nook-text mb-6 flex items-center gap-2">
                    <BarChart3 className="w-5 h-5 text-nook-leaf" />
                    三大主題比較
                </h3>
                <div className="grid grid-cols-3 gap-6">
                    {/* 酒駕 */}
                    <div className="bg-nook-red/5 rounded-2xl p-5">
                        <div className="flex items-center gap-3 mb-4">
                            <span className="text-3xl">🍺</span>
                            <span className="font-bold text-nook-text">酒駕</span>
                        </div>
                        <div className="flex items-end justify-between">
                            <div>
                                <p className="text-3xl font-bold text-nook-text">{data.current.topics.dui}</p>
                                <p className="text-sm text-nook-text/60">本期</p>
                            </div>
                            <div className="text-right">
                                <p className="text-xl font-medium text-nook-text/60">{data.last_year.topics.dui}</p>
                                <p className="text-sm text-nook-text/40">去年同期</p>
                            </div>
                        </div>
                        <div className="mt-3 pt-3 border-t border-nook-text/10">
                            <div className={`text-sm font-medium ${data.current.topics.dui < data.last_year.topics.dui ? 'text-nook-leaf' :
                                data.current.topics.dui > data.last_year.topics.dui ? 'text-nook-red' : 'text-nook-text/60'
                                }`}>
                                {data.current.topics.dui < data.last_year.topics.dui ? '✓ 減少 ' :
                                    data.current.topics.dui > data.last_year.topics.dui ? '↑ 增加 ' : '持平 '}
                                {Math.abs(data.current.topics.dui - data.last_year.topics.dui)} 件
                            </div>
                        </div>
                    </div>

                    {/* 闖紅燈 */}
                    <div className="bg-nook-orange/5 rounded-2xl p-5">
                        <div className="flex items-center gap-3 mb-4">
                            <span className="text-3xl">🚦</span>
                            <span className="font-bold text-nook-text">闖紅燈</span>
                        </div>
                        <div className="flex items-end justify-between">
                            <div>
                                <p className="text-3xl font-bold text-nook-text">{data.current.topics.red_light}</p>
                                <p className="text-sm text-nook-text/60">本期</p>
                            </div>
                            <div className="text-right">
                                <p className="text-xl font-medium text-nook-text/60">{data.last_year.topics.red_light}</p>
                                <p className="text-sm text-nook-text/40">去年同期</p>
                            </div>
                        </div>
                        <div className="mt-3 pt-3 border-t border-nook-text/10">
                            <div className={`text-sm font-medium ${data.current.topics.red_light < data.last_year.topics.red_light ? 'text-nook-leaf' :
                                data.current.topics.red_light > data.last_year.topics.red_light ? 'text-nook-red' : 'text-nook-text/60'
                                }`}>
                                {data.current.topics.red_light < data.last_year.topics.red_light ? '✓ 減少 ' :
                                    data.current.topics.red_light > data.last_year.topics.red_light ? '↑ 增加 ' : '持平 '}
                                {Math.abs(data.current.topics.red_light - data.last_year.topics.red_light)} 件
                            </div>
                        </div>
                    </div>

                    {/* 危險駕駛 */}
                    <div className="bg-nook-sky/5 rounded-2xl p-5">
                        <div className="flex items-center gap-3 mb-4">
                            <span className="text-3xl">⚡</span>
                            <span className="font-bold text-nook-text">危險駕駛</span>
                        </div>
                        <div className="flex items-end justify-between">
                            <div>
                                <p className="text-3xl font-bold text-nook-text">{data.current.topics.dangerous_driving}</p>
                                <p className="text-sm text-nook-text/60">本期</p>
                            </div>
                            <div className="text-right">
                                <p className="text-xl font-medium text-nook-text/60">{data.last_year.topics.dangerous_driving}</p>
                                <p className="text-sm text-nook-text/40">去年同期</p>
                            </div>
                        </div>
                        <div className="mt-3 pt-3 border-t border-nook-text/10">
                            <div className={`text-sm font-medium ${data.current.topics.dangerous_driving < data.last_year.topics.dangerous_driving ? 'text-nook-leaf' :
                                data.current.topics.dangerous_driving > data.last_year.topics.dangerous_driving ? 'text-nook-red' : 'text-nook-text/60'
                                }`}>
                                {data.current.topics.dangerous_driving < data.last_year.topics.dangerous_driving ? '✓ 減少 ' :
                                    data.current.topics.dangerous_driving > data.last_year.topics.dangerous_driving ? '↑ 增加 ' : '持平 '}
                                {Math.abs(data.current.topics.dangerous_driving - data.last_year.topics.dangerous_driving)} 件
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* 趨勢圖表區 */}
            {trendData.length > 0 && (
                <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow mb-8 print:hidden">
                    <h3 className="text-lg font-bold text-nook-text mb-6 flex items-center gap-2">
                        <LineChart className="w-5 h-5 text-nook-leaf" />
                        近 6 個月趨勢
                    </h3>
                    <div className="grid grid-cols-2 gap-4">
                        <SimpleTrendChart data={trendData} dataKey="tickets" color="bg-nook-sky" title="違規案件趨勢" />
                        <SimpleTrendChart data={trendData} dataKey="crashes" color="bg-nook-orange" title="交通事故趨勢" />
                    </div>
                </div>
            )}

            {/* 交叉分析趨勢圖 */}
            {trendData.length > 0 && (
                <CrossAnalysisChart data={trendData} />
            )}

            {/* 成效摘要 */}
            <div className="bg-nook-leaf/10 rounded-3xl p-6">
                <h3 className="text-lg font-bold text-nook-text mb-4 flex items-center gap-2">
                    <CheckCircle className="w-5 h-5 text-nook-leaf" />
                    成效摘要
                </h3>
                <div className="grid grid-cols-2 gap-4">
                    <div className="bg-white/80 rounded-2xl p-4">
                        <p className="text-sm text-nook-text/60 mb-2">違規案件</p>
                        <p className={`text-lg font-bold ${data.comparison.tickets_trend === '下降' ? 'text-nook-leaf' :
                            data.comparison.tickets_trend === '上升' ? 'text-nook-red' : 'text-nook-text'
                            }`}>
                            {data.comparison.tickets_trend === '下降' ? '✓ 下降' :
                                data.comparison.tickets_trend === '上升' ? '↑ 上升' : '持平'} {Math.abs(data.comparison.tickets_change)}%
                        </p>
                    </div>
                    <div className="bg-white/80 rounded-2xl p-4">
                        <p className="text-sm text-nook-text/60 mb-2">交通事故</p>
                        <p className={`text-lg font-bold ${data.comparison.crashes_trend === '下降' ? 'text-nook-leaf' :
                            data.comparison.crashes_trend === '上升' ? 'text-nook-red' : 'text-nook-text'
                            }`}>
                            {data.comparison.crashes_trend === '下降' ? '✓ 下降' :
                                data.comparison.crashes_trend === '上升' ? '↑ 上升' : '持平'} {Math.abs(data.comparison.crashes_change)}%
                        </p>
                    </div>
                </div>
                <p className="mt-4 text-sm text-nook-text/60 text-center">
                    🔒 {data.note}
                </p>
            </div>
        </div>
    );
};

export default PerformanceComparisonPage;
