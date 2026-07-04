/**
 * Main App Component - 精準執法儀表板
 * 專注於事故分析和違規取締
 */

import React, { useState, useEffect, useMemo } from 'react';
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
  Shield,
  Zap,
  Eye,
  Lock,
  LogOut,
  Wine,
  Truck,
  Target,
  Bot,
  PersonStanding,
  Construction,
  Gauge,
  Pill,
  ClipboardList
} from 'lucide-react';

// Import custom components
import { StatCard } from './components/StatCard';
import { TopicSelector } from './components/TopicSelector';
import { ShiftSelector } from './components/ShiftSelector';
import { Top5List } from './components/Top5Card';
import { MonthlyComparison } from './components/MonthlyComparison';
import DataImportPage from './components/DataImportPage';
import ViolationsPage from './components/ViolationsPage';
import { HotspotMap } from './components/HotspotMap';
import AccidentAnalysisPage from './components/AccidentAnalysisPage';
import ElderlyPreventionPage from './components/ElderlyPreventionPage';
import PerformanceComparisonPage from './components/PerformanceComparisonPage';
import MapViewPage from './components/MapViewPage';
import AIReportPage from './components/AIReportPage';
import EVehicleAnalysisPage from './components/EVehicleAnalysisPage';
import DuiPerformancePage from './components/DuiPerformancePage';
import DrugDrivePage from './components/DrugDrivePage';
import HeavyVehiclePerformancePage from './components/HeavyVehiclePerformancePage';
import SpeedPerformancePage from './components/SpeedPerformancePage';
import PedestrianAnalysisPage from './components/PedestrianAnalysisPage';
import RoadEngineeringPage from './components/RoadEngineeringPage';
import PatrolPlanPage from './components/PatrolPlanPage';
import DateRangePicker, { type DateRange } from './components/DateRangePicker';
import BrandLogo from './components/BrandLogo';
import TrendCardSkeleton from './components/TrendCardSkeleton';

// recharts 依賴較重，動態載入讓它獨立成 chunk，不灌進主 bundle
const TrendCard = React.lazy(() => import('./components/TrendCard'));

// Import hooks
import {
  useOverview,
  useTop5,
  useMonthlyStats,
  useHealthCheck,
  useHeatmap,
  useAccidentHotspots,
  useCrossAnalysis
} from './hooks/useAPI';

import { TopicCode, apiClient } from './api/client';

