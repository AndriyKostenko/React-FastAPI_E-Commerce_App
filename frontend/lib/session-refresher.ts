import type { RefreshOutcome } from "@/lib/gateway-auth-client";

/** What the refresher needs from the gateway: one refresh call. */
export interface RefreshClient {
    refresh(refreshToken: string, forwardedFor: string | null): Promise<RefreshOutcome>;
}

export interface SessionRefresherOptions {
    /** Refresh when the access token has this many seconds left, or fewer. */
    marginSeconds: number;
    /**
     * How long a finished refresh is remembered. A request that started before
     * the browser stored the new cookie still carries the spent token; within
     * this window it gets the same new tokens instead of reusing the spent one.
     */
    graceSeconds: number;
    now: () => number;
}

interface Attempt {
    outcome: Promise<RefreshOutcome>;
    /** Unix seconds after which the attempt is forgotten; infinite while in flight. */
    keepUntil: number;
}

/**
 * Refreshes backend tokens so that each refresh token reaches the gateway at
 * most once.
 *
 * That is a hard requirement, not an optimisation: the gateway rotates refresh
 * tokens, and user-service treats a second use of a spent one as theft. It
 * bumps the account's token version, which revokes every session and every
 * access token the user has. A page load sends several requests at once, and
 * each would otherwise refresh with the same token.
 *
 * So concurrent callers with the same token share one call, and the result
 * stays available for `graceSeconds` after it lands, for requests the browser
 * sent before it stored the new cookie. A refresh that could not reach the
 * gateway is forgotten at once, so the next request tries again.
 *
 * The memory is this process's. It holds while one Next process serves the
 * shop (one container on one host, as deployed); running several would need
 * the same guard in shared storage, or a reuse window in user-service.
 */
export class SessionRefresher {
    private readonly attempts = new Map<string, Attempt>();

    constructor(
        private readonly client: RefreshClient,
        private readonly options: SessionRefresherOptions,
    ) {}

    /** Whether an access token expiring at `accessExpiry` (unix seconds) should be refreshed now. */
    isDue(accessExpiry: number): boolean {
        return Number.isFinite(accessExpiry) && accessExpiry - this.options.now() <= this.options.marginSeconds;
    }

    refresh(refreshToken: string, forwardedFor: string | null): Promise<RefreshOutcome> {
        this.forgetExpired();
        const known = this.attempts.get(refreshToken);
        if (known) {
            return known.outcome;
        }

        const attempt: Attempt = {
            outcome: this.client.refresh(refreshToken, forwardedFor),
            keepUntil: Number.POSITIVE_INFINITY,
        };
        this.attempts.set(refreshToken, attempt);
        attempt.outcome.then(
            (outcome) => {
                if (outcome.kind === "unavailable") {
                    // Nothing was spent (as far as anyone can tell): let the next request retry.
                    this.attempts.delete(refreshToken);
                } else {
                    // Refreshed: late requests with the spent token get these tokens.
                    // Rejected: they get the same answer without asking again.
                    attempt.keepUntil = this.options.now() + this.options.graceSeconds;
                }
            },
            () => this.attempts.delete(refreshToken),
        );
        return attempt.outcome;
    }

    private forgetExpired(): void {
        const now = this.options.now();
        this.attempts.forEach((attempt, token) => {
            if (attempt.keepUntil < now) {
                this.attempts.delete(token);
            }
        });
    }
}
