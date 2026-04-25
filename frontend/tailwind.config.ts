import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Cream / paper background — softer than pure white, signals "physical document"
        ink: {
          50: '#FAF7F2',
          100: '#F4EFE6',
          200: '#E8DFCE',
          300: '#C9BBA0',
          900: '#1B1A17',
        },
        // Deep forest green — gravitas without "navy/cream lawyer cliche"
        sage: {
          50: '#F0F4F0',
          100: '#DCE6DC',
          400: '#638A6B',
          600: '#3F5F46',
          700: '#2F4A36',
          800: '#1F3424',
        },
        // Accent: muted gold for CTAs and progress
        ochre: {
          400: '#D9A441',
          500: '#C18B2A',
          600: '#9C6E1F',
        },
      },
      fontFamily: {
        // Serif for headings = legal gravitas; sans for UI = modern feel
        serif: ['"Source Serif 4"', 'Charter', 'Cambria', 'Georgia', 'serif'],
        sans: ['"Inter"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      boxShadow: {
        paper: '0 1px 0 rgba(27, 26, 23, 0.04), 0 8px 32px -12px rgba(27, 26, 23, 0.18)',
        sink: 'inset 0 1px 0 rgba(255, 255, 255, 0.6), 0 1px 2px rgba(27, 26, 23, 0.06)',
      },
      animation: {
        'fade-in-up': 'fadeInUp 0.4s ease-out',
        'pulse-soft': 'pulseSoft 2.5s ease-in-out infinite',
      },
      keyframes: {
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.55' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
