/**
 * AccidentViolationMap Component - 事故與違規對照地圖
 * 參考歸仁分局「事故與執法關聯性分析」圖表樣式
 * 
 * 功能：
 * - 紅色圓點：事故高發區（大小依嚴重度權重）
 * - 藍色圓點：違規執法點位（大小依違規數量）
 * - 前十大易肇事區域列表
 */

import React, { useEffect, useRef, useMemo } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Map, AlertTriangle, FileText } from 'lucide-react';

// 台南市新化分局轄區中心座標
const TAINAN_CENTER: L.LatLngExpression = [23.04, 120.31];
const DEFAULT_ZOOM = 11;

// 區域座標對照表
const DISTRICT_COORDS: Record<string, [number, number]> = {
    '新化區': [23.0383, 120.3108],
    '市新化區': [23.0383, 120.3108],
    '左鎮區': [23.0581, 120.4028],
    '市左鎮區': [23.0581, 120.4028],
    '山上區': [23.1003, 120.3858],
    '市山上區': [23.1003, 120.3858],
    '南化區': [23.0421, 120.4683],
    '市南化區': [23.0421, 120.4683],
    '玉井區': [23.1228, 120.4603],
    '市玉井區': [23.1228, 120.4603],
    '楠西區': [23.1788, 120.4858],
    '市楠西區': [23.1788, 120.4858],
    '善化區': [23.1322, 120.2967],
    '市善化區': [23.1322, 120.2967],
    '大內區': [23.1203, 120.3508],
    '市大內區': [23.1203, 120.3508],
    '歸仁區': [22.9672, 120.2939],
    '市歸仁區': [22.9672, 120.2939],
    '仁德區': [22.9722, 120.2272],
    '市仁德區': [22.9722, 120.2272],
};

interface AccidentData {
    district: string;
    total: number;
    a1_count: number;
    a2_count: number;
    a3_count: number;
    severity_score: number;
}

interface ViolationData {
    district: string;
    count: number;
    dui?: number;
    red_light?: number;
    dangerous?: number;
}

interface AccidentViolationMapProps {
    accidentData: AccidentData[];
    violationData: ViolationData[];
    loading?: boolean;
    showViolations?: boolean;
    showAccidents?: boolean;
}

