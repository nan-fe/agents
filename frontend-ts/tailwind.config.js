/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: '#f0e4cc',
        ivory: '#faf3e8',
        ink: {
          DEFAULT: '#2a2218',
          muted: '#5c4d3a',
        },
        gold: {
          DEFAULT: '#c9a227',
          light: '#e8d48b',
          dark: '#8a6b1f',
        },
        burgundy: {
          DEFAULT: '#6b2d3e',
          dark: '#4a1f2c',
        },
        umber: {
          DEFAULT: '#3d2f24',
          dark: '#1f1812',
        },
        sepia: '#8b7355',
        sage: '#4a5c47',
      },
      fontFamily: {
        display: ['Cinzel', 'Times New Roman', 'serif'],
        body: ['Cormorant Garamond', 'Georgia', 'Times New Roman', 'serif'],
      },
      animation: {
        'atelier-reveal': 'atelier-reveal 0.9s cubic-bezier(0.22, 1, 0.36, 1) both',
      },
      keyframes: {
        'atelier-reveal': {
          from: { opacity: '0', transform: 'translateY(14px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
};
