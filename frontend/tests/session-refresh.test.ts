// Session refresh, against the running gateway and user-service.
//
// No mocks: every sign-in, refresh and logout goes to the real gateway, which
// rotates refresh tokens in Redis and treats a second use of a spent one as
// theft (user-service then revokes every session of the account). The classes
// under test are the production ones (lib/gateway-auth-client.ts,
// lib/session-refresher.ts, lib/session-proxy.ts). The only thing this suite
// supplies itself is the key the session cookie is encrypted with: it encodes
// and decodes its own cookies with a random one and never talks to the running
// frontend, so the app's secret is not needed.
//
// Some tests revoke every session of the test account on purpose; each test
// signs in afresh. Needs the stack up (`backend/local/dev.sh up`) and the
// session test account (`node tests/seed-session-users.mjs`). Run with:
//
//   npm run test:session-refresh
//
// Configuration (all optional):
//   GATEWAY_URL       default http://127.0.0.1:8000
//   SESSION_TEST_A    default session.a@example-shop.com  (password: SESSION_TEST_A_PASSWORD)

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { randomBytes, randomInt } from "node:crypto";
import { NextRequest } from "next/server";
import type { JWT } from "next-auth/jwt";
import { GatewayAuthClient, type BackendTokens, type RefreshOutcome, type SignedInBody } from "@/lib/gateway-auth-client";
import { SessionCookie } from "@/lib/session-cookie";
import { SessionProxy } from "@/lib/session-proxy";
import { SessionRefresher } from "@/lib/session-refresher";

// This suite's own cookie key (see the header). Read when a cookie is encoded.
process.env.NEXTAUTH_SECRET = randomBytes(32).toString("hex");

const GATEWAY = `${process.env.GATEWAY_URL ?? "http://127.0.0.1:8000"}/api/v1`;
const ACCOUNT = {
    email: process.env.SESSION_TEST_A ?? "session.a@example-shop.com",
    password: process.env.SESSION_TEST_A_PASSWORD ?? "CorrectHorse1",
};
const REFRESH_MARGIN_SECONDS = 120;
const GRACE_SECONDS = 120;
// Browsers drop cookies above 4096 bytes; NextAuth would split one this big.
const COOKIE_LIMIT = 4000;

const nowInSeconds = () => Math.floor(Date.now() / 1000);

const client = new GatewayAuthClient({ refresh: `${GATEWAY}/refresh`, logout: `${GATEWAY}/logout` });

// The gateway limits sign-ins and refreshes per client address, and trusts the
// forwarded address from loopback. Each call gets a fresh one (TEST-NET-2,
// random per run), so the suite never waits out a limit.
const runBlock = randomInt(0, 200);
let addressCount = 0;
const nextAddress = () => `198.51.${100 + Math.floor(runBlock / 2)}.${(++addressCount % 250) + 1}`;

/** Signs in at the gateway exactly as NextAuth's authorize() does. */
const signIn = async (): Promise<BackendTokens> => {
    const response = await fetch(`${GATEWAY}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded", "X-Forwarded-For": nextAddress() },
        body: new URLSearchParams({ username: ACCOUNT.email, password: ACCOUNT.password }),
    });
    assert.equal(response.status, 200, `sign-in failed with ${response.status}; seed the account first`);
    const tokens = client.tokensFrom(response, (await response.json()) as SignedInBody);
    assert.ok(tokens, "the sign-in response carried no refresh cookie");
    return tokens;
};

/** Whether the gateway accepts this access token. */
const accessWorks = async (accessToken: string): Promise<boolean> => {
    const response = await fetch(`${GATEWAY}/me`, {
        headers: { Authorization: `Bearer ${accessToken}`, "X-Forwarded-For": nextAddress() },
    });
    return response.status === 200;
};

const refreshed = (outcome: RefreshOutcome): BackendTokens => {
    assert.equal(outcome.kind, "refreshed", `expected a refresh, got ${JSON.stringify(outcome)}`);
    return (outcome as Extract<RefreshOutcome, { kind: "refreshed" }>).tokens;
};

const newRefresher = () =>
    new SessionRefresher(client, {
        marginSeconds: REFRESH_MARGIN_SECONDS,
        graceSeconds: GRACE_SECONDS,
        now: nowInSeconds,
    });

/** A session cookie as NextAuth writes it, for these backend tokens. */
const sessionToken = (tokens: BackendTokens, overrides: Partial<JWT> = {}): JWT => ({
    id: "session-refresh-test",
    email: ACCOUNT.email,
    role: "user",
    jwt: tokens.accessToken,
    token_expiry: tokens.accessExpiry,
    refresh_token: tokens.refreshToken,
    refresh_expiry: tokens.refreshExpiry,
    ...overrides,
});

const requestWith = async (path: string, token: JWT) =>
    new NextRequest(`http://localhost:30000${path}`, {
        headers: {
            cookie: `${SessionCookie.cookieName()}=${await SessionCookie.encode(token)}`,
            "x-forwarded-for": nextAddress(),
        },
    });

