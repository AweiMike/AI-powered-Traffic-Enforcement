/**
 * SpecialCausesCard - 特殊致因卡（文本挖掘，各專區共用）
 *
 * 存在理由：結構化「肇因」欄位有嚴重低登錄。實測「動物竄出」85 件中，
 * 肇因欄僅 4 件（4.7%）正確歸類，45 件掛「恍神、緊張、心不在焉分心駕駛」。
 * 此類特殊致因（動物、農機、油漬、視線遮蔽、路面坑洞）平時只能靠人工翻閱摘要挖掘。
 *
 * ⚠️ 資料庫只存標籤與命中關鍵詞，不存原文——摘要含車牌／姓名／地址。
 *    需回查個案原文請至原始 EIS 檔以案件編號檢索。
 *
 * 資料來源：GET /stats/special-causes?start_date=&end_date=&topic=&casualty_only=
 */
import React, { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import type { DateRange } from './DateRangePicker';
import { apiClient } from '../api/client';

interface CauseItem {
  tag: string;
  cases: number;
  pct_of_total: number;
}

interface SpecialCausesData {
  period: { start: string; end: string };
  topic: string | null;
  casualty_only: boolean;
  total_cases: number;
  tagged_cases: number;
  coverage_pct: number;
  items: CauseItem[];
  note: string;
}

interface Props {
  range: DateRange;
  /** 不傳＝全部事故；傳 elderly/pedestrian/… 則限定該主題 */
  topic?: string;
  casualtyOnly?: boolean;
  title?: string;
}

/** 標籤配色：工程可改善者用琥珀（可提會勘），行為類用中性 */
const ENGINEERING_TAGS = new Set(['路面坑洞', '油漬路滑', '視線遮蔽']);

const SpecialCausesCard: React.FC<Props> = ({
  range, topic, casualtyOnly = true, title = '特殊致因（摘要文本挖掘）',
}) => {
  const [data, setData] = useState<SpecialCausesData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    apiClient
      .getSpecialCauses(range.startDate, range.endDate, topic, casualtyOnly)
      .then((d) => { if (alive) setData(d); })
      .catch(() => { if (alive) setData(null); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [range.startDate, range.endDate, topic, casualtyOnly]);

  if (loading) {
    return (
      <div className="bg-white/80 rounded-2xl p-6 nook-shadow animate-pulse mb-6">
        <div className="h-5 w-44 bg-nook-text/10 rounded mb-4" />
        <div className="h-20 bg-nook-text/5 rounded" />
      </div>
    );
  }
  if (!data || data.items.length === 0) {
    return (
      <div className="bg-white/80 rounded-2xl p-6 nook-shadow mb-6">
        <h3 className="font-bold text-nook-text flex items-center gap-2 mb-2">
          <Search className="w-5 h-5 text-accent" />{title}
        </h3>
        <p className="text-sm text-text-subtle">此區間之現場處理摘要未命中任何特殊致因標籤。</p>
      </div>
    );
  }

  const max = Math.max(...data.items.map((i) => i.cases), 1);

  return (
    <div className="bg-white/80 rounded-2xl nook-shadow overflow-hidden mb-6">
      <div className="p-4 border-b border-nook-cream/50 flex items-center gap-2 flex-wrap">
        <Search className="w-5 h-5 text-accent" />
        <h3 className="font-bold text-nook-text">{title}</h3>
        <span className="text-xs text-text-subtle ml-auto tabular-nums">
          標記 {data.tagged_cases} 件／共 {data.total_cases} 件（覆蓋 {data.coverage_pct}%）
        </span>
      </div>

      <div className="p-4 space-y-2">
        {data.items.map((it) => {
          const eng = ENGINEERING_TAGS.has(it.tag);
          return (
            <div key={it.tag} className="flex items-center gap-3 text-xs">
              <span className={`w-20 shrink-0 font-semibold ${eng ? 'text-warning' : 'text-text-muted'}`}>
                {it.tag}
              </span>
              <div className="h-2.5 flex-1 bg-surface-3 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${eng ? 'bg-warning' : 'bg-accent'}`}
                  style={{ width: `${(it.cases / max) * 100}%` }}
                />
              </div>
              <span className="w-24 text-right tabular-nums text-text-muted shrink-0">
                {it.cases} 件（{it.pct_of_total}%）
              </span>
            </div>
          );
        })}

        <div className="pt-3 mt-1 border-t border-nook-text/5 space-y-1.5">
          <p className="text-[11px] text-warning leading-relaxed">
            <b>琥珀色為工程可改善項目</b>（路面坑洞／油漬路滑／視線遮蔽），可作為會勘提報依據。
          </p>
          <p className="text-[11px] text-text-subtle leading-relaxed">
            ⚠️ 本卡補的是<b>結構化肇因欄的低登錄</b>——實測「動物竄出」85 件中，
            肇因欄僅 <b>4 件（4.7%）</b>正確歸類，45 件掛「恍神、緊張、心不在焉分心駕駛」。
            標籤取自現場處理摘要之規則式比對；<b>資料庫僅存標籤與命中關鍵詞，不存原文</b>，
            回查個案請至原始 EIS 檔以案件編號檢索。
          </p>
        </div>
      </div>
    </div>
  );
};

export default SpecialCausesCard;
