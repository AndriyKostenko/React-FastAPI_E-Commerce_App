// Session isolation between users, against the running local stack.
//
// No mocks: every request goes to the real frontend (and through it to the
// real gateway and user-service). It needs the stack up (`backend/local/dev.sh up`)
// and two verified accounts. Create them once with:
//
//   node tests/seed-session-users.mjs
//
// Run the tests with:
//
//   npm run test:session
//
// Configuration (all optional):
//   FRONTEND_URL      default http://localhost:30000
//   SESSION_TEST_A    default session.a@example-shop.com  (password: SESSION_TEST_A_PASSWORD)
//   SESSION_TEST_B    default session.b@example-shop.com  (password: SESSION_TEST_B_PASSWORD)

import { describe, it, before } from "node:test";
import assert from "node:assert/strict";

// The token Cloudflare's test widget issues. Locally user-service holds the
// always-pass test secret (dev.sh), so it is accepted; a real secret refuses it.
const CAPTCHA_TOKEN = "XXXX.DUMMY.TOKEN.XXXX";

const FRONTEND = process.env.FRONTEND_URL ?? "http://localhost:30000";
const ACCOUNTS = {
    a: {
        email: process.env.SESSION_TEST_A ?? "session.a@example-shop.com",
        password: process.env.SESSION_TEST_A_PASSWORD ?? "CorrectHorse1",
    },
    b: {
        email: process.env.SESSION_TEST_B ?? "session.b@example-shop.com",
        password: process.env.SESSION_TEST_B_PASSWORD ?? "CorrectHorse2",
    },
};

/** Cookie header built from every Set-Cookie a response sent. */
const cookieHeader = (response, previous = "") => {
    const jar = new Map(
        previous
            .split("; ")
            .filter(Boolean)
            .map((pair) => {
                const [name, ...rest] = pair.split("=");
                return [name, rest.join("=")];
            }),
    );
    for (const raw of response.headers.getSetCookie()) {
        const [pair] = raw.split(";");
        const [name, ...rest] = pair.split("=");
        if (rest.join("=") === "") {
            jar.delete(name);
        } else {
            jar.set(name, rest.join("="));
        }
    }
    return [...jar].map(([name, value]) => `${name}=${value}`).join("; ");
};

const LOGIN_RETRY_MS = 65_000;

/**
 * Signs in through NextAuth exactly as the login form does; returns the cookie header.
 * The gateway limits logins per client, so a 429 waits out its window and tries again.
 */
const signIn = async ({ email, password }, { attempt = 1, forwardedFor, retryOnLimit = true } = {}) => {
    const csrfResponse = await fetch(`${FRONTEND}/api/auth/csrf`, {
        headers: forwardedFor ? { "X-Forwarded-For": forwardedFor } : {},
    });
    let cookies = cookieHeader(csrfResponse);
    const { csrfToken } = await csrfResponse.json();

    const response = await fetch(`${FRONTEND}/api/auth/callback/credentials`, {
        method: "POST",
        redirect: "manual",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            Cookie: cookies,
            ...(forwardedFor ? { "X-Forwarded-For": forwardedFor } : {}),
        },
        body: new URLSearchParams({ csrfToken, email, password, captchaToken: CAPTCHA_TOKEN, json: "true" }),
    });
    cookies = cookieHeader(response, cookies);
    if (response.status === 401 && retryOnLimit && attempt < 3) {
        // NextAuth reports a gateway 429 as a 401; wait out the one-minute window.
        await new Promise((resolve) => setTimeout(resolve, LOGIN_RETRY_MS));
        return signIn({ email, password }, { attempt: attempt + 1, forwardedFor, retryOnLimit });
    }
    assert.equal(response.status, 200, `sign-in for ${email} failed with ${response.status}`);
    return cookies;
};

// One sign-in per account per run: logins are rate limited per client.
const sessionCache = new Map();
const signedInAs = (account) => {
    if (!sessionCache.has(account.email)) {
        sessionCache.set(account.email, signIn(account));
    }
    return sessionCache.get(account.email);
};

/** The session as the server sees it for this cookie header. */
const sessionOf = async (cookies) => {
    const response = await fetch(`${FRONTEND}/api/auth/session`, { headers: { Cookie: cookies } });
    return response.json();
};

/** A page rendered for this cookie header. */
const pageFor = async (cookies) => {
    const response = await fetch(`${FRONTEND}/`, { headers: cookies ? { Cookie: cookies } : {} });
    assert.equal(response.status, 200);
    return response.text();
};

