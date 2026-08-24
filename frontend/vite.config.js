import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // framer-motion isn't reachable from Vite's static import crawl at cold
  // start (Landing.jsx is the only non-lazy route that imports it, but the
  // dev server was still discovering it mid-session and re-optimizing on
  // the fly) - that late re-optimization produces a second react-dom
  // module instance, and anything using hooks across that boundary
  // (framer-motion's motion.div) throws "Invalid hook call" in dev only
  // (production build bundles everything into one graph, so this never
  // reproduced there). Forcing it into the initial pre-bundle fixes it.
  optimizeDeps: {
    include: ['framer-motion'],
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('reactflow')) return 'reactflow';
            if (id.includes('recharts')) return 'recharts';
          }
        },
      },
    },
  },
})
