/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // ============================================
        // 語意化 color tokens（Option B — B2B 深藍專業）
        // 新程式碼請優先使用以下 token。
        // 舊 nook-* 保留為 alias，值已重新映射到專業色系。
        // ============================================
        'primary':        '#0F172A',  // 深藍近黑 — 標題 / 主元素
        'primary-light':  '#1E293B',  // 石板深藍
        'accent':         '#0369A1',  // 專業藍 — CTA / 強調
        'accent-hover':   '#075985',
        'accent-soft':    '#E0F2FE',  // 淡藍 — active 背景

        'surface':        '#FFFFFF',  // 白色面板
        'surface-2':      '#F8FAFC',  // 冷白 — 頁面背景
        'surface-3':      '#F1F5F9',  // 更淡面板

        'border':         '#E2E8F0',
        'border-strong':  '#CBD5E1',

        'text':           '#0F172A',
        'text-muted':     '#475569',
        'text-subtle':    '#64748B',

        'danger':         '#DC2626',  // A1 死亡 / 錯誤
        'warning':        '#D97706',  // A2 受傷 / 警告
        'success':        '#059669',  // 成功
        'info':           '#0284C7',

        // ============================================
        // 舊 nook-* alias（相容既有程式碼，色值已重新映射）
        // ============================================
        'nook-cream':     '#F8FAFC',  // 原米黃 → 冷白背景
        'nook-leaf':      '#0369A1',  // 原葉綠 → 專業藍
        'nook-leaf-dark': '#0F172A',  // 原深葉綠 → 深藍近黑
        'nook-sky':       '#0284C7',  // 原天空藍 → 資訊藍
        'nook-sky-light': '#E0F2FE',  // 原淡天空藍 → 淡藍
        'nook-bell':      '#F59E0B',  // 原金色 → 琥珀（給 star/emphasis）
        'nook-wood':      '#CBD5E1',  // 原木色 → 邊框灰
        'nook-wood-dark': '#94A3B8',  // 原深木色 → 深邊框灰
        'nook-ocean':     '#334155',  // 原青色 → 石板灰
        'nook-sand':      '#F1F5F9',  // 原沙色 → 淡面板灰
        'nook-text':      '#0F172A',  // 原棕 → 深藍近黑
        'nook-red':       '#DC2626',  // 危險紅（比原本更飽和）
        'nook-orange':    '#F97316',  // 警告橘
      },
      fontFamily: {
        'round': ['"Varela Round"', '"Kosugi Maru"', 'sans-serif'],
      },
      borderRadius: {
        '4xl': '2rem',
      },
      boxShadow: {
        // 低疲勞柔和陰影（取代原本 animal crossing 卡通陰影）
        'soft':  '0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.06)',
        'card':  '0 4px 12px -2px rgb(15 23 42 / 0.06), 0 2px 4px -2px rgb(15 23 42 / 0.04)',
      },
    },
  },
  plugins: [],
}
