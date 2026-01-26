import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { apiClient, ReportResponse } from '../api/client';
import { Leaf, Calendar, Printer, BarChart3, Bot, Settings, Key, AlertTriangle, X } from 'lucide-react';

// Provider & Model Definitions
const PROVIDER_MODELS: Record<string, { name: string; value: string }[]> = {
    openai: [
        { name: 'GPT-5 Pro (Latest)', value: 'gpt-5-pro' },
        { name: 'GPT-4o (Omni)', value: 'gpt-4o' },
        { name: 'OpenAI o3 (Reasoning)', value: 'openai-o3' },
        { name: 'GPT-4.5 Preview', value: 'gpt-4.5-preview' }
    ],
    anthropic: [
        { name: 'Claude 4 Opus (Latest)', value: 'claude-4-opus' },
        { name: 'Claude 3.5 Sonnet', value: 'claude-3-5-sonnet-20240620' },
        { name: 'Claude Haiku 4.5', value: 'claude-haiku-4.5' }
    ],
    gemini: [
        { name: 'Gemini 3 Pro (Latest)', value: 'gemini-3-pro' },
        { name: 'Gemini 2.5 Flash', value: 'gemini-2.5-flash' },
        { name: 'Gemini 3 Deep Think', value: 'gemini-3-deep-think' }
    ],
    ollama: [
        { name: 'Llama 3 (8B)', value: 'llama3' },
        { name: 'Llama 3 (70B)', value: 'llama3:70b' },
        { name: 'Mistral (7B)', value: 'mistral' },
        { name: 'Gemma 2 (9B)', value: 'gemma:latest' },
        { name: 'Custom Model...', value: 'custom' }
    ]
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
        // For Ollama, key is optional (send 'local' if empty to satisfy non-empty check if needed, or just let it be empty)
        const finalKey = isLocal && !key ? 'local-ollama' : key;

        onSave(finalKey, provider, finalModel);
        onClose();
    };

    return (
        <div className="fixed inset-0 bg-black/50 z-[60] flex items-center justify-center p-4 backdrop-blur-sm">
            <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in duration-200">
                <div className="p-6 bg-gradient-to-r from-stone-800 to-stone-700 text-white flex justify-between items-center">
                    <h3 className="text-lg font-bold flex items-center gap-2">
                        <Key className="w-5 h-5 text-emerald-400" />
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
                            <label className="block text-sm font-medium text-stone-700 mb-2">
                                供應商
                            </label>
                            <select
                                value={provider}
                                onChange={(e) => handleProviderChange(e.target.value)}
                                className="w-full px-4 py-2 rounded-xl border border-stone-200 focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white"
                            >
                                <option value="openai">OpenAI</option>
                                <option value="anthropic">Anthropic</option>
                                <option value="gemini">Google</option>
                                <option value="ollama">Ollama (Local)</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-stone-700 mb-2">
                                模型
                            </label>
                            <select
                                value={model}
                                onChange={(e) => setModel(e.target.value)}
                                className="w-full px-4 py-2 rounded-xl border border-stone-200 focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white"
                            >
                                {PROVIDER_MODELS[provider]?.map(m => (
                                    <option key={m.value} value={m.value}>{m.name}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    {/* Custom Model Input for Ollama */}
                    {isLocal && model === 'custom' && (
                        <div>
                            <label className="block text-sm font-medium text-stone-700 mb-2">
                                自訂模型名稱 (需已下載)
                            </label>
                            <input
                                type="text"
                                value={customModel}
                                onChange={(e) => setCustomModel(e.target.value)}
                                placeholder="例如: llama3:latest"
                                className="w-full px-4 py-2 rounded-xl border border-stone-200 focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white"
                                required
                            />
                        </div>
                    )}

                    {!isLocal && (
                        <div>
                            <label className="block text-sm font-medium text-stone-700 mb-2">
                                API Key
                            </label>
                            <input
                                type="password"
                                value={key}
                                onChange={(e) => setKey(e.target.value)}
                                placeholder={`Enter ${provider} API Key...`}
                                className="w-full px-4 py-2 rounded-xl border border-stone-200 focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white font-mono"
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

                    <div className="pt-2 flex justify-end gap-3">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 rounded-xl text-stone-500 hover:bg-stone-100 transition-colors"
                        >
                            取消
                        </button>
                        <button
                            type="submit"
                            className="px-6 py-2 bg-stone-800 text-white rounded-xl hover:bg-stone-900 transition-colors font-medium shadow-lg shadow-stone-200"
                        >
                            確認使用
                        </button>
                    </div>
                </form>
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

    // API Key State (Memory Only)
    const [apiKey, setApiKey] = useState<string>('');
    const [provider, setProvider] = useState<string>('openai');
    const [model, setModel] = useState<string>('gpt-4o');
    const [showKeyModal, setShowKeyModal] = useState(false);

    const handleGenerate = async () => {
        // 如果沒有 Key，先提示設定
        if (!apiKey) {
            setShowKeyModal(true);
            return;
        }

        setLoading(true);
        setError(null);
        try {
            const data = await apiClient.generateAIReport(year, month, apiKey, provider, model);
            setReport(data);
        } catch (err) {
            console.error(err);
            setError('報告生成失敗，請檢查 API Key 是否正確或稍後再試');
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
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-6 rounded-3xl shadow-sm border border-stone-100 print:hidden">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2 text-stone-800">
                        <Bot className="w-8 h-8 text-emerald-600" />
                        AI 智慧執法報告
                    </h1>
                    <p className="text-stone-500 mt-1">基於數據驅動的執法成效分析與建議</p>
                </div>

                <div className="flex gap-3 bg-stone-50 p-2 rounded-2xl">
                    <button
                        onClick={() => setShowKeyModal(true)}
                        className={`px-4 py-2 rounded-xl flex items-center gap-2 transition-all border ${apiKey
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : 'bg-white text-stone-600 border-stone-200 hover:bg-stone-100'}`}
                        title="設定 API Key"
                    >
                        <Settings className="w-4 h-4" />
                        {apiKey ? 'API 已設定' : 'API 設定'}
                    </button>

                    <div className="w-px bg-stone-200 mx-1"></div>

                    <select
                        value={year}
                        onChange={(e) => setYear(Number(e.target.value))}
                        className="px-4 py-2 rounded-xl border border-stone-200 focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white"
                    >
                        {[2024, 2025, 2026].map(y => (
                            <option key={y} value={y}>{y}年</option>
                        ))}
                    </select>
                    <select
                        value={month}
                        onChange={(e) => setMonth(Number(e.target.value))}
                        className="px-4 py-2 rounded-xl border border-stone-200 focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white"
                    >
                        {Array.from({ length: 12 }, (_, i) => i + 1).map(m => (
                            <option key={m} value={m}>{m}月</option>
                        ))}
                    </select>
                    <button
                        onClick={handleGenerate}
                        disabled={loading}
                        className={`px-6 py-2 text-white rounded-xl hover:shadow-lg transition-all font-medium flex items-center gap-2
                            ${apiKey ? 'bg-emerald-600 hover:bg-emerald-700 shadow-emerald-200' : 'bg-stone-400 hover:bg-stone-500'}
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

            {/* Error Message */}
            {error && (
                <div className="bg-red-50 text-red-600 p-4 rounded-xl flex items-center gap-2 border border-red-100 print:hidden">
                    <Leaf className="w-5 h-5" />
                    {error}
                </div>
            )}

            {/* Report Content */}
            {report && (
                <div className="report-container bg-white rounded-3xl shadow-lg border border-stone-100 overflow-hidden print:shadow-none print:border-none print:w-full">
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
                    <div className="bg-emerald-600 text-white p-8 print:bg-white print:text-black print:p-0 print:mb-8">
                        <div className="flex justify-between items-start">
                            <div>
                                <h2 className="text-3xl font-bold mb-2">交通執法成效與事故防制分析報告</h2>
                                <p className="text-emerald-100 print:text-stone-500">
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
                                <p className="text-sm text-stone-400">生成時間：{new Date().toLocaleDateString()}</p>
                                <p className="text-sm text-stone-400">機密等級：內部限閱</p>
                            </div>
                        </div>
                    </div>

                    {/* Markdown Content */}
                    <div className="p-8 md:p-12 max-w-4xl mx-auto prose prose-emerald prose-lg print:max-w-none print:p-0">
                        <ReactMarkdown
                            components={{
                                h1: ({ node, ...props }: any) => <h1 className="text-3xl font-bold text-stone-800 mb-6 pb-4 border-b-2 border-emerald-500" {...props} />,
                                h2: ({ node, ...props }: any) => <h2 className="text-2xl font-bold text-stone-800 mt-8 mb-4 flex items-center gap-2" {...props} />,
                                h3: ({ node, ...props }: any) => <h3 className="text-xl font-bold text-emerald-800 mt-6 mb-3" {...props} />,
                                p: ({ node, ...props }: any) => <p className="text-stone-600 leading-relaxed mb-4" {...props} />,
                                ul: ({ node, ...props }: any) => <ul className="list-disc list-outside ml-6 space-y-2 mb-6" {...props} />,
                                li: ({ node, ...props }: any) => <li className="text-stone-600" {...props} />,
                                strong: ({ node, ...props }: any) => <strong className="font-bold text-stone-800 bg-yellow-50 px-1 rounded" {...props} />,
                            }}
                        >
                            {report.ai_analysis.content}
                        </ReactMarkdown>
                    </div>

                    {/* Footer */}
                    <div className="bg-stone-50 p-6 text-center text-sm text-stone-400 border-t border-stone-100 print:hidden">
                        報告由 {report.ai_analysis.provider} ({report.ai_analysis.model}) 生成 • 僅供參考，決策請以實際情況為準
                    </div>
                </div>
            )}

            {/* Empty State */}
            {!report && !loading && !error && (
                <div className="text-center py-20 bg-stone-50 rounded-3xl border border-dashed border-stone-200 print:hidden">
                    <Bot className="w-16 h-16 text-stone-300 mx-auto mb-4" />
                    <h3 className="text-xl font-bold text-stone-400 mb-2">AI 智慧分析助手</h3>
                    <p className="text-stone-400 max-w-md mx-auto mb-6">
                        請先點擊上方「API 設定」輸入您的 OpenAI/Gemini 金鑰，<br />
                        系統將根據本月數據自動撰寫專業分析報告。
                    </p>

                    {!apiKey && (
                        <button
                            onClick={() => setShowKeyModal(true)}
                            className="px-6 py-2 bg-stone-800 text-white rounded-xl hover:bg-stone-900 transition-colors font-medium shadow-lg shadow-stone-200 inline-flex items-center gap-2"
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
