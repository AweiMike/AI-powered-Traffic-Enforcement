import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { apiClient, ReportResponse } from '../api/client';
import { Leaf, Printer, BarChart3, Bot, Settings, Key, AlertTriangle, X, ChevronDown, ChevronUp, Database } from 'lucide-react';

// Provider & Model Definitions（僅列出經驗證真實可呼叫的 model id）
// 若將來出現新版，只需在此加入即可，無需改其他檔案
const PROVIDER_MODELS: Record<string, { name: string; value: string; hint?: string }[]> = {
    openai: [
        { name: 'GPT-5（最新旗艦）', value: 'gpt-5', hint: '2025/08 發布，最強分析能力，推理模式' },
        { name: 'GPT-5 mini（便宜旗艦）', value: 'gpt-5-mini', hint: '便宜、快速，適合測試' },
        { name: 'GPT-4.1（高性價比）', value: 'gpt-4.1', hint: '2025/04 穩定版，支援溫度調整' },
        { name: 'GPT-4o（舊版穩定）', value: 'gpt-4o', hint: '上一代旗艦，完全穩定' },
        { name: 'o3（深度推理）', value: 'o3', hint: '擅長複雜邏輯，但較慢較貴' },
        { name: 'o4-mini（快速推理）', value: 'o4-mini', hint: '經濟型推理模型' },
    ],
    anthropic: [
        { name: 'Claude Opus 4.5（最新旗艦）', value: 'claude-opus-4-5', hint: '2025/11 發布，分析與寫作最強' },
        { name: 'Claude Sonnet 4.5（推薦）', value: 'claude-sonnet-4-5', hint: '高性價比、速度快、品質優' },
        { name: 'Claude Opus 4.1', value: 'claude-opus-4-1', hint: '上一代旗艦' },
        { name: 'Claude 3.5 Haiku（最便宜）', value: 'claude-3-5-haiku-20241022', hint: '便宜快速，適合測試' },
    ],
    gemini: [
        { name: 'Gemini 2.5 Pro（推薦）', value: 'gemini-2.5-pro', hint: '品質最佳，長文分析能力強' },
        { name: 'Gemini 2.5 Flash（快速）', value: 'gemini-2.5-flash', hint: '快速便宜，免費額度高' },
        { name: 'Gemini 2.5 Flash Lite', value: 'gemini-2.5-flash-lite', hint: '最經濟，適合大量測試' },
        { name: 'Gemini 2.0 Flash', value: 'gemini-2.0-flash', hint: '上一代穩定版' },
    ],
    ollama: [
        { name: 'Llama 3.1 (8B)', value: 'llama3.1', hint: '需先 ollama pull llama3.1' },
        { name: 'Qwen 2.5 (7B) 中文好', value: 'qwen2.5', hint: '需先 ollama pull qwen2.5' },
        { name: 'Mistral (7B)', value: 'mistral', hint: '需先 ollama pull mistral' },
        { name: '自訂模型名稱...', value: 'custom' },
    ],
    mock: [
        { name: 'Mock（測試用，無需 API Key）', value: 'mock', hint: '使用模擬回應測試資料流與版型，不呼叫真實 LLM' },
    ],
};

// API Key Modal Component
interface ApiKeyModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSave: (key: string, provider: string, model: string) => void;
    currentProvider: string;
    currentModel: string;
}

