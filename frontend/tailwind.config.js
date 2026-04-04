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
        // Added the missing glows for your cables, splitters, and customers
        'green-glow': '0 0 10px rgba(74, 222, 128, 0.5)',
        'purple-glow': '0 0 10px rgba(192, 132, 252, 0.5)',
        'orange-glow': '0 0 10px rgba(251, 146, 60, 0.5)',
      },
      // NEW: Added the animation and keyframes for the sidebar
      keyframes: {
        'slide-in-right': {
          '0%': { transform: 'translateX(100%)' },
          '100%': { transform: 'translateX(0)' },
        }
      },
      animation: {
        'slide-in-right': 'slide-in-right 0.3s ease-out forwards',
      }
    },
  },
  plugins: [],
}