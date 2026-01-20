/**
 * Main App Component - 精準執法儀表板
 * 專注於事故分析和違規取締
 */

import React, { useState } from 'react';
import {
  Home,
  AlertTriangle,
  FileText,
  Settings,
  Leaf,
  Bell,
  Search,
  TreePine,
  MapPin,
  Users,
  Calendar,
  ChevronRight,
  BarChart3,
  Shield
} from 'lucide-react';

// Import custom components
import { StatCard } from './components/StatCard';
import { TopicSelector } from './components/TopicSelector';
import { ShiftSelector } from './components/ShiftSelector';
import { Top5List } from './components/Top5Card';
import { BriefingCard } from './components/BriefingCard';
import { MonthlyComparison } from './components/MonthlyComparison';
import DataImportPage from './components/DataImportPage';
import ViolationsPage from './components/ViolationsPage';
import { HotspotMap } from './components/HotspotMap';
import AccidentAnalysisPage from './components/AccidentAnalysisPage';
import ElderlyPreventionPage from './components/ElderlyPreventionPage';
import PerformanceComparisonPage from './components/PerformanceComparisonPage';

// Import hooks
import {
  useOverview,
  useTop5,
  useMonthlyStats,
  useBriefingCard,
  useHealthCheck,
  useHeatmap,
  useAccidentHotspots,
  useCrossAnalysis
} from './hooks/useAPI';

import { TopicCode } from './api/client';

// ============================================
// Sidebar Component
// ============================================
interface SidebarProps {
  activeView: string;
  onViewChange: (view: string) => void;
}

