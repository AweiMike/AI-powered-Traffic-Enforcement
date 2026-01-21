/**
 * MapViewPage - 地圖視覺化頁面
 * 使用真實座標顯示事故/違規點位與熱力圖
 */

import React, { useState, useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Map, Filter, Layers, AlertTriangle, Circle, Eye, EyeOff, RefreshCw } from 'lucide-react';
import { apiClient } from '../api/client';

// 台南市中心座標
const TAINAN_CENTER: L.LatLngExpression = [23.04, 120.31];
const DEFAULT_ZOOM = 11;

interface MapPoint {
    id: number;
    lat: number;
    lng: number;
    district: string;
    location: string;
    severity?: string;
    topic?: string;
    date?: string;
    shift?: string;
    is_elderly?: boolean;
    is_dui?: boolean;
    vehicle_type?: string;
}

interface MapData {
    crash_points: MapPoint[];
    ticket_points: MapPoint[];
    summary: {
        total_crashes: number;
        total_tickets: number;
        crashes_with_coords: number;
        tickets_with_coords: number;
    };
}

const MapViewPage: React.FC = () => {
    const mapRef = useRef<L.Map | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const markersRef = useRef<L.CircleMarker[]>([]);

    const [mapReady, setMapReady] = useState(false);
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<MapData | null>(null);
    const [days, setDays] = useState(90);

    // 篩選器狀態
    const [showCrashes, setShowCrashes] = useState(true);
    const [showTickets, setShowTickets] = useState(true);
    const [severityFilter, setSeverityFilter] = useState<string>('all');
    const [topicFilter, setTopicFilter] = useState<string>('all');

    // 初始化地圖
    useEffect(() => {
        const timer = setTimeout(() => {
            if (!containerRef.current || mapRef.current) return;

            const container = containerRef.current;
            if (container.offsetWidth === 0 || container.offsetHeight === 0) {
                container.style.height = '600px';
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

    // 載入資料
    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            try {
                const result = await apiClient.getMapPoints(days);
                setData(result);
            } catch (e) {
                console.error('Failed to load map data:', e);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [days]);

    // 更新地圖標記
    useEffect(() => {
        const map = mapRef.current;
        if (!map || !mapReady || !data) return;

        // 清除現有標記
        markersRef.current.forEach(marker => marker.remove());
        markersRef.current = [];

        const bounds: L.LatLngBoundsExpression = [];

        // 繪製事故點位（紅色）
        if (showCrashes) {
            data.crash_points
                .filter(p => severityFilter === 'all' || p.severity === severityFilter)
                .forEach((point) => {
                    const color = point.severity === 'A1' ? '#B91C1C' :
                        point.severity === 'A2' ? '#EA580C' : '#F59E0B';
                    const radius = point.severity === 'A1' ? 10 :
                        point.severity === 'A2' ? 8 : 6;

                    const marker = L.circleMarker([point.lat, point.lng], {
                        radius: radius,
                        color: color,
                        fillColor: color,
                        fillOpacity: 0.7,
                        weight: 2
                    }).addTo(map);

                    marker.bindPopup(`
                        <div style="font-size: 13px; min-width: 180px;">
                            <div style="font-weight: bold; color: ${color}; margin-bottom: 6px; border-bottom: 1px solid #eee; padding-bottom: 4px;">
                                🚧 事故點位 (${point.severity})
                            </div>
                            <table style="width: 100%; font-size: 12px;">
                                <tr><td style="color: #666;">位置</td><td style="text-align: right;">${point.district} ${point.location || ''}</td></tr>
                                <tr><td style="color: #666;">日期</td><td style="text-align: right;">${point.date?.split('T')[0] || '-'}</td></tr>
                                <tr><td style="color: #666;">班別</td><td style="text-align: right;">${point.shift || '-'}</td></tr>
                                ${point.is_elderly ? '<tr><td colspan="2" style="color: #EA580C;">👴 高齡者相關</td></tr>' : ''}
                                ${point.is_dui ? '<tr><td colspan="2" style="color: #7C3AED;">🍺 疑似酒駕</td></tr>' : ''}
                            </table>
                        </div>
                    `);

                    markersRef.current.push(marker);
                    bounds.push([point.lat, point.lng]);
                });
        }

        // 繪製違規點位（藍色）
        if (showTickets) {
            data.ticket_points
                .filter(p => topicFilter === 'all' || p.topic === topicFilter)
                .forEach((point) => {
                    const color = point.topic === 'DUI' ? '#7C3AED' :
                        point.topic === 'RED_LIGHT' ? '#2563EB' : '#0891B2';

                    const marker = L.circleMarker([point.lat, point.lng], {
                        radius: 5,
                        color: color,
                        fillColor: color,
                        fillOpacity: 0.6,
                        weight: 1
                    }).addTo(map);

                    const topicName = point.topic === 'DUI' ? '酒駕' :
                        point.topic === 'RED_LIGHT' ? '闖紅燈' :
                            point.topic === 'DANGEROUS_DRIVING' ? '危險駕駛' : '其他';

                    marker.bindPopup(`
                        <div style="font-size: 13px; min-width: 160px;">
                            <div style="font-weight: bold; color: ${color}; margin-bottom: 6px; border-bottom: 1px solid #eee; padding-bottom: 4px;">
                                📋 違規點位 (${topicName})
                            </div>
                            <table style="width: 100%; font-size: 12px;">
                                <tr><td style="color: #666;">位置</td><td style="text-align: right;">${point.district} ${point.location || ''}</td></tr>
                                <tr><td style="color: #666;">日期</td><td style="text-align: right;">${point.date?.split('T')[0] || '-'}</td></tr>
                            </table>
                        </div>
                    `);

                    markersRef.current.push(marker);
                    bounds.push([point.lat, point.lng]);
                });
        }

        // 自動調整視野
        if (bounds.length > 0) {
            map.fitBounds(bounds, { padding: [30, 30], maxZoom: 14 });
        }
    }, [data, showCrashes, showTickets, severityFilter, topicFilter, mapReady]);

    const dayOptions = [
        { value: 30, label: '30 天' },
        { value: 90, label: '90 天' },
        { value: 180, label: '180 天' },
        { value: 365, label: '1 年' },
    ];

    return (
        <div className="p-8">
            {/* 標題區 */}
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h2 className="text-2xl font-bold text-nook-text mb-2">🗺️ 地圖視覺化</h2>
                    <p className="text-nook-text/60">基於真實座標的事故與違規點位分布</p>
                </div>
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 bg-white/80 rounded-2xl px-4 py-2 nook-shadow">
                        <span className="text-sm text-nook-text/60">📅</span>
                        <select
                            value={days}
                            onChange={(e) => setDays(Number(e.target.value))}
                            className="bg-transparent text-sm font-medium text-nook-text outline-none"
                        >
                            {dayOptions.map(opt => (
                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                        </select>
                    </div>
                    <button
                        onClick={() => setDays(days)}
                        className="p-2 bg-nook-leaf text-white rounded-xl hover:bg-nook-leaf/90 transition-colors"
                    >
                        <RefreshCw className="w-5 h-5" />
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-12 gap-6">
                {/* 控制面板 */}
                <div className="col-span-3 space-y-4">
                    {/* 資料統計 */}
                    {data && (
                        <div className="bg-white/80 rounded-2xl p-4 nook-shadow">
                            <h3 className="font-bold text-nook-text mb-3 flex items-center gap-2">
                                <Layers className="w-4 h-4 text-nook-leaf" />
                                資料統計
                            </h3>
                            <div className="space-y-2 text-sm">
                                <div className="flex justify-between">
                                    <span className="text-nook-text/60">事故總數</span>
                                    <span className="font-bold text-red-600">{data.summary.total_crashes}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-nook-text/60">有座標</span>
                                    <span className="font-medium text-nook-text">{data.summary.crashes_with_coords}</span>
                                </div>
                                <div className="border-t border-nook-cream pt-2 mt-2 flex justify-between">
                                    <span className="text-nook-text/60">違規總數</span>
                                    <span className="font-bold text-blue-600">{data.summary.total_tickets}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-nook-text/60">有座標</span>
                                    <span className="font-medium text-nook-text">{data.summary.tickets_with_coords}</span>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* 圖層控制 */}
                    <div className="bg-white/80 rounded-2xl p-4 nook-shadow">
                        <h3 className="font-bold text-nook-text mb-3 flex items-center gap-2">
                            <Filter className="w-4 h-4 text-nook-leaf" />
                            圖層控制
                        </h3>
                        <div className="space-y-3">
                            <label className="flex items-center justify-between cursor-pointer">
                                <span className="flex items-center gap-2">
                                    <Circle className="w-4 h-4 text-red-500 fill-red-500" />
                                    <span className="text-sm text-nook-text">事故點位</span>
                                </span>
                                <button
                                    onClick={() => setShowCrashes(!showCrashes)}
                                    className={`p-1 rounded ${showCrashes ? 'bg-nook-leaf text-white' : 'bg-gray-200 text-gray-500'}`}
                                >
                                    {showCrashes ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                                </button>
                            </label>
                            <label className="flex items-center justify-between cursor-pointer">
                                <span className="flex items-center gap-2">
                                    <Circle className="w-4 h-4 text-blue-500 fill-blue-500" />
                                    <span className="text-sm text-nook-text">違規點位</span>
                                </span>
                                <button
                                    onClick={() => setShowTickets(!showTickets)}
                                    className={`p-1 rounded ${showTickets ? 'bg-nook-leaf text-white' : 'bg-gray-200 text-gray-500'}`}
                                >
                                    {showTickets ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                                </button>
                            </label>
                        </div>
                    </div>

                    {/* 事故篩選 */}
                    <div className="bg-white/80 rounded-2xl p-4 nook-shadow">
                        <h3 className="font-bold text-nook-text mb-3">🚧 事故嚴重度</h3>
                        <div className="flex flex-wrap gap-2">
                            {[
                                { value: 'all', label: '全部', color: 'bg-gray-100 text-gray-700' },
                                { value: 'A1', label: 'A1 死亡', color: 'bg-red-100 text-red-700' },
                                { value: 'A2', label: 'A2 受傷', color: 'bg-orange-100 text-orange-700' },
                                { value: 'A3', label: 'A3 財損', color: 'bg-yellow-100 text-yellow-700' },
                            ].map(opt => (
                                <button
                                    key={opt.value}
                                    onClick={() => setSeverityFilter(opt.value)}
                                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${severityFilter === opt.value
                                            ? 'ring-2 ring-nook-leaf ' + opt.color
                                            : opt.color + ' opacity-60 hover:opacity-100'
                                        }`}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* 違規篩選 */}
                    <div className="bg-white/80 rounded-2xl p-4 nook-shadow">
                        <h3 className="font-bold text-nook-text mb-3">📋 違規類型</h3>
                        <div className="flex flex-wrap gap-2">
                            {[
                                { value: 'all', label: '全部', color: 'bg-gray-100 text-gray-700' },
                                { value: 'DUI', label: '🍺 酒駕', color: 'bg-purple-100 text-purple-700' },
                                { value: 'RED_LIGHT', label: '🚦 闖紅燈', color: 'bg-blue-100 text-blue-700' },
                                { value: 'DANGEROUS_DRIVING', label: '⚡ 危駕', color: 'bg-cyan-100 text-cyan-700' },
                            ].map(opt => (
                                <button
                                    key={opt.value}
                                    onClick={() => setTopicFilter(opt.value)}
                                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${topicFilter === opt.value
                                            ? 'ring-2 ring-nook-leaf ' + opt.color
                                            : opt.color + ' opacity-60 hover:opacity-100'
                                        }`}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* 圖例 */}
                    <div className="bg-nook-cream/30 rounded-2xl p-4">
                        <h3 className="font-bold text-nook-text mb-3">📌 圖例說明</h3>
                        <div className="space-y-2 text-xs text-nook-text/70">
                            <div className="flex items-center gap-2">
                                <span className="w-3 h-3 rounded-full bg-red-600"></span>
                                <span>A1 死亡事故（大圓）</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="w-3 h-3 rounded-full bg-orange-500"></span>
                                <span>A2 受傷事故（中圓）</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="w-3 h-3 rounded-full bg-yellow-500"></span>
                                <span>A3 財損事故（小圓）</span>
                            </div>
                            <div className="flex items-center gap-2 pt-2 border-t border-nook-cream">
                                <span className="w-3 h-3 rounded-full bg-purple-500"></span>
                                <span>酒駕違規</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="w-3 h-3 rounded-full bg-blue-500"></span>
                                <span>闖紅燈違規</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="w-3 h-3 rounded-full bg-cyan-500"></span>
                                <span>危險駕駛違規</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* 地圖區域 */}
                <div className="col-span-9">
                    <div className="bg-white/80 rounded-2xl nook-shadow overflow-hidden">
                        {/* 地圖標題 */}
                        <div className="p-3 border-b border-nook-cream/50 bg-white/50 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <Map className="w-5 h-5 text-nook-leaf" />
                                <span className="font-bold text-nook-text">精準點位地圖</span>
                            </div>
                            {loading && (
                                <span className="text-xs text-nook-text/50 flex items-center gap-1">
                                    <RefreshCw className="w-3 h-3 animate-spin" />
                                    載入中...
                                </span>
                            )}
                            {!loading && data && (
                                <span className="text-xs text-nook-text/50">
                                    顯示 {markersRef.current.length} 個點位
                                </span>
                            )}
                        </div>

                        {/* 地圖容器 */}
                        <div ref={containerRef} className="h-[600px] w-full" />
                    </div>

                    {/* 提示訊息 */}
                    {data && data.summary.crashes_with_coords === 0 && data.summary.tickets_with_coords === 0 && (
                        <div className="mt-4 bg-yellow-50 rounded-2xl p-4 flex items-start gap-3">
                            <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                            <div>
                                <p className="font-medium text-yellow-800">無座標資料</p>
                                <p className="text-sm text-yellow-600">
                                    目前匯入的資料沒有經緯度座標。請確認 Excel 檔案包含「緯度」和「經度」欄位，或使用含有座標的原始資料檔案。
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default MapViewPage;
