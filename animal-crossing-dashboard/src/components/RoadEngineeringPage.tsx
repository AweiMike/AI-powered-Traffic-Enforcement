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
import { Construction, Lightbulb, Download, MapPin, Moon, AlertTriangle, FileSearch, Milestone, ChevronDown, ChevronUp } from 'lucide-react';
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

  // ---- 會勘資料產生器 + 卷宗 ----
  const [dossierLat, setDossierLat] = useState('');
  const [dossierLng, setDossierLng] = useState('');
  const [dossierRadius, setDossierRadius] = useState(200);
  const [dossier, setDossier] = useState<any>(null);
  const [dossierLoading, setDossierLoading] = useState(false);
  const [casesExpanded, setCasesExpanded] = useState(false);
  const dossierSectionRef = useRef<HTMLDivElement>(null);

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

  // 列印完成（或取消）後移除 body class，避免影響下次一般畫面顯示
  useEffect(() => {
    const handleAfterPrint = () => document.body.classList.remove('printing-area');
    window.addEventListener('afterprint', handleAfterPrint);
    return () => window.removeEventListener('afterprint', handleAfterPrint);
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

  /** 列印會勘卷宗：先展開案件明細，再觸發瀏覽器列印（僅印 .print-area 範圍，見 index.css） */
  const handlePrintDossier = () => {
    setCasesExpanded(true);
    setTimeout(() => {
      document.body.classList.add('printing-area');
      window.print();
    }, 50);
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
                  <button
                    onClick={handlePrintDossier}
                    className="print:hidden shrink-0 px-3 py-1.5 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-lg transition-colors"
                  >
                    🖨 列印
                  </button>
                </div>

                {/* b. 概要 6 小卡 + by_year */}
                <div className="p-5 border-b border-surface-3">
                  <div className="grid grid-cols-6 gap-2 mb-3">
                    <SummaryMini label="3年總件數" value={dossier.summary.total} />
                    <SummaryMini label="EPDO" value={dossier.summary.epdo} />
                    <SummaryMini label="A1" value={dossier.summary.a1} valueClassName="text-danger" />
                    <SummaryMini label="死亡" value={dossier.summary.deaths} />
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
                    <div className="max-h-96 overflow-y-auto border border-surface-3 rounded-xl">
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
                              </td>
                              <td className="px-3 py-2 max-w-[200px] truncate" title={c.location}>{c.location}</td>
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
        </>
      )}
    </div>
  );
};

export default RoadEngineeringPage;
