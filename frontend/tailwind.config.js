/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {
      colors: {
        'neon-blue': '#00f3ff',
        'neon-pink': '#ff00ff',
        'neon-green': '#00ff9f',
        'glass-bg': 'rgba(255, 255, 255, 0.1)',
        'glass-border': 'rgba(255, 255, 255, 0.2)',
        'tech-dark': '#050510',
        'tech-panel': '#0a0a1f',
      },
      fontFamily: {
        'tech': ['"Rajdhani"', 'sans-serif'],
        'mono': ['"Share Tech Mono"', 'monospace'],
      },
      boxShadow: {
        'neon-blue': '0 0 10px #00f3ff, 0 0 20px #00f3ff',
        'neon-pink': '0 0 10px #ff00ff, 0 0 20px #ff00ff',
      },
      backgroundImage: {
        'grid-pattern': "linear-gradient(to right, #1f1f3a 1px, transparent 1px), linear-gradient(to bottom, #1f1f3a 1px, transparent 1px)",
      }
    },
  },
  plugins: [],
}
