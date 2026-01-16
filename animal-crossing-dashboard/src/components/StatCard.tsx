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
    <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow hover:shadow-xl transition-all duration-300 hover:-translate-y-1">
      <div className="flex items-start justify-between mb-4">
        <div className={`w-14 h-14 ${color} rounded-2xl flex items-center justify-center text-2xl shadow-lg`}>
          {emoji}
        </div>
        {change !== undefined && (
          <div className={`flex items-center gap-1 px-2 py-1 rounded-lg text-sm ${
            isPositive ? 'bg-nook-leaf/10 text-nook-leaf' : 'bg-nook-red/10 text-nook-red'
          }`}>
            {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            <span>{Math.abs(change)}%</span>
          </div>
        )}
      </div>
      <p className="text-nook-text/60 text-sm mb-1">{title}</p>
      <p className="text-3xl font-bold text-nook-text">
        {typeof value === 'number' ? value.toLocaleString() : value}
      </p>
    </div>
  );
};
