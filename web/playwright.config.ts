import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests",
  workers: 1,
  fullyParallel: false,
  use: {
    viewport: { width: 1440, height: 1050 },
    headless: true,
    video: "on",
    launchOptions: process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {},
  },
  reporter: "list",
});
