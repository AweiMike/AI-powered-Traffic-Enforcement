/**
 * BriefingCard Component - 班前勤務建議卡
 * 顯示當班的執法建議
 */

import React from 'react';
import { Clock, MapPin, Target, AlertCircle, Calendar } from 'lucide-react';
import { BriefingCard as BriefingCardData } from '../api/client';
import { Top5List } from './Top5Card';

interface BriefingCardProps {
  data: BriefingCardData;
  loading?: boolean;
}

export const BriefingCard: React.FC<BriefingCardProps> = ({ data, loading = false }) => {
  if (loading) {
    return (
      <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow animate-pulse">
        <div className="h-8 bg-nook-cream rounded w-1/3 mb-4"></div>
        <div className="space-y-3">
          <div className="h-4 bg-nook-cream rounded w-full"></div>
          <div className="h-4 bg-nook-cream rounded w-3/4"></div>
        </div>
      </div>
    );
  }

  const topicColors = {
    DUI: 'bg-nook-red',
    RED_LIGHT: 'bg-nook-orange',
    DANGEROUS_DRIVING: 'bg-nook-sky'
  };

  const topicColor = topicColors[data.topic.code] || 'bg-nook-leaf';

  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`w-12 h-12 ${topicColor} rounded-2xl flex items-center justify-center text-2xl shadow-lg`}>
              {data.topic.emoji}
            </div>
            <div>
              <h3 className="text-xl font-bold text-nook-text">{data.topic.name}</h3>
              <p className="text-sm text-nook-text/60">{data.topic.focus}</p>
            </div>
          </div>
          <div className="text-right">
            <div className="flex items-center gap-2 text-nook-text/60 text-sm mb-1">
              <Calendar className="w-4 h-4" />
              <span>{data.date}</span>
            </div>
            <div className="flex items-center gap-2 text-nook-text/60 text-sm">
              <Clock className="w-4 h-4" />
              <span>班別 {data.shift.shift_id} ({data.shift.time_range})</span>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-nook-cream/30 rounded-2xl p-3">
            <p className="text-xs text-nook-text/60 mb-1">分析期間</p>
            <p className="text-lg font-bold text-nook-text">{data.statistics.period_days} 天</p>
          </div>
          <div className="bg-nook-cream/30 rounded-2xl p-3">
            <p className="text-xs text-nook-text/60 mb-1">分析點位</p>
            <p className="text-lg font-bold text-nook-text">{data.statistics.total_sites} 處</p>
          </div>
        </div>
      </div>

      {/* Top 5 Recommendations */}
      <div className="mb-6">
        <h4 className="text-lg font-bold text-nook-text flex items-center gap-2 mb-4">
          <Target className="w-5 h-5 text-nook-leaf" />
          Top 5 推薦點位
        </h4>
        <Top5List
          recommendations={data.top5_sites}
          topicEmoji={data.topic.emoji}
          topicColor={topicColor}
        />
      </div>

      {/* Notes */}
      <div className="bg-nook-cream/30 rounded-2xl p-4">
        <h4 className="text-sm font-bold text-nook-text flex items-center gap-2 mb-3">
          <AlertCircle className="w-4 h-4 text-nook-orange" />
          注意事項
        </h4>
        <ul className="space-y-2">
          {data.notes.map((note, index) => (
            <li key={index} className="text-sm text-nook-text/80 flex items-start gap-2">
              <span className="mt-0.5">•</span>
              <span>{note}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Privacy Note */}
      <div className="mt-4 text-xs text-nook-text/40 text-center">
        🔒 {data.privacy_note}
      </div>
    </div>
  );
};
