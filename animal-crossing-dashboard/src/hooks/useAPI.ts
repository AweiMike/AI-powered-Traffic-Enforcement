/**
 * React Hooks for API
 * 提供便捷的 React Hooks 來使用 API
 */

import { useState, useEffect, useCallback } from 'react';
import {
  apiClient,
  TopicCode,
  OverviewStats,
  TopicStats,
  MonthlyStats,
  Top5Response,
  ShiftStats,
  BriefingCard,
  ViolationStats,
  HeatmapResponse,
  AccidentHotspotsResponse,
  PeakTimesResponse,
  AccidentHeatmapResponse,
  CrossAnalysisResponse
} from '../api/client';

// ============================================
// Generic API Hook
// ============================================

interface UseAPIState<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

function useAPI<T>(
  fetcher: () => Promise<T>,
  deps: any[] = []
): UseAPIState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await fetcher();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
    } finally {
      setLoading(false);
    }
  }, [fetcher]);

  useEffect(() => {
    fetchData();
  }, deps);

  return { data, loading, error, refetch: fetchData };
}

// ============================================
// Specific Hooks
// ============================================

/**
 * 取得總覽統計
 */
export function useOverview(days: number = 30): UseAPIState<OverviewStats> {
  return useAPI(
    () => apiClient.getOverview(days),
    [days]
  );
}

/**
 * 取得主題統計
 */
export function useTopicStats(
  topicCode: TopicCode,
  shiftId?: string,
  days: number = 30
): UseAPIState<TopicStats> {
  return useAPI(
    () => apiClient.getTopicStats(topicCode, shiftId, days),
    [topicCode, shiftId, days]
  );
}

/**
 * 取得月度統計（含去年同期比較）
 */
export function useMonthlyStats(
  year: number,
  month: number
): UseAPIState<MonthlyStats> {
  return useAPI(
    () => apiClient.getMonthlyStats(year, month),
    [year, month]
  );
}

/**
 * 取得 Top 5 推薦
 */
export function useTop5(
  topicCode: TopicCode,
  shiftId?: string,
  days: number = 30
): UseAPIState<Top5Response> {
  return useAPI(
    () => apiClient.getTop5(topicCode, shiftId, days),
    [topicCode, shiftId, days]
  );
}

/**
 * 取得班別分析
 */
export function useShiftAnalysis(days: number = 30): UseAPIState<{
  period: any;
  shifts: ShiftStats[];
  note: string;
}> {
  return useAPI(
    () => apiClient.getShiftAnalysis(days),
    [days]
  );
}

/**
 * 取得班前勤務建議卡
 */
export function useBriefingCard(
  topicCode: TopicCode,
  shiftId: string,
  date?: string
): UseAPIState<BriefingCard> {
  return useAPI(
    () => apiClient.getBriefingCard(topicCode, shiftId, date),
    [topicCode, shiftId, date]
  );
}

/**
 * 取得高齡者統計
 */
export function useElderlyStats(days: number = 30): UseAPIState<any> {
  return useAPI(
    () => apiClient.getElderlyStats(days),
    [days]
  );
}

/**
 * 取得主題列表
 */
export function useTopics(): UseAPIState<{ topics: any[]; total: number }> {
  return useAPI(
    () => apiClient.getTopics(),
    []
  );
}

/**
 * 取得主題趨勢
 */
export function useTopicTrends(
  topicCode: TopicCode,
  months: number = 12
): UseAPIState<any> {
  return useAPI(
    () => apiClient.getTopicTrends(topicCode, months),
    [topicCode, months]
  );
}

/**
 * 取得熱力圖資料
 */
export function useHeatmap(
  topicCode?: TopicCode,
  shiftId?: string,
  days: number = 30
): UseAPIState<HeatmapResponse> {
  return useAPI(
    () => apiClient.getHeatmapData(topicCode, shiftId, days),
    [topicCode, shiftId, days]
  );
}

/**
 * 取得違規分析統計
 */
export function useViolationStats(days: number = 30): UseAPIState<ViolationStats> {
  return useAPI(
    () => apiClient.getViolationStats(days),
    [days]
  );
}

/**
 * 系統健康檢查
 */
export function useHealthCheck(): UseAPIState<any> {
  return useAPI(
    () => apiClient.healthCheck(),
    []
  );
}

// ============================================
// 事故分析 Hooks
// ============================================

/**
 * 取得事故熱點分析
 */
export function useAccidentHotspots(days: number = 30): UseAPIState<AccidentHotspotsResponse> {
  return useAPI(
    () => apiClient.getAccidentHotspots(days),
    [days]
  );
}

/**
 * 取得特定區域的時段分析
 */
export function useAccidentPeakTimes(
  district: string,
  days: number = 30
): UseAPIState<PeakTimesResponse> {
  return useAPI(
    () => apiClient.getAccidentPeakTimes(district, days),
    [district, days]
  );
}

/**
 * 取得事故熱力圖資料
 */
export function useAccidentHeatmap(
  shiftId?: string,
  days: number = 30
): UseAPIState<AccidentHeatmapResponse> {
  return useAPI(
    () => apiClient.getAccidentHeatmap(shiftId, days),
    [shiftId, days]
  );
}

/**
 * 取得事故與違規交叉分析
 */
export function useCrossAnalysis(
  district?: string,
  days: number = 30
): UseAPIState<CrossAnalysisResponse> {
  return useAPI(
    () => apiClient.getCrossAnalysis(district, days),
    [district, days]
  );
}

