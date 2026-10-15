// Deterministic race test for the server-side session manager.
//
// The production manager is one shared instance (`sessionManagaer`), used by
// every request. A bug there would show only when two requests interleave in a
// particular order, which a live server rarely produces. So this test controls
// the order itself:
//
//   - one manager instance, as in production;
//   - each request carries its own cookies, bound with AsyncLocalStorage (the
//     same mechanism next/headers uses to tell requests apart);
//   - the token decoder is a controlled seam: each decode finishes only when the
//     test says so, so the test picks the interleaving.
//
// The seam is the approved one: the decoder is replaced, not the session logic.
//
// Run with:  npm run test:race

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { AsyncLocalStorage } from "node:async_hooks";
import type { JWT } from "next-auth/jwt";
import { SessionManager, type SessionDependencies } from "@/actions/getCurrentUser";

const SESSION_COOKIE = "next-auth.session-token";

/** Cookies of the request being handled, as next/headers would expose them. */
const requestCookies = new AsyncLocalStorage<Record<string, string>>();

/** Runs `work` as the request that carries this session cookie. */
const asRequest = <T>(sessionCookie: string, work: () => Promise<T>): Promise<T> =>
    requestCookies.run({ [SESSION_COOKIE]: sessionCookie }, work);

const tokenFor = (id: string, overrides: Partial<JWT> = {}): JWT =>
    ({
        id,
        email: `${id}@example.test`,
        name: `User ${id}`,
        jwt: `access-${id}`,
        role: "user",
        token_expiry: Math.floor(Date.now() / 1000) + 3600,
        ...overrides,
    }) as JWT;

/**
 * A decoder whose answers the test releases one by one. `decodeToken` parks
 * until `release(raw)` is called for that cookie, so the test chooses which
 * request finishes first.
 */
const controlledDecoder = () => {
    const parked = new Map<string, (token: JWT | null) => void>();
    return {
        decodeToken: (raw: string) =>
            new Promise<JWT | null>((resolve) => {
                parked.set(raw, resolve);
            }),
        release(raw: string, token: JWT | null) {
            const resolve = parked.get(raw);
            if (!resolve) throw new Error(`no decode is waiting for ${raw}`);
            parked.delete(raw);
            resolve(token);
        },
        /** Resolves once `count` decodes are parked, so every request has reached the decoder. */
        async untilParked(count: number) {
            while (parked.size < count) {
                await new Promise((resolve) => setImmediate(resolve));
            }
        },
    };
};

const sharedManager = (decoder: ReturnType<typeof controlledDecoder>) => {
    const deps: SessionDependencies = {
        readCookie: async (name) => requestCookies.getStore()?.[name],
        decodeToken: decoder.decodeToken,
    };
    // One instance for every request, exactly as the production singleton.
    return new SessionManager(deps);
};

describe("the session manager under interleaved requests", () => {
    it("two requests that finish in opposite order each get their own user", async () => {
        const decoder = controlledDecoder();
        const manager = sharedManager(decoder);

        const userA = asRequest("cookie-a", () => manager.getCurrentUser());
        const userB = asRequest("cookie-b", () => manager.getCurrentUser());
        await decoder.untilParked(2);

        // B finishes first, A last: the order that exposes shared state.
        decoder.release("cookie-b", tokenFor("user-b"));
        decoder.release("cookie-a", tokenFor("user-a"));

        assert.equal((await userA)?.id, "user-a", "request A was answered with another user");
        assert.equal((await userB)?.id, "user-b", "request B was answered with another user");
    });

    it("the same pair in the other order is also correct", async () => {
        const decoder = controlledDecoder();
        const manager = sharedManager(decoder);

        const userA = asRequest("cookie-a", () => manager.getCurrentUser());
        const userB = asRequest("cookie-b", () => manager.getCurrentUser());
        await decoder.untilParked(2);

        decoder.release("cookie-a", tokenFor("user-a"));
        decoder.release("cookie-b", tokenFor("user-b"));

        assert.equal((await userA)?.id, "user-a");
        assert.equal((await userB)?.id, "user-b");
    });

    it("the access token each request gets is its own, whichever finishes first", async () => {
        const decoder = controlledDecoder();
        const manager = sharedManager(decoder);

        const jwtA = asRequest("cookie-a", () => manager.getCurrentUserJWT());
        const jwtB = asRequest("cookie-b", () => manager.getCurrentUserJWT());
        await decoder.untilParked(2);

        decoder.release("cookie-b", tokenFor("user-b"));
        decoder.release("cookie-a", tokenFor("user-a"));

        assert.equal(await jwtA, "access-user-a");
        assert.equal(await jwtB, "access-user-b");
    });

    it("forty overlapping requests from six users, released in shuffled order", async () => {
        const decoder = controlledDecoder();
        const manager = sharedManager(decoder);
        const users = ["u1", "u2", "u3", "u4", "u5", "u6"];

        // Each request gets its own cookie, so each is parked separately.
        const requests = Array.from({ length: 40 }, (_, index) => {
            const user = users[index % users.length];
            const cookie = `cookie-${index}-${user}`;
            return { user, cookie, result: asRequest(cookie, () => manager.getCurrentUser()) };
        });
        await decoder.untilParked(requests.length);

        // A fixed shuffle: deterministic, and far from the request order.
        const order = requests.map((_, index) => (index * 17) % requests.length);
        for (const index of order) {
            const { user, cookie } = requests[index];
            decoder.release(cookie, tokenFor(user));
        }

        for (const { user, result } of requests) {
            assert.equal((await result)?.id, user, `a request for ${user} was answered with another user`);
        }
    });

    it("a request with no session cookie is anonymous even while others are signed in", async () => {
        const decoder = controlledDecoder();
        const manager = sharedManager(decoder);

        const signedIn = asRequest("cookie-a", () => manager.getCurrentUser());
        const anonymous = asRequest("", () => manager.getCurrentUser());
        await decoder.untilParked(1);
        decoder.release("cookie-a", tokenFor("user-a"));

        assert.equal((await signedIn)?.id, "user-a");
        assert.equal(await anonymous, null);
    });

    it("an expired session is refused, and it does not leak into a concurrent valid one", async () => {
        const decoder = controlledDecoder();
        const manager = sharedManager(decoder);
        const expired = tokenFor("user-old", { token_expiry: Math.floor(Date.now() / 1000) - 60 });

        const oldSession = asRequest("cookie-old", () => manager.getCurrentUser());
        const freshSession = asRequest("cookie-a", () => manager.getCurrentUser());
        await decoder.untilParked(2);

        decoder.release("cookie-a", tokenFor("user-a"));
        decoder.release("cookie-old", expired);

        assert.equal(await oldSession, null);
        assert.equal((await freshSession)?.id, "user-a");
    });
});
