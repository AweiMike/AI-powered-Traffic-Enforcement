/**
 * API Client - 後端 API 連接
 * 連接到 FastAPI 後端
 */

// 使用相對路徑，讓 Vite 代理轉發請求到後端
const API_BASE_URL = '';
const API_VERSION = '/api/v1';

// 主題代碼
export type TopicCode = 'DUI' | 'RED_LIGHT' | 'DANGEROUS_DRIVING';

// 年齡組
export type AgeGroup = '<18' | '18-24' | '25-44' | '45-64' | '65+' | '未知';

// 性別
export type Gender = '男' | '女' | '未知';

// ============================================
// 型別定義
// ============================================

export interface Topic {
  code: TopicCode;
  name: string;
  emoji: string;
  description: string;
  color: string;
}

export interface TopicStats {
  topic: Topic;
  period: {
    start_date: string;
    end_date: string;
    days: number;
  };
  shift_id?: string;
  tickets: {
    total: number;
    elderly: number;
    elderly_percentage: number;
  };
  crashes: {
    total: number;
    elderly: number;
  };
  demographics: {
    gender: Array<{ gender: Gender; count: number }>;
    age_groups: Array<{ age_group: AgeGroup; count: number }>;
  };
  distribution: {
    shifts: Array<{ shift_id: string; count: number }>;
    districts: Array<{ district: string; count: number }>;
  };
  note: string;
}

export interface OverviewStats {
  period: {
    start_date: string;
    end_date: string;
    days: number;
  };
  tickets: {
    total: number;
    elderly: number;
    elderly_percentage: number;
  };
  crashes: {
    total: number;
    elderly: number;
    elderly_percentage: number;
  };
  topics: {
    dui: number;
    red_light: number;
    dangerous_driving: number;
  };
  note: string;
}

export interface MonthlyStats {
  period: {
    year: number;
    month: number;
  };
  current: {
    tickets: number;
    crashes: number;
    topics: {
      dui: number;
      red_light: number;
      dangerous_driving: number;
    };
    severity?: {
      a1: number;
      a2: number;
      a3: number;
    };
  };
  last_year: {
    year: number;
    tickets: number;
    crashes: number;
    topics: {
      dui: number;
      red_light: number;
      dangerous_driving: number;
    };
    severity?: {
      a1: number;
      a2: number;
      a3: number;
    };
  };
  comparison: {
    tickets_change: number;
    crashes_change: number;
    tickets_trend: '上升' | '下降' | '持平';
    crashes_trend: '上升' | '下降' | '持平';
  };
  note: string;
}

export interface SiteRecommendation {
  rank: number;
  site_id: number;
  site_name: string;
  district: string;
  location_desc: string;
  coordinates?: {
    latitude: number;
    longitude: number;
  };
  metrics: {
    vpi: number;
    cri: number;
    score: number;
  };
  statistics: {
    tickets: number;
    crashes: number;
    violation_days: number;
    avg_tickets_per_day: number;
  };
}

export interface Top5Response {
  topic_code: TopicCode;
  shift_id?: string;
  period: {
    start_date: string;
    end_date: string;
    days: number;
  };
  recommendations: SiteRecommendation[];
  total_sites_analyzed: number;
  methodology: {
    vpi: string;
    cri: string;
    score: string;
  };
  note: string;
}

export interface ShiftStats {
  shift_id: string;
  shift_number: number;
  time_range: string;
  tickets: number;
  crashes: number;
  topics: {
    dui: number;
    red_light: number;
    dangerous_driving: number;
  };
  elderly: number;
}

export interface BriefingCard {
  date: string;
  shift: {
    shift_id: string;
    shift_number: number;
    time_range: string;
  };
  topic: {
    code: TopicCode;
    name: string;
    emoji: string;
    focus: string;
  };
  top5_sites: SiteRecommendation[];
  statistics: {
    period_days: number;
    total_sites: number;
  };
  notes: string[];
  generated_at: string;
  privacy_note: string;
}

export interface ViolationStats {
  period: {
    start_date: string;
    end_date: string;
    days: number;
  };
  total_tickets: number;
  districts: Array<{
    district: string;
    count: number;
    percentage: number;
  }>;
  top_violations: Array<{
    code: string;
    name: string;
    count: number;
  }>;
  topics: {
    dui: number;
    red_light: number;
    dangerous_driving: number;
    others: number;
  };
}

export interface HeatmapPoint {
  latitude: number;
  longitude: number;
  intensity: number;
  site_name: string;
  district: string;
}

export interface HeatmapResponse {
  topic_code: TopicCode | null;
  shift_id: string | null;
  period: {
    start_date: string;
    end_date: string;
    days: number;
  };
  points: HeatmapPoint[];
  total_points: number;
  note: string;
}

// ============================================
// 事故分析型別
// ============================================

