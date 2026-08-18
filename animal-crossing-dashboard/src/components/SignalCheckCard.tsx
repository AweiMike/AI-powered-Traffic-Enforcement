/**
 * SignalCheckCard - 訊號／雜訊判讀卡（各專區共用）
 *
 * 為什麼需要這張卡：
 * 系統原本只顯示「較去年 ±N%」，不說那是真變化還是隨機波動。
 * 113 年高齡事故率 130.1 曾被寫成「四年最佳」並據以追問「當年做對什麼」，
 * 事後查核為統計假象——降幅 p=0.136 不顯著、非高齡同步下降、減少量 86% 來自
 * 兩個僅占 9.8% 量體的小區且隔年全數反彈。本卡即為擋掉此類誤判而設。
 *
 * 資料來源：GET /stats/signal-check?topic=...&start_date=...&end_date=...
 * 判讀順序：① 是否被單獨惡化 → ② 可否歸因於作為 → ③ 是否達趨勢門檻
 * 三者皆通過（can_claim_effectiveness）才可對外宣稱防制成效。
 */
import React, { useEffect, useState } from 'react';
import { Activity, AlertTriangle, CheckCircle2, HelpCircle } from 'lucide-react';
import type { DateRange } from './DateRangePicker';
import { apiClient } from '../api/client';

interface MonthPoint {
  month: number;
  center: number | null;
  lcl: number | null;
  ucl: number | null;
  actual: number;
  breach: 'below' | 'above' | null;
  baseline_years?: number;
}

interface SignalCheckData {
  topic: string;
  period: { start: string; end: string };
  baseline: { start: string; end: string; note: string };
  counts: {
    topic_now: number; topic_baseline: number;
    other_now: number; other_baseline: number;
    topic_share_now: number; topic_share_baseline: number;
  };
  indicator_1_over_representation: {
    supported: boolean; now: number | null; baseline: number | null;
    alert_threshold: number; normal_band: number[];
    status: 'alert' | 'normal' | null;
    population_data_through: string | null; note: string | null;
  };
  indicator_2_control_diff: {
    topic_ratio: number | null; other_ratio: number | null;
    diff_ratio: number | null; chi2: number; p_value: number;
    significant: boolean; verdict: string;
  };
  indicator_3_control_limits: {
    months: MonthPoint[]; max_consecutive_below: number;
    insufficient_baseline: boolean; verdict: string;
  };
  can_claim_effectiveness: boolean;
  summary: string;
}

interface Props {
  range: DateRange;
  topic: string;
  title?: string;
}

/** 迷你管制圖：灰帶為管制界限，折線為實績，破界點標色 */
const MiniControlChart: React.FC<{ months: MonthPoint[] }> = ({ months }) => {
  const valid = months.filter((m) => m.center !== null);
  if (valid.length === 0) {
    return (
      <p className="text-xs text-nook-text/50 py-6 text-center">
        基準年資料不足，無法建立管制界限
      </p>
    );
  }
  const W = 320, H = 96, PAD_L = 4, PAD_B = 16;
  const maxV = Math.max(...months.map((m) => Math.max(m.actual, m.ucl ?? 0))) * 1.1 || 1;
  const stepX = (W - PAD_L * 2) / Math.max(months.length - 1, 1);
  const x = (i: number) => PAD_L + i * stepX;
  const y = (v: number) => H - PAD_B - (v / maxV) * (H - PAD_B - 6);

  const bandTop = months.map((m, i) => `${x(i)},${y(m.ucl ?? m.actual)}`).join(' ');
  const bandBot = months.slice().reverse()
    .map((m, i) => `${x(months.length - 1 - i)},${y(m.lcl ?? m.actual)}`).join(' ');

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-24" role="img"
         aria-label="月別管制圖">
      <polygon points={`${bandTop} ${bandBot}`} fill="#0369A1" opacity="0.10" />
      <polyline
        points={months.map((m, i) => `${x(i)},${y(m.actual)}`).join(' ')}
        fill="none" stroke="#D97706" strokeWidth="2"
      />
      {months.map((m, i) => (
        <g key={m.month}>
          <circle
            cx={x(i)} cy={y(m.actual)} r={m.breach ? 4 : 2.8}
            fill={m.breach === 'below' ? '#059669' : m.breach === 'above' ? '#DC2626' : '#fff'}
            stroke={m.breach ? 'none' : '#D97706'} strokeWidth="1.8"
          />
          <text x={x(i)} y={H - 4} textAnchor="middle"
                className="fill-nook-text/50" fontSize="9">{m.month}月</text>
        </g>
      ))}
    </svg>
  );
};

const Verdict: React.FC<{ ok: boolean | null; children: React.ReactNode }> =
  ({ ok, children }) => (
  <div className="flex items-start gap-2">
    {ok === null
      ? <HelpCircle className="w-4 h-4 text-nook-text/40 mt-0.5 shrink-0" />
      : ok
        ? <CheckCircle2 className="w-4 h-4 text-green-600 mt-0.5 shrink-0" />
        : <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />}
    <span className="text-xs leading-relaxed text-nook-text/70">{children}</span>
  </div>
);

