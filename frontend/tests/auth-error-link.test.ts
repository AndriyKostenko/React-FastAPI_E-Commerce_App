// AuthErrorLink: /login shows a sign-in error from the URL only when we signed it.
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import {
    AUTH_ERROR_MAX_LENGTH,
    AUTH_ERROR_PARAM,
    AUTH_ERROR_SIGNATURE_PARAM,
    AuthErrorLink,
} from "@/lib/auth-error-link";

// Read when a link is made or checked, not at import.
process.env.NEXTAUTH_SECRET = randomBytes(32).toString("hex");

/** The query of a link as the login page receives it. */
const paramsOf = (url: string): Record<string, string> =>
    Object.fromEntries(new URL(url, "http://localhost").searchParams);

describe("AuthErrorLink", () => {
    it("shows the message it signed", () => {
        const url = AuthErrorLink.url("This account is not active yet.");
        assert.equal(AuthErrorLink.read(paramsOf(url)), "This account is not active yet.");
    });

    it("ignores a message without a signature", () => {
        assert.equal(AuthErrorLink.read({ [AUTH_ERROR_PARAM]: "Your account is locked, call us" }), undefined);
    });

    it("ignores a message whose text was changed after signing", () => {
        const params = paramsOf(AuthErrorLink.url("Google sign-in failed."));
        params[AUTH_ERROR_PARAM] = "Your account is locked, call us";
        assert.equal(AuthErrorLink.read(params), undefined);
    });

    it("ignores a signature made with another secret", () => {
        const params = paramsOf(AuthErrorLink.url("Google sign-in failed."));
        process.env.NEXTAUTH_SECRET = randomBytes(32).toString("hex");
        try {
            assert.equal(AuthErrorLink.read(params), undefined);
        } finally {
            process.env.NEXTAUTH_SECRET = randomBytes(32).toString("hex");
        }
    });

    it("cuts a long message to the limit before signing it", () => {
        const params = paramsOf(AuthErrorLink.url("x".repeat(AUTH_ERROR_MAX_LENGTH + 50)));
        assert.equal(params[AUTH_ERROR_PARAM].length, AUTH_ERROR_MAX_LENGTH);
        assert.ok(params[AUTH_ERROR_SIGNATURE_PARAM]);
        assert.equal(AuthErrorLink.read(params)?.length, AUTH_ERROR_MAX_LENGTH);
    });

    it("sends a bare /login when no secret is set", () => {
        const secret = process.env.NEXTAUTH_SECRET;
        delete process.env.NEXTAUTH_SECRET;
        try {
            assert.equal(AuthErrorLink.url("Google sign-in failed."), "/login");
        } finally {
            process.env.NEXTAUTH_SECRET = secret;
        }
    });
});
