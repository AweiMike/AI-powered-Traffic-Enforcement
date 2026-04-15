/**
 * MapViewPage - 地圖視覺化頁面
 * 使用真實座標顯示事故/違規點位與熱力圖
 * 支援事故點位手動拖曳校正
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Map as MapIcon, Filter, Layers, AlertTriangle, Circle, Eye, EyeOff, RefreshCw, Edit3, Save, X, Move, Building2, Target, Trash2 } from 'lucide-react';
import { apiClient } from '../api/client';
import DateRangePicker, { type DateRange } from './DateRangePicker';

// 台南市中心座標
// 新化分局轄區中心
const TAINAN_CENTER: L.LatLngExpression = [23.04, 120.33];
const DEFAULT_ZOOM = 12;

interface MapPoint {
    id: number;
    lat: number;
    lng: number;
    district: string;
    location: string;
    severity?: string;
    topic?: string;
    date?: string;
    time?: string;
    shift?: string;
    is_elderly?: boolean;
    is_dui?: boolean;
    vehicle_type?: string;
    violation_name?: string;
    enforcement_type?: string;
    unit?: string;
}

interface SelectionCircle {
    lat: number;
    lng: number;
    radius: number; // 公尺
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

interface PendingUpdate {
    id: number;
    type: 'crash' | 'ticket';
    lat: number;
    lng: number;
    original_lat: number;
    original_lng: number;
}

interface MapViewPageProps {
    readOnly?: boolean;
}

const MapViewPage: React.FC<MapViewPageProps> = ({ readOnly = false }) => {
    const mapRef = useRef<L.Map | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const markersRef = useRef<L.Marker[]>([]);
    const circleMarkersRef = useRef<L.CircleMarker[]>([]);

    const [mapReady, setMapReady] = useState(false);
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<MapData | null>(null);
    const [dateRange, setDateRange] = useState<DateRange>(() => {
        const now = new Date();
        const start = new Date(now.getFullYear(), 0, 1);
        const fmt = (d: Date) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
        return { startDate: fmt(start), endDate: fmt(now) };
    });

    // 篩選器狀態
    const [showCrashes, setShowCrashes] = useState(true);
    const [showTickets, setShowTickets] = useState(true);
    const [severityFilter, setSeverityFilter] = useState<Set<string>>(new Set(['A1', 'A2', 'A3']));
    const [topicFilter, setTopicFilter] = useState<string>('all');
    const [availableUnits, setAvailableUnits] = useState<string[]>([]);
    const [unitFilter, setUnitFilter] = useState<Set<string>>(new Set());

    // 編輯模式狀態
    const [editMode, setEditMode] = useState(false);
    const [pendingUpdates, setPendingUpdates] = useState<globalThis.Map<number, PendingUpdate>>(new globalThis.Map());
    const [saving, setSaving] = useState(false);
    const [saveMessage, setSaveMessage] = useState<string | null>(null);

    // 圈選工具狀態
    const [selectionMode, setSelectionMode] = useState(false);
    const [selectionCircle, setSelectionCircle] = useState<SelectionCircle | null>(null);
    const selectionLayerRef = useRef<L.Circle | null>(null);

    // 載入可用派出所清單
    useEffect(() => {
        apiClient.getMapUnits()
            .then(r => setAvailableUnits(r.units || []))
            .catch(e => console.error('Failed to load units:', e));
    }, []);

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
    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const unitsParam = unitFilter.size > 0 ? Array.from(unitFilter).join(',') : undefined;
            const result = await apiClient.getMapPoints(
                365, 'all', undefined, undefined,
                dateRange.startDate, dateRange.endDate,
                unitsParam
            );
            setData(result);
        } catch (e) {
            console.error('Failed to load map data:', e);
        } finally {
            setLoading(false);
        }
    }, [dateRange, unitFilter]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    // 圈選模式：點擊地圖設定圈選範圍（點一下設中心，點第二下設半徑）
    const clickStateRef = useRef<'idle' | 'awaiting_radius'>('idle');
    const tempCenterRef = useRef<{ lat: number; lng: number } | null>(null);

    useEffect(() => {
        const map = mapRef.current;
        if (!map || !mapReady) return;

        if (!selectionMode) {
            map.getContainer().style.cursor = '';
            return;
        }

        map.getContainer().style.cursor = 'crosshair';

        const handleClick = (e: L.LeafletMouseEvent) => {
            if (clickStateRef.current === 'idle') {
                // 第一次點擊：設為中心
                tempCenterRef.current = { lat: e.latlng.lat, lng: e.latlng.lng };
                clickStateRef.current = 'awaiting_radius';
            } else {
                // 第二次點擊：計算半徑並完成圈選
                const center = tempCenterRef.current!;
                const radius = map.distance([center.lat, center.lng], [e.latlng.lat, e.latlng.lng]);
                setSelectionCircle({ lat: center.lat, lng: center.lng, radius });
                clickStateRef.current = 'idle';
                tempCenterRef.current = null;
                setSelectionMode(false);
            }
        };

        const handleMouseMove = (e: L.LeafletMouseEvent) => {
            if (clickStateRef.current === 'awaiting_radius' && tempCenterRef.current) {
                // 即時預覽圓圈
                const center = tempCenterRef.current;
                const radius = map.distance([center.lat, center.lng], [e.latlng.lat, e.latlng.lng]);
                if (selectionLayerRef.current) {
                    selectionLayerRef.current.remove();
                }
                selectionLayerRef.current = L.circle([center.lat, center.lng], {
                    radius,
                    color: '#10b981',
                    fillColor: '#10b981',
                    fillOpacity: 0.1,
                    weight: 2,
                    dashArray: '5, 5',
                }).addTo(map);
            }
        };

        map.on('click', handleClick);
        map.on('mousemove', handleMouseMove);

        return () => {
            map.off('click', handleClick);
            map.off('mousemove', handleMouseMove);
            map.getContainer().style.cursor = '';
        };
    }, [selectionMode, mapReady]);

    // 繪製確定後的圈選範圍
    useEffect(() => {
        const map = mapRef.current;
        if (!map || !mapReady) return;

        if (selectionLayerRef.current) {
            selectionLayerRef.current.remove();
            selectionLayerRef.current = null;
        }

        if (selectionCircle) {
            selectionLayerRef.current = L.circle([selectionCircle.lat, selectionCircle.lng], {
                radius: selectionCircle.radius,
                color: '#10b981',
                fillColor: '#10b981',
                fillOpacity: 0.15,
                weight: 3,
            }).addTo(map);
        }
    }, [selectionCircle, mapReady]);

    // 清除圈選
    const handleClearSelection = () => {
        setSelectionCircle(null);
        setSelectionMode(false);
        clickStateRef.current = 'idle';
        tempCenterRef.current = null;
        if (selectionLayerRef.current) {
            selectionLayerRef.current.remove();
            selectionLayerRef.current = null;
        }
    };

    // 計算圈選範圍內的統計
    const selectionStats = React.useMemo(() => {
        if (!selectionCircle || !data || !mapRef.current) return null;
        const map = mapRef.current;
        const center: L.LatLngExpression = [selectionCircle.lat, selectionCircle.lng];

        const inside = (lat: number, lng: number) =>
            map.distance(center, [lat, lng]) <= selectionCircle.radius;

        const crashesIn = data.crash_points.filter(p => inside(p.lat, p.lng));
        const ticketsIn = data.ticket_points.filter(p => inside(p.lat, p.lng));

        const severityCount = { A1: 0, A2: 0, A3: 0 };
        crashesIn.forEach(c => {
            if (c.severity && c.severity in severityCount) {
                severityCount[c.severity as 'A1' | 'A2' | 'A3']++;
            }
        });

        const topicCount: Record<string, number> = { DUI: 0, RED_LIGHT: 0, DANGEROUS_DRIVING: 0, OTHER: 0 };
        ticketsIn.forEach(t => {
            if (t.topic && t.topic in topicCount) topicCount[t.topic]++;
            else topicCount.OTHER++;
        });

        const unitCount: Record<string, number> = {};
        [...crashesIn, ...ticketsIn].forEach(p => {
            if (p.unit) unitCount[p.unit] = (unitCount[p.unit] || 0) + 1;
        });

        return {
            crashTotal: crashesIn.length,
            ticketTotal: ticketsIn.length,
            severity: severityCount,
            topic: topicCount,
            units: Object.entries(unitCount).sort((a, b) => b[1] - a[1]),
        };
    }, [selectionCircle, data]);

    // 處理標記拖曳
    const handleMarkerDrag = useCallback((pointId: number, pointType: 'crash' | 'ticket', originalLat: number, originalLng: number, newLat: number, newLng: number) => {
        const key = `${pointType}_${pointId}`;
        setPendingUpdates(prev => {
            const updated = new globalThis.Map(prev);
            updated.set(key as any, {
                id: pointId,
                type: pointType,
                lat: newLat,
                lng: newLng,
                original_lat: originalLat,
                original_lng: originalLng
            });
            return updated;
        });
    }, []);

    // 儲存變更
    const handleSaveChanges = async () => {
        if (pendingUpdates.size === 0) return;

        setSaving(true);
        setSaveMessage(null);

        try {
            const updates = Array.from(pendingUpdates.values());

            // 逐一更新（區分事故與違規）
            let successCount = 0;
            for (const update of updates) {
                try {
                    if (update.type === 'ticket') {
                        await apiClient.updateTicketCoordinates(update.id, update.lat, update.lng);
                    } else {
                        await apiClient.updateCrashCoordinates(update.id, update.lat, update.lng);
                    }
                    successCount++;
                } catch (e) {
                    console.error(`Failed to update ${update.type} ${update.id}:`, e);
                }
            }

            setSaveMessage(`已儲存 ${successCount} 筆座標變更`);
            setPendingUpdates(new globalThis.Map());

            // 重新載入資料
            await fetchData();

            setTimeout(() => setSaveMessage(null), 3000);
        } catch (e) {
            setSaveMessage('儲存失敗，請重試');
        } finally {
            setSaving(false);
        }
    };

    // 取消編輯
    const handleCancelEdit = () => {
        setEditMode(false);
        setPendingUpdates(new globalThis.Map());
        // 重新渲染地圖以還原位置
        if (data) {
            setData({ ...data });
        }
    };

    // 更新地圖標記
    useEffect(() => {
        const map = mapRef.current;
        if (!map || !mapReady || !data) return;

        // 清除現有標記
        markersRef.current.forEach(marker => marker.remove());
        markersRef.current = [];
        circleMarkersRef.current.forEach(marker => marker.remove());
        circleMarkersRef.current = [];

        const bounds: L.LatLngBoundsExpression = [];

        // 繪製事故點位
        if (showCrashes) {
            data.crash_points
                .filter(p => severityFilter.size === 3 || (p.severity && severityFilter.has(p.severity)))
                .forEach((point) => {
                    // 檢查是否有待儲存的更新
                    const pendingUpdate = pendingUpdates.get(`crash_${point.id}` as any);
                    const lat = pendingUpdate?.lat ?? point.lat;
                    const lng = pendingUpdate?.lng ?? point.lng;

                    const color = point.severity === 'A1' ? '#B91C1C' :
                        point.severity === 'A2' ? '#EA580C' : '#F59E0B';
                    const radius = point.severity === 'A1' ? 10 :
                        point.severity === 'A2' ? 8 : 6;

                    if (editMode) {
                        // 編輯模式 - 使用可拖曳標記
                        const icon = L.divIcon({
                            className: 'custom-marker',
                            html: `<div style="
                                width: ${radius * 2 + 8}px;
                                height: ${radius * 2 + 8}px;
                                background-color: ${color};
                                border: 3px solid white;
                                border-radius: 50%;
                                box-shadow: 0 2px 6px rgba(0,0,0,0.3);
                                cursor: move;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                            "><span style="color: white; font-size: 10px; font-weight: bold;">${point.severity?.charAt(1) || ''}</span></div>`,
                            iconSize: [radius * 2 + 8, radius * 2 + 8],
                            iconAnchor: [radius + 4, radius + 4]
                        });

                        const marker = L.marker([lat, lng], {
                            icon: icon,
                            draggable: true
                        }).addTo(map);

                        marker.on('dragend', (e) => {
                            const newPos = e.target.getLatLng();
                            handleMarkerDrag(point.id, 'crash', point.lat, point.lng, newPos.lat, newPos.lng);
                        });

                        marker.bindPopup(`
                            <div style="font-size: 13px; min-width: 180px;">
                                <div style="font-weight: bold; color: ${color}; margin-bottom: 6px;">
                                    🚧 ${point.severity} - ${point.district}
                                </div>
                                <div style="font-size: 11px; color: #666; margin-bottom: 8px;">
                                    ${point.location || ''}
                                </div>
                                <div style="font-size: 11px; background: #f0f9ff; padding: 6px; border-radius: 4px;">
                                    <strong>📍 拖曳此點位以校正位置</strong>
                                </div>
                            </div>
                        `);

                        markersRef.current.push(marker);
                    } else {
                        // 一般模式 - 使用圓形標記
                        const marker = L.circleMarker([lat, lng], {
                            radius: radius,
                            color: color,
                            fillColor: color,
                            fillOpacity: 0.7,
                            weight: 2
                        }).addTo(map);

                        marker.bindPopup(`
                            <div style="font-size: 13px; min-width: 200px;">
                                <div style="font-weight: bold; color: ${color}; margin-bottom: 6px; border-bottom: 1px solid #eee; padding-bottom: 4px;">
                                    🚧 事故點位 (${point.severity})
                                </div>
                                <table style="width: 100%; font-size: 12px;">
                                    <tr><td style="color: #666;">位置</td><td style="text-align: right;">${point.district} ${point.location || ''}</td></tr>
                                    <tr><td style="color: #666;">發生時間</td><td style="text-align: right;">${point.date?.split('T')[0] || '-'} ${point.time || ''}</td></tr>
                                    <tr><td style="color: #666;">班別</td><td style="text-align: right;">${point.shift || '-'}</td></tr>
                                    ${point.vehicle_type ? `<tr><td style="color: #666;">車種</td><td style="text-align: right;">${point.vehicle_type}</td></tr>` : ''}
                                    ${point.is_elderly ? '<tr><td colspan="2" style="color: #EA580C;">👴 高齡者相關</td></tr>' : ''}
                                    ${point.is_dui ? '<tr><td colspan="2" style="color: #7C3AED;">🍺 疑似酒駕</td></tr>' : ''}
                                </table>
                            </div>
                        `);

                        circleMarkersRef.current.push(marker);
                    }

                    bounds.push([lat, lng]);
                });
        }

        // 繪製違規點位（藍色）
        if (showTickets) {
            data.ticket_points
                .filter(p => topicFilter === 'all' || p.topic === topicFilter)
                .forEach((point) => {
                    const pendingUpdate = pendingUpdates.get(`ticket_${point.id}` as any);
                    const lat = pendingUpdate?.lat ?? point.lat;
                    const lng = pendingUpdate?.lng ?? point.lng;

                    const color = point.topic === 'DUI' ? '#7C3AED' :
                        point.topic === 'RED_LIGHT' ? '#2563EB' : '#0891B2';

                    const topicName = point.topic === 'DUI' ? '酒駕' :
                        point.topic === 'RED_LIGHT' ? '闖紅燈' :
                            point.topic === 'DANGEROUS_DRIVING' ? '危險駕駛' : '';
                    const violationDesc = point.violation_name || topicName || '一般違規';

                    if (editMode) {
                        // 編輯模式 - 可拖曳
                        const icon = L.divIcon({
                            className: 'custom-marker',
                            html: `<div style="
                                width: 16px;
                                height: 16px;
                                background-color: ${color};
                                border: 2px solid white;
                                border-radius: 50%;
                                box-shadow: 0 2px 6px rgba(0,0,0,0.3);
                                cursor: move;
                            "></div>`,
                            iconSize: [16, 16],
                            iconAnchor: [8, 8]
                        });

                        const marker = L.marker([lat, lng], {
                            icon: icon,
                            draggable: true
                        }).addTo(map);

                        marker.on('dragend', (e) => {
                            const newPos = e.target.getLatLng();
                            handleMarkerDrag(point.id, 'ticket', point.lat, point.lng, newPos.lat, newPos.lng);
                        });

                        marker.bindPopup(`
                            <div style="font-size: 13px; min-width: 200px;">
                                <div style="font-weight: bold; color: ${color}; margin-bottom: 6px;">
                                    📋 ${violationDesc}
                                </div>
                                <div style="font-size: 11px; color: #666; margin-bottom: 4px;">
                                    ${point.district} ${point.location || ''}
                                </div>
                                <div style="font-size: 11px; color: #666; margin-bottom: 8px;">
                                    ${point.date?.split('T')[0] || ''} ${point.time || ''} ${point.enforcement_type ? `| ${point.enforcement_type}` : ''}
                                </div>
                                <div style="font-size: 11px; background: #f0f9ff; padding: 6px; border-radius: 4px;">
                                    <strong>📍 拖曳此點位以校正位置</strong>
                                </div>
                            </div>
                        `);

                        markersRef.current.push(marker);
                    } else {
                        // 一般模式
                        const marker = L.circleMarker([lat, lng], {
                            radius: 5,
                            color: color,
                            fillColor: color,
                            fillOpacity: 0.6,
                            weight: 1
                        }).addTo(map);

                        marker.bindPopup(`
                            <div style="font-size: 13px; min-width: 220px;">
                                <div style="font-weight: bold; color: ${color}; margin-bottom: 6px; border-bottom: 1px solid #eee; padding-bottom: 4px;">
                                    📋 ${violationDesc}
                                </div>
                                <table style="width: 100%; font-size: 12px;">
                                    <tr><td style="color: #666;">位置</td><td style="text-align: right;">${point.district} ${point.location || ''}</td></tr>
                                    <tr><td style="color: #666;">違規時間</td><td style="text-align: right;">${point.date?.split('T')[0] || '-'} ${point.time || ''}</td></tr>
                                    ${point.enforcement_type ? `<tr><td style="color: #666;">舉發子類型</td><td style="text-align: right;">${point.enforcement_type}</td></tr>` : ''}
                                    ${point.vehicle_type ? `<tr><td style="color: #666;">車種</td><td style="text-align: right;">${point.vehicle_type}</td></tr>` : ''}
                                </table>
                            </div>
                        `);

                        circleMarkersRef.current.push(marker);
                    }

                    bounds.push([lat, lng]);
                });
        }

        // 自動調整視野
        if (bounds.length > 0 && !editMode) {
            map.fitBounds(bounds, { padding: [30, 30], maxZoom: 14 });
        }
    }, [data, showCrashes, showTickets, severityFilter, topicFilter, mapReady, editMode, pendingUpdates, handleMarkerDrag]);

    return (
        <div className="p-8">
            {/* 標題區 */}
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h2 className="text-2xl font-bold text-nook-text mb-2">🗺️ 地圖視覺化</h2>
                    <p className="text-nook-text/60">基於真實座標的事故與違規點位分布</p>
                </div>
                <div className="flex items-center gap-4">
                    <DateRangePicker value={dateRange} onChange={setDateRange} showCompare={false} />
                    <button
                        onClick={fetchData}
                        disabled={editMode}
                        className="p-2 bg-nook-leaf text-white rounded-xl hover:bg-nook-leaf/90 transition-colors disabled:opacity-50"
                    >
                        <RefreshCw className="w-5 h-5" />
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-12 gap-6">
                {/* 控制面板 */}
                <div className="col-span-3 space-y-4">
                    {/* 編輯模式控制 - 唯讀模式隱藏 */}
                    {!readOnly && (
                    <div className={`rounded-2xl p-4 nook-shadow ${editMode ? 'bg-amber-50 border-2 border-amber-300' : 'bg-white/80'}`}>
                        <h3 className="font-bold text-nook-text mb-3 flex items-center gap-2">
                            <Edit3 className={`w-4 h-4 ${editMode ? 'text-amber-600' : 'text-nook-leaf'}`} />
                            點位校正
                        </h3>
                        {!editMode ? (
                            <button
                                onClick={() => setEditMode(true)}
                                className="w-full py-2 px-4 bg-amber-500 text-white rounded-xl font-medium hover:bg-amber-600 transition-colors flex items-center justify-center gap-2"
                            >
                                <Move className="w-4 h-4" />
                                進入編輯模式
                            </button>
                        ) : (
                            <div className="space-y-3">
                                <p className="text-sm text-amber-700">
                                    🔸 拖曳標記以校正位置<br />
                                    🔸 紅/橙/黃 = 事故點位<br />
                                    🔸 紫/藍/青 = 違規點位
                                </p>
                                {pendingUpdates.size > 0 && (
                                    <div className="bg-amber-100 rounded-lg p-2 text-center">
                                        <span className="text-sm font-bold text-amber-800">
                                            {pendingUpdates.size} 筆待儲存
                                        </span>
                                    </div>
                                )}
                                <div className="flex gap-2">
                                    <button
                                        onClick={handleSaveChanges}
                                        disabled={pendingUpdates.size === 0 || saving}
                                        className="flex-1 py-2 px-3 bg-nook-leaf text-white rounded-xl font-medium hover:bg-nook-leaf/90 transition-colors disabled:opacity-50 flex items-center justify-center gap-1"
                                    >
                                        <Save className="w-4 h-4" />
                                        {saving ? '儲存中...' : '儲存'}
                                    </button>
                                    <button
                                        onClick={handleCancelEdit}
                                        className="flex-1 py-2 px-3 bg-gray-400 text-white rounded-xl font-medium hover:bg-gray-500 transition-colors flex items-center justify-center gap-1"
                                    >
                                        <X className="w-4 h-4" />
                                        取消
                                    </button>
                                </div>
                            </div>
                        )}
                        {saveMessage && (
                            <div className={`mt-3 p-2 rounded-lg text-sm text-center ${saveMessage.includes('失敗') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                                {saveMessage}
                            </div>
                        )}
                    </div>
                    )}

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

                    {/* 圖層控制 - 非編輯模式 */}
                    {!editMode && (
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
                    )}

                    {/* 事故篩選 */}
                    <div className="bg-white/80 rounded-2xl p-4 nook-shadow">
                        <h3 className="font-bold text-nook-text mb-3">🚧 事故嚴重度（可複選）</h3>
                        <div className="flex flex-wrap gap-2">
                            {[
                                { value: 'A1', label: 'A1 死亡', color: 'bg-red-100 text-red-700' },
                                { value: 'A2', label: 'A2 受傷', color: 'bg-orange-100 text-orange-700' },
                                { value: 'A3', label: 'A3 財損', color: 'bg-yellow-100 text-yellow-700' },
                            ].map(opt => {
                                const isActive = severityFilter.has(opt.value);
                                return (
                                    <button
                                        key={opt.value}
                                        onClick={() => {
                                            const next = new Set(severityFilter);
                                            if (next.has(opt.value)) {
                                                if (next.size > 1) next.delete(opt.value);
                                            } else {
                                                next.add(opt.value);
                                            }
                                            setSeverityFilter(next);
                                        }}
                                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${isActive
                                            ? 'ring-2 ring-nook-leaf ' + opt.color
                                            : opt.color + ' opacity-40 hover:opacity-70'
                                            }`}
                                    >
                                        {opt.label}
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    {/* 派出所篩選（可複選） */}
                    {!editMode && availableUnits.length > 0 && (
                        <div className="bg-white/80 rounded-2xl p-4 nook-shadow">
                            <div className="flex items-center justify-between mb-3">
                                <h3 className="font-bold text-nook-text flex items-center gap-2">
                                    <Building2 className="w-4 h-4 text-nook-leaf" />
                                    派出所/單位（可複選）
                                </h3>
                                {unitFilter.size > 0 && (
                                    <button
                                        onClick={() => setUnitFilter(new Set())}
                                        className="text-xs text-nook-text/60 hover:text-nook-leaf"
                                    >
                                        清除
                                    </button>
                                )}
                            </div>
                            <div className="space-y-1 max-h-48 overflow-y-auto">
                                {availableUnits.map(unit => {
                                    const active = unitFilter.has(unit);
                                    const displayName = unit.replace(/^新化分局/, '');
                                    return (
                                        <button
                                            key={unit}
                                            onClick={() => {
                                                const next = new Set(unitFilter);
                                                if (next.has(unit)) next.delete(unit);
                                                else next.add(unit);
                                                setUnitFilter(next);
                                            }}
                                            className={`w-full text-left px-2 py-1.5 rounded-lg text-xs transition-all ${
                                                active
                                                    ? 'bg-nook-leaf/20 text-nook-leaf font-bold ring-1 ring-nook-leaf'
                                                    : 'bg-gray-50 text-nook-text/70 hover:bg-nook-cream/50'
                                            }`}
                                        >
                                            {active && '✓ '}{displayName}
                                        </button>
                                    );
                                })}
                            </div>
                            <p className="text-[10px] text-nook-text/50 mt-2">
                                {unitFilter.size === 0 ? '未選擇 = 顯示全部' : `已選 ${unitFilter.size} 個單位`}
                            </p>
                        </div>
                    )}

                    {/* 圈選工具 */}
                    {!editMode && (
                        <div className={`rounded-2xl p-4 nook-shadow ${selectionCircle || selectionMode ? 'bg-emerald-50 border-2 border-emerald-300' : 'bg-white/80'}`}>
                            <h3 className="font-bold text-nook-text mb-3 flex items-center gap-2">
                                <Target className="w-4 h-4 text-emerald-600" />
                                範圍圈選統計
                            </h3>
                            {!selectionCircle && !selectionMode && (
                                <button
                                    onClick={() => setSelectionMode(true)}
                                    className="w-full py-2 px-3 bg-emerald-500 text-white rounded-xl text-sm font-medium hover:bg-emerald-600 transition-colors"
                                >
                                    🎯 開始圈選
                                </button>
                            )}
                            {selectionMode && !selectionCircle && (
                                <div className="space-y-2">
                                    <p className="text-xs text-emerald-700">
                                        1. 點地圖設定中心<br />
                                        2. 再點一次決定半徑
                                    </p>
                                    <button
                                        onClick={() => { setSelectionMode(false); clickStateRef.current = 'idle'; tempCenterRef.current = null; if (selectionLayerRef.current) { selectionLayerRef.current.remove(); selectionLayerRef.current = null; } }}
                                        className="w-full py-1.5 px-3 bg-gray-400 text-white rounded-lg text-xs"
                                    >
                                        取消
                                    </button>
                                </div>
                            )}
                            {selectionCircle && selectionStats && (
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between text-xs">
                                        <span className="text-nook-text/60">半徑</span>
                                        <span className="font-bold text-emerald-700">{Math.round(selectionCircle.radius)} 公尺</span>
                                    </div>

                                    <div className="bg-white rounded-lg p-2 space-y-1">
                                        <div className="flex justify-between text-xs">
                                            <span className="text-nook-text/60">事故總數</span>
                                            <span className="font-bold text-red-600">{selectionStats.crashTotal}</span>
                                        </div>
                                        {selectionStats.severity.A1 > 0 && (
                                            <div className="flex justify-between text-[11px] pl-2">
                                                <span className="text-red-700">A1 死亡</span>
                                                <span className="font-medium">{selectionStats.severity.A1}</span>
                                            </div>
                                        )}
                                        {selectionStats.severity.A2 > 0 && (
                                            <div className="flex justify-between text-[11px] pl-2">
                                                <span className="text-orange-600">A2 受傷</span>
                                                <span className="font-medium">{selectionStats.severity.A2}</span>
                                            </div>
                                        )}
                                        {selectionStats.severity.A3 > 0 && (
                                            <div className="flex justify-between text-[11px] pl-2">
                                                <span className="text-yellow-600">A3 財損</span>
                                                <span className="font-medium">{selectionStats.severity.A3}</span>
                                            </div>
                                        )}
                                    </div>

                                    <div className="bg-white rounded-lg p-2 space-y-1">
                                        <div className="flex justify-between text-xs">
                                            <span className="text-nook-text/60">違規總數</span>
                                            <span className="font-bold text-blue-600">{selectionStats.ticketTotal}</span>
                                        </div>
                                        {selectionStats.topic.DUI > 0 && (
                                            <div className="flex justify-between text-[11px] pl-2">
                                                <span className="text-purple-600">🍺 酒駕</span>
                                                <span className="font-medium">{selectionStats.topic.DUI}</span>
                                            </div>
                                        )}
                                        {selectionStats.topic.RED_LIGHT > 0 && (
                                            <div className="flex justify-between text-[11px] pl-2">
                                                <span className="text-blue-600">🚦 闖紅燈</span>
                                                <span className="font-medium">{selectionStats.topic.RED_LIGHT}</span>
                                            </div>
                                        )}
                                        {selectionStats.topic.DANGEROUS_DRIVING > 0 && (
                                            <div className="flex justify-between text-[11px] pl-2">
                                                <span className="text-cyan-600">⚡ 危駕</span>
                                                <span className="font-medium">{selectionStats.topic.DANGEROUS_DRIVING}</span>
                                            </div>
                                        )}
                                        {selectionStats.topic.OTHER > 0 && (
                                            <div className="flex justify-between text-[11px] pl-2">
                                                <span className="text-gray-600">其他</span>
                                                <span className="font-medium">{selectionStats.topic.OTHER}</span>
                                            </div>
                                        )}
                                    </div>

                                    {selectionStats.units.length > 0 && (
                                        <div className="bg-white rounded-lg p-2">
                                            <p className="text-[10px] text-nook-text/50 mb-1">單位分布</p>
                                            {selectionStats.units.slice(0, 3).map(([unit, cnt]) => (
                                                <div key={unit} className="flex justify-between text-[10px]">
                                                    <span className="text-nook-text/70 truncate">{unit.replace(/^新化分局/, '')}</span>
                                                    <span className="font-medium">{cnt}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}

                                    <button
                                        onClick={handleClearSelection}
                                        className="w-full py-1.5 px-3 bg-gray-500 text-white rounded-lg text-xs flex items-center justify-center gap-1 hover:bg-gray-600"
                                    >
                                        <Trash2 className="w-3 h-3" />
                                        清除圈選
                                    </button>
                                </div>
                            )}
                        </div>
                    )}

                    {/* 違規篩選 */}
                    {!editMode && (
                        <div className="bg-white/80 rounded-2xl p-4 nook-shadow">
                            <h3 className="font-bold text-nook-text mb-3">📋 違規類型</h3>
                            <div className="flex flex-wrap gap-2">
                                {[
                                    { value: 'all', label: '全部', color: 'bg-gray-100 text-gray-700' },
                                    { value: 'DUI', label: '🍺 酒駕', color: 'bg-purple-100 text-purple-700' },
                                    { value: 'RED_LIGHT', label: '🚦 闘紅燈', color: 'bg-blue-100 text-blue-700' },
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
                    )}

                    {/* 圖例 */}
                    <div className="bg-nook-cream/30 rounded-2xl p-4">
                        <h3 className="font-bold text-nook-text mb-3">📌 圖例說明</h3>
                        <div className="space-y-2 text-xs text-nook-text/70">
                            <div className="flex items-center gap-2">
                                <span className="w-3 h-3 rounded-full bg-red-600"></span>
                                <span>A1 死亡事故</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="w-3 h-3 rounded-full bg-orange-500"></span>
                                <span>A2 受傷事故</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="w-3 h-3 rounded-full bg-yellow-500"></span>
                                <span>A3 財損事故</span>
                            </div>
                            {!editMode && (
                                <>
                                    <div className="flex items-center gap-2 pt-2 border-t border-nook-cream">
                                        <span className="w-3 h-3 rounded-full bg-purple-500"></span>
                                        <span>酒駕違規</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="w-3 h-3 rounded-full bg-blue-500"></span>
                                        <span>闘紅燈違規</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="w-3 h-3 rounded-full bg-cyan-500"></span>
                                        <span>危險駕駛違規</span>
                                    </div>
                                    <div className="mt-2 pt-2 border-t border-nook-cream/50 text-[10px] text-nook-text/50">
                                        <p className="font-medium text-nook-text/60 mb-1">危險駕駛涵蓋：</p>
                                        <p>超速、逼車、競速、蛇行、甩尾、任意變換車道、未保持安全距離、肇事逃逸等</p>
                                    </div>
                                </>
                            )}
                        </div>
                    </div>
                </div>

                {/* 地圖區域 */}
                <div className="col-span-9">
                    <div className={`bg-white/80 rounded-2xl nook-shadow overflow-hidden ${editMode ? 'ring-4 ring-amber-300' : ''}`}>
                        {/* 地圖標題 */}
                        <div className={`p-3 border-b flex items-center justify-between ${editMode ? 'bg-amber-50 border-amber-200' : 'border-nook-cream/50 bg-white/50'}`}>
                            <div className="flex items-center gap-2">
                                <MapIcon className={`w-5 h-5 ${editMode ? 'text-amber-600' : 'text-nook-leaf'}`} />
                                <span className="font-bold text-nook-text">
                                    {editMode ? '📍 編輯模式 - 拖曳點位以校正位置' : '精準點位地圖'}
                                </span>
                            </div>
                            {loading && (
                                <span className="text-xs text-nook-text/50 flex items-center gap-1">
                                    <RefreshCw className="w-3 h-3 animate-spin" />
                                    載入中...
                                </span>
                            )}
                            {!loading && data && !editMode && (
                                <span className="text-xs text-nook-text/50">
                                    顯示 {data.summary.crashes_with_coords + data.summary.tickets_with_coords} 個點位
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
                                    目前匯入的資料沒有經緯度座標。請重新匯入資料以自動分配區域座標。
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
