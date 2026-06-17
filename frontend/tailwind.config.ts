import type { Config } from 'tailwindcss';

// Observatory design palette — see docs/UI_SPEC.md.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        void: '#070B0F',
        base: '#0D1117',
        elevated: '#161B22',
        muted: '#1C2128',
        'border-subtle': '#21262D',
        'border-default': '#30363D',
        'border-strong': '#3D444D',
        'text-primary': '#E6EDF3',
        'text-secondary': '#8B949E',
        'text-muted': '#484F58',
        'text-inverse': '#0D1117',
        'accent-purple': '#8B5CF6',
        'accent-blue': '#3B82F6',
        success: '#3FB950',
        warning: '#D29922',
        danger: '#F85149',
        info: '#58A6FF',
        // Language colours — used in CitationCard and file tree.
        'lang-py': '#60A5FA',
        'lang-ts': '#34D399',
        'lang-go': '#67E8F9',
        'lang-rs': '#FB923C',
        'lang-js': '#FBBF24',
        'lang-c': '#A78BFA',
        'lang-java': '#F472B6',
        'lang-md': '#94A3B8',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      backgroundImage: {
        'accent-grad': 'linear-gradient(135deg, #8B5CF6 0%, #3B82F6 100%)',
        'card-grad': 'linear-gradient(180deg, #161B22 0%, #0D1117 100%)',
      },
      backdropBlur: {
        glass: '12px',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'stream-cursor': 'blink 1s step-end infinite',
        'ring-fill': 'ringFill 0.8s ease-out forwards',
      },
      keyframes: {
        blink: { '0%, 100%': { opacity: '1' }, '50%': { opacity: '0' } },
        ringFill: { from: { strokeDashoffset: '100' }, to: {} },
      },
    },
  },
  plugins: [],
} satisfies Config;