export interface AccidentHotspot {
  district: string;
  latitude: number;
  longitude: number;
  accidents: {
    total: number;
    a1_count: number;
    a2_count: number;
    a3_count: number;
    severity_score: number;
  };
  violations: {
    total: number;
    dui: number;
    red_light: number;
    dangerous_driving: number;
  };
  recommendation: {
    priority_topic: TopicCode | null;
    enforcement_focus: string;
  };
}

export interface AccidentHotspotsResponse {
  period: {
    start_date: string;
    end_date: string;
    days: number;
  };
  hotspots: AccidentHotspot[];
  total_districts: number;
  summary: {
    total_accidents: number;
    a1_total: number;
    a2_total: number;
    a3_total: number;
    dui_crash_total?: number;
    total_dui_violations?: number;
  };
  note: string;
}

export interface ShiftData {
  shift_id: string;
  time_range: string;
  accidents: number;
  accident_severity: number;
  violations: number;
  combined_score: number;
  dui_citations?: number;
}

export interface PeakTimesResponse {
  district: string;
  period: {
    start_date: string;
    end_date: string;
    days: number;
  };
  shifts: ShiftData[];
  analysis: {
    total_accidents: number;
    total_violations: number;
    peak_accident_shift: string | null;
    peak_violation_shift: string | null;
  };
  recommendations: {
    priority_shifts: string[];
    enforcement_suggestion: string;
    rationale: string;
  };
  note: string;
}

export interface AccidentHeatmapPoint {
  district: string;
  latitude: number;
  longitude: number;
  intensity: number;
  severity_score: number;
  breakdown: {
    a1: number;
    a2: number;
    a3: number;
  };
  site_name: string;
}

export interface AccidentHeatmapResponse {
  shift_id: string | null;
  period: {
    start_date: string;
    end_date: string;
    days: number;
  };
  points: AccidentHeatmapPoint[];
  total_points: number;
  total_accidents: number;
  note: string;
}

export interface CrossAnalysisItem {
  district: string;
  shift_id: string;
  time_range: string;
  accidents: number;
  severity_score: number;
  violations: number;
  enforcement_gap: number;
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
}

export interface CrossAnalysisResponse {
  district_filter: string | null;
  period: {
    start_date: string;
    end_date: string;
    days: number;
  };
  cross_analysis: CrossAnalysisItem[];
  summary: {
    total_combinations: number;
    high_priority_count: number;
    medium_priority_count: number;
    low_priority_count: number;
  };
  recommendations: {
    high_priority_targets: CrossAnalysisItem[];
    suggestion: string;
  };
  note: string;
}


// ============================================
// API Client Class
// ============================================

