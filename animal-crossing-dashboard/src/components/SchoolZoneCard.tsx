/**
 * SchoolZoneCard - 校園時段熱區卡（青少年微電車事故）
 *
 * 資料來源：GET /recommendations/school-zone-hotspots?start_date=...&end_date=...
 * 回傳 { period, morning:{label,total,hotspots:[{location,count,district}]},
 *        afternoon:{...}, other_total, youth_total }
 *
 * 版面：左右兩欄（上學／放學），各欄顯示 label + total 大字 + 熱點清單；
 * 底部說明段落標示時段定義與勤務參考用途。
 */
import React, { useEffect, useState } from 'react';
import { School } from 'lucide-react';
import type { DateRange } from './DateRangePicker';

interface SchoolZoneHotspot {
  location: string;
  count: number;
  district: string;
}

interface SchoolZonePeriod {
  label: string;
  total: number;
  hotspots: SchoolZoneHotspot[];
}

interface SchoolZoneData {
  period: { start_date: string; end_date: string };
  morning: SchoolZonePeriod;
  afternoon: SchoolZonePeriod;
  other_total: number;
  youth_total: number;
}

interface SchoolZoneCardProps {
  range: DateRange;
}

/** 單一時段欄位：label + total 大字 + 熱點清單 */
function PeriodColumn({ period }: { period: SchoolZonePeriod }) {
  return (
    <div>
      <div className="flex items-baseline gap-2 mb-3">
        <h4 className="text-sm font-bold text-nook-text">{period.label}</h4>
        <span className="text-2xl font-bold text-accent tabular-nums">{period.total}</span>
        <span className="text-xs text-text-subtle">件</span>
      </div>
      {period.hotspots.length === 0 ? (
        <p className="text-xs text-text-subtle">無明顯熱點</p>
      ) : (
        <div className="space-y-2">
          {period.hotspots.map((h) => (
            <div key={h.location} className="flex items-center justify-between gap-2 px-3 py-2 bg-surface-2 rounded-lg">
              <div className="min-w-0">
                <p className="text-sm font-medium text-nook-text truncate" title={h.location}>{h.location}</p>
                <p className="text-xs text-text-subtle">{h.district}</p>
              </div>
              <span className="shrink-0 text-xs font-semibold tabular-nums bg-accent-soft text-accent px-2 py-0.5 rounded-full">
                {h.count} 件
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const SchoolZoneCard: React.FC<SchoolZoneCardProps> = ({ range }) => {
  const [data, setData] = useState<SchoolZoneData | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      setFailed(false);
      try {
        const { apiClient } = await import('../api/client');
        const res = await apiClient.getSchoolZoneHotspots(range.startDate, range.endDate);
        if (alive) setData(res);
      } catch (e) {
        console.error('Failed to fetch school zone hotspots', e);
        if (alive) setFailed(true);
      }
      if (alive) setLoading(false);
    })();
    return () => { alive = false; };
  }, [range.startDate, range.endDate]);

  if (failed) return null;

  if (loading) {
    return (
      <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden mb-6">
        <div className="p-4 border-b border-nook-cream/50 flex items-center gap-2">
          <School className="w-5 h-5 text-accent" />
          <h3 className="font-bold text-nook-text">校園時段熱區（青少年微電車）</h3>
        </div>
        <div className="p-6 space-y-4 animate-pulse">
          <div className="h-32 bg-surface-3 rounded-xl" />
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden mb-6">
      <div className="p-4 border-b border-nook-cream/50 flex items-center gap-2">
        <School className="w-5 h-5 text-accent" />
        <h3 className="font-bold text-nook-text">校園時段熱區（青少年微電車）</h3>
        <span className="text-xs text-text-subtle ml-auto tabular-nums">青少年案件共 {data.youth_total} 件</span>
      </div>

      {data.youth_total === 0 ? (
        <div className="p-12 text-center text-text-subtle">此區間無青少年微電車案件</div>
      ) : (
        <div className="p-4">
          <div className="grid grid-cols-2 gap-x-8 gap-y-4">
            <PeriodColumn period={data.morning} />
            <PeriodColumn period={data.afternoon} />
          </div>
          <p className="text-xs text-text-subtle mt-4 pt-3 border-t border-nook-cream/50 leading-relaxed">
            上學 06-08 時 · 放學 16-18 時 · 其他時段 {data.other_total} 件。熱點清單可作為校方交通安全宣導與護童勤務參考。
          </p>
        </div>
      )}
    </div>
  );
};

export default SchoolZoneCard;
