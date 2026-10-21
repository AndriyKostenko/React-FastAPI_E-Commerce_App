import { defineConfig, devices } from "@playwright/test";

// End-to-end journeys against the local stack (`backend/local/dev.sh up`),
// nothing mocked: the real frontend, gateway, services, Stripe test mode, the
// CJ sandbox, and every email caught by Mailpit (`dev.sh mail catch`).
// Run with `npm run test:e2e`; e2e/README.md has the details.

const FRONTEND_URL = process.env.FRONTEND_URL ?? "http://localhost:30000";

export default defineConfig({
    testDir: "e2e",
    // One shared stack and one dev server, which compiles pages on first
    // visit: the journeys run one at a time, each in its own browser context.
    workers: 1,
    fullyParallel: false,
    forbidOnly: true,
    retries: 0,
    timeout: 90_000,
    expect: { timeout: 15_000 },
    outputDir: "e2e/.results",
    reporter: [["list"], ["html", { open: "never", outputFolder: "e2e/.report" }]],
    use: {
        baseURL: FRONTEND_URL,
        // The installed Google Chrome, not a downloaded build.
        channel: "chrome",
        trace: "retain-on-failure",
        screenshot: "only-on-failure",
        navigationTimeout: 45_000,
        actionTimeout: 15_000,
    },
    projects: [
        // Checks the stack, then signs up a shopper through the real email link.
        { name: "setup", testMatch: /setup\/.*\.setup\.ts/ },
        {
            name: "desktop",
            testIgnore: /setup\//,
            dependencies: ["setup"],
            use: { ...devices["Desktop Chrome"], channel: "chrome" },
        },
    ],
});