export const AccidentViolationMap: React.FC<AccidentViolationMapProps> = ({
    accidentData,
    violationData,
    loading = false,
    showViolations = true,
    showAccidents = true
}) => {
    const mapRef = useRef<L.Map | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const markersRef = useRef<L.CircleMarker[]>([]);
    const [mapReady, setMapReady] = React.useState(false);

    // 計算最大值用於正規化
    const maxAccident = useMemo(() => Math.max(...accidentData.map(a => a.severity_score || a.total), 1), [accidentData]);
    const maxViolation = useMemo(() => Math.max(...violationData.map(v => v.count), 1), [violationData]);

    // 初始化地圖
    useEffect(() => {
        const timer = setTimeout(() => {
            if (!containerRef.current || mapRef.current) return;

            const container = containerRef.current;
            if (container.offsetWidth === 0 || container.offsetHeight === 0) {
                container.style.height = '400px';
            }

            mapRef.current = L.map(container).setView(TAINAN_CENTER, DEFAULT_ZOOM);

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            }).addTo(mapRef.current);

            setTimeout(() => {
                mapRef.current?.invalidateSize();
                setMapReady(true);
            }, 100);
        }, 50);

        return () => {
            clearTimeout(timer);
            setMapReady(false);
            if (mapRef.current) {
                mapRef.current.remove();
                mapRef.current = null;
            }
        };
    }, []);

    // 更新標記
    useEffect(() => {
        const map = mapRef.current;
        if (!map || !mapReady) return;

        // 清除現有標記
        markersRef.current.forEach(marker => marker.remove());
        markersRef.current = [];

        const bounds: L.LatLngBoundsExpression = [];

        // 繪製事故點位（紅色）
        if (showAccidents) {
            accidentData.forEach((accident) => {
                const coords = DISTRICT_COORDS[accident.district];
                if (!coords) return;

                const normalizedSize = (accident.severity_score || accident.total) / maxAccident;
                const radius = 15 + normalizedSize * 25;

                const marker = L.circleMarker(coords, {
                    radius: radius,
                    color: '#DC2626',
                    fillColor: '#EF4444',
                    fillOpacity: 0.6,
                    weight: 2
                }).addTo(map);

                marker.bindPopup(`
          <div style="font-size: 13px; min-width: 150px;">
            <div style="font-weight: bold; color: #DC2626; margin-bottom: 6px; border-bottom: 1px solid #eee; padding-bottom: 4px;">
              🚧 ${accident.district} - 事故統計
            </div>
            <table style="width: 100%; font-size: 12px;">
              <tr><td>總事故數</td><td style="text-align: right; font-weight: bold;">${accident.total}</td></tr>
              <tr style="color: #B91C1C;"><td>A1 死亡</td><td style="text-align: right; font-weight: bold;">${accident.a1_count}</td></tr>
              <tr style="color: #EA580C;"><td>A2 受傷</td><td style="text-align: right; font-weight: bold;">${accident.a2_count}</td></tr>
              <tr style="color: #CA8A04;"><td>A3 財損</td><td style="text-align: right; font-weight: bold;">${accident.a3_count || 0}</td></tr>
            </table>
          </div>
        `);

                markersRef.current.push(marker);
                bounds.push(coords);
            });
        }

        // 繪製違規點位（藍色）- 稍微偏移避免重疊
        if (showViolations) {
            violationData.forEach((violation) => {
                const baseCoords = DISTRICT_COORDS[violation.district];
                if (!baseCoords) return;

                // 稍微偏移避免與事故點重疊
                const coords: [number, number] = [baseCoords[0] + 0.008, baseCoords[1] + 0.008];

                const normalizedSize = violation.count / maxViolation;
                const radius = 12 + normalizedSize * 20;

                const marker = L.circleMarker(coords, {
                    radius: radius,
                    color: '#2563EB',
                    fillColor: '#3B82F6',
                    fillOpacity: 0.6,
                    weight: 2
                }).addTo(map);

                marker.bindPopup(`
          <div style="font-size: 13px; min-width: 150px;">
            <div style="font-weight: bold; color: #2563EB; margin-bottom: 6px; border-bottom: 1px solid #eee; padding-bottom: 4px;">
              📋 ${violation.district} - 違規執法
            </div>
            <table style="width: 100%; font-size: 12px;">
              <tr><td>總違規數</td><td style="text-align: right; font-weight: bold;">${violation.count}</td></tr>
              ${violation.dui !== undefined ? `<tr><td>🍺 酒駕</td><td style="text-align: right;">${violation.dui}</td></tr>` : ''}
              ${violation.red_light !== undefined ? `<tr><td>🚦 闖紅燈</td><td style="text-align: right;">${violation.red_light}</td></tr>` : ''}
              ${violation.dangerous !== undefined ? `<tr><td>⚡ 危險駕駛</td><td style="text-align: right;">${violation.dangerous}</td></tr>` : ''}
            </table>
          </div>
        `);

                markersRef.current.push(marker);
                bounds.push(coords);
            });
        }

        // 自動調整視野
        if (bounds.length > 0) {
            map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
        }
    }, [accidentData, violationData, maxAccident, maxViolation, mapReady, showAccidents, showViolations]);

    if (loading) {
        return (
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow h-full min-h-[450px] flex items-center justify-center">
                <div className="text-center">
                    <div className="animate-spin text-4xl mb-2">🗺️</div>
                    <p className="text-nook-text/60 text-sm">載入地圖中...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden">
            {/* 標題 */}
            <div className="p-4 border-b border-nook-cream/50 bg-white/50">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Map className="w-5 h-5 text-nook-leaf" />
                        <span className="font-bold text-nook-text">事故與執法關聯性分析</span>
                    </div>
                    <span className="text-xs text-nook-text/50">
                        共 {accidentData.length} 個事故區域 | {violationData.length} 個執法區域
                    </span>
                </div>
            </div>

            {/* 圖例 */}
            <div className="px-4 py-2 bg-nook-cream/20 border-b border-nook-cream/30 flex items-center gap-6 text-xs">
                <div className="flex items-center gap-2">
                    <span className="w-4 h-4 rounded-full bg-red-500 border-2 border-red-600"></span>
                    <span className="text-nook-text/70 font-medium">事故點位（紅）</span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="w-4 h-4 rounded-full bg-blue-500 border-2 border-blue-600"></span>
                    <span className="text-nook-text/70 font-medium">違規點位（藍）</span>
                </div>
                <div className="flex items-center gap-1 ml-auto text-nook-text/50">
                    <AlertTriangle className="w-3 h-3" />
                    <span>圓點大小依數量/嚴重度</span>
                </div>
            </div>

            {/* 地圖容器 */}
            <div ref={containerRef} className="h-[400px] w-full" />
        </div>
    );
};

