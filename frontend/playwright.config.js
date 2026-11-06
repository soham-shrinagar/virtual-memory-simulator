import { defineConfig } from '@playwright/test';

const port = 8011;
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: './browser',
  testMatch: '*.e2e.js',
  forbidOnly: Boolean(process.env.CI),
  reporter: 'list',
  use: { baseURL, serviceWorkers: 'block' },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
    { name: 'firefox', use: { browserName: 'firefox' } },
  ],
  webServer: {
    command: `python -I -m vmsim --port ${port}`,
    url: `${baseURL}/`,
    reuseExistingServer: false,
  },
});
