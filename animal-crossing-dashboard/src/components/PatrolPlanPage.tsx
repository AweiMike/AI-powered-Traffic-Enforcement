/**
 * PatrolPlanPage - 勤務建議單（Phase 2）
 *
 * DDACTS（Data-Driven Approach to Crime and Traffic Safety）簡化版：
 * 依「事故能量（EPDO）× 班別 × 熱點」找出轄下 7 個派出所/分駐所各自的高風險時段，
 * 並比對現有舉發張數標記「取締缺口」，供勤務編排參採。
 */
import React, { useEffect, useState } from 'react';
import { ClipboardList, AlertTriangle } from 'lucide-react';
import DateRangePicker, { type DateRange } from './DateRangePicker';
import { apiClient } from '../api/client';

/** 預設近 90 天 */
function defaultRange(): DateRange {
  const now = new Date();
  const start = new Date(now);
  start.setDate(now.getDate() - 90);
  const fmt = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return { startDate: fmt(start), endDate: fmt(now) };
}

/**
 * 明日風險預警卡（Phase 3）
 * 依歷史同星期型態推估 7 所各班別的風險分數，供勤務編排提前部署參考。
 * 掛載時獨立呼叫 getRiskForecast()（不帶參數，後端預設抓「資料最新日 + 1」）；
 * 載入失敗或無資料時整卡隱藏，不影響下方主要的勤務建議單功能。
 */
const RiskForecastCard: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await apiClient.getRiskForecast();
        if (alive) setData(res);
      } catch (e) {
        console.error('Failed to fetch risk forecast', e);
        if (alive) setFailed(true);
      }
      if (alive) setLoading(false);
    })();
    return () => { alive = false; };
  }, []);

  // 失敗或無資料時整卡隱藏（不擋主功能）
  if (failed) return null;

  if (loading) {
    return (
      <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-4 nook-shadow mb-6 print:hidden animate-pulse">
        <div className="h-5 bg-surface-3 rounded w-40 mb-2" />
        <div className="h-3 bg-surface-3 rounded w-64 mb-4" />
        <div className="space-y-2">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="h-8 bg-surface-2 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  const rows: any[] = data?.per_unit_top ?? [];
  if (!data || rows.length === 0) return null;

  const sorted = [...rows].sort((a, b) => b.score - a.score);
  const maxScore = Math.max(...sorted.map((r) => r.score), 1);
  // 前 3 名（依 score）用較顯眼的 bg-warning，其餘用對比色 bg-amber-300
  const top3Keys = new Set(sorted.slice(0, 3).map((r) => `${r.unit}-${r.shift_id}`));

  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-4 nook-shadow mb-6 print:hidden">
      <div className="flex items-center gap-2">
        <AlertTriangle className="w-5 h-5 text-warning" />
        <h3 className="font-bold text-nook-text">明日風險預警</h3>
      </div>
      <p className="text-xs text-text-subtle mt-0.5 mb-4">
        依歷史同星期型態推估（{data.weekday_label}·樣本 {data.history_weeks} 週）
      </p>

      <div className="space-y-2">
        {sorted.map((row) => {
          const isTop3 = top3Keys.has(`${row.unit}-${row.shift_id}`);
          const width = Math.min(100, (row.score / maxScore) * 100);
          return (
            <div key={`${row.unit}-${row.shift_id}`} className="flex items-center gap-3 flex-wrap">
              <span className="w-24 shrink-0 font-medium text-sm text-nook-text truncate">{row.unit}</span>
              <span className="w-16 shrink-0 text-lg font-bold text-nook-text tabular-nums">{row.shift_label}</span>
              <div className="flex-1 min-w-[80px] h-3 bg-surface-3 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${isTop3 ? 'bg-warning' : 'bg-amber-300'}`}
                  style={{ width: `${width}%` }}
                />
              </div>
              <span className="shrink-0 text-xs text-text-muted tabular-nums whitespace-nowrap">
                score {row.score} · 樣本 {row.samples}
              </span>
              {row.top_cause && (
                <span className="shrink-0 bg-surface-3 rounded px-2 text-xs text-text-muted">{row.top_cause}</span>
              )}
              {row.dui_count > 0 && (
                <span className="shrink-0 text-xs text-danger font-bold">酒駕{row.dui_count}</span>
              )}
            </div>
          );
        })}
      </div>

      <p className="mt-3 text-[11px] text-text-subtle">
        分數 = 歷史同星期該班別事故能量之加權估計；樣本數低時僅供參考。本系統採寧可多攔不可漏網原則，7 所皆列出。
      </p>
    </div>
  );
};

