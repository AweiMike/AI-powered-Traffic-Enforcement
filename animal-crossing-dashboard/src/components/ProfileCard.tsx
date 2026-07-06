/**
 * ProfileCard - 泛用「當事者特徵剖析」卡（各執法/事故防制專區共用）
 *
 * 資料來源：GET /recommendations/profile?topic=...&start_date=...&end_date=...
 * 回傳 { topic, period, total, groups: { age_groups[6固定], gender[3固定], party_types[top8],
 *        crash_types[top8], protective_gear[], license_status[], by_shift[12], top_routes[top5] } }
 *
 * 版面：單一卡片內兩欄網格呈現六個小區塊（各為小標 + 水平 bar 列表），
 * 底部再接 12 班別迷你直條圖與 top_routes chips。
 * 保護裝備／駕照狀態兩區塊對「未戴/未繫/無照」等宣導重點項目做紅字醒目處理。
 */
import React, { useEffect, useState } from 'react';
import { Users2 } from 'lucide-react';
import type { DateRange } from './DateRangePicker';

interface ProfileGroupItem {
  name: string;
  count: number;
}

interface CrashProfileData {
  topic: string;
  period: { start_date: string; end_date: string };
  total: number;
  groups: {
    age_groups: ProfileGroupItem[];
    gender: ProfileGroupItem[];
    party_types: ProfileGroupItem[];
    crash_types: ProfileGroupItem[];
    protective_gear: ProfileGroupItem[];
    license_status: ProfileGroupItem[];
    by_shift: ProfileGroupItem[];
    top_routes: ProfileGroupItem[];
  };
}

interface ProfileCardProps {
  range: DateRange;
  topic: string;
  title?: string;
}

/** 宣導重點關鍵字：命中時該列改用危險配色（紅字 + 紅色 bar） */
function isWarningItem(name: string): boolean {
  return name.includes('未戴') || name.includes('未繫') || name.includes('無照');
}

