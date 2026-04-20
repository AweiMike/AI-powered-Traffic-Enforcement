/**
 * BrandLogo — 精準執法儀表板品牌 logo
 *
 * 設計概念（方向 B + 在地變體）：
 * - 十字路口幾何：表達交通、路口分析、精準執法
 * - 4 個節點：其中 3 個為藍色圓點（資料節點），
 *   右上 1 個替換為台灣島輪廓（在地識別）
 * - 中心白點：焦點、決策中心
 *
 * Variant 使用規則（已驗證於 logo-dark-mode-verification.html）：
 *
 *   variant="dark"       → 淺色背景：white / surface-2 / slate-50 / slate-100
 *   variant="light"      → 深色/品牌色背景：primary / slate-900 / slate-800 /
 *                          accent / accent-hover
 *   variant="mono-dark"  → 白底印刷、簡報黑白投影片、favicon 備用
 *   variant="mono-light" → 深底浮水印、極簡 dark mode
 *
 * ⚠ 避免：放在 danger / warning / success 語意色背景上（色彩衝突）。
 * ✓ 最佳實踐：包裝在 bg-primary 或 bg-slate-900 rounded 容器裡配 light variant。
 *
 * 用法範例：
 *   <BrandLogo size={40} variant="dark" />     // 白底
 *   <BrandLogo size={40} variant="light" />    // 深底反白
 *   <BrandLogo size={16} variant="mono-dark" /> // favicon 16px
 */

import React from 'react';

interface BrandLogoProps {
  size?: number;
  /**
   * dark     = 深色線條（用於白底/淺底）
   * light    = 白色線條（用於深底/彩底 反白版）
   * mono-dark = 單色深（favicon / 印刷）
   * mono-light = 單色白
   */
  variant?: 'dark' | 'light' | 'mono-dark' | 'mono-light';
  className?: string;
  title?: string;
}

const BrandLogo: React.FC<BrandLogoProps> = ({
  size = 40,
  variant = 'dark',
  className = '',
  title = '精準執法儀表板',
}) => {
  // 色彩 scheme 表
  const colors = {
    dark: {
      cross: '#0F172A',        // 十字線深藍
      node: '#0369A1',          // 資料節點專業藍
      taiwan: '#0F172A',        // 台灣輪廓（與十字同色凸顯）
      center: '#FFFFFF',        // 中心白點
      centerStroke: '#0F172A',
    },
    light: {
      cross: '#FFFFFF',
      node: '#0EA5E9',          // 淺底轉亮藍
      taiwan: '#FFFFFF',
      center: '#0F172A',
      centerStroke: '#FFFFFF',
    },
    'mono-dark': {
      cross: '#0F172A',
      node: '#0F172A',
      taiwan: '#0F172A',
      center: '#FFFFFF',
      centerStroke: '#0F172A',
    },
    'mono-light': {
      cross: '#FFFFFF',
      node: '#FFFFFF',
      taiwan: '#FFFFFF',
      center: '#0F172A',
      centerStroke: '#FFFFFF',
    },
  }[variant];

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label={title}
    >
      <title>{title}</title>

      {/* 十字道路 */}
      <rect x="28" y="8" width="8" height="48" rx="1.5" fill={colors.cross} />
      <rect x="8" y="28" width="48" height="8" rx="1.5" fill={colors.cross} />

      {/* 節點 1：左上 — 藍色資料點 */}
      <circle cx="14" cy="14" r="5" fill={colors.node} />

      {/* 節點 2：右上 — 台灣島輪廓（在地識別點）
          簡化 Taiwan 形狀：寬上窄下、略向東傾、葉型輪廓 */}
      <path
        d="M 48.5 9.5
           Q 50 10 51 11.5
           Q 52 13 52 15
           Q 51.8 17 50.5 18.5
           Q 49 19.5 47.5 18.5
           Q 46.5 17.5 46 15.5
           Q 46 12.5 47 10.5
           Q 47.5 9.5 48.5 9.5 Z"
        fill={colors.taiwan}
      />

      {/* 節點 3：左下 — 藍色資料點 */}
      <circle cx="14" cy="50" r="5" fill={colors.node} />

      {/* 節點 4：右下 — 藍色資料點 */}
      <circle cx="50" cy="50" r="5" fill={colors.node} />

      {/* 中心焦點 */}
      <circle
        cx="32"
        cy="32"
        r="4"
        fill={colors.center}
        stroke={colors.centerStroke}
        strokeWidth="2"
      />
    </svg>
  );
};

export default BrandLogo;