const Sidebar: React.FC<SidebarProps> = ({ activeView, onViewChange }) => {
  const menuItems = [
    { id: 'dashboard', icon: Home, label: '總覽', emoji: '🏠', description: '整體統計概覽' },
    { id: 'accidents', icon: MapPin, label: '執法缺口分析', emoji: '🎯', description: '事故與違規綜合分析' },
    { id: 'elderly', icon: Users, label: '高齡者事故防制專區', emoji: '👴', description: '高齡者事故防治' },
    { id: 'monthly', icon: Calendar, label: '成效比較', emoji: '📊', description: '同期比較與報表' },
    { id: 'briefing', icon: FileText, label: '班前勤務卡', emoji: '📋', description: '勤務建議' },
    { id: 'import', icon: FileText, label: '資料匯入', emoji: '📥', description: '匯入 Excel 資料' },
  ];

  return (
    <aside className="w-72 bg-white/80 backdrop-blur-sm h-screen fixed left-0 top-0 nook-shadow z-50 overflow-y-auto">
      <div className="p-6 border-b border-nook-leaf/20">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-nook-leaf rounded-2xl flex items-center justify-center">
            <Shield className="w-7 h-7 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-nook-text text-lg">精準執法儀表板</h1>
            <p className="text-sm text-nook-text/60">事故與違規分析</p>
          </div>
        </div>
      </div>

      <nav className="p-4 space-y-2">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-2xl transition-all duration-200 ${isActive
                ? 'bg-nook-leaf text-white shadow-lg shadow-nook-leaf/30'
                : 'text-nook-text hover:bg-nook-leaf/10'
                }`}
              title={item.description}
            >
              <span className="text-xl">{item.emoji}</span>
              <span className="font-medium">{item.label}</span>
              {isActive && <ChevronRight className="w-4 h-4 ml-auto" />}
            </button>
          );
        })}
      </nav>

      <div className="absolute bottom-6 left-4 right-4">
        <SystemStatus />
      </div>
    </aside>
  );
};

// ============================================
// System Status Component
// ============================================
const SystemStatus: React.FC = () => {
  const { data: health, loading, error } = useHealthCheck();

  const getStatusColor = () => {
    if (loading) return 'bg-yellow-500';
    if (error) return 'bg-red-500';
    if (health?.status === 'ok') return 'bg-green-500';
    return 'bg-gray-500';
  };

  const getStatusText = () => {
    if (loading) return '檢查中...';
    if (error) return '⚠ 連線異常';
    if (health?.mode === 'simple') return '⚠ 模擬模式';
    if (health?.status === 'ok') return '✓ 正常運作';
    return '未知狀態';
  };

  return (
    <div className="bg-nook-sky/20 rounded-2xl p-4">
      <div className="flex items-center gap-3">
        <div className={`w-3 h-3 rounded-full ${getStatusColor()} animate-pulse`} />
        <div className="flex-1">
          <p className="text-sm font-medium text-nook-text">後端狀態</p>
          <p className="text-xs text-nook-text/60">{getStatusText()}</p>
        </div>
      </div>
      {health?.mode === 'simple' && (
        <div className="mt-2 text-xs text-nook-orange bg-nook-orange/10 rounded-lg p-2">
          ⚠️ 目前使用模擬數據。請安裝 PostgreSQL 以使用真實資料。
        </div>
      )}
    </div>
  );
};

// ============================================
// Header Component
// ============================================
const Header: React.FC = () => {
  const now = new Date();
  const dateStr = now.toLocaleDateString('zh-TW', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'short'
  });

  return (
    <header className="h-20 bg-white/60 backdrop-blur-sm border-b border-nook-leaf/10 flex items-center justify-between px-8">
      <div className="flex items-center gap-4">
        <div className="relative">
          <Search className="w-5 h-5 text-nook-text/40 absolute left-4 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="搜尋點位、地區或條款..."
            className="w-96 pl-12 pr-4 py-3 bg-nook-cream/50 border border-nook-leaf/20 rounded-2xl text-nook-text placeholder:text-nook-text/40 focus:outline-none focus:ring-2 focus:ring-nook-leaf/30"
          />
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 px-4 py-2 bg-nook-sky/10 rounded-2xl">
          <Calendar className="w-4 h-4 text-nook-sky" />
          <span className="text-sm text-nook-text font-medium">{dateStr}</span>
        </div>

        <button className="relative p-3 bg-nook-cream rounded-2xl hover:bg-nook-bell/20 transition-colors">
          <Bell className="w-5 h-5 text-nook-text" />
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-nook-red rounded-full text-white text-xs flex items-center justify-center">
            0
          </span>
        </button>

        <div className="flex items-center gap-3 pl-4 border-l border-nook-leaf/20">
          <div className="w-10 h-10 bg-nook-leaf rounded-full flex items-center justify-center text-xl">
            👮
          </div>
          <div>
            <p className="text-sm font-medium text-nook-text">執法人員</p>
            <p className="text-xs text-nook-text/60">新化分局</p>
          </div>
        </div>
      </div>
    </header>
  );
};

// ============================================
// Dashboard View (總覽)
// ============================================
const DashboardView: React.FC = () => {
  const { data: overview, loading, error } = useOverview(30);
  const now = new Date();
  const { data: monthly } = useMonthlyStats(now.getFullYear(), now.getMonth() + 1);

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 rounded-2xl p-6">
          <p className="text-red-800">⚠️ 無法載入數據：{error.message}</p>
          <p className="text-sm text-red-600 mt-2">請確認後端服務是否正常運行</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Welcome Banner */}
      <div className="bg-gradient-to-r from-nook-leaf to-nook-leaf-dark rounded-3xl p-8 mb-8 text-white nook-shadow">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold mb-2">🌿 精準執法儀表板系統</h2>
            <p className="text-white/80">事故分析 + 違規取締 + 精準執法建議（完全去識別化）</p>
          </div>
          <div className="flex items-center gap-2 bg-white/20 rounded-2xl px-4 py-2">
            <Shield className="w-5 h-5" />
            <span className="font-medium">無個資風險</span>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-4 gap-6 mb-8">
        <StatCard
          title="違規案件（30天）"
          value={overview?.tickets.total || 0}
          emoji="📋"
          color="bg-nook-orange"
          loading={loading}
        />
        <StatCard
          title="交通事故（30天）"
          value={overview?.crashes.total || 0}
          emoji="⚠️"
          color="bg-nook-red"
          loading={loading}
        />
        <StatCard
          title="高齡者違規"
          value={overview?.tickets.elderly || 0}
          emoji="👴"
          color="bg-nook-sky"
          loading={loading}
        />
        <StatCard
          title="酒駕案件"
          value={overview?.topics.dui || 0}
          emoji="🍺"
          color="bg-nook-leaf"
          loading={loading}
        />
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2">
          {monthly ? (
            <MonthlyComparison data={monthly} />
          ) : (
            <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-12 nook-shadow text-center">
              <BarChart3 className="w-16 h-16 mx-auto text-nook-text/20 mb-4" />
              <p className="text-nook-text/60">載入月度比較數據中...</p>
            </div>
          )}
        </div>
        <div>
          <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow">
            <h3 className="text-lg font-bold text-nook-text flex items-center gap-2 mb-4">
              🎯 三大執法主題
            </h3>
            <div className="space-y-3">
              <div className="bg-nook-red/10 rounded-2xl p-4 hover:bg-nook-red/20 transition-colors cursor-pointer">
                <div className="text-2xl mb-2">🍺</div>
                <div className="font-bold text-nook-text">酒駕精準打擊</div>
                <div className="text-sm text-nook-text/60 mt-1">最高優先級</div>
                <div className="text-2xl font-bold text-nook-red mt-2">
                  {overview?.topics.dui || 0} 件
                </div>
              </div>
              <div className="bg-nook-orange/10 rounded-2xl p-4 hover:bg-nook-orange/20 transition-colors cursor-pointer">
                <div className="text-2xl mb-2">🚦</div>
                <div className="font-bold text-nook-text">闖紅燈防制</div>
                <div className="text-sm text-nook-text/60 mt-1">號誌違規取締</div>
                <div className="text-2xl font-bold text-nook-orange mt-2">
                  {overview?.topics.red_light || 0} 件
                </div>
              </div>
              <div className="bg-nook-sky/10 rounded-2xl p-4 hover:bg-nook-sky/20 transition-colors cursor-pointer">
                <div className="text-2xl mb-2">⚡</div>
                <div className="font-bold text-nook-text">危險駕駛防制</div>
                <div className="text-sm text-nook-text/60 mt-1">超速與危險駕駛</div>
                <div className="text-2xl font-bold text-nook-sky mt-2">
                  {overview?.topics.dangerous_driving || 0} 件
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================
// Recommendations View (Top 5 推薦) - 含事故分析分頁
// ============================================
const RecommendationsView: React.FC = () => {
  const [selectedTopic, setSelectedTopic] = useState<TopicCode>('DUI');
  const [selectedShift, setSelectedShift] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'violation' | 'accident' | 'cross'>('violation');
  const [days, setDays] = useState<number>(30);
  const [crossDistrict, setCrossDistrict] = useState<string | null>(null);

  const { data: top5, loading: top5Loading } = useTop5(selectedTopic, selectedShift || undefined, days);
  const { data: heatmap, loading: heatmapLoading } = useHeatmap(selectedTopic, selectedShift || undefined, days);
  const { data: accidentHotspots, loading: accidentLoading } = useAccidentHotspots(days);
  const { data: crossAnalysis, loading: crossLoading } = useCrossAnalysis(crossDistrict || undefined, days);

  const topicColors = {
    DUI: 'bg-nook-red',
    RED_LIGHT: 'bg-nook-orange',
    DANGEROUS_DRIVING: 'bg-nook-sky'
  };

  const topicEmojis = {
    DUI: '🍺',
    RED_LIGHT: '🚦',
    DANGEROUS_DRIVING: '⚡'
  };

  const tabs = [
    { id: 'violation' as const, label: '🎯 違規熱點', description: '違規取締推薦' },
    { id: 'accident' as const, label: '🚧 事故熱點', description: '事故高發區域' },
    { id: 'cross' as const, label: '📊 時段交叉分析', description: '執法缺口分析' }
  ];

  const dayOptions = [
    { value: 30, label: '30天' },
    { value: 90, label: '90天' },
    { value: 180, label: '180天' },
    { value: 365, label: '1年' },
  ];

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-nook-text mb-2">🎯 精準執法分析</h2>
          <p className="text-nook-text/60">基於事故與違規數據的精準執法建議（無個資）</p>
        </div>
        {/* 日期範圍選擇器 */}
        <div className="flex items-center gap-2 bg-white/80 rounded-2xl px-3 py-2 nook-shadow">
          <span className="text-xs text-nook-text/60">📅</span>
          {dayOptions.map(opt => (
            <button
              key={opt.value}
              onClick={() => setDays(opt.value)}
              className={`px-2 py-1 rounded-lg text-xs font-medium transition-all ${days === opt.value
                ? 'bg-nook-leaf text-white'
                : 'text-nook-text/70 hover:bg-nook-leaf/10'
                }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* 分頁標籤 */}
      <div className="flex gap-2 mb-6">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-6 py-3 rounded-2xl font-medium transition-all ${activeTab === tab.id
              ? 'bg-nook-leaf text-white shadow-lg'
              : 'bg-white/60 text-nook-text hover:bg-nook-leaf/10'
              }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 違規熱點分頁 */}
      {activeTab === 'violation' && (
        <>
          <div className="grid grid-cols-2 gap-6 mb-6">
            <TopicSelector selectedTopic={selectedTopic} onTopicChange={setSelectedTopic} />
            <ShiftSelector selectedShift={selectedShift} onShiftChange={setSelectedShift} />
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-4">
              <div className="bg-nook-sky/10 rounded-2xl p-4">
                <h4 className="font-bold text-sm text-nook-text mb-2">📊 指標說明</h4>
                <div className="text-xs text-nook-text/70 grid grid-cols-3 gap-2">
                  <p><strong>VPI</strong>：違規壓力指數</p>
                  <p><strong>CRI</strong>：事故風險指數</p>
                  <p><strong>Score</strong>：綜合評分</p>
                </div>
              </div>
              <Top5List
                recommendations={top5?.recommendations || []}
                topicEmoji={topicEmojis[selectedTopic]}
                topicColor={topicColors[selectedTopic]}
                loading={top5Loading}
              />
            </div>
            <div>
              <HotspotMap
                heatmapPoints={heatmap?.points || []}
                top5Sites={top5?.recommendations || []}
                topicCode={selectedTopic}
                loading={heatmapLoading}
              />
            </div>
          </div>
        </>
      )}

      {/* 事故熱點分頁 */}
      {activeTab === 'accident' && (
        <div className="grid grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="bg-nook-orange/10 rounded-2xl p-4">
              <h4 className="font-bold text-sm text-nook-text mb-2">🚧 事故熱點分析 <span className="font-normal text-xs bg-nook-orange/30 px-2 py-0.5 rounded-full">近 30 天</span></h4>
              <p className="text-xs text-nook-text/70">
                依事故嚴重度權重排序（A1:5分, A2:3分, A3:1分），建議在事故高發區加強相關違規取締
              </p>
            </div>

            {accidentLoading ? (
              <div className="bg-white/80 rounded-2xl p-8 text-center">
                <p className="text-nook-text/60">載入中...</p>
              </div>
            ) : (
              <div className="space-y-3">
                {accidentHotspots?.hotspots.map((hotspot, idx) => (
                  <div key={hotspot.district} className="bg-white/80 rounded-2xl p-4 nook-shadow">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="w-8 h-8 bg-nook-orange/20 rounded-full flex items-center justify-center font-bold text-nook-orange">
                        {idx + 1}
                      </span>
                      <h5 className="font-bold text-nook-text">{hotspot.district}</h5>
                    </div>
                    <div className="grid grid-cols-4 gap-2 text-xs mb-3">
                      <div className="bg-gray-100 rounded-lg p-2 text-center">
                        <p className="text-nook-text font-bold text-lg">{hotspot.accidents.total}</p>
                        <p className="text-nook-text/60">總數</p>
                      </div>
                      <div className="bg-red-100 rounded-lg p-2 text-center border-2 border-red-400">
                        <p className="text-red-700 font-bold text-lg">{hotspot.accidents.a1_count}</p>
                        <p className="text-red-600 font-semibold">A1 死亡</p>
                      </div>
                      <div className="bg-orange-50 rounded-lg p-2 text-center">
                        <p className="text-orange-600 font-bold text-lg">{hotspot.accidents.a2_count}</p>
                        <p className="text-orange-500">A2 受傷</p>
                      </div>
                      <div className="bg-blue-50 rounded-lg p-2 text-center">
                        <p className="text-blue-600 font-bold text-lg">{hotspot.violations.total}</p>
                        <p className="text-blue-500">違規數</p>
                      </div>
                    </div>
                    <div className="bg-nook-leaf/10 rounded-lg p-2 text-xs text-nook-leaf-dark">
                      💡 {hotspot.recommendation.enforcement_focus}
                    </div>
                  </div>
                ))}
                {accidentHotspots?.hotspots.length === 0 && (
                  <div className="bg-white/80 rounded-2xl p-8 text-center">
                    <p className="text-nook-text/60">目前沒有事故熱點數據</p>
                  </div>
                )}
              </div>
            )}

            {/* 事故嚴重度摘要 */}
            {accidentHotspots && (
              <div className="bg-white/80 rounded-2xl p-4 nook-shadow">
                <h5 className="font-bold text-sm text-nook-text mb-3">📈 事故嚴重度分布</h5>
                <div className="grid grid-cols-4 gap-2 text-center text-xs">
                  <div className="bg-gray-50 rounded-lg p-2">
                    <p className="font-bold text-lg text-nook-text">{accidentHotspots.summary.total_accidents}</p>
                    <p className="text-nook-text/60">總計</p>
                  </div>
                  <div className="bg-red-50 rounded-lg p-2">
                    <p className="font-bold text-lg text-red-600">{accidentHotspots.summary.a1_total}</p>
                    <p className="text-red-500">A1 死亡</p>
                  </div>
                  <div className="bg-orange-50 rounded-lg p-2">
                    <p className="font-bold text-lg text-orange-600">{accidentHotspots.summary.a2_total}</p>
                    <p className="text-orange-500">A2 受傷</p>
                  </div>
                  <div className="bg-yellow-50 rounded-lg p-2">
                    <p className="font-bold text-lg text-yellow-600">{accidentHotspots.summary.a3_total}</p>
                    <p className="text-yellow-500">A3 財損</p>
                  </div>
                </div>
              </div>
            )}
          </div>
          <div>
            <div className="bg-white/80 rounded-2xl p-6 nook-shadow h-full">
              <h4 className="font-bold text-nook-text mb-4">🗺️ 事故熱點地圖</h4>
              <div className="bg-nook-cream/30 rounded-xl h-80 flex items-center justify-center">
                <p className="text-nook-text/40 text-sm">事故地圖顯示事故高發區域</p>
              </div>
              <p className="text-xs text-nook-text/50 mt-2 text-center">
                共 {accidentHotspots?.total_districts || 0} 個區域有事故記錄
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 時段交叉分析分頁 */}
      {activeTab === 'cross' && (
        <div className="space-y-6">
          {/* 區域篩選器 */}
          <div className="bg-nook-sky/10 rounded-2xl p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h4 className="font-bold text-sm text-nook-text">📊 時段交叉分析</h4>
                <p className="text-xs text-nook-text/70">
                  分析「事故多但違規取締少」的區域與時段，精準識別需加強執法的時間與地點
                </p>
              </div>
            </div>
            {/* 區域選擇器 */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-nook-text/60">🎯 篩選區域：</span>
              <button
                onClick={() => setCrossDistrict(null)}
                className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${crossDistrict === null
                  ? 'bg-nook-leaf text-white'
                  : 'bg-white/60 text-nook-text hover:bg-nook-leaf/10'
                  }`}
              >
                全部區域
              </button>
              {accidentHotspots?.hotspots.map(h => (
                <button
                  key={h.district}
                  onClick={() => setCrossDistrict(h.district)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${crossDistrict === h.district
                    ? 'bg-nook-orange text-white'
                    : 'bg-white/60 text-nook-text hover:bg-nook-orange/10'
                    }`}
                >
                  {h.district}
                </button>
              ))}
            </div>
          </div>

          {crossLoading ? (
            <div className="bg-white/80 rounded-2xl p-8 text-center">
              <p className="text-nook-text/60">載入中...</p>
            </div>
          ) : (
            <>
              {/* 優先級統計 */}
              <div className="grid grid-cols-4 gap-4">
                <div className="bg-white/80 rounded-2xl p-4 nook-shadow text-center">
                  <p className="text-2xl font-bold text-nook-text">{crossAnalysis?.summary.total_combinations || 0}</p>
                  <p className="text-xs text-nook-text/60">分析組合數</p>
                </div>
                <div className="bg-red-50 rounded-2xl p-4 text-center border-2 border-red-200">
                  <p className="text-2xl font-bold text-red-600">{crossAnalysis?.summary.high_priority_count || 0}</p>
                  <p className="text-xs text-red-500">高優先 🔴</p>
                </div>
                <div className="bg-orange-50 rounded-2xl p-4 text-center">
                  <p className="text-2xl font-bold text-orange-600">{crossAnalysis?.summary.medium_priority_count || 0}</p>
                  <p className="text-xs text-orange-500">中優先 🟡</p>
                </div>
                <div className="bg-green-50 rounded-2xl p-4 text-center">
                  <p className="text-2xl font-bold text-green-600">{crossAnalysis?.summary.low_priority_count || 0}</p>
                  <p className="text-xs text-green-500">低優先 🟢</p>
                </div>
              </div>

              {/* 高優先建議 */}
              {crossAnalysis?.recommendations.high_priority_targets && crossAnalysis.recommendations.high_priority_targets.length > 0 && (
                <div className="bg-red-50 border-2 border-red-200 rounded-2xl p-4">
                  <h5 className="font-bold text-red-700 mb-3">🚨 建議優先加強執法</h5>
                  <div className="grid grid-cols-2 gap-3">
                    {crossAnalysis.recommendations.high_priority_targets.slice(0, 4).map((item, idx) => (
                      <div key={idx} className="bg-white rounded-xl p-3">
                        <div className="flex justify-between items-center mb-2">
                          <span className="font-bold text-nook-text">{item.district}</span>
                          <span className="text-xs bg-red-100 text-red-600 px-2 py-1 rounded-full">
                            {item.time_range}
                          </span>
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-xs">
                          <div>
                            <p className="text-red-600 font-bold">{item.accidents}</p>
                            <p className="text-nook-text/50">事故</p>
                          </div>
                          <div>
                            <p className="text-blue-600 font-bold">{item.violations}</p>
                            <p className="text-nook-text/50">違規</p>
                          </div>
                          <div>
                            <p className="text-orange-600 font-bold">{item.enforcement_gap}</p>
                            <p className="text-nook-text/50">缺口</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 前幾大事故地點輔助資訊 */}
              {accidentHotspots && accidentHotspots.hotspots.length > 0 && (
                <div className="bg-orange-50 border-2 border-orange-200 rounded-2xl p-4">
                  <h5 className="font-bold text-orange-700 mb-3">🚧 前幾大事故地點（輔助參考）</h5>
                  <p className="text-xs text-orange-600/70 mb-3">
                    依事故嚴重度權重排序，紅色數字為 A1 死亡事故
                  </p>
                  <div className="grid grid-cols-3 gap-3">
                    {accidentHotspots.hotspots.slice(0, 3).map((hotspot, idx) => (
                      <div key={hotspot.district} className="bg-white rounded-xl p-3">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${idx === 0 ? 'bg-red-500 text-white' :
                            idx === 1 ? 'bg-orange-400 text-white' :
                              'bg-yellow-400 text-white'
                            }`}>
                            {idx + 1}
                          </span>
                          <span className="font-bold text-nook-text text-sm">{hotspot.district}</span>
                        </div>
                        <div className="grid grid-cols-3 gap-1 text-xs">
                          <div className="text-center">
                            <p className="font-bold text-gray-700">{hotspot.accidents.total}</p>
                            <p className="text-nook-text/50">總數</p>
                          </div>
                          <div className="text-center">
                            <p className={`font-bold ${hotspot.accidents.a1_count > 0 ? 'text-red-600' : 'text-gray-400'}`}>
                              {hotspot.accidents.a1_count}
                            </p>
                            <p className="text-red-500/70">A1</p>
                          </div>
                          <div className="text-center">
                            <p className="font-bold text-orange-500">{hotspot.accidents.a2_count}</p>
                            <p className="text-orange-400/70">A2</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-orange-500/60 mt-2 text-center">
                    共 {accidentHotspots.summary.total_accidents} 件事故 | A1:{accidentHotspots.summary.a1_total} A2:{accidentHotspots.summary.a2_total}
                  </p>
                </div>
              )}

              {/* 完整分析列表 */}
              <div className="bg-white/80 rounded-2xl p-4 nook-shadow">
                <h5 className="font-bold text-nook-text mb-3">📋 完整分析列表</h5>
                <div className="max-h-80 overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-white">
                      <tr className="text-left text-nook-text/60 border-b">
                        <th className="py-2 px-2">區域</th>
                        <th className="py-2 px-2">時段</th>
                        <th className="py-2 px-2 text-center">事故</th>
                        <th className="py-2 px-2 text-center">違規</th>
                        <th className="py-2 px-2 text-center">執法缺口</th>
                        <th className="py-2 px-2 text-center">優先級</th>
                      </tr>
                    </thead>
                    <tbody>
                      {crossAnalysis?.cross_analysis.map((item, idx) => (
                        <tr key={idx} className="border-b border-nook-leaf/10 hover:bg-nook-leaf/5">
                          <td className="py-2 px-2 font-medium">{item.district}</td>
                          <td className="py-2 px-2 text-nook-text/70">{item.time_range}</td>
                          <td className="py-2 px-2 text-center">{item.accidents}</td>
                          <td className="py-2 px-2 text-center">{item.violations}</td>
                          <td className="py-2 px-2 text-center font-bold">{item.enforcement_gap}</td>
                          <td className="py-2 px-2 text-center">
                            <span className={`px-2 py-1 rounded-full text-xs ${item.priority === 'HIGH' ? 'bg-red-100 text-red-600' :
                              item.priority === 'MEDIUM' ? 'bg-orange-100 text-orange-600' :
                                'bg-green-100 text-green-600'
                              }`}>
                              {item.priority === 'HIGH' ? '高' : item.priority === 'MEDIUM' ? '中' : '低'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

// ============================================
// Briefing View (班前勤務卡)
// ============================================
const BriefingView: React.FC = () => {
  const [selectedTopic, setSelectedTopic] = useState<TopicCode>('DUI');
  const [selectedShift, setSelectedShift] = useState<string>('11');

  const { data: briefing, loading } = useBriefingCard(
    selectedTopic,
    selectedShift,
    undefined
  );

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-nook-text mb-2">📋 班前勤務建議卡</h2>
        <p className="text-nook-text/60">為您準備的執法勤務建議（無個資）</p>
      </div>

      <div className="grid grid-cols-4 gap-6">
        <div className="space-y-6">
          <TopicSelector
            selectedTopic={selectedTopic}
            onTopicChange={setSelectedTopic}
          />
          <ShiftSelector
            selectedShift={selectedShift}
            onShiftChange={(shift) => shift && setSelectedShift(shift)}
          />
        </div>

        <div className="col-span-3">
          {briefing ? (
            <BriefingCard data={briefing} loading={loading} />
          ) : (
            <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-12 nook-shadow text-center">
              <div className="text-6xl mb-4">📋</div>
              <p className="text-nook-text/60">載入勤務建議卡中...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// ============================================
// Placeholder Views (其他視圖)
// ============================================
const PlaceholderView: React.FC<{ title: string; emoji: string; description: string }> = ({ title, emoji, description }) => {
  return (
    <div className="p-8">
      <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-12 nook-shadow text-center">
        <div className="text-6xl mb-4">{emoji}</div>
        <h2 className="text-2xl font-bold text-nook-text mb-2">{title}</h2>
        <p className="text-nook-text/60">{description}</p>
        <p className="text-sm text-nook-text/40 mt-4">此功能即將推出</p>
      </div>
    </div>
  );
};

// ============================================
// Main App
// ============================================
const App: React.FC = () => {
  const [activeView, setActiveView] = useState('dashboard');

  const renderView = () => {
    switch (activeView) {
      case 'dashboard':
        return <DashboardView />;
      case 'accidents':
        return <AccidentAnalysisPage />;
      case 'elderly':
        return <ElderlyPreventionPage />;
      case 'monthly':
        return <PerformanceComparisonPage />;
      case 'briefing':
        return <BriefingView />;
      case 'import':
        return <DataImportPage />;
      default:
        return <DashboardView />;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-nook-cream via-white to-nook-sky/10">
      <Sidebar activeView={activeView} onViewChange={setActiveView} />
      <main className="ml-72 min-h-screen">
        <Header />
        {renderView()}
      </main>
    </div>
  );
};

export default App;
