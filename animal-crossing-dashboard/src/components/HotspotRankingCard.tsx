/**
 * HotspotRankingCard - 熱點排名卡片組件
 * 顯示事故或違規熱點的 Top N 排名
 */

import React, { useState, useEffect } from 'react';
import { MapPin, TrendingUp, TrendingDown, Minus, AlertTriangle, Award } from 'lucide-react';
import { apiClient } from '../api/client';

interface HotspotItem {
    rank: number;
    location: string;
    district: string;
    a1_count?: number;
    a2_count?: number;
    a3_count?: number;
    total: number;
    count?: number;
    trend_pct?: number | null;
    latitude?: number | null;
    longitude?: number | null;
}

interface HotspotRankingCardProps {
    type: 'accident' | 'ticket';
    days?: number;
    year?: number;
    month?: number;
    topN?: number;
    severity?: string;
    topic?: string;
    title?: string;
    onHotspotClick?: (item: HotspotItem) => void;
}

const HotspotRankingCard: React.FC<HotspotRankingCardProps> = ({
    type,
    days = 30,
    year,
    month,
    topN = 5,
    severity,
    topic,
    title,
    onHotspotClick
}) => {
    const [hotspots, setHotspots] = useState<HotspotItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [totalInPeriod, setTotalInPeriod] = useState(0);

    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            setError(null);
            try {
                if (type === 'accident') {
                    const result = await apiClient.getAccidentHotspotsRanking({
                        days,
                        year,
                        month,
                        topN,
                        severity
                    });
                    setHotspots(result.hotspots || []);
                    setTotalInPeriod(result.total_in_period || 0);
                } else {
                    const result = await apiClient.getTicketHotspots(days, topN, topic, year, month);
                    setHotspots(result.hotspots || []);
                }
            } catch (err) {
                console.error('Failed to fetch hotspots:', err);
                setError('載入熱點資料失敗');
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [type, days, year, month, topN, severity, topic]);

    const getRankBadge = (rank: number) => {
        if (rank === 1) return <span className="w-6 h-6 flex items-center justify-center bg-yellow-400 text-white rounded-full text-xs font-bold">🥇</span>;
        if (rank === 2) return <span className="w-6 h-6 flex items-center justify-center bg-gray-300 text-white rounded-full text-xs font-bold">🥈</span>;
        if (rank === 3) return <span className="w-6 h-6 flex items-center justify-center bg-amber-600 text-white rounded-full text-xs font-bold">🥉</span>;
        return <span className="w-6 h-6 flex items-center justify-center bg-nook-leaf/20 text-nook-leaf rounded-full text-xs font-bold">{rank}</span>;
    };

    const getTrendIcon = (trend: number | null | undefined) => {
        if (trend === null || trend === undefined) return <Minus className="w-4 h-4 text-gray-400" />;
        if (trend > 0) return <TrendingUp className="w-4 h-4 text-red-500" />;
        if (trend < 0) return <TrendingDown className="w-4 h-4 text-green-500" />;
        return <Minus className="w-4 h-4 text-gray-400" />;
    };

    const getTrendColor = (trend: number | null | undefined) => {
        if (trend === null || trend === undefined) return 'text-gray-400';
        if (trend > 0) return 'text-red-500';
        if (trend < 0) return 'text-green-500';
        return 'text-gray-400';
    };

    const defaultTitle = type === 'accident'
        ? `🚨 事故熱點 Top ${topN}`
        : `📋 違規熱點 Top ${topN}`;

    if (loading) {
        return (
            <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow">
                <h3 className="text-lg font-bold text-nook-text mb-4">{title || defaultTitle}</h3>
                <div className="animate-pulse space-y-3">
                    {[...Array(topN)].map((_, i) => (
                        <div key={i} className="h-12 bg-nook-cream rounded-xl"></div>
                    ))}
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow">
                <h3 className="text-lg font-bold text-nook-text mb-4">{title || defaultTitle}</h3>
                <div className="text-center py-8 text-nook-text/60">
                    <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-nook-red/60" />
                    <p>{error}</p>
                </div>
            </div>
        );
    }

    return (
        <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-nook-text flex items-center gap-2">
                    {type === 'accident' ? <AlertTriangle className="w-5 h-5 text-red-500" /> : <Award className="w-5 h-5 text-blue-500" />}
                    {title || defaultTitle}
                </h3>
                {type === 'accident' && totalInPeriod > 0 && (
                    <span className="text-sm text-nook-text/60 bg-nook-cream/50 px-3 py-1 rounded-full">
                        總計 {totalInPeriod} 件
                    </span>
                )}
            </div>

            {hotspots.length === 0 ? (
                <div className="text-center py-8 text-nook-text/60">
                    <MapPin className="w-8 h-8 mx-auto mb-2 opacity-40" />
                    <p>此期間無熱點資料</p>
                </div>
            ) : (
                <div className="space-y-2">
                    {hotspots.map((item) => (
                        <div
                            key={item.rank}
                            className={`flex items-center gap-3 p-3 rounded-xl transition-all ${onHotspotClick
                                ? 'hover:bg-nook-leaf/10 cursor-pointer'
                                : 'bg-nook-cream/30'
                                }`}
                            onClick={() => onHotspotClick?.(item)}
                        >
                            {/* 排名徽章 */}
                            {getRankBadge(item.rank)}

                            {/* 地點資訊 */}
                            <div className="flex-1 min-w-0">
                                <p className="font-bold text-nook-text truncate" title={item.location}>
                                    {item.location}
                                </p>
                                <p className="text-xs text-nook-text/60">{item.district}</p>
                            </div>

                            {/* 數量 */}
                            <div className="text-right">
                                <p className="font-bold text-nook-text text-lg">
                                    {type === 'accident' ? item.total : (item.count || item.total)}
                                </p>
                                {type === 'accident' && item.a1_count !== undefined && (
                                    <p className="text-xs text-nook-text/60">
                                        A1:{item.a1_count} A2:{item.a2_count}
                                    </p>
                                )}
                            </div>

                            {/* 趨勢 */}
                            {item.trend_pct !== undefined && item.trend_pct !== null && (
                                <div className={`flex items-center gap-1 min-w-[60px] justify-end ${getTrendColor(item.trend_pct)}`}>
                                    {getTrendIcon(item.trend_pct)}
                                    <span className="text-sm font-medium">
                                        {item.trend_pct > 0 ? '+' : ''}{item.trend_pct}%
                                    </span>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* 說明 */}
            <div className="mt-4 pt-3 border-t border-nook-cream/50 text-xs text-nook-text/50 text-center">
                {type === 'accident' ? (
                    <span>📊 依事故總數排名 · 趨勢為去年同期比較</span>
                ) : (
                    <span>📋 依違規件數排名</span>
                )}
            </div>
        </div>
    );
};

export default HotspotRankingCard;