const PatrolPlanPage: React.FC = () => {
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const res = await apiClient.getPatrolPlan(range.startDate, range.endDate);
        if (alive) setData(res);
      } catch (e) {
        console.error('Failed to fetch patrol plan', e);
        if (alive) setData(null);
      }
      if (alive) setLoading(false);
    })();
    return () => { alive = false; };
  }, [range.startDate, range.endDate]);

  // 列印完成（或取消）後移除 body class，避免影響下次一般畫面顯示
  useEffect(() => {
    const handleAfterPrint = () => document.body.classList.remove('printing-area');
    window.addEventListener('afterprint', handleAfterPrint);
    return () => window.removeEventListener('afterprint', handleAfterPrint);
  }, []);

  /** 列印勤務建議單（僅印 .print-area 範圍，機制見 index.css） */
  const handlePrint = () => {
    document.body.classList.add('printing-area');
    window.print();
  };

  return (
    <div className="p-8">
      <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-2xl font-bold text-nook-text flex items-center gap-2">
            <ClipboardList className="w-6 h-6 text-accent" />
            勤務建議單
          </h2>
          <p className="text-nook-text/60 mt-1">DDACTS 模式：事故能量 × 班別 × 熱點，供勤務編排參採</p>
        </div>
        <button
          onClick={handlePrint}
          className="print:hidden shrink-0 px-4 py-2 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-xl transition-colors"
        >
          🖨 列印勤務建議單
        </button>
      </div>

      <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-4 nook-shadow mb-6 print:hidden">
        <DateRangePicker value={range} onChange={setRange} />
      </div>

      <RiskForecastCard />

      <div className="print-area">
        {loading ? (
          <div className="p-12 text-center text-text-subtle">載入中...</div>
        ) : !data || !data.units?.length ? (
          <div className="p-12 text-center text-text-subtle">尚無資料</div>
        ) : (
          <div className="space-y-5">
            {data.units.map((unit: any) => {
              const hasGap = unit.top_slots?.some((slot: any) => slot.is_gap);
              return (
                <div key={unit.unit} className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden">
                  {/* 卡 header */}
                  <div className="p-4 border-b border-surface-3 flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-lg text-nook-text">{unit.unit}</span>
                      {hasGap && (
                        <span className="px-2 py-0.5 bg-red-50 text-danger text-xs font-bold rounded">⚠ 取締缺口</span>
                      )}
                    </div>
                    <span className="text-sm text-text-muted tabular-nums">
                      事故 {unit.total_crashes} 件 · EPDO {unit.total_epdo}
                    </span>
                  </div>

                  {unit.top_slots?.length > 0 ? (
                    unit.top_slots.map((slot: any) => (
                      <div key={slot.shift_id} className="p-4 border-t border-surface-3 flex gap-4 flex-wrap">
                        <div className="w-28 shrink-0 text-xl font-bold text-nook-text tabular-nums">
                          {slot.shift_label}
                        </div>
                        <div className="flex-1 min-w-[240px] space-y-1.5">
                          {/* 第一行：事故/EPDO/酒駕 + 缺口小標 */}
                          <div className="flex items-center gap-3 flex-wrap text-sm">
                            <span className="text-nook-text">
                              事故 {slot.crash_count} 件 · EPDO {slot.epdo} ·{' '}
                              <span className={slot.dui_count > 0 ? 'text-danger font-bold' : ''}>酒駕 {slot.dui_count}</span>
                            </span>
                            {slot.is_gap && (
                              <span className="text-danger text-xs font-bold">
                                取締 {slot.existing_tickets} 張，密度偏低
                              </span>
                            )}
                          </div>
                          {/* 第二行：型態/肇因 */}
                          <p className="text-sm text-text-muted">
                            {slot.top_crash_type || '型態不明'} / {slot.top_cause || '肇因不明'}
                          </p>
                          {/* 第三行：熱點 chips（GPS 聚類）／分散誠實標記 */}
                          {slot.scattered ? (
                            <p className="text-xs text-amber-600">事故點分散無明確熱點</p>
                          ) : (
                            slot.hotspots?.length > 0 && (
                              <div className="flex flex-wrap gap-1.5">
                                {slot.hotspots.map((h: any, i: number) => (
                                  <span key={i} className="inline-flex items-center gap-1 bg-surface-3 rounded px-2 text-xs text-text-muted">
                                    {h.location}×{h.count}
                                    {h.latitude != null && (
                                      <button
                                        type="button"
                                        onClick={() => {
                                          sessionStorage.setItem('pending_dossier', JSON.stringify({ lat: h.latitude, lng: h.longitude }));
                                          window.dispatchEvent(new CustomEvent('app:navigate', { detail: { view: 'road-eng' } }));
                                        }}
                                        className="print:hidden leading-none hover:opacity-70"
                                        title="開啟會勘卷宗"
                                      >
                                        🔍
                                      </button>
                                    )}
                                  </span>
                                ))}
                              </div>
                            )
                          )}
                          {/* 第四行：勤務建議 */}
                          <p className="text-sm bg-accent-soft/40 rounded-lg px-3 py-1.5">
                            💡 {slot.suggestion}
                          </p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="p-6 text-center text-text-subtle text-sm">本期無事故紀錄</div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default PatrolPlanPage;
