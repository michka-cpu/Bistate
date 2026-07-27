import { defineConfig } from 'vitest/config'

// Keep test configuration separate from Vite's production configuration. Vitest
// 2 ships its own Vite types, so sharing a plugin-bearing config would create
// incompatible duplicate Vite type definitions with Vite 6.
export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    // Playwright owns the end-to-end specs under e2e/; keep them out of the Vitest run.
    exclude: ['**/node_modules/**', '**/dist/**', 'e2e/**'],
  },
})
