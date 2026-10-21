// lib/env-schema.ts: the checks on public environment variables, alone and through createEnv.
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { createEnv } from "@t3-oss/env-nextjs";
import { env as rule } from "@/lib/env-schema";

const run = <T>(schema: { "~standard": { validate: (value: unknown) => T } }, value: unknown): T =>
    schema["~standard"].validate(value);

describe("env-schema", () => {
    it("accepts a URL and refuses anything else", () => {
        assert.deepEqual(run(rule.url(), "https://shop.example.com"), { value: "https://shop.example.com" });
        assert.deepEqual(run(rule.url(), "shop.example.com"), { issues: [{ message: "must be a URL" }] });
        assert.deepEqual(run(rule.url(), undefined), { issues: [{ message: "is required" }] });
    });

    it("reads an unset or empty optional value as undefined", () => {
        assert.deepEqual(run(rule.optionalUrl(), undefined), { value: undefined });
        assert.deepEqual(run(rule.optionalText(), ""), { value: undefined });
        assert.deepEqual(run(rule.optionalUrl(), "not a url"), { issues: [{ message: "must be a URL" }] });
    });

    it("requires required text to be there", () => {
        assert.deepEqual(run(rule.text(), "pk_test_123"), { value: "pk_test_123" });
        assert.deepEqual(run(rule.text(), ""), { issues: [{ message: "must not be empty" }] });
    });

    it("makes createEnv refuse a bad value and pass good ones through", () => {
        const make = (origin: string | undefined) =>
            createEnv({
                client: { NEXT_PUBLIC_API_ORIGIN: rule.optionalUrl(), NEXT_PUBLIC_KEY: rule.text() },
                runtimeEnv: { NEXT_PUBLIC_API_ORIGIN: origin, NEXT_PUBLIC_KEY: "key" },
                onValidationError: () => {
                    throw new Error("invalid env");
                },
            });
        assert.equal(make("https://api.example.com").NEXT_PUBLIC_API_ORIGIN, "https://api.example.com");
        assert.equal(make(undefined).NEXT_PUBLIC_API_ORIGIN, undefined);
        assert.throws(() => make("nope"), /invalid env/);
    });
});