const ApiKeyModal: React.FC<ApiKeyModalProps> = ({ isOpen, onClose, onSave, currentProvider, currentModel }) => {
    const [key, setKey] = useState('');
    const [provider, setProvider] = useState(currentProvider);
    const [model, setModel] = useState(currentModel);
    const [customModel, setCustomModel] = useState('');

    const isLocal = provider === 'ollama';
    const isMock = provider === 'mock';
    const needsKey = !isLocal && !isMock;

    // Reset model when provider changes (default to first option)
    const handleProviderChange = (newProvider: string) => {
        setProvider(newProvider);
        const models = PROVIDER_MODELS[newProvider];
        if (models && models.length > 0) {
            setModel(models[0].value);
        }
    };

    if (!isOpen) return null;

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        // For Ollama, we might use custom model name if 'custom' is selected
        const finalModel = (provider === 'ollama' && model === 'custom') ? customModel : model;
        // Mock + Ollama 不需要真正的 key，塞個 marker 字串讓前端 `if (!apiKey)` 邏輯能通過
        let finalKey = key;
        if (isMock) finalKey = 'mock-mode';
        else if (isLocal && !key) finalKey = 'local-ollama';

        onSave(finalKey, provider, finalModel);
        onClose();
    };

    return (
        <div className="fixed inset-0 bg-black/50 z-[60] flex items-center justify-center p-4 backdrop-blur-sm">
            <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in duration-200">
                <div className="p-6 bg-gradient-to-r from-slate-800 to-slate-700 text-white flex justify-between items-center">
                    <h3 className="text-lg font-bold flex items-center gap-2">
                        <Key className="w-5 h-5 text-sky-400" />
                        設定 AI 模型金鑰
                    </h3>
                    <button onClick={onClose} className="text-white/70 hover:text-white transition-colors">
                        <X className="w-6 h-6" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex gap-3 text-amber-800 text-sm">
                        <AlertTriangle className="w-5 h-5 shrink-0" />
                        <div>
                            <p className="font-bold mb-1">隱私安全聲明</p>
                            <p>您的 API Key 僅會暫存於記憶體並透過加密連線傳送，<strong>不會儲存於任何資料庫或日誌中</strong>。重新整理頁面後即會清除。</p>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">
                                供應商
                            </label>
                            <select
                                value={provider}
                                onChange={(e) => handleProviderChange(e.target.value)}
                                className="w-full px-4 py-2 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
                            >
                                <option value="mock">🧪 Mock（測試）</option>
                                <option value="openai">OpenAI</option>
                                <option value="anthropic">Anthropic</option>
                                <option value="gemini">Google Gemini</option>
                                <option value="ollama">Ollama（本地）</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">
                                模型
                            </label>
                            <select
                                value={model}
                                onChange={(e) => setModel(e.target.value)}
                                className="w-full px-4 py-2 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
                            >
                                {PROVIDER_MODELS[provider]?.map(m => (
                                    <option key={m.value} value={m.value}>{m.name}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    {/* 模型提示 */}
                    {PROVIDER_MODELS[provider]?.find(m => m.value === model)?.hint && (
                        <div className="text-[11px] text-slate-500 -mt-2 pl-1">
                            💡 {PROVIDER_MODELS[provider]?.find(m => m.value === model)?.hint}
                        </div>
                    )}

                    {/* Custom Model Input for Ollama */}
                    {isLocal && model === 'custom' && (
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">
                                自訂模型名稱 (需已下載)
                            </label>
                            <input
                                type="text"
                                value={customModel}
                                onChange={(e) => setCustomModel(e.target.value)}
                                placeholder="例如: llama3:latest"
                                className="w-full px-4 py-2 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
                                required
                            />
                        </div>
                    )}

                    {needsKey && (
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">
                                API Key
                            </label>
                            <input
                                type="password"
                                value={key}
                                onChange={(e) => setKey(e.target.value)}
                                placeholder={`Enter ${provider} API Key...`}
                                className="w-full px-4 py-2 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white font-mono"
                                required
                            />
                        </div>
                    )}

                    {isLocal && (
                        <div className="bg-blue-50 text-blue-800 text-sm p-3 rounded-lg space-y-2">
                            <p>正在使用本地 Ollama (http://localhost:11434)。無需 API Key。</p>
                            <div className="bg-blue-100 p-2 rounded border border-blue-200 text-xs font-mono">
                                <strong>⚠️ 錯誤排查：</strong><br />
                                若出現 "model not found"，請開啟終端機執行：<br />
                                <code>ollama pull {model === 'custom' ? (customModel || '模型名稱') : model}</code>
                            </div>
                        </div>
                    )}

                    {isMock && (
                        <div className="bg-amber-50 text-amber-800 text-sm p-3 rounded-lg space-y-1.5">
                            <p className="font-bold">🧪 Mock 測試模式</p>
                            <p className="text-xs">不呼叫真實 LLM，由後端直接根據資料組裝樣板報告。</p>
                            <p className="text-xs">用途：驗證資料撈取、prompt 組裝、前端版型，不花 API 費用。</p>
                        </div>
                    )}

                    <div className="pt-2 flex justify-end gap-3">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 rounded-xl text-slate-500 hover:bg-slate-100 transition-colors"
                        >
                            取消
                        </button>
                        <button
                            type="submit"
                            className="px-6 py-2 bg-slate-800 text-white rounded-xl hover:bg-slate-900 transition-colors font-medium shadow-lg shadow-slate-200"
                        >
                            確認使用
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

// ============================================
// Raw Data 檢視元件 — 將後端回傳的 JSON 統計轉成可讀表格
// 讓使用者驗證 AI 是否基於真實數據
// ============================================
const RawDataView: React.FC<{ data: any }> = ({ data }) => {
    if (!data) return <div className="text-slate-400 text-sm">無資料</div>;

    const period = data.period || {};
    const overall = data.overall_stats || {};
    const topics = data.topics || {};
    const severity = data.severity || {};
    const subtypes = data.enforcement_subtypes || {};
    const units = data.unit_stats || [];
    const accidentHot = data.accident_hotspots || [];
    const violationHot = data.violation_hotspots || [];
    const focusDistricts = data.focus_districts || [];
    const focusCauses = data.focus_causes || [];

    const StatRow: React.FC<{ label: string; stat: any }> = ({ label, stat }) => (
        <div className="flex justify-between py-1 text-xs">
            <span className="text-slate-600">{label}</span>
            <span className="tabular-nums">
                <span className="font-semibold text-slate-800">{stat?.current ?? 0}</span>
                <span className="text-slate-400 mx-1">/ 去年 {stat?.last_year ?? 0}</span>
                <span className={`ml-1 ${stat?.change_pct > 0 ? 'text-danger' : stat?.change_pct < 0 ? 'text-success' : 'text-slate-400'}`}>
                    ({stat?.change_pct > 0 ? '+' : ''}{stat?.change_pct ?? 0}%)
                </span>
            </span>
        </div>
    );

    return (
        <div className="space-y-4 text-sm">
            {/* 區間完整性警示（若不完整）*/}
            {period.is_partial && (
                <div className="bg-amber-50 border border-amber-300 rounded-xl p-3 text-xs text-amber-900">
                    <div className="font-semibold mb-1">⚠ 資料涵蓋警示</div>
                    <div>
                        本期 <span className="font-mono tabular-nums">{period.start_date} ~ {period.actual_end_date}</span>
                        （共 <strong className="tabular-nums">{period.days_covered}</strong> 天）。
                        下方所有「本期 vs 去年」的比較，去年同期已自動對齊為相同天數，
                        避免「半個月 vs 完整月」的假象。
                    </div>
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 總體 + 主題 */}
            <div className="bg-slate-50 rounded-xl p-4 space-y-2">
                <h4 className="font-semibold text-slate-700 text-xs uppercase tracking-wider mb-2">📊 總體與主題</h4>
                <StatRow label="總違規" stat={overall.tickets} />
                <StatRow label="總事故" stat={overall.accidents} />
                <StatRow label="A1+A2 傷亡" stat={overall.injuries} />
                <div className="h-px bg-slate-200 my-2" />
                <StatRow label="酒駕" stat={topics.dui} />
                <StatRow label="闖紅燈" stat={topics.red_light} />
                <StatRow label="危險駕駛" stat={topics.dangerous} />
            </div>

            {/* 嚴重度 + 舉發子類型 */}
            <div className="bg-slate-50 rounded-xl p-4 space-y-2">
                <h4 className="font-semibold text-slate-700 text-xs uppercase tracking-wider mb-2">🚑 嚴重度 & 舉發類型</h4>
                <div className="flex justify-between text-xs">
                    <span className="text-slate-600">A1 死亡</span>
                    <span className="font-semibold text-danger tabular-nums">{severity.A1 ?? 0}</span>
                </div>
                <div className="flex justify-between text-xs">
                    <span className="text-slate-600">A2 受傷</span>
                    <span className="font-semibold text-warning tabular-nums">{severity.A2 ?? 0}</span>
                </div>
                <div className="flex justify-between text-xs">
                    <span className="text-slate-600">A3 財損</span>
                    <span className="font-semibold text-slate-600 tabular-nums">{severity.A3 ?? 0}</span>
                </div>
                <div className="h-px bg-slate-200 my-2" />
                {Object.entries(subtypes).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs">
                        <span className="text-slate-600">{k}</span>
                        <span className="tabular-nums text-slate-700">{String(v)}</span>
                    </div>
                ))}
            </div>

            {/* 派出所 */}
            <div className="bg-slate-50 rounded-xl p-4 space-y-1.5">
                <h4 className="font-semibold text-slate-700 text-xs uppercase tracking-wider mb-2">🏢 派出所表現 Top {units.length}</h4>
                {units.length === 0 && <div className="text-xs text-slate-400">無資料</div>}
                {units.map((u: any, i: number) => (
                    <div key={i} className="flex justify-between text-xs">
                        <span className="text-slate-700">{u.unit}</span>
                        <span className="text-slate-500 tabular-nums">
                            事故 <span className="text-warning font-semibold">{u.crashes}</span> · 違規 <span className="text-accent font-semibold">{u.tickets}</span>
                        </span>
                    </div>
                ))}
            </div>

            {/* 熱點 */}
            <div className="bg-slate-50 rounded-xl p-4 space-y-2">
                <h4 className="font-semibold text-slate-700 text-xs uppercase tracking-wider mb-2">📍 熱點 Top 3</h4>
                <div className="text-[11px] text-slate-500 font-medium">事故</div>
                {accidentHot.slice(0, 3).map((h: any, i: number) => (
                    <div key={i} className="flex justify-between text-xs pl-2">
                        <span className="text-slate-700 truncate max-w-[70%]">{i + 1}. {h.district} {h.location}</span>
                        <span className="tabular-nums text-slate-500">{h.count}</span>
                    </div>
                ))}
                <div className="text-[11px] text-slate-500 font-medium mt-2">違規</div>
                {violationHot.slice(0, 3).map((h: any, i: number) => (
                    <div key={i} className="flex justify-between text-xs pl-2">
                        <span className="text-slate-700 truncate max-w-[70%]">{i + 1}. {h.district} {h.location}</span>
                        <span className="tabular-nums text-slate-500">{h.count}</span>
                    </div>
                ))}
            </div>

            {/* 重點關注 — 橫跨兩欄 */}
            {(focusCauses.length > 0 || focusDistricts.length > 0) && (
                <div className="md:col-span-2 bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-1">
                    <h4 className="font-semibold text-amber-800 text-xs uppercase tracking-wider mb-2">⚠ AI 關注重點（自動偵測）</h4>
                    {focusCauses.map((c: string, i: number) => (
                        <div key={i} className="text-xs text-amber-700">• {c}</div>
                    ))}
                    {focusDistricts.map((d: string, i: number) => (
                        <div key={`d-${i}`} className="text-xs text-amber-700">• {d}</div>
                    ))}
                </div>
            )}
            </div>
        </div>
    );
};

const AIReportPage: React.FC = () => {
    const [year, setYear] = useState(new Date().getFullYear());
    const [month, setMonth] = useState(new Date().getMonth() + 1);
    const [loading, setLoading] = useState(false);
    const [report, setReport] = useState<ReportResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

    // API Key State (Memory Only) — 預設為 Mock 模式便於測試
    const [apiKey, setApiKey] = useState<string>('mock-mode');
    const [provider, setProvider] = useState<string>('mock');
    const [model, setModel] = useState<string>('mock');
    const [showKeyModal, setShowKeyModal] = useState(false);
    const [showRawData, setShowRawData] = useState(false);

    const handleGenerate = async () => {
        // 如果沒有 Key，先提示設定
        if (!apiKey) {
            setShowKeyModal(true);
            return;
        }

        setLoading(true);
        setError(null);
        setReport(null);
        try {
            const data = await apiClient.generateAIReport(year, month, apiKey, provider, model);
            setReport(data);
        } catch (err: any) {
            console.error(err);
            // 嘗試從 fetch error 中提取後端回傳的 detail 訊息
            let msg = '報告生成失敗';
            if (err?.message) {
                msg += '：' + err.message;
            }
            // 如果後端回傳 JSON detail，通常會 attach 在 err.detail
            if (err?.detail) {
                msg = err.detail;
            }
            setError(msg);
        } finally {
            setLoading(false);
        }
    };

    const handleKeySave = (key: string, newProvider: string, newModel: string) => {
        setApiKey(key);
        setProvider(newProvider);
        setModel(newModel);
        // 自動觸發生成 (User experience optimization)
        setTimeout(() => {
            // 這裡不直接調用 handleGenerate，避免閉包問題，使用者需再點一次或我們用 useEffect
            // 簡單起見，讓使用者手動點擊，或顯示 Key 已設定
        }, 100);
    };

    const handlePrint = () => {
        window.print();
    };

    return (
        <div className="p-6 space-y-6 max-w-5xl mx-auto">
            {/* API Key Modal */}
            <ApiKeyModal
                isOpen={showKeyModal}
                onClose={() => setShowKeyModal(false)}
                onSave={handleKeySave}
                currentProvider={provider}
                currentModel={model}
            />

            {/* Header - Print Hidden */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-6 rounded-3xl shadow-sm border border-slate-100 print:hidden">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2 text-slate-800">
                        <Bot className="w-8 h-8 text-sky-700" />
                        AI 智慧執法報告
                    </h1>
                    <p className="text-slate-500 mt-1">基於數據驅動的執法成效分析與建議</p>
                </div>

                <div className="flex gap-3 bg-slate-50 p-2 rounded-2xl">
                    <button
                        onClick={() => setShowKeyModal(true)}
                        className={`px-4 py-2 rounded-xl flex items-center gap-2 transition-all border ${apiKey && apiKey !== 'mock-mode'
                            ? 'bg-sky-50 text-sky-700 border-sky-200'
                            : provider === 'mock'
                                ? 'bg-amber-50 text-amber-700 border-amber-200'
                                : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-100'}`}
                        title="設定 AI 模型"
                    >
                        <Settings className="w-4 h-4" />
                        {provider === 'mock' ? 'Mock 測試' : (apiKey ? `${provider} 已設定` : 'API 設定')}
                    </button>

                    <div className="w-px bg-slate-200 mx-1"></div>

                    <select
                        value={year}
                        onChange={(e) => setYear(Number(e.target.value))}
                        className="px-4 py-2 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
                    >
                        {[2024, 2025, 2026].map(y => (
                            <option key={y} value={y}>{y}年</option>
                        ))}
                    </select>
                    <select
                        value={month}
                        onChange={(e) => setMonth(Number(e.target.value))}
                        className="px-4 py-2 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
                    >
                        {Array.from({ length: 12 }, (_, i) => i + 1).map(m => (
                            <option key={m} value={m}>{m}月</option>
                        ))}
                    </select>
                    <button
                        onClick={handleGenerate}
                        disabled={loading}
                        className={`px-6 py-2 text-white rounded-xl hover:shadow-lg transition-all font-medium flex items-center gap-2
                            ${apiKey ? 'bg-sky-700 hover:bg-sky-700 shadow-sky-200' : 'bg-slate-400 hover:bg-slate-500'}
                        `}
                    >
                        {loading ? (
                            <>
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                分析中...
                            </>
                        ) : (
                            <>
                                <BarChart3 className="w-4 h-4" />
                                生成報告
                            </>
                        )}
                    </button>
                </div>
            </div>

            {/* Error Message — 支援多行訊息 */}
            {error && (
                <div className="bg-red-50 text-red-700 p-4 rounded-xl flex gap-3 border border-red-200 print:hidden">
                    <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5 text-red-500" />
                    <div className="text-sm leading-relaxed whitespace-pre-line">{error}</div>
                </div>
            )}

            {/* Report Content */}
            {report && (
                <div className="report-container bg-white rounded-3xl shadow-lg border border-slate-100 overflow-hidden print:shadow-none print:border-none print:w-full">
                    <style>{`
                        @media print {
                            body * {
                                visibility: hidden;
                            }
                            .report-container, .report-container * {
                                visibility: visible;
                            }
                            .report-container {
                                position: absolute;
                                left: 0;
                                top: 0;
                                width: 100%;
                            }
                            /* Hide sidebar and other layout elements specifically if possible */
                            nav, aside, header {
                                display: none !important;
                            }
                        }
                    `}</style>

                    {/* Report Header for Print */}
                    <div className="bg-sky-700 text-white p-8 print:bg-white print:text-black print:p-0 print:mb-8">
                        <div className="flex justify-between items-start">
                            <div>
                                <h2 className="text-3xl font-bold mb-2">交通執法成效與事故防制分析報告</h2>
                                <p className="text-sky-100 print:text-slate-500">
                                    分析期間：{report.period.year}年{report.period.month}月
                                </p>
                            </div>
                            <div className="print:hidden">
                                <button
                                    onClick={handlePrint}
                                    className="p-2 bg-white/20 hover:bg-white/30 rounded-lg text-white transition-colors"
                                    title="列印報告"
                                >
                                    <Printer className="w-6 h-6" />
                                </button>
                            </div>
                            <div className="hidden print:block text-right">
                                <p className="text-sm text-slate-400">生成時間：{new Date().toLocaleDateString()}</p>
                                <p className="text-sm text-slate-400">機密等級：內部限閱</p>
                            </div>
                        </div>
                    </div>

                    {/* Markdown Content */}
                    <div className="p-8 md:p-12 max-w-4xl mx-auto prose prose-emerald prose-lg print:max-w-none print:p-0">
                        <ReactMarkdown
                            components={{
                                h1: ({ node, ...props }: any) => <h1 className="text-3xl font-bold text-slate-800 mb-6 pb-4 border-b-2 border-sky-600" {...props} />,
                                h2: ({ node, ...props }: any) => <h2 className="text-2xl font-bold text-slate-800 mt-8 mb-4 flex items-center gap-2" {...props} />,
                                h3: ({ node, ...props }: any) => <h3 className="text-xl font-bold text-sky-800 mt-6 mb-3" {...props} />,
                                p: ({ node, ...props }: any) => <p className="text-slate-600 leading-relaxed mb-4" {...props} />,
                                ul: ({ node, ...props }: any) => <ul className="list-disc list-outside ml-6 space-y-2 mb-6" {...props} />,
                                li: ({ node, ...props }: any) => <li className="text-slate-600" {...props} />,
                                strong: ({ node, ...props }: any) => <strong className="font-bold text-slate-800 bg-sky-50 px-1 rounded" {...props} />,
                            }}
                        >
                            {report.ai_analysis.content}
                        </ReactMarkdown>
                    </div>

                    {/* Raw Data 檢視 — 驗證 AI 是否基於真實資料 */}
                    <div className="border-t border-slate-100 print:hidden">
                        <button
                            onClick={() => setShowRawData(!showRawData)}
                            className="w-full px-6 py-3 flex items-center justify-between text-sm text-slate-600 hover:bg-slate-50 transition-colors"
                        >
                            <span className="flex items-center gap-2">
                                <Database className="w-4 h-4" />
                                <span className="font-medium">檢視 AI 使用的原始資料</span>
                                <span className="text-xs text-slate-400">（驗證 AI 是否編造數據）</span>
                            </span>
                            {showRawData ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        </button>

                        {showRawData && (
                            <div className="px-6 pb-6 space-y-4">
                                <RawDataView data={report.raw_data} />
                                <details className="text-xs">
                                    <summary className="cursor-pointer text-slate-500 hover:text-slate-700 py-2">
                                        展開完整 JSON（開發者用）
                                    </summary>
                                    <pre className="mt-2 p-3 bg-slate-900 text-slate-100 rounded-lg overflow-x-auto text-[10px] leading-relaxed">
                                        {JSON.stringify(report.raw_data, null, 2)}
                                    </pre>
                                </details>
                            </div>
                        )}
                    </div>

                    {/* Footer */}
                    <div className="bg-slate-50 p-6 text-center text-sm text-slate-400 border-t border-slate-100 print:hidden">
                        報告由 <span className="font-mono">{report.ai_analysis.provider}</span> / <span className="font-mono">{report.ai_analysis.model}</span> 生成 • 僅供參考，決策請以實際情況為準
                    </div>
                </div>
            )}

            {/* Empty State */}
            {!report && !loading && !error && (
                <div className="text-center py-20 bg-slate-50 rounded-3xl border border-dashed border-slate-200 print:hidden">
                    <Bot className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                    <h3 className="text-xl font-bold text-slate-400 mb-2">AI 智慧分析助手</h3>
                    <p className="text-slate-400 max-w-md mx-auto mb-6">
                        請先點擊上方「API 設定」輸入您的 OpenAI/Gemini 金鑰，<br />
                        系統將根據本月數據自動撰寫專業分析報告。
                    </p>

                    {!apiKey && (
                        <button
                            onClick={() => setShowKeyModal(true)}
                            className="px-6 py-2 bg-slate-800 text-white rounded-xl hover:bg-slate-900 transition-colors font-medium shadow-lg shadow-slate-200 inline-flex items-center gap-2"
                        >
                            <Key className="w-4 h-4" />
                            輸入 API Key
                        </button>
                    )}
                </div>
            )}
        </div>
    );
};

export default AIReportPage;
