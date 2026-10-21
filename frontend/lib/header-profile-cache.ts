/** What the header shows of the signed-in user's stored profile. */
export interface HeaderProfile {
    name: string;
    image: string | null;
}

interface Entry {
    profile: HeaderProfile;
    /** Epoch milliseconds after which the entry is read again. */
    until: number;
}

/**
 * The header's copy of each signed-in user's name and picture, kept briefly.
 *
 * The header is rendered on every full page load, and the gateway allows a
 * user only a few profile reads a minute (GET /users/{id}); without this the
 * header would spend the budget the account page needs. A change made through
 * the site (the gateway proxy route) replaces the user's entry with the saved
 * profile, or forgets it, at once, so a new avatar shows on the next render; a
 * change made elsewhere (AdminJS, another device) shows once the entry expires.
 *
 * The memory is this process's, like SessionRefresher's: correct for one Next
 * process. A failed read is never cached.
 */
export class HeaderProfileCache {
    private readonly entries = new Map<string, Entry>();

    constructor(
        private readonly ttlMs: number,
        private readonly now: () => number = Date.now,
    ) {}

    get(userId: string): HeaderProfile | undefined {
        const entry = this.entries.get(userId);
        if (!entry) return undefined;
        if (entry.until <= this.now()) {
            this.entries.delete(userId);
            return undefined;
        }
        return entry.profile;
    }

    set(userId: string, profile: HeaderProfile): void {
        this.forgetExpired();
        this.entries.set(userId, { profile, until: this.now() + this.ttlMs });
    }

    forget(userId: string): void {
        this.entries.delete(userId);
    }

    /**
     * The header's part of a response body, when the body is this user's own
     * profile (what PATCH /users/{id} and the avatar calls return); otherwise
     * null, as for an address or a password change.
     */
    static profileFrom(body: unknown, userId: string): HeaderProfile | null {
        if (typeof body !== "object" || body === null) return null;
        const { id, name, image } = body as Record<string, unknown>;
        if (id !== userId || typeof name !== "string") return null;
        if (image !== null && typeof image !== "string") return null;
        return { name, image };
    }

    private forgetExpired(): void {
        const now = this.now();
        this.entries.forEach((entry, userId) => {
            if (entry.until <= now) this.entries.delete(userId);
        });
    }
}

const HEADER_PROFILE_TTL_MS = 60_000;

// One instance per process, shared by the pages that read it and the proxy
// route that updates it; on globalThis because the dev server re-evaluates
// modules on every edit and may bundle the two separately.
const holder = globalThis as typeof globalThis & { __headerProfileCache?: HeaderProfileCache };
export const headerProfileCache = (holder.__headerProfileCache ??= new HeaderProfileCache(HEADER_PROFILE_TTL_MS));
