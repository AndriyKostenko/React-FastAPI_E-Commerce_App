import { isJsonObject, JsonObject, JsonValue } from './json.js';

/** A gateway call that did not succeed, with the status and FastAPI's detail. */
export class GatewayError extends Error {
    constructor(
        readonly status: number,
        readonly detail: string,
    ) {
        super(detail);
    }
}

/** What the browser hands to navigator.credentials.get() / .create(). */
export interface CeremonyOptions {
    readonly challengeId: string;
    readonly options: JsonObject;
}

/** A session's tokens. Held server-side only (see AdminTokenStore). */
export interface AdminTokens {
    readonly accessToken: string;
    // Unix time in milliseconds.
    readonly accessExpiresAt: number;
    readonly refreshToken: string;
}

export interface SignedInAdmin {
    readonly userId: string;
    readonly email: string;
    readonly role: string;
    readonly tokens: AdminTokens;
}

export interface GatewayRequest {
    readonly method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
    readonly accessToken?: string;
    readonly body?: JsonValue | FormData;
    readonly query?: URLSearchParams;
}

const REFRESH_COOKIE = 'refresh_token';

/**
 * The admin panel's only way to the backend: the API gateway, never a
 * service directly, so every call meets the same authentication, admin
 * checks, rate limits and audit trail as any other client.
 */
export class GatewayClient {
    constructor(private readonly apiUrl: string) {}

    // ------------------------------ passkeys ------------------------------

    async passkeySignInOptions(email: string, password: string): Promise<CeremonyOptions> {
        return this.ceremonyOptions(await this.send('/login/passkey/options', { method: 'POST', body: { email, password } }));
    }

    async passkeySignIn(challengeId: string, credential: JsonObject): Promise<SignedInAdmin> {
        const response = await this.raw('/login/passkey/verify', {
            method: 'POST',
            body: { challenge_id: challengeId, credential },
        });
        const body = await this.objectBody(response);
        return {
            userId: this.text(body, 'user_id'),
            email: this.text(body, 'user_email'),
            role: this.text(body, 'user_role'),
            tokens: this.tokens(response, body),
        };
    }

    async passkeyEnrolmentOptions(token: string): Promise<CeremonyOptions> {
        return this.ceremonyOptions(await this.send('/passkeys/enrolment/options', { method: 'POST', body: { token } }));
    }

    async passkeyEnrolment(token: string, challengeId: string, credential: JsonObject, name: string): Promise<JsonObject> {
        const body = await this.send('/passkeys/enrolment/verify', {
            method: 'POST',
            body: { token, challenge_id: challengeId, credential, name },
        });
        if (!isJsonObject(body)) throw new GatewayError(502, 'Unexpected enrolment response');
        return body;
    }

    // ------------------------------ sessions ------------------------------

    /** Trade the refresh token for a new pair; the old refresh token is spent. */
    async refresh(refreshToken: string): Promise<AdminTokens> {
        const response = await this.raw('/refresh', {
            method: 'POST',
            headers: { Cookie: `${REFRESH_COOKIE}=${refreshToken}` },
        });
        return this.tokens(response, await this.objectBody(response));
    }

    /** Revoke the refresh token at user-service. Best effort: the caller signs out regardless. */
    async logout(tokens: AdminTokens): Promise<void> {
        await this.raw('/logout', {
            method: 'POST',
            headers: {
                Authorization: `Bearer ${tokens.accessToken}`,
                Cookie: `${REFRESH_COOKIE}=${tokens.refreshToken}`,
            },
        });
    }

    // ------------------------------ data API ------------------------------

    /** An authenticated JSON call, e.g. from an AdminJS resource. */
    async send(path: string, request: GatewayRequest = {}): Promise<JsonValue | null> {
        const response = await this.raw(path, {
            method: request.method ?? 'GET',
            query: request.query,
            body: request.body,
            headers: request.accessToken ? { Authorization: `Bearer ${request.accessToken}` } : {},
        });
        if (response.status === 204) return null;
        const text = await response.text();
        return text ? (JSON.parse(text) as JsonValue) : null;
    }

