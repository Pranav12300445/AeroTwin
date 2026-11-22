/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        aero: {
          dark: '#0a0e17',
          panel: '#111827',
          border: '#1e293b',
          accent: '#3b82f6',
          green: '#22c55e',
          yellow: '#eab308',
          red: '#ef4444',
          orange: '#f97316',
        },
      },
    },
  },
  plugins: [],
}
