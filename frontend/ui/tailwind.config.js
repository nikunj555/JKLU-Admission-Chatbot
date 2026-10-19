/** Design tokens for "JKLU Admission Assistant": clean light neutral canvas, dark navy typography, restrained university blue & teal accents. */
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#070f26',
          900: '#0f172a',
          850: '#15203b',
          800: '#1e293b',
          700: '#334155',
          600: '#475569',
          500: '#64748b',
          400: '#94a3b8',
          300: '#cbd5e1',
          200: '#e2e8f0',
          100: '#f1f5f9',
          50: '#f8fafc',
        },
        brand: {
          DEFAULT: '#1e40af', // University Navy
          primary: '#1e3a8a',
          hover: '#1d4ed8',
          accent: '#0284c7', // Accessible Sky/Blue
          teal: '#0f766e',   // Deep Teal
          tealSoft: '#f0fdfa',
          soft: '#eff6ff',
          muted: '#f8fafc',
        },
        ink: {
          950: '#0f172a',
          900: '#1e293b',
          850: '#334155',
          800: '#475569',
          700: '#64748b',
          600: '#94a3b8',
        },
        mist: {
          50: '#0f172a',
          100: '#1e293b',
          200: '#334155',
          300: '#475569',
          400: '#64748b',
          500: '#94a3b8',
        },
        accent: {
          DEFAULT: '#1e40af',
          soft: '#2563eb',
          deep: '#1e3a8a',
        },
        ok: '#059669',
        warn: '#d97706',
        bad: '#dc2626',
      },
      fontFamily: {
        sans: ['"Inter Variable"', 'Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        serif: ['"Instrument Serif"', 'Georgia', 'serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'Consolas', 'monospace'],
      },
      borderRadius: {
        xl: '0.75rem',
        '2xl': '1rem',
        '3xl': '1.25rem',
      },
      boxShadow: {
        subtle: '0 1px 2px 0 rgba(15, 23, 42, 0.05)',
        card: '0 1px 3px 0 rgba(15, 23, 42, 0.08), 0 1px 2px -1px rgba(15, 23, 42, 0.04)',
        glow: '0 0 0 3px rgba(30, 64, 175, 0.15)',
        pop: '0 10px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04)',
      },
      keyframes: {
        rise: { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'none' } },
        fade: { from: { opacity: '0' }, to: { opacity: '1' } },
        pop: { from: { opacity: '0', transform: 'scale(.98) translateY(4px)' }, to: { opacity: '1', transform: 'none' } },
        shimmer: { from: { backgroundPosition: '200% 0' }, to: { backgroundPosition: '-200% 0' } },
        dots: { '0%,80%,100%': { opacity: '.3', transform: 'translateY(0)' }, '40%': { opacity: '1', transform: 'translateY(-2px)' } },
      },
      animation: {
        rise: 'rise .35s cubic-bezier(.16, 1, .3, 1) both',
        fade: 'fade .25s ease both',
        pop: 'pop .2s cubic-bezier(.16, 1, .3, 1) both',
        shimmer: 'shimmer 2s linear infinite',
        dots: 'dots 1.2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
