/**
 * Reads the one-time token an email link carries in the URL fragment
 * (`/activate#token=…`, `/password-reset#token=…`).
 *
 * The backend puts it there on purpose: a browser never sends the fragment to
 * any server, so the token stays out of access logs, proxies and Referer
 * headers. Reading it is the page's job, and once read it is wiped from the
 * address bar so it does not linger in history or get copied along with the URL.
 */
export class FragmentToken {
    static readonly PARAM = "token";

    /** The token, or null when the link has none. Removes it from the URL. Browser only. */
    static consume(): string | null {
        if (typeof window === "undefined") return null;
        const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
        const token = params.get(FragmentToken.PARAM)?.trim();
        if (!token) return null;
        window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
        return token;
    }
}
