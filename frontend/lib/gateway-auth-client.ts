/**
 * The backend session a NextAuth session carries. Expiries are unix seconds.
 *
 * The gateway returns the access token in the response body and the refresh
 * token only as an HttpOnly Set-Cookie. Sign-in happens on the Next server, so
 * that cookie reaches this code, not the browser; it is kept inside the
 * encrypted NextAuth cookie, next to the access token.
 */
export interface BackendTokens {
    accessToken: string;
    accessExpiry: number;
    refreshToken: string;
    refreshExpiry: number;
}

/** The fields a gateway sign-in or refresh response body carries. */
export interface SignedInBody {
    access_token: string;
    token_expiry: number;
    user_role: string;
    user_id: string;
}

export type RefreshOutcome =
    /** New tokens; the refresh token that was sent is now spent. */
    | { kind: "refreshed"; tokens: BackendTokens }
    /** The refresh token is spent, revoked or expired: the session is over. */
    | { kind: "rejected"; status: number }
    /** The gateway could not answer (down, rate limited): keep the session and try later. */
    | { kind: "unavailable"; reason: string };

export interface GatewayAuthEndpoints {
    refresh: string;
    logout: string;
}

const REFRESH_COOKIE = "refresh_token";

const nowInSeconds = (): number => Math.floor(Date.now() / 1000);

/**
 * The gateway's refresh and logout endpoints, called from the Next server with
 * the refresh token as the cookie the gateway expects.
 */
export class GatewayAuthClient {
    constructor(
        private readonly endpoints: GatewayAuthEndpoints,
        private readonly now: () => number = nowInSeconds,
    ) {}

    /**
     * The backend tokens of a successful sign-in or refresh response, or null
     * when the response carries no refresh cookie.
     */
    tokensFrom(response: Response, body: SignedInBody): BackendTokens | null {
        const refresh = this.cookieSetBy(response, REFRESH_COOKIE);
        if (!refresh || !body.access_token) {
            return null;
        }
        return {
            accessToken: body.access_token,
            accessExpiry: Number(body.token_expiry),
            refreshToken: refresh.value,
            refreshExpiry: refresh.expiry,
        };
    }

    /**
     * Exchanges a refresh token for new tokens. The gateway rotates it: once this
     * succeeds, the token sent is spent, and sending it again signs the user out
     * everywhere (user-service treats reuse as theft). See SessionRefresher.
     *
     * `forwardedFor` is the browser's address, so the gateway's rate limit counts
     * the customer, not the Next server.
     */
    async refresh(refreshToken: string, forwardedFor: string | null): Promise<RefreshOutcome> {
        let response: Response;
        try {
            response = await fetch(this.endpoints.refresh, {
                method: "POST",
                headers: {
                    Cookie: `${REFRESH_COOKIE}=${refreshToken}`,
                    ...(forwardedFor ? { "X-Forwarded-For": forwardedFor } : {}),
                },
                cache: "no-store",
            });
        } catch (error) {
            return { kind: "unavailable", reason: `gateway unreachable: ${String(error)}` };
        }

        if (response.status === 401 || response.status === 403) {
            return { kind: "rejected", status: response.status };
        }
        if (!response.ok) {
            return { kind: "unavailable", reason: `gateway answered ${response.status}` };
        }
        const body = (await response.json()) as SignedInBody;
        const tokens = this.tokensFrom(response, body);
        return tokens
            ? { kind: "refreshed", tokens }
            : { kind: "unavailable", reason: "refresh response carried no refresh cookie" };
    }

    /** Revokes the refresh token. Best effort: a failure leaves it to expire on its own. */
    async logout(refreshToken: string): Promise<void> {
        try {
            const response = await fetch(this.endpoints.logout, {
                method: "POST",
                headers: { Cookie: `${REFRESH_COOKIE}=${refreshToken}` },
                cache: "no-store",
            });
            if (!response.ok) {
                console.warn("Gateway logout answered", response.status);
            }
        } catch (error) {
            console.warn("Gateway logout failed:", error);
        }
    }

    /** A cookie the response set, with its expiry from Max-Age (or Expires). */
    private cookieSetBy(response: Response, name: string): { value: string; expiry: number } | null {
        for (const header of response.headers.getSetCookie()) {
            const [pair, ...attributes] = header.split(";").map((part) => part.trim());
            const separator = pair.indexOf("=");
            if (separator === -1 || pair.slice(0, separator) !== name) {
                continue;
            }
            const value = pair.slice(separator + 1).replace(/^"(.*)"$/, "$1");
            if (!value) {
                return null;
            }
            return { value, expiry: this.expiryOf(attributes) };
        }
        return null;
    }

    private expiryOf(attributes: string[]): number {
        const attribute = (key: string) =>
            attributes.find((entry) => entry.toLowerCase().startsWith(`${key}=`))?.slice(key.length + 1);
        const maxAge = Number(attribute("max-age"));
        if (Number.isFinite(maxAge)) {
            return this.now() + maxAge;
        }
        const expires = Date.parse(attribute("expires") ?? "");
        return Number.isFinite(expires) ? Math.floor(expires / 1000) : 0;
    }
}