/** 水平 bar 列表區塊：小標 + 每列 name / bar / count */
function BarListSection({ title, items, warnHighlight = false }: {
  title: string;
  items: ProfileGroupItem[];
  /** 是否對命中「未戴/未繫/無照」關鍵字的列做紅色醒目處理 */
  warnHighlight?: boolean;
}) {
  const max = Math.max(1, ...items.map((it) => it.count));
  return (
    <div>
      <h4 className="text-sm font-bold text-nook-text mb-2">{title}</h4>
      {items.length === 0 ? (
        <p className="text-xs text-text-subtle">無資料</p>
      ) : (
        <div className="space-y-1.5">
          {items.map((it) => {
            const warn = warnHighlight && isWarningItem(it.name);
            const widthPct = (it.count / max) * 100;
            return (
              <div key={it.name} className="flex items-center gap-2 text-xs">
                <span className={`w-20 shrink-0 truncate ${warn ? 'text-danger font-semibold' : 'text-text-muted'}`} title={it.name}>
                  {it.name}
                </span>
                <div className="h-2 flex-1 bg-surface-3 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${warn ? 'bg-danger' : 'bg-accent'}`}
                    style={{ width: `${widthPct}%` }}
                  />
                </div>
                <span className="w-8 shrink-0 text-right font-semibold tabular-nums text-nook-text">{it.count}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** 12 班別迷你直條圖：每 3 班標一次時間刻度（00/06/12/18） */
function ShiftMiniBars({ items }: { items: ProfileGroupItem[] }) {
  const max = Math.max(1, ...items.map((it) => it.count));
  const hourLabels = ['00', '', '', '06', '', '', '12', '', '', '18', '', ''];
  return (
    <div>
      <h4 className="text-sm font-bold text-nook-text mb-2">班別分布</h4>
      {items.length === 0 ? (
        <p className="text-xs text-text-subtle">無資料</p>
      ) : (
        <div className="flex items-end gap-1.5 h-10">
          {items.map((it, i) => {
            const heightPct = (it.count / max) * 100;
            return (
              <div key={it.name} className="flex-1 flex flex-col items-center justify-end h-full gap-0.5">
                <div
                  className="w-full bg-accent rounded-t-sm"
                  style={{ height: `${Math.max(2, heightPct)}%` }}
                  title={`${it.name}：${it.count} 件`}
                />
                <span className="text-[9px] text-text-subtle tabular-nums leading-none">
                  {hourLabels[i] ?? ''}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

const ProfileCard: React.FC<ProfileCardProps> = ({ range, topic, title = '當事者特徵剖析' }) => {
  const [data, setData] = useState<CrashProfileData | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      setFailed(false);
      try {
        // 動態 import 避免與呼叫端形成循環相依（apiClient 型別已足夠寬鬆）
        const { apiClient } = await import('../api/client');
        const res = await apiClient.getCrashProfile(topic, range.startDate, range.endDate);
        if (alive) setData(res);
      } catch (e) {
        console.error('Failed to fetch crash profile', e);
        if (alive) setFailed(true);
      }
      if (alive) setLoading(false);
    })();
    return () => { alive = false; };
  }, [range.startDate, range.endDate, topic]);

  // fetch 失敗 → 整卡隱藏
  if (failed) return null;

  if (loading) {
    return (
      <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden mb-6">
        <div className="p-4 border-b border-nook-cream/50 flex items-center gap-2">
          <Users2 className="w-5 h-5 text-accent" />
          <h3 className="font-bold text-nook-text">{title}</h3>
        </div>
        <div className="p-6 space-y-4 animate-pulse">
          <div className="h-24 bg-surface-3 rounded-xl" />
          <div className="h-24 bg-surface-3 rounded-xl" />
        </div>
      </div>
    );
  }

  if (!data) return null;

  const g = data.groups || ({} as CrashProfileData['groups']);
  const ageGroups = g.age_groups ?? [];
  const gender = g.gender ?? [];
  const partyTypes = (g.party_types ?? []).slice(0, 6);
  const crashTypes = (g.crash_types ?? []).slice(0, 6);
  const protectiveGear = (g.protective_gear ?? []).slice(0, 6);
  const licenseStatus = (g.license_status ?? []).slice(0, 6);
  const byShift = g.by_shift ?? [];
  const topRoutes = g.top_routes ?? [];

  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden mb-6">
      <div className="p-4 border-b border-nook-cream/50 flex items-center gap-2">
        <Users2 className="w-5 h-5 text-accent" />
        <h3 className="font-bold text-nook-text">{title}</h3>
        <span className="text-xs text-text-subtle ml-auto tabular-nums">共 {data.total} 件</span>
      </div>

      {data.total === 0 ? (
        <div className="p-12 text-center text-text-subtle">此區間無符合案件</div>
      ) : (
        <div className="p-4 space-y-4">
          <div className="grid grid-cols-2 gap-x-8 gap-y-4">
            <BarListSection title="年齡層" items={ageGroups} />
            <BarListSection title="性別" items={gender} />
            <BarListSection title="車種/當事者" items={partyTypes} />
            <BarListSection title="事故型態" items={crashTypes} />
            <BarListSection title="保護裝備" items={protectiveGear} warnHighlight />
            <BarListSection title="駕照狀態" items={licenseStatus} warnHighlight />
          </div>

          <div className="pt-2 border-t border-nook-cream/50">
            <ShiftMiniBars items={byShift} />
          </div>

          {topRoutes.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-nook-cream/50">
              <span className="text-xs text-text-subtle">主要路線：</span>
              {topRoutes.map((r) => (
                <span
                  key={r.name}
                  className="inline-flex items-center gap-1 text-xs bg-surface-2 text-text-muted px-2 py-0.5 rounded-full"
                >
                  {r.name} <span className="font-semibold tabular-nums">×{r.count}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ProfileCard;
