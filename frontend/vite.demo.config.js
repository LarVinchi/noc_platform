import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { env } from 'node:process'
import { demoFixtureServer } from './demo/fixtureServer.js'

// Design preview only: serves demo/index.html with synthetic fixtures on same-origin /api.
// Never used by `npm run build`; production builds use vite.config.js.
export default defineConfig({
  plugins: [react(), demoFixtureServer()],
  server: {
    watch: { usePolling: env.DEV_WATCH_POLLING === 'true', interval: 500 },
  },
})
