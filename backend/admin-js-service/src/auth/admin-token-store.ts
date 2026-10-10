import { randomUUID } from 'node:crypto';
import { setTimeout as sleep } from 'node:timers/promises';
import type { Redis } from 'ioredis';

import { AdminTokens, GatewayClient, GatewayError } from '../gateway/gateway-client.js';

/** The session can no longer reach the backend; the admin must sign in again. */
export class AdminSessionExpiredError extends Error {}

// Refresh this long before the access token expires, so a request never
// starts with a token that lapses on its way through the gateway.
const REFRESH_MARGIN_MS = 2 * 60_000;
const LOCK_TTL_MS = 10_000;
const LOCK_WAIT_MS = 150;

/**
 * An admin session's tokens, kept in Redis and never in the browser.
 *
 * AdminJS renders the signed-in admin (`currentAdmin`) into every page as
 * `window.REDUX_STATE`, so anything stored there is readable by any script on
 * the page. The session keeps only an opaque reference; the tokens live here.
 *
 * Refreshing is serialised. user-service rotates the refresh token on every
 * use and treats a second use of the old one as theft, revoking every session
 * the admin has, so two requests that both see an expiring token must not
 * both refresh with it: one does, the other waits and reads the result.
 */
export class AdminTokenStore {
    private readonly inFlight = new Map<string, Promise<AdminTokens>>();

    constructor(
        private readonly redis: Redis,
        private readonly prefix: string,
        private readonly gateway: GatewayClient,
        private readonly ttlMs: number,
    ) {}

    /** Store a new session's tokens; returns the reference the session keeps. */
    async open(tokens: AdminTokens): Promise<string> {
        const sessionRef = randomUUID();
        await this.write(sessionRef, tokens);
        return sessionRef;
    }

    /** A usable access token for this session, refreshed first if it is about to expire. */
    async accessToken(sessionRef: string): Promise<string> {
        const tokens = await this.read(sessionRef);
        if (tokens.accessExpiresAt - Date.now() > REFRESH_MARGIN_MS) {
            return tokens.accessToken;
        }
        let pending = this.inFlight.get(sessionRef);
        if (!pending) {
            pending = this.refresh(sessionRef, tokens).finally(() => this.inFlight.delete(sessionRef));
            this.inFlight.set(sessionRef, pending);
        }
        return (await pending).accessToken;
    }

    /** Forget the session's tokens, returning them for a last revocation call. */
    async close(sessionRef: string): Promise<AdminTokens | null> {
        const raw = await this.redis.getdel(this.key(sessionRef));
        return raw ? AdminTokenStore.parse(raw) : null;
    }

    private async refresh(sessionRef: string, seen: AdminTokens): Promise<AdminTokens> {
        const lockKey = `${this.key(sessionRef)}:refreshing`;
        const deadline = Date.now() + LOCK_TTL_MS;
        while (Date.now() < deadline) {
            const locked = await this.redis.set(lockKey, '1', 'PX', LOCK_TTL_MS, 'NX');
            if (locked === 'OK') {
                try {
                    // Another process may have refreshed while we waited for the lock.
                    const current = await this.read(sessionRef);
                    if (current.refreshToken !== seen.refreshToken) return current;
                    const renewed = await this.gateway.refresh(current.refreshToken);
                    await this.write(sessionRef, renewed);
                    return renewed;
                } catch (error) {
                    if (error instanceof GatewayError && error.status >= 400 && error.status < 500) {
                        // Refused (expired, revoked, or no longer an admin): the
                        // session is over. Anything else may be passing.
                        await this.redis.del(this.key(sessionRef));
                        throw new AdminSessionExpiredError(error.detail);
                    }
                    throw error;
                } finally {
                    await this.redis.del(lockKey);
                }
            }
            await sleep(LOCK_WAIT_MS);
            const current = await this.read(sessionRef);
            if (current.refreshToken !== seen.refreshToken) return current;
        }
        throw new AdminSessionExpiredError('Timed out waiting for the session to be refreshed');
    }

    private async read(sessionRef: string): Promise<AdminTokens> {
        const raw = await this.redis.get(this.key(sessionRef));
        if (!raw) throw new AdminSessionExpiredError('No tokens for this session');
        return AdminTokenStore.parse(raw);
    }

    private async write(sessionRef: string, tokens: AdminTokens): Promise<void> {
        await this.redis.set(this.key(sessionRef), JSON.stringify(tokens), 'PX', this.ttlMs);
    }

    private key(sessionRef: string): string {
        return `${this.prefix}session-tokens:${sessionRef}`;
    }

    private static parse(raw: string): AdminTokens {
        const value: Partial<AdminTokens> = JSON.parse(raw);
        if (
            typeof value.accessToken !== 'string' ||
            typeof value.refreshToken !== 'string' ||
            typeof value.accessExpiresAt !== 'number'
        ) {
            throw new AdminSessionExpiredError('Stored session tokens are unreadable');
        }
        return { accessToken: value.accessToken, refreshToken: value.refreshToken, accessExpiresAt: value.accessExpiresAt };
    }
}
