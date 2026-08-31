import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Native dev: 127.0.0.1:8000. Docker Compose: set DEV_API_PROXY_TARGET=http://core-api:8000
const apiProxyTarget = process.env.DEV_API_PROXY_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
})
