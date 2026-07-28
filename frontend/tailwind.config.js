/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          primary:   '#080b14',
          secondary: '#0d1020',
          tertiary:  '#121629',
          card:      '#151b2e',
          border:    '#1e2640',
          hover:     '#1a2038',
        },
        accent: {
          blue:   '#3b82f6',
          cyan:   '#06b6d4',
          purple: '#8b5cf6',
          green:  '#10b981',
          yellow: '#f59e0b',
          red:    '#ef4444',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'fade-in':      'fadeIn 0.2s ease-out',
        'slide-up':     'slideUp 0.2s ease-out',
        'pulse-slow':   'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        fadeIn:  { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        slideUp: { '0%': { transform: 'translateY(8px)', opacity: '0' }, '100%': { transform: 'translateY(0)', opacity: '1' } },
      },
      backdropBlur: { xs: '2px' },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.3)',
      },
    },
  },
  plugins: [],
}