describe("session isolation between users", { concurrency: false }, () => {
    let a;
    let b;

    before(async () => {
        a = { ...ACCOUNTS.a, cookies: await signedInAs(ACCOUNTS.a) };
        b = { ...ACCOUNTS.b, cookies: await signedInAs(ACCOUNTS.b) };
        // The account id is the marker: it appears in a rendered page only for
        // the session it belongs to.
        a.id = (await sessionOf(a.cookies)).user.id;
        b.id = (await sessionOf(b.cookies)).user.id;
        assert.notEqual(a.id, b.id, "the two test accounts must be different users");
    });

    it("each sign-in gets a session for its own account", async () => {
        const sessionA = await sessionOf(a.cookies);
        const sessionB = await sessionOf(b.cookies);
        assert.equal(sessionA.user.email, a.email);
        assert.equal(sessionB.user.email, b.email);
    });

    it("a signed-out visitor sees neither account", async () => {
        const html = await pageFor("");
        assert.ok(!html.includes(a.id), "anonymous page contains user A's id");
        assert.ok(!html.includes(b.id), "anonymous page contains user B's id");
    });

    it("a signed-in page shows its own account only, even under concurrent requests", async () => {
        // Requests from both users run at the same time. Shared server state would
        // let one user's session answer for the other: each response has to match
        // the cookies that were sent with it.
        // Batches keep the dev server from refusing connections; each batch still
        // overlaps, which is where the race happens.
        const rounds = Number(process.env.SESSION_TEST_ROUNDS ?? 40);
        const batch = 24;
        const results = [];
        for (let i = 0; i < rounds; i += batch) {
            const jobs = [];
            for (let j = i; j < Math.min(i + batch, rounds); j++) {
                jobs.push(pageFor(a.cookies).then((html) => ({ who: "a", html })));
                jobs.push(pageFor(b.cookies).then((html) => ({ who: "b", html })));
            }
            results.push(...(await Promise.all(jobs)));
        }

        for (const { who, html } of results) {
            const own = who === "a" ? a : b;
            const other = who === "a" ? b : a;
            assert.ok(html.includes(own.id), `page for ${who} does not show its own account`);
            assert.ok(!html.includes(other.id), `page for ${who} shows the other account`);
        }
    });

    it("signing out ends that session and leaves the other one alone", async () => {
        const csrfResponse = await fetch(`${FRONTEND}/api/auth/csrf`, { headers: { Cookie: b.cookies } });
        const { csrfToken } = await csrfResponse.json();
        const signOut = await fetch(`${FRONTEND}/api/auth/signout`, {
            method: "POST",
            redirect: "manual",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                Cookie: cookieHeader(csrfResponse, b.cookies),
            },
            body: new URLSearchParams({ csrfToken, json: "true" }),
        });
        assert.ok(signOut.status < 400, `sign-out returned ${signOut.status}`);

        const afterSignOut = await sessionOf(cookieHeader(signOut, b.cookies));
        assert.equal(Object.keys(afterSignOut).length, 0, "B's session survived sign-out");

        const stillSignedInA = await sessionOf(a.cookies);
        assert.equal(stillSignedInA.user.id, a.id, "signing B out ended A's session");
    });
});

describe("the access token stays on the server", { concurrency: false }, () => {
    let cookies;

    before(async () => {
        cookies = await signedInAs(ACCOUNTS.a);
    });

    it("the session endpoint does not return the access token to the browser", async () => {
        const session = await sessionOf(cookies);
        assert.equal(session.jwt, undefined, "/api/auth/session exposes the access token");
    });

    it("a rendered page does not carry the access token", async () => {
        const session = await sessionOf(cookies);
        // The token is an HS/EdDSA JWT: three base64url parts. Anything that
        // looks like one, in the HTML, reached the page's JavaScript.
        const html = await pageFor(cookies);
        const jwtShape = /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/;
        assert.equal(jwtShape.test(html), false, "the page HTML contains a JWT");
        assert.ok(session.user, "precondition: the session is signed in");
    });
});

