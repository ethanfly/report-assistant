/** @type {import('tailwindcss').Config} */
// 像素风清新绿主题
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // 主色：清新绿
        primary: {
          DEFAULT: '#7BC47F',
          50: '#F0F9F1',
          100: '#E1F2E3',
          200: '#C6E5C9',
          300: '#A8D6AC',
          400: '#8FC893',
          500: '#7BC47F',
          600: '#5DAE63',
          700: '#4A8F50',
          800: '#3A7140',
          900: '#2C5532',
        },
        // 强调色：粉，少量点缀
        accent: {
          DEFAULT: '#FF8FA3',
          50: '#FFF1F4',
          100: '#FFE4EA',
          500: '#FF8FA3',
          600: '#E97388',
        },
        ink: {
          DEFAULT: '#2F3E2F', // 文字主
          soft: '#3F523F',
        },
        ink2: '#6B8472', // 文字副
        bg: '#F5F9F5', // 浅绿白背景
        canvas: '#F5F9F5', // 兼容旧用法
        card: '#FFFFFF',
        border: '#D7E5D8',
        muted: '#6B8472',
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
        // 像素风字体（用于强调标识；正文仍用 sans）
        pixel: ['"Press Start 2P"', '"VT323"', 'monospace'],
      },
      borderRadius: {
        // 像素风偏方一点
        card: '6px',
        pix: '4px',
      },
      boxShadow: {
        card: '0 1px 0 0 rgb(47 62 47 / 0.04), 0 1px 3px rgb(47 62 47 / 0.06)',
        soft: '0 4px 12px rgb(47 62 47 / 0.06)',
        pix: '2px 2px 0 0 rgb(47 62 47 / 0.08)',
        pixhover: '0 3px 0 0 rgb(93 174 99 / 0.18), 2px 2px 0 0 rgb(47 62 47 / 0.06)',
      },
      animation: {
        pop: 'pop 0.14s ease-out',
        fadein: 'fadeIn 0.22s ease-out',
        slidein: 'slideIn 0.24s ease-out',
        wiggle: 'wiggle 0.3s ease-in-out',
      },
      keyframes: {
        pop: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideIn: {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        wiggle: {
          '0%, 100%': { transform: 'rotate(0deg)' },
          '25%': { transform: 'rotate(-2deg)' },
          '75%': { transform: 'rotate(2deg)' },
        },
      },
    },
  },
  plugins: [],
};
