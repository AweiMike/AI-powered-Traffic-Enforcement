/**
 * DateRangePicker - 共用日期區間選擇器
 * 支援快捷按鈕（本週/本月/本季/本年/自訂）
 * 自動計算去年同期供對比
 */

import React, { useState, useMemo } from 'react';
import { Calendar, ChevronDown, ArrowLeftRight } from 'lucide-react';

export interface DateRange {
  startDate: string;   // YYYY-MM-DD
  endDate: string;     // YYYY-MM-DD
}

export interface DateRangeWithCompare extends DateRange {
  compareStartDate: string;
  compareEndDate: string;
  label: string;
}

interface DateRangePickerProps {
  value: DateRange;
  onChange: (range: DateRange) => void;
  showCompare?: boolean;
  className?: string;
}

/** 格式化日期為 YYYY-MM-DD */
function fmt(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** 取得今天（以資料通常到昨天為準，但用今天也可） */
function today(): Date {
  return new Date();
}

/** 本週一到今天 */
function thisWeek(): DateRange {
  const now = today();
  const dayOfWeek = now.getDay() || 7; // 0=Sun -> 7
  const mon = new Date(now);
  mon.setDate(now.getDate() - dayOfWeek + 1);
  return { startDate: fmt(mon), endDate: fmt(now) };
}

/** 本月1日到今天 */
function thisMonth(): DateRange {
  const now = today();
  const start = new Date(now.getFullYear(), now.getMonth(), 1);
  return { startDate: fmt(start), endDate: fmt(now) };
}

/** 本季第一天到今天 */
function thisQuarter(): DateRange {
  const now = today();
  const qStart = Math.floor(now.getMonth() / 3) * 3;
  const start = new Date(now.getFullYear(), qStart, 1);
  return { startDate: fmt(start), endDate: fmt(now) };
}

/** 今年1/1到今天 */
function thisYear(): DateRange {
  const now = today();
  const start = new Date(now.getFullYear(), 0, 1);
  return { startDate: fmt(start), endDate: fmt(now) };
}

/** 近 N 天 */
function lastNDays(n: number): DateRange {
  const now = today();
  const start = new Date(now);
  start.setDate(now.getDate() - n);
  return { startDate: fmt(start), endDate: fmt(now) };
}

/** 計算去年同期 */
export function getCompareRange(range: DateRange): DateRange {
  const s = new Date(range.startDate);
  const e = new Date(range.endDate);
  s.setFullYear(s.getFullYear() - 1);
  e.setFullYear(e.getFullYear() - 1);
  return { startDate: fmt(s), endDate: fmt(e) };
}

/** 把 DateRange 格式化為顯示文字 */
function rangeLabel(range: DateRange): string {
  return `${range.startDate} ~ ${range.endDate}`;
}

type PresetKey = 'week' | 'month' | 'quarter' | 'year' | '30d' | '90d' | '180d' | 'custom';

const presets: { key: PresetKey; label: string; fn?: () => DateRange }[] = [
  { key: 'week', label: '本週', fn: thisWeek },
  { key: 'month', label: '本月', fn: thisMonth },
  { key: 'quarter', label: '本季', fn: thisQuarter },
  { key: 'year', label: '本年', fn: thisYear },
  { key: '30d', label: '近30天', fn: () => lastNDays(30) },
  { key: '90d', label: '近90天', fn: () => lastNDays(90) },
  { key: '180d', label: '近180天', fn: () => lastNDays(180) },
  { key: 'custom', label: '自訂區間' },
];

const DateRangePicker: React.FC<DateRangePickerProps> = ({
  value,
  onChange,
  showCompare = true,
  className = '',
}) => {
  const [activePreset, setActivePreset] = useState<PresetKey>('year');
  const [expanded, setExpanded] = useState(false);
  const [customStart, setCustomStart] = useState(value.startDate);
  const [customEnd, setCustomEnd] = useState(value.endDate);

  const compareRange = useMemo(() => getCompareRange(value), [value]);

  const handlePreset = (key: PresetKey) => {
    setActivePreset(key);
    const preset = presets.find(p => p.key === key);
    if (preset?.fn) {
      const range = preset.fn();
      onChange(range);
      setCustomStart(range.startDate);
      setCustomEnd(range.endDate);
      setExpanded(false);
    } else {
      // custom - keep expanded
      setExpanded(true);
    }
  };

  const handleCustomApply = () => {
    if (customStart && customEnd && customStart <= customEnd) {
      onChange({ startDate: customStart, endDate: customEnd });
      setExpanded(false);
    }
  };

  return (
    <div className={`relative ${className}`}>
      {/* 主按鈕列 */}
      <div className="flex items-center gap-2 flex-wrap">
        <Calendar className="w-4 h-4 text-nook-leaf shrink-0" />
        <div className="flex gap-1 flex-wrap">
          {presets.map(p => (
            <button
              key={p.key}
              onClick={() => handlePreset(p.key)}
              className={`px-2.5 py-1 text-xs rounded-lg font-medium transition-colors ${
                activePreset === p.key
                  ? 'bg-nook-leaf text-white shadow-sm'
                  : 'bg-white/80 text-nook-text/70 hover:bg-nook-leaf/10'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* 自訂日期輸入 */}
      {activePreset === 'custom' && expanded && (
        <div className="mt-2 flex items-center gap-2 flex-wrap">
          <input
            type="date"
            value={customStart}
            onChange={e => setCustomStart(e.target.value)}
            className="px-2 py-1 text-xs border border-nook-leaf/30 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-nook-leaf"
          />
          <span className="text-xs text-nook-text/50">至</span>
          <input
            type="date"
            value={customEnd}
            onChange={e => setCustomEnd(e.target.value)}
            className="px-2 py-1 text-xs border border-nook-leaf/30 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-nook-leaf"
          />
          <button
            onClick={handleCustomApply}
            className="px-3 py-1 text-xs bg-nook-leaf text-white rounded-lg font-medium hover:bg-nook-leaf/90"
          >
            套用
          </button>
        </div>
      )}

      {/* 日期範圍摘要 & 同期對比資訊 */}
      <div className="mt-1.5 flex items-center gap-3 text-xs text-nook-text/50">
        <span>{rangeLabel(value)}</span>
        {showCompare && (
          <>
            <ArrowLeftRight className="w-3 h-3" />
            <span>去年同期 {rangeLabel(compareRange)}</span>
          </>
        )}
      </div>
    </div>
  );
};

export default DateRangePicker;
