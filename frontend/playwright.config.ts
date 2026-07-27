import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end tests run against the already-running application. Override the target
 * with E2E_BASE_URL (e.g. the Docker web container). The API is reached through the
 * same origin because the web server proxies /api, so no separate API URL is needed.
 */
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['list']] : [['list']],
  use: {
    baseURL,
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
})
