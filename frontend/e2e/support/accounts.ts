// The accounts the journeys sign in with.
//
// The gateway limits, per client and hour, sign-ups and email confirmations
// to five and password resets to three, so accounts that can outlive a run do:
// the shopper and the password-reset account are kept in e2e/.auth (git-
// ignored) and made again only when they no longer work. Only the visitor of
// the sign-up journey is new each run, and it deletes itself at the end.
import { randomBytes } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

export interface Credentials {
    name: string;
    email: string;
    password: string;
}

/** Accounts kept between runs. */
export type KeptRole = "shopper" | "forgetful";

// The token Cloudflare's always-pass test widget issues. Locally user-service
// holds the matching test secret (dev.sh infra up), so it is accepted.
export const TEST_CAPTCHA_TOKEN = "XXXX.DUMMY.TOKEN.XXXX";

const AUTH_DIR = path.resolve(__dirname, "../.auth");

export class TestAccounts {
    /** Where the signed-in shopper's cookies are kept between the setup and the journeys. */
    static readonly SHOPPER_STATE = path.join(AUTH_DIR, "shopper.json");

    /**
     * A fresh address and password. The domain must accept mail (user-service
     * checks its MX record); every email to it is caught by Mailpit, never sent.
     */
    static fresh(role: string): Credentials {
        const run = `${Date.now().toString(36)}${randomBytes(2).toString("hex")}`;
        return {
            name: `E2E ${role}`,
            email: `e2e.${role}.${run}@example-shop.com`,
            password: TestAccounts.newPassword(),
        };
    }

    static newPassword(): string {
        return `E2e-${randomBytes(12).toString("base64url")}`;
    }

    static kept(role: KeptRole): Credentials | null {
        const file = TestAccounts.file(role);
        return existsSync(file) ? (JSON.parse(readFileSync(file, "utf8")) as Credentials) : null;
    }

    static keep(role: KeptRole, credentials: Credentials): void {
        mkdirSync(AUTH_DIR, { recursive: true });
        writeFileSync(TestAccounts.file(role), JSON.stringify(credentials), { mode: 0o600 });
    }

    /**
     * Products the kept shopper has reviewed: a shopper reviews a product once
     * (a second review is a 409), so the checkout journey buys another one.
     */
    static reviewedByShopper(): string[] {
        const file = path.join(AUTH_DIR, "shopper-reviewed.json");
        return existsSync(file) ? (JSON.parse(readFileSync(file, "utf8")) as string[]) : [];
    }

    /** A new shopper has reviewed nothing. */
    static forgetShopperReviews(): void {
        writeFileSync(path.join(AUTH_DIR, "shopper-reviewed.json"), "[]");
    }

    static recordShopperReview(productId: string): void {
        mkdirSync(AUTH_DIR, { recursive: true });
        const reviewed = [...TestAccounts.reviewedByShopper(), productId];
        writeFileSync(path.join(AUTH_DIR, "shopper-reviewed.json"), JSON.stringify(reviewed));
    }

    /** The shopper the setup signed in; the journeys run with its cookies. */
    static shopper(): Credentials {
        const shopper = TestAccounts.kept("shopper");
        if (!shopper) throw new Error("No shopper: the setup project makes one");
        return shopper;
    }

    /**
     * Signs up through user-service directly, as tests/seed-session-users.mjs
     * does: the sign-up journey spends the gateway's sign-ups on the page.
     */
    static async register(credentials: Credentials): Promise<void> {
        const userService = process.env.USER_SERVICE_URL ?? "http://127.0.0.1:8001";
        const response = await fetch(`${userService}/api/v1/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ...credentials, captcha_token: TEST_CAPTCHA_TOKEN }),
        });
        if (response.status !== 202) {
            throw new Error(`Sign-up of ${credentials.email} answered ${response.status}: ${await response.text()}`);
        }
    }

    private static file(role: KeptRole): string {
        return path.join(AUTH_DIR, `${role}-credentials.json`);
    }
}
