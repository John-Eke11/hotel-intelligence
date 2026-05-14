/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'bg-base':        '#0D1B2A',
        'bg-elevated':    '#142234',
        'bg-surface':     '#1A2E45',
        'accent':         '#E8A020',
        'accent-hover':   '#C4861A',
        'text-primary':   '#FFFFFF',
        'text-secondary': '#B8C4D0',
        'text-muted':     '#4A5568',
        'positive':       '#27AE60',
        'negative':       '#E74C3C',
      },
      fontFamily: {
        display: ['Cambria', 'Georgia', 'serif'],
        body:    ['"Source Sans 3"', 'Calibri', 'sans-serif'],
        mono:    ['Consolas', '"Courier New"', 'monospace'],
      },
      borderRadius: { card: '10px' },
    },
  },
  plugins: [],
}
