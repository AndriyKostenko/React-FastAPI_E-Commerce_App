import { headers } from "next/headers";

/**
 * The browser's address as the edge proxy recorded it, for the gateway's rate
 * limits. A server-side call would otherwise reach the gateway from the
 * frontend's own address, so every user would share one bucket.
 *
 * The gateway reads this header only when the call comes from a trusted proxy
 * network (TRUSTED_PROXY_NETWORKS), so a client cannot pick its own address.
 * Server code only: next/headers is not available in the browser.
 */
export const clientAddressHeaders = async (): Promise<Record<string, string>> => {
    try {
        const forwardedFor = (await headers()).get("x-forwarded-for");
        return forwardedFor ? { "X-Forwarded-For": forwardedFor } : {};
    } catch {
        // Outside a request (for example at build time): nothing to attribute.
        return {};
    }
};
