import { createHmac, timingSafeEqual } from "node:crypto";
import { SessionCookie } from "@/lib/session-cookie";
import type { SearchParams } from "@/types/auth";

/** The query params carrying the message and its signature. */
export const AUTH_ERROR_PARAM = "authError";
export const AUTH_ERROR_SIGNATURE_PARAM = "authErrorSig";
/** Longest message a link carries; longer ones are cut before signing. */
export const AUTH_ERROR_MAX_LENGTH = 200;

const firstValue = (value: string | string[] | undefined): string | undefined =>
    Array.isArray(value) ? value[0] : value;

/**
 * The /login link a failed Google sign-in lands on, carrying the backend's
 * message for the page to show.
 *
 * The message is signed with the session secret, and the page shows only a
 * message whose signature matches. Without that, anyone could send a link to
 * our login page saying whatever they like ("your account is locked, call ...").
 */
export class AuthErrorLink {
    // Keeps these signatures apart from anything else signed with the same secret.
    private static readonly PURPOSE = "login-error:";

    static url(message: string): string {
        const text = message.slice(0, AUTH_ERROR_MAX_LENGTH);
        const signature = AuthErrorLink.sign(text);
        if (!signature) return "/login";
        const query = new URLSearchParams({ [AUTH_ERROR_PARAM]: text, [AUTH_ERROR_SIGNATURE_PARAM]: signature });
        return `/login?${query.toString()}`;
    }

    /** The message in the link, or undefined when it is missing or was not signed by us. */
    static read(params: SearchParams): string | undefined {
        const text = firstValue(params[AUTH_ERROR_PARAM]);
        const signature = firstValue(params[AUTH_ERROR_SIGNATURE_PARAM]);
        if (!text || !signature || text.length > AUTH_ERROR_MAX_LENGTH) return undefined;

        const expected = AuthErrorLink.sign(text);
        if (!expected) return undefined;
        const given = Buffer.from(signature);
        const wanted = Buffer.from(expected);
        return given.length === wanted.length && timingSafeEqual(given, wanted) ? text : undefined;
    }

    private static sign(text: string): string | undefined {
        const secret = SessionCookie.secret();
        if (!secret) return undefined;
        return createHmac("sha256", secret).update(AuthErrorLink.PURPOSE + text).digest("base64url");
    }
}
