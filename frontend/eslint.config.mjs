import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// Next's own rules (React hooks, images, core web vitals) plus TypeScript's.
export default defineConfig([
    ...nextVitals,
    ...nextTs,
    // Playwright's report, results and saved sign-ins are generated, not written.
    globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts", "e2e/.report/**", "e2e/.results/**", "e2e/.auth/**"]),
]);