describe("gateway refresh tokens", { concurrency: false }, () => {
    it("a sign-in gives an access token and a longer-lived refresh token", async () => {
        const tokens = await signIn();
        assert.ok(tokens.accessExpiry > nowInSeconds(), "the access token is already expired");
        assert.ok(tokens.refreshExpiry > tokens.accessExpiry, "the refresh token ends before the access token");
        assert.ok(await accessWorks(tokens.accessToken));
    });

    it("a refresh rotates the refresh token and gives a working access token", async () => {
        const first = await signIn();
        const second = refreshed(await client.refresh(first.refreshToken, nextAddress()));
        assert.notEqual(second.refreshToken, first.refreshToken, "the refresh token was not rotated");
        assert.ok(await accessWorks(second.accessToken), "the refreshed access token is refused");
        // The rotated token works in turn: the chain continues.
        const third = refreshed(await client.refresh(second.refreshToken, nextAddress()));
        assert.ok(await accessWorks(third.accessToken));
    });

    it("without the refresher, a second use of a spent token signs the user out everywhere", async () => {
        // Why SessionRefresher exists: two requests refreshing with one token.
        const tokens = await signIn();
        const outcomes = await Promise.all([
            client.refresh(tokens.refreshToken, nextAddress()),
            client.refresh(tokens.refreshToken, nextAddress()),
        ]);
        const kinds = outcomes.map((outcome) => outcome.kind).sort();
        assert.deepEqual(kinds, ["refreshed", "rejected"], `outcomes: ${JSON.stringify(kinds)}`);
        const winner = refreshed(outcomes.find((outcome) => outcome.kind === "refreshed")!);
        assert.equal(await accessWorks(winner.accessToken), false, "reuse did not revoke the session");
    });

    it("signing out revokes the refresh token", async () => {
        const tokens = await signIn();
        await client.logout(tokens.refreshToken);
        const outcome = await client.refresh(tokens.refreshToken, nextAddress());
        assert.equal(outcome.kind, "rejected", "a revoked refresh token still refreshed");
    });
});

describe("SessionRefresher", { concurrency: false }, () => {
    it("is due only within the margin before the access token expires", () => {
        const refresher = newRefresher();
        const now = nowInSeconds();
        assert.equal(refresher.isDue(now + REFRESH_MARGIN_SECONDS + 60), false);
        assert.equal(refresher.isDue(now + REFRESH_MARGIN_SECONDS - 1), true);
        assert.equal(refresher.isDue(now - 1), true);
        assert.equal(refresher.isDue(Number.NaN), false, "a session without an expiry was refreshed");
    });

    it("sends a refresh token to the gateway once, however many requests refresh at the same time", async () => {
        const refresher = newRefresher();
        const tokens = await signIn();
        const outcomes = await Promise.all(
            Array.from({ length: 8 }, () => refresher.refresh(tokens.refreshToken, nextAddress())),
        );
        const fresh = refreshed(outcomes[0]);
        for (const outcome of outcomes) {
            assert.equal(refreshed(outcome).accessToken, fresh.accessToken, "requests got different tokens");
        }
        // A second use would have revoked everything (previous test); these still work.
        assert.ok(await accessWorks(fresh.accessToken), "the session was revoked: the token was used twice");
        refreshed(await client.refresh(fresh.refreshToken, nextAddress()));
    });

    it("gives a late request with the spent token the same new tokens, without asking again", async () => {
        const refresher = newRefresher();
        const tokens = await signIn();
        const first = refreshed(await refresher.refresh(tokens.refreshToken, nextAddress()));
        // The browser had not stored the new cookie yet when this request left.
        const late = refreshed(await refresher.refresh(tokens.refreshToken, nextAddress()));
        assert.equal(late.accessToken, first.accessToken);
        assert.ok(await accessWorks(first.accessToken), "the late request reused the spent token");
    });

    it("forgets a refresh that could not reach the gateway, so the next request retries", async () => {
        // Port 9 (discard) is closed: a real connection failure, not a stand-in.
        const offline = new SessionRefresher(
            new GatewayAuthClient({ refresh: "http://127.0.0.1:9/api/v1/refresh", logout: "http://127.0.0.1:9/api/v1/logout" }),
            { marginSeconds: REFRESH_MARGIN_SECONDS, graceSeconds: GRACE_SECONDS, now: nowInSeconds },
        );
        const first = offline.refresh("any-token", null);
        assert.equal((await first).kind, "unavailable");
        const second = offline.refresh("any-token", null);
        assert.notEqual(second, first, "a failed attempt was remembered");
        assert.equal((await second).kind, "unavailable");
    });
});

