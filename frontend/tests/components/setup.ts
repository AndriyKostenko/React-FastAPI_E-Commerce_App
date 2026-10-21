// Runs before every component test file.
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Testing Library unmounts after each test by itself only when the test
// runner's globals are on; they are off here, so unmount explicitly.
afterEach(cleanup);
