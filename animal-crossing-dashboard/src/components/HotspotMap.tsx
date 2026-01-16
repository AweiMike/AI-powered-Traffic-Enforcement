/**
 * HotspotMap Component - 熱點地圖
 * 使用 Leaflet + OpenStreetMap 顯示違規/事故熱點
 * 
 * 改用區域(District)統計顯示，不需要精確座標
 */

import React, { useEffect, useRef, useMemo } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Map, AlertTriangle } from 'lucide-react';
import { HeatmapPoint, SiteRecommendation, TopicCode } from '../api/client';

// 台南市新化區中心座標
const TAINAN_CENTER: L.LatLngExpression = [23.04, 120.31];
const DEFAULT_ZOOM = 11;

interface HotspotMapProps {
    heatmapPoints: HeatmapPoint[];
    top5Sites?: SiteRecommendation[];
    topicCode: TopicCode;
    loading?: boolean;
}

// 主題配色
const topicColors: Record<TopicCode, string> = {
    DUI: '#E89A9A',
    RED_LIGHT: '#F4B860',
    DANGEROUS_DRIVING: '#8DCEDC'
};

// 計算標記大小（根據強度）- 區域級別使用較大標記
const getMarkerRadius = (intensity: number, maxIntensity: number): number => {
    const minRadius = 18;
    const maxRadius = 45;
    const normalized = maxIntensity > 0 ? intensity / maxIntensity : 0;
    return minRadius + normalized * (maxRadius - minRadius);
};

export const HotspotMap: React.FC<HotspotMapProps> = ({
    heatmapPoints,
    top5Sites = [],
    topicCode,
    loading = false
}) => {
    const mapRef = useRef<L.Map | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const markersRef = useRef<L.CircleMarker[]>([]);
    const [mapReady, setMapReady] = React.useState(false);
    const topicColor = topicColors[topicCode];

    // 計算最大強度（用於標記大小正規化）
    const maxIntensity = useMemo(() => {
        if (heatmapPoints.length === 0) return 1;
        return Math.max(...heatmapPoints.map(p => p.intensity));
    }, [heatmapPoints]);

    // 初始化地圖
    useEffect(() => {
        // Delay initialization to ensure DOM is ready
        const timer = setTimeout(() => {
            if (!containerRef.current || mapRef.current) return;

            // Force container dimensions
            const container = containerRef.current;
            if (container.offsetWidth === 0 || container.offsetHeight === 0) {
                container.style.height = '350px';
            }

            mapRef.current = L.map(container).setView(TAINAN_CENTER, DEFAULT_ZOOM);

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            }).addTo(mapRef.current);

            // Force map to recalculate size after init, then signal ready
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

    // 更新標記 - 等待 mapReady 確保地圖已初始化
    useEffect(() => {
        const map = mapRef.current;
        if (!map || !mapReady) return;

        // 清除現有標記
        markersRef.current.forEach(marker => marker.remove());
        markersRef.current = [];

        if (heatmapPoints.length === 0) return;

        console.log('[HotspotMap] Adding markers:', heatmapPoints.length, 'points');

        // 新增標記
        const bounds: L.LatLngBoundsExpression = [];

        heatmapPoints.forEach((point) => {
            if (!point.latitude || !point.longitude) return;

            const isTop5 = top5Sites.some(
                s => s.coordinates?.latitude === point.latitude &&
                    s.coordinates?.longitude === point.longitude
            );

            const radius = getMarkerRadius(point.intensity, maxIntensity);
            const color = isTop5 ? '#9ECE9A' : topicColor;
            const borderColor = isTop5 ? '#7DAC7A' : topicColor;

            const marker = L.circleMarker([point.latitude, point.longitude], {
                radius: isTop5 ? radius + 4 : radius,
                color: borderColor,
                fillColor: color,
                fillOpacity: isTop5 ? 0.9 : 0.6,
                weight: isTop5 ? 3 : 2
            }).addTo(map);

            // Popup 內容
            marker.bindPopup(`
                <div style="font-size: 14px;">
                    <div style="font-weight: bold; margin-bottom: 4px;">
                        📍 ${point.site_name}
                    </div>
                    <div style="color: #666; font-size: 12px; margin-bottom: 8px;">
                        ${point.district}
                    </div>
                    <div style="font-size: 12px;">
                        ⚠️ 違規強度：${point.intensity} 件
                    </div>
                    ${isTop5 ? '<div style="color: #9ECE9A; font-weight: 600; margin-top: 4px;">⭐ Top 5 推薦點位</div>' : ''}
                </div>
            `);

            markersRef.current.push(marker);
            bounds.push([point.latitude, point.longitude]);
        });

        // 自動調整視野
        if (bounds.length > 0) {
            map.fitBounds(bounds, { padding: [30, 30], maxZoom: 13 });
        }
    }, [heatmapPoints, top5Sites, topicColor, maxIntensity, mapReady]);

    // 載入中狀態
    if (loading) {
        return (
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow h-full min-h-[400px] flex items-center justify-center">
                <div className="text-center">
                    <div className="animate-spin text-4xl mb-2">🗺️</div>
                    <p className="text-nook-text/60 text-sm">載入地圖中...</p>
                </div>
            </div>
        );
    }

    // 無資料狀態
    if (heatmapPoints.length === 0) {
        return (
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow h-full min-h-[400px] flex items-center justify-center p-6">
                <div className="text-center">
                    <Map className="w-12 h-12 text-nook-text/30 mx-auto mb-3" />
                    <p className="text-nook-text/60 font-medium">📍 目前沒有推薦點位資料</p>
                    <p className="text-nook-text/40 text-sm mt-1">請先匯入資料或調整篩選條件</p>
                </div>
            </div>
        );
    }

    return (
        <div className="bg-white/80 backdrop-blur-sm rounded-2xl nook-shadow overflow-hidden h-full min-h-[400px]">
            {/* 地圖標題 */}
            <div className="p-3 border-b border-nook-cream/50 bg-white/50">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Map className="w-4 h-4 text-nook-leaf" />
                        <span className="font-bold text-sm text-nook-text">熱點分布圖</span>
                    </div>
                    <span className="text-xs text-nook-text/50">
                        共 {heatmapPoints.length} 個區域
                    </span>
                </div>
            </div>

            {/* 圖例 */}
            <div className="px-3 py-2 bg-nook-cream/20 border-b border-nook-cream/30 flex items-center gap-4 text-xs">
                <div className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: topicColor }}></span>
                    <span className="text-nook-text/70">違規熱點</span>
                </div>
                <div className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded-full bg-nook-leaf border-2 border-nook-leaf-dark"></span>
                    <span className="text-nook-text/70">Top 5</span>
                </div>
                <div className="flex items-center gap-1 ml-auto">
                    <AlertTriangle className="w-3 h-3 text-nook-orange" />
                    <span className="text-nook-text/50">依區域統計</span>
                </div>
            </div>

            {/* 地圖容器 */}
            <div ref={containerRef} className="h-[350px] w-full" />
        </div>
    );
};

export default HotspotMap;