// 前十大易肇事區域列表組件
interface TopAccidentLocationsProps {
    data: AccidentData[];
    loading?: boolean;
}

export const TopAccidentLocations: React.FC<TopAccidentLocationsProps> = ({ data, loading }) => {
    const sortedData = useMemo(() =>
        [...data].sort((a, b) => (b.severity_score || b.total) - (a.severity_score || a.total)).slice(0, 10),
        [data]
    );

    if (loading) {
        return (
            <div className="bg-white/80 rounded-2xl p-4 nook-shadow animate-pulse">
                <div className="h-6 bg-nook-cream rounded w-1/2 mb-4"></div>
                {[1, 2, 3, 4, 5].map(i => (
                    <div key={i} className="h-10 bg-nook-cream rounded mb-2"></div>
                ))}
            </div>
        );
    }

    return (
        <div className="bg-white/80 rounded-2xl nook-shadow">
            <div className="p-4 border-b border-nook-cream/50">
                <div className="flex items-center gap-2">
                    <FileText className="w-5 h-5 text-red-500" />
                    <span className="font-bold text-nook-text">前十大易肇事區域</span>
                </div>
                <p className="text-xs text-nook-text/50 mt-1">依嚴重度權重排序（A1:5分 A2:3分 A3:1分）</p>
            </div>

            <div className="max-h-[400px] overflow-y-auto">
                <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-nook-cream/50">
                        <tr className="text-left text-nook-text/60 text-xs">
                            <th className="py-2 px-3">排名</th>
                            <th className="py-2 px-3">行政區</th>
                            <th className="py-2 px-3 text-center">總數</th>
                            <th className="py-2 px-3 text-center text-red-600">A1</th>
                            <th className="py-2 px-3 text-center text-orange-500">A2</th>
                            <th className="py-2 px-3 text-center">權重</th>
                        </tr>
                    </thead>
                    <tbody>
                        {sortedData.map((item, idx) => (
                            <tr key={item.district} className={`border-b border-nook-cream/30 ${idx < 3 ? 'bg-red-50' : ''}`}>
                                <td className="py-2 px-3">
                                    <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${idx === 0 ? 'bg-red-500 text-white' :
                                            idx === 1 ? 'bg-orange-400 text-white' :
                                                idx === 2 ? 'bg-yellow-400 text-white' :
                                                    'bg-gray-200 text-gray-600'
                                        }`}>
                                        {idx + 1}
                                    </span>
                                </td>
                                <td className="py-2 px-3 font-medium text-nook-text">{item.district}</td>
                                <td className="py-2 px-3 text-center font-bold">{item.total}</td>
                                <td className={`py-2 px-3 text-center font-bold ${item.a1_count > 0 ? 'text-red-600' : 'text-gray-400'}`}>
                                    {item.a1_count}
                                </td>
                                <td className="py-2 px-3 text-center font-bold text-orange-500">{item.a2_count}</td>
                                <td className="py-2 px-3 text-center font-bold text-purple-600">{item.severity_score || 0}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default AccidentViolationMap;