    /** An authenticated call whose body is a file (artwork, photos), streamed through. */
    async download(path: string, accessToken: string): Promise<Response> {
        return this.raw(path, { method: 'GET', headers: { Authorization: `Bearer ${accessToken}` } });
    }

    // ------------------------------- helpers ------------------------------

    private async raw(
        path: string,
        init: {
            method: string;
            headers?: Record<string, string>;
            body?: JsonValue | FormData;
            query?: URLSearchParams;
        },
    ): Promise<Response> {
        const url = new URL(`${this.apiUrl}${path}`);
        init.query?.forEach((value, key) => url.searchParams.append(key, value));
        const headers: Record<string, string> = { Accept: 'application/json', ...init.headers };
        let body: string | FormData | undefined;
        if (init.body instanceof FormData) {
            body = init.body;
        } else if (init.body !== undefined) {
            headers['Content-Type'] = 'application/json';
            body = JSON.stringify(init.body);
        }
        let response: Response;
        try {
            response = await fetch(url, { method: init.method, headers, body, redirect: 'error' });
        } catch {
            throw new GatewayError(503, 'The API gateway is not reachable');
        }
        if (!response.ok) {
            throw new GatewayError(response.status, await GatewayClient.detail(response));
        }
        return response;
    }

    private static async detail(response: Response): Promise<string> {
        try {
            const body: JsonValue = await response.json();
            if (isJsonObject(body)) {
                const { detail, errors } = body;
                // The services' error contract: a summary plus the specific
                // problems, e.g. {detail: "Validation request error",
                // errors: [{field, message}]}; the specifics are what an admin needs.
                if (Array.isArray(errors)) {
                    const messages = errors
                        .map((item) => (isJsonObject(item) && typeof item.message === 'string'
                            ? item.message.replace(/^Value error, /, '') : ''))
                        .filter(Boolean);
                    if (messages.length > 0) return messages.join('; ');
                }
                if (typeof detail === 'string') return detail;
                // FastAPI validation errors: a list of {loc, msg}.
                if (Array.isArray(detail)) {
                    return detail
                        .map((item) => (isJsonObject(item) && typeof item.msg === 'string' ? item.msg : ''))
                        .filter(Boolean)
                        .join('; ');
                }
            }
        } catch {
            // not JSON: fall through to the status text
        }
        return `${response.status} ${response.statusText}`;
    }

    private async objectBody(response: Response): Promise<JsonObject> {
        const body: JsonValue = await response.json();
        if (!isJsonObject(body)) throw new GatewayError(502, 'Unexpected response from the API gateway');
        return body;
    }

    private ceremonyOptions(body: JsonValue | null): CeremonyOptions {
        if (!isJsonObject(body) || typeof body.challenge_id !== 'string' || !isJsonObject(body.options)) {
            throw new GatewayError(502, 'Unexpected passkey options from the API gateway');
        }
        return { challengeId: body.challenge_id, options: body.options };
    }

    private text(body: JsonObject, key: string): string {
        const value = body[key];
        if (typeof value !== 'string') throw new GatewayError(502, `Missing ${key} in the gateway response`);
        return value;
    }

    /**
     * The access token comes in the body; the refresh token only as the
     * gateway's HttpOnly cookie, so it is read from Set-Cookie.
     */
    private tokens(response: Response, body: JsonObject): AdminTokens {
        const expiry = body.token_expiry;
        const refreshCookie = response.headers
            .getSetCookie()
            .map((cookie) => cookie.split(';', 1)[0])
            .find((pair) => pair.startsWith(`${REFRESH_COOKIE}=`));
        const refreshToken = refreshCookie?.slice(REFRESH_COOKIE.length + 1).replace(/^"|"$/g, '');
        if (typeof expiry !== 'number' || !refreshToken) {
            throw new GatewayError(502, 'The API gateway did not return a complete session');
        }
        return {
            accessToken: this.text(body, 'access_token'),
            accessExpiresAt: expiry * 1000,
            refreshToken,
        };
    }
}
