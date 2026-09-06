/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f5f3ff',
          100: '#ede9fe',
          200: '#ddd6fe',
          300: '#c4b5fd',
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
          700: '#6d28d9',
          800: '#5b21b6',
          900: '#4c1d95',
          950: '#2e1065',
        },
        // Paper/ink editorial system. One signal accent — reserve gradients
        // for data-viz only, never for text or chrome.
        paper: '#FAFAF8',
        ink: {
          DEFAULT: '#14213D',
          soft: '#3D4A68',
          muted: '#5C6B84',
        },
        signal: {
          DEFAULT: '#E85D2A',
          dark: '#B53E14',
          soft: '#FDEEE6',
        },
      },
      fontFamily: {
        // Display (headlines) + body + mono (labels/metrics) pairing.
        display: ['"Space Grotesk"', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
