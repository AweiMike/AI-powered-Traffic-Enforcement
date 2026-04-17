/**
 * StatCard Component - 統計卡片
 * 顯示關鍵指標的卡片組件
 */

import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';

export interface StatCardProps {
  title: string;
  value: string | number;
  change?: number;
  icon?: React.ReactNode;
  emoji: string;
  color: string;
  loading?: boolean;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  change,
  emoji,
  color,
  loading = false
}) => {
  const isPositive = change !== undefined && change > 0;

  if (loading) {
    return (
      <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow animate-pulse">
        <div className={`w-14 h-14 ${color} rounded-2xl mb-4`}></div>
        <div className="h-4 bg-nook-cream rounded w-2/3 mb-2"></div>
        <div className="h-8 bg-nook-cream rounded w-1/2"></div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl p-5 nook-shadow hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className={`w-10 h-10 ${color} rounded-xl flex items-center justify-center text-xl`}>
          {emoji}
        </div>
        {change !== undefined && (
          <div className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium tabular-nums ${
            isPositive ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'
          }`}>
            {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
            <span>{Math.abs(change)}%</span>
          </div>
        )}
      </div>
      <p className="text-slate-500 text-xs mb-1 font-medium">{title}</p>
      <p className="text-[28px] font-bold text-slate-900 tabular-nums tracking-tight leading-none">
        {typeof value === 'number' ? value.toLocaleString() : value}
      </p>
    </div>
  );
};
