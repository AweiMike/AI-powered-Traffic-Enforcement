/**
 * Top5Card Component - Top 5 推薦卡片
 * 顯示精準執法推薦點位
 */

import React from 'react';
import { MapPin, TrendingUp, AlertTriangle, Car } from 'lucide-react';
import { SiteRecommendation } from '../api/client';

interface Top5CardProps {
  recommendation: SiteRecommendation;
  topicEmoji: string;
  topicColor: string;
}

export const Top5Card: React.FC<Top5CardProps> = ({
  recommendation,
  topicEmoji,
  topicColor
}) => {
  const { rank, site_name, district, metrics, statistics } = recommendation;

  // 根據排名選擇獎牌
  const getRankEmoji = (rank: number) => {
    switch (rank) {
      case 1: return '🥇';
      case 2: return '🥈';
      case 3: return '🥉';
      default: return `${rank}`;
    }
  };

  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-4 nook-shadow hover:shadow-lg transition-all duration-300 hover:-translate-y-1">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 ${topicColor} rounded-xl flex items-center justify-center text-lg font-bold shadow-md`}>
            {rank <= 3 ? getRankEmoji(rank) : rank}
          </div>
          <div>
            <h4 className="font-bold text-nook-text text-sm">{site_name}</h4>
            <div className="flex items-center gap-1 text-xs text-nook-text/60">
              <MapPin className="w-3 h-3" />
              <span>{district}</span>
            </div>
          </div>
        </div>
        <div className="text-2xl">{topicEmoji}</div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="bg-nook-cream/30 rounded-xl p-2 text-center">
          <p className="text-xs text-nook-text/60 mb-1">Score</p>
          <p className="text-lg font-bold text-nook-leaf">{metrics.score.toFixed(1)}</p>
        </div>
        <div className="bg-nook-cream/30 rounded-xl p-2 text-center">
          <p className="text-xs text-nook-text/60 mb-1">VPI</p>
          <p className="text-lg font-bold text-nook-orange">{metrics.vpi.toFixed(1)}</p>
        </div>
        <div className="bg-nook-cream/30 rounded-xl p-2 text-center">
          <p className="text-xs text-nook-text/60 mb-1">CRI</p>
          <p className="text-lg font-bold text-nook-red">{metrics.cri.toFixed(1)}</p>
        </div>
      </div>

      {/* Statistics */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1 text-nook-text/60">
          <Car className="w-3 h-3" />
          <span>{statistics.tickets} 件違規</span>
        </div>
        <div className="flex items-center gap-1 text-nook-text/60">
          <AlertTriangle className="w-3 h-3" />
          <span>{statistics.crashes} 件事故</span>
        </div>
      </div>
    </div>
  );
};

interface Top5ListProps {
  recommendations: SiteRecommendation[];
  topicEmoji: string;
  topicColor: string;
  loading?: boolean;
}

export const Top5List: React.FC<Top5ListProps> = ({
  recommendations,
  topicEmoji,
  topicColor,
  loading = false
}) => {
  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="bg-white/80 backdrop-blur-sm rounded-2xl p-4 nook-shadow animate-pulse">
            <div className="flex items-center gap-3 mb-3">
              <div className={`w-10 h-10 ${topicColor} rounded-xl`}></div>
              <div className="flex-1">
                <div className="h-4 bg-nook-cream rounded w-3/4 mb-2"></div>
                <div className="h-3 bg-nook-cream rounded w-1/2"></div>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="h-12 bg-nook-cream/30 rounded-xl"></div>
              <div className="h-12 bg-nook-cream/30 rounded-xl"></div>
              <div className="h-12 bg-nook-cream/30 rounded-xl"></div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!recommendations || recommendations.length === 0) {
    return (
      <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-8 nook-shadow text-center">
        <p className="text-nook-text/60">😴 目前沒有推薦點位資料</p>
        <p className="text-sm text-nook-text/40 mt-2">請先匯入資料或調整篩選條件</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {recommendations.map((rec) => (
        <Top5Card
          key={rec.site_id}
          recommendation={rec}
          topicEmoji={topicEmoji}
          topicColor={topicColor}
        />
      ))}
    </div>
  );
};
