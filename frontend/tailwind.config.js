/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Our custom NOC dark mode palette
        charcoal: {
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
        },
        cyan: {
          400: '#22d3ee',
          500: '#06b6d4',
        },
        lime: {
          400: '#a3e635',
          500: '#84cc16',
        }
      },
      boxShadow: {
        'cyan-glow': '0 0 10px rgba(34, 211, 238, 0.5)',
        'lime-glow': '0 0 10px rgba(163, 230, 53, 0.5)',
      }
    },
  },
  plugins: [],
}