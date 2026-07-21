/**
 * RoadEngineeringPage - 道路工程改善（Phase 1 + Phase 2）
 *
 * Phase 1：道路照明故障事故清冊（快贏）
 *   資料源：EIS「5.道路照明設備」=「有照明未開啟或故障」
 *   用途：含 GPS 的修燈通報清單，一鍵匯出 CSV 給養工處，附死傷佐證。
 *
 * Phase 2：
 *   - 廊帶（公路路線）線性分析：找出應優先介入的路線與熱段（0.5 公里分段）
 *   - 會勘資料產生器：輸入座標＋半徑，彙整近 3 年事故樣態與改善建議，支援列印卷宗
 */
import React, { useEffect, useRef, useState } from 'react';
import { Construction, Lightbulb, Download, MapPin, Moon, AlertTriangle, FileSearch, Milestone, ChevronDown, ChevronUp, Hammer, Trash2 } from 'lucide-react';
import DateRangePicker, { type DateRange } from './DateRangePicker';
import { apiClient } from '../api/client';

function defaultRange(): DateRange {
  const now = new Date();
  const start = new Date(now.getFullYear() - 1, now.getMonth(), now.getDate());
  const fmt = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return { startDate: fmt(start), endDate: fmt(now) };
}

const SEV_COLOR: Record<string, string> = {
  A1: 'text-red-600 bg-red-50',
  A2: 'text-orange-600 bg-orange-50',
  A3: 'text-amber-600 bg-amber-50',
};

/** 會勘卷宗用：概要小卡 */
function SummaryMini({ label, value, valueClassName }: { label: string; value: React.ReactNode; valueClassName?: string }) {
  return (
    <div className="bg-surface-2 rounded-xl p-2.5 text-center">
      <div className={`text-lg font-bold tabular-nums ${valueClassName || 'text-nook-text'}`}>{value}</div>
      <div className="text-[10px] text-text-muted mt-0.5">{label}</div>
    </div>
  );
}

/** 會勘卷宗用：{name,count} 水平長條清單（事故型態 Top5 / 肇因 Top5 共用） */
function HBarList({ items }: { items: Array<{ name: string; count: number }> | undefined }) {
  if (!items || items.length === 0) return <p className="text-xs text-text-subtle">無資料</p>;
  const max = Math.max(...items.map((i) => i.count), 1);
  return (
    <div className="space-y-1.5">
      {items.map((it) => (
        <div key={it.name} className="flex items-center gap-2">
          <span className="w-20 shrink-0 text-xs text-text-muted truncate" title={it.name}>{it.name}</span>
          <div className="flex-1 h-4 bg-surface-3 rounded overflow-hidden">
            <div className="h-full bg-accent/70 rounded" style={{ width: `${(it.count / max) * 100}%` }} />
          </div>
          <span className="w-6 text-right text-xs font-bold tabular-nums">{it.count}</span>
        </div>
      ))}
    </div>
  );
}

/** 改善成效追蹤：登記表單欄位 */
interface ImprovementFormState {
  title: string;
  measure_type: string;
  implemented_date: string;
  latitude: string;
  longitude: string;
  radius_m: number;
  source: string;
  description: string;
}

const MEASURE_TYPES = ['照明改善', '號誌增設', '標線標誌', '實體工程', '測速科技執法', '其他'];

function defaultImprovementForm(): ImprovementFormState {
  return {
    title: '',
    measure_type: MEASURE_TYPES[0],
    implemented_date: '',
    latitude: '',
    longitude: '',
    radius_m: 200,
    source: '',
    description: '',
  };
}

/** 淨效果 badge 色階（net_pct 越負代表改善幅度越大；null 表示樣本不足無法計算） */
function netEffectBadgeClass(netPct: number | null | undefined): string {
  if (netPct == null) return 'bg-surface-3 text-text-muted';
  if (netPct <= -30) return 'bg-success text-white';
  if (netPct <= -10) return 'bg-success/15 text-success';
  if (netPct < 10) return 'bg-surface-3 text-text-muted';
  return 'bg-danger text-white';
}

/** 改善成效追蹤：單筆措施成效卡（改善前後對比 + 全區同期控制 + 淨效果判讀） */
function ImprovementCard({ ev, onDelete }: { ev: any; onDelete: (id: number) => void }) {
  return (
    <div className="border border-surface-3 rounded-xl p-4">
      <div className="flex items-start justify-between mb-3 gap-2">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-nook-text">{ev.title}</span>
            <span className="px-2 py-0.5 bg-surface-3 rounded-full text-xs text-text-muted">{ev.measure_type}</span>
          </div>
          <p className="text-xs text-text-subtle mt-0.5 tabular-nums">實施日 {ev.implemented_date}</p>
        </div>
        <button
          onClick={() => onDelete(ev.id)}
          title="刪除此登記"
          className="shrink-0 p-1.5 rounded-lg text-text-subtle hover:bg-red-50 hover:text-danger transition-colors"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {ev.status === 'no_after_data' ? (
        <p className="text-sm text-text-subtle py-1">實施日之後尚無資料，無法評估</p>
      ) : (
        <>
          <table className="w-full text-sm mb-3">
            <thead>
              <tr className="text-text-muted">
                <th className="text-left font-medium py-1"> </th>
                <th className="text-right font-medium py-1">改善前（{ev.before?.days ?? '—'}天）</th>
                <th className="text-right font-medium py-1">
                  改善後（{ev.after?.days ?? '—'}天）
                  {ev.preliminary && <span className="text-[10px] text-text-subtle ml-1">(初期)</span>}
                </th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              <tr className="border-t border-surface-3">
                <td className="py-1 text-text-muted">事故件數</td>
                <td className="py-1 text-right font-bold">{ev.before?.total ?? '—'}</td>
                <td className="py-1 text-right font-bold">{ev.after?.total ?? '—'}</td>
              </tr>
              <tr className="border-t border-surface-3">
                <td className="py-1 text-text-muted">日均率</td>
                <td className="py-1 text-right">{ev.before?.daily_rate != null ? ev.before.daily_rate.toFixed(4) : '—'}</td>
                <td className="py-1 text-right">{ev.after?.daily_rate != null ? ev.after.daily_rate.toFixed(4) : '—'}</td>
              </tr>
              <tr className="border-t border-surface-3">
                <td className="py-1 text-text-muted">EPDO</td>
                <td className="py-1 text-right">{ev.before?.epdo ?? '—'}</td>
                <td className="py-1 text-right">{ev.after?.epdo ?? '—'}</td>
              </tr>
              <tr className="border-t border-surface-3">
                <td className="py-1 text-text-muted">死/傷</td>
                <td className="py-1 text-right">{ev.before?.deaths ?? 0}/{ev.before?.injuries ?? 0}</td>
                <td className="py-1 text-right">{ev.after?.deaths ?? 0}/{ev.after?.injuries ?? 0}</td>
              </tr>
            </tbody>
          </table>

          <div className="flex items-center flex-wrap gap-x-3 gap-y-1.5 text-xs text-text-muted mb-2">
            <span>點位變化 <span className="font-bold tabular-nums text-nook-text">{ev.pct_change != null ? `${ev.pct_change}%` : '—'}</span></span>
            <span className="text-border-strong">·</span>
            <span>全區同期 <span className="font-bold tabular-nums text-nook-text">{ev.baseline_pct != null ? `${ev.baseline_pct}%` : '—'}</span></span>
            <span className="text-border-strong">·</span>
            <span className={`px-2 py-0.5 rounded-full font-bold tabular-nums ${netEffectBadgeClass(ev.net_pct)}`}>
              {ev.net_pct == null ? '無法計算' : `淨效果 ${ev.net_pct > 0 ? '+' : ''}${ev.net_pct}%`}
            </span>
          </div>

          {ev.verdict && (
            <div className="bg-accent-soft/40 rounded-lg px-3 py-1.5 text-sm text-nook-text">
              📋 {ev.verdict}
            </div>
          )}
        </>
      )}
    </div>
  );
}