// ============================================
// Sidebar Component
// ============================================
// ============================================
// Read-only mode detection (唯讀模式偵測)
// URL hash #view = read-only for field units
// ============================================
function useReadOnlyMode(): boolean {
  const [isReadOnly, setIsReadOnly] = useState(() => window.location.hash === '#view');

  useEffect(() => {
    const handleHashChange = () => setIsReadOnly(window.location.hash === '#view');
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  return isReadOnly;
}

// Items hidden in read-only mode (唯讀模式隱藏的頁面)
const ADMIN_ONLY_VIEWS = new Set(['ai-report', 'import']);

interface SidebarProps {
  activeView: string;
  onViewChange: (view: string) => void;
  readOnly: boolean;
  onLogout?: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ activeView, onViewChange, readOnly, onLogout }) => {
  // 菜單分組：資料分析 / 防制專區 / 工具
  const menuGroups: { section?: string; items: Array<{ id: string; icon: any; label: string; description: string }> }[] = [
    {
      section: undefined,  // 首組不顯示 section label
      items: [
        { id: 'dashboard', icon: Home, label: '總覽', description: '整體統計概覽' },
      ],
    },
    {
      section: '分析',
      items: [
        { id: 'accidents', icon: Target, label: '執法缺口', description: '事故與違規綜合分析' },
        { id: 'map', icon: MapPin, label: '地圖視覺化', description: '精準座標點位分布' },
        { id: 'monthly', icon: BarChart3, label: '綜合執法成效', description: '數據總覽·趨勢·A1清單' },
        { id: 'road-eng', icon: Construction, label: '道路工程改善', description: '照明故障通報·會勘佐證資料' },
        { id: 'patrol-plan', icon: ClipboardList, label: '勤務建議', description: 'DDACTS 高風險班別與熱點建議' },
      ],
    },
    {
      section: '專區',
      items: [
        { id: 'elderly', icon: Users, label: '高齡者專區', description: '高齡者事故防治' },
        { id: 'pedestrian', icon: PersonStanding, label: '行人事故', description: '行人事故發生率與熱點' },
        { id: 'evehicle', icon: Zap, label: '青少年微電車', description: '青少年微電車/電輔車事故分析' },
        { id: 'dui', icon: Wine, label: '酒駕成效', description: '各派出所酒駕取締與事故統計' },
        { id: 'drug', icon: Pill, label: '毒駕分析', description: '毒品駕駛取締、時段與區域分析' },
        { id: 'speed', icon: Gauge, label: '速度管理', description: '超速取締與嚴重度分級' },
        { id: 'heavy-vehicle', icon: Truck, label: '大型車成效', description: '各派出所大型車取締與事故統計' },
      ],
    },
    {
      section: '工具',
      items: [
        { id: 'ai-report', icon: Bot, label: 'AI 智慧報告', description: 'AI 自動生成分析報告' },
        { id: 'import', icon: FileText, label: '資料匯入', description: '匯入 Excel 資料' },
      ],
    },
  ];

  // 過濾唯讀模式隱藏的項目
  const visibleGroups = menuGroups
    .map(g => ({ ...g, items: readOnly ? g.items.filter(i => !ADMIN_ONLY_VIEWS.has(i.id)) : g.items }))
    .filter(g => g.items.length > 0);

  return (
    <aside className="w-64 bg-white h-screen fixed left-0 top-0 border-r border-slate-200 z-50 flex flex-col">
      {/* Brand Lockup */}
      <div className="p-5 border-b border-slate-100 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center shrink-0 p-1.5">
            <BrandLogo size={28} variant="light" />
          </div>
          <div className="min-w-0">
            <h1 className="font-semibold text-slate-800 text-[15px] leading-tight tracking-tight">精準執法儀表板</h1>
            <p className="text-[11px] text-slate-500 mt-0.5">新化分局</p>
            {readOnly && (
              <span className="inline-flex items-center gap-1 mt-1.5 px-1.5 py-0.5 bg-sky-50 text-sky-700 text-[10px] font-medium rounded">
                <Eye className="w-2.5 h-2.5" />
                唯讀
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Navigation — grouped */}
      <nav className="px-3 py-4 flex-1 overflow-y-auto min-h-0">
        {visibleGroups.map((group, gIdx) => (
          <div key={gIdx} className={gIdx > 0 ? 'mt-5' : ''}>
            {group.section && (
              <div className="px-3 mb-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                {group.section}
              </div>
            )}
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                const isActive = activeView === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => onViewChange(item.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                      isActive
                        ? 'bg-primary text-white'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    }`}
                    title={item.description}
                  >
                    <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-white' : 'text-slate-400'}`} strokeWidth={2} />
                    <span className="font-medium truncate">{item.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer — data info + system status + logout */}
      <div className="shrink-0 border-t border-slate-100">
        <DataInfo />
        <SystemStatus />
        {onLogout && (
          <button
            onClick={onLogout}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-xs text-slate-500 hover:text-danger hover:bg-red-50 transition-colors border-t border-slate-100"
          >
            <LogOut className="w-3.5 h-3.5" />
            登出
          </button>
        )}
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
    if (loading) return 'bg-amber-400';
    if (error) return 'bg-danger';
    if (health?.status === 'ok') return 'bg-success';
    return 'bg-slate-400';
  };

  const getStatusText = () => {
    if (loading) return '檢查中';
    if (error) return '連線異常';
    if (health?.mode === 'simple') return '模擬模式';
    if (health?.status === 'ok') return '正常';
    return '未知';
  };

  // 正常狀態一行就好；異常才展開
  const isAbnormal = error || health?.mode === 'simple';

  return (
    <div className="px-4 py-2 border-t border-slate-100">
      <div className="flex items-center gap-2">
        <div className={`w-1.5 h-1.5 rounded-full ${getStatusColor()}`} />
        <span className="text-[11px] text-slate-500">後端 {getStatusText()}</span>
      </div>
      {isAbnormal && health?.mode === 'simple' && (
        <div className="mt-1.5 text-[10px] text-warning bg-amber-50 rounded px-2 py-1">
          使用模擬數據
        </div>
      )}
    </div>
  );
};

// ============================================
// Data Info Component (資料庫涵蓋範圍)
// ============================================
const DataInfo: React.FC = () => {
  const [info, setInfo] = useState<{
    crash: { earliest: string | null; latest: string | null; count: number; last_upload: string | null };
    ticket: { earliest: string | null; latest: string | null; count: number; last_upload: string | null };
    last_upload: string | null;
  } | null>(null);

  useEffect(() => {
    apiClient.getDataInfo().then(setInfo).catch(() => {});
  }, []);

  if (!info) return null;

  const formatDate = (d: string | null) => d ? d.replace(/-/g, '/') : '--';
  const formatUpload = (d: string | null) => {
    if (!d) return '--';
    const dt = new Date(d);
    return `${dt.getMonth() + 1}/${dt.getDate()} ${dt.getHours().toString().padStart(2, '0')}:${dt.getMinutes().toString().padStart(2, '0')}`;
  };

  return (
    <div className="px-4 py-3 text-[11px] text-slate-500 space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-slate-400 uppercase tracking-wider text-[9px] font-semibold">資料範圍</span>
        {info.last_upload && (
          <span className="text-[10px] text-slate-400 tabular-nums">
            更新 {formatUpload(info.last_upload)}
          </span>
        )}
      </div>
      <div className="flex items-baseline justify-between">
        <span className="text-slate-600">事故</span>
        <span className="tabular-nums text-slate-500">
          {formatDate(info.crash.latest)} · {info.crash.count.toLocaleString()} 筆
        </span>
      </div>
      <div className="flex items-baseline justify-between">
        <span className="text-slate-600">違規</span>
        <span className="tabular-nums text-slate-500">
          {formatDate(info.ticket.latest)} · {info.ticket.count.toLocaleString()} 筆
        </span>
      </div>
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
    <header className="h-14 bg-white/80 backdrop-blur-sm border-b border-slate-200 flex items-center justify-end gap-3 px-6">
      {/* 今天日期 — 低調呈現 */}
      <div className="flex items-center gap-1.5 text-xs text-slate-500">
        <Calendar className="w-3.5 h-3.5" />
        <span className="tabular-nums">{dateStr}</span>
      </div>

      {/* 分隔線 */}
      <div className="w-px h-5 bg-slate-200" />

      {/* 通知鈴 — 僅在有未讀時顯示紅點 */}
      <button
        className="relative w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 transition-colors"
        aria-label="通知"
        title="通知"
      >
        <Bell className="w-4 h-4 text-slate-500" strokeWidth={2} />
        {/* 未讀通知才顯示 — 目前為 0 隱藏 */}
        {/* <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-danger rounded-full" /> */}
      </button>

      {/* 使用者 chip — 只顯示真實資訊 */}
      <div className="flex items-center gap-2 pl-2 border-l border-slate-200">
        <div className="w-7 h-7 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-semibold">
          新
        </div>
        <span className="text-sm text-slate-700 font-medium">新化分局</span>
      </div>
    </header>
  );
};

// ============================================
// Dashboard View (總覽)
// ============================================
const DashboardView: React.FC = () => {
  // 預設近 30 天，可由 DateRangePicker 覆寫
  const today = new Date();
  const thirtyDaysAgo = new Date(today);
  thirtyDaysAgo.setDate(today.getDate() - 30);
  const fmt = (d: Date) => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${dd}`;
  };
  const [dateRange, setDateRange] = useState<DateRange>({
    startDate: fmt(thirtyDaysAgo),
    endDate: fmt(today),
  });

  const { data: overview, loading, error } = useOverview(30, dateRange.startDate, dateRange.endDate);
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
      {/* Welcome Banner — 在地紋理：等高線 + Taiwan 水印 */}
      <div className="relative overflow-hidden bg-gradient-to-br from-primary via-primary-light to-accent-hover rounded-2xl p-8 mb-6 text-white shadow-md">
        {/* 等高線紋理（極淡）*/}
        <svg className="absolute inset-0 w-full h-full opacity-[0.08] pointer-events-none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <defs>
            <pattern id="welcomeTopo" x="0" y="0" width="80" height="80" patternUnits="userSpaceOnUse">
              <circle cx="40" cy="40" r="10" fill="none" stroke="white" strokeWidth="0.5" />
              <circle cx="40" cy="40" r="20" fill="none" stroke="white" strokeWidth="0.5" />
              <circle cx="40" cy="40" r="30" fill="none" stroke="white" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#welcomeTopo)" />
        </svg>
        {/* Taiwan 水印（右側淡出）*/}
        <svg className="absolute -right-12 -bottom-20 opacity-[0.08] pointer-events-none" width="320" height="320" viewBox="0 0 200 300" aria-hidden="true">
          <path d="M 110 20 Q 125 30 130 55 Q 135 85 130 120 Q 125 155 120 180 Q 115 210 100 240 Q 85 265 70 270 Q 55 265 50 245 Q 45 215 50 180 Q 55 140 65 100 Q 75 60 90 35 Q 100 22 110 20 Z" fill="white"/>
        </svg>

        <div className="relative flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-white/10 backdrop-blur-sm rounded-xl flex items-center justify-center p-2 border border-white/20">
              <BrandLogo size={32} variant="light" />
            </div>
            <div>
              <h2 className="text-xl font-bold tracking-tight">精準執法儀表板系統</h2>
              <p className="text-sm text-white/70 mt-0.5">事故分析 · 違規取締 · 精準執法建議（完全去識別化）</p>
            </div>
          </div>
          <div className="flex items-center gap-2 bg-white/10 backdrop-blur-sm rounded-lg px-3 py-1.5 border border-white/20 text-xs">
            <Shield className="w-3.5 h-3.5" />
            <span className="font-medium">無個資風險</span>
          </div>
        </div>
      </div>

      {/* 日期範圍選擇器 */}
      <div className="mb-6 bg-white rounded-2xl p-4 nook-shadow">
        <DateRangePicker value={dateRange} onChange={setDateRange} showCompare={false} />
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-5 gap-6 mb-8">
        <StatCard
          title="違規案件"
          value={overview?.tickets.total || 0}
          emoji="📋"
          color="bg-nook-orange"
          loading={loading}
        />
        <StatCard
          title="交通事故"
          value={overview?.crashes.total || 0}
          emoji="⚠️"
          color="bg-nook-red"
          loading={loading}
        />
        <StatCard
          title="事故當量 EPDO"
          value={overview?.crashes.epdo || 0}
          emoji="⚖️"
          color="bg-nook-bell"
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

      {/* 週事故趨勢與專業判讀（趨勢引擎 + Recharts）*/}
      <React.Suspense fallback={<TrendCardSkeleton title="週事故趨勢與專業判讀" />}>
        <TrendCard
          range={dateRange}
          title="週事故趨勢與專業判讀"
          fetcher={(s, e) => apiClient.getAccidentTrend(s, e)}
          primaryName="A2/A3 事故"
          secondaryName="A1 死亡事故"
          primaryColor="#D97706"
          secondaryColor="#DC2626"
        />
      </React.Suspense>

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
// Login Page (管理登入頁面)
// ============================================
const AUTH_KEY = 'dashboard_auth';

function useAuth() {
  // sessionStorage 存後端簽發的 token（非 'true' 旗標）；client.ts 發請求時自動帶上
  const [authenticated, setAuthenticated] = useState(
    () => {
      const v = sessionStorage.getItem(AUTH_KEY);
      return !!v && v !== 'true'; // 舊版旗標視為未登入，強制重新驗證
    }
  );

  const login = async (username: string, password: string): Promise<boolean> => {
    try {
      const res = await apiClient.login(username, password);
      if (res?.token) {
        sessionStorage.setItem(AUTH_KEY, res.token);
        setAuthenticated(true);
        return true;
      }
    } catch {
      // 401 帳密錯誤或後端未啟動
    }
    return false;
  };

  const logout = () => {
    sessionStorage.removeItem(AUTH_KEY);
    setAuthenticated(false);
  };

  return { authenticated, login, logout };
}

const LoginPage: React.FC<{ onLogin: (u: string, p: string) => Promise<boolean> }> = ({ onLogin }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(false);
  const [shake, setShake] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await onLogin(username, password);
    if (!ok) {
      setError(true);
      setShake(true);
      setTimeout(() => setShake(false), 500);
    }
  };

  return (
    <div className="min-h-screen relative flex items-center justify-center overflow-hidden bg-slate-50">
      {/* 意境背景：台灣地形漸層 + 微細網格（新化在地 × 專業資料感）*/}
      <div className="absolute inset-0 z-0">
        {/* 底色漸層 */}
        <div className="absolute inset-0 bg-gradient-to-br from-slate-100 via-sky-50 to-slate-100" />
        {/* 地形等高線 SVG 紋理 */}
        <svg className="absolute inset-0 w-full h-full opacity-[0.12]" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <defs>
            <pattern id="topo" x="0" y="0" width="120" height="120" patternUnits="userSpaceOnUse">
              {/* 同心圓漸層仿造等高線 */}
              <circle cx="60" cy="60" r="12" fill="none" stroke="#0369A1" strokeWidth="0.6" />
              <circle cx="60" cy="60" r="24" fill="none" stroke="#0369A1" strokeWidth="0.6" />
              <circle cx="60" cy="60" r="36" fill="none" stroke="#0369A1" strokeWidth="0.6" />
              <circle cx="60" cy="60" r="48" fill="none" stroke="#0369A1" strokeWidth="0.6" />
            </pattern>
            <radialGradient id="fade" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="white" stopOpacity="0" />
              <stop offset="100%" stopColor="white" stopOpacity="1" />
            </radialGradient>
          </defs>
          <rect width="100%" height="100%" fill="url(#topo)" />
          <rect width="100%" height="100%" fill="url(#fade)" />
        </svg>
        {/* 大型 watermark Taiwan 輪廓（右下角淡水印） */}
        <svg className="absolute bottom-0 right-0 opacity-[0.04] translate-x-1/4 translate-y-1/4" width="500" height="500" viewBox="0 0 200 300" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <path
            d="M 110 20
               Q 125 30 130 55
               Q 135 85 130 120
               Q 125 155 120 180
               Q 115 210 100 240
               Q 85 265 70 270
               Q 55 265 50 245
               Q 45 215 50 180
               Q 55 140 65 100
               Q 75 60 90 35
               Q 100 22 110 20 Z"
            fill="#0F172A"
          />
        </svg>
      </div>

      {/* 登入卡 */}
      <div className={`relative z-10 bg-white rounded-2xl p-10 shadow-xl w-full max-w-md border border-slate-200 ${shake ? 'animate-shake' : ''}`}>
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-primary rounded-2xl flex items-center justify-center mx-auto mb-4 p-2.5">
            <BrandLogo size={44} variant="light" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">精準執法儀表板</h1>
          <p className="text-sm text-slate-500 mt-1">新化分局 · 管理員登入</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-nook-text mb-1.5">帳號</label>
            <div className="relative">
              <Users className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-nook-text/40" />
              <input
                type="text"
                value={username}
                onChange={e => { setUsername(e.target.value); setError(false); }}
                className="w-full pl-10 pr-4 py-2.5 border border-nook-leaf/30 rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-nook-leaf/50 text-nook-text"
                placeholder="請輸入帳號"
                autoFocus
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-nook-text mb-1.5">密碼</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-nook-text/40" />
              <input
                type="password"
                value={password}
                onChange={e => { setPassword(e.target.value); setError(false); }}
                className="w-full pl-10 pr-4 py-2.5 border border-nook-leaf/30 rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-nook-leaf/50 text-nook-text"
                placeholder="請輸入密碼"
              />
            </div>
          </div>

          {error && (
            <p className="text-red-500 text-sm text-center">帳號或密碼錯誤，請重新輸入</p>
          )}

          <button
            type="submit"
            className="w-full py-2.5 bg-nook-leaf text-white font-medium rounded-xl hover:bg-nook-leaf/90 transition-colors shadow-lg shadow-nook-leaf/30"
          >
            登入
          </button>
        </form>

        <p className="text-xs text-nook-text/40 text-center mt-6">新化分局精準執法儀表板系統</p>
      </div>

      <style>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          20%, 60% { transform: translateX(-8px); }
          40%, 80% { transform: translateX(8px); }
        }
        .animate-shake { animation: shake 0.4s ease-in-out; }
      `}</style>
    </div>
  );
};

// ============================================
// Main App
// ============================================
const App: React.FC = () => {
  const [activeView, setActiveView] = useState('dashboard');
  const readOnly = useReadOnlyMode();
  const { authenticated, login, logout } = useAuth();

  // Read-only mode: no login needed; admin mode: require login
  // 唯讀模式免登入，管理模式需登入
  if (!readOnly && !authenticated) {
    return <LoginPage onLogin={login} />;
  }

  // In read-only mode, redirect admin-only views back to dashboard
  // 唯讀模式下，管理頁面自動導回總覽
  const safeSetView = (view: string) => {
    if (readOnly && ADMIN_ONLY_VIEWS.has(view)) return;
    setActiveView(view);
  };

  const renderView = () => {
    switch (activeView) {
      case 'dashboard':
        return <DashboardView />;
      case 'accidents':
        return <AccidentAnalysisPage />;
      case 'map':
        return <MapViewPage readOnly={readOnly} />;
      case 'elderly':
        return <ElderlyPreventionPage />;
      case 'evehicle':
        return <EVehicleAnalysisPage />;
      case 'dui':
        return <DuiPerformancePage />;
      case 'drug':
        return <DrugDrivePage />;
      case 'heavy-vehicle':
        return <HeavyVehiclePerformancePage />;
      case 'road-eng':
        return <RoadEngineeringPage />;
      case 'patrol-plan':
        return <PatrolPlanPage />;
      case 'speed':
        return <SpeedPerformancePage />;
      case 'pedestrian':
        return <PedestrianAnalysisPage />;
      case 'monthly':
        return <PerformanceComparisonPage />;
      case 'ai-report':
        return readOnly ? <DashboardView /> : <AIReportPage />;
      case 'import':
        return readOnly ? <DashboardView /> : <DataImportPage />;
      default:
        return <DashboardView />;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-nook-cream via-white to-nook-sky/10">
      <Sidebar activeView={activeView} onViewChange={safeSetView} readOnly={readOnly} onLogout={!readOnly ? logout : undefined} />
      <main className="ml-64 min-h-screen">
        <Header />
        {renderView()}
      </main>
    </div>
  );
};

export default App;
