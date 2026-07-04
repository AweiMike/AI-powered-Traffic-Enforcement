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
    /** 事故當量（Equivalent Property Damage Only）— 依嚴重度加權的事故能量指標 */
    epdo: number;
    /** 去年同期 EPDO，供卡片對照 */
    epdo_last_year: number;
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
    enforcement?: Record<string, number>;
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
    enforcement?: Record<string, number>;
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
    death_count?: number;
    injury_count?: number;
  };
  violations: {
    total: number;
    dui: number;
    dui_no_crash?: number;
    red_light: number;
    dangerous_driving: number;
  };
  /** DUI 專屬統計（資料來源：Ticket.enforcement_subtype，比 Crash.suspected_alcohol 可靠） */
  dui_stats?: {
    total_dui: number;
    dui_with_crash: number;
    dui_no_crash: number;
    dui_crash_source?: string;
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
    death_total?: number;
    injury_total?: number;
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
  /** 含肇事的酒駕舉發數（攔舉-肇事 子類）— 真實酒駕肇事的可靠指標 */
  dui_crash_citations?: number;
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

/** 登入 token 的 sessionStorage key（App.tsx useAuth 寫入、此處自動帶上） */
const AUTH_TOKEN_KEY = 'dashboard_auth';

class APIClient {

  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${API_VERSION}${endpoint}`;
    const token = sessionStorage.getItem(AUTH_TOKEN_KEY);

    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          // 寫入型 API 需要登入憑證（後端 write-protect middleware 驗證）
          ...(token ? { 'X-Auth-Token': token } : {}),
          ...options?.headers,
        },
      });

      if (!response.ok) {
        // 嘗試從 response body 中提取 FastAPI 的 detail 訊息（包含給 user 的具體錯誤）
        let detail = `${response.status} ${response.statusText}`;
        try {
          const errorBody = await response.json();
          if (errorBody?.detail) {
            detail = typeof errorBody.detail === 'string' ? errorBody.detail : JSON.stringify(errorBody.detail);
          }
        } catch {
          // body 不是 JSON，保留原始 status
        }
        const err = new Error(detail) as any;
        err.detail = detail;
        err.status = response.status;
        throw err;
      }

      return await response.json();
    } catch (error) {
      console.error('API Request Failed:', error);
      throw error;
    }
  }

  // ============================================
  // Auth API（登入驗證 — 帳密由後端驗證，不再存在前端）
  // ============================================

  async login(username: string, password: string): Promise<{ success: boolean; token: string }> {
    return this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
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
    days: number = 30,
    startDate?: string,
    endDate?: string,
  ): Promise<TopicStats> {
    const params = new URLSearchParams({ days: days.toString() });
    if (shiftId) params.append('shift_id', shiftId);
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);

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

  async getOverview(days: number = 30, startDate?: string, endDate?: string): Promise<OverviewStats> {
    const params = new URLSearchParams({ days: days.toString() });
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    return this.request(`/stats/overview?${params}`);
  }

  async getMonthlyStats(year: number, month: number): Promise<MonthlyStats> {
    return this.request(`/stats/monthly?year=${year}&month=${month}`);
  }

  async getMonthlyStatsByRange(startDate: string, endDate: string): Promise<MonthlyStats> {
    return this.request(`/stats/monthly?start_date=${startDate}&end_date=${endDate}`);
  }

  async getDataInfo(): Promise<{
    crash: { earliest: string | null; latest: string | null; count: number; last_upload: string | null };
    ticket: { earliest: string | null; latest: string | null; count: number; last_upload: string | null };
    last_upload: string | null;
  }> {
    return this.request('/stats/data-info');
  }

  async getA1AccidentList(startDate?: string, endDate?: string): Promise<{
    period: { start: string; end: string };
    total: number;
    items: Array<{
      date: string;
      time: string | null;
      district: string;
      location: string;
      cause: string;
      party_type: string;
      death_count: number;
      injury_count: number;
      is_elderly: boolean;
      precinct: string;
      latitude: number | null;
      longitude: number | null;
    }>;
  }> {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    return this.request(`/hotspots/a1-accident-list?${params}`);
  }

  async getElderlyStats(days: number = 30, startDate?: string, endDate?: string): Promise<any> {
    const params = new URLSearchParams({ days: days.toString() });
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    return this.request(`/stats/elderly?${params}`);
  }

  async getShiftAnalysis(days: number = 30, startDate?: string, endDate?: string): Promise<{
    period: any;
    shifts: ShiftStats[];
    note: string;
  }> {
    const params = new URLSearchParams({ days: days.toString() });
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    return this.request(`/stats/shifts?${params}`);
  }

  async getViolationStats(days: number = 30, startDate?: string, endDate?: string): Promise<ViolationStats> {
    const params = new URLSearchParams({ days: days.toString() });
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    return this.request(`/stats/violations?${params}`);
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

  async getAccidentHotspots(days: number = 30, isElderly: boolean = false, startDate?: string, endDate?: string): Promise<AccidentHotspotsResponse> {
    const params = new URLSearchParams({ days: days.toString() });
    if (isElderly) params.append('is_elderly', 'true');
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    return this.request(`/recommendations/accidents/hotspots?${params}`);
  }

  async getAccidentPeakTimes(district: string, days: number = 30, isElderly: boolean = false, startDate?: string, endDate?: string): Promise<PeakTimesResponse> {
    const params = new URLSearchParams({ days: days.toString() });
    if (isElderly) params.append('is_elderly', 'true');
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    return this.request(`/recommendations/accidents/peak-times/${encodeURIComponent(district)}?${params}`);
  }

  async getAccidentHeatmap(shiftId?: string, days: number = 30): Promise<AccidentHeatmapResponse> {
    const params = new URLSearchParams({ days: days.toString() });
    if (shiftId) params.append('shift_id', shiftId);
    return this.request(`/recommendations/heatmap/accidents?${params}`);
  }

  async getCrossAnalysis(district?: string, days: number = 30, startDate?: string, endDate?: string): Promise<CrossAnalysisResponse> {
    const params = new URLSearchParams({ days: days.toString() });
    if (district) params.append('district', district);
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
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

  async getElderlyVehicleAnalysis(days: number = 365, startDate?: string, endDate?: string): Promise<any> {
    const params = new URLSearchParams({ days: days.toString() });
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    return this.request(`/recommendations/analysis/elderly-vehicle-types?${params}`);
  }

  async getDuiEnvironmentAnalysis(days: number = 365): Promise<any> {
    return this.request(`/recommendations/analysis/dui-environment?days=${days}`);
  }

  // ============================================
  // Map Data API (地圖資料)
  // ============================================

  async getMapPoints(
    days: number = 90,
    pointType: string = 'all',
    severity?: string,
    topic?: string,
    startDate?: string,
    endDate?: string,
    units?: string,
  ): Promise<any> {
    const params = new URLSearchParams({ days: days.toString(), point_type: pointType });
    if (severity) params.append('severity', severity);
    if (topic) params.append('topic', topic);
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (units) params.append('units', units);
    return this.request(`/recommendations/map/points?${params}`);
  }

  async getMapUnits(querySuffix: string = ''): Promise<{
    units: string[];
    units_with_count?: Array<{ unit: string; crash_count: number; ticket_count: number; total: number }>;
  }> {
    return this.request(`/recommendations/map/units${querySuffix}`);
  }

  async getPreciseHeatmapData(days: number = 90, dataType: string = 'crash'): Promise<any> {
    return this.request(`/recommendations/map/heatmap-data?days=${days}&data_type=${dataType}`);
  }

  async updateCrashCoordinates(crashId: number, lat: number, lng: number): Promise<any> {
    return this.request(`/recommendations/map/crash/${crashId}/coordinates?latitude=${lat}&longitude=${lng}`, {
      method: 'PUT'
    });
  }

  async updateTicketCoordinates(ticketId: number, lat: number, lng: number): Promise<any> {
    return this.request(`/recommendations/map/ticket/${ticketId}/coordinates?latitude=${lat}&longitude=${lng}`, {
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
    options: {
      days?: number;
      year?: number;
      month?: number;
      startDate?: string;
      endDate?: string;
      topN?: number;
      severity?: string;
      compareBaseline?: boolean;
    } = {}
  ): Promise<any> {
    const { days = 30, year, month, startDate, endDate, topN = 10, severity, compareBaseline = true } = options;
    const params = new URLSearchParams({
      top_n: topN.toString(),
      compare_baseline: compareBaseline.toString()
    });

    // 優先 startDate/endDate > year/month > days
    if (startDate && endDate) {
      params.append('start_date', startDate);
      params.append('end_date', endDate);
    } else if (year && month) {
      params.append('year', year.toString());
      params.append('month', month.toString());
    } else {
      params.append('days', days.toString());
    }

    if (severity) params.append('severity', severity);
    return this.request(`/hotspots/accident-hotspots?${params}`);
  }

  async getTicketHotspots(
    days: number = 30,
    topN: number = 10,
    topic?: string,
    year?: number,
    month?: number,
    startDate?: string,
    endDate?: string
  ): Promise<any> {
    const params = new URLSearchParams({
      top_n: topN.toString()
    });

    // 優先 startDate/endDate > year/month > days
    if (startDate && endDate) {
      params.append('start_date', startDate);
      params.append('end_date', endDate);
    } else if (year && month) {
      params.append('year', year.toString());
      params.append('month', month.toString());
    } else {
      params.append('days', days.toString());
    }

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

  // ============================================
  // AI Report API
  // ============================================

  /**
   * 生成 AI 報告（支援兩種期間模式）
   * - 完整月份：傳 year + month
   * - 自訂區間：傳 startDate + endDate（YYYY-MM-DD）
   */
  async generateAIReport(
    options: {
      year?: number;
      month?: number;
      startDate?: string;
      endDate?: string;
      apiKey?: string;
      provider?: string;
      model?: string;
    },
  ): Promise<ReportResponse> {
    const { year, month, startDate, endDate, apiKey, provider = 'openai', model } = options;

    const headers: Record<string, string> = {};
    if (apiKey) {
      headers['X-LLM-API-KEY'] = apiKey;
      headers['X-LLM-PROVIDER'] = provider;
      if (model) {
        headers['X-LLM-MODEL'] = model;
      }
    }

    const params = new URLSearchParams();
    if (startDate && endDate) {
      params.append('start_date', startDate);
      params.append('end_date', endDate);
    } else if (year && month) {
      params.append('year', year.toString());
      params.append('month', month.toString());
    } else {
      throw new Error('必須提供 year+month 或 startDate+endDate');
    }

    return this.request(`/report/generate?${params}`, {
      method: 'POST',
      headers,
    });
  }

  // ============================================
  // Enforcement Performance API (執法績效統計)
  // ============================================

  async getDuiPerformance(startDate: string, endDate: string): Promise<any> {
    return this.request(`/enforcement/dui?start_date=${startDate}&end_date=${endDate}`);
  }

  /** 酒駕週趨勢：移動平均 / 環比 / 異常偵測 + 專業判讀 */
  async getDuiTrend(startDate: string, endDate: string): Promise<any> {
    return this.request(`/enforcement/dui/trend?start_date=${startDate}&end_date=${endDate}`);
  }

  /** 毒駕週趨勢 */
  async getDrugTrend(startDate: string, endDate: string): Promise<any> {
    return this.request(`/enforcement/drug/trend?start_date=${startDate}&end_date=${endDate}`);
  }

  /** 大型車週趨勢 */
  async getHeavyVehicleTrend(startDate: string, endDate: string): Promise<any> {
    return this.request(`/enforcement/heavy-vehicle/trend?start_date=${startDate}&end_date=${endDate}`);
  }

  /** 超速週趨勢（單序列總量） */
  async getSpeedTrend(startDate: string, endDate: string): Promise<any> {
    return this.request(`/enforcement/speed/trend?start_date=${startDate}&end_date=${endDate}`);
  }

  /** 週事故趨勢（總覽用，Crash 側 A1/A2/A3） */
  async getAccidentTrend(startDate: string, endDate: string): Promise<any> {
    return this.request(`/recommendations/accidents/trend?start_date=${startDate}&end_date=${endDate}`);
  }

  /** 道路照明故障事故清冊（通報養工處修燈） */
  async getRoadLightingIssues(startDate: string, endDate: string): Promise<any> {
    return this.request(`/recommendations/road-lighting-issues?start_date=${startDate}&end_date=${endDate}`);
  }

  /**
   * 廊帶（公路路線）線性分析
   * - 不帶 route：回傳全路線排名（依 EPDO 降冪）
   * - 帶 route：回傳該路線 0.5 公里分段熱段分析（route 以 URLSearchParams 自動編碼，中文路名安全）
   */
  async getCorridorAnalysis(startDate: string, endDate: string, route?: string): Promise<any> {
    const params = new URLSearchParams({ start_date: startDate, end_date: endDate });
    // 注意：URLSearchParams.append 已自動做 percent-encoding，route 傳原始字串即可，
    // 若再套用 encodeURIComponent 會造成雙重編碼（%25xx)
    if (route) params.append('route', route);
    return this.request(`/recommendations/corridor-analysis?${params}`);
  }

  /** 會勘資料包：座標＋半徑範圍內近 3 年事故彙整、樣態、涉入對象與改善建議 */
  async getSiteDossier(lat: number, lng: number, radiusM: number): Promise<any> {
    return this.request(`/recommendations/site-dossier?lat=${lat}&lng=${lng}&radius_m=${radiusM}`);
  }

  /** 勤務建議單（DDACTS 簡化版）：7 所依 EPDO 降冪排序，各所前 3 高風險班別與取締缺口標記 */
  async getPatrolPlan(startDate: string, endDate: string): Promise<any> {
    return this.request(`/recommendations/patrol-plan?start_date=${startDate}&end_date=${endDate}`);
  }

  // ============================================
  // Improvement Tracking API（改善成效追蹤）
  // ============================================

  /** 登記改善措施（需登入；未登入時後端回應 401 寫入保護） */
  async createImprovement(data: {
    title: string;
    measure_type: string;
    latitude: number;
    longitude: number;
    radius_m: number;
    implemented_date: string;
    description?: string;
    source?: string;
  }): Promise<any> {
    return this.request('/improvements/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 取得所有已登記改善措施 */
  async getImprovements(): Promise<any> {
    return this.request('/improvements/');
  }

  /** 刪除改善措施登記（需登入；未登入時後端回應 401 寫入保護） */
  async deleteImprovement(id: number): Promise<any> {
    return this.request(`/improvements/${id}`, {
      method: 'DELETE',
    });
  }

  /** 改善成效評估：比較各已登記措施實施前後事故率（含全區同期基準線，預設近 365 天） */
  async getImprovementEvaluations(days: number = 365): Promise<any> {
    return this.request(`/improvements/evaluations?days=${days}`);
  }

  /** 明日風險預警：依歷史同星期型態推估各所各班別風險分數（不帶參數時，後端預設抓「資料最新日 + 1」） */
  async getRiskForecast(targetDate?: string): Promise<any> {
    return this.request(`/recommendations/risk-forecast${targetDate ? `?target_date=${targetDate}` : ''}`);
  }

  /** 系統操作稽核軌跡：最近 N 筆寫入操作與登入事件（預設 30 筆） */
  async getAuditLog(limit?: number): Promise<any> {
    return this.request(`/admin/audit-log?limit=${limit ?? 30}`);
  }

  /** 資料品質總覽 */
  async getDataQuality(): Promise<any> {
    return this.request('/admin/data-quality');
  }

  async getDrugPerformance(startDate: string, endDate: string): Promise<any> {
    return this.request(`/enforcement/drug?start_date=${startDate}&end_date=${endDate}`);
  }

  async getHeavyVehiclePerformance(startDate: string, endDate: string): Promise<any> {
    return this.request(`/enforcement/heavy-vehicle?start_date=${startDate}&end_date=${endDate}`);
  }

  async getSpeedPerformance(startDate: string, endDate: string): Promise<any> {
    return this.request(`/enforcement/speed?start_date=${startDate}&end_date=${endDate}`);
  }

  async getPedestrianAnalysis(startDate: string, endDate: string): Promise<any> {
    return this.request(`/enforcement/pedestrian?start_date=${startDate}&end_date=${endDate}`);
  }
}

// 報告相關介面定義
export interface ReportResponse {
  period: {
    year: number;
    month: number;
  };
  raw_data: any; // 原始統計數據
  ai_analysis: {
    provider: string;
    model: string;
    content: string; // Markdown 格式報告
  };
}

// Export singleton instance
export const apiClient = new APIClient();

// Export class for testing
export { APIClient };
