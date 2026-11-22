/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: {
          dark: '#0B0F17',
          card: '#131B2E',
          hover: '#19243C',
          lighter: '#1E293B',
        },
        brand: {
          orange: '#F97316',
          orangeDark: '#EA580C',
          orangeLight: '#FB923C',
        },
        accent: {
          teal: '#14B8A6',
          tealDark: '#0D9488',
          tealLight: '#2DD4BF',
          amber: '#F59E0B',
          amberDark: '#D97706',
          amberLight: '#FBBF24',
          slate: '#64748B',
        },
        border: {
          subtle: '#1E293B',
          glow: 'rgba(249, 115, 22, 0.25)',
        }
      },
      fontFamily: {
        serif: ['ui-serif', 'Georgia', 'Cambria', '"Times New Roman"', 'Times', 'serif'],
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      borderRadius: {
        'card': '14px',
      }
    },
  },
  plugins: [],
}
