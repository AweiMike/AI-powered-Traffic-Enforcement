/**
 * MonthlyComparison Component - 月度同期比較
 * 顯示當月與去年同期的比較
 */

import React from 'react';
import { Calendar, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { MonthlyStats } from '../api/client';

interface MonthlyComparisonProps {
  data: MonthlyStats;
  loading?: boolean;
}

export const MonthlyComparison: React.FC<MonthlyComparisonProps> = ({ data, loading = false }) => {
  if (loading) {
    return (
      <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow animate-pulse">
        <div className="h-6 bg-nook-cream rounded w-1/3 mb-4"></div>
        <div className="space-y-3">
          <div className="h-20 bg-nook-cream rounded"></div>
          <div className="h-20 bg-nook-cream rounded"></div>
        </div>
      </div>
    );
  }

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

  const getTrendColor = (trend: string) => {
    switch (trend) {
      case '上升':
        return 'text-nook-red bg-nook-red/10';
      case '下降':
        return 'text-nook-leaf bg-nook-leaf/10';
      default:
        return 'text-nook-text/60 bg-nook-cream/30';
    }
  };

  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow">
      <div className="flex items-center gap-2 mb-4">
        <Calendar className="w-5 h-5 text-nook-leaf" />
        <h3 className="text-lg font-bold text-nook-text">
          {data.period.year} 年 {data.period.month} 月 vs 去年同期
        </h3>
      </div>

      {/* Tickets Comparison */}
      <div className="mb-4 bg-nook-cream/30 rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-sm text-nook-text/60 mb-1">違規案件</p>
            <p className="text-2xl font-bold text-nook-text">
              {data.current.tickets.toLocaleString()}
            </p>
          </div>
          <div className={`flex items-center gap-2 px-3 py-2 rounded-xl ${getTrendColor(data.comparison.tickets_trend)}`}>
            {getTrendIcon(data.comparison.tickets_trend)}
            <span className="font-bold">{Math.abs(data.comparison.tickets_change)}%</span>
          </div>
        </div>
        <div className="text-sm text-nook-text/60">
          去年同期：{data.last_year.tickets.toLocaleString()} 件
        </div>
      </div>

      {/* Crashes Comparison */}
      <div className="bg-nook-cream/30 rounded-2xl p-4 mb-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-sm text-nook-text/60 mb-1">交通事故</p>
            <p className="text-2xl font-bold text-nook-text">
              {data.current.crashes.toLocaleString()}
            </p>
          </div>
          <div className={`flex items-center gap-2 px-3 py-2 rounded-xl ${getTrendColor(data.comparison.crashes_trend)}`}>
            {getTrendIcon(data.comparison.crashes_trend)}
            <span className="font-bold">{Math.abs(data.comparison.crashes_change)}%</span>
          </div>
        </div>
        <div className="text-sm text-nook-text/60">
          去年同期：{data.last_year.crashes.toLocaleString()} 件
        </div>
      </div>

      {/* Topics Breakdown */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-nook-red/10 rounded-xl p-3 text-center">
          <div className="text-2xl mb-1">🍺</div>
          <div className="text-xs text-nook-text/60 mb-1">酒駕</div>
          <div className="text-lg font-bold text-nook-text">{data.current.topics.dui}</div>
          <div className="text-xs text-nook-text/40">({data.last_year.topics.dui})</div>
        </div>
        <div className="bg-nook-orange/10 rounded-xl p-3 text-center">
          <div className="text-2xl mb-1">🚦</div>
          <div className="text-xs text-nook-text/60 mb-1">闖紅燈</div>
          <div className="text-lg font-bold text-nook-text">{data.current.topics.red_light}</div>
          <div className="text-xs text-nook-text/40">({data.last_year.topics.red_light})</div>
        </div>
        <div className="bg-nook-sky/10 rounded-xl p-3 text-center">
          <div className="text-2xl mb-1">⚡</div>
          <div className="text-xs text-nook-text/60 mb-1">危險駕駛</div>
          <div className="text-lg font-bold text-nook-text">{data.current.topics.dangerous_driving}</div>
          <div className="text-xs text-nook-text/40">({data.last_year.topics.dangerous_driving})</div>
        </div>
      </div>

      {/* Privacy Note */}
      <div className="mt-4 text-xs text-nook-text/40 text-center">
        🔒 {data.note}
      </div>
    </div>
  );
};
