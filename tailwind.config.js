/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#8B5CF6',
          50: '#F5F3FF',
          100: '#EDE9FE',
          200: '#DDD6FE',
          300: '#C4B5FD',
          400: '#A78BFA',
          500: '#8B5CF6',
          600: '#7C3AED',
          700: '#6D28D9',
          800: '#5B21B6',
          900: '#4C1D95',
        },
        ink: {
          DEFAULT: '#1F1F2E',
          soft: '#2A2A3D',
        },
        canvas: '#FAFAFA',
        border: '#EEEEEE',
        muted: '#6B7280',
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          '"Segoe UI"',
          'Roboto',
          'sans-serif',
        ],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'Consolas', 'Menlo', 'monospace'],
      },
      borderRadius: {
        card: '12px',
      },
      boxShadow: {
        card: '0 1px 3px rgb(0 0 0 / 0.06)',
        soft: '0 4px 12px rgb(0 0 0 / 0.06)',
      },
    },
  },
  plugins: [],
};
