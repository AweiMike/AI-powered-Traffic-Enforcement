/**
 * 資料匯入頁面元件
 * Animal Crossing 風格的 Excel 上傳介面
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { Upload, FileSpreadsheet, CheckCircle, XCircle, Loader2, Database, AlertCircle } from 'lucide-react';

// API 基礎 URL
const API_BASE = 'http://localhost:8080/api/v1';

// ============================================
// 型別定義
// ============================================
interface ImportStats {
  total: number;
  new: number;
  skipped: number;
  errors: number;
}

interface ImportResult {
  success: boolean;
  message: string;
  batch_id: string;
  stats: ImportStats;
  errors: string[];
  database: {
    total_crashes?: number;
    total_tickets?: number;
    severity?: Record<string, number>;
    topics?: Record<string, number>;
    elderly?: number;
  };
  topics_imported?: Record<string, number>;
}

interface DatabaseStatus {
  crashes: {
    total: number;
    severity: Record<string, number>;
  };
  tickets: {
    total: number;
    topics: Record<string, number>;
  };
  elderly: {
    tickets: number;
    crashes: number;
  };
}

type UploadType = 'crash' | 'ticket';

// ============================================
// 上傳卡片元件
// ============================================
interface UploadCardProps {
  type: UploadType;
  onUploadComplete: () => void;
}

const UploadCard: React.FC<UploadCardProps> = ({ type, onUploadComplete }) => {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const config = {
    crash: {
      title: '交通事故資料',
      emoji: '🚗',
      description: '上傳事故 Excel 檔案（需含「案件編號」、「發生時間」、「發生地點」欄位）',
      color: 'nook-orange',
      endpoint: `${API_BASE}/import/crash`,
    },
    ticket: {
      title: '舉發案件資料',
      emoji: '📋',
      description: '上傳舉發 Excel 檔案（需含「舉發單號」、「違規時間(出)」、「違規地點一」欄位）',
      color: 'nook-sky',
      endpoint: `${API_BASE}/import/ticket`,
    },
  };

  const cfg = config[type];

  // 處理拖放
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && (droppedFile.name.endsWith('.xlsx') || droppedFile.name.endsWith('.xls'))) {
      setFile(droppedFile);
      setResult(null);
      setError(null);
    } else {
      setError('請上傳 Excel 檔案（.xlsx 或 .xls）');
    }
  }, []);

  // 處理檔案選擇
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setResult(null);
      setError(null);
    }
  };

  // 處理上傳
  const handleUpload = async () => {
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(cfg.endpoint, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || '上傳失敗');
      }

      const data: ImportResult = await response.json();
      setResult(data);
      onUploadComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : '上傳過程發生錯誤');
    } finally {
      setIsUploading(false);
    }
  };

  // 重置
  const handleReset = () => {
    setFile(null);
    setResult(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow">
      {/* 標題 */}
      <div className="flex items-center gap-3 mb-4">
        <div className={`w-12 h-12 bg-${cfg.color}/20 rounded-2xl flex items-center justify-center text-2xl`}>
          {cfg.emoji}
        </div>
        <div>
          <h3 className="text-lg font-bold text-nook-text">{cfg.title}</h3>
          <p className="text-sm text-nook-text/60">{cfg.description}</p>
        </div>
      </div>

      {/* 拖放區域 */}
      <div
        className={`
          relative border-2 border-dashed rounded-2xl p-8 text-center transition-all duration-200 cursor-pointer
          ${isDragging 
            ? `border-${cfg.color} bg-${cfg.color}/10` 
            : `border-nook-text/20 hover:border-${cfg.color}/50 hover:bg-${cfg.color}/5`
          }
          ${file ? 'border-nook-leaf bg-nook-leaf/5' : ''}
        `}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls"
          onChange={handleFileSelect}
          className="hidden"
        />

        {file ? (
          <div className="flex items-center justify-center gap-3">
            <FileSpreadsheet className="w-8 h-8 text-nook-leaf" />
            <div className="text-left">
              <p className="font-medium text-nook-text">{file.name}</p>
              <p className="text-sm text-nook-text/60">
                {(file.size / 1024).toFixed(1)} KB
              </p>
            </div>
          </div>
        ) : (
          <>
            <Upload className={`w-12 h-12 mx-auto mb-4 text-${cfg.color}/60`} />
            <p className="text-nook-text font-medium mb-1">
              拖放 Excel 檔案到此處
            </p>
            <p className="text-sm text-nook-text/60">
              或點擊選擇檔案（.xlsx, .xls）
            </p>
          </>
        )}
      </div>

      {/* 錯誤訊息 */}
      {error && (
        <div className="mt-4 bg-nook-red/10 rounded-2xl p-4 flex items-start gap-3">
          <XCircle className="w-5 h-5 text-nook-red flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-nook-red">匯入失敗</p>
            <p className="text-sm text-nook-red/80">{error}</p>
          </div>
        </div>
      )}

      {/* 上傳結果 */}
      {result && (
        <div className={`mt-4 rounded-2xl p-4 ${result.success ? 'bg-nook-leaf/10' : 'bg-nook-red/10'}`}>
          <div className="flex items-start gap-3">
            {result.success ? (
              <CheckCircle className="w-5 h-5 text-nook-leaf flex-shrink-0 mt-0.5" />
            ) : (
              <XCircle className="w-5 h-5 text-nook-red flex-shrink-0 mt-0.5" />
            )}
            <div className="flex-1">
              <p className={`font-medium ${result.success ? 'text-nook-leaf' : 'text-nook-red'}`}>
                {result.success ? '✅ 匯入成功' : '❌ 匯入失敗'}
              </p>
              <div className="mt-2 text-sm text-nook-text/80 space-y-1">
                <p>📊 新增：<strong>{result.stats.new}</strong> 筆</p>
                <p>⏭️ 略過（重複）：<strong>{result.stats.skipped}</strong> 筆</p>
                <p>⚠️ 錯誤：<strong>{result.stats.errors}</strong> 筆</p>
              </div>
              
              {/* 主題分類統計（僅舉發） */}
              {result.topics_imported && (
                <div className="mt-3 pt-3 border-t border-nook-text/10">
                  <p className="text-sm font-medium text-nook-text mb-2">本次匯入主題分類：</p>
                  <div className="flex gap-4 text-sm">
                    <span>🍺 酒駕 {result.topics_imported.dui}</span>
                    <span>🚦 闘紅燈 {result.topics_imported.red_light}</span>
                    <span>⚡ 危駕 {result.topics_imported.dangerous}</span>
                  </div>
                </div>
              )}

              {/* 錯誤詳情 */}
              {result.errors.length > 0 && (
                <div className="mt-3 pt-3 border-t border-nook-text/10">
                  <p className="text-sm font-medium text-nook-text mb-2">錯誤詳情（前 10 筆）：</p>
                  <ul className="text-xs text-nook-text/60 space-y-1">
                    {result.errors.map((err, idx) => (
                      <li key={idx}>• {err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 操作按鈕 */}
      <div className="mt-4 flex gap-3">
        <button
          onClick={handleUpload}
          disabled={!file || isUploading}
          className={`
            flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-2xl font-medium transition-all duration-200
            ${file && !isUploading
              ? `bg-${cfg.color} text-white hover:opacity-90 shadow-lg shadow-${cfg.color}/30`
              : 'bg-nook-text/10 text-nook-text/40 cursor-not-allowed'
            }
          `}
        >
          {isUploading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              匯入中...
            </>
          ) : (
            <>
              <Upload className="w-5 h-5" />
              開始匯入
            </>
          )}
        </button>
        
        {(file || result) && (
          <button
            onClick={handleReset}
            className="px-4 py-3 rounded-2xl font-medium text-nook-text/60 hover:bg-nook-text/10 transition-colors"
          >
            重置
          </button>
        )}
      </div>
    </div>
  );
};

// ============================================
// 資料庫狀態元件
// ============================================
interface DatabaseStatusCardProps {
  refreshTrigger: number;
}

const DatabaseStatusCard: React.FC<DatabaseStatusCardProps> = ({ refreshTrigger }) => {
  const [status, setStatus] = useState<DatabaseStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${API_BASE}/import/status`);
        if (!response.ok) throw new Error('無法取得狀態');
        const data = await response.json();
        setStatus(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : '載入失敗');
      } finally {
        setLoading(false);
      }
    };

    fetchStatus();
  }, [refreshTrigger]);

  if (loading) {
    return (
      <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow">
        <div className="flex items-center justify-center gap-3 py-8">
          <Loader2 className="w-6 h-6 animate-spin text-nook-leaf" />
          <span className="text-nook-text/60">載入資料庫狀態...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow">
        <div className="flex items-center gap-3 text-nook-red">
          <AlertCircle className="w-5 h-5" />
          <span>{error}</span>
        </div>
      </div>
    );
  }

  if (!status) return null;

  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-3xl p-6 nook-shadow">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-12 h-12 bg-nook-leaf/20 rounded-2xl flex items-center justify-center">
          <Database className="w-6 h-6 text-nook-leaf" />
        </div>
        <div>
          <h3 className="text-lg font-bold text-nook-text">目前資料庫狀態</h3>
          <p className="text-sm text-nook-text/60">所有資料皆已去識別化</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* 事故統計 */}
        <div className="bg-nook-orange/10 rounded-2xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-2xl">🚗</span>
            <span className="font-bold text-nook-text">交通事故</span>
          </div>
          <div className="text-3xl font-bold text-nook-orange mb-3">
            {status.crashes.total.toLocaleString()} 筆
          </div>
          <div className="space-y-1 text-sm text-nook-text/70">
            <div className="flex justify-between">
              <span>A1 死亡</span>
              <span className="font-medium text-nook-red">{status.crashes.severity.A1 || 0}</span>
            </div>
            <div className="flex justify-between">
              <span>A2 受傷</span>
              <span className="font-medium text-nook-orange">{status.crashes.severity.A2 || 0}</span>
            </div>
            <div className="flex justify-between">
              <span>A3 財損</span>
              <span className="font-medium text-nook-text">{status.crashes.severity.A3 || 0}</span>
            </div>
          </div>
        </div>

        {/* 舉發統計 */}
        <div className="bg-nook-sky/10 rounded-2xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-2xl">📋</span>
            <span className="font-bold text-nook-text">舉發案件</span>
          </div>
          <div className="text-3xl font-bold text-nook-sky mb-3">
            {status.tickets.total.toLocaleString()} 筆
          </div>
          <div className="space-y-1 text-sm text-nook-text/70">
            <div className="flex justify-between">
              <span>🍺 酒駕</span>
              <span className="font-medium text-nook-red">{status.tickets.topics.dui || 0}</span>
            </div>
            <div className="flex justify-between">
              <span>🚦 闘紅燈</span>
              <span className="font-medium text-nook-orange">{status.tickets.topics.red_light || 0}</span>
            </div>
            <div className="flex justify-between">
              <span>⚡ 危險駕駛</span>
              <span className="font-medium text-nook-sky">{status.tickets.topics.dangerous || 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 高齡者統計 */}
      <div className="mt-4 bg-nook-cream/50 rounded-2xl p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">👴</span>
            <span className="font-medium text-nook-text">高齡者（65歲以上）</span>
          </div>
          <div className="flex gap-6 text-sm">
            <span>違規 <strong className="text-nook-orange">{status.elderly.tickets}</strong> 件</span>
            <span>事故 <strong className="text-nook-red">{status.elderly.crashes}</strong> 件</span>
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================
// 主頁面元件
// ============================================
const DataImportPage: React.FC = () => {
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleUploadComplete = () => {
    setRefreshTrigger(prev => prev + 1);
  };

  return (
    <div className="p-8">
      {/* 標題區 */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-nook-text mb-2">📥 資料匯入</h2>
        <p className="text-nook-text/60">
          上傳 Excel 檔案匯入事故與舉發資料。系統會自動去識別化、分類主題、計算班別。
        </p>
      </div>

      {/* 說明卡片 */}
      <div className="bg-nook-leaf/10 rounded-3xl p-6 mb-8">
        <div className="flex items-start gap-4">
          <div className="text-3xl">🔒</div>
          <div>
            <h3 className="font-bold text-nook-text mb-2">個資保護說明</h3>
            <ul className="text-sm text-nook-text/70 space-y-1">
              <li>✅ 自動移除姓名、身分證、車號等個資</li>
              <li>✅ 地址去識別化（移除門牌號碼）</li>
              <li>✅ 年齡轉換為年齡組（如：65+）</li>
              <li>✅ 自動分類三大主題：酒駕、闘紅燈、危險駕駛</li>
              <li>✅ 重複資料自動略過（依案件編號/舉發單號）</li>
            </ul>
          </div>
        </div>
      </div>

      {/* 上傳區塊 */}
      <div className="grid grid-cols-2 gap-6 mb-8">
        <UploadCard type="crash" onUploadComplete={handleUploadComplete} />
        <UploadCard type="ticket" onUploadComplete={handleUploadComplete} />
      </div>

      {/* 資料庫狀態 */}
      <DatabaseStatusCard refreshTrigger={refreshTrigger} />
    </div>
  );
};

export default DataImportPage;