class APIClient {

  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${API_VERSION}${endpoint}`;

    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('API Request Failed:', error);
      throw error;
    }
  }

  // ============================================
  // Topics API
  // ============================================

  async getTopics(): Promise<{ topics: Topic[]; total: number }> {
    return this.request('/topics');
  }

  async getTopicStats(
    topicCode: TopicCode,
    shiftId?: string,
    days: number = 30
  ): Promise<TopicStats> {
    const params = new URLSearchParams({ days: days.toString() });
    if (shiftId) params.append('shift_id', shiftId);

    return this.request(`/topics/${topicCode}/stats?${params}`);
  }

  async getTopicTrends(
    topicCode: TopicCode,
    months: number = 12
  ): Promise<any> {
    return this.request(`/topics/${topicCode}/trends?months=${months}`);
  }

  // ============================================
  // Stats API
  // ============================================

  async getOverview(days: number = 30): Promise<OverviewStats> {
    return this.request(`/stats/overview?days=${days}`);
  }

  async getMonthlyStats(year: number, month: number): Promise<MonthlyStats> {
    return this.request(`/stats/monthly?year=${year}&month=${month}`);
  }

  async getElderlyStats(days: number = 30): Promise<any> {
    return this.request(`/stats/elderly?days=${days}`);
  }

  async getShiftAnalysis(days: number = 30): Promise<{
    period: any;
    shifts: ShiftStats[];
    note: string;
  }> {
    return this.request(`/stats/shifts?days=${days}`);
  }

  async getViolationStats(days: number = 30): Promise<ViolationStats> {
    return this.request(`/stats/violations?days=${days}`);
  }

  // ============================================
  // Recommendations API
  // ============================================

  async getTop5(
    topicCode: TopicCode,
    shiftId?: string,
    days: number = 30
  ): Promise<Top5Response> {
    const params = new URLSearchParams({
      topic_code: topicCode,
      days: days.toString(),
    });
    if (shiftId) params.append('shift_id', shiftId);

    return this.request(`/recommendations/top5?${params}`);
  }

  async getHeatmapData(
    topicCode?: TopicCode,
    shiftId?: string,
    days: number = 30
  ): Promise<HeatmapResponse> {
    const params = new URLSearchParams({ days: days.toString() });
    if (topicCode) params.append('topic_code', topicCode);
    if (shiftId) params.append('shift_id', shiftId);

    return this.request(`/recommendations/heatmap?${params}`);
  }

  async getBriefingCard(
    topicCode: TopicCode,
    shiftId: string,
    date?: string
  ): Promise<BriefingCard> {
    const params = new URLSearchParams({
      topic_code: topicCode,
      shift_id: shiftId,
    });
    if (date) params.append('date', date);

    return this.request(`/recommendations/briefing-card?${params}`);
  }

  // ============================================
  // Accident Analysis API (事故分析)
  // ============================================

  async getAccidentHotspots(days: number = 30, isElderly: boolean = false): Promise<AccidentHotspotsResponse> {
    const params = new URLSearchParams({ days: days.toString() });
    if (isElderly) params.append('is_elderly', 'true');
    return this.request(`/recommendations/accidents/hotspots?${params}`);
  }

  async getAccidentPeakTimes(district: string, days: number = 30, isElderly: boolean = false): Promise<PeakTimesResponse> {
    const params = new URLSearchParams({ days: days.toString() });
    if (isElderly) params.append('is_elderly', 'true');
    return this.request(`/recommendations/accidents/peak-times/${encodeURIComponent(district)}?${params}`);
  }

  async getAccidentHeatmap(shiftId?: string, days: number = 30): Promise<AccidentHeatmapResponse> {
    const params = new URLSearchParams({ days: days.toString() });
    if (shiftId) params.append('shift_id', shiftId);
    return this.request(`/recommendations/heatmap/accidents?${params}`);
  }

  async getCrossAnalysis(district?: string, days: number = 30): Promise<CrossAnalysisResponse> {
    const params = new URLSearchParams({ days: days.toString() });
    if (district) params.append('district', district);
    return this.request(`/recommendations/cross-analysis?${params}`);
  }

  // ============================================
  // System Admin API
  // ============================================

  async resetDatabase(): Promise<{ status: string; message: string }> {
    return this.request('/admin/reset-database', {
      method: 'POST',
    });
  }

  // ============================================
  // Advanced Analysis API (進階分析)
  // ============================================

  async getElderlyVehicleAnalysis(days: number = 365): Promise<any> {
    return this.request(`/recommendations/analysis/elderly-vehicle-types?days=${days}`);
  }

  async getDuiEnvironmentAnalysis(days: number = 365): Promise<any> {
    return this.request(`/recommendations/analysis/dui-environment?days=${days}`);
  }

  // ============================================
  // Map Data API (地圖資料)
  // ============================================

  async getMapPoints(days: number = 90, pointType: string = 'all', severity?: string, topic?: string): Promise<any> {
    const params = new URLSearchParams({ days: days.toString(), point_type: pointType });
    if (severity) params.append('severity', severity);
    if (topic) params.append('topic', topic);
    return this.request(`/recommendations/map/points?${params}`);
  }

  async getPreciseHeatmapData(days: number = 90, dataType: string = 'crash'): Promise<any> {
    return this.request(`/recommendations/map/heatmap-data?days=${days}&data_type=${dataType}`);
  }

  async updateCrashCoordinates(crashId: number, lat: number, lng: number): Promise<any> {
    return this.request(`/recommendations/map/crash/${crashId}/coordinates?latitude=${lat}&longitude=${lng}`, {
      method: 'PUT'
    });
  }

  async batchUpdateCrashCoordinates(updates: Array<{ id: number, lat: number, lng: number }>): Promise<any> {
    return this.request('/recommendations/map/crashes/coordinates/batch', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    });
  }

  // ============================================
  // Hotspot Analysis API
  // ============================================

  async getAccidentHotspotsRanking(
    days: number = 30,
    topN: number = 10,
    severity?: string,
    compareBaseline: boolean = true
  ): Promise<any> {
    const params = new URLSearchParams({
      days: days.toString(),
      top_n: topN.toString(),
      compare_baseline: compareBaseline.toString()
    });
    if (severity) params.append('severity', severity);
    return this.request(`/hotspots/accident-hotspots?${params}`);
  }

  async getTicketHotspots(
    days: number = 30,
    topN: number = 10,
    topic?: string
  ): Promise<any> {
    const params = new URLSearchParams({
      days: days.toString(),
      top_n: topN.toString()
    });
    if (topic) params.append('topic', topic);
    return this.request(`/hotspots/ticket-hotspots?${params}`);
  }

  async getHotspotOverlap(
    days: number = 30,
    topN: number = 10
  ): Promise<any> {
    return this.request(`/hotspots/hotspot-overlap?days=${days}&top_n=${topN}`);
  }

  // ============================================
  // System API (root-level, no /api/v1 prefix)
  // ============================================


  async getSystemInfo(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/`);
    if (!response.ok) throw new Error(`API Error: ${response.status}`);
    return response.json();
  }

  async healthCheck(): Promise<any> {
    // /health 會被 Vite 代理轉發到後端
    const response = await fetch(`${this.baseUrl}/health`);
    if (!response.ok) throw new Error(`API Error: ${response.status}`);
    return response.json();
  }
}

// Export singleton instance
export const apiClient = new APIClient();

// Export class for testing
export { APIClient };
