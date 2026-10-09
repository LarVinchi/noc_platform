import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { env } from 'node:process'
import { fileURLToPath } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: { input: {
      main: fileURLToPath(new URL('./index.html', import.meta.url)),
      redirect: fileURLToPath(new URL('./redirect.html', import.meta.url)),
    } },
  },
  server: {
    watch: { usePolling: env.DEV_WATCH_POLLING === 'true', interval: 500 },
    proxy: {
      '/api': env.API_PROXY_TARGET || 'http://localhost:8000',
      '/static': env.API_PROXY_TARGET || 'http://localhost:8000',
    },
  },
})
