/**
 * PatrolPlanPage - 勤務建議單（Phase 2）
 *
 * DDACTS（Data-Driven Approach to Crime and Traffic Safety）簡化版：
 * 依「事故能量（EPDO）× 班別 × 熱點」找出轄下 7 個派出所/分駐所各自的高風險時段，
 * 並比對現有舉發張數標記「取締缺口」，供勤務編排參採。
 */
import React, { useEffect, useState } from 'react';
import { ClipboardList } from 'lucide-react';
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
                          {/* 第三行：熱點 chips */}
                          {slot.hotspots?.length > 0 && (
                            <div className="flex flex-wrap gap-1.5">
                              {slot.hotspots.map((h: any, i: number) => (
                                <span key={i} className="bg-surface-3 rounded px-2 text-xs text-text-muted">
                                  {h.location}×{h.count}
                                </span>
                              ))}
                            </div>
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
