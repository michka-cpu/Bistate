import { defineConfig } from 'vitest/config'

// Keep test configuration separate from Vite's production configuration. Vitest
// 2 ships its own Vite types, so sharing a plugin-bearing config would create
// incompatible duplicate Vite type definitions with Vite 6.
export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
