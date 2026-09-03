import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Native: 127.0.0.1:8000. Docker Compose: set DEV_API_PROXY_TARGET=http://core-api:8000
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget =
    env.DEV_API_PROXY_TARGET || process.env.DEV_API_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      host: true,
      allowedHosts: true,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