const SignalCheckCard: React.FC<Props> = ({ range, topic, title = '訊號／雜訊判讀' }) => {
  const [data, setData] = useState<SignalCheckData | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setErr(null);
    apiClient
      .getSignalCheck(topic, range.startDate, range.endDate, true)
      .then((d) => { if (alive) setData(d); })
      .catch((e) => { if (alive) setErr(String(e?.message ?? e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [topic, range.startDate, range.endDate]);

  if (loading) {
    return (
      <div className="bg-white/80 rounded-2xl p-6 nook-shadow animate-pulse">
        <div className="h-5 w-40 bg-nook-text/10 rounded mb-4" />
        <div className="h-24 bg-nook-text/5 rounded" />
      </div>
    );
  }
  if (err || !data) {
    return (
      <div className="bg-white/80 rounded-2xl p-6 nook-shadow">
        <p className="text-sm text-nook-text/60">訊號判讀載入失敗：{err ?? '無資料'}</p>
      </div>
    );
  }

  const i1 = data.indicator_1_over_representation;
  const i2 = data.indicator_2_control_diff;
  const i3 = data.indicator_3_control_limits;
  const claim = data.can_claim_effectiveness;

  return (
    <div className="bg-white/80 rounded-2xl p-6 nook-shadow space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-bold text-nook-text flex items-center gap-2">
            <Activity className="w-5 h-5 text-accent" />{title}
          </h3>
          <p className="text-xs text-nook-text/50 mt-1">
            A1＋A2 傷亡口徑　·　基準期 {data.baseline.start} ~ {data.baseline.end}
            （{data.baseline.note}）
          </p>
        </div>
        <div className={`px-3 py-1.5 rounded-full text-xs font-bold whitespace-nowrap ${
          claim ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-800'}`}>
          {claim ? '可宣稱成效' : '未達宣稱門檻'}
        </div>
      </div>

      <p className="text-sm text-nook-text/70 bg-nook-text/[0.03] rounded-xl px-4 py-2.5">
        {data.summary}
      </p>

      <div className="grid grid-cols-3 gap-4">
        {/* 指標1 */}
        <div className="space-y-2">
          <p className="text-xs font-bold text-nook-text/80">① 過度代表倍數</p>
          {i1.supported ? (
            <>
              <p className="text-2xl font-bold tabular-nums tracking-tight leading-none">
                <span className={i1.status === 'alert' ? 'text-red-600' : 'text-nook-text'}>
                  {i1.now}
                </span>
                <span className="text-sm text-nook-text/40 font-medium ml-2">
                  ← {i1.baseline}
                </span>
              </p>
              <Verdict ok={i1.status !== 'alert'}>
                警戒門檻 {i1.alert_threshold}；常態帶 {i1.normal_band[0]}–{i1.normal_band[1]}。
                人口資料至 {i1.population_data_through ?? '—'}
              </Verdict>
            </>
          ) : (
            <Verdict ok={null}>{i1.note}</Verdict>
          )}
        </div>

        {/* 指標2 */}
        <div className="space-y-2">
          <p className="text-xs font-bold text-nook-text/80">② 控制組差分比</p>
          <p className="text-2xl font-bold tabular-nums tracking-tight leading-none text-nook-text">
            {i2.diff_ratio ?? '—'}
            {i2.significant && (
              <span className="text-xs text-red-600 font-bold ml-2">p={i2.p_value}</span>
            )}
          </p>
          <Verdict ok={i2.diff_ratio !== null && i2.diff_ratio <= 0.85}>
            {i2.verdict}
            <br />
            <span className="text-nook-text/45">
              本主題率比 {i2.topic_ratio ?? '—'}／其他 {i2.other_ratio ?? '—'}
            </span>
          </Verdict>
        </div>

        {/* 指標3 */}
        <div className="space-y-2">
          <p className="text-xs font-bold text-nook-text/80">③ 月別管制界限</p>
          <MiniControlChart months={i3.months} />
          <Verdict ok={i3.max_consecutive_below >= 3 && !i3.insufficient_baseline}>
            {i3.verdict}
          </Verdict>
        </div>
      </div>

      <p className="text-[11px] text-nook-text/40 leading-relaxed border-t border-nook-text/5 pt-3">
        判讀順序：① 確認是否被單獨惡化 → ② 確認可否歸因於作為 → ③ 確認是否達趨勢門檻。
        三者皆通過方可對外宣稱防制成效。
        <span className="text-amber-700">
          　基準期為事前固定之去年同期——請勿於看過數據後才挑基準期，
          以序列極值當基準會系統性膨脹顯著性。
        </span>
      </p>
    </div>
  );
};

export default SignalCheckCard;
