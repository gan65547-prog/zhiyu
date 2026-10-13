import fs from 'node:fs'
import { defineConfig, devices } from '@playwright/test'

const e2ePort = Number(process.env.GANFY_E2E_PORT || 3000)
const baseURL = process.env.GANFY_E2E_BASE_URL || `http://127.0.0.1:${e2ePort}`
const systemChrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const executablePath = process.env.GANFY_E2E_CHROME_PATH || (fs.existsSync(systemChrome) ? systemChrome : undefined)

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  snapshotPathTemplate: '{testDir}/visual-snapshots/{arg}{ext}',
  use: {
    baseURL,
    browserName: 'chromium',
    ...devices['Desktop Chrome'],
    launchOptions: { executablePath },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  // CI 使用已构建的产物（vite preview），避免 dev server 在低配 Runner 上
  // 按需编译模块时被 CPU 饥饿挂起（曾导致视图 chunk 请求永不返回、
  // networkidle 永不达成）；本地保留 dev server 便于调试。
  webServer: process.env.CI
    ? {
        command: `VITE_DEV_API=${process.env.VITE_DEV_API || 'http://127.0.0.1:8000'} npm run preview -- --host 127.0.0.1 --port ${e2ePort}`,
        url: baseURL,
        reuseExistingServer: true,
        timeout: 120_000,
      }
    : {
        command: `VITE_DEV_API=${process.env.VITE_DEV_API || 'http://127.0.0.1:8000'} npm run dev -- --host 127.0.0.1 --port ${e2ePort}`,
        url: baseURL,
        reuseExistingServer: true,
        timeout: 120_000,
      },
})
