import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // API_TOKEN has no VITE_ prefix, so it is never bundled into client code; the
  // dev proxy attaches it server-side. Repo-root .env first, frontend/.env overrides.
  const env = { ...loadEnv(mode, '..', ''), ...loadEnv(mode, process.cwd(), '') }
  const apiToken = process.env.API_TOKEN ?? env.API_TOKEN ?? ''
  const apiTarget = process.env.API_PROXY_TARGET ?? env.API_PROXY_TARGET ?? 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          headers: apiToken ? { Authorization: `Bearer ${apiToken}` } : {},
        },
      },
    },
  }
})