const RoadEngineeringPage: React.FC = () => {
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  // 「有照明未開啟或故障」白天屬正常狀態（燈本不開）；夜間才是修燈通報重點，預設只看夜間
  const [nightOnly, setNightOnly] = useState(true);

  // ---- 廊帶線性分析 ----
  const [corridorRoutes, setCorridorRoutes] = useState<any[]>([]);
  const [corridorRoutesLoading, setCorridorRoutesLoading] = useState(false);
  const [selectedRoute, setSelectedRoute] = useState<string>('');
  const [corridorData, setCorridorData] = useState<any>(null);
  const [corridorLoading, setCorridorLoading] = useState(false);

  // ---- 易肇事路口 Top10（依 EPDO）----
  const [hotspotsTop10, setHotspotsTop10] = useState<any[]>([]);
  const [hotspotsTop10Loading, setHotspotsTop10Loading] = useState(false);

  // ---- A1 死亡事故清冊 ----
  const [a1Cases, setA1Cases] = useState<any[]>([]);
  const [a1CasesLoading, setA1CasesLoading] = useState(false);

  // ---- 會勘資料產生器 + 卷宗 ----
  const [dossierLat, setDossierLat] = useState('');
  const [dossierLng, setDossierLng] = useState('');
  const [dossierRadius, setDossierRadius] = useState(200);
  const [dossier, setDossier] = useState<any>(null);
  const [dossierLoading, setDossierLoading] = useState(false);
  const [casesExpanded, setCasesExpanded] = useState(false);
  const dossierSectionRef = useRef<HTMLDivElement>(null);

  // ---- 改善成效追蹤 ----
  const [improvementFormOpen, setImprovementFormOpen] = useState(false);
  const [improvementForm, setImprovementForm] = useState<ImprovementFormState>(defaultImprovementForm);
  const [improvementSaving, setImprovementSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [evaluations, setEvaluations] = useState<any[]>([]);
  const [evaluationsLoading, setEvaluationsLoading] = useState(false);
  const improvementSectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const res = await apiClient.getRoadLightingIssues(range.startDate, range.endDate);
        if (alive) setData(res);
      } catch (e) {
        console.error('Failed to fetch road lighting issues', e);
        if (alive) setData(null);
      }
      if (alive) setLoading(false);
    })();
    return () => { alive = false; };
  }, [range.startDate, range.endDate]);

  // 廊帶：區間變動時重新取得路線排名，並預設選第一條（EPDO 最高）
  useEffect(() => {
    let alive = true;
    (async () => {
      setCorridorRoutesLoading(true);
      try {
        const res = await apiClient.getCorridorAnalysis(range.startDate, range.endDate);
        if (!alive) return;
        const routes = res?.routes || [];
        setCorridorRoutes(routes);
        setSelectedRoute(routes.length > 0 ? routes[0].route : '');
        if (routes.length === 0) setCorridorData(null);
      } catch (e) {
        console.error('Failed to fetch corridor route ranking', e);
        if (alive) { setCorridorRoutes([]); setSelectedRoute(''); setCorridorData(null); }
      }
      if (alive) setCorridorRoutesLoading(false);
    })();
    return () => { alive = false; };
  }, [range.startDate, range.endDate]);

  // 廊帶：選定路線（或區間變動）時取得該路線分段熱段
  useEffect(() => {
    if (!selectedRoute) return;
    let alive = true;
    (async () => {
      setCorridorLoading(true);
      try {
        const res = await apiClient.getCorridorAnalysis(range.startDate, range.endDate, selectedRoute);
        if (alive) setCorridorData(res);
      } catch (e) {
        console.error('Failed to fetch corridor segment analysis', e);
        if (alive) setCorridorData(null);
      }
      if (alive) setCorridorLoading(false);
    })();
    return () => { alive = false; };
  }, [selectedRoute, range.startDate, range.endDate]);

  // 易肇事路口 Top10：區間變動時重新取得（依 EPDO 降冪，GPS 100m 聚類）
  useEffect(() => {
    let alive = true;
    (async () => {
      setHotspotsTop10Loading(true);
      try {
        const res = await apiClient.getAccidentHotspotsRanking({ startDate: range.startDate, endDate: range.endDate, topN: 10 });
        if (alive) setHotspotsTop10(res?.hotspots || []);
      } catch (e) {
        console.error('Failed to fetch accident hotspots ranking', e);
        if (alive) setHotspotsTop10([]);
      }
      if (alive) setHotspotsTop10Loading(false);
    })();
    return () => { alive = false; };
  }, [range.startDate, range.endDate]);

  // A1 死亡事故清冊：區間變動時重新取得
  useEffect(() => {
    let alive = true;
    (async () => {
      setA1CasesLoading(true);
      try {
        const res = await apiClient.getA1Cases(range.startDate, range.endDate);
        if (alive) setA1Cases(res?.items || []);
      } catch (e) {
        console.error('Failed to fetch A1 cases', e);
        if (alive) setA1Cases([]);
      }
      if (alive) setA1CasesLoading(false);
    })();
    return () => { alive = false; };
  }, [range.startDate, range.endDate]);

  // 列印完成（或取消）後移除 body class，避免影響下次一般畫面顯示
  useEffect(() => {
    const handleAfterPrint = () => document.body.classList.remove('printing-area');
    window.addEventListener('afterprint', handleAfterPrint);
    return () => window.removeEventListener('afterprint', handleAfterPrint);
  }, []);

  /** 改善成效清單：取得所有已登記措施的改善前後比較（掛載時載入一次，儲存/刪除後重新載入） */
  const loadEvaluations = async () => {
    setEvaluationsLoading(true);
    try {
      const res = await apiClient.getImprovementEvaluations(365);
      setEvaluations(res?.items || []);
    } catch (e) {
      console.error('Failed to fetch improvement evaluations', e);
      setEvaluations([]);
    }
    setEvaluationsLoading(false);
  };

  useEffect(() => {
    loadEvaluations();
  }, []);

  const visibleItems = (data?.items || []).filter((r: any) => !nightOnly || r.is_night);

  /** 匯出 CSV（UTF-8 BOM，Excel 直開不亂碼）——給養工處的修燈通報清單，跟隨夜間篩選 */
  const exportCsv = () => {
    if (!visibleItems.length) return;
    const header = ['日期', '時間', '夜間', '行政區', '轄區派出所', '地點', '公路路線', 'GPS緯度', 'GPS經度', '嚴重度', '死亡', '受傷'];
    const rows = visibleItems.map((r: any) => [
      r.date, r.time, r.is_night ? '是' : '', r.district, r.sub_unit || '',
      (r.location || '').replaceAll(',', '，'), r.route || '',
      r.latitude ?? '', r.longitude ?? '', r.severity, r.deaths, r.injuries,
    ]);
    const csv = [header, ...rows].map((r: any[]) => r.join(',')).join('\r\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `照明故障事故清冊${nightOnly ? '_夜間' : ''}_${range.startDate}_${range.endDate}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  /** 依座標與半徑呼叫 API 產生會勘資料包 */
  const fetchDossier = async (lat: number, lng: number, radius: number) => {
    setDossierLoading(true);
    try {
      const res = await apiClient.getSiteDossier(lat, lng, radius);
      setDossier(res);
      setCasesExpanded(false); // 新查詢一律重置為收合
    } catch (e) {
      console.error('Failed to fetch site dossier', e);
      setDossier(null);
    }
    setDossierLoading(false);
  };

  /** 手動輸入座標後按「產生會勘資料」 */
  const handleGenerateDossier = () => {
    const lat = parseFloat(dossierLat);
    const lng = parseFloat(dossierLng);
    if (Number.isNaN(lat) || Number.isNaN(lng)) return;
    fetchDossier(lat, lng, dossierRadius);
  };

  /** 由照明清冊列點擊「產生會勘資料」按鈕觸發：帶入座標、直接查詢、捲動到產生器區塊 */
  const openDossier = (lat: number | null, lng: number | null) => {
    if (lat == null || lng == null) return;
    setDossierLat(String(lat));
    setDossierLng(String(lng));
    fetchDossier(lat, lng, dossierRadius);
    setTimeout(() => dossierSectionRef.current?.scrollIntoView({ behavior: 'smooth' }), 0);
  };

  // 跨頁導頁接棒：其他頁面（如勤務建議單熱點 🔍）透過 sessionStorage 帶入座標，
  // 掛載時取出並直接開啟會勘卷宗（openDossier 內建 scrollIntoView，見上，不需另補捲動）
  useEffect(() => {
    const raw = sessionStorage.getItem('pending_dossier');
    if (!raw) return;
    sessionStorage.removeItem('pending_dossier');
    try {
      const { lat, lng } = JSON.parse(raw);
      if (lat != null && lng != null) openDossier(lat, lng);
    } catch {
      /* ignore malformed payload */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** 列印會勘卷宗：先展開案件明細，再觸發瀏覽器列印（僅印 .print-area 範圍，見 index.css） */
  const handlePrintDossier = () => {
    setCasesExpanded(true);
    setTimeout(() => {
      document.body.classList.add('printing-area');
      window.print();
    }, 50);
  };

  /** 儲存改善措施登記；未登入（401）顯示唯讀模式提示，其餘錯誤顯示後端 detail */
  const handleSaveImprovement = async () => {
    setFormError(null);
    const lat = parseFloat(improvementForm.latitude);
    const lng = parseFloat(improvementForm.longitude);
    if (!improvementForm.title || !improvementForm.implemented_date || Number.isNaN(lat) || Number.isNaN(lng)) {
      setFormError('請填寫必填欄位（措施名稱、實施日期、緯度、經度）');
      return;
    }
    setImprovementSaving(true);
    try {
      await apiClient.createImprovement({
        title: improvementForm.title,
        measure_type: improvementForm.measure_type,
        latitude: lat,
        longitude: lng,
        radius_m: improvementForm.radius_m,
        implemented_date: improvementForm.implemented_date,
        description: improvementForm.description || undefined,
        source: improvementForm.source || undefined,
      });
      setImprovementForm(defaultImprovementForm());
      setImprovementFormOpen(false);
      await loadEvaluations();
    } catch (e: any) {
      setFormError(e?.status === 401 ? '需登入後才能登記（唯讀模式無法寫入）' : (e?.detail || '登記失敗，請稍後再試'));
    }
    setImprovementSaving(false);
  };

  /** 刪除改善措施登記；未登入（401）顯示唯讀模式提示，其餘錯誤顯示後端 detail */
  const handleDeleteImprovement = async (id: number) => {
    if (!window.confirm('確定刪除此登記？')) return;
    setActionError(null);
    try {
      await apiClient.deleteImprovement(id);
      await loadEvaluations();
    } catch (e: any) {
      setActionError(e?.status === 401 ? '需登入後才能刪除（唯讀模式無法寫入）' : (e?.detail || '刪除失敗，請稍後再試'));
    }
  };

  /** 由會勘卷宗點擊「登記此點改善」：展開登記表單、帶入卷宗座標/半徑、來源預設會勘、捲動到表單 */
  const handleRegisterFromDossier = () => {
    if (!dossier) return;
    setImprovementForm((f) => ({
      ...f,
      latitude: String(dossier.center.lat),
      longitude: String(dossier.center.lng),
      radius_m: dossier.center.radius_m,
      source: '會勘',
    }));
    setImprovementFormOpen(true);
    setFormError(null);
    setTimeout(() => improvementSectionRef.current?.scrollIntoView({ behavior: 'smooth' }), 0);
  };

  const s = data?.summary;

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-nook-text flex items-center gap-2">
          <Construction className="w-6 h-6 text-amber-600" />
          道路工程改善
        </h2>
        <p className="text-nook-text/60 mt-1">工程端資料分析：照明故障通報、廊帶熱段分析、會勘佐證資料（Phase 2）</p>
      </div>

      <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-4 nook-shadow mb-6">
        <DateRangePicker value={range} onChange={setRange} />
      </div>

      {loading ? (
        <div className="p-12 text-center text-text-subtle">載入中...</div>
      ) : !data ? (
        <div className="p-12 text-center text-text-subtle">尚無資料</div>
      ) : (
        <>
          {/* KPI */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="bg-gradient-to-br from-amber-50 to-amber-100/50 border border-amber-200 rounded-2xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-nook-text/70">照明故障事故</span>
                <Lightbulb className="w-5 h-5 text-amber-600" />
              </div>
              <div className="text-2xl font-bold text-nook-text tabular-nums">{s.total}</div>
              <p className="text-[10px] text-amber-600/80 mt-1">路燈未開啟或故障之事故案件</p>
            </div>
            <div className="bg-gradient-to-br from-indigo-50 to-indigo-100/50 border border-indigo-200 rounded-2xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-nook-text/70">夜間占比</span>
                <Moon className="w-5 h-5 text-indigo-600" />
              </div>
              <div className="text-2xl font-bold text-nook-text tabular-nums">{s.night_pct}%</div>
              <p className="text-[10px] text-indigo-600/80 mt-1">夜間 {s.night} 件（18-06 時）</p>
            </div>
            <div className="bg-gradient-to-br from-red-50 to-red-100/50 border border-red-200 rounded-2xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-nook-text/70">涉及死傷</span>
                <AlertTriangle className="w-5 h-5 text-red-600" />
              </div>
              <div className="text-2xl font-bold text-nook-text tabular-nums">
                {s.deaths + s.injuries}
              </div>
              <p className="text-[10px] text-red-600/80 mt-1">死亡 {s.deaths} · 受傷 {s.injuries}</p>
            </div>
            <button
              onClick={exportCsv}
              disabled={!visibleItems.length}
              className="bg-accent hover:bg-accent-hover disabled:bg-border text-white rounded-2xl p-4 flex flex-col items-center justify-center gap-2 transition-colors"
            >
              <Download className="w-6 h-6" />
              <span className="font-bold text-sm">匯出修燈通報清冊</span>
              <span className="text-[10px] text-white/70">CSV {visibleItems.length} 件 · 供發文養工處</span>
            </button>
          </div>

          {/* 廊帶線性分析 */}
          <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-5 nook-shadow mb-6">
            <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
              <h3 className="font-bold text-nook-text flex items-center gap-2">
                <Milestone className="w-4 h-4 text-accent" />廊帶線性分析
              </h3>
              {corridorRoutes.length > 0 && (
                <select
                  value={selectedRoute}
                  onChange={(e) => setSelectedRoute(e.target.value)}
                  className="text-sm border border-surface-3 rounded-lg px-2 py-1.5 bg-white text-nook-text focus:outline-none focus:ring-1 focus:ring-accent"
                >
                  {corridorRoutes.map((r: any) => (
                    <option key={r.route} value={r.route}>{r.route}（{r.total}件）</option>
                  ))}
                </select>
              )}
            </div>

            {corridorRoutesLoading ? (
              <div className="py-8 text-center text-text-subtle text-sm">載入路線資料中...</div>
            ) : corridorRoutes.length === 0 ? (
              <div className="py-8 text-center text-text-subtle text-sm">此區間查無公路路線事故資料</div>
            ) : corridorLoading ? (
              <div className="py-8 text-center text-text-subtle text-sm">載入分段資料中...</div>
            ) : corridorData?.segments?.length ? (
              <>
                {/* top_segments 前 3：熱段 chips */}
                {corridorData.top_segments?.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-3">
                    {corridorData.top_segments.slice(0, 3).map((seg: any) => (
                      <span
                        key={`${seg.km_start}-${seg.km_end}`}
                        className="inline-flex items-center gap-1 px-2.5 py-1 bg-surface-3 rounded-full text-xs font-medium text-nook-text"
                      >
                        🔥 {seg.km_start.toFixed(1)}-{seg.km_end.toFixed(1)}K · {seg.total}件 · {seg.top_crash_type || '型態不明'}
                      </span>
                    ))}
                  </div>
                )}

                {/* 段列表 */}
                <div className="max-h-80 overflow-y-auto space-y-1.5 pr-1">
                  {(() => {
                    const maxEpdo = Math.max(...corridorData.segments.map((seg: any) => seg.epdo), 1);
                    return corridorData.segments.map((seg: any) => {
                      const barColor = seg.a1 > 0 ? 'bg-danger' : seg.a2 > 0 ? 'bg-warning' : 'bg-amber-400';
                      return (
                        <div
                          key={`${seg.km_start}-${seg.km_end}`}
                          className="flex items-center gap-2"
                          title={seg.top_cause || undefined}
                        >
                          <span className="w-24 shrink-0 text-xs text-text-muted tabular-nums">
                            {seg.km_start.toFixed(1)}-{seg.km_end.toFixed(1)}K
                          </span>
                          <div className="flex-1 h-5 bg-surface-3 rounded overflow-hidden">
                            <div className={`h-full ${barColor} rounded`} style={{ width: `${(seg.epdo / maxEpdo) * 100}%` }} />
                          </div>
                          <span className="w-32 shrink-0 text-right text-xs font-bold text-nook-text tabular-nums">
                            {seg.total}件/EPDO {seg.epdo}
                          </span>
                        </div>
                      );
                    });
                  })()}
                </div>
                <p className="text-[11px] text-text-subtle mt-2">
                  {selectedRoute} 共 {corridorData.total_with_km} 件含里程座標事故，切為 {corridorData.segments.length} 段（每段 0.5 公里）
                </p>
              </>
            ) : (
              <div className="py-8 text-center text-text-subtle text-sm">此路線於本區間內無含里程座標之事故資料</div>
            )}
          </div>

          {/* 易肇事路口 Top10（依 EPDO） */}
          <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-5 nook-shadow mb-6">
            <h3 className="font-bold text-nook-text flex items-center gap-2">
              🚨 易肇事路口 Top 10（依 EPDO）
            </h3>
            <p className="text-[11px] text-text-subtle mt-1 mb-3">
              GPS 100 公尺聚類 · 依 EPDO（事故當量）排序 · 點 <FileSearch className="inline w-3 h-3" /> 產生該路口會勘資料包
            </p>
            {hotspotsTop10Loading ? (
              <div className="py-8 text-center text-text-subtle text-sm">載入中...</div>
            ) : hotspotsTop10.length === 0 ? (
              <div className="py-8 text-center text-text-subtle text-sm">此區間無易肇事路口資料</div>
            ) : (
              <div className="max-h-80 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-surface-2">
                    <tr className="text-nook-text/70">
                      <th className="px-3 py-2.5 text-center font-medium">排名</th>
                      <th className="px-3 py-2.5 text-left font-medium">地點</th>
                      <th className="px-3 py-2.5 text-left font-medium">行政區</th>
                      <th className="px-3 py-2.5 text-right font-medium">EPDO</th>
                      <th className="px-3 py-2.5 text-right font-medium">總件數</th>
                      <th className="px-3 py-2.5 text-right font-medium">A1·A2·A3</th>
                      <th className="px-3 py-2.5 text-right font-medium">趨勢</th>
                      <th className="px-3 py-2.5 text-center font-medium">會勘</th>
                    </tr>
                  </thead>
                  <tbody>
                    {hotspotsTop10.map((h: any) => (
                      <tr key={`${h.rank}-${h.location}`} className="border-t border-surface-3">
                        <td className="px-3 py-2 text-center tabular-nums">
                          {h.rank === 1 ? '🥇' : h.rank === 2 ? '🥈' : h.rank === 3 ? '🥉' : h.rank}
                        </td>
                        <td className="px-3 py-2 max-w-[220px] truncate" title={h.location}>{h.location}</td>
                        <td className="px-3 py-2 whitespace-nowrap">{h.district}</td>
                        <td className="px-3 py-2 text-right font-bold text-danger tabular-nums">{h.epdo}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{h.total}</td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          <span className={h.a1_count > 0 ? 'text-red-600 font-bold' : ''}>{h.a1_count}</span>
                          ・{h.a2_count}・{h.a3_count}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {h.trend_pct != null ? (
                            <span className={h.trend_pct > 0 ? 'text-red-600 font-bold' : h.trend_pct < 0 ? 'text-green-600 font-bold' : 'text-text-muted'}>
                              {h.trend_pct > 0 ? '↑' : h.trend_pct < 0 ? '↓' : ''}{Math.abs(h.trend_pct)}%
                            </span>
                          ) : '—'}
                        </td>
                        <td className="px-3 py-2 text-center">
                          <button
                            onClick={() => openDossier(h.latitude, h.longitude)}
                            disabled={h.latitude == null || h.longitude == null}
                            title="產生會勘資料"
                            className="p-1.5 rounded-lg text-accent hover:bg-accent-soft disabled:text-text-subtle disabled:hover:bg-transparent disabled:cursor-not-allowed transition-colors"
                          >
                            <FileSearch className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* A1 死亡事故清冊 */}
          <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-5 nook-shadow mb-6">
            <h3 className="font-bold text-nook-text flex items-center gap-2">
              ⚫ A1 死亡事故清冊
            </h3>
            <p className="text-[11px] text-text-subtle mt-1 mb-3">
              A1 案件依規定應辦理會勘檢討 · 點 <FileSearch className="inline w-3 h-3" /> 一鍵產生會勘資料包
            </p>
            {a1CasesLoading ? (
              <div className="py-8 text-center text-text-subtle text-sm">載入中...</div>
            ) : a1Cases.length === 0 ? (
              <div className="py-8 text-center text-text-subtle text-sm">此區間無 A1 死亡事故</div>
            ) : (
              <div className="max-h-80 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-surface-2">
                    <tr className="text-nook-text/70">
                      <th className="px-3 py-2.5 text-left font-medium">日期</th>
                      <th className="px-3 py-2.5 text-left font-medium">時間</th>
                      <th className="px-3 py-2.5 text-left font-medium">區</th>
                      <th className="px-3 py-2.5 text-left font-medium">轄區</th>
                      <th className="px-3 py-2.5 text-left font-medium">地點</th>
                      <th className="px-3 py-2.5 text-right font-medium">死亡</th>
                      <th className="px-3 py-2.5 text-right font-medium">受傷</th>
                      <th className="px-3 py-2.5 text-center font-medium">會勘</th>
                    </tr>
                  </thead>
                  <tbody>
                    {a1Cases.map((c: any, i: number) => (
                      <tr key={i} className="border-t border-surface-3">
                        <td className="px-3 py-2 tabular-nums whitespace-nowrap">{c.date}</td>
                        <td className="px-3 py-2 tabular-nums">{c.time}</td>
                        <td className="px-3 py-2 whitespace-nowrap">{c.district}</td>
                        <td className="px-3 py-2 whitespace-nowrap text-text-muted">{c.sub_unit || '—'}</td>
                        <td className="px-3 py-2 max-w-[260px] truncate" title={c.location}>{c.location}</td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          <span className="text-red-600 font-bold">{c.deaths}</span>
                          {c.late_deaths > 0 && (
                            <span className="tabular-nums text-red-600 text-[10px] block">⚰30日亡{c.late_deaths}</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">{c.injuries || '—'}</td>
                        <td className="px-3 py-2 text-center">
                          <button
                            onClick={() => openDossier(c.latitude, c.longitude)}
                            disabled={c.latitude == null || c.longitude == null}
                            title="產生會勘資料"
                            className="p-1.5 rounded-lg text-accent hover:bg-accent-soft disabled:text-text-subtle disabled:hover:bg-transparent disabled:cursor-not-allowed transition-colors"
                          >
                            <FileSearch className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* 分區統計 */}
          {data.by_district?.length > 0 && (
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-5 nook-shadow mb-6">
              <h3 className="font-bold text-nook-text mb-3 flex items-center gap-2">
                <MapPin className="w-4 h-4 text-accent" />各行政區照明故障事故
              </h3>
              <div className="space-y-2">
                {data.by_district.map((d: any) => {
                  const max = data.by_district[0].count;
                  return (
                    <div key={d.district} className="flex items-center gap-2">
                      <span className="text-xs text-text-muted w-16">{d.district}</span>
                      <div className="flex-1 h-5 bg-surface-3 rounded overflow-hidden">
                        <div className="h-full bg-amber-500 rounded" style={{ width: `${(d.count / max) * 100}%` }} />
                      </div>
                      <span className="font-bold text-sm tabular-nums w-12 text-right">{d.count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 清冊 */}
          <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden">
            <div className="p-4 border-b border-nook-cream/50 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-nook-text">照明故障事故清冊</h3>
                <p className="text-[11px] text-text-subtle mt-0.5">
                  白天「未開啟」屬正常狀態；<strong>夜間</strong>發生的照明未開啟/故障事故才是修燈通報重點
                </p>
              </div>
              <label className="flex items-center gap-2 text-sm text-text-muted cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={nightOnly}
                  onChange={(e) => setNightOnly(e.target.checked)}
                  className="w-4 h-4 accent-indigo-600"
                />
                僅顯示夜間（{data.summary?.night ?? 0} 件）
              </label>
            </div>
            {visibleItems.length ? (
              <div className="overflow-x-auto max-h-[540px] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-surface-2">
                    <tr className="text-nook-text/70">
                      <th className="px-3 py-2.5 text-left font-medium">日期</th>
                      <th className="px-3 py-2.5 text-left font-medium">時間</th>
                      <th className="px-3 py-2.5 text-left font-medium">區</th>
                      <th className="px-3 py-2.5 text-left font-medium">轄區</th>
                      <th className="px-3 py-2.5 text-left font-medium">地點</th>
                      <th className="px-3 py-2.5 text-left font-medium">路線</th>
                      <th className="px-3 py-2.5 text-center font-medium">嚴重度</th>
                      <th className="px-3 py-2.5 text-right font-medium">死/傷</th>
                      <th className="px-3 py-2.5 text-center font-medium">會勘</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleItems.map((r: any, i: number) => (
                      <tr key={i} className={`border-t border-surface-3 ${r.is_night ? 'bg-indigo-50/40' : ''}`}>
                        <td className="px-3 py-2 tabular-nums whitespace-nowrap">{r.date}</td>
                        <td className="px-3 py-2 tabular-nums">
                          {r.time}{r.is_night && <Moon className="inline w-3 h-3 ml-1 text-indigo-500" />}
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap">{r.district}</td>
                        <td className="px-3 py-2 whitespace-nowrap text-text-muted">{r.sub_unit || '—'}</td>
                        <td className="px-3 py-2 max-w-[260px] truncate" title={r.location}>{r.location}</td>
                        <td className="px-3 py-2 whitespace-nowrap text-text-muted tabular-nums">{r.route || '—'}</td>
                        <td className="px-3 py-2 text-center">
                          <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${SEV_COLOR[r.severity] || ''}`}>{r.severity}</span>
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {r.deaths > 0 && <span className="text-red-600 font-bold">{r.deaths}亡 </span>}
                          {r.injuries > 0 ? `${r.injuries}傷` : (r.deaths === 0 ? '—' : '')}
                        </td>
                        <td className="px-3 py-2 text-center">
                          <button
                            onClick={() => openDossier(r.latitude, r.longitude)}
                            disabled={r.latitude == null || r.longitude == null}
                            title="產生會勘資料"
                            className="p-1.5 rounded-lg text-accent hover:bg-accent-soft disabled:text-text-subtle disabled:hover:bg-transparent disabled:cursor-not-allowed transition-colors"
                          >
                            <FileSearch className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-10 text-center text-text-subtle">
                {nightOnly && (data.items?.length ?? 0) > 0
                  ? '此區間無「夜間」照明故障事故（取消勾選可看全部時段）'
                  : '此區間無照明故障事故（此欄位需「全選條件」匯出檔才有值）'}
              </div>
            )}
          </div>

          {/* 會勘資料產生器 + 卷宗顯示區 */}
          <div className="mt-6" ref={dossierSectionRef}>
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-5 nook-shadow mb-4">
              <h3 className="font-bold text-nook-text flex items-center gap-2 mb-3">
                <FileSearch className="w-4 h-4 text-accent" />會勘資料產生器
              </h3>
              <div className="flex items-end gap-3 flex-wrap">
                <div>
                  <label className="block text-xs text-text-muted mb-1">緯度 Lat</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={dossierLat}
                    onChange={(e) => setDossierLat(e.target.value)}
                    placeholder="23.0356"
                    className="w-32 px-2.5 py-1.5 text-sm border border-surface-3 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-accent tabular-nums"
                  />
                </div>
                <div>
                  <label className="block text-xs text-text-muted mb-1">經度 Lng</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={dossierLng}
                    onChange={(e) => setDossierLng(e.target.value)}
                    placeholder="120.3111"
                    className="w-32 px-2.5 py-1.5 text-sm border border-surface-3 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-accent tabular-nums"
                  />
                </div>
                <div>
                  <label className="block text-xs text-text-muted mb-1">半徑</label>
                  <select
                    value={dossierRadius}
                    onChange={(e) => setDossierRadius(Number(e.target.value))}
                    className="px-2.5 py-1.5 text-sm border border-surface-3 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-accent"
                  >
                    <option value={100}>100 公尺</option>
                    <option value={200}>200 公尺</option>
                    <option value={300}>300 公尺</option>
                    <option value={500}>500 公尺</option>
                  </select>
                </div>
                <button
                  onClick={handleGenerateDossier}
                  disabled={!dossierLat || !dossierLng}
                  className="px-4 py-1.5 bg-accent hover:bg-accent-hover disabled:bg-border text-white text-sm font-medium rounded-lg transition-colors"
                >
                  產生會勘資料
                </button>
              </div>
              <p className="text-[11px] text-text-subtle mt-2">
                可由上方照明清冊點擊 <FileSearch className="inline w-3 h-3" /> 按鈕自動帶入座標，或手動輸入座標查詢
              </p>
            </div>

            {dossierLoading && (
              <div className="p-8 text-center text-text-subtle bg-white/80 rounded-2xl nook-shadow">載入會勘資料中...</div>
            )}

            {!dossierLoading && dossier && (
              <div id="dossier-print-area" className="print-area bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden">
                {/* a. 標頭 */}
                <div className="p-5 border-b border-surface-3 flex items-start justify-between">
                  <div>
                    <h3 className="font-bold text-lg text-nook-text">會勘資料包</h3>
                    <p className="text-xs text-text-muted mt-1 tabular-nums">
                      座標 {dossier.center.lat.toFixed(4)}, {dossier.center.lng.toFixed(4)} · 半徑 {dossier.center.radius_m} 公尺
                    </p>
                    <p className="text-xs text-text-subtle mt-0.5 tabular-nums">
                      分析窗 {dossier.window.start_date} ~ {dossier.window.end_date}
                    </p>
                  </div>
                  <div className="print:hidden shrink-0 flex items-center gap-2">
                    <button
                      onClick={handleRegisterFromDossier}
                      className="px-3 py-1.5 bg-white border border-accent text-accent hover:bg-accent-soft text-sm font-medium rounded-lg transition-colors flex items-center gap-1.5"
                    >
                      <Hammer className="w-4 h-4" />➕ 登記此點改善
                    </button>
                    <button
                      onClick={handlePrintDossier}
                      className="px-3 py-1.5 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-lg transition-colors"
                    >
                      🖨 列印
                    </button>
                  </div>
                </div>

                {/* b. 概要 6 小卡 + by_year */}
                <div className="p-5 border-b border-surface-3">
                  <div className="grid grid-cols-6 gap-2 mb-3">
                    <SummaryMini label="3年總件數" value={dossier.summary.total} />
                    <SummaryMini label="EPDO" value={dossier.summary.epdo} />
                    <SummaryMini label="A1" value={dossier.summary.a1} valueClassName="text-danger" />
                    <SummaryMini
                      label="死亡"
                      value={
                        <>
                          {dossier.summary.deaths}
                          {dossier.summary.late_deaths > 0 && (
                            <div className="text-[10px] text-danger font-normal mt-0.5">
                              另 30日死亡 {dossier.summary.late_deaths}（列A2）
                            </div>
                          )}
                        </>
                      }
                    />
                    <SummaryMini label="受傷" value={dossier.summary.injuries} />
                    <SummaryMini label="夜間占比" value={`${dossier.patterns.night_pct}%`} />
                  </div>
                  {dossier.summary.by_year?.length > 0 && (() => {
                    const maxY = Math.max(...dossier.summary.by_year.map((y: any) => y.count), 1);
                    return (
                      <div className="space-y-1">
                        {dossier.summary.by_year.map((y: any) => (
                          <div key={y.year} className="flex items-center gap-2">
                            <span className="w-10 text-xs text-text-muted tabular-nums">{y.year}</span>
                            <div className="flex-1 h-3 bg-surface-3 rounded overflow-hidden">
                              <div className="h-full bg-accent/70 rounded" style={{ width: `${(y.count / maxY) * 100}%` }} />
                            </div>
                            <span className="w-8 text-xs text-right tabular-nums">{y.count}</span>
                          </div>
                        ))}
                      </div>
                    );
                  })()}
                </div>

                {/* c. 樣態分析：型態/肇因雙欄 + 班別分布 + 號誌/道路型態 chips */}
                <div className="p-5 border-b border-surface-3 space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <h4 className="text-sm font-bold text-nook-text mb-2">事故型態 Top5</h4>
                      <HBarList items={dossier.patterns.top_crash_types} />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-nook-text mb-2">肇因 Top5</h4>
                      <HBarList items={dossier.patterns.top_causes} />
                    </div>
                  </div>

                  <div>
                    <h4 className="text-sm font-bold text-nook-text mb-2">班別分布（12 班，每班 2 小時）</h4>
                    <div className="flex items-end gap-1 h-16">
                      {(() => {
                        const maxShift = Math.max(...dossier.patterns.by_shift.map((sh: any) => sh.count), 1);
                        return dossier.patterns.by_shift.map((sh: any, idx: number) => (
                          <div key={sh.shift} className="flex-1 flex flex-col items-center justify-end h-full" title={`第${sh.shift}班 ${sh.count}件`}>
                            <div
                              className="w-full bg-accent/60 rounded-t"
                              style={{ height: `${(sh.count / maxShift) * 100}%`, minHeight: sh.count > 0 ? '2px' : '0' }}
                            />
                            <span className="text-[9px] text-text-subtle mt-0.5 tabular-nums">
                              {idx % 3 === 0 ? `${(idx * 2).toString().padStart(2, '0')}` : ''}
                            </span>
                          </div>
                        ));
                      })()}
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-4">
                    <div className="flex flex-wrap gap-1.5">
                      {dossier.patterns.signal_types?.map((it: any) => (
                        <span key={it.name} className="bg-surface-3 rounded px-2 text-xs text-text-muted">{it.name}×{it.count}</span>
                      ))}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {dossier.patterns.road_types?.map((it: any) => (
                        <span key={it.name} className="bg-surface-3 rounded px-2 text-xs text-text-muted">{it.name}×{it.count}</span>
                      ))}
                    </div>
                  </div>
                </div>

                {/* d. 涉入對象 */}
                <div className="p-5 border-b border-surface-3">
                  <h4 className="text-sm font-bold text-nook-text mb-2">涉入對象</h4>
                  <div className="flex flex-wrap gap-1.5 text-xs">
                    <span className="bg-surface-3 rounded px-2 text-text-muted">高齡 {dossier.involved.elderly}</span>
                    <span className="bg-surface-3 rounded px-2 text-text-muted">青少年 {dossier.involved.youth}</span>
                    <span className={`rounded px-2 ${dossier.involved.dui > 0 ? 'bg-red-50 text-danger font-bold' : 'bg-surface-3 text-text-muted'}`}>
                      酒駕 {dossier.involved.dui}
                    </span>
                    <span className="bg-surface-3 rounded px-2 text-text-muted">無照 {dossier.involved.unlicensed}</span>
                    <span className="bg-surface-3 rounded px-2 text-text-muted">行人 {dossier.involved.pedestrian}</span>
                    <span className="bg-surface-3 rounded px-2 text-text-muted">肇逃 {dossier.involved.hit_and_run}</span>
                  </div>
                </div>

                {/* e. 改善建議 */}
                <div className="p-5 border-b border-surface-3">
                  <h4 className="text-sm font-bold text-nook-text mb-2">改善建議</h4>
                  <div className="space-y-2">
                    {dossier.suggestions?.map((sug: any, i: number) => (
                      <div key={i} className="bg-amber-50 border border-amber-200 rounded-xl p-3">
                        <p className="font-bold text-sm text-nook-text">{sug.title}</p>
                        <p className="text-sm text-text-muted mt-0.5">{sug.reason}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* f. 案件明細（預設收合） */}
                <div className="p-5">
                  <button
                    onClick={() => setCasesExpanded((v) => !v)}
                    className="print:hidden flex items-center gap-1.5 text-sm font-bold text-nook-text mb-2"
                  >
                    {casesExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    案件明細（{dossier.cases?.length ?? 0} 件）
                  </button>
                  <p className="hidden print:block text-sm font-bold text-nook-text mb-2">
                    案件明細（{dossier.cases?.length ?? 0} 件）
                  </p>

                  {casesExpanded && (
                    <div className="max-h-96 overflow-y-auto border border-surface-3 rounded-xl print:max-h-none print:overflow-visible">
                      <table className="w-full text-sm">
                        <thead className="sticky top-0 bg-surface-2">
                          <tr className="text-text-muted">
                            <th className="px-3 py-2 text-left font-medium">日期</th>
                            <th className="px-3 py-2 text-left font-medium">時間</th>
                            <th className="px-3 py-2 text-center font-medium">嚴重度</th>
                            <th className="px-3 py-2 text-left font-medium">型態</th>
                            <th className="px-3 py-2 text-left font-medium">肇因</th>
                            <th className="px-3 py-2 text-right font-medium">死/傷</th>
                            <th className="px-3 py-2 text-left font-medium">地點</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dossier.cases?.map((c: any, i: number) => (
                            <tr key={i} className="border-t border-surface-3">
                              <td className="px-3 py-2 tabular-nums whitespace-nowrap">{c.date}</td>
                              <td className="px-3 py-2 tabular-nums">{c.time}</td>
                              <td className="px-3 py-2 text-center">
                                <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${SEV_COLOR[c.severity] || ''}`}>{c.severity}</span>
                              </td>
                              <td className="px-3 py-2">{c.crash_type || '—'}</td>
                              <td className="px-3 py-2">{c.cause || '—'}</td>
                              <td className="px-3 py-2 text-right tabular-nums">
                                {c.deaths > 0 && <span className="text-danger font-bold">{c.deaths}亡 </span>}
                                {c.injuries > 0 ? `${c.injuries}傷` : (c.deaths === 0 ? '—' : '')}
                                {/* 2-30日內死亡註記：案件分類仍為 A2，僅提示實質有人員亡故，不影響上方死/傷口徑數字 */}
                                {c.late_deaths > 0 && (
                                  <span className="tabular-nums text-danger text-[10px] block">⚰30日亡{c.late_deaths}</span>
                                )}
                              </td>
                              <td className="px-3 py-2 max-w-[200px] truncate print:max-w-none print:whitespace-normal print:overflow-visible" title={c.location}>{c.location}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* 改善成效追蹤 */}
          <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-5 nook-shadow mt-6" ref={improvementSectionRef}>
            <div className="flex items-start justify-between mb-4 flex-wrap gap-2">
              <div>
                <h3 className="font-bold text-nook-text flex items-center gap-2">
                  <Hammer className="w-4 h-4 text-accent" />改善成效追蹤
                </h3>
                <p className="text-xs text-text-subtle mt-1">登記改善措施，系統自動比較改善前後事故率（含全區同期控制）</p>
              </div>
              <button
                onClick={() => { setImprovementFormOpen((v) => !v); setFormError(null); }}
                className="shrink-0 px-3 py-1.5 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-lg transition-colors"
              >
                ➕ 登記新措施
              </button>
            </div>

            {improvementFormOpen && (
              <div className="bg-surface-2 rounded-xl p-4 mb-5">
                <div className="grid grid-cols-4 gap-3 mb-3">
                  <div className="col-span-2">
                    <label className="block text-xs text-text-muted mb-1">措施名稱 *</label>
                    <input
                      type="text"
                      value={improvementForm.title}
                      onChange={(e) => setImprovementForm((f) => ({ ...f, title: e.target.value }))}
                      placeholder="例：OO路口號誌增設"
                      className="w-full px-2.5 py-1.5 text-sm border border-surface-3 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-accent"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-text-muted mb-1">對策類型</label>
                    <select
                      value={improvementForm.measure_type}
                      onChange={(e) => setImprovementForm((f) => ({ ...f, measure_type: e.target.value }))}
                      className="w-full px-2.5 py-1.5 text-sm border border-surface-3 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-accent"
                    >
                      {MEASURE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-text-muted mb-1">實施日期 *</label>
                    <input
                      type="date"
                      value={improvementForm.implemented_date}
                      onChange={(e) => setImprovementForm((f) => ({ ...f, implemented_date: e.target.value }))}
                      className="w-full px-2.5 py-1.5 text-sm border border-surface-3 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-accent tabular-nums"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-text-muted mb-1">緯度 Lat *</label>
                    <input
                      type="number"
                      step="0.0001"
                      value={improvementForm.latitude}
                      onChange={(e) => setImprovementForm((f) => ({ ...f, latitude: e.target.value }))}
                      placeholder="23.0356"
                      className="w-full px-2.5 py-1.5 text-sm border border-surface-3 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-accent tabular-nums"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-text-muted mb-1">經度 Lng *</label>
                    <input
                      type="number"
                      step="0.0001"
                      value={improvementForm.longitude}
                      onChange={(e) => setImprovementForm((f) => ({ ...f, longitude: e.target.value }))}
                      placeholder="120.3111"
                      className="w-full px-2.5 py-1.5 text-sm border border-surface-3 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-accent tabular-nums"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-text-muted mb-1">評估半徑</label>
                    <select
                      value={improvementForm.radius_m}
                      onChange={(e) => setImprovementForm((f) => ({ ...f, radius_m: Number(e.target.value) }))}
                      className="w-full px-2.5 py-1.5 text-sm border border-surface-3 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-accent"
                    >
                      <option value={100}>100 公尺</option>
                      <option value={200}>200 公尺</option>
                      <option value={300}>300 公尺</option>
                      <option value={500}>500 公尺</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-text-muted mb-1">來源</label>
                    <select
                      value={improvementForm.source}
                      onChange={(e) => setImprovementForm((f) => ({ ...f, source: e.target.value }))}
                      className="w-full px-2.5 py-1.5 text-sm border border-surface-3 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-accent"
                    >
                      <option value="">（未指定）</option>
                      <option value="會勘">會勘</option>
                      <option value="道安會報">道安會報</option>
                      <option value="自行改善">自行改善</option>
                    </select>
                  </div>
                  <div className="col-span-2">
                    <label className="block text-xs text-text-muted mb-1">說明</label>
                    <input
                      type="text"
                      value={improvementForm.description}
                      onChange={(e) => setImprovementForm((f) => ({ ...f, description: e.target.value }))}
                      placeholder="選填備註"
                      className="w-full px-2.5 py-1.5 text-sm border border-surface-3 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-accent"
                    />
                  </div>
                </div>

                {formError && (
                  <div className="mb-3 bg-amber-50 border border-amber-200 text-amber-700 text-xs rounded-lg px-3 py-2">
                    {formError}
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <button
                    onClick={handleSaveImprovement}
                    disabled={improvementSaving}
                    className="px-4 py-1.5 bg-accent hover:bg-accent-hover disabled:bg-border text-white text-sm font-medium rounded-lg transition-colors"
                  >
                    {improvementSaving ? '儲存中...' : '儲存登記'}
                  </button>
                  <button
                    onClick={() => { setImprovementFormOpen(false); setFormError(null); }}
                    className="px-4 py-1.5 text-sm text-text-muted hover:bg-surface-3 rounded-lg transition-colors"
                  >
                    取消
                  </button>
                </div>
              </div>
            )}

            {actionError && (
              <div className="mb-3 bg-amber-50 border border-amber-200 text-amber-700 text-xs rounded-lg px-3 py-2">
                {actionError}
              </div>
            )}

            {evaluationsLoading ? (
              <div className="py-8 text-center text-text-subtle text-sm">載入成效資料中...</div>
            ) : evaluations.length === 0 ? (
              <div className="py-8 text-center text-text-subtle text-sm">
                尚未登記任何改善措施——完成會勘後在此登記，系統將自動追蹤成效
              </div>
            ) : (
              <div className="space-y-3">
                {evaluations.map((ev: any) => (
                  <ImprovementCard key={ev.id} ev={ev} onDelete={handleDeleteImprovement} />
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default RoadEngineeringPage;
