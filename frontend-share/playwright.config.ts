import { defineConfig, devices } from '@playwright/test';

const authSecret = process.env.AUTH_SECRET ?? 'e2e-auth-secret-minimum-32-characters';
const databaseUrl =
  process.env.DATABASE_URL ??
  'postgresql://postgres:postgres@127.0.0.1:5432/xhs_auth';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:3000',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'pnpm start',
    url: 'http://127.0.0.1:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      ...process.env,
      AUTH_SECRET: authSecret,
      DATABASE_URL: databaseUrl,
      NODE_ENV: 'production',
      API_UPSTREAM_URL: process.env.API_UPSTREAM_URL ?? 'http://127.0.0.1:8000',
      API_BASE_URL: process.env.API_BASE_URL ?? 'http://127.0.0.1:8000',
      NEXT_PUBLIC_API_BASE_URL:
        process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000',
    },
  },
});
