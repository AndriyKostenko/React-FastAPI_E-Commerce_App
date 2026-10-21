import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const root = path.dirname(fileURLToPath(import.meta.url));

// Component tests: React components rendered into jsdom with Testing Library.
// Only tests/components: the other files in tests/ are node:test suites
// (npm run test:unit, test:race, ...) and e2e/ is Playwright's.
export default defineConfig({
    resolve: {
        alias: { "@": root },
    },
    test: {
        environment: "jsdom",
        include: ["tests/components/**/*.test.tsx"],
        setupFiles: ["tests/components/setup.ts"],
    },
});
