/**
 * TrendCardSkeleton - <TrendCard> 的 React.Suspense fallback
 *
 * TrendCard 依賴 recharts（~700KB+ 未壓縮），故各頁改用 React.lazy 動態載入，
 * 讓 recharts 進入獨立 chunk、不再灌進主 bundle。此 skeleton 不 import recharts，
 * 留在主 bundle 內、極輕量，用於 <Suspense> 載入中的過渡畫面，
 * 版面（標題列 + Activity 圖示）與真正的 TrendCard 一致，避免載入完成時版面跳動。
 */
import React from 'react';
import { Activity } from 'lucide-react';

const TrendCardSkeleton: React.FC<{ title: string }> = ({ title }) => (
  <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden mb-6">
    <div className="p-4 border-b border-nook-cream/50 flex items-center gap-2">
      <Activity className="w-5 h-5 text-accent" />
      <h3 className="font-bold text-nook-text">{title}</h3>
    </div>
    <div className="p-6 space-y-4 animate-pulse">
      <div className="h-16 bg-surface-3 rounded-xl" />
      <div className="h-64 bg-surface-3 rounded-xl" />
    </div>
  </div>
);

export default TrendCardSkeleton;
