import { decode, encode, type JWT } from "next-auth/jwt";

export interface SessionCookieOptions {
    httpOnly: true;
    sameSite: "lax";
    path: "/";
    secure: boolean;
    maxAge: number;
}

/**
 * NextAuth's session cookie: its name, lifetime, attributes and codec.
 *
 * NextAuth writes it at sign-in; the server reads it on every request
 * (actions/getCurrentUser.ts); the request proxy rewrites it when it refreshes
 * the backend tokens inside (lib/session-proxy.ts). All three go through this
 * one place, so they always agree on the name, the secret and the attributes.
 *
 * Kept free of the auth configuration and of lib/config, so the proxy and the
 * tests can load it without the providers or the app's environment.
 */
export class SessionCookie {
    /** NextAuth's default lifetime. A session ends sooner when its refresh token expires. */
    static readonly MAX_AGE_SECONDS = 30 * 24 * 60 * 60;

    /** NextAuth names the cookie after the scheme of NEXTAUTH_URL (see getToken in next-auth/jwt). */
    static isSecure(): boolean {
        return process.env.NEXTAUTH_URL?.startsWith("https://") ?? false;
    }

    static cookieName(): string {
        return SessionCookie.isSecure() ? "__Secure-next-auth.session-token" : "next-auth.session-token";
    }

    /** The key the cookie is encrypted with; undefined only when the deployment forgot to set one. */
    static secret(): string | undefined {
        return process.env.NEXTAUTH_SECRET || process.env.SECRET_KEY || undefined;
    }

    static options(): SessionCookieOptions {
        return {
            httpOnly: true,
            sameSite: "lax",
            path: "/",
            secure: SessionCookie.isSecure(),
            maxAge: SessionCookie.MAX_AGE_SECONDS,
        };
    }

    static decode(raw: string): Promise<JWT | null> {
        return decode({ token: raw, secret: SessionCookie.requiredSecret() });
    }

    static encode(token: JWT): Promise<string> {
        return encode({ token, secret: SessionCookie.requiredSecret(), maxAge: SessionCookie.MAX_AGE_SECONDS });
    }

    private static requiredSecret(): string {
        const secret = SessionCookie.secret();
        if (!secret) {
            throw new Error("NEXTAUTH_SECRET is not set: the session cookie cannot be read or written");
        }
        return secret;
    }
}