describe("the gateway proxy", { concurrency: false }, () => {
    let a;
    let b;

    before(async () => {
        a = { ...ACCOUNTS.a, cookies: await signedInAs(ACCOUNTS.a) };
        b = { ...ACCOUNTS.b, cookies: await signedInAs(ACCOUNTS.b) };
        a.id = (await sessionOf(a.cookies)).user.id;
        b.id = (await sessionOf(b.cookies)).user.id;
    });

    it("refuses an anonymous caller on an authenticated route", async () => {
        const response = await fetch(`${FRONTEND}/api/gateway/api/v1/orders/user/${a.id}`);
        assert.equal(response.status, 401, "anonymous call reached the gateway as a user");
    });

    it("serves a signed-in user's own authenticated call", async () => {
        const response = await fetch(`${FRONTEND}/api/gateway/api/v1/orders/user/${a.id}`, {
            headers: { Cookie: a.cookies },
        });
        assert.equal(response.status, 200);
        const orders = await response.json();
        assert.ok(Array.isArray(orders), "the proxy did not return the order list");
        for (const order of orders) {
            assert.equal(order.user_id, a.id, "an order in A's list belongs to someone else");
        }
    });

    it("does not let one user read another user's orders through the proxy", async () => {
        const response = await fetch(`${FRONTEND}/api/gateway/api/v1/orders/user/${b.id}`, {
            headers: { Cookie: a.cookies },
        });
        assert.notEqual(response.status, 200, "user A read user B's orders");
    });

    it("forwards only the versioned API", async () => {
        for (const path of ["admin", "api/v2/orders", "api/v1/../../admin"]) {
            const response = await fetch(`${FRONTEND}/api/gateway/${path}`, { headers: { Cookie: a.cookies } });
            assert.ok([400, 404].includes(response.status), `${path} answered ${response.status}`);
        }
    });

    it("refuses a write that comes from another site", async () => {
        const response = await fetch(`${FRONTEND}/api/gateway/api/v1/orders/user/${a.id}`, {
            method: "POST",
            headers: { Cookie: a.cookies, Origin: "https://evil.example", "Content-Type": "application/json" },
            body: "{}",
        });
        assert.equal(response.status, 403);
    });

    it("accepts a same-origin write on whichever address the shop was opened at", async () => {
        // The same server reached as 127.0.0.1 instead of localhost: the page and
        // the proxy share that origin, so the write is not cross-site. The check
        // compares Origin with the Host the browser used, not a fixed list.
        const alternate = new URL(FRONTEND);
        alternate.hostname = alternate.hostname === "localhost" ? "127.0.0.1" : "localhost";
        const response = await fetch(`${alternate.origin}/api/gateway/api/v1/orders/user/${a.id}`, {
            method: "POST",
            headers: { Cookie: a.cookies, Origin: alternate.origin, "Content-Type": "application/json" },
            body: "{}",
        });
        // Past the origin check: whatever the gateway answers, it is not our 403.
        assert.notEqual(response.status, 403, await response.text());
    });
});

// Rate limits follow the browser's address. The frontend forwards the address
// the edge proxy recorded (X-Forwarded-For), and the gateway trusts it only from
// the frontend's network. Each test client here is a different address.
describe("rate limits follow the client", { concurrency: false }, () => {
    const GATEWAY = process.env.GATEWAY_URL ?? "http://127.0.0.1:8000";

    it("sign-ins from different clients are not counted against each other", async () => {
        // Eight valid sign-ins, each from its own address. If the frontend's own
        // address were used for all of them, the login limit would trip after a few.
        const base = 10 + Math.floor(Math.random() * 200);
        for (let i = 0; i < 8; i++) {
            // No retry: a rate-limit answer must fail this test, not wait it out.
            const cookies = await signIn(ACCOUNTS.a, { forwardedFor: `198.51.100.${base + i}`, retryOnLimit: false });
            assert.ok(cookies.includes("session-token"), `client ${i} could not sign in`);
        }
    });

    it("one client that keeps trying is still limited", async () => {
        // Direct to the gateway, so the status is the gateway's own answer.
        const forwardedFor = `203.0.113.${10 + Math.floor(Math.random() * 200)}`;
        let limited = false;
        for (let attempt = 0; attempt < 15 && !limited; attempt++) {
            const response = await fetch(`${GATEWAY}/api/v1/login`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Forwarded-For": forwardedFor,
                },
                body: new URLSearchParams({ username: ACCOUNTS.a.email, password: "wrong-password", captcha_token: CAPTCHA_TOKEN }),
            });
            limited = response.status === 429;
        }
        assert.ok(limited, "the login limit never applied to a single client");
    });
});
