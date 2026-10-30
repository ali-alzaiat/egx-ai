import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ mode }) => {
  // API_TOKEN has no VITE_ prefix, so it is never bundled into client code; the
  // dev proxy attaches it server-side. Repo-root .env first, frontend/.env overrides.
  const env = { ...loadEnv(mode, '..', ''), ...loadEnv(mode, process.cwd(), '') }
  const apiToken = process.env.API_TOKEN ?? env.API_TOKEN ?? ''
  const apiTarget = process.env.API_PROXY_TARGET ?? env.API_PROXY_TARGET ?? 'http://localhost:8000'

  return {
    plugins: [react(), tailwindcss()],
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    build: {
      rollupOptions: {
        output: {
          // The shadcn stack (R48 U2: Radix, Floating UI, tailwind-merge, cva) is ~120 kB: its own cacheable chunk keeps the app chunk under Vite's 500 kB warning.
          manualChunks(id: string) {
            if (/node_modules[\\/](radix-ui|@radix-ui|@floating-ui|tailwind-merge|class-variance-authority|clsx)[\\/]/.test(id)) return 'ui-kit'
            if (/node_modules[\\/]lightweight-charts[\\/]/.test(id)) return 'charts'
            return undefined
          },
        },
      },
    },
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
