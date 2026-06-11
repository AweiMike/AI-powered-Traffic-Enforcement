/**
 * TrendCard - 泛用「週趨勢與專業判讀」卡（各執法主題共用）
 *
 * 資料來源：任一 `/enforcement/<topic>/trend` 端點，統一回傳：
 *   { weeks: [{label, total, primary, secondary}], trend: {...} }
 *   - primary   = 主動取締 / 取締（綠）
 *   - secondary = 肇事舉發（紅）；單序列主題（如超速）此值為 0
 *
 * 後端 trend_engine 提供 4 週移動平均 / 環比(MoM) / Z-score 異常偵測 / 專業判讀文字。
 * 視覺：Recharts ComposedChart（堆疊長條 + 移動平均線）+ 互動 tooltip。
 */
import React, { useEffect, useState } from 'react';
import {
  ResponsiveContainer, ComposedChart, Bar, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts';
import { Activity, AlertTriangle, TrendingUp, TrendingDown, Minus, ShieldCheck } from 'lucide-react';
import type { DateRange } from './DateRangePicker';

const DEFAULT = {
  primary: '#059669',   // success 綠 — 主動 / 取締
  secondary: '#DC2626', // danger 紅 — 肇事舉發
  ma: '#0369A1',        // accent 藍 — 移動平均
  grid: '#E2E8F0',
  axis: '#64748B',
};

interface TrendData {
  weeks: { week_start: string; label: string; total: number; primary: number; secondary: number }[];
  trend: {
    points: { label: string; value: number; ma: number }[];
    window: number;
    mom_pct: number | null;
    mean: number;
    std: number;
    zscore: number;
    is_anomaly: boolean;
    direction: 'up' | 'down' | 'flat';
    interpretation: string;
  };
}

interface TrendCardProps {
  range: DateRange;
  title: string;
  fetcher: (startDate: string, endDate: string) => Promise<TrendData>;
  /** 主序列名稱（綠），如「主動取締」「取締」 */
  primaryName: string;
  /** 次序列名稱（紅）；省略 = 單序列總量模式（如超速） */
  secondaryName?: string;
  metricName?: string;
  primaryColor?: string;
  secondaryColor?: string;
  emptyText?: string;
}

function MomBadge({ pct }: { pct: number | null }) {
  if (pct === null) return <span className="text-text-subtle text-xs">環比 —</span>;
  const up = pct > 0, down = pct < 0;
  const cls = up ? 'text-danger' : down ? 'text-success' : 'text-text-subtle';
  const Icon = up ? TrendingUp : down ? TrendingDown : Minus;
  return (
    <span className={`inline-flex items-center gap-1 text-sm font-bold tabular-nums ${cls}`}>
      <Icon className="w-4 h-4" />環比 {pct > 0 ? '+' : ''}{pct}%
    </span>
  );
}

const TrendCard: React.FC<TrendCardProps> = ({
  range, title, fetcher, primaryName, secondaryName,
  metricName = '件', primaryColor, secondaryColor, emptyText = '此區間尚無資料',
}) => {
  const [data, setData] = useState<TrendData | null>(null);
  const [loading, setLoading] = useState(false);
  const dual = !!secondaryName;
  const cPrimary = primaryColor || DEFAULT.primary;
  const cSecondary = secondaryColor || DEFAULT.secondary;

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const res = await fetcher(range.startDate, range.endDate);
        if (alive) setData(res);
      } catch (e) {
        console.error('Failed to fetch trend', e);
        if (alive) setData(null);
      }
      if (alive) setLoading(false);
    })();
    return () => { alive = false; };
  }, [range.startDate, range.endDate]);

  const chartData = (data?.weeks || []).map((w, i) => ({
    ...w,
    ma: data?.trend.points[i]?.ma ?? null,
  }));
  const hasData = chartData.some((d) => d.total > 0);
  const t = data?.trend;

  const Tip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    const row = payload[0]?.payload;
    return (
      <div className="bg-white rounded-lg shadow-card border border-border px-3 py-2 text-xs space-y-0.5">
        <div className="font-bold text-text mb-1">{label} 當週</div>
        {dual ? (
          <>
            <div className="flex items-center justify-between gap-6">
              <span style={{ color: cPrimary }} className="font-medium">● {primaryName}</span>
              <span className="tabular-nums">{row.primary} {metricName}</span>
            </div>
            <div className="flex items-center justify-between gap-6">
              <span style={{ color: cSecondary }} className="font-medium">● {secondaryName}</span>
              <span className="tabular-nums">{row.secondary} {metricName}</span>
            </div>
            <div className="flex items-center justify-between gap-6 border-t border-border mt-1 pt-1">
              <span className="text-text-muted">合計</span>
              <span className="tabular-nums font-bold">{row.total} {metricName}</span>
            </div>
          </>
        ) : (
          <div className="flex items-center justify-between gap-6">
            <span style={{ color: cPrimary }} className="font-medium">● {primaryName}</span>
            <span className="tabular-nums font-bold">{row.total} {metricName}</span>
          </div>
        )}
        <div className="flex items-center justify-between gap-6">
          <span className="text-accent font-medium">— 移動平均</span>
          <span className="tabular-nums">{row.ma}</span>
        </div>
      </div>
    );
  };

  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden mb-6">
      <div className="p-4 border-b border-nook-cream/50 flex items-center gap-2">
        <Activity className="w-5 h-5 text-accent" />
        <h3 className="font-bold text-nook-text">{title}</h3>
        <span className="text-xs text-text-subtle ml-2">
          {dual ? `${primaryName} vs ${secondaryName} · ` : ''}{t?.window ?? 4} 週移動平均 · 異常偵測
        </span>
      </div>

      {loading ? (
        <div className="p-6 space-y-4 animate-pulse">
          <div className="h-16 bg-surface-3 rounded-xl" />
          <div className="h-64 bg-surface-3 rounded-xl" />
        </div>
      ) : !hasData ? (
        <div className="p-12 text-center text-text-subtle">{emptyText}</div>
      ) : (
        <div className="p-4">
          {t && (
            <div className={`rounded-xl p-4 mb-4 border ${t.is_anomaly ? 'bg-danger/5 border-danger/30' : 'bg-accent-soft/40 border-accent/20'}`}>
              <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
                <div className="flex items-center gap-3">
                  <MomBadge pct={t.mom_pct} />
                  {t.is_anomaly ? (
                    <span className="inline-flex items-center gap-1 text-xs font-bold text-danger bg-danger/10 px-2 py-0.5 rounded-full">
                      <AlertTriangle className="w-3.5 h-3.5" /> 統計異常 (z={t.zscore})
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-xs font-bold text-success bg-success/10 px-2 py-0.5 rounded-full">
                      <ShieldCheck className="w-3.5 h-3.5" /> 常態波動 (z={t.zscore})
                    </span>
                  )}
                </div>
                <span className="text-xs text-text-subtle tabular-nums">
                  歷史均值 {t.mean} · 標準差 {t.std}
                </span>
              </div>
              <p className="text-sm text-text-muted leading-relaxed">{t.interpretation}</p>
            </div>
          )}

          <div style={{ width: '100%', height: 300 }}>
            <ResponsiveContainer>
              <ComposedChart data={chartData} margin={{ top: 8, right: 8, bottom: 8, left: -12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={DEFAULT.grid} vertical={false} />
                <XAxis
                  dataKey="label" interval="preserveStartEnd"
                  tick={{ fontSize: 11, fill: DEFAULT.axis }}
                  tickLine={false} axisLine={{ stroke: DEFAULT.grid }}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: DEFAULT.axis }}
                  tickLine={false} axisLine={false} allowDecimals={false} width={36}
                />
                <Tooltip content={<Tip />} cursor={{ fill: 'rgba(15,23,42,0.04)' }} />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 4 }} iconType="circle" />
                <Bar dataKey="primary" stackId="a" name={primaryName} fill={cPrimary} maxBarSize={28}
                     radius={dual ? undefined : [3, 3, 0, 0]} />
                {dual && (
                  <Bar dataKey="secondary" stackId="a" name={secondaryName} fill={cSecondary}
                       radius={[3, 3, 0, 0]} maxBarSize={28} />
                )}
                <Line
                  type="monotone" dataKey="ma" name={`${t?.window ?? 4} 週移動平均`}
                  stroke={DEFAULT.ma} strokeWidth={2.5} dot={false} activeDot={{ r: 4 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
};

export default TrendCard;
