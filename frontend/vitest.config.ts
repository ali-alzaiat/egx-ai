import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  test: {
    globals: true,
    // jsdom is not installed (no new deps without a named brief); pure-logic tests run in node.
    // Switch back to 'jsdom' and add the dep when component tests need a DOM.
    environment: 'node',
    setupFiles: [],
  },
})
