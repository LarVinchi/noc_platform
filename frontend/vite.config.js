import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { env } from 'node:process'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': env.API_PROXY_TARGET || 'http://localhost:8000',
      '/static': env.API_PROXY_TARGET || 'http://localhost:8000',
    },
  },
})
