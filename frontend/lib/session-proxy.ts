import { NextResponse, type NextRequest } from "next/server";
import type { JWT } from "next-auth/jwt";
import type { SessionCookieOptions } from "@/lib/session-cookie";
import type { SessionRefresher } from "@/lib/session-refresher";

/** How the proxy reads and writes the session cookie (SessionCookie in production). */
export interface SessionCookieCodec {
    cookieName(): string;
    options(): SessionCookieOptions;
    decode(raw: string): Promise<JWT | null>;
    encode(token: JWT): Promise<string>;
}

// NextAuth's own routes write the session cookie themselves (sign-in, sign-out,
// session). A refreshed cookie set here as well could land after theirs: a
// sign-out would be undone, or a new sign-in replaced by the old session.
const NEXTAUTH_ROUTES = "/api/auth/";

/**
 * Keeps a signed-in session's backend access token fresh, before any page or
 * route handler reads it.
 *
 * Server components cannot write cookies, and the server reads the session by
 * decoding the cookie directly (actions/getCurrentUser.ts), so the refresh has
 * to happen here, ahead of rendering. When the access token is about to expire
 * the proxy refreshes it (SessionRefresher), then writes the new session cookie
 * twice: into this request, so the page being rendered already uses the new
 * token, and onto the response, so the browser keeps it.
 *
 * A refresh the gateway refuses ends the session: the cookie is removed from
 * both. A refresh that could not reach the gateway changes nothing; the next
 * request tries again.
 */
export class SessionProxy {
    constructor(
        private readonly refresher: SessionRefresher,
        private readonly cookie: SessionCookieCodec,
        private readonly now: () => number,
    ) {}

    async handle(request: NextRequest): Promise<NextResponse> {
        if (request.nextUrl.pathname.startsWith(NEXTAUTH_ROUTES)) {
            return NextResponse.next();
        }
        const name = this.cookie.cookieName();
        const raw = request.cookies.get(name)?.value;
        if (!raw) {
            return NextResponse.next();
        }

        let token: JWT | null;
        try {
            token = await this.cookie.decode(raw);
        } catch {
            token = null;
        }
        if (!token || typeof token.jwt !== "string") {
            return NextResponse.next();
        }

        const accessExpiry = Number(token.token_expiry);
        if (!this.refresher.isDue(accessExpiry)) {
            return NextResponse.next();
        }

        const refreshToken = typeof token.refresh_token === "string" ? token.refresh_token : null;
        if (!refreshToken) {
            // A session from before refresh tokens were kept: it lasts as long
            // as its access token, then it is over.
            return accessExpiry <= this.now() ? this.endSession(request, name) : NextResponse.next();
        }

        const outcome = await this.refresher.refresh(refreshToken, request.headers.get("x-forwarded-for"));
        switch (outcome.kind) {
            case "refreshed": {
                const refreshed: JWT = {
                    ...token,
                    jwt: outcome.tokens.accessToken,
                    token_expiry: outcome.tokens.accessExpiry,
                    refresh_token: outcome.tokens.refreshToken,
                    refresh_expiry: outcome.tokens.refreshExpiry,
                };
                return this.continueWith(request, name, await this.cookie.encode(refreshed));
            }
            case "rejected":
                return this.endSession(request, name);
            case "unavailable":
                console.warn("Session refresh postponed:", outcome.reason);
                return NextResponse.next();
        }
    }

    private continueWith(request: NextRequest, name: string, value: string): NextResponse {
        // RequestCookies.set rewrites the request's Cookie header, which
        // NextResponse.next passes on to the page or route handler.
        request.cookies.set(name, value);
        const response = NextResponse.next({ request: { headers: request.headers } });
        response.cookies.set(name, value, this.cookie.options());
        return response;
    }

    private endSession(request: NextRequest, name: string): NextResponse {
        request.cookies.delete(name);
        const response = NextResponse.next({ request: { headers: request.headers } });
        response.cookies.set(name, "", { ...this.cookie.options(), maxAge: 0 });
        return response;
    }
}