describe("SessionProxy", { concurrency: false }, () => {
    const newProxy = () => new SessionProxy(newRefresher(), SessionCookie, nowInSeconds);

    it("refreshes a session about to expire, for this request and for the browser", async () => {
        const tokens = await signIn();
        // Same tokens, but the access token is treated as one about to expire.
        const request = await requestWith("/cart", sessionToken(tokens, { token_expiry: nowInSeconds() + 30 }));
        const response = await newProxy().handle(request);

        const written = response.cookies.get(SessionCookie.cookieName())?.value;
        assert.ok(written, "no new session cookie for the browser");
        assert.ok(written.length < COOKIE_LIMIT, `the session cookie is ${written.length} bytes`);
        const session = await SessionCookie.decode(written);
        assert.ok(session, "the new session cookie does not decode");
        assert.notEqual(session.jwt, tokens.accessToken, "the access token was not replaced");
        assert.notEqual(session.refresh_token, tokens.refreshToken, "the refresh token was not replaced");
        assert.ok(Number(session.token_expiry) > nowInSeconds() + REFRESH_MARGIN_SECONDS);
        assert.equal(session.email, ACCOUNT.email, "the rest of the session was not kept");
        assert.ok(await accessWorks(String(session.jwt)));

        // The page being rendered reads the new cookie too, not the expiring one.
        const forwarded = response.headers.get("x-middleware-request-cookie") ?? "";
        assert.ok(forwarded.includes(written), "the request was not given the new session cookie");
    });

    it("leaves a session with time left alone", async () => {
        const tokens = await signIn();
        const response = await newProxy().handle(await requestWith("/cart", sessionToken(tokens)));
        assert.equal(response.cookies.get(SessionCookie.cookieName()), undefined, "a fresh session was rewritten");
    });

    it("ends the session when the gateway refuses the refresh token", async () => {
        const tokens = await signIn();
        const refused = sessionToken(tokens, { token_expiry: nowInSeconds() + 30, refresh_token: "not-a-refresh-token" });
        const response = await newProxy().handle(await requestWith("/cart", refused));

        const cleared = response.cookies.get(SessionCookie.cookieName());
        assert.ok(cleared, "the session cookie was not cleared");
        assert.equal(cleared.value, "");
        assert.equal(cleared.maxAge, 0);
        const forwarded = response.headers.get("x-middleware-request-cookie") ?? "";
        assert.ok(!forwarded.includes(SessionCookie.cookieName()), "the request still carries the ended session");
    });

    it("ends a session from before refresh tokens once its access token expires", async () => {
        const tokens = await signIn();
        const legacy = sessionToken(tokens, { token_expiry: nowInSeconds() - 1, refresh_token: undefined, refresh_expiry: undefined });
        const response = await newProxy().handle(await requestWith("/orders", legacy));
        assert.equal(response.cookies.get(SessionCookie.cookieName())?.maxAge, 0);
    });

    it("never refreshes on NextAuth's own routes, which write the cookie themselves", async () => {
        const tokens = await signIn();
        const due = sessionToken(tokens, { token_expiry: nowInSeconds() + 30 });
        for (const path of ["/api/auth/signout", "/api/auth/session", "/api/auth/callback/credentials"]) {
            const response = await newProxy().handle(await requestWith(path, due));
            assert.equal(response.cookies.get(SessionCookie.cookieName()), undefined, `${path} was refreshed`);
        }
        // Not spent by the proxy: it still refreshes.
        refreshed(await client.refresh(tokens.refreshToken, nextAddress()));
    });
});
