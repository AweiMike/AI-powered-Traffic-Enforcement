/**
 * RoadEngineeringPage - 道路工程改善（Phase 1）
 *
 * 首發功能：道路照明故障事故清冊（快贏）
 *   資料源：EIS「5.道路照明設備」=「有照明未開啟或故障」
 *   用途：含 GPS 的修燈通報清單，一鍵匯出 CSV 給養工處，附死傷佐證。
 *
 * 後續（Phase 2）：會勘卷宗生成器、台20線廊帶分析、對策庫將掛載於此頁。
 */
import React, { useEffect, useState } from 'react';
import { Construction, Lightbulb, Download, MapPin, Moon, AlertTriangle } from 'lucide-react';
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

const RoadEngineeringPage: React.FC = () => {
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  // 「有照明未開啟或故障」白天屬正常狀態（燈本不開）；夜間才是修燈通報重點，預設只看夜間
  const [nightOnly, setNightOnly] = useState(true);

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

  const s = data?.summary;

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-nook-text flex items-center gap-2">
          <Construction className="w-6 h-6 text-amber-600" />
          道路工程改善
        </h2>
        <p className="text-nook-text/60 mt-1">工程端資料分析：照明故障通報、會勘佐證資料（Phase 1）</p>
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
        </>
      )}
    </div>
  );
};

export default RoadEngineeringPage;
