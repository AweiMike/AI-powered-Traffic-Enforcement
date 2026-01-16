/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Animal Crossing "Nook" palette
        'nook-cream': '#FDF6E3',
        'nook-leaf': '#7ABB6A',
        'nook-leaf-dark': '#5A9B4A',
        'nook-sky': '#87CEEB',
        'nook-sky-light': '#B0E0E6',
        'nook-bell': '#FFD700',
        'nook-wood': '#D2B48C',
        'nook-wood-dark': '#A0826D',
        'nook-ocean': '#4A90A4',
        'nook-sand': '#FAE7C9',
        'nook-text': '#5D4037',
        'nook-red': '#E57373',
        'nook-orange': '#FFB74D',
      },
      fontFamily: {
        'round': ['"Varela Round"', '"Kosugi Maru"', 'sans-serif'],
      },
      borderRadius: {
        '4xl': '2rem',
      },
    },
  },
  plugins: [],
}
