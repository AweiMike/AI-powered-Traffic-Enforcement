/**
 * 違規分析頁面
 * 顯示違規統計、行政區分佈與重點違規項目
 */

import React from 'react';
import { useViolationStats } from '../hooks/useAPI';
import { Loader2, AlertTriangle, MapPin, BarChart3, AlertCircle } from 'lucide-react';

// ============================================
// 子元件：簡易長條圖
// ============================================
const BarChart: React.FC<{
  data: Array<{ label: string; value: number; percentage: number }>;
  colorClass: string;
}> = ({ data, colorClass }) => {
  return (
    <div className="space-y-3">
      {data.map((item, idx) => (
        <div key={idx} className="flex items-center gap-3 text-sm">
          <div className="w-24 font-medium text-nook-text truncate" title={item.label}>
            {item.label}
          </div>
          <div className="flex-1 h-3 bg-nook-leaf/10 rounded-full overflow-hidden">
            <div
              className={`h-full ${colorClass} rounded-full transition-all duration-500`}
              style={{ width: `${item.percentage}%` }}
            />
          </div>
          <div className="w-16 text-right text-nook-text/60 text-xs">
            {item.value.toLocaleString()}
          </div>
        </div>
      ))}
    </div>
  );
};

// ============================================
// 子元件：主題卡片
// ============================================
const TopicCard: React.FC<{
  title: string;
  count: number;
  total: number;
  emoji: string;
  color: string;
  bgColor: string;
}> = ({ title, count, total, emoji, color, bgColor }) => {
  const percentage = total > 0 ? Math.round((count / total) * 100) : 0;

  return (
    <div className={`${bgColor} rounded-2xl p-4 flex items-center gap-4 transition-transform hover:-translate-y-1`}>
      <div className={`w-12 h-12 ${color.replace('text-', 'bg-')}/20 rounded-full flex items-center justify-center text-2xl`}>
        {emoji}
      </div>
      <div className="flex-1">
        <p className="text-sm text-nook-text/60 font-medium">{title}</p>
        <div className="flex items-end gap-2">
          <span className={`text-2xl font-bold ${color}`}>{count.toLocaleString()}</span>
          <span className="text-xs text-nook-text/40 mb-1">({percentage}%)</span>
        </div>
      </div>
    </div>
  );
};

// ============================================
// 主頁面元件
// ============================================
const ViolationsPage: React.FC = () => {
  const { data, loading, error } = useViolationStats(30);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center h-[50vh]">
        <div className="text-center">
          <Loader2 className="w-10 h-10 animate-spin text-nook-leaf mx-auto mb-4" />
          <p className="text-nook-text/60">正在分析違規數據...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-nook-red/10 border border-nook-red/20 rounded-2xl p-6 flex items-center gap-4">
          <AlertCircle className="w-8 h-8 text-nook-red" />
          <div>
            <h3 className="font-bold text-nook-red">無法載入數據</h3>
            <p className="text-nook-red/80">{error.message}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="p-8 space-y-6">
      {/* 標題區 */}
      <div>
        <h2 className="text-2xl font-bold text-nook-text flex items-center gap-2 mb-2">
          <BarChart3 className="w-6 h-6" />
          違規分析
        </h2>
        <p className="text-nook-text/60">
          過去 30 天 ({data.period.start_date} ~ {data.period.end_date}) 的違規統計分析
        </p>
      </div>

      {/* 主題統計卡片 */}
      <div className="grid grid-cols-4 gap-4">
        <TopicCard
          title="總違規數"
          count={data.total_tickets}
          total={data.total_tickets}
          emoji="📋"
          color="text-nook-text"
          bgColor="bg-white"
        />
        <TopicCard
          title="酒後駕車"
          count={data.topics.dui}
          total={data.total_tickets}
          emoji="🍺"
          color="text-nook-red"
          bgColor="bg-white"
        />
        <TopicCard
          title="闖紅燈"
          count={data.topics.red_light}
          total={data.total_tickets}
          emoji="🚦"
          color="text-nook-orange"
          bgColor="bg-white"
        />
        <TopicCard
          title="危險駕駛"
          count={data.topics.dangerous_driving}
          total={data.total_tickets}
          emoji="⚡"
          color="text-nook-sky"
          bgColor="bg-white"
        />
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* 行政區分佈 */}
        <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow">
          <div className="flex items-center gap-2 mb-6">
            <MapPin className="w-5 h-5 text-nook-leaf" />
            <h3 className="font-bold text-nook-text">各行政區違規熱點</h3>
          </div>
          
          <div className="h-[400px] overflow-y-auto pr-2 custom-scrollbar">
            <BarChart
              data={data.districts.map(d => ({
                label: d.district,
                value: d.count,
                percentage: d.percentage
              }))}
              colorClass="bg-nook-leaf"
            />
          </div>
        </div>

        {/* 重點違規項目 */}
        <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow">
          <div className="flex items-center gap-2 mb-6">
            <AlertTriangle className="w-5 h-5 text-nook-orange" />
            <h3 className="font-bold text-nook-text">前十大違規項目</h3>
          </div>

          <div className="space-y-4">
            {data.top_violations.map((item, idx) => {
              const percentage = Math.round((item.count / data.total_tickets) * 100);
              return (
                <div key={idx} className="relative">
                  <div className="flex justify-between items-start mb-1">
                    <div className="flex items-center gap-2">
                      <span className={`
                        w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold
                        ${idx < 3 ? 'bg-nook-orange text-white' : 'bg-nook-leaf/20 text-nook-text'}
                      `}>
                        {idx + 1}
                      </span>
                      <span className="font-medium text-nook-text text-sm max-w-[200px] truncate" title={item.name}>
                        {item.name || item.code}
                      </span>
                    </div>
                    <span className="font-bold text-nook-text text-sm">
                      {item.count.toLocaleString()}
                    </span>
                  </div>
                  
                  {/* 進度條背景 */}
                  <div className="w-full h-2 bg-nook-leaf/5 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${idx < 3 ? 'bg-nook-orange' : 'bg-nook-leaf'}`}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ViolationsPage;
